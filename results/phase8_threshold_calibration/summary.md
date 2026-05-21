# Phase 8A: EfficientAD Raw Threshold Calibration Report

Generated: 2026-05-21 22:58:05

## 1. Phase 8A Goal

Calibrate per-category thresholds for the EfficientAD FP16/raw RKNN model
on MVTec AD 15-class test split. These thresholds control the T2 gate in the
C++ edge pipeline: frames with `final_score > threshold` are passed to T3
(FastSAM + Qwen3-VL) for further analysis; frames below threshold are dropped.

## 2. Execution Environment

- **Board**: Orange Pi 5 16GB (RK3588)
- **Calibration mode**: RKNNLite on-device inference
- **EfficientAD model**: FP16/no-quant raw RKNN (`model.rknn`, ~17MB each)
- **Score mode**: `map_mean`
- **Input CSV**: `results/phase8_threshold_calibration/rknn_scores_15cls.csv`
- **Inference pipeline**: Decode → resize 256x256 → uint8 RGB → RKNNLite

## 3. Data Completeness

All 15 MVTec AD classes verified present on board:

| Category | Good | Defect | Status |
|----------|------|--------|--------|
| bottle | 20 | 63 | OK |
| cable | 58 | 92 | OK |
| capsule | 23 | 109 | OK |
| carpet | 28 | 89 | OK |
| grid | 21 | 57 | OK |
| hazelnut | 40 | 70 | OK |
| leather | 32 | 92 | OK |
| metal_nut | 22 | 93 | OK |
| pill | 26 | 141 | OK |
| screw | 41 | 119 | OK |
| tile | 33 | 84 | OK |
| toothbrush | 12 | 30 | OK |
| transistor | 60 | 40 | OK |
| wood | 19 | 60 | OK |
| zipper | 32 | 119 | OK |

## 4. Model Completeness

All 15 `model.rknn` files verified present (~17MB each), FP16/no-quant raw format.

## 5. Per-Category Statistics

### 5.1 Good Distribution

| Category | Count | Min | Max | Mean | Median | P90 | P95 | P99 |
|----------|-------|-----|-----|------|--------|-----|-----|-----|
| bottle | 20 | 11.49 | 12.37 | 11.89 | 11.89 | 12.20 | 12.31 | 12.36 |
| cable | 58 | 10.55 | 14.54 | 11.78 | 11.60 | 12.70 | 13.44 | 14.37 |
| capsule | 23 | 21.96 | 30.74 | 25.90 | 26.48 | 27.96 | 29.04 | 30.39 |
| carpet | 28 | 15.54 | 18.76 | 17.27 | 17.24 | 18.17 | 18.22 | 18.62 |
| grid | 21 | 18.46 | 31.15 | 24.18 | 23.76 | 29.30 | 29.95 | 30.91 |
| hazelnut | 40 | 67.14 | 194.06 | 122.26 | 118.53 | 168.05 | 176.06 | 187.95 |
| leather | 32 | 232.21 | 320.46 | 282.83 | 291.78 | 308.34 | 313.54 | 318.58 |
| metal_nut | 22 | 37.79 | 42.66 | 40.31 | 40.20 | 41.50 | 42.56 | 42.65 |
| pill | 26 | 30.65 | 80.92 | 43.60 | 35.81 | 66.25 | 73.02 | 79.32 |
| screw | 41 | 11.89 | 13.16 | 12.37 | 12.32 | 12.80 | 12.90 | 13.14 |
| tile | 33 | 8.23 | 14.11 | 11.21 | 11.06 | 12.95 | 13.39 | 14.07 |
| toothbrush | 12 | 7.27 | 22.94 | 16.35 | 20.02 | 21.81 | 22.34 | 22.82 |
| transistor | 60 | 37.58 | 77.31 | 52.15 | 52.04 | 61.82 | 64.36 | 71.74 |
| wood | 19 | 247.44 | 448.03 | 323.06 | 306.91 | 440.54 | 446.51 | 447.73 |
| zipper | 32 | 13.97 | 16.94 | 15.25 | 15.07 | 16.41 | 16.54 | 16.83 |

### 5.2 Defect Distribution

| Category | Count | Min | Max | Mean | Median | P10 | P5 | P1 |
|----------|-------|-----|-----|------|--------|-----|-----|-----|
| bottle | 63 | 11.48 | 212.05 | 17.49 | 12.12 | 11.79 | 11.70 | 11.49 |
| cable | 92 | 10.03 | 15.28 | 11.87 | 11.62 | 10.49 | 10.36 | 10.13 |
| capsule | 109 | 17.42 | 36.36 | 25.20 | 25.05 | 21.93 | 20.44 | 18.49 |
| carpet | 89 | 14.39 | 23.51 | 18.54 | 18.75 | 15.70 | 14.88 | 14.64 |
| grid | 57 | 14.98 | 29.40 | 20.96 | 20.57 | 16.67 | 16.11 | 15.14 |
| hazelnut | 70 | 71.46 | 212.97 | 122.36 | 119.94 | 88.09 | 79.10 | 71.90 |
| leather | 92 | 205.93 | 378.22 | 268.68 | 254.64 | 230.09 | 224.83 | 206.20 |
| metal_nut | 93 | 35.20 | 47.91 | 41.09 | 40.57 | 37.65 | 36.97 | 36.11 |
| pill | 141 | 24.61 | 79.86 | 36.75 | 35.46 | 31.77 | 30.67 | 26.62 |
| screw | 119 | 11.38 | 12.92 | 12.18 | 12.17 | 11.81 | 11.77 | 11.55 |
| tile | 84 | 9.19 | 49.25 | 17.10 | 12.97 | 11.09 | 10.71 | 9.65 |
| toothbrush | 30 | 7.17 | 39.34 | 17.86 | 19.22 | 7.34 | 7.22 | 7.19 |
| transistor | 40 | 34.46 | 72.52 | 46.95 | 45.12 | 39.27 | 39.03 | 35.91 |
| wood | 60 | 145.80 | 341.21 | 243.11 | 253.82 | 164.04 | 154.87 | 150.18 |
| zipper | 119 | 12.52 | 17.26 | 14.53 | 14.29 | 13.29 | 13.03 | 12.64 |

### 5.3 Metrics

| Category | AUROC | Best F1 Thr | Best F1 | Recall@FPR=1% | Recall@FPR=5% | Rec. Threshold | Overlap |
|----------|-------|-------------|---------|---------------|---------------|----------------|---------|
| bottle | 0.7421 | 11.68 | 0.8696 | 0.0159 | 0.0159 | **12.31** | YES |
| cable | 0.4957 | 10.03 | 0.7603 | 0.0109 | 0.0109 | **13.44** | YES |
| capsule | 0.3937 | 17.42 | 0.9046 | 0.0092 | 0.0092 | **29.04** | YES |
| carpet | 0.7263 | 14.39 | 0.8641 | 0.0112 | 0.0112 | **18.22** | YES |
| grid | 0.2857 | 14.98 | 0.8444 | 1.0000 | 0.0000 | **29.95** | YES |
| hazelnut | 0.5114 | 67.29 | 0.7821 | 0.0143 | 0.0143 | **176.06** | YES |
| leather | 0.3512 | 205.93 | 0.8519 | 0.0109 | 0.0109 | **313.54** | YES |
| metal_nut | 0.5538 | 35.20 | 0.8942 | 0.0108 | 0.0108 | **42.56** | YES |
| pill | 0.3399 | 24.61 | 0.9156 | 1.0000 | 0.0000 | **73.02** | YES |
| screw | 0.3505 | 11.38 | 0.8530 | 1.0000 | 0.0000 | **12.90** | YES |
| tile | 0.7918 | 10.61 | 0.8696 | 0.0119 | 0.0119 | **13.39** | YES |
| toothbrush | 0.5361 | 7.17 | 0.8333 | 0.0333 | 0.0333 | **22.34** | YES |
| transistor | 0.2979 | 34.46 | 0.5714 | 1.0000 | 0.0000 | **64.36** | YES |
| wood | 0.1965 | 145.80 | 0.8633 | 1.0000 | 1.0000 | **446.51** | YES |
| zipper | 0.2684 | 12.52 | 0.8815 | 0.0084 | 0.0084 | **16.54** | YES |

## 6. Distribution Overlap Analysis — CRITICAL FINDING

**All 15 categories exhibit severe good/defect distribution overlap.** No category achieves AUROC ≥ 0.80. The best-performing categories are tile (AUROC=0.7918) and bottle (AUROC=0.7421); most categories fall below 0.55.

**Root cause**: The EfficientAD-S model was trained with Anomalib's post-processing pipeline (clip raw values to [0,300], normalize to [0,1], apply Sigmoid) which creates calibrated anomaly scores. The raw model output (before post-processing) is NOT a well-calibrated anomaly score. The post-processor cannot run on RKNN due to INT8/FLOAT type incompatibility in the `Greater` node, and the Clip+Normalize+Sigmoid post-processing saturates when applied to FP16 output.

**Implication for T2 gate**: With `map_mean` score mode, the T2 gate threshold can only control how many frames enter T3, but cannot reliably separate good from defective images. Setting the threshold at `good_p95` means ~5% of good images will trigger T3, while the defect pass-through rate depends on the defect type and severity.

**Potential improvement paths** (not implemented in Phase 8A):
1. Try `raw_score` (ReduceMax) or `map_top01` (top-0.1% mean) as alternative score modes — these may better capture localized defects without dilution from normal regions.
2. Implement a simplified post-processor in C++ that applies the Sigmoid normalization without the problematic `Greater` node.
3. Re-calibrate thresholds on real production data where defect characteristics may differ from MVTec AD.

The following categories have severe good/defect distribution overlap
(AUROC < 0.80 or good_p99 >= defect_p5):

- **bottle**: AUROC=0.7421, good_p99=12.36, defect_p5=11.70
- **cable**: AUROC=0.4957, good_p99=14.37, defect_p5=10.36
- **capsule**: AUROC=0.3937, good_p99=30.39, defect_p5=20.44
- **carpet**: AUROC=0.7263, good_p99=18.62, defect_p5=14.88
- **grid**: AUROC=0.2857, good_p99=30.91, defect_p5=16.11
- **hazelnut**: AUROC=0.5114, good_p99=187.95, defect_p5=79.10
- **leather**: AUROC=0.3512, good_p99=318.58, defect_p5=224.83
- **metal_nut**: AUROC=0.5538, good_p99=42.65, defect_p5=36.97
- **pill**: AUROC=0.3399, good_p99=79.32, defect_p5=30.67
- **screw**: AUROC=0.3505, good_p99=13.14, defect_p5=11.77
- **tile**: AUROC=0.7918, good_p99=14.07, defect_p5=10.71
- **toothbrush**: AUROC=0.5361, good_p99=22.82, defect_p5=7.22
- **transistor**: AUROC=0.2979, good_p99=71.74, defect_p5=39.03
- **wood**: AUROC=0.1965, good_p99=447.73, defect_p5=154.87
- **zipper**: AUROC=0.2684, good_p99=16.83, defect_p5=13.03

For these categories, the recommended threshold is based on good_p95
(more permissive) rather than good_p99. Detection reliability is lower;
real-world calibration with production data is strongly recommended.

## 7. Configuration Update

### Recommended `per_category_threshold` for `edge/config.yaml`:

```yaml
# Preliminary thresholds calibrated on MVTec test split using Orange Pi RKNN raw EfficientAD.
# Not production-certified.
per_category_threshold:
  bottle: 12.31
  cable: 13.44
  capsule: 29.04
  carpet: 18.22
  grid: 29.95
  hazelnut: 176.06
  leather: 313.54
  metal_nut: 42.56
  pill: 73.02
  screw: 12.90
  tile: 13.39
  toothbrush: 22.34
  transistor: 64.36
  wood: 446.51
  zipper: 16.54
```

## 8. ONNX PC Reference (Supplementary)

PC ONNX calibration was run on the same 15-class MVTec test set as a reference
(output: `onnx_scores_15cls.csv`). ONNX results are **not used for threshold
selection** — only RKNN on-board scores are authoritative for edge deployment.

### ONNX vs RKNN AUROC Comparison (map_mean)

| Category | RKNN AUROC | ONNX AUROC | Delta |
|----------|-----------|-----------|-------|
| bottle | 0.7421 | 0.7421 | 0.0000 |
| cable | 0.4957 | 0.4955 | 0.0002 |
| capsule | 0.3937 | 0.3941 | -0.0004 |
| carpet | 0.7263 | 0.7267 | -0.0004 |
| grid | 0.2857 | 0.2857 | 0.0000 |
| hazelnut | 0.5114 | 0.5111 | 0.0003 |
| leather | 0.3512 | 0.3512 | 0.0000 |
| metal_nut | 0.5538 | 0.5533 | 0.0005 |
| pill | 0.3399 | 0.3399 | 0.0000 |
| screw | 0.3505 | 0.3743 | -0.0238 |
| tile | 0.7918 | 0.7922 | -0.0004 |
| toothbrush | 0.5361 | 0.5361 | 0.0000 |
| transistor | 0.2979 | 0.2983 | -0.0004 |
| wood | 0.1965 | 0.1965 | 0.0000 |
| zipper | 0.2684 | 0.2684 | 0.0000 |

**Key finding**: ONNX and RKNN AUROC values are nearly identical (max delta 0.024
for screw). This confirms that the poor discrimination is inherent to the raw
EfficientAD output, NOT caused by RKNN FP16 quantization loss.

## 9. Disclaimers

1. These thresholds are calibrated on MVTec AD test split images only.
2. They are NOT industrial production-certified thresholds.
3. Real-world deployment requires calibration with production-line data
   from the actual inspection environment.
4. Score distribution on real industrial images may differ significantly
   from MVTec AD due to different lighting, backgrounds, and defect types.
5. ONNX PC scores and RKNN on-board scores may differ due to FP16 precision;
   only RKNN scores should be used for edge deployment thresholds.

## 9. Threshold Strategy

The recommended threshold prioritizes controlling good false positives:

1. **Primary**: `good_p99` — at most 1% of good images score above threshold.
2. **Fallback** (severe overlap): `good_p95` — at most 5% of good images above threshold.
3. **Alternative**: `best_f1_threshold` — maximizes F1 score on test split.

All three are reported for each category in the summary CSV.
The `recommended_threshold` column uses the strategy described above.
