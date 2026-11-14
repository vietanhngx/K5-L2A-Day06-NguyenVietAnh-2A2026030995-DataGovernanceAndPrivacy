"""Individual T02 tests: offline output, human corrections, provenance failures."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image, ImageFilter

from src import main as runner
from src.common.context import RunContext
from src.common.io import load_config
from src.common.review import AuditLog
from src.pipeline import decide, load, process, rank, review
from src.t02_qc import image_features


def context(tmp_path):
    return RunContext("t02", Path("fixtures/t02_raw_qc"), tmp_path,
                      load_config("configs/lab.yaml"), 42, np.random.default_rng(42),
                      audit=AuditLog(tmp_path / "audit_log.jsonl"))


def test_features_detect_blur_dark_and_local_glare():
    pixels = np.zeros((80, 120, 3), dtype=np.uint8) + 120
    pixels[::4, ::4] = 240
    base = image_features(pixels)
    blurred = image_features(np.asarray(Image.fromarray(pixels).filter(ImageFilter.GaussianBlur(3))))
    assert blurred["laplacian"] < base["laplacian"]
    assert image_features(pixels // 5)["road_p90"] < base["road_p90"]
    pixels[30:50, 40:60] = 255
    assert image_features(pixels)["glare_area"] == pytest.approx(400 / (80 * 120))


def test_poc_runs_offline_and_repeats_exact_ranking(tmp_path):
    for name in ["first", "second"]:
        assert runner.main(["--track", "t02", "--output", str(tmp_path / name), "--offline", "--seed", "42"]) == 0
    first, second = tmp_path / "first", tmp_path / "second"
    assert (first / "ranked_review.csv").read_bytes() == (second / "ranked_review.csv").read_bytes()
    ranked = pd.read_csv(first / "ranked_review.csv")
    queue = pd.read_csv(first / "review_queue.csv")
    assert len(ranked) == 96 and ranked.image_id.nunique() == 96
    assert np.isfinite(ranked.score).all() and len(queue) == 20
    assert set(queue.item_id) == set(ranked.nlargest(20, "score").image_id)
    assert (ranked.pred_action == "HOLD").all()
    assert ranked.final_is_defect.isna().all()
    assert json.loads((first / "decision.json").read_text(encoding="utf-8"))["status"] == "HOLD"
    assert "data:image/jpeg;base64," in (first / "contact_sheet.html").read_text(encoding="utf-8")


def test_human_override_preserves_raw_and_audit_is_idempotent(tmp_path):
    ctx = context(tmp_path)
    scored = process(ctx, load(ctx))
    raw = (tmp_path / "raw_predictions.csv").read_bytes()
    queue = rank(ctx, scored)
    reviewed = queue.iloc[:2].copy()
    reviewed.loc[:, "reviewer"] = "Test reviewer (automated test only)"
    reviewed.loc[:, "reviewer_decision"] = "edit"
    reviewed.loc[:, "override_value"] = "KEEP"
    reviewed.loc[:, "review_note"] = "Synthetic test of the override path"
    reviewed.to_csv(tmp_path / "review_queue_reviewed.csv", index=False)
    final = review(ctx, scored, queue)
    assert (final.loc[final.image_id.isin(reviewed.item_id), "pred_action"] == "KEEP").all()
    assert (final.loc[~final.image_id.isin(reviewed.item_id), "pred_action"] == "HOLD").all()
    assert (tmp_path / "raw_predictions.csv").read_bytes() == raw
    assert len(ctx.audit.read()) == 2
    review(ctx, scored, queue)
    assert len(ctx.audit.read()) == 2


@pytest.mark.parametrize("problem", ["duplicate", "outside_queue", "bad_action", "missing_reviewer", "stale_score"])
def test_review_rejects_invalid_or_stale_decisions(tmp_path, problem):
    ctx = context(tmp_path)
    scored = process(ctx, load(ctx))
    queue = rank(ctx, scored)
    reviewed = queue.iloc[:1].copy()
    reviewed.loc[:, "reviewer"] = "Test only"
    reviewed.loc[:, "reviewer_decision"] = "edit"
    reviewed.loc[:, "override_value"] = "KEEP"
    if problem == "duplicate":
        reviewed = pd.concat([reviewed, reviewed])
    elif problem == "outside_queue":
        reviewed.loc[:, "item_id"] = "not_in_queue"
    elif problem == "bad_action":
        reviewed.loc[:, "override_value"] = "delete"
    elif problem == "missing_reviewer":
        reviewed.loc[:, "reviewer"] = ""
    elif problem == "stale_score":
        reviewed.loc[:, "score"] = -1.0
    reviewed.to_csv(tmp_path / "review_queue_reviewed.csv", index=False)
    with pytest.raises(ValueError):
        review(ctx, scored, queue)
    assert not ctx.audit.read()


def test_missing_input_file_fails_provenance_check(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    manifest = pd.read_csv("fixtures/t02_raw_qc/manifest.csv").head(1)
    manifest.to_csv(root / "manifest.csv", index=False)
    ctx = context(tmp_path)
    ctx.input_dir = root
    with pytest.raises(ValueError, match="provenance check failed"):
        load(ctx)


def test_laplacian_baseline_has_same_contract(tmp_path):
    assert runner.main(["--track", "t02", "--pipeline", "src.baseline_t02",
                        "--output", str(tmp_path), "--offline"]) == 0
    scored = pd.read_csv(tmp_path / "raw_predictions.csv")
    np.testing.assert_allclose(scored.score, 1 / (scored.laplacian + 1e-6))


def test_decision_gate_is_scoped_and_requires_explicit_approval(tmp_path):
    ctx = context(tmp_path)
    ctx.config["params"]["review_gate_approved"] = False
    final = pd.DataFrame({"review_status": ["confirmed", "confirmed"], "pred_action": ["KEEP", "KEEP"]})
    ctx.stats.update(n_queue=2, n_reviewed=2)
    assert decide(ctx, final).reason_code == "AWAITING_POLICY_APPROVAL"
    # Test-only opt-in: does not change the working configuration.
    ctx.config["params"]["review_gate_approved"] = True
    assert decide(ctx, final).status == "KEEP"
    assert decide(ctx, final).scope == "t02:review_queue"
    final.loc[0, "pred_action"] = "RECAPTURE"
    assert decide(ctx, final).status == "RECAPTURE"
    ctx.stats["n_reviewed"] = 1
    assert decide(ctx, final).reason_code == "REVIEW_INCOMPLETE"


def test_invalid_second_review_does_not_leave_partial_audit(tmp_path):
    ctx = context(tmp_path)
    scored = process(ctx, load(ctx))
    queue = rank(ctx, scored)
    reviewed = queue.iloc[:2].copy()
    reviewed.loc[:, "reviewer"] = "Test only"
    reviewed.loc[:, "reviewer_decision"] = "edit"
    reviewed.loc[:, "override_value"] = "KEEP"
    reviewed.loc[reviewed.index[1], "override_value"] = "invalid"
    reviewed.to_csv(tmp_path / "review_queue_reviewed.csv", index=False)
    with pytest.raises(ValueError):
        review(ctx, scored, queue)
    assert ctx.audit.read() == []
