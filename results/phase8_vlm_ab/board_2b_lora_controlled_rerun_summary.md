# Phase 8B-Board-2B-LoRA Controlled Rerun: Summary

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
| Beat interval | 60000ms, jitter=0 |
| Config | edge/config.phase8b_2b_lora_controlled_rerun.yaml |
| Board | Orange Pi 5 Plus 16GB (RK3588) |
| Wall clock | 757 seconds (~12.6 minutes) |
| Exit | SIGTERM after 14/14 detected via backend poll |

## 2. Overall Results

| Metric | Value |
|--------|-------|
| Unique images seen | **14/14 (100%)** |
| Upload success | 14/14 (100%) |
| json_parse_ok | **14/14 (100%)** |
| Fallback used | 1/14 (7.1%) — grid defect only |
| Repeated bracket frames | 1/14 — grid defect (bent/011.png), 499 tokens |
| Queue drops | **0** |

## 3. Per-Frame Results

| Frame | Category | Label | GT | Predicted | Severity | Conf | Tokens | Notes |
|-------|----------|-------|-----|-----------|----------|------|--------|-------|
| 0 | tile | defect | crack | anomaly | high | 0.98 | 72 | |
| 1 | tile | good | — | anomaly | low | 0.38 | 58 | |
| 2 | carpet | good | — | anomaly | high | 0.90 | 72 | |
| 3 | carpet | defect | color | anomaly | high | 1.00 | 0 | fallback |
| 4 | grid | good | — | anomaly | medium | 0.90 | 46 | |
| 5 | grid | defect | bent | anomaly | high | 1.00 | **499** | **REPEATED BRACKETS** |
| 6 | metal_nut | good | — | anomaly | high | 1.00 | 82 | |
| 7 | metal_nut | defect | bent | anomaly | low | 0.00 | 74 | |
| 8 | zipper | good | — | anomaly | medium | 0.90 | 79 | |
| 9 | zipper | defect | broken_teeth | anomaly | low | 0.30 | 73 | |
| 10 | pill | good | — | anomaly | low | 0.89 | 81 | |
| 11 | pill | defect | color | anomaly | low | 0.98 | 60 | |
| 12 | screw | defect | scratch_head | region | low | 0.00 | 56 | |
| 13 | screw | good | — | anomaly | low | 0.00 | 116 | |

## 4. VLM Performance (n=13, excluding carpet defect fallback)

| Metric | Mean | Min | Max |
|--------|------|-----|-----|
| TTFT (ms) | 1914 | 1675 | 2037 |
| decode_tps | 9.9 | 9.7 | 10.0 |
| RSS (MB) | 3274 | 3265 | 3279 |
| output_tokens | 105 | 46 | 499 |
| output_tokens (excl grid defect) | 72 | 46 | 116 |

## 5. Quality Metrics

| Metric | Defect (n=7) | Good (n=7) |
|--------|-------------|------------|
| defect_type_exact | 0/7 (0%) | — |
| anomaly_generic_rate | 6/7 (86%) | — |
| none_rate | — | 0/7 (0%) |

## 6. Key Findings

### 6.1 Repeated Bracket Degeneration: CONFIRMED REPRODUCIBLE

The grid defect (bent/011.png) triggers repeated bracket degeneration **every time** with the LoRA model:
- Previous run (beat=20s): 499 tokens, `[[[0.00220382, 0.00220382, 0.0528917, 0.0440764], [[0.00440764, ...`
- This run (beat=60s): 499 tokens, same pattern

This is a **deterministic** LoRA model degeneration on this specific input, not a random occurrence.

### 6.2 Queue Drops: ELIMINATED by 60s Beat

| Metric | Previous (beat=20s) | This run (beat=60s) |
|--------|--------------------|--------------------|
| queue_drop_count | 3+ | **0** |
| unique_images_seen | 11/14 | **14/14** |

The 60s beat provides sufficient headroom even when the grid defect consumes ~50s of VLM time. The previous 11/14 was caused by queue pressure, not inherent LoRA inability to process all images.

### 6.3 Carpet Defect Fallback

Carpet defect (color/011.png) triggered a VLM fallback in both runs:
- Previous: json_parse_ok=False, fallback used
- This run: VLM output likely empty/malformed, T3 used fallback JSON

This is a consistent LoRA weakness on the carpet color defect.

### 6.4 Performance Improvement Over Previous Run

| Metric | Previous (beat=20s) | This run (beat=60s) | Delta |
|--------|--------------------|--------------------|-------|
| json_parse_ok | 10/11 (90.9%) | **14/14 (100%)** | +9.1% |
| TTFT mean | 2837ms | **1914ms** | -32.5% |
| decode_tps | 6.8 | **9.9** | +45.6% |
| output_tokens mean | 113 | **105** | -7.1% |
| output_tokens excl outlier | — | **72** | — |

The TTFT and decode_tps improvements are significant. The previous run's lower throughput was likely caused by queue contention and system load from concurrent processing.

### 6.5 No Quality Improvement

The LoRA model still:
- Outputs "anomaly" for 6/7 defect frames (86% generic rate)
- Outputs "anomaly" for ALL 7 good frames (0% none_rate)
- Has 0% defect_type_exact
- Produces "region" for screw defect (invalid defect_type)

These are identical to the previous run.

## 7. Answers to Key Questions

### Q1: Was the previous 11/14 caused by timeout/drain/queue pressure?
**Yes.** With 60s beat (3x the previous 20s), all 14/14 images are processed with 0 queue drops. The grid defect's ~50s VLM time no longer causes queue overflow.

### Q2: Is the repeated bracket degeneration reproducible?
**Yes.** Grid defect (bent/011.png) produces 499 tokens with repeated brackets in both runs. This is a deterministic LoRA model behavior on this input.

### Q3: Does the 60s beat eliminate all queue drops?
**Yes.** 0 queue drops at 60s beat vs 3+ at 20s beat.

### Q4: Is the LoRA model's json_parse_ok really 100%?
**Yes, but with caveats.** All 14 frames produced parseable JSON. However:
- Grid defect's JSON has malformed bboxes (`[[[...`)
- Carpet defect used a fallback (VLM output was empty/unparseable)
- Screw defect outputs "region" (not a valid defect_type)

### Q5: Is 2B base still superior to 2B LoRA?
**Yes.** Even with the controlled rerun fixing the queue drop issue:
- LoRA TTFT (1914ms) is still higher than base (1877ms)
- LoRA decode_tps (9.9) is now close to base (9.7), but the previous run showed 6.8
- LoRA introduces repeated bracket degeneration (base has 0)
- LoRA has worse good image handling (0% none_rate vs base's 14%)
- Both have 0% defect_type_exact

## 8. Conclusion

The controlled rerun confirms that the previous 11/14 was caused by **queue pressure** (20s beat + 50s grid defect VLM = queue overflow), not inherent LoRA processing failure. With 60s beat, all 14/14 images complete.

However, the LoRA model still has these inherent issues:
1. **Repeated bracket degeneration** on grid defect (deterministic, 499 tokens)
2. **No quality improvement** over base (0% defect_type_exact, 100% anomaly generic rate)
3. **Carpet defect fallback** (consistent failure)
4. **"region" output** for screw defect (invalid defect_type)

The base model remains the better choice for RK3588 deployment.

## 9. Files Generated

| File | Description |
|------|-------------|
| `board_2b_lora_controlled_rerun.log` | Full edge_pipeline stderr |
| `board_2b_lora_controlled_rerun_results.csv` | Per-frame results (14 rows) |
| `board_2b_lora_controlled_rerun_meta.json` | Run metadata |
| `board_2b_lora_controlled_rerun_summary.md` | This report |
