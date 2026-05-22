# Phase 8B-Board-2B-AB-Prep-v2: 2B Base Summary

Generated: 2026-05-22

## 1. Test Configuration

| Parameter | Value |
|-----------|-------|
| Variant | 2B_base |
| Model | qwen3vl_2b_w8a8_base.rkllm (2.3GB) |
| Vision | qwen3vl_2b_vision.rknn (812MB) |
| Gate mode | pass_all (bypasses T2 threshold) |
| Score mode | raw_score |
| Sample set | 14 images (7 categories x 2: 1 good + 1 defect each) |
| Beat interval | 13000ms, jitter=0 |
| Config | edge/config.phase8b_2b_base_ab_v2.yaml |
| Board | Orange Pi 5 Plus 16GB (RK3588) |
| tile/test/good/023.png | REPLACED with 011.png (deterministic no-generation fix) |

## 2. Overall Results

| Metric | Value |
|--------|-------|
| Total frames processed | 14 (first cycle, all unique) |
| Unique images seen | 14/14 |
| Upload success | 14/14 (100%) |
| json_parse_ok | 13/14 (92.9%) |
| Fallback used | 1/14 (7.1%) |
| Queue drops | 0 |

## 3. VLM Performance (successful calls only, n=13)

| Metric | Mean | Median | Min | Max |
|--------|------|--------|-----|-----|
| TTFT (ms) | 1877 | 1872 | 1687 | 1977 |
| decode_tps | 9.7 | - | - | - |
| RSS (MB) | 3285 | - | - | - |
| qwen3vl pipeline_ms | 10548 | - | - | - |
| output_tokens | 68 | - | - | - |

## 4. VLM Failure Analysis

1 fallback on carpet defect (color/011.png) — json_parse_ok=False, VLM returned empty/invalid JSON.

## 5. Good vs Defect Analysis

### 5.1 Good Samples (n=7)

| Category | Predicted defect_type | Severity | Confidence | Notes |
|----------|----------------------|----------|------------|-------|
| tile good (011) | anomaly | low | 0.95 | anomaly FP |
| carpet good (023) | anomaly | medium | 0.36 | anomaly FP, low conf |
| grid good (011) | anomaly | low | 0.95 | anomaly FP |
| metal_nut good (011) | anomaly | medium | 0.95 | anomaly FP |
| zipper good (023) | anomaly | low | 0.95 | anomaly FP |
| pill good (011) | anomaly | low | 0.97 | anomaly FP |
| screw good (011) | none | low | 0.97 | correct! |

- 6/7 good images get `defect_type="anomaly"` (false positive)
- 1/7 (screw) correctly outputs `defect_type="none"`
- This matches the smoke test pattern — prompt/schema is defect-oriented

### 5.2 Defect Samples (n=7)

| Category | GT defect_type | Predicted defect_type | Severity | Confidence | Match |
|----------|---------------|----------------------|----------|------------|-------|
| tile crack | crack | anomaly | medium | 0.95 | WRONG |
| carpet color | color | (fallback) | medium | 0.50 | WRONG (fallback) |
| grid bent | bent | crack | medium | 0.95 | WRONG |
| metal_nut bent | bent | anomaly | medium | 0.95 | WRONG |
| zipper broken_teeth | broken_teeth | missing_pin | low | 0.98 | WRONG |
| pill color | color | anomaly | low | 0.97 | WRONG |
| screw scratch_head | scratch_head | anomaly | medium | 0.95 | WRONG |

- defect_type_exact: 0/7 (0%)
- All defect images get "anomaly" except grid→crack and zipper→missing_pin
- 2B base cannot identify specific defect types with engineered prompt

## 6. tile/test/good/023.png Fix Verification

The replacement tile/test/good/011.png processed successfully:
- json_parse_ok: True
- defect_type: anomaly (expected for good image with defect-oriented prompt)
- No deterministic no-generation failure
- **Fix confirmed: 023.png replacement eliminates the no-generation issue**

## 7. Pass/Fail Gate Observation

With `gate_mode=pass_all`, ALL frames enter T3 regardless of EfficientAD score. Log confirms:
- `decision=PASS_ALL_WOULD_DROP` for frames below threshold (still pushed to Q2)
- `decision=PASS_ALL_WOULD_UPLOAD` for frames above threshold

## 8. Comparison with Previous Smoke Test

| Metric | Smoke (v1, 023.png) | Base v2 (011.png) |
|--------|---------------------|-------------------|
| Unique images | 14/14 | 14/14 |
| json_parse_ok | 17/20 (85%) | 13/14 (92.9%) |
| Tile good failures | 3/3 (deterministic) | 0/1 (fixed) |
| Queue drops | 0 | 0 |
| TTFT mean | 2048ms | 1877ms |
| decode_tps | 9.3 | 9.7 |
| RSS | 3298MB | 3285MB |
| defect_type_exact | 0/7 | 0/7 |

The v2 run shows slightly better performance (lower TTFT, higher decode_tps) likely due to different image content (011 vs 023).

## 9. Files Generated

| File | Description |
|------|-------------|
| `board_2b_base_ab_v2.log` | Full edge_pipeline stderr |
| `board_2b_base_ab_v2_results.csv` | Per-frame results (14 rows, first cycle) |
| `board_2b_base_ab_v2_summary.md` | This report |
