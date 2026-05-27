# Phase 10.1b-5d Snapshot Telemetry Precheck Report

**Date**: 2026-05-27
**Branch**: `phase10.1b/live-soak-runner-dryrun-presoak`
**Base**: `bf9332a`

---

## 1. Scope

- Snapshot display completeness precheck only.
- No 200/500 full soak.
- No public snapshot capture.
- No Phase 10.1b-5d success claim.
- No backend behavior change.
- No schema change.
- No model logic change.

---

## 2. Problem

Runner-generated uploads had two display gaps in the frontend:

1. **Empty Profile / Trace page**: `pipeline_ms` was `{efficientad: 0, fastsam: 0, qwen3vl: 0}` and `trace_events` was absent. The frontend Profile/Chrome Trace page rendered empty.

2. **VLM display confusion**: The `description` field (runner metadata like "production_yolo_soak cable/bent_wire") was sometimes confused with VLM output. The actual VLM enrichment output is `observation`, `severity_reason`, and `observation_source`.

---

## 3. Telemetry Design

### pipeline_ms

Runner-derived wall-clock timing, not hardware-level NPU trace:

```json
{
  "efficientad": 0,
  "fastsam": 0,
  "localizer": <yolo_total_ms>,
  "upload": <upload_latency_ms>,
  "enrichment": <enrichment_latency_ms>,
  "qwen3vl": <enrichment_latency_ms>
}
```

- `localizer`: YOLOv8n ONNX Runtime CPU inference time from `ort_localizer.py` (`total_ms` field).
- `upload`: HTTP POST latency in ms.
- `enrichment`: Time from upload to enrichment terminal state in ms.
- `qwen3vl`: Same as enrichment (EdgeVLM subprocess wraps the VLM call).
- `efficientad` / `fastsam`: 0 (not part of runner pipeline).

### trace_events

Chrome Trace format events (ts/dur in microseconds):

| Event Name | Category | Thread ID | Duration Source |
|------------|----------|-----------|-----------------|
| YOLO localizer | localizer | T3.localizer | ort_localizer.py total_ms |
| upload POST | upload | T4.upload | HTTP POST wall-clock |
| EdgeVLM enrichment | vlm | T3.vlm | Enrichment poll wall-clock |

Events are sequential: localizer ts=0, upload ts=localizer_dur, enrichment ts=localizer_dur+upload_dur.

### Caveat

Each snapshot record includes:
- `trace_source: "runner_derived"`
- `trace_caveat: "Runner-derived localizer/upload/enrichment wall-clock trace; not hardware-level RK3588 NPU trace."`

No NPU.core0/core1/core2 events are included (no real hardware-level timings available from the runner).

---

## 4. Validation Result

**Sample size**: 5 uploads (ids 4171-4175)
**Mode**: `pre-soak --limit 5 --snapshot-output`

| Check | Result |
|-------|--------|
| pipeline_ms.localizer > 0 | PASS (186-201 ms) |
| pipeline_ms.upload > 0 | PASS (1628-1871 ms) |
| pipeline_ms.enrichment > 0 | PASS (12901-21980 ms) |
| trace_events length >= 3 | PASS (3/3 per record) |
| T3.localizer present | PASS (5/5) |
| T4.upload present | PASS (5/5) |
| T3.vlm present | PASS (5/5) |
| observation non-empty | PASS (5/5) |
| severity_reason non-empty | PASS (5/5) |
| observation_source = edge_vlm | PASS (5/5) |
| trace_source = runner_derived | PASS (5/5) |
| trace_caveat present | PASS (5/5) |
| 0 HTTP 409 conflicts | PASS |
| 0 upload errors | PASS |
| All canonical fields from YOLO | PASS |

### Sample Telemetry (id=4171)

```
pipeline_ms: localizer=194.3  upload=1635.0  enrichment=21980.0
trace_events:
  [0] YOLO localizer       T3.localizer  dur=194300us
  [1] upload POST           T4.upload     dur=1635000us
  [2] EdgeVLM enrichment    T3.vlm        dur=21980000us
```

### VLM Output Fields (id=4171)

```
observation: "Three insulated wires with copper cores; one wire shows slight bending at the en..."
severity_reason: "Minor bend may affect performance but not critical to safety or function."
observation_source: edge_vlm
```

Note: `description` ("production_yolo_soak cable/bent_wire") is runner detection metadata, not VLM output.

### Frontend Profile Page Expected Display

With `trace_events` present and non-zero `pipeline_ms`, the frontend Profile/Chrome Trace page should render:
- Three horizontal bars (localizer, upload, enrichment)
- Total wall-clock duration visible
- Thread lanes: T3.localizer, T4.upload, T3.vlm

This is runner-derived timing, not hardware NPU trace. The page will not show EfficientAD/FastSAM/Qwen3-VL NPU events.

---

## 5. Safety

| Constraint | Status |
|------------|--------|
| No canonical fields fabricated | PASS |
| No bbox/category/defect_type/confidence fabrication | PASS |
| All canonical fields from YOLO inference | PASS |
| Invalid ids 4113-4150 excluded | PASS |
| No secrets/private paths/tokens in report | PASS |
| No backend behavior change | PASS |
| No schema change | PASS |
| No model logic change | PASS |

---

## 6. Decision Gate

**Status: PASS**

All validation criteria met:
- Runner-derived telemetry produces non-zero pipeline_ms and 3+ trace_events
- VLM enrichment fields (observation, severity_reason, observation_source) are populated
- No canonical fields fabricated
- Frontend Profile page should display non-empty trace from snapshot overlay data

**Next steps**:
1. Run 200 full soak with runner-derived telemetry enabled (`--snapshot-output`)
2. After 200 pass, capture public snapshot with complete display data
3. Public snapshot should use snapshot overlay JSON for Profile/Trace page data

---

## 7. Explicit Not Done

- No 200/500 full soak.
- No public snapshot capture.
- No public demo switch.
- No backend/frontend behavior change.
- No EDGE_VLM_MODE=http.
- No cloud_vlm.
- No schema changes.
- No YOLO/ORT/RKNN/LoRA model changes.
- No hardware-level NPU trace events (not available from runner).
