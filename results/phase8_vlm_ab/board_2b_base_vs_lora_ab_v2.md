# Phase 8B-Board-2B-AB-Prep-v2: 2B Base vs 2B LoRA A/B Comparison

Generated: 2026-05-22

## 1. Test Configuration

| Parameter | 2B Base | 2B LoRA |
|-----------|---------|---------|
| Model | qwen3vl_2b_w8a8_base.rkllm | qwen3vl_2b_w8a8_lora_15cls.rkllm |
| Model size | 2.3GB | 2.3GB |
| Vision encoder | qwen3vl_2b_vision.rknn | qwen3vl_2b_vision.rknn |
| Gate mode | pass_all | pass_all |
| Beat interval | 13000ms | 20000ms |
| Fixed samples | fixed_sample_images_v2 (14 images) | fixed_sample_images_v2 (14 images) |
| Board | Orange Pi 5 Plus 16GB | Orange Pi 5 Plus 16GB |

## 2. Overall Metrics

| Metric | 2B Base | 2B LoRA | Delta |
|--------|---------|---------|-------|
| frames_processed | 14 | 11 | -3 (queue drops) |
| unique_images_seen | 14/14 | 11/14 | -3 |
| upload_ok | 14/14 (100%) | 11/11 (100%) | — |
| json_parse_ok | 13/14 (92.9%) | 10/11 (90.9%) | -2.0% |
| fallback_used | 1/14 (7.1%) | 1/11 (9.1%) | +2.0% |
| empty_generation_count | 0 | 0 | — |
| repeated_bracket_count | 0 | 1 (grid defect, 499 tok) | +1 |
| avg_prompt_tokens | 407 | 395 | -12 |
| avg_output_tokens | 68 | 113 | +45 (+66%) |
| avg_ttft_ms | 1877 | 2837 | +960 (+51%) |
| avg_decode_tps | 9.7 | 6.8 | -2.9 (-30%) |
| avg_rss_mb | 3285 | 3285 | 0 |
| avg_qwen3vl_ms | 10548 | 26334 | +15786 (+149%) |
| queue_drop_count | 0 | 3+ | +3 |

## 3. Defect Samples Analysis

### 3.1 Count and JSON Success

| Metric | 2B Base | 2B LoRA |
|--------|---------|---------|
| count | 7 | 6 |
| json_parse_ok | 6/7 (85.7%) | 5/6 (83.3%) |
| fallback_used | 1/7 | 1/6 |

### 3.2 Defect Type Accuracy

| Metric | 2B Base | 2B LoRA |
|--------|---------|---------|
| defect_type_exact | 0/7 (0%) | 0/6 (0%) |
| anomaly_generic_rate | 5/7 (71%) | 5/6 (83%) |
| specific_wrong_type_count | 2 (grid→crack, zipper→missing_pin) | 1 (screw→region) |

### 3.3 Per-Sample Comparison (Defect)

| Category | GT | Base pred | LoRA pred | Notes |
|----------|-----|-----------|-----------|-------|
| tile crack | crack | anomaly | anomaly | Both wrong |
| carpet color | color | anomaly (fallback) | anomaly (fallback) | Both fallback |
| grid bent | bent | crack | anomaly | Base closer (crack≈bent) |
| metal_nut bent | bent | anomaly | (dropped) | LoRA missing |
| zipper broken_teeth | broken_teeth | missing_pin | anomaly | Base closer |
| pill color | color | anomaly | anomaly | Both wrong |
| screw scratch_head | scratch_head | anomaly | region | Both wrong |

### 3.4 Severity Distribution (Defect)

| Severity | 2B Base | 2B LoRA |
|----------|---------|---------|
| low | 2/7 | 3/6 |
| medium | 4/7 | 0/6 |
| high | 1/7 | 3/6 |

### 3.5 Confidence (Defect)

| Metric | 2B Base | 2B LoRA |
|--------|---------|---------|
| mean | 0.74 | 0.71 |
| median | 0.95 | 0.98 |

## 4. Good Samples Analysis

### 4.1 Count and JSON Success

| Metric | 2B Base | 2B LoRA |
|--------|---------|---------|
| count | 7 | 5 |
| json_parse_ok | 7/7 (100%) | 5/5 (100%) |
| fallback_used | 0/7 | 0/5 |

### 4.2 Good Image Handling

| Metric | 2B Base | 2B LoRA |
|--------|---------|---------|
| none_rate | 1/7 (14%) — screw only | 0/5 (0%) |
| anomaly_false_positive_rate | 6/7 (86%) | 5/5 (100%) |

**LoRA is worse** at good image handling: it never outputs "none", while base at least correctly identifies screw as "none".

### 4.3 Per-Sample Comparison (Good)

| Category | Base pred | LoRA pred | Notes |
|----------|-----------|-----------|-------|
| tile good | anomaly (low, 0.95) | anomaly (low, 0.38) | Both wrong; LoRA lower conf |
| carpet good | anomaly (medium, 0.36) | anomaly (high, 0.90) | Both wrong; LoRA higher conf |
| grid good | anomaly (low, 0.95) | anomaly (medium, 0.90) | Both wrong |
| metal_nut good | anomaly (medium, 0.95) | (dropped) | LoRA missing |
| zipper good | anomaly (low, 0.95) | (dropped) | LoRA missing |
| pill good | anomaly (low, 0.97) | anomaly (low, 0.89) | Both wrong |
| screw good | none (low, 0.97) | anomaly (low, 0.00) | Base correct! |

### 4.4 Severity Distribution (Good)

| Severity | 2B Base | 2B LoRA |
|----------|---------|---------|
| low | 5/7 | 3/5 |
| medium | 2/7 | 1/5 |
| high | 0/7 | 1/5 |

### 4.5 Confidence (Good)

| Metric | 2B Base | 2B LoRA |
|--------|---------|---------|
| mean | 0.79 | 0.61 |
| median | 0.95 | 0.89 |

## 5. Performance Metrics

| Metric | 2B Base | 2B LoRA | Delta |
|--------|---------|---------|-------|
| TTFT mean | 1877ms | 2837ms | +51% |
| TTFT median | 1872ms | 3068ms | +64% |
| decode_tps mean | 9.7 | 6.8 | -30% |
| RSS mean | 3285MB | 3285MB | 0 |
| RSS max | — | 3297MB | — |
| qwen3vl pipeline mean | 10548ms | 26334ms | +149% |
| output_tokens mean | 68 | 113 | +66% |
| output_tokens max | — | 499 | — |
| Long output (>120 tok) | 0 | 1 (grid defect) | +1 |

**LoRA is significantly slower**: 2.5x pipeline latency, 30% lower decode throughput, 66% more output tokens. The primary driver is the grid defect's repeated bracket degeneration (499 tokens, ~50s).

## 6. Key Findings

### 6.1 Repeated Bracket Degeneration (LoRA-specific)

The LoRA model produces `[[[0.00220382, 0.00220382, 0.0528917, 0.0440764], [[0.00440764, ...` on the grid defect (bent) image. This is a systematic degeneration where the model enters a bracket repetition loop, consuming all 499 output tokens. The JSON parser extracts the first valid `}` but the bboxes are malformed.

**Impact**: This single frame blocks the VLM for ~50 seconds, causing subsequent metal_nut and zipper frames to be dropped from Q2.

### 6.2 Queue Drop Cascading

Because the LoRA model is slower (mean VLM=26.3s vs base's 10.5s) and has a worst-case of ~50s (grid defect), the Q2 BoundedQueue (capacity=2) drops frames even with beat_ms=20000. The base model with beat_ms=13000 has 0 drops.

### 6.3 No Quality Improvement

- defect_type_exact: 0% for both variants
- Good image none_rate: LoRA is worse (0% vs base's 14%)
- Generic "anomaly" rate: LoRA is worse (83% vs base's 71%)

## 7. Answers to Required Questions

### Q1: Did fixed_samples_v2 eliminate tile good no-generation?
**Yes.** tile/test/good/011.png processes successfully in both variants (json_parse_ok=True). The 023→011 replacement fixed the deterministic VLM failure.

### Q2: Is 2B base v2 still stable?
**Yes.** 14/14 unique images, 92.9% json_parse_ok, 0 queue drops, consistent performance.

### Q3: Can 2B LoRA stably generate JSON?
**Partially.** 90.9% json_parse_ok is acceptable, but the grid defect triggers repeated bracket degeneration (499 tokens). This is a systematic issue, not a random failure.

### Q4: Does 2B LoRA reduce generic "anomaly" output?
**No.** LoRA has 83% anomaly rate vs base's 71%. LoRA is worse at specific defect type identification.

### Q5: Does 2B LoRA improve defect_type_exact?
**No.** Both variants have 0% defect_type_exact on the board.

### Q6: Does 2B LoRA improve good samples' "none" output?
**No.** LoRA has 0% none_rate vs base's 14% (screw). LoRA is worse.

### Q7: Does 2B LoRA introduce repeated brackets, fallback, abnormal output?
**Yes.** 1 repeated bracket frame (grid defect, 499 tokens). 1 fallback (carpet defect). 1 "region" output (screw defect). These are LoRA-specific issues.

### Q8: Is LoRA TTFT/decode_tps/RSS close to base?
**No.**
- TTFT: +51% (2837ms vs 1877ms)
- decode_tps: -30% (6.8 vs 9.7)
- RSS: identical (3285MB)
- Pipeline latency: +149% (26334ms vs 10548ms)

### Q9: Should 2B LoRA be included in formal 8B extended evaluation?
**Not in current form.** The repeated bracket degeneration, higher latency, and no quality improvement make 2B LoRA strictly worse than 2B base on the board. However, the LoRA adapter was trained with rank=32 on 15 classes — the board-side issues may be RKLLM quantization artifacts rather than training failures. A PC-side transformers evaluation (Phase 8B-PC) would clarify whether the LoRA adapter itself is sound.

### Q10: Should prompt/schema for good image handling be fixed first?
**Yes, this is the highest priority.** Both variants output "anomaly" for 86-100% of good images. The prompt forces a defect-oriented output format. Before any model variant comparison is meaningful, the prompt should be updated to support "no defect" as a valid output, or a post-processing step should check EfficientAD scores.

### Q11: Should 4B board A/B be deferred?
**Yes.** `qwen3vl_runner.cpp` still falls back to 2B base for 4B variants. No 4B board results are valid until the 4B path is implemented.

### Q12: Can we enter Phase 8C?
**Not yet.** Phase 8C is `image_loop_beat_ms` parameter sweep, which requires:
1. Selection of deployment variant → **2B base** is the clear winner
2. Understanding of T3 processing time distribution → Done (base: 10.5s mean, LoRA: 26.3s mean)
3. But the prompt/schema good image handling issue should be addressed first, as it affects the meaning of any beat_ms tuning

**Recommendation**: Fix prompt/schema good image handling (allow "none" output), then proceed to Phase 8C with 2B base only.

## 8. Recommendation

**Deploy 2B base, not 2B LoRA.** The LoRA adapter provides no quality improvement on the board and introduces significant latency and stability issues (repeated brackets, queue drops). The base model with engineered prompt is the better choice for RK3588 deployment.

The LoRA adapter's failure to improve over base on the board may be due to:
1. RKLLM W8A8 quantization degrading LoRA-specific weights
2. The LoRA prompt (minimal, ~50 tokens) being too short for the board context
3. Training data mismatch (PC eval set vs MVTec board images)

These should be investigated in Phase 8B-PC (transformers evaluation) before discarding the LoRA approach entirely.
