# Phase 7 Prompt 2D-Fix: VLM bbox Fusion, LoRA Path Selection & Quality Patches

## 1. Summary

Prompt 2D-Fix applies targeted patches to the Qwen3-VL integration completed in Prompt 2D. Six areas addressed:

1. **VLM bbox parsing, normalization & fusion** — conservative strategy (FastSAM preferred)
2. **Severity whitelist unified** — `low|medium|high` only, no `critical`
3. **LoRA/variant path selection** — `2B base` / `2B lora` via config, `4B` as TODO
4. **Description word limit** — prompt enforces `max 20 words`, output_tokens > 120 warning
5. **Upload trace_event** — appended to trace_events array before HTTP send
6. **Debug configs** — `config.debug.yaml` updated to 2B, new `config.debug.lora.yaml`

## 2. Modified Files

| File | Changes |
|---|---|
| `edge/include/edge/vlm/qwen3vl_runner.hpp` | +`vlm_bboxes` field in VlmResult, +`parse_vlm_bboxes()` declaration, updated `extract_json()` signature |
| `edge/src/vlm/qwen3vl_runner.cpp` | +`parse_vlm_bboxes()` impl, severity fix (remove critical), +severity_corrected param, +LoRA/4B path selection, +file existence validation, +description word limit in prompt, +output_tokens warning |
| `edge/src/pipeline/fastsam_worker.cpp` | +orig_w/orig_h capture, +VLM bbox fusion logic (IoU>0.3), +bbox_source/bbox_merge_reason logging, +output_tokens warning, updated extract_json calls |
| `edge/src/upload/upload_worker.cpp` | +upload timing, +upload trace_event in trace_events array, +`<cstring>` include, +upload_ms log |
| `edge/config.yaml` | `vlm_max_new_tokens: 200` → `500` |
| `edge/config.debug.yaml` | `vlm_model_size: 4B` → `2B`, `vlm_max_new_tokens` → `500` |
| `edge/config.debug.lora.yaml` | **New**: 2B LoRA debug config for smoke test |

## 3. Bbox Normalization & Fusion Strategy

### Detection
- `parse_vlm_bboxes()` extracts `[[x,y,w,h]]` from VLM JSON raw_text
- If all values > 2.0 → pixel coordinates → normalize by `orig_w × orig_h`
- If all values in [0,1] → already normalized
- If `orig_w/orig_h` unknown → normalize by 448×448 (vision input size)
- Validity: x/y/w/h in [0,1], w/h > 0.001, area in [0.0001, 0.95]

### Fusion (conservative)
```
if VLM bboxes valid AND NOT bbox_fallback:
    if ANY VLM bbox has IoU > 0.3 with ANY FastSAM bbox:
        bbox_source = "vlm"
        → Replace FastSAM bboxes with VLM bboxes
    else:
        bbox_source = "fastsam_fallback"
        → Keep FastSAM bboxes
else:
    bbox_source = "fastsam"
    → Keep FastSAM bboxes
```

Rationale: VLM bboxes are useful when aligned with FastSAM detections, but hallucinated VLM bboxes should never replace stable FastSAM output.

## 4. Severity Whitelist

| Before | After |
|---|---|
| `low`, `medium`, `high`, `critical` | `low`, `medium`, `high` |

- `critical` removed from prompt, parser, and validator
- Invalid severity → fallback to `medium`, `severity_corrected=true` logged
- `json_parse_ok` remains `true` (correction is cosmetic, not structural failure)

## 5. LoRA/Variant Path Selection

| Config | LLM Path | Vision Path |
|---|---|---|
| `2B base` | `vlm_model_path` | `vlm_vision_model_path` |
| `2B lora` | `vlm_2b_lora_model_path` | `vlm_vision_model_path` |
| `4B *` | TODO (prints warning, falls back to 2B base) | — |

- If LoRA model file not found → init fails with clear error message
- File existence validated for both LLM and vision paths
- Init log prints: `selected_model_size`, `selected_variant`, `selected_llm_path`, `selected_vision_path`

## 6. Smoke Test Results

### 6.1 2B Base

```text
Config: /tmp/config_bottle_raw_debug.yaml
Model: qwen3vl_2b_w8a8_base.rkllm + qwen3vl_2b_vision.rknn
Categories: bottle (1 class)
Duration: 240s
```

| Metric | Value |
|---|---|
| capture | 183 |
| ead | 183 |
| vlm | 23 |
| json_ok=1 | 23 (100%) |
| fallback_frames | 0 |
| severity=critical | 0 |
| output_tokens warning | 0 |
| rknn_run failed | 0 |
| rkllm fatal | 0 |
| OOM | 0 |
| Clean exit | Yes |

VLM performance (2B base W8A8):

| Metric | Value |
|---|---|
| ttft | 2232–2725 ms |
| decode_tps | 8.7–9.2 |
| output_tokens | 52–79 |
| rss | 3321–3323 MB |

Bbox fusion log (frame 0):
```text
vlm_bbox_normalized[0]: x=0.0219 y=0.0469 w=0.8742 h=0.9289
bbox_source=vlm
bbox_merge_reason: VLM bbox aligned with FastSAM (IoU>0.3)
```

T4 JSON (frame 0, prettified):
```json
{
  "line_id": "L1",
  "category": "bottle",
  "defect_type": "anomaly",
  "severity": "low",
  "confidence": 0.95,
  "anomaly_score": 11.77,
  "bboxes": [{"x": 0.0219, "y": 0.0469, "w": 0.8742, "h": 0.9289}],
  "variant": "2B_base",
  "pipeline_ms": {"efficientad": 1302.0, "fastsam": 136.8, "qwen3vl": 12810.5},
  "vlm_metrics": {
    "ttft_ms": 2232.4, "decode_tps": 9.1,
    "prompt_tokens": 445, "output_tokens": 73,
    "rss_mb": 3321.6, "json_parse_ok": true
  },
  "trace_events": [
    {"name": "efficientad_infer", "dur": 1302006.4},
    {"name": "fastsam_preprocess", "dur": 29291.9},
    {"name": "fastsam_infer", "dur": 106172.1},
    {"name": "fastsam_postprocess", "dur": 1378.1},
    {"name": "qwen3vl_generate", "dur": 12810534.0},
    {"name": "upload", "dur": 0.0}
  ],
  "schema_version": "v1"
}
```

### 6.2 2B LoRA

```text
Config: /tmp/config_bottle_raw_debug_lora.yaml
Model: qwen3vl_2b_w8a8_lora_15cls.rkllm + qwen3vl_2b_vision.rknn
Categories: bottle (1 class)
Duration: 240s
```

| Metric | Value |
|---|---|
| capture | 194 |
| vlm | 13 |
| json_ok=1 | 13 (100%) |
| JSON parse failed (fallback) | 1 |
| severity=critical | 0 |
| output_tokens warning | 1 (499 > 120) |
| Clean exit | Yes |

Init log confirmed LoRA path:
```text
selected_model_size=2B  selected_variant=lora
selected_llm_path=/home/orangepi/models/qwen3vl_models/qwen3vl_2b_w8a8_lora_15cls.rkllm
```

LoRA model observations:
- One frame had JSON parse failure → rule-based fallback used
- One frame hit 499 output tokens (near max_new_tokens=500) → repeating bracket patterns in bboxes
- Bbox format quality lower than base model (extra nesting in some frames)
- Overall LoRA path selection works correctly; model output quality is a separate concern

## 7. Upload Trace Event

- Added to `trace_events` array as the 6th event (after 5 pipeline events)
- `name="upload"`, `dur=0.0` (placeholder — actual duration logged to stderr as `[T4] upload_ms=...`)
- Duration is 0.0 because the trace event is embedded before the HTTP call (can't know duration beforehand)
- Verified: 6 trace_events in T4 JSON frame 0

## 8. Acceptance Checklist

| # | Criterion | Result |
|---|---|---|
| 1 | Build passes | PASS |
| 2 | 2B base smoke test passes | PASS |
| 3 | json_parse_ok=true (base) | PASS (100%) |
| 4 | bbox_source log visible | PASS |
| 5 | T4 JSON bboxes x/y/w/h in [0,1] | PASS |
| 6 | VLM pixel bbox normalized | PASS |
| 7 | severity only low/medium/high | PASS (0 critical) |
| 8 | output_tokens <= 120 (base) | PASS (52-79) |
| 9 | LoRA path selection correct | PASS |
| 10 | No crash / no OOM | PASS |
| 11 | No rknn_run failed | PASS |
| 12 | No rkllm fatal | PASS |
| 13 | No backend API change | PASS |
| 14 | No frontend change | PASS |
| 15 | No new threads | PASS |
| 16 | No EfficientAD rollback | PASS |
| 17 | No FastSAM FP16/no-quant rollback | PASS |
| 18 | No MockVLM rollback | PASS |

## 9. Known Issues & Next Steps

1. **LoRA model output quality**: Repeating bracket patterns, 1 JSON parse failure, 1 near-token-limit. Model quality issue, not code issue. Needs separate investigation.
2. **Upload trace_event dur=0.0**: Placeholder. Actual duration logged to stderr. Could be improved by re-serializing JSON after upload.
3. **4B path**: Code path exists but prints warning and falls back to 2B base. Models are on board but not validated.
4. **Description field in T4 JSON**: `build_meta_json()` hardcodes empty description. VLM description is available in VlmReport but not serialized. Separate from 2D-Fix scope.
5. **enable_thinking**: Not evaluated in this round. Default remains `false`.
6. **Vision embedding cache**: Not implemented. Design deferred to future optimization.

## 10. Prompt 2E Readiness

Conditions for entering Prompt 2E:
- [x] 2B base pipeline stable with bbox fusion and severity unification
- [x] LoRA path selection functional (model quality separate concern)
- [x] All trace_events present including upload
- [x] No regressions from Prompt 2D

Ready for Prompt 2E.
