"""Freeze T02 parameters using only internal DEV labels; never score eval here.

python -m tools.calibrate_t02 --labels data/manual/t02_manual_labels.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.image_ops import load_rgb
from src.common.io import sha256_file, write_json
from src.t02_qc import FEATURE_VERSION, image_features, reference_key, score_features


def best_threshold(scores: np.ndarray, truth: np.ndarray) -> tuple[float, dict]:
    unique = np.unique(scores)
    candidates = np.r_[np.nextafter(unique[-1], np.inf), unique]
    best = None
    for threshold in candidates:
        pred = scores >= threshold
        tp = int((pred & truth).sum())
        fp = int((pred & ~truth).sum())
        fn = int((~pred & truth).sum())
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        # Ties: fewer false positives, then higher threshold.
        value = (f1, -fp, float(threshold))
        if best is None or value > best[0]:
            best = (value, float(threshold), {"tp": tp, "fp": fp, "fn": fn, "f1": f1})
    return best[1], best[2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--input", default="fixtures/t02_raw_qc")
    ap.add_argument("--output", default="configs/t02_calibration.json")
    args = ap.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Calibration already frozen. Use a new --output for an explicitly new protocol.")
    root = Path(args.input)
    images = pd.read_csv(root / "images.csv")
    images = images[images.split == "dev"].copy()
    # Drop eval rows before inspecting any labels; features are extracted only for dev IDs.
    labels = pd.read_csv(args.labels)
    labels = labels[labels.split == "dev"].copy()
    if labels.image_id.duplicated().any() or set(labels.image_id) != set(images.image_id):
        raise ValueError("DEV labels must cover every dev image exactly once")
    if not (labels.status == "labeled").all() or not labels.is_defect.isin([0, 1]).all():
        raise ValueError("DEV labels must be complete binary labels")
    table = images.merge(labels[["image_id", "is_defect", "image_sha256"]], on="image_id", validate="one_to_one")
    rows = []
    for row in table.to_dict("records"):
        path = root / row["path"]
        if sha256_file(path) != row.pop("image_sha256"):
            raise ValueError(f"Image changed since labeling: {path}")
        rows.append(row | image_features(load_rgb(path)))
    features = pd.DataFrame(rows)
    usable = features[features.is_defect == 0]
    columns = ["laplacian", "road_p90"]
    def median(part):
        return {c: float(part[c].median()) for c in columns}
    calibration = {
        "feature_version": FEATURE_VERSION,
        "fit_split": "dev",
        "n_fit": len(features),
        "n_dev_defects": int(features.is_defect.sum()),
        "dev_labels_sha256": __import__("hashlib").sha256(labels.sort_values("image_id").to_csv(index=False).encode()).hexdigest(),
        "reference_global": median(usable),
        "reference_by_light": {str(k): median(v) for k, v in usable.groupby("light")},
        "references": {reference_key(*k): median(v) for k, v in usable.groupby(["camera_id", "light"])},
        "thresholds": {"laplacian": 1.0, "poc": 1.0},
        "threshold_selection": "Maximum dev binary F1; ties: fewer FP then larger threshold. No eval tuning.",
        "fixed_cue_anchors": {"blur_reference_fraction": 0.25, "dark_reference_fraction": 0.30, "glare_image_area": 0.015},
        "label_source": "Student manual internal reference; not instructor GT",
        "dev_fit_results": {},
    }
    for method in ["laplacian", "poc"]:
        scored = score_features(features, calibration, method)
        threshold, summary = best_threshold(scored.score.to_numpy(), features.is_defect.to_numpy(dtype=bool))
        calibration["thresholds"][method] = threshold
        calibration["dev_fit_results"][method] = summary
    write_json(output, calibration)
    print(f"Frozen {output}: dev N={len(features)}, defects={int(features.is_defect.sum())}; eval unused")
    print(calibration["dev_fit_results"])


if __name__ == "__main__":
    main()
