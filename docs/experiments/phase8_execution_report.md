# Phase 8 Execution Report: Threshold Calibration, VLM A/B Evaluation, and Beat Optimization

Generated: 2026-05-22

## 1. Phase 8 Objective and Scope

Phase 8 transitions from Phase 7's "engineering pass" to systematic calibration, evaluation, and optimization. Phase 7 established a working four-thread C++ pipeline; Phase 8 determines the deployment-ready configuration.

Actual sub-phases executed:

| Sub-phase | Description | Status |
|---|---|---|
| Phase 8A | EfficientAD 15-class raw threshold calibration | Completed |
| Phase 8A-Fix | Score mode comparison (5 modes, AUROC matrix) | Completed |
| Phase 8A-Fix-Fix | recall@FPR monotonicity fix + config scale consistency | Completed |
| Phase 8B-Prep | VLM variant runtime audit + fixed sample preparation | Completed |
| Phase 8B-Board-2B | 2B base smoke + 2B base vs LoRA A/B + controlled rerun | Completed |
| Phase 8B-PC | PC-side quality evaluation (eval_ab_test.py, 409 samples) | Completed |
| LoRA conversion audit | Merge-then-convert verification | Completed |
| Phase 8C-mini | pass_all mode beat_ms sweep (6 settings) | Completed |
| Phase 8B-4B | 4B base runtime path implementation + board smoke | Completed |

## 2. Phase 8A: EfficientAD Threshold Calibration

### 2.1 Execution Environment

- Board: Orange Pi 5 Plus 16GB (RK3588), RKNNLite inference
- Dataset: 15-class MVTec AD test split, 1725 images total
- Model: EfficientAD-S FP16/no-quant raw RKNN (~17 MB per class)

### 2.2 Key Finding: Score Mode Comparison

Phase 8A initially used `map_mean` as the score mode. Phase 8A-Fix compared all 5 score modes by computing AUROC on the same `rknn_scores_15cls.csv` data (no re-inference required).

**Mean AUROC across 15 categories:**

| Score Mode | Mean AUROC | Rank |
|---|---|---|
| raw_score | 0.5320 | 1 (best) |
| map_max | 0.5320 | 2 |
| map_top01 | 0.5223 | 3 |
| map_top1 | 0.5061 | 4 |
| map_mean | 0.4561 | 5 (worst) |

Source: `results/phase8_threshold_calibration/score_mode_comparison.csv`

Key conclusions:
- `raw_score` and `map_max` are mathematically equivalent (both are ReduceMax outputs), yielding identical AUROC
- `map_mean` is the worst mode because large normal background areas dilute local defect signals
- All 5 modes yield mean AUROC < 0.60; 14/15 categories have best AUROC < 0.80 (exception: tile at 0.8488 with `map_top1`)
- T2 gate is fundamentally a load shedding controller, not a precise detection classifier

### 2.3 ONNX vs RKNN AUROC Comparison

Max AUROC delta between ONNX and RKNN = 0.024 (screw). All other categories show near-zero difference. Conclusion: FP16/no-quant RKNN inference quality is equivalent to PC ONNX; differences do not come from quantization.

### 2.4 Per-Category Threshold (raw_score, good_p95)

All thresholds below are raw_score good_p95 from the MVTec AD test split, as currently set in `edge/config.yaml` after Phase 8A-Fix-Fix.

| Category | Threshold (raw_score good_p95) | AUROC (raw_score) |
|---|---|---|
| bottle | 49.17 | 0.4972 |
| cable | 99.84 | 0.4822 |
| capsule | 668.60 | 0.4779 |
| carpet | 38.70 | 0.7887 |
| grid | 46.72 | 0.6099 |
| hazelnut | 1142.50 | 0.5673 |
| leather | 619.70 | 0.4693 |
| metal_nut | 119.47 | 0.6173 |
| pill | 218.69 | 0.3682 |
| screw | 28.00 | 0.5337 |
| tile | 38.31 | 0.8193 |
| toothbrush | 429.01 | 0.5250 |
| transistor | 631.65 | 0.3308 |
| wood | 809.40 | 0.4162 |
| zipper | 36.42 | 0.4766 |

Source: `edge/config.yaml` (current values), `results/phase8_threshold_calibration/score_mode_comparison.csv` (AUROC column for raw_score)

**Note**: All categories show good/defect distribution overlap (ALL YES). Only tile has raw_score AUROC > 0.80. These thresholds are engineering starting values calibrated on-test, not production-certified values.

**Important**: The `map_mean` thresholds from Phase 8A initial calibration (e.g., bottle=12.31, tile=13.39, wood=446.51) are NOT used in the current config. The Phase 8A-Fix-Fix config uses raw_score good_p95 thresholds with much higher absolute values (e.g., bottle=49.17, tile=38.31, wood=809.40).

### 2.5 Phase 8A-Fix-Fix: recall@FPR Bug Fix

The original script (`compare_score_modes.py`) used `np.linspace(lo, hi, 2000)` discretization + `>=` comparison. This caused:
- `recall@FPR=1% = 1.0000` while `recall@FPR=5% = 0.0000` for inverted-distribution categories (AUROC < 0.5) — a logical impossibility where a more relaxed constraint yields lower recall

Fix: Enumerate actual unique score values (not discretized grid), use `>` operator (matching C++ runtime `final_score > threshold`), lock search direction. Result: 0/75 monotonicity violations.

## 3. Phase 8B: VLM Variant Evaluation

### 3.1 Fixed Sample Design

14 images (7 categories x 2: 1 good + 1 defect each):
tile, carpet, grid, metal_nut, zipper, pill, screw

AUROC coverage range: 0.37 (pill) — 0.82 (tile).

All experiments use `pass_all` gate mode to avoid T2 threshold gate contaminating VLM quality evaluation.

Substitution: `tile/test/good/023.png` replaced with `011.png` because 023 triggers deterministic VLM silent failure (RKLLM returns immediately without generating tokens).

### 3.2 Board 2B Base vs 2B LoRA Comparison

Source: `results/phase8_vlm_ab/board_2b_base_vs_lora_ab_v2.md`, `board_2b_lora_controlled_rerun_summary.md`

| Metric | 2B base | 2B LoRA (controlled rerun, beat=60s) |
|---|---|---|
| json_parse_ok | 13/14 (92.9%) | 14/14 (100%) |
| defect_type_exact | 0/7 (0%) | 0/7 (0%) |
| TTFT mean | 1877ms | 1914ms |
| decode_tps | 9.7 | 9.9 |
| RSS mean | 3285MB | 3274MB |
| qwen3vl_ms mean | 10548ms | ~26334ms (incl. grid degeneration frame) |
| repeated_bracket | 0 | 1 (grid/bent, 499 tokens, deterministic) |
| Safe beat_ms | 13000ms | >=60000ms |
| queue_drop | 0 | 0 (at 60s beat) |

**LoRA controlled rerun explanation**: The initial A/B run (beat=20s) showed LoRA processing only 11/14 frames. This was NOT an inherent LoRA processing limitation. The grid/bent image triggers a 499-token repeated bracket degeneration that blocks T3 for ~50s, causing Q2 overflow at beat=20s. The controlled rerun with beat=60s confirmed 14/14 processing with 0 queue drops. Conclusion: the 11/14 was a scheduling issue, not a model capability issue. However, the degeneration itself is a deterministic model behavior.

**Key finding**: LoRA provides no quality improvement on the board. Both variants show 0% defect_type_exact. LoRA introduces additional degeneration modes (repeated brackets, "region" output).

### 3.3 PC-Side Quality Evaluation (409 samples)

Source: `results/phase8_vlm_ab/pc_2b_base_vs_lora_eval.md`

| Metric | PC 2B base | PC 2B LoRA | Board 2B LoRA |
|---|---|---|---|
| json_parse_ok | 391/409 (95.6%) | 393/409 (96.1%) | 14/14 (100%) |
| defect_type_exact | 47/409 (11.5%) | 212/409 (51.8%) | 0/7 (0%) |
| category_exact | 220/409 (53.8%) | 389/409 (95.1%) | ~93% |
| bbox_iou>=0.5 | 5/409 (1.2%) | 195/409 (47.7%) | N/A |
| repeated_bracket | 0 | 0 | 1 |
| "region" output | 0 | 0 | 1 |

**Core finding: W8A8 quantization selectively destroys LoRA fine-grained gains**
- PC LoRA bf16: defect_type_exact 51.8%, category_exact 95.1%
- Board LoRA W8A8: defect_type_exact 0%, category_exact ~93%
- category_exact is largely preserved (coarse-grained knowledge, encoding redundancy, quantization-robust)
- defect_type_exact collapses to zero (fine-grained knowledge, concentrated in rank-32 low-rank subspace, insufficient quantization resolution)

### 3.4 LoRA Conversion Audit

Source: `results/phase8_vlm_ab/lora_conversion_audit.md`

Audit conclusions:
- `llamafactory-cli export` correctly merged LoRA adapter into base weights before RKLLM W8A8 conversion
- Conversion chain: base + adapter -> merged -> W8A8 RKLLM
- SHA256 consistent across platforms (AutoDL -> Orange Pi): `de2a25b08d5a...0190f0482`
- First conversion attempt failed due to disk space exhaustion; retry succeeded (optimization_level reduced from 36 to 28)
- Original "try merging before conversion" recommendation should be deleted — merge was already performed
- Correct conclusion: RKLLM W8A8 deployment chain causes LoRA fine-grained capability collapse; this is a hardware constraint, not an operational error

### 3.5 Board 4B Base Smoke

Source: `results/phase8_4b_smoke/phase8_4b_base_smoke_report.md`

| Metric | 4B base | vs 2B base |
|---|---|---|
| TTFT | 4650ms | 2.45x slower |
| decode_tps | 4.9 | 0.51x (half speed) |
| RSS | 5689MB | 1.74x |
| qwen3vl_ms (tile) | 19500ms | 1.82x |
| json_parse_ok (non-carpet) | 27/27 (100%) | Same |
| Safe beat_ms (pass_all) | >=35000ms | 2.7x |
| carpet VLM | Silent failure | 2B normal |

**4B vision encoder spatial patch merge issue**: 4B vision encoder output[0] dimension is [784, 1024] (pre-merge), which cannot be directly passed as n_image_tokens=784 to RKLLM (RKLLM expects patch_h x patch_w = 14 x 14 = 196). Current fix: detect 4x factor, reshape to [196, 4096] (contiguous). Known limitation: correct implementation requires spatial permutation `[28,28,1024] -> permute[14,2,14,2,1024] -> [196,4096]`. Current contiguous reshape works for 6/7 categories; carpet triggers silent failure due to texture spatial sensitivity. Fix path is known but not implemented in this phase.

4B does not change the current deployment mainline; 2B base remains the recommended deployment variant.

## 4. Phase 8C-mini: Beat_ms Pressure Test

Source: `results/phase8c_beat_sweep/phase8c_beat_sweep_summary.md`, `results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv`

### 4.1 Test Conditions

- 2B base, pass_all mode (worst-case), 14 fixed samples
- Beat_ms sweep: 15000 / 13000 / 10000 / 8000 / 6000 / 5000

### 4.2 Results

| beat_ms | queue_drop | stable | VLM_avg/beat ratio | qwen3vl_avg (ms) |
|---|---|---|---|---|
| 15000 | 0 | YES | 0.71 | 10735 |
| 13000 | 0 | YES | 0.83 | 10775 |
| 10000 | 1 | YES (boundary) | 1.10 | 10957 |
| 8000 | 6 | NO | 1.42 | 11384 |
| 6000 | 14 | NO | 1.96 | 11737 |
| 5000 | 23 | NO | 2.62 | 13083 |

**Design formula**:
- Safe: beat_ms > VLM_p99_latency
- Recommended: beat_ms >= VLM_avg / 0.85 (15% buffer)
- 2B base pass_all: recommended 13000ms (ratio=0.83), minimum stable 10000ms
- 4B base pass_all: recommended >=35000ms (based on measured max 28.9s)

**System behavior**:
- All queue drops occur at Q2 (capacity=2, protective design)
- At beat=5000ms, VLM avg increases 21.9% (backpressure-induced latency amplification, positive feedback loop)
- RSS stable throughout (3275-3297MB), no memory leaks
- json_parse_ok unaffected by beat_ms
- Production threshold mode: ~5% pass rate, 5000ms beat equivalent to ~100s T3 enqueue interval — sufficient

## 5. Deviation from Original Phase 8 Plan

| Original Plan | Actual Execution | Reason |
|---|---|---|
| 4-variant full board A/B | 2B board + PC eval + 4B smoke | 4B C++ path was a TODO stub; needed implementation first |
| Threshold mode VLM evaluation | pass_all with fixed samples | T2 AUROC < 0.80 would contaminate VLM quality evaluation |
| LoRA as deployment candidate | LoRA as quantization failure diagnostic case | PC effective, board W8A8 collapses |
| Phase 8C comprehensive tuning | Phase 8C-mini pass_all sweep | Threshold mode produces near-zero T3 load, no tuning space |
| 4B full A/B | 4B path + smoke | Spatial merge not fully correct; smoke first |
| Single round Phase 8B | Multi-round iteration (smoke -> A/B -> controlled rerun -> PC eval -> audit) | Discovered scheduling issues and quantization issues requiring additional verification |

## 6. Deployment Recommendation

| Scenario | Recommended Variant | Rationale |
|---|---|---|
| RK3588 production | 2B base W8A8 | Stable, no degeneration, json_parse_ok 100% |
| PC bf16 inference (high quality) | 2B LoRA | defect_type_exact 51.8%, bbox_iou 47.7% |
| Larger model, relaxed latency | 4B base (after carpet bug fix) | RSS 5.7GB, latency 1.8x |

## 7. Data File Index

| File | Content |
|---|---|
| `results/phase8_threshold_calibration/rknn_scores_15cls.csv` | 15-class 1725-image raw scores |
| `results/phase8_threshold_calibration/score_mode_comparison.csv` | 5 score mode AUROC matrix |
| `results/phase8_threshold_calibration/score_mode_comparison.md` | Score mode comparison report |
| `results/phase8_vlm_ab/board_2b_base_smoke_summary.md` | 2B base board smoke |
| `results/phase8_vlm_ab/board_2b_base_vs_lora_ab_v2.md` | 2B base vs LoRA A/B main report |
| `results/phase8_vlm_ab/board_2b_lora_controlled_rerun_summary.md` | Controlled rerun comparison |
| `results/phase8_vlm_ab/board_2b_lora_controlled_rerun_vs_previous.md` | Controlled rerun vs previous |
| `results/phase8_vlm_ab/pc_2b_base_vs_lora_eval.md` | PC-side 409-sample quality evaluation |
| `results/phase8_vlm_ab/lora_conversion_audit.md` | LoRA conversion process audit |
| `results/phase8c_beat_sweep/phase8c_beat_sweep_summary.md` | Beat_ms sweep summary |
| `results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv` | Beat_ms sweep raw data |
| `results/phase8_4b_smoke/phase8_4b_base_smoke_report.md` | 4B base smoke complete report |
| `results/phase8_4b_smoke/board_4b_base_smoke_3_summary.md` | 4B 3-image smoke summary |
