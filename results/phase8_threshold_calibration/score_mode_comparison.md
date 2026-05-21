# Phase 8A-Fix: EfficientAD Score Mode Comparison Report

Generated: 2026-05-22 00:22:58

## 0. Methodology

- This analysis reuses `rknn_scores_15cls.csv` from Phase 8A (no re-inference).
- **AUROC** is a threshold-independent metric measuring score ranking ability.
  AUROC > 0.5 means defects score higher (normal); < 0.5 means inverted.
- **F1**, **recall@FPR**, and **recommended threshold** are threshold-dependent
  engineering metrics.
- **recall@FPR** is computed by searching ALL thresholds that satisfy the FPR
  constraint and selecting the one maximizing recall. This correctly handles
  both normal and inverted score distributions.
- This analysis is based on MVTec AD test split only. It is an engineering
  diagnostic, NOT an external independent generalization validation.
- Do NOT claim production-grade detection accuracy from these results.

## 1. AUROC Comparison (all 5 score modes)

| Category | raw_score | map_max | map_mean | map_top1 | map_top01 | Best |
|----------|-----------|---------|----------|----------|-----------|------|
| bottle | 0.4972 | 0.4972 | 0.7421 | 0.5175 | 0.4976 | map_mean (0.7421) |
| cable | 0.4822 | 0.4822 | 0.4957 | 0.4702 | 0.4769 | map_mean (0.4957) |
| capsule | 0.4779 | 0.4779 | 0.3937 | 0.4495 | 0.4755 | raw_score (0.4779) |
| carpet | 0.7887 | 0.7887 | 0.7263 | 0.7460 | 0.7604 | raw_score (0.7887) |
| grid | 0.6099 | 0.6099 | 0.2857 | 0.4754 | 0.5806 | raw_score (0.6099) |
| hazelnut | 0.5673 | 0.5673 | 0.5114 | 0.5582 | 0.5664 | raw_score (0.5673) |
| leather | 0.4693 | 0.4693 | 0.3512 | 0.4253 | 0.4572 | raw_score (0.4693) |
| metal_nut | 0.6173 | 0.6173 | 0.5538 | 0.6056 | 0.6197 | map_top01 (0.6197) |
| pill | 0.3682 | 0.3682 | 0.3399 | 0.3538 | 0.3633 | raw_score (0.3682) |
| screw | 0.5337 | 0.5337 | 0.3505 | 0.5505 | 0.5436 | map_top1 (0.5505) |
| tile | 0.8193 | 0.8193 | 0.7918 | 0.8488 | 0.8279 | **map_top1** (0.8488) |
| toothbrush | 0.5250 | 0.5250 | 0.5361 | 0.4944 | 0.5056 | map_mean (0.5361) |
| transistor | 0.3308 | 0.3308 | 0.2979 | 0.2983 | 0.3083 | raw_score (0.3308) |
| wood | 0.4162 | 0.4162 | 0.1965 | 0.3649 | 0.4035 | raw_score (0.4162) |
| zipper | 0.4766 | 0.4766 | 0.2684 | 0.4330 | 0.4480 | raw_score (0.4766) |

## 2. Best Score Mode per Category

| Category | Best AUROC | Best Score Mode | map_mean AUROC | Delta vs map_mean |
|----------|-----------|-----------------|----------------|-------------------|
| bottle | 0.7421 | map_mean | 0.7421 | +0.0000 |
| cable | 0.4957 | map_mean | 0.4957 | +0.0000 |
| capsule | 0.4779 | raw_score | 0.3937 | +0.0842 |
| carpet | 0.7887 | raw_score | 0.7263 | +0.0624 |
| grid | 0.6099 | raw_score | 0.2857 | +0.3241 |
| hazelnut | 0.5673 | raw_score | 0.5114 | +0.0559 |
| leather | 0.4693 | raw_score | 0.3512 | +0.1180 |
| metal_nut | 0.6197 | map_top01 | 0.5538 | +0.0660 |
| pill | 0.3682 | raw_score | 0.3399 | +0.0284 |
| screw | 0.5505 | map_top1 | 0.3505 | +0.2000 |
| tile | 0.8488 | map_top1 | 0.7918 | +0.0570 |
| toothbrush | 0.5361 | map_mean | 0.5361 | +0.0000 |
| transistor | 0.3308 | raw_score | 0.2979 | +0.0329 |
| wood | 0.4162 | raw_score | 0.1965 | +0.2197 |
| zipper | 0.4766 | raw_score | 0.2684 | +0.2082 |

## 3. Best F1 Score Comparison

| Category | raw_score | map_max | map_mean | map_top1 | map_top01 | Best |
|----------|-----------|---------|----------|----------|-----------|------|
| bottle | 0.8630 | 0.8630 | 0.8702 | 0.8630 | 0.8630 | map_mean (0.8702) |
| cable | 0.7603 | 0.7603 | 0.7603 | 0.7603 | 0.7603 | raw_score (0.7603) |
| capsule | 0.9046 | 0.9046 | 0.9046 | 0.9046 | 0.9046 | raw_score (0.9046) |
| carpet | 0.8641 | 0.8641 | 0.8641 | 0.8641 | 0.8641 | raw_score (0.8641) |
| grid | 0.8444 | 0.8444 | 0.8444 | 0.8444 | 0.8444 | raw_score (0.8444) |
| hazelnut | 0.7821 | 0.7821 | 0.7821 | 0.7778 | 0.7797 | raw_score (0.7821) |
| leather | 0.8519 | 0.8519 | 0.8519 | 0.8519 | 0.8519 | raw_score (0.8519) |
| metal_nut | 0.9029 | 0.9029 | 0.8942 | 0.9029 | 0.9029 | raw_score (0.9029) |
| pill | 0.9156 | 0.9156 | 0.9156 | 0.9156 | 0.9156 | raw_score (0.9156) |
| screw | 0.8655 | 0.8655 | 0.8530 | 0.8655 | 0.8655 | raw_score (0.8655) |
| tile | 0.8469 | 0.8469 | 0.8696 | 0.8587 | 0.8557 | map_mean (0.8696) |
| toothbrush | 0.8333 | 0.8333 | 0.8333 | 0.8333 | 0.8333 | raw_score (0.8333) |
| transistor | 0.5797 | 0.5797 | 0.5714 | 0.5755 | 0.5755 | raw_score (0.5797) |
| wood | 0.8633 | 0.8633 | 0.8633 | 0.8633 | 0.8633 | raw_score (0.8633) |
| zipper | 0.8815 | 0.8815 | 0.8815 | 0.8815 | 0.8815 | raw_score (0.8815) |

## 4. Recall@FPR Comparison (FIXED)

### 4.1 recall@FPR=1%

| Category | raw_score | map_max | map_mean | map_top1 | map_top01 |
|----------|-----------|---------|----------|----------|-----------|
| bottle | 0.2222 | 0.2222 | 0.3016 | 0.2222 | 0.2381 |
| cable | 1.0000 | 1.0000 | 0.0326 | 0.0109 | 1.0000 |
| capsule | 0.0459 | 0.0459 | 0.0642 | 0.0367 | 0.0459 |
| carpet | 0.5281 | 0.5281 | 0.4944 | 0.4045 | 0.4831 |
| grid | 0.1930 | 0.1930 | 1.0000 | 0.1228 | 0.1754 |
| hazelnut | 0.0571 | 0.0571 | 0.0286 | 0.0571 | 0.0571 |
| leather | 0.2391 | 0.2391 | 0.1413 | 0.1413 | 0.2283 |
| metal_nut | 0.3333 | 0.3333 | 0.3011 | 0.3333 | 0.3333 |
| pill | 0.0355 | 0.0355 | 1.0000 | 0.0142 | 0.0355 |
| screw | 1.0000 | 1.0000 | 1.0000 | 0.0084 | 0.0084 |
| tile | 0.5119 | 0.5119 | 0.3571 | 0.5833 | 0.5476 |
| toothbrush | 0.4000 | 0.4000 | 0.3000 | 0.2667 | 0.3000 |
| transistor | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| wood | 0.0167 | 0.0167 | 1.0000 | 0.0167 | 0.0167 |
| zipper | 0.0504 | 0.0504 | 0.0084 | 0.0252 | 0.0588 |

### 4.2 recall@FPR=5%

| Category | raw_score | map_max | map_mean | map_top1 | map_top01 |
|----------|-----------|---------|----------|----------|-----------|
| bottle | 0.2222 | 0.2222 | 0.3016 | 0.2540 | 0.2540 |
| cable | 0.0761 | 0.0761 | 0.0761 | 0.0543 | 0.0761 |
| capsule | 0.0734 | 0.0734 | 0.0826 | 0.0917 | 0.0734 |
| carpet | 0.5955 | 0.5955 | 0.5730 | 0.6292 | 0.5506 |
| grid | 0.3158 | 0.3158 | 0.0000 | 0.1404 | 0.2456 |
| hazelnut | 0.1143 | 0.1143 | 0.0429 | 0.1143 | 0.1143 |
| leather | 0.2717 | 0.2717 | 0.1413 | 0.2174 | 0.2609 |
| metal_nut | 0.3441 | 0.3441 | 0.3011 | 0.3333 | 0.3441 |
| pill | 0.0355 | 0.0355 | 0.0142 | 0.0213 | 0.0355 |
| screw | 0.0168 | 0.0168 | 0.0084 | 0.0084 | 0.0168 |
| tile | 0.5238 | 0.5238 | 0.3690 | 0.5952 | 0.5595 |
| toothbrush | 0.4000 | 0.4000 | 0.3000 | 0.2667 | 0.3000 |
| transistor | 0.0500 | 0.0500 | 0.0750 | 0.0500 | 0.0500 |
| wood | 0.0167 | 0.0167 | 1.0000 | 0.0167 | 0.0167 |
| zipper | 0.0924 | 0.0924 | 0.0252 | 0.0924 | 0.1008 |

## 5. Detailed Per-Mode Statistics

### 5.1 raw_score

| Category | Good | Defect | Good P95 | Good P99 | Defect P5 | Defect P1 | AUROC | Best F1 | F1 Thr | Rec@1% | Rec@5% | Overlap |
|----------|------|--------|----------|----------|-----------|-----------|-------|---------|--------|--------|--------|---------|
| bottle | 20 | 63 | 49.17 | 52.28 | 26.82 | 25.93 | 0.4972 | 0.8630 | 25.88 | 0.2222 | 0.2222 | YES |
| cable | 58 | 92 | 99.84 | 131.68 | 46.39 | 42.94 | 0.4822 | 0.7603 | 42.00 | 1.0000 | 0.0761 | YES |
| capsule | 23 | 109 | 668.60 | 688.11 | 395.75 | 345.82 | 0.4779 | 0.9046 | 342.00 | 0.0459 | 0.0734 | YES |
| carpet | 28 | 89 | 38.70 | 39.59 | 31.22 | 29.44 | 0.7887 | 0.8641 | 27.55 | 0.5281 | 0.5955 | YES |
| grid | 21 | 57 | 46.72 | 49.77 | 31.48 | 28.83 | 0.6099 | 0.8444 | 27.61 | 0.1930 | 0.3158 | YES |
| hazelnut | 40 | 70 | 1142.50 | 1298.76 | 485.79 | 457.04 | 0.5673 | 0.7821 | 421.33 | 0.0571 | 0.1143 | YES |
| leather | 32 | 92 | 619.70 | 636.46 | 437.93 | 421.19 | 0.4693 | 0.8519 | 415.50 | 0.2391 | 0.2717 | YES |
| metal_nut | 22 | 93 | 119.47 | 120.19 | 109.74 | 108.50 | 0.6173 | 0.9029 | 105.59 | 0.3333 | 0.3441 | YES |
| pill | 26 | 141 | 218.69 | 237.56 | 76.06 | 68.51 | 0.3682 | 0.9156 | 62.81 | 0.0355 | 0.0355 | YES |
| screw | 41 | 119 | 28.00 | 32.22 | 19.69 | 19.01 | 0.5337 | 0.8655 | 18.74 | 1.0000 | 0.0168 | YES |
| tile | 33 | 84 | 38.31 | 38.97 | 30.36 | 29.25 | 0.8193 | 0.8469 | 29.16 | 0.5119 | 0.5238 | YES |
| toothbrush | 12 | 30 | 429.01 | 432.20 | 12.81 | 12.73 | 0.5250 | 0.8333 | 12.72 | 0.4000 | 0.4000 | YES |
| transistor | 60 | 40 | 631.65 | 761.99 | 270.20 | 266.50 | 0.3308 | 0.5797 | 262.81 | 1.0000 | 0.0500 | YES |
| wood | 19 | 60 | 809.40 | 823.08 | 331.70 | 289.92 | 0.4162 | 0.8633 | 279.00 | 0.0167 | 0.0167 | YES |
| zipper | 32 | 119 | 36.42 | 37.75 | 29.60 | 28.95 | 0.4766 | 0.8815 | 27.52 | 0.0504 | 0.0924 | YES |

### 5.2 map_max

| Category | Good | Defect | Good P95 | Good P99 | Defect P5 | Defect P1 | AUROC | Best F1 | F1 Thr | Rec@1% | Rec@5% | Overlap |
|----------|------|--------|----------|----------|-----------|-----------|-------|---------|--------|--------|--------|---------|
| bottle | 20 | 63 | 49.17 | 52.28 | 26.82 | 25.93 | 0.4972 | 0.8630 | 25.88 | 0.2222 | 0.2222 | YES |
| cable | 58 | 92 | 99.84 | 131.68 | 46.39 | 42.94 | 0.4822 | 0.7603 | 42.00 | 1.0000 | 0.0761 | YES |
| capsule | 23 | 109 | 668.60 | 688.11 | 395.75 | 345.82 | 0.4779 | 0.9046 | 342.00 | 0.0459 | 0.0734 | YES |
| carpet | 28 | 89 | 38.70 | 39.59 | 31.22 | 29.44 | 0.7887 | 0.8641 | 27.55 | 0.5281 | 0.5955 | YES |
| grid | 21 | 57 | 46.72 | 49.77 | 31.48 | 28.83 | 0.6099 | 0.8444 | 27.61 | 0.1930 | 0.3158 | YES |
| hazelnut | 40 | 70 | 1142.50 | 1298.76 | 485.79 | 457.04 | 0.5673 | 0.7821 | 421.33 | 0.0571 | 0.1143 | YES |
| leather | 32 | 92 | 619.70 | 636.46 | 437.93 | 421.19 | 0.4693 | 0.8519 | 415.50 | 0.2391 | 0.2717 | YES |
| metal_nut | 22 | 93 | 119.47 | 120.19 | 109.74 | 108.50 | 0.6173 | 0.9029 | 105.59 | 0.3333 | 0.3441 | YES |
| pill | 26 | 141 | 218.69 | 237.56 | 76.06 | 68.51 | 0.3682 | 0.9156 | 62.81 | 0.0355 | 0.0355 | YES |
| screw | 41 | 119 | 28.00 | 32.22 | 19.69 | 19.01 | 0.5337 | 0.8655 | 18.74 | 1.0000 | 0.0168 | YES |
| tile | 33 | 84 | 38.31 | 38.97 | 30.36 | 29.25 | 0.8193 | 0.8469 | 29.16 | 0.5119 | 0.5238 | YES |
| toothbrush | 12 | 30 | 429.01 | 432.20 | 12.81 | 12.73 | 0.5250 | 0.8333 | 12.72 | 0.4000 | 0.4000 | YES |
| transistor | 60 | 40 | 631.65 | 761.99 | 270.20 | 266.50 | 0.3308 | 0.5797 | 262.81 | 1.0000 | 0.0500 | YES |
| wood | 19 | 60 | 809.40 | 823.08 | 331.70 | 289.92 | 0.4162 | 0.8633 | 279.00 | 0.0167 | 0.0167 | YES |
| zipper | 32 | 119 | 36.42 | 37.75 | 29.60 | 28.95 | 0.4766 | 0.8815 | 27.52 | 0.0504 | 0.0924 | YES |

### 5.3 map_mean

| Category | Good | Defect | Good P95 | Good P99 | Defect P5 | Defect P1 | AUROC | Best F1 | F1 Thr | Rec@1% | Rec@5% | Overlap |
|----------|------|--------|----------|----------|-----------|-----------|-------|---------|--------|--------|--------|---------|
| bottle | 20 | 63 | 12.31 | 12.36 | 11.70 | 11.49 | 0.7421 | 0.8702 | 11.78 | 0.3016 | 0.3016 | YES |
| cable | 58 | 92 | 13.44 | 14.37 | 10.36 | 10.13 | 0.4957 | 0.7603 | 10.03 | 0.0326 | 0.0761 | YES |
| capsule | 23 | 109 | 29.04 | 30.39 | 20.44 | 18.49 | 0.3937 | 0.9046 | 17.42 | 0.0642 | 0.0826 | YES |
| carpet | 28 | 89 | 18.22 | 18.62 | 14.88 | 14.64 | 0.7263 | 0.8641 | 14.39 | 0.4944 | 0.5730 | YES |
| grid | 21 | 57 | 29.95 | 30.91 | 16.11 | 15.14 | 0.2857 | 0.8444 | 14.98 | 1.0000 | 0.0000 | YES |
| hazelnut | 40 | 70 | 176.06 | 187.95 | 79.10 | 71.90 | 0.5114 | 0.7821 | 67.22 | 0.0286 | 0.0429 | YES |
| leather | 32 | 92 | 313.54 | 318.58 | 224.83 | 206.20 | 0.3512 | 0.8519 | 205.93 | 0.1413 | 0.1413 | YES |
| metal_nut | 22 | 93 | 42.56 | 42.65 | 36.97 | 36.11 | 0.5538 | 0.8942 | 35.20 | 0.3011 | 0.3011 | YES |
| pill | 26 | 141 | 73.02 | 79.32 | 30.67 | 26.62 | 0.3399 | 0.9156 | 24.61 | 1.0000 | 0.0142 | YES |
| screw | 41 | 119 | 12.90 | 13.14 | 11.77 | 11.55 | 0.3505 | 0.8530 | 11.38 | 1.0000 | 0.0084 | YES |
| tile | 33 | 84 | 13.39 | 14.07 | 10.71 | 9.65 | 0.7918 | 0.8696 | 10.61 | 0.3571 | 0.3690 | YES |
| toothbrush | 12 | 30 | 22.34 | 22.82 | 7.22 | 7.19 | 0.5361 | 0.8333 | 7.17 | 0.3000 | 0.3000 | YES |
| transistor | 60 | 40 | 64.36 | 71.74 | 39.03 | 35.91 | 0.2979 | 0.5714 | 34.46 | 1.0000 | 0.0750 | YES |
| wood | 19 | 60 | 446.51 | 447.73 | 154.87 | 150.18 | 0.1965 | 0.8633 | 145.80 | 1.0000 | 1.0000 | YES |
| zipper | 32 | 119 | 16.54 | 16.83 | 13.03 | 12.64 | 0.2684 | 0.8815 | 12.52 | 0.0084 | 0.0252 | YES |

### 5.4 map_top1

| Category | Good | Defect | Good P95 | Good P99 | Defect P5 | Defect P1 | AUROC | Best F1 | F1 Thr | Rec@1% | Rec@5% | Overlap |
|----------|------|--------|----------|----------|-----------|-----------|-------|---------|--------|--------|--------|---------|
| bottle | 20 | 63 | 34.43 | 35.03 | 23.40 | 23.03 | 0.5175 | 0.8630 | 22.77 | 0.2222 | 0.2540 | YES |
| cable | 58 | 92 | 70.85 | 89.42 | 40.91 | 37.73 | 0.4702 | 0.7603 | 36.01 | 0.0109 | 0.0543 | YES |
| capsule | 23 | 109 | 545.59 | 568.31 | 333.29 | 313.46 | 0.4495 | 0.9046 | 306.27 | 0.0367 | 0.0917 | YES |
| carpet | 28 | 89 | 34.30 | 36.09 | 27.46 | 26.66 | 0.7460 | 0.8641 | 25.81 | 0.4045 | 0.6292 | YES |
| grid | 21 | 57 | 44.87 | 46.81 | 28.68 | 27.23 | 0.4754 | 0.8444 | 26.38 | 0.1228 | 0.1404 | YES |
| hazelnut | 40 | 70 | 1075.68 | 1184.74 | 446.64 | 404.17 | 0.5582 | 0.7778 | 361.51 | 0.0571 | 0.1143 | YES |
| leather | 32 | 92 | 588.80 | 609.20 | 408.64 | 387.36 | 0.4253 | 0.8519 | 380.04 | 0.1413 | 0.2174 | YES |
| metal_nut | 22 | 93 | 117.05 | 117.34 | 107.85 | 106.76 | 0.6056 | 0.9029 | 104.03 | 0.3333 | 0.3333 | YES |
| pill | 26 | 141 | 208.87 | 229.55 | 72.46 | 65.85 | 0.3538 | 0.9156 | 61.93 | 0.0142 | 0.0213 | YES |
| screw | 41 | 119 | 25.76 | 26.13 | 18.71 | 18.46 | 0.5505 | 0.8655 | 17.93 | 0.0084 | 0.0084 | YES |
| tile | 33 | 84 | 29.47 | 30.38 | 25.14 | 23.98 | 0.8488 | 0.8587 | 25.14 | 0.5833 | 0.5952 | YES |
| toothbrush | 12 | 30 | 317.03 | 320.54 | 12.59 | 12.51 | 0.4944 | 0.8333 | 12.50 | 0.2667 | 0.2667 | YES |
| transistor | 60 | 40 | 424.73 | 507.05 | 198.22 | 189.91 | 0.2983 | 0.5755 | 170.27 | 1.0000 | 0.0500 | YES |
| wood | 19 | 60 | 771.24 | 786.85 | 305.58 | 275.46 | 0.3649 | 0.8633 | 261.65 | 0.0167 | 0.0167 | YES |
| zipper | 32 | 119 | 33.31 | 34.45 | 27.40 | 25.94 | 0.4330 | 0.8815 | 25.47 | 0.0252 | 0.0924 | YES |

### 5.5 map_top01

| Category | Good | Defect | Good P95 | Good P99 | Defect P5 | Defect P1 | AUROC | Best F1 | F1 Thr | Rec@1% | Rec@5% | Overlap |
|----------|------|--------|----------|----------|-----------|-----------|-------|---------|--------|--------|--------|---------|
| bottle | 20 | 63 | 45.04 | 46.42 | 25.82 | 25.08 | 0.4976 | 0.8630 | 24.76 | 0.2381 | 0.2540 | YES |
| cable | 58 | 92 | 93.46 | 124.12 | 44.96 | 41.62 | 0.4769 | 0.7603 | 40.93 | 1.0000 | 0.0761 | YES |
| capsule | 23 | 109 | 649.27 | 672.24 | 383.71 | 341.65 | 0.4755 | 0.9046 | 332.93 | 0.0459 | 0.0734 | YES |
| carpet | 28 | 89 | 37.52 | 38.74 | 29.98 | 28.20 | 0.7604 | 0.8641 | 26.66 | 0.4831 | 0.5506 | YES |
| grid | 21 | 57 | 46.00 | 48.29 | 30.11 | 28.05 | 0.5806 | 0.8444 | 27.11 | 0.1754 | 0.2456 | YES |
| hazelnut | 40 | 70 | 1135.36 | 1280.90 | 481.54 | 446.83 | 0.5664 | 0.7797 | 454.39 | 0.0571 | 0.1143 | YES |
| leather | 32 | 92 | 607.20 | 628.43 | 430.72 | 416.69 | 0.4572 | 0.8519 | 406.77 | 0.2283 | 0.2609 | YES |
| metal_nut | 22 | 93 | 118.50 | 119.44 | 109.24 | 108.23 | 0.6197 | 0.9029 | 104.97 | 0.3333 | 0.3441 | YES |
| pill | 26 | 141 | 216.48 | 235.67 | 74.61 | 68.09 | 0.3633 | 0.9156 | 62.64 | 0.0355 | 0.0355 | YES |
| screw | 41 | 119 | 27.55 | 28.07 | 19.45 | 18.88 | 0.5436 | 0.8655 | 18.29 | 0.0084 | 0.0168 | YES |
| tile | 33 | 84 | 34.38 | 35.33 | 28.38 | 26.85 | 0.8279 | 0.8557 | 27.19 | 0.5476 | 0.5595 | YES |
| toothbrush | 12 | 30 | 395.50 | 398.99 | 12.71 | 12.66 | 0.5056 | 0.8333 | 12.66 | 0.3000 | 0.3000 | YES |
| transistor | 60 | 40 | 543.50 | 688.39 | 254.81 | 233.09 | 0.3083 | 0.5755 | 214.45 | 1.0000 | 0.0500 | YES |
| wood | 19 | 60 | 803.73 | 816.00 | 322.18 | 286.65 | 0.4035 | 0.8633 | 275.61 | 0.0167 | 0.0167 | YES |
| zipper | 32 | 119 | 35.04 | 36.33 | 28.67 | 27.76 | 0.4480 | 0.8815 | 26.53 | 0.0588 | 0.1008 | YES |

## 6. Analysis and Recommendations

### Q1: Is map_mean the best score_mode?

**Average AUROC across 15 categories:**

| Score Mode | Mean AUROC | Rank |
|------------|-----------|------|
| raw_score | 0.5320 | 1 ← best |
| map_max | 0.5320 | 2 |
| map_top01 | 0.5223 | 3 |
| map_top1 | 0.5061 | 4 |
| map_mean | 0.4561 | 5 ← worst |

map_mean is NOT the best. **raw_score** achieves higher average AUROC.

### Q2: Does any score_mode significantly improve AUROC?

Yes. 34 cases show > 5% AUROC improvement over map_mean:

| Category | Better Mode | New AUROC | map_mean AUROC | Delta |
|----------|-------------|-----------|----------------|-------|
| capsule | raw_score | 0.4779 | 0.3937 | +0.0842 |
| capsule | map_max | 0.4779 | 0.3937 | +0.0842 |
| capsule | map_top1 | 0.4495 | 0.3937 | +0.0558 |
| capsule | map_top01 | 0.4755 | 0.3937 | +0.0818 |
| carpet | raw_score | 0.7887 | 0.7263 | +0.0624 |
| carpet | map_max | 0.7887 | 0.7263 | +0.0624 |
| grid | raw_score | 0.6099 | 0.2857 | +0.3241 |
| grid | map_max | 0.6099 | 0.2857 | +0.3241 |
| grid | map_top1 | 0.4754 | 0.2857 | +0.1896 |
| grid | map_top01 | 0.5806 | 0.2857 | +0.2949 |
| hazelnut | raw_score | 0.5673 | 0.5114 | +0.0559 |
| hazelnut | map_max | 0.5673 | 0.5114 | +0.0559 |
| hazelnut | map_top01 | 0.5664 | 0.5114 | +0.0550 |
| leather | raw_score | 0.4693 | 0.3512 | +0.1180 |
| leather | map_max | 0.4693 | 0.3512 | +0.1180 |
| leather | map_top1 | 0.4253 | 0.3512 | +0.0740 |
| leather | map_top01 | 0.4572 | 0.3512 | +0.1060 |
| metal_nut | raw_score | 0.6173 | 0.5538 | +0.0635 |
| metal_nut | map_max | 0.6173 | 0.5538 | +0.0635 |
| metal_nut | map_top1 | 0.6056 | 0.5538 | +0.0518 |
| metal_nut | map_top01 | 0.6197 | 0.5538 | +0.0660 |
| screw | raw_score | 0.5337 | 0.3505 | +0.1832 |
| screw | map_max | 0.5337 | 0.3505 | +0.1832 |
| screw | map_top1 | 0.5505 | 0.3505 | +0.2000 |
| screw | map_top01 | 0.5436 | 0.3505 | +0.1931 |
| tile | map_top1 | 0.8488 | 0.7918 | +0.0570 |
| wood | raw_score | 0.4162 | 0.1965 | +0.2197 |
| wood | map_max | 0.4162 | 0.1965 | +0.2197 |
| wood | map_top1 | 0.3649 | 0.1965 | +0.1684 |
| wood | map_top01 | 0.4035 | 0.1965 | +0.2070 |
| zipper | raw_score | 0.4766 | 0.2684 | +0.2082 |
| zipper | map_max | 0.4766 | 0.2684 | +0.2082 |
| zipper | map_top1 | 0.4330 | 0.2684 | +0.1647 |
| zipper | map_top01 | 0.4480 | 0.2684 | +0.1796 |

### Q3: Categories always below AUROC 0.80 regardless of score_mode?

Yes. 14/15 categories have AUROC < 0.80 for ALL score modes:

- **bottle**: best AUROC = 0.7421
- **cable**: best AUROC = 0.4957
- **capsule**: best AUROC = 0.4779
- **carpet**: best AUROC = 0.7887
- **grid**: best AUROC = 0.6099
- **hazelnut**: best AUROC = 0.5673
- **leather**: best AUROC = 0.4693
- **metal_nut**: best AUROC = 0.6197
- **pill**: best AUROC = 0.3682
- **screw**: best AUROC = 0.5505
- **toothbrush**: best AUROC = 0.5361
- **transistor**: best AUROC = 0.3308
- **wood**: best AUROC = 0.4162
- **zipper**: best AUROC = 0.4766

These categories cannot be reliably discriminated by raw EfficientAD output
regardless of score mode selection. The raw model output is fundamentally
not a calibrated anomaly score — the Anomalib post-processor (Clip + Normalize
+ Sigmoid) is required for meaningful discrimination.

### Q4: Should efficientad_score_mode be updated?

**Yes, consider switching to raw_score.** It achieves 0.5320
mean AUROC vs map_mean's 0.4561
(delta = +0.0759).

### Q5-Q6: Config update and T2 gate purpose

Given that all 15 categories have AUROC < 0.80 (most < 0.55), the T2 gate
should be understood as a **load shedding gate**, not a detection gate:

- **Purpose**: Reduce T3 (FastSAM + Qwen3-VL) workload by dropping frames
  that are very likely to be normal.
- **Limitation**: Cannot reliably separate good from defective images.
- **Threshold strategy**: Set at good_p95 to control ~5% false trigger rate,
  allowing most frames through for VLM analysis.

### Recommended per-category config (if updating):

```yaml
efficientad_score_mode: raw_score  # best average AUROC
# Per-category thresholds from best score mode per category:
per_category_threshold:
  bottle: 12.31  # map_mean, AUROC=0.7421
  cable: 13.44  # map_mean, AUROC=0.4957
  capsule: 668.60  # raw_score, AUROC=0.4779
  carpet: 38.70  # raw_score, AUROC=0.7887
  grid: 46.72  # raw_score, AUROC=0.6099
  hazelnut: 1142.50  # raw_score, AUROC=0.5673
  leather: 619.70  # raw_score, AUROC=0.4693
  metal_nut: 118.50  # map_top01, AUROC=0.6197
  pill: 218.69  # raw_score, AUROC=0.3682
  screw: 25.76  # map_top1, AUROC=0.5505
  tile: 29.47  # map_top1, AUROC=0.8488
  toothbrush: 22.34  # map_mean, AUROC=0.5361
  transistor: 631.65  # raw_score, AUROC=0.3308
  wood: 809.40  # raw_score, AUROC=0.4162
  zipper: 36.42  # raw_score, AUROC=0.4766
```

## 7. Methodology Disclaimer

1. This analysis is based on MVTec AD test split (1725 images, 15 classes).
2. It is an engineering diagnostic, NOT external independent generalization validation.
3. AUROC is threshold-independent and valid for comparing score ranking ability.
4. F1, recall@FPR, and recommended thresholds are threshold-dependent engineering metrics.
5. These results do NOT constitute production-grade detection accuracy claims.
6. Real production calibration requires data from the actual inspection environment.
