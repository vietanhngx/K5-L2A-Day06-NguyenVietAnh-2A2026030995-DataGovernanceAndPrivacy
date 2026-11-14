"""YOUR PoC PIPELINE — this is the file your group owns.

Lab contract = 5 automated steps, run by `python -m src.main ...`:
    01 load      input + provenance check (manifest.csv)
    02 process   your algorithm / model (the research part)
    03 rank      prioritise for a fixed review budget B
    04 review    human-in-the-loop: queue -> reviewer decisions -> overrides + audit log
    05 decide    GO / HOLD / REWORK (or track equivalent) with reason_code + owner, write outputs

Required output: out/<pred_file> with the columns listed for your track in
docs/tracks/TXX.md (also in src/metrics/tracks.py::TRACKS). Then evaluate with
    python -m src.evaluate --track tXX --pred out/<pred_file>

Rules: never read fixtures/*/gt/ here (the GT guard will stop you); seed everything via ctx.rng;
no network calls; fail loudly on missing models instead of downloading.
See src/examples/random_baseline.py for a minimal end-to-end wiring example.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import json

from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import load_rgb
from .common.io import read_json, sha256_file, sha256_text
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track
from .t02_qc import FEATURE_VERSION, image_features, score_features
from .t02_review_page import render


# ---------------------------------------------------------------- 01 load
def load(ctx: RunContext) -> dict:
    if ctx.track != "t02":
        raise NotImplementedError("This individual project implements T02 only")
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    data = {"manifest": pd.read_csv(manifest) if manifest.exists() else None}
    images = pd.read_csv(ctx.input_dir / "images.csv", dtype=str)
    required = {"image_id", "path", "camera_id", "light", "split"}
    if not required.issubset(images.columns) or images.empty:
        raise ValueError("images.csv must contain nonempty image_id/path/camera_id/light/split")
    if images.image_id.duplicated().any() or images[list(required)].isna().any().any():
        raise ValueError("images.csv has missing fields or duplicate image_id")
    root = ctx.input_dir.resolve()
    manifested = set(data["manifest"].path) if data["manifest"] is not None else set()
    for path in images.path:
        full = (root / path).resolve()
        if not full.is_relative_to(root) or not full.is_file():
            raise ValueError(f"Unsafe or missing image path: {path}")
        if ctx.config.get("strict_provenance", True) and path not in manifested:
            raise ValueError(f"Image not covered by manifest: {path}")
    calibration_path = ctx.param("calibration", "configs/t02_calibration.json")
    calibration = read_json(calibration_path)
    if calibration.get("feature_version") != FEATURE_VERSION or calibration.get("fit_split") != "dev":
        raise ValueError("Calibration must match the feature version and use dev only")
    ctx.stats["calibration_sha256"] = sha256_file(calibration_path)
    data.update(images=images, calibration=calibration)
    return data


# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    rows = []
    for row in data["images"].to_dict("records"):
        try:
            features = image_features(load_rgb(ctx.input_dir / row["path"]))
        except OSError as exc:
            raise ValueError(f"Cannot decode image {row['path']}: {exc}") from exc
        rows.append(row | features)
    method = ctx.stats.get("method", "poc")
    result = score_features(pd.DataFrame(rows), data["calibration"], method)
    if not np.isfinite(result.score).all():
        raise ValueError("QC scores must be finite")
    result.to_csv(ctx.out("raw_predictions.csv"), index=False)
    ctx.stats["method"] = method
    return result


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    """Default: top-B by `score`. Adapt id/score/reason columns to your track."""
    budget = int(ctx.param("budget", 20))
    if "score" not in scored.columns:
        raise ValueError("rank(): process() output needs a numeric `score` column (higher = review first), "
                         "or adapt rank() to your track")
    if budget <= 0:
        raise ValueError("Review budget must be positive")
    q = make_review_queue(scored, id_col="image_id", score_col="score", budget=budget,
                          reason_col="reason", action_col="pred_action", slice_col="slice", evidence_col="path")
    write_review_queue(q, ctx.out("review_queue.csv"))
    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """If a reviewed queue exists (out/review_queue_reviewed.csv), apply it. Otherwise pass through.

    TODO: decide what an `edit` / `reject` means for your track and apply it
    (e.g. via common.review.apply_overrides), logging every change to ctx.audit.
    """
    final = scored.copy()
    final["model_action"] = final["pred_action"]
    # A machine suggestion is not a human approval.
    final["pred_action"] = "HOLD"
    final["review_status"] = "unreviewed"
    final["reviewer"] = ""
    reviewed = None
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        if reviewed.item_id.duplicated().any() or not set(reviewed.item_id).issubset(set(queue.item_id)):
            raise ValueError("Reviewed rows must be unique and belong to the current top-B queue")
        queued = queue.set_index("item_id")
        latest = {}
        for event in ctx.audit.read():
            if event["action"] == "human_review":
                latest[event["item_id"]] = event.get("extra", {}).get("review_signature")
        validated = []
        for row in reviewed.to_dict("records"):
            ident, decision = row["item_id"], row["reviewer_decision"]
            expected = queued.loc[ident]
            if row["suggested_action"] != expected.suggested_action or not np.isclose(float(row["score"]), expected.score, atol=1e-6):
                raise ValueError(f"Reviewed CSV is stale for {ident}; review the current queue")
            action = "HOLD" if decision == "skip" else str(expected.suggested_action)
            if decision in {"edit", "reject"}:
                action = row["override_value"].strip().upper()
                if action not in {"KEEP", "RECAPTURE"}:
                    raise ValueError("An edit/reject must specify KEEP or RECAPTURE")
            elif decision == "escalate":
                action = "HOLD"
            validated.append((row, action))
        # Validate the entire file before applying/logging any decisions.
        for row, action in validated:
            ident, decision = row["item_id"], row["reviewer_decision"]
            expected = queued.loc[ident]
            mask = final.image_id == ident
            status = "confirmed" if decision in {"approve", "edit", "reject"} else "escalated" if decision == "escalate" else "skipped"
            final.loc[mask, ["pred_action", "review_status", "reviewer"]] = [action, status, row["reviewer"]]
            signature = sha256_text(json.dumps(row, sort_keys=True))
            if latest.get(ident) != signature:
                ctx.audit.log(actor=row["reviewer"], action="human_review", item_id=ident,
                              before=str(expected.suggested_action), after=action,
                              reason=row["review_note"], review_signature=signature,
                              reviewer_decision=decision)
    ctx.stats["n_reviewed"] = int((final.review_status == "confirmed").sum())
    ctx.stats["n_queue"] = len(queue)
    final["final_is_defect"] = final.pred_action.map({"KEEP": 0, "RECAPTURE": 1}).astype("Int64")
    render(queue, ctx.out("contact_sheet.html"), ctx.input_dir, reviewed)
    final.to_csv(ctx.out("final_actions.csv"), index=False)
    return final


# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    evidence = [str(ctx.out(name)) for name in ["review_queue.csv", "final_actions.csv", "audit_log.jsonl"]]
    metrics = {"queue_size": ctx.stats.get("n_queue", 0), "confirmed_reviews": ctx.stats.get("n_reviewed", 0)}
    if not ctx.param("review_gate_approved", False):
        status, code, reason = "HOLD", "AWAITING_POLICY_APPROVAL", "Chờ bạn duyệt chính sách quyết định; các lựa chọn từng ảnh đã được lưu riêng nếu có."
    elif metrics["confirmed_reviews"] < metrics["queue_size"]:
        status, code, reason = "HOLD", "REVIEW_INCOMPLETE", "Hàng chờ còn ảnh chưa có quyết định cuối cùng của người duyệt."
    elif ((final.review_status == "confirmed") & (final.pred_action == "RECAPTURE")).any():
        status, code, reason = "RECAPTURE", "CONFIRMED_SEVERE_DEFECT", "Người duyệt xác nhận có ảnh cần chụp lại trong hàng chờ."
    else:
        status, code, reason = "KEEP", "REVIEWED_QUEUE_USABLE", "Người duyệt xác nhận các ảnh trong hàng chờ dùng được; không kết luận các ảnh ngoài hàng chờ."
    return Decision(status=status, reason_code=code, reason=reason,
                    owner=ctx.config["owner"], scope="t02:review_queue", evidence=evidence, metrics=metrics)


def run_method(ctx: RunContext, method: str) -> None:
    spec = get_track(ctx.track)
    ctx.stats["method"] = method
    ctx.audit.log(actor="pipeline", action="run_started", item_id=ctx.track,
                  after={"method": method, "seed": ctx.seed})
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    final[spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]].to_csv(ctx.out(spec.pred_file), index=False)
    write_decision(decide(ctx, final), ctx.out("decision.json"), ctx.out("decision_log.csv"))


def run(ctx: RunContext) -> None:
    run_method(ctx, "poc")
