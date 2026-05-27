# Phase 10.1b-4: Frontend / WebSocket Enrichment UX

**Date:** 2026-05-27
**Scope:** Realtime enrichment lifecycle UX via existing WebSocket channel
**Type:** Local enrichment UX polish — NOT a full frontend redesign

---

## Summary

Adds realtime WebSocket events for enrichment lifecycle state transitions
(pending / running / complete / rejected / failed) and corresponding frontend
UX indicators. The enrichment subsystem remains narrative-only: VLM may update
`observation`, `severity_reason`, and `observation_source` only. Geometry,
canonical label, confidence, and anomaly score are never modified.

---

## Event Schema

```json
{
  "type": "defect_enrichment_updated",
  "defect_id": 123,
  "enrichment_id": 456,
  "status": "pending | running | complete | rejected | failed",
  "provider": "template | edge_vlm | cloud_vlm",
  "observation_source": "template | edge_vlm | cloud_vlm",
  "updated_fields": ["observation", "severity_reason", "observation_source"],
  "error_message": "sanitized optional string",
  "ts": "ISO-8601"
}
```

Events are broadcast on the existing `dashboard` WebSocket room alongside
`defect_created`, `metrics_tick`, and `ping` messages.

---

## Backend Event Emission Points

| Location | Status | Trigger |
|---|---|---|
| `enrichment.py::trigger_enrichment` | `pending` | Manual POST `/api/defects/{id}/enrich` |
| `enrichment_enqueue.py::maybe_auto_enqueue_enrichment` | `pending` | Auto-enqueue on defect creation |
| `enrichment_worker.py::process_enrichment_job` | `running` | Job picked up by worker |
| `enrichment_worker.py::process_enrichment_job` | `complete` | Provider returned valid output |
| `enrichment_worker.py::process_enrichment_job` | `rejected` | Guard validation failed |
| `enrichment_worker.py::process_enrichment_job` | `failed` | Provider error / image resolution error |

Event emission is best-effort: failures are logged at DEBUG level and never
block the enrichment pipeline or defect creation.

---

## Hard Safety Boundaries

### Worker/provider write boundary (unchanged)

**May write only:**
- `defects.observation`
- `defects.severity_reason`
- `defects.observation_source`

**Must never write:**
- `defects.bboxes`
- `defects.category`
- `defects.defect_type`
- `defects.confidence`
- `defects.anomaly_score`
- `defects.localization_source`
- `defects.label_source`
- masks, train labels

### Error sanitization

All error messages in WS events are sanitized by `sanitize_error_message()`:
- Filesystem paths → `[redacted]`
- IP addresses → `[redacted]`
- Tokens/keys/secrets/passwords → `[redacted]`
- sshpass patterns → `[redacted]`
- EDGE_VLM_COMMAND values → `[redacted]`
- Stack trace file:line patterns → `[redacted]`
- Truncated to 200 characters

### Non-blocking upload

`POST /api/edge/report` remains non-blocking. Auto-enqueue creates a pending
job only; the provider is never called during the upload path.

---

## Frontend UX States

| Enrichment Status | Badge | Observation Display | Behavior |
|---|---|---|---|
| (none) | Hidden | Template/detector observation | Default state |
| `pending` | Gray pulsing | Template observation + "Queued…" note | Waiting for worker |
| `running` | Green pulsing | Template observation + "Processing…" note | Worker active |
| `complete` | Green solid "ENRICHED" | EdgeVLM observation + severity_reason | VLM narrative replaces template |
| `rejected` | Amber "REJECTED" | Template observation + warning note | Guard rejected VLM output |
| `failed` | Red "FAILED" | Template observation + error note | Provider error, fallback active |

All states include a provenance note:
> "VLM enrichment is narrative-only: observation / severity_reason / observation_source. BBox, category, defect_type, confidence, anomaly_score are unchanged."

---

## Frontend Components Changed

| File | Change |
|---|---|
| `frontend/src/lib/ws.ts` | Added `EnrichmentUpdate` type and optional `onEnrichment` callback to `useDefectWebSocket` |
| `frontend/src/app/page.tsx` | Added enrichment state Map, enrichment event handler, passes state to DetailDrawer |
| `frontend/src/components/v4/DetailDrawer.tsx` | Added `EnrichmentState` interface and enrichment section showing status/observation/errors |
| `frontend/src/components/v4/primitives.tsx` | Added `EnrichmentStatusBadge` and `EnrichmentInfoRow` components |

---

## Backend Files Changed

| File | Change |
|---|---|
| `backend/app/services/enrichment_ws_events.py` | **New.** Event builder + error sanitizer |
| `backend/app/services/enrichment_worker.py` | Added `ws_manager` param, `_emit()` helper, event emission at lifecycle points |
| `backend/app/services/enrichment_enqueue.py` | Added `ws_manager` param, emits `pending` event on auto-enqueue |
| `backend/app/services/enrichment_worker_loop.py` | Added `ws_manager` passthrough to `_poll_once` |
| `backend/app/routers/enrichment.py` | Added `request` param to process routes, emits `pending` event on manual trigger |
| `backend/app/routers/edge.py` | Passes `ws_manager` to auto-enqueue |
| `backend/app/main.py` | Passes `ws_manager` to worker loop |

---

## DESIGN.md Usage

Used as local styling reference for enrichment UX components:
- 2px border radius on badges and panels
- Hairline borders (`var(--line)`)
- Dense technical layout, engineering-oriented
- Green accent (`var(--acc)`) only for active/complete EdgeVLM state
- Amber/red for rejected/failed, kept restrained
- No decorative gradients, no soft card shadows
- Monospace font (`var(--font-mono)`) for badges and metadata
- Compatible with existing dark theme variables

**Not applied to:** global navigation, page layout, routing, theme architecture,
unrelated components.

---

## Tests Added

`backend/tests/contract/test_enrichment_ws_events.py` — 34 tests:
- `TestBuildEnrichmentEvent` (7 tests): payload structure for all 5 statuses, ISO-8601 timestamp, JSON serializable
- `TestForbiddenFields` (5 tests): no forbidden keys in event payload, no raw commands/IPs/paths in errors
- `TestSanitizeErrorMessage` (10 tests): None/empty handling, path/IP/token/sshpass/command/stack-trace redaction, truncation
- `TestEnrichmentWsBroadcast` (3 tests): manual trigger emits pending, process emits running+terminal, no mutation fields
- `TestEdgeReportNonBlocking` (1 test): report returns in <2s without calling provider

---

## Not Included (Out of Scope)

- No public deployment
- No public demo snapshot switch
- No live RK3588 → vision.hanlab.app stream
- No cloud VLM provider
- No worker status endpoint
- No retry schema
- No full frontend redesign
- No changes to YOLO/ORT/RKNN/LoRA/segmentation
- No changes to Phase 10 ORT snapshot or Phase 10.1b EdgeVLM snapshot

---

## Next Stage

Phase 10.1b-5: Real RK3588 → vision.hanlab.app live stream soak + public snapshot capture.
