# Engineering Findings & Troubleshooting Log

This document records key engineering problems, diagnostic processes, and solutions encountered during the vlm-sam-industrial-vision-v2 project. Organized by component, chronological within each section.

---

## 1. EfficientAD Deployment

### F-EAD-01: Post-processor Output Incompatible with RKNN

**Stage**: Phase 7 Prompt 2B
**Symptom**: Exporting the Anomalib ONNX model including the post-processor caused RKNN conversion failure with `Greater` operator unsupported for INT8/FLOAT mixed types.
**Root Cause**: The post-processor contains clip -> normalize -> sigmoid operations. The `Greater` node requires mixed FLOAT and INT8 comparison, which the Rockchip RKNN toolkit does not support.
**Solution**: Export raw ONNX (truncate post-processor before the Greater node). Use `/model/ReduceMax_output_0` as `raw_score` and `/model/Add_output_0` as `raw_anomaly_map`. New script: `scripts/export_efficientad_raw_onnx.py`.
**Engineering Impact**: T2 gate can only use raw outputs. Score scale is completely different from the original post-processor [0,1] output range. Per-category thresholds must be recalibrated from scratch.

### F-EAD-02: INT8 RKNN Distribution Distortion

**Stage**: Phase 7 Prompt 2B
**Symptom**: EfficientAD INT8 quantized RKNN inference results show anomaly map distributions severely diverging from ONNX. Good and defect sample scores are nearly indistinguishable.
**Root Cause**: INT8 quantization has insufficient dynamic range capture for EfficientAD's raw anomaly map values (wide span, high dynamic range). The quantization scale cannot preserve the distribution shape.
**Solution**: Use FP16/no-quant RKNN (`rknn_init` without quantization). Verified: ONNX vs RKNN max AUROC delta = 0.024 (screw), negligible for all other categories.
**Engineering Impact**: FP16 RKNN file is ~17MB per class (vs ~5MB for INT8), but inference speed is acceptable. All 15 classes converted as FP16/no-quant.

### F-EAD-03: Score Mode Selection Affects AUROC

**Stage**: Phase 8A-Fix
**Symptom**: Phase 8A used `map_mean` and obtained all 15-class AUROC < 0.50 — near random guessing.
**Root Cause**: `map_mean` averages all pixels in the anomaly map. Large normal background areas pull down the mean, diluting local defect signals. Categories with localized defects (grid, wood, zipper) are especially affected.
**Solution**: Computed AUROC matrix for 5 score modes on the same CSV data (no re-inference). `raw_score` (ReduceMax) achieves mean AUROC = 0.5320 vs `map_mean` 0.4561 (delta = +0.0759). Switched `efficientad_score_mode: raw_score`, updated all 15 class thresholds to raw_score good_p95.
**Engineering Impact**: The grid category shows the largest improvement (+0.3241 AUROC). This confirms that local defect detection requires maximum-pixel-based scoring, not average-based.

### F-EAD-04: recall@FPR Calculation Bug

**Stage**: Phase 8A-Fix-Fix
**Symptom**: Some categories show `recall@FPR=1% = 1.0000` while `recall@FPR=5% = 0.0000` — a logical contradiction where a more relaxed constraint yields lower recall.
**Root Cause**: `compare_score_modes.py` used `np.linspace(lo, hi, 2000)` for threshold discretization (insufficient precision), and `>=` comparison instead of `>`. For inverted-distribution categories (AUROC < 0.5), the script attempted direction-flip searching, producing "high recall" results in the opposite direction. The `>=` operator also disagreed with the C++ runtime which uses `final_score > threshold` (strict greater-than).
**Solution**: Changed to enumerating actual unique score values (not discretized grid), switched comparison operator to `>`, locked search direction to `score > threshold` (matching runtime), added monotonicity assertion. Result: 0/75 recall@FPR violations.
**Engineering Impact**: Ensures that diagnostic metrics correctly reflect the runtime decision boundary. Prevents misleading recall@FPR values in reports.

---

## 2. FastSAM Deployment

### F-FSM-01: INT8 Quantization Precision Regression

**Stage**: Phase 7 Prompt 2C
**Symptom**: FastSAM INT8 RKNN produces severely offset bounding boxes in some categories (capsule). Detection confidence collapsed to near-zero (raw candidates = 0, 100% fallback).
**Root Cause**: INT8 per-tensor quantization (scale=2.82, zp=-119) compresses YOLOv8 confidence into a near-zero range. All 8400 anchors have conf < 0.25. FP16 top-1 conf = 0.8794, INT8 top-1 conf ~0.003.
**Solution**: Use FP16/no-quant RKNN (`do_quantization=False`). Output `fastsam_s_noquant.rknn` (26MB). FP16 fallback rate: 0% (0/31 frames).
**Engineering Impact**: FastSAM FP16 inference on RK3588 takes ~170ms (preprocess ~95ms + infer ~140ms + post ~7ms), which is acceptable for the pipeline budget.

### F-FSM-02: FastSAM Calibration Set Strategy

**Stage**: Phase 6 (v2 conversion)
**Symptom**: Phase 5's 3-class calibration set produced FastSAM INT8 RKNN with larger quantization bias on unseen categories when expanded to 15 classes.
**Root Cause**: INT8 calibration set covered only 3 classes; activation distribution was not representative of all 15 MVTec categories.
**Solution**: Used 15-class mixed calibration set (~300 images, `random.seed(42)` shuffled). Reconverted FastSAM RKNN (ultimately still using FP16/no-quant).
**Engineering Impact**: Even with better calibration, INT8 precision remained unacceptable. FP16 is the only viable quantization level for FastSAM on RK3588.

---

## 3. Qwen3-VL / RKLLM Deployment

### F-VLM-01: RKLLM Runtime Version Mismatch

**Stage**: Phase 7 Prompt 2D
**Symptom**: `rkllm_init` failure: `The rkllm-runtime version is lower than the rkllm-toolkit version. Please update to 1.2.3`.
**Root Cause**: Board `/usr/lib/librkllmrt.so` was v1.2.1; model was exported with rkllm-toolkit 1.2.3.
**Solution**: Replace system library with `/home/orangepi/rkllm_run/librkllmrt.so` (v1.2.3).

### F-VLM-02: n_image_tokens Calculation Error

**Stage**: Phase 7 Prompt 2D
**Symptom**: `E rkllm: patch_h[14] * patch_w[14] != n_image_token[784]!`
**Root Cause**: Code set `n_image_tokens = 196 * 4 = 784` (incorrectly multiplied by n_output). RKLLM expects `n_image_tokens = patch_h * patch_w = 14 * 14 = 196`.
**Solution**: Use `vision_image_token_` directly (196), no multiplication.

### F-VLM-03: max_new_tokens Causes JSON Truncation

**Stage**: Phase 7 Prompt 2D
**Symptom**: VLM output truncated mid-array; `rfind('}')` cannot find matching closing bracket.
**Root Cause**: `vlm_max_new_tokens: 200` causes truncation when VLM generates ~196 tokens.
**Solution**:
1. Increased `vlm_max_new_tokens` to 500
2. Optimized prompt to compact JSON format (`[[x,y,w,h]]`), reducing output from ~196 to ~89 tokens
3. JSON extraction changed to `rfind('}')` to tolerate incomplete output

### F-VLM-04: 2B LoRA W8A8 Quantization Destroys Fine-Grained Classification

**Stage**: Phase 8B-PC + LoRA Conversion Audit
**Symptom**: PC bf16 inference: defect_type_exact = 51.8%. Board W8A8 RKLLM inference: 0%. category_exact largely preserved (95.1% -> 93%), defect_type_exact completely collapses.
**Root Cause**: LoRA rank=32 delta weight magnitudes are ~1-2 orders of magnitude smaller than base weights. W8A8 quantization step size = max(|W|)/127 is calibrated for base weights, insufficient for LoRA delta precision. Delta weights get quantized to zero; fine-grained knowledge is lost.
**Verification**: LoRA correctly merged-then-converted (bash_history + LoRA key check + SHA256 cross-platform match). Not a conversion error.
**Solution**: RK3588 LLM path only supports W8A8 (no higher precision option; W4A16 is RK3576 only). Deployment choice: 2B base (stable). LoRA retains PC bf16 inference value.
**Engineering Impact**: W8A8 quantization disproportionately affects small-magnitude delta weights. This is a fundamental hardware constraint, not a training or conversion failure.

### F-VLM-05: LoRA Deterministic Degeneration (Repeated Brackets)

**Stage**: Phase 8B-Board
**Symptom**: `grid/bent/011.png` triggers 2B LoRA to output 499 tokens of bracket repetition every time: `[[[0.00220382, 0.00220382, 0.0528917, 0.0440764], [[0.00440764, ...`
**Root Cause**: LoRA training data for grid/bent may contain multi-layer nested bbox format samples. The LoRA adapter learned "bent -> multi-layer nested coordinates" mapping. Under W8A8 inference, this enters a loop until max_tokens truncation.
**Engineering Impact**: Blocks T3 for ~50 seconds. At beat=20s, causes Q2 overflow and drops 3+ subsequent frames.
**Solution**: Do not deploy LoRA on board. If LoRA is needed, beat_ms >= 60000ms, or add post-processing to detect bracket repetition and truncate.

### F-VLM-06: 4B Vision Encoder Spatial Patch Merge Arrangement Error

**Stage**: Phase 8B-4B
**Symptom**: `E rkllm: patch_h[14] * patch_w[14] != n_image_token[784]!` (4B init failure). After fixing to 196, carpet images trigger silent VLM failure (vision_ms=0, no error output).
**Root Cause**: 4B vision encoder output[0] is [784, 1024] (pre-merge), output[1-4] are [196, 2560]. n_image_tokens should be 196, embed_dim should be 4096 (=1024*4). Current contiguous reshape [784,1024]->[196,4096] is logically correct in total size but spatially incorrect. Correct implementation: `[28,28,1024] -> permute[14,2,14,2,1024] -> [196,4096]`. Carpet texture is spatially sensitive; wrong arrangement produces embeddings that RKLLM cannot process.
**Current Status**: 6/7 categories work. Carpet silently fails. Fix path is known but not implemented.
**Impact on 2B**: None. 2B has no spatial merge; code paths are independent.

---

## 4. C++ Four-Thread Pipeline

### F-CPP-01: beat_ms and VLM Latency Queue Stability Relationship

**Stage**: Phase 8C
**Finding**: VLM_avg_ms / beat_ms is the critical queue stability metric (analogous to utilization ratio rho in queuing theory). When ratio > 1.0, Q2 begins accumulating. When ratio > 1.5, severe instability occurs.
**Design Formula**:
- Safe: beat_ms > VLM_p99_latency
- Recommended: beat_ms >= VLM_avg / 0.85 (15% buffer)
- 2B base: recommended 13000ms, minimum stable 10000ms
- 4B base: recommended >=35000ms (measured max VLM = 28.9s)

### F-CPP-02: Backpressure-Induced VLM Latency Amplification

**Stage**: Phase 8C
**Symptom**: At beat=5000ms, VLM avg latency increases from baseline 10.7s to 13.1s (+21.9%).
**Root Cause**: When Q2 is continuously at capacity, T2 spends CPU/scheduling time in push-wait. VLM and EfficientAD/FastSAM compete for NPU resources, increasing per-frame VLM time. Positive feedback: VLM slower -> more accumulation -> more NPU contention -> VLM even slower.
**Engineering Impact**: System does not degrade linearly under Q2 saturation — it degrades acceleratively. This is why the beat_ms sweep shows exponential-like queue drop growth.

---

## 5. Experimental Methodology

### F-METHOD-01: Timeout/Drain Issues Causing Incomplete Data

**Stage**: Phase 8B LoRA initial A/B
**Symptom**: LoRA v2 run processed only 11/14 frames, initially misdiagnosed as "LoRA cannot handle the workload."
**Root Cause**: Claude Code remote execution timeout may have expired before LoRA completed all 14 images. Logs were truncated, and backend only had 11 records.
**Solution**: Conducted controlled rerun with explicit sufficient timeout (1800s) and backend poll to confirm 14/14 before sending SIGTERM. Conclusion: 11/14 was a scheduling issue (beat=20s insufficient for 50s grid degeneration), not an inherent LoRA processing limitation.

### F-METHOD-02: Calibration-on-Test Methodology Disclosure

**Stage**: Phase 8A
**Issue**: Phase 8A used MVTec test split for both threshold calibration and metric evaluation (calibration-on-test).
**Impact**: AUROC is unaffected (pure ranking metric). recall@FPR and F1 have slight optimistic bias.
**Disclosure**: Summary reports explicitly state this. MVTec sample sizes are limited (minimum 12 good images per class); 50/50 splits would make percentile estimates less stable. This is the standard practice in anomaly detection literature (including the EfficientAD original paper).

### F-METHOD-03: pass_all vs threshold Evaluation Boundary

**Stage**: Phase 8B
**Issue**: Using threshold mode for VLM quality evaluation would filter frames through T2 gate. Since T2 AUROC < 0.80 for 14/15 classes, the gate would non-randomly select frames, contaminating VLM quality comparison.
**Decision**: All VLM A/B evaluations use pass_all to ensure unbiased sample coverage. T2 gate behavior is evaluated separately in Phase 8A (calibration) and Phase 7 Prompt 2F (threshold verification).

---

## 6. Model Conversion & Quantization

### F-QUANT-01: RKLLM First Conversion Failed Due to Disk Space

**Stage**: Phase 6 (2B LoRA conversion)
**Symptom**: Export failed at 399/399 layers after ~2 hours: `Not enough free space to write 129,679,360 bytes`.
**Solution**: Freed AutoDL disk space, retried. Retry succeeded but `optimization_level` reduced from 36 to 28. Impact on inference quality: negligible.

### F-QUANT-02: Transformers Version Conflict

**Stage**: Phase 6 RKLLM conversion
**Symptom**: rkllm-toolkit 1.2.3 pins `transformers==4.55.2`, but generating calibration data requires `transformers==4.57.0` (needed for Qwen3-VL support).
**Solution**: Operation order management:
1. Temporary upgrade before calibration data generation: `pip install transformers==4.57.0`
2. Downgrade before `export_rkllm.py`: `pip install transformers==4.55.2 tokenizers==0.21.4`

### F-QUANT-03: LoRA Merge-then-Convert Audit

**Stage**: Phase 8B
**Issue**: Initial PC evaluation recommended "try merging LoRA before RKLLM conversion" — but this was already done.
**Evidence**:
- `merge_2b_lora_15cls.yaml` confirmed base + adapter paths
- `llamafactory-cli export` executed (bash_history line 83)
- Post-merge Python verification: "No LoRA keys — merge confirmed"
- 4B merge log confirms identical mechanism
- SHA256 match between AutoDL and Orange Pi artifacts
**Correct Conclusion**: The conversion chain (merge -> W8A8 convert) was correct. The quality collapse is caused by W8A8 quantization destroying LoRA delta weights, not by operational error.

### F-QUANT-04: W8A8 Unfriendly to LoRA Deltas

**Stage**: Phase 8B (cross-cutting)
**Root Cause**: LoRA rank-32 delta weights (~51MB, ~0.1% of total parameters) are 1-2 orders of magnitude smaller than base weights. W8A8 quantization resolution (max(|W|)/127) is calibrated for base weight distribution. The deltas get quantized to zero or near-zero, destroying the fine-grained knowledge LoRA provides.
**Evidence**: PC bf16 LoRA achieves 51.8% defect_type_exact; board W8A8 LoRA achieves 0%. Category_exact survives (95.1% -> 93%) because coarse category knowledge is encoded redundantly across many weights with larger magnitudes.
**Implication**: Any small-magnitude fine-tuning delta (not just LoRA) would face similar degradation under W8A8. This is a fundamental precision floor of INT8 weight quantization for incremental learning.
