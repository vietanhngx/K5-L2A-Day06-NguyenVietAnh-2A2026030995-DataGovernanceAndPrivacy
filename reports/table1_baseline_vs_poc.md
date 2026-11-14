Baseline: `baseline_internal` (git b0ce8bf, seed 42) · PoC: `poc_internal` (git b0ce8bf, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (GT defects in top-B / GT defects) | all | 1.0000 | 1.0000 | 0.0000 | +0.0% | higher | 40 |
| Precision@B (GT defects in top-B / B) | all | 0.3000 | 0.3000 | 0.0000 | +0.0% | higher | 40 |
| Defect-type accuracy (GT defects) (fraction) | all | 0.0000 | 0.1667 | 0.1667 | baseline=0 | higher | 6 |
| False alarm in top-B (clean images in top-B / clean images) | light=day | 0.3529 | 0.5882 | 0.2353 | +66.7% | lower | 20 |
| False alarm in top-B (clean images in top-B / clean images) | light=dusk | 0.5000 | 0.0000 | -0.5000 | -100.0% | lower | 4 |
| False alarm in top-B (clean images in top-B / clean images) | light=night | 0.4667 | 0.2667 | -0.2000 | -42.9% | lower | 16 |
| Runtime / 100 items (s) | all | 0.4284 | 0.4584 | | | lower | |
