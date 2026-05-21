# Phase 8B-Board-2B-Smoke: 2B Base Summary

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
| Beat interval | 5000ms, jitter=0 |
| Config | edge/config.phase8b_2b_base_smoke.yaml |
| Board | Orange Pi 5 Plus 16GB (RK3588) |

## 2. Overall Results

| Metric | Value |
|--------|-------|
| Total frames processed | 20 (1.4 cycles through 14 images) |
| Unique images seen | 14 (all 14 fixed samples processed at least once) |
| Upload success | 20/20 (100%) |
| json_parse_ok | 17/20 (85%) |
| Fallback used | 3/20 (15%) |
| Queue drops | 0 |

## 3. VLM Performance (successful calls only, n=17)

| Metric | Mean | Median | Min | Max |
|--------|------|--------|-----|-----|
| TTFT (ms) | 2048 | 2106 | 1824 | 2460 |
| decode_tps | 9.3 | 9.2 | 8.8 | 10.1 |
| RSS (MB) | 3298 | 3299 | 3281 | 3299 |
| qwen3vl pipeline_ms | 11591 | 11136 | 9436 | 17786 |
| EfficientAD ms | 325 | 317 | 247 | 462 |
| FastSAM ms | 171 | 155 | 144 | 270 |
| prompt_tokens | 407 | 399 | 390 | 442 |
| output_tokens | 63 | 57 | 45 | 121 |

## 4. VLM Failure Analysis

3 failures, all on the **same image**: `tile/test/good/023.png`.

| Backend ID | Category | Image | qwen3vl_ms | Cause |
|------------|----------|-------|------------|-------|
| 137 | tile | good/023.png | 0.1ms | VLM returned immediately, no generation |
| 144 | tile | good/023.png | 0.0ms | Same — VLM init or inference failed |
| 151 | tile | good/023.png | 0.1ms | Same — consistent failure on this image |

All 3 failures show `qwen3vl_generate` trace duration of ~35-76 microseconds (not milliseconds), indicating the RKLLM inference call returned immediately without generating tokens. This is a **deterministic failure on a specific image**, not a random timeout. The tile defect image (crack/011.png) and all other categories succeed.

**Root cause hypothesis**: The tile good image may trigger an edge case in the vision encoder or prompt construction that causes RKLLM to fail silently. Needs investigation (but NOT in this round — see Task G).

## 5. Good vs Defect Analysis

### 5.1 Good Samples (n=12 results, 7 unique images)

| Category | Predicted defect_type | Severity | Confidence | VLM OK | Notes |
|----------|----------------------|----------|------------|--------|-------|
| tile good | anomaly | high | 1.00 | NO | VLM failed (3 occurrences) |
| carpet good | anomaly | medium | 0.36 | YES | Low confidence, "anomaly" |
| grid good | anomaly | low | 0.95 | YES | "anomaly" (3 occurrences) |
| metal_nut good | anomaly | medium | 0.95 | YES | "anomaly" (2 occurrences) |
| zipper good | anomaly | low | 0.95 | YES | "anomaly" (2 occurrences) |
| pill good | anomaly | low | 0.97 | YES | "anomaly" (2 occurrences) |
| screw good | none | low | 0.97 | YES | "none" (3 occurrences) |

**Key findings for good samples**:
- 10/12 VLM calls succeeded (83%).
- 6/7 unique good images get `defect_type="anomaly"` — the VLM does NOT output "no defect" for most categories.
- Only screw good correctly outputs `defect_type="none"`.
- This is expected: the prompt asks "Inspect for defects" and the VLM tends to report observations even on normal images.
- **Good samples are used to inspect normal-sample behavior, not defect_type accuracy.** The prompt/schema forces a defect-oriented output format.

### 5.2 Defect Samples (n=8 results, 7 unique images)

| Category | GT defect_type | Predicted defect_type | Severity | Confidence | VLM OK |
|----------|---------------|----------------------|----------|------------|--------|
| tile defect (crack) | crack | anomaly | medium | 0.90 | YES |
| carpet defect (color) | color | anomaly | medium/high | 0.36-1.00 | YES |
| grid defect (bent) | bent | crack / anomaly | medium/low | 0.95 | YES |
| metal_nut defect (bent) | bent | anomaly | medium | 0.95 | YES |
| zipper defect (broken_teeth) | broken_teeth | missing_pin | low | 0.98 | YES |
| pill defect (color) | color | anomaly | low | 0.97 | YES |
| screw defect (scratch_head) | scratch_head | anomaly | medium | 0.95 | YES |

**Key findings for defect samples**:
- 7/8 VLM calls succeeded (88%).
- 7/7 unique defect images successfully processed.
- **defect_type accuracy**: 0/7 exact match. All output "anomaly" except:
  - grid defect: "crack" (close but wrong — GT is "bent")
  - zipper defect: "missing_pin" (close but wrong — GT is "broken_teeth")
- **severity**: Mostly "low" or "medium". Carpet defect shows variable confidence (0.36 vs 1.00) suggesting instability.
- The 2B base model with engineered prompt detects that defects exist but cannot reliably identify specific defect types.

## 6. Pass/Fail Gate Observation

With `gate_mode=pass_all`, ALL frames enter T3 regardless of EfficientAD score. The logs show:
- tile good: score=38.22 < threshold=38.31 → `PASS_ALL_WOULD_DROP` (would have been filtered in threshold mode)
- This confirms pass_all successfully bypasses the T2 threshold gate.

## 7. Answers to Required Questions

### Q1: Did 2B base board smoke pass?

**Yes.** The pipeline processed all 14 fixed sample images, uploaded 20 results (1.4 cycles), and collected VLM metrics. The T1→T2→T3→T4→Backend chain is fully functional.

### Q2: Is the fixed sample input method reliable? Only 14 images?

**Yes.** The dedicated directory `fixed_sample_images/` with MVTec-compatible structure works correctly with image_loop. Each category's `test/` directory contains exactly 2 images (1 good + 1 defect). The capture worker sees only these 14 images total.

### Q3: Did pass_all successfully bypass T2 threshold gate?

**Yes.** Logs confirm `decision=PASS_ALL_WOULD_DROP` for frames below threshold — they are still pushed to Q2.

### Q4: Did backend receive 14 results?

**Yes.** Backend received 20 results (14 in first cycle + 6 in partial second cycle). All 14 unique images were processed at least once.

### Q5: json_parse_ok / fallback situation?

- json_parse_ok: 17/20 (85%)
- 3 failures all on tile good image (deterministic VLM failure)
- Fallback JSON generated for failed frames: `{"defect_type":"anomaly","severity":"high","confidence":1.0}`

### Q6: TTFT / decode_tps / RSS / qwen3vl latency observable?

**Yes, fully observable** from backend `vlm_metrics` and `pipeline_ms` fields:
- TTFT: mean 2048ms
- decode_tps: mean 9.3
- RSS: 3298MB (stable)
- qwen3vl: mean 11591ms

### Q7: Do good images need separate prompt/schema treatment?

**Yes, this is a known limitation.** The current prompt forces defect-oriented output. Good images get `defect_type="anomaly"` instead of "none" (except screw). For production, the prompt should be updated to allow "no defect" as a valid output, or a post-processing step should check if the EfficientAD score is below a "likely normal" threshold.

### Q8: Can we proceed to 2B base vs 2B LoRA A/B?

**Yes.** The smoke test validates the full pipeline. The 2B LoRA test can use the same fixed sample directory and config (with `vlm_variant: "lora"`).

## 8. Files Generated

| File | Description |
|------|-------------|
| `board_2b_base_smoke.log` | Full edge_pipeline stderr (1536 lines) |
| `board_2b_base_smoke_results.csv` | Per-frame results (20 rows) |
| `board_2b_base_smoke_summary.md` | This report |

## 9. Known Issues for Follow-up

1. **Tile good VLM failure**: Deterministic failure on `tile/test/good/023.png`. Needs investigation (possible vision encoder edge case or prompt issue).
2. **defect_type accuracy**: 2B base with engineered prompt outputs "anomaly" for most defects. LoRA fine-tuning should improve this.
3. **Good image handling**: Prompt schema forces defect output on normal images. Consider prompt update or post-processing.
4. **Carpet confidence instability**: Same carpet color defect image gets conf=0.36 in some runs, conf=1.00 in others (different cycles show different results).
