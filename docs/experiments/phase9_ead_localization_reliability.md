# Phase 9: EfficientAD Heatmap Localization Reliability Report

**Date**: 2026-05-25
**Stage**: 0.5 + 0.6 Board PRE-STAGE
**Hardware**: Orange Pi 5 Plus (RK3588 16GB), NPU CORE_0
**RKNN Runtime**: librknnrt 2.3.2, driver 0.9.8

---

## 1. Objective

Before modifying the C++ pipeline (Stage 1), verify whether EfficientAD-S `raw_anomaly_map` provides
reliable spatial localization for defect bounding boxes across MVTec AD categories.

## 2. Methodology

- **Model**: EfficientAD-S FP16/no-quant RKNN (`model.rknn`, per-category)
- **Input**: uint8 [0,255] NHWC, 256x256 resize (bilinear, no letterbox)
- **Preprocessing**: RKNN driver applies ImageNet normalization (mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375])
- **Bbox extraction**: percentile threshold (p70/p80/p90/p95) + 4-connected components + min_area filter + top-1 by mean score
- **Evaluation**: IoU(EAD bbox, GT mask bbox), peak_in_gt (max pixel inside GT region)
- **Test set**: MVTec test split, 1 image per defect type per category (5 defect types per category)
- **GT source**: MVTec ground_truth pixel masks → bounding rectangle

## 3. Critical Bug Found: Preprocessing Mismatch

**float32 [0,1] input (WRONG)**: anomaly map mean=257.5, max=337.5 (saturated, near-constant)
**uint8 [0,255] input (CORRECT)**: anomaly map mean=15-17, max=30-35 (correct range)

The RKNN model was converted with `mean_values`/`std_values` expecting uint8 [0,255] input.
Passing float32 [0,1] bypasses the normalization, producing degenerate outputs.
This was the root cause of Stage 0.5 initial FAIL before correction.

## 4. Results Summary

| category   | type    | n | mean_iou | peak_in_gt | diff_mean | judgement |
|------------|---------|---|----------|------------|-----------|-----------|
| carpet     | texture | 5 | 0.0006   | 0/5        | 1.30      | FAIL      |
| capsule    | object  | 5 | 0.2425   | 2/5        | 595.04    | PASS      |
| cable      | object  | 5 | 0.2186   | 3/5        | 56.95     | PASS      |
| metal_nut  | object  | 4 | 0.0103   | 1/4        | 120.98    | FAIL      |
| pill       | object  | 5 | 0.0419   | 0/5        | 100.15    | FAIL      |
| screw      | object  | 5 | 0.0091   | 0/5        | 23.27     | FAIL      |

**PASS criteria**: mean IoU > 0.2

## 5. Per-Category Analysis

### carpet (FAIL — mean IoU 0.0006)

The anomaly map is diffuse and nearly uniform across the carpet texture.
The max anomaly pixel NEVER falls inside the GT region (0/5).
Root cause: carpet's woven texture generates widespread low-level anomaly activation,
drowning out the localized defect signal. diff (max-min) is only 1.30 — essentially no spatial discrimination.

| defect_type | IoU   | peak_in_gt | diff  |
|-------------|-------|------------|-------|
| color       | 0.003 | False      | 1.30  |
| cut         | 0.000 | False      | 1.20  |
| hole        | 0.000 | False      | 1.25  |
| metal_cont  | 0.000 | False      | 1.35  |
| thread      | 0.000 | False      | 1.40  |

### capsule (PASS — mean IoU 0.2425)

Large, high-contrast defects (squeeze: 0.56, scratch: 0.30, poke: 0.30) produce well-localized heatmaps.
Small/subtle defects (crack: 0.001) still fail — the model is distracted by capsule tip geometry.
diff = 595 — strong spatial signal.

| defect_type    | IoU   | peak_in_gt | diff   |
|----------------|-------|------------|--------|
| squeeze        | 0.562 | True       | 681.09 |
| scratch        | 0.298 | True       | 705.09 |
| poke           | 0.298 | False      | 454.84 |
| faulty_imprint | 0.054 | False      | 540.09 |
| crack          | 0.001 | False      | 594.09 |

### cable (PASS — mean IoU 0.2186)

Cable swap (0.38), cut_inner (0.37), combined (0.34) show good localization.
bent_wire and cut_outer fail — the model detects the wrong region.
diff = 57 — moderate spatial signal.

| defect_type         | IoU   | peak_in_gt | diff  |
|---------------------|-------|------------|-------|
| cable_swap          | 0.376 | True       | 46.20 |
| cut_inner_insulation| 0.374 | True       | 79.05 |
| combined            | 0.344 | True       | 59.55 |
| bent_wire           | 0.000 | False      | 52.48 |
| cut_outer_insulation| 0.000 | False      | 47.48 |

### metal_nut (FAIL — mean IoU 0.0103)

Only flip (0.037) shows any overlap. The model consistently activates at the center
of the image rather than at the defect location. diff = 121 but spatial signal is not
correlated with defect position.

### pill (FAIL — mean IoU 0.0419)

Only combined (0.209) shows marginal overlap. The model activates at the pill edges
rather than at the defect surface. diff = 100 but spatial signal is not defect-localized.

### screw (FAIL — mean IoU 0.0091)

All defect types show near-zero IoU. The model produces a nearly uniform anomaly map.
diff = 23 — very weak spatial signal. Screw's fine thread structure may be below
the model's effective spatial resolution at 256x256.

## 6. Key Findings

1. **Spatial discrimination (diff) is necessary but not sufficient for localization.**
   metal_nut has diff=121 but IoU=0.01. The spatial signal exists but is not correlated with defect position.

2. **Localization reliability is defect-type dependent, not just category dependent.**
   Within capsule, squeeze (0.56 IoU) works but crack (0.001 IoU) fails completely.

3. **Large, high-contrast, spatially concentrated defects are reliably localized.**
   capsule squeeze, cable swap/cut_inner — these are defects that occupy a distinct region.

4. **Texture classes (carpet) and fine-grained defects (screw threads, pill color) are NOT reliably localized.**
   The anomaly map is too diffuse or the defect is below the model's spatial resolution.

5. **EAD bbox cannot serve as a global primary localization signal.**
   Only 2/6 categories pass the IoU > 0.2 threshold, and even within PASS categories,
   individual defect types can fail.

## 7. Recommendation

- Do NOT replace FastSAM/VLM bbox with EAD bbox as the primary localization signal.
- The `raw_anomaly_map` retains value as a diagnostic/auxiliary signal.
- Frontend bbox overlay should be labeled "proposal bbox" (not "detection" or "localization").
- For texture categories, display a caveat that bbox is image-level anomaly, not reliable localization.
- Future work: per-category threshold tuning, or EAD bbox as FastSAM refinement signal (IoU fusion).

## 8. Overlay Paths

All overlays saved to board: `/tmp/ead_verify/output/` (carpet) and `/tmp/ead_stage06/output/` (all categories).

Carpet corrected overlays: `/tmp/ead_overlays/corrected_*.png`
Capsule/cable overlays: `/tmp/ead_stage06_overlays/`
