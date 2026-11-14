"""Evaluate frozen T02 runs against student manual labels, never instructor GT.

Run after the metric contract has been approved. This command does not tune.
python -m tools.evaluate_t02_internal
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src import compare, evaluate
from src.common.io import load_config, read_json, sha256_file, write_json
from src.metrics.classification import prf


def cluster_intervals(table: pd.DataFrame, repetitions: int = 2000) -> dict:
    # IDs identify the source scenes in this synthetic evaluation fixture only.
    # Scene IDs are never provided to the scoring pipeline.
    scenes = table.image_id.str.extract(r"^(img_\d+)_\d+$", expand=False)
    if scenes.isna().any():
        raise ValueError("Cannot identify evaluation scene groups for bootstrap")
    groups = [part for _, part in table.assign(scene=scenes).groupby("scene", sort=True)]
    rng = np.random.default_rng(42)
    recalls, precisions = [], []
    for _ in range(repetitions):
        sample = pd.concat([groups[i] for i in rng.integers(len(groups), size=len(groups))])
        sample = sample.sort_values("score", ascending=False, kind="mergesort")
        positives = int(sample.is_defect.sum())
        hits = int(sample.head(20).is_defect.sum())
        precisions.append(hits / min(20, len(sample)))
        if positives:
            recalls.append(hits / positives)
    def interval(values):
        return [float(x) for x in np.quantile(values, [0.025, 0.975])] if values else None
    return {"method": "source-scene cluster bootstrap, percentile 95%, fixed B=20",
            "repetitions": repetitions, "seed": 42, "n_scenes": len(groups),
            "recall_valid_repetitions": len(recalls), "recall_ci95": interval(recalls),
            "precision_ci95": interval(precisions)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="data/manual/t02_manual_labels.csv")
    ap.add_argument("--output", default="out/internal_eval")
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    labels = pd.read_csv(args.labels)
    images = pd.read_csv("fixtures/t02_raw_qc/images.csv")
    if labels.image_id.duplicated().any() or set(labels.image_id) != set(images.image_id):
        raise ValueError("Manual labels must cover the fixed 96-image pool exactly once")
    if not (labels.status == "labeled").all() or not labels.is_defect.isin([0, 1]).all():
        raise ValueError("Manual labels incomplete")
    if not (labels.is_defect == (labels.severity == 2).astype(int)).all():
        raise ValueError("Manual binary labels conflict with the approved severity policy")
    joined = images.merge(labels, on="image_id", suffixes=("_input", ""), validate="one_to_one")
    for row in joined.itertuples():
        if row.split != row.split_input or sha256_file(Path("fixtures/t02_raw_qc") / row.path) != row.image_sha256:
            raise ValueError(f"Manual labels do not match fixture: {row.image_id}")
    cfg = load_config("configs/lab.yaml")
    calibration_path = Path(cfg["params"]["calibration"])
    calibration = read_json(calibration_path)
    dev = labels[labels.split == "dev"].copy().sort_values("image_id")
    import hashlib
    if hashlib.sha256(dev.to_csv(index=False).encode()).hexdigest() != calibration["dev_labels_sha256"]:
        raise ValueError("DEV labels changed after calibration; explicitly review protocol before evaluating")
    runs = {"random": Path("out/random_baseline/ranked_review.csv"),
            "baseline": Path("out/baseline/ranked_review.csv"), "poc": Path("out/poc/ranked_review.csv")}
    provenance = {
        "evaluation_kind": "student_manual_internal_reference_not_official_GT",
        "eval_is_blind": False,
        "metric_contract_sha256": sha256_file("reports/metric_contract.md"),
        "labels_sha256": sha256_file(args.labels),
        "calibration_sha256": sha256_file(calibration_path),
        "predictions_sha256": {name: sha256_file(path) for name, path in runs.items()},
        "source_sha256": {str(p): sha256_file(p) for folder in ["src", "tools"] for p in sorted(Path(folder).rglob("*.py"))},
        "note": "Dirty working tree code hashes are recorded; git HEAD alone does not identify these changes.",
        "git_status": subprocess.check_output(["git", "status", "--short"], text=True),
    }
    lock = out / "protocol_lock.json"
    if lock.exists():
        old = read_json(lock)
        for key in ["labels_sha256", "calibration_sha256", "predictions_sha256", "metric_contract_sha256"]:
            if old[key] != provenance[key]:
                raise ValueError(f"Frozen evaluation inputs changed: {key}; use a new output and document a new protocol")
    else:
        # Save all fingerprints before the first evaluation.
        write_json(lock, provenance)
    result = {}
    for name, prediction in runs.items():
        pred = pd.read_csv(prediction)
        info = read_json(prediction.parent / "run_info.json")
        if info["seed"] != 42 or not info["offline"] or info["status"] != 0:
            raise ValueError(f"Invalid run metadata: {name}")
        if pred.image_id.duplicated().any() or set(pred.image_id) != set(images.image_id) or not np.isfinite(pred.score).all():
            raise ValueError(f"Invalid prediction pool/scores: {name}")
        metrics_path = out / f"metrics_{name}.json"
        assert evaluate.main(["--track", "t02", "--gt", args.labels, "--pred", str(prediction),
                              "--split", "eval", "--budget", "20", "--run-name", name + "_internal",
                              "--out", str(metrics_path), "--slices-out", str(out / f"slices_{name}.csv")]) == 0
        payload = read_json(metrics_path)
        payload["extra"]["reference_provenance"] = {k: v for k, v in provenance.items() if k not in {"source_sha256", "git_status"}}
        write_json(metrics_path, payload)
        table = labels[labels.split == "eval"].merge(pred, on="image_id", suffixes=("", "_pred"), validate="one_to_one")
        table = table.sort_values("score", ascending=False, kind="mergesort")
        # Independently reconcile the primary numerator/denominator.
        positives = int(table.is_defect.sum())
        hits = int(table.head(20).is_defect.sum())
        primary = next(m for m in payload["metrics"] if m["primary"])
        assert primary["numerator"] == hits and primary["denominator"] == positives
        camera_slices = []
        top = set(table.head(20).image_id)
        for camera, part in table.groupby("camera_id"):
            positive = part[part.is_defect == 1]
            usable = part[part.is_defect == 0]
            found = int(positive.image_id.isin(top).sum())
            false_alarm = int(usable.image_id.isin(top).sum())
            camera_slices.append({"camera_id": camera, "n": len(part), "defects": len(positive),
                                  "hits_in_eval_top20": found, "usable_in_eval_top20": false_alarm,
                                  "recall": found / len(positive) if len(positive) else None})
        pd.DataFrame(camera_slices).to_csv(out / f"camera_slices_{name}.csv", index=False)
        detail = table.copy()
        detail["eval_rank"] = range(1, len(detail) + 1)
        detail["in_eval_top20"] = detail.image_id.isin(top)
        detail.to_csv(out / f"image_results_{name}.csv", index=False)
        result[name] = {
            "eval_n": len(table), "eval_severe_defects": positives,
            "hits_in_top20": hits, "recall_at20": hits / positives if positives else None,
            "precision_at20": hits / 20, "missed_defect_ids": table.loc[(table.is_defect == 1) & ~table.image_id.isin(top), "image_id"].tolist(),
            "usable_in_top20": table.loc[(table.is_defect == 0) & table.image_id.isin(top), "image_id"].tolist(),
            "bootstrap": cluster_intervals(table), "camera_slices": camera_slices,
            "runtime_per_100_items_s": payload["runtime_per_100_items_s"],
        }
        if "pred_is_defect" in table:
            result[name]["threshold_classification"] = prf(table.is_defect, table.pred_is_defect)
    write_json(out / "summary.json", result)
    assert compare.main([str(out / "metrics_baseline.json"), str(out / "metrics_poc.json"),
                         "--out", str(out / "table1_baseline_vs_poc.md")]) == 0
    print("\nInternal evaluation complete. No parameter or label was changed.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
