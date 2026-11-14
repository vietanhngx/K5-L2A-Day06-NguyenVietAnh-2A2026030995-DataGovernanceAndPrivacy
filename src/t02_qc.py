"""T02 image-only features and frozen, dev-calibrated QC scores.

No labels are loaded here. Calibration is a separate development command.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.ndimage import label

from .common.image_ops import brightness_stats, laplacian_variance, to_gray


FEATURE_VERSION = "t02-qc-v1"


def image_features(image: np.ndarray) -> dict[str, float]:
    gray = to_gray(image)
    # Lower 65% contains road/objects; no object boxes or scene IDs are used.
    road = gray[int(0.35 * len(gray)):]
    bright_labels, count = label(gray > 245)
    areas = np.bincount(bright_labels.ravel())[1:] if count else np.array([0])
    return {
        "laplacian": laplacian_variance(image),
        "road_p90": float(np.percentile(road, 90)),
        "glare_area": float(areas.max() / gray.size),
        **brightness_stats(image),
    }


def reference_key(camera: str, light: str) -> str:
    return f"{camera}|{light}"


def score_features(features: pd.DataFrame, calibration: dict, method: str) -> pd.DataFrame:
    out = features.copy()
    if method == "laplacian":
        out["score"] = 1.0 / (out.laplacian + 1e-6)
        out["pred_defect_type"] = "blur"
        out["reason"] = "Điểm nghi mờ từ độ nét toàn ảnh (baseline)"
    elif method == "poc":
        refs = calibration["references"]
        defaults = calibration["reference_global"]
        ref_rows = [refs.get(reference_key(r.camera_id, r.light),
                            calibration["reference_by_light"].get(r.light, defaults))
                    for r in out.itertuples(index=False)]
        ref_lap = np.array([r["laplacian"] for r in ref_rows])
        ref_bright = np.array([r["road_p90"] for r in ref_rows])
        anchors = calibration["fixed_cue_anchors"]
        # A ratio of 1 is the fixed warning anchor. Larger = more suspicious.
        out["blur_score"] = float(anchors["blur_reference_fraction"]) * ref_lap / (out.laplacian + 1e-6)
        out["dark_score"] = float(anchors["dark_reference_fraction"]) * (ref_bright + 1) / (out.road_p90 + 1)
        out["glare_score"] = out.glare_area / float(anchors["glare_image_area"])
        cues = out[["blur_score", "dark_score", "glare_score"]]
        out["score"] = cues.max(axis=1)
        winning = cues.idxmax(axis=1)
        out["pred_defect_type"] = winning.map({"blur_score": "blur", "dark_score": "dark", "glare_score": "glare"})
        out["reason"] = winning.map({
            "blur_score": "Độ nét thấp so với ảnh dev cùng camera/điều kiện sáng",
            "dark_score": "Chi tiết vùng đường tối hơn mức tham chiếu dev",
            "glare_score": "Có vùng trắng cháy sáng liền nhau lớn",
        })
    else:
        raise ValueError(f"unknown T02 method: {method}")
    threshold = float(calibration["thresholds"][method])
    out["pred_is_defect"] = (out.score >= threshold).astype(int)
    # Type prediction is only a suspicion; no supervised compression classifier.
    out.loc[out.pred_is_defect == 0, "pred_defect_type"] = "none"
    out["pred_action"] = np.where(out.pred_is_defect == 1, "RECAPTURE", "KEEP")
    out["slice"] = out.camera_id.astype(str) + "/" + out.light.astype(str)
    return out
