# Phase 8B-Board-2B-AB-Prep-v2: 2B LoRA Summary

Generated: 2026-05-22

## 1. Test Configuration

| Parameter | Value |
|-----------|-------|
| Variant | 2B_lora |
| Model | qwen3vl_2b_w8a8_lora_15cls.rkllm (2.3GB) |
| Vision | qwen3vl_2b_vision.rknn (812MB) |
| Gate mode | pass_all (bypasses T2 threshold) |
| Score mode | raw_score |
| Sample set | 14 images (7 categories x 2: 1 good + 1 defect each) |
| Beat interval | 20000ms, jitter=0 |
| Config | edge/config.phase8b_2b_lora_ab_v2.yaml |
| Board | Orange Pi 5 Plus 16GB (RK3588) |

## 2. Overall Results

| Metric | Value |
|--------|-------|
| Unique images seen | 11/14 |
| Upload success | 14/14 (100% of processed frames) |
| json_parse_ok | 10/11 (90.9%) |
| Fallback used | 1/11 (9.1%) |
| Repeated bracket frames | 1 (grid defect, 499 tokens) |
| Missing images | metal_nut good, metal_nut defect, zipper good |

## 3. Missing Images Explanation

3 images were dropped from the Q2 BoundedQueue because the grid defect (bent) image triggers a **repeated bracket degeneration** in the LoRA model, producing 499 output tokens (max_new_tokens limit). This ~50s VLM block causes subsequent metal_nut and zipper frames to overflow Q2 (capacity=2) and be dropped. Even with beat_ms=20000, the grid defect's 50s processing time exceeds the inter-frame interval.

## 4. VLM Performance (successful calls, n=10)

| Metric | Mean | Median | Min | Max |
|--------|------|--------|-----|-----|
| TTFT (ms) | 2837 | 3068 | - | - |
| decode_tps | 6.8 | - | - | - |
| RSS (MB) | 3285 | - | 3280 | 3297 |
| qwen3vl pipeline_ms | 26334 | - | - | - |
| output_tokens | 113 | - | - | 499 |

## 5. VLM Failure Analysis

- 1 fallback on carpet defect (color/011.png) — json_parse_ok=False
- 1 repeated bracket degeneration on grid defect (bent/011.png) — 499 tokens, JSON parse OK but malformed bboxes `[[[...`
- Grid defect is a systematic LoRA issue: model enters bracket repetition loop

## 6. Good vs Defect Analysis

### 6.1 Good Samples (n=5)

| Category | Predicted defect_type | Severity | Confidence |
|----------|----------------------|----------|------------|
| tile good | anomaly | low | 0.38 |
| carpet good | anomaly | high | 0.90 |
| grid good | anomaly | medium | 0.90 |
| pill good | anomaly | low | 0.89 |
| screw good | anomaly | low | 0.00 |

- **none_rate: 0/5 (0%)** — LoRA does NOT improve good image handling
- All good images get "anomaly" with LoRA, same as base

### 6.2 Defect Samples (n=6)

| Category | GT | Predicted | Severity | Confidence | Tokens |
|----------|-----|-----------|----------|------------|--------|
| tile crack | crack | anomaly | high | 0.98 | 72 |
| carpet color | color | (fallback) | high | 1.00 | 0 |
| grid bent | bent | anomaly | high | 1.00 | 499 |
| zipper broken_teeth | broken_teeth | anomaly | low | 0.30 | 73 |
| pill color | color | anomaly | low | 0.98 | 60 |
| screw scratch_head | scratch_head | region | low | 0.00 | 56 |

- **defect_type_exact: 0/6 (0%)** — LoRA does NOT improve defect type identification on board
- All outputs are "anomaly" except screw→"region" (wrong)
- Generic "anomaly" rate: 5/6 (83%)

## 7. Anomalies Detected

1. **Repeated brackets**: grid defect → `[[[0.00220382, ...` (499 tokens, hit max_new_tokens)
   - This is a systematic LoRA model degeneration on certain inputs
   - Causes ~50s VLM block, dropping subsequent frames from Q2
2. **Low confidence outputs**: screw defect/confidence=0.00, screw good/confidence=0.00
3. **"region" output**: screw defect predicted "region" instead of a valid defect_type

## 8. Files Generated

| File | Description |
|------|-------------|
| `board_2b_lora_ab_v2.log` | Full edge_pipeline stderr |
| `board_2b_lora_ab_v2_results.csv` | Per-frame results (11 rows, first cycle unique) |
| `board_2b_lora_ab_v2_summary.md` | This report |
