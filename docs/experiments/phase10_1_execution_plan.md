# Phase 10.1 — Execution Plan: VLM Async Enrichment

> Plan only — no implementation code until reviewed.
>
> Baseline: `main` after Phase 10 v1 merge (commit `9dc8afe`)
> Branch: `phase10.1/vlm-async-enrichment`
> Reference: `docs/experiments/phase10_1_vlm_async_enrichment_plan.md`

---

## 1. Branch / Baseline

**Start from `main`** after Phase 10 v1 merge.

```bash
git checkout main && git pull origin main
git checkout -b phase10.1/vlm-async-enrichment
```

The PR #2 merge commit (`9dc8afe`) is the new main baseline. No rebase onto old `phase10/localization-refactor-v1` needed.

---

## 2. Scope

### Goal

Async cloud VLM enrichment of `observation` + `severity_reason` for defects already localized by YOLO/ORT.

### Allowed VLM Outputs

| Field | Description |
|---|---|
| `observation` | Short visual inspection note (zh-CN) |
| `severity_reason` | Justification for the assigned severity |
| `accepted_box_ids` | Which input box IDs the VLM confirmed (optional) |

### Forbidden VLM Outputs (must never be written)

| Field | Owned by |
|---|---|
| `bbox` / `bboxes` | YOLO/ORT localizer |
| `mask` | Not used in Phase 10 |
| `category` | YOLO class head |
| `defect_type` | YOLO class head |
| `confidence` | YOLO detection score |
| `anomaly_score` | EfficientAD |
| geometry correction | N/A |
| training labels | N/A |

---

## 3. Architecture — Async Flow

```
Edge T1/T2/T3/T4 upload
  → POST /api/edge/report
  → Backend writes defects row (200 to edge immediately)
  → If enrichment_enabled AND enrichment_auto_enqueue:
      → Background enqueue: create defect_enrichments row (status=pending)
  → [No VLM call in upload path]

Worker loop (separate asyncio task, started in lifespan):
  → SELECT pending defect_enrichments row (ORDER BY created_at LIMIT 1)
  → UPDATE status=running
  → Load defect row + image from disk
  → Build VLM prompt (full image + crop + metadata)
  → Call cloud VLM provider (HTTP API)
  → Parse strict JSON response
  → Hallucination guard: reject forbidden keys
  → Validate accepted_box_ids
  → If valid:
      → UPDATE enrichment status=complete, store observation/severity_reason
      → UPDATE defects.observation, defects.severity_reason, defects.observation_source
      → Broadcast WebSocket defect_enriched event
  → If invalid:
      → UPDATE enrichment status=failed/rejected, store error_message
      → Broadcast WebSocket defect_enrichment_failed event
```

**Hard rule:** `POST /api/edge/report` never calls VLM and never blocks on enrichment.

### Staging

| Stage | Scope |
|---|---|
| **10.1a** | Manual trigger (`POST /api/defects/{id}/enrich`) + worker + frontend display |
| **10.1b** | Auto-enqueue on new defect insert, behind `enrichment_auto_enqueue` config flag |
| **10.1c** (future) | `edge_vlm` provider adapter, still async, still no YOLO output modification |

---

## 4. Backend Design

### 4.1 New Table: `defect_enrichments`

Separate table to keep enrichment lifecycle isolated from the canonical defect row.

```python
class DefectEnrichment(Base):
    __tablename__ = "defect_enrichments"

    id: int                  # PK, autoincrement
    defect_id: int           # FK → defects.id, indexed
    provider: str            # "cloud_vlm" | "edge_vlm"  (future)
    provider_model: str      # e.g. "qwen-vl-plus" or "qwen3-vl-2b"
    prompt_version: str      # e.g. "phase10_1_obs_v1"
    status: str              # "pending" | "running" | "complete" | "failed" | "rejected" | "skipped"
    observation: str | None  # VLM output
    severity_reason: str | None
    accepted_box_ids: list | None  # JSON list[int]
    input_digest: str | None       # sha256(image_url + bbox + defect_type + prompt_version)
    raw_response: str | None       # raw VLM JSON, internal/debug only
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

Unique constraint: `(defect_id, provider, prompt_version)` to prevent duplicate active jobs.

### 4.2 Denormalized Display Fields on `defects` Table

These already exist from v1.3 — no schema migration needed:

- `defects.observation` (String 1024, nullable)
- `defects.severity_reason` (String 512, nullable)
- `defects.observation_source` (String 64, nullable)

On successful enrichment, the worker updates these three fields on the `defects` row. No new columns needed on `defects`.

### 4.3 API Routes

| Method | Path | Purpose | Response |
|---|---|---|---|
| `POST` | `/api/defects/{id}/enrich` | Manual trigger to enqueue enrichment job | `202 Accepted` + enrichment ID |
| `GET` | `/api/defects/{id}/enrichment` | Get latest enrichment status for a defect | `200` with enrichment record or `404` |
| `POST` | `/api/enrich/retry-failed` | Re-enqueue all failed enrichments (admin/dev) | `200` with count re-enqueued |

#### POST /api/defects/{id}/enrich

```python
# Preconditions:
# - defect exists (404 if not)
# - defect.bboxes is non-empty (400 if empty)
# - defect.confidence > 0 (400 if zero — fallback placeholder)
# - no existing pending/running enrichment for same defect_id + provider + prompt_version (409 if duplicate)

# Returns 202:
{
    "enrichment_id": 42,
    "defect_id": 123,
    "status": "pending"
}
```

#### GET /api/defects/{id}/enrichment

```python
# Returns the latest enrichment record for this defect, or 404
{
    "id": 42,
    "defect_id": 123,
    "provider": "cloud_vlm",
    "provider_model": "qwen-vl-plus",
    "prompt_version": "phase10_1_obs_v1",
    "status": "complete",
    "observation": "线缆外层绝缘区域可见局部切伤...",
    "severity_reason": "缺陷位于绝缘层表面...",
    "accepted_box_ids": [0],
    "created_at": "...",
    "completed_at": "..."
}
```

### 4.4 Worker Behavior

| Transition | Trigger |
|---|---|
| `pending` → `running` | Worker picks up job |
| `running` → `complete` | VLM response valid, display fields updated |
| `running` → `failed` | Provider error / timeout / JSON parse failure |
| `running` → `rejected` | Hallucination guard rejected output |
| `failed` → `pending` | Retry via `/api/enrich/retry-failed` |

**Worker config (edge/config.yaml equivalent for backend):**

```yaml
enrichment_enabled: false          # master switch
enrichment_auto_enqueue: false     # auto-enqueue on new defect
enrichment_provider: cloud_vlm     # "cloud_vlm" | "edge_vlm" (future)
enrichment_max_per_minute: 10      # rate limit
enrichment_timeout_s: 30           # per-call timeout
enrichment_max_retries: 2          # retry count
enrichment_prompt_version: phase10_1_obs_v1
```

**Implementation:** Environment variables in `backend/.env`, read at startup:

```
ENRICHMENT_ENABLED=false
ENRICHMENT_AUTO_ENQUEUE=false
ENRICHMENT_PROVIDER=cloud_vlm
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_TIMEOUT_S=30
ENRICHMENT_MAX_RETRIES=2
ENRICHMENT_PROMPT_VERSION=phase10_1_obs_v1
CLOUD_VLM_API_KEY=           # required when provider=cloud_vlm
CLOUD_VLM_MODEL=             # e.g. qwen-vl-plus
CLOUD_VLM_BASE_URL=          # API endpoint
```

**Duplicate prevention:** Unique constraint `(defect_id, provider, prompt_version)` + check before insert.

**Timeout:** `asyncio.wait_for(provider_call, timeout=enrichment_timeout_s)`.

**Worker startup:** New asyncio task created in `lifespan()` in `main.py`, cancelled on shutdown. Worker polls every 2 seconds when there are pending jobs, sleeps 5 seconds when idle.

---

## 5. Provider Design

### 5.1 Provider Interface

```python
# backend/app/services/vlm_provider.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class VlmEnrichmentInput:
    image_path: str           # absolute path to saved JPEG
    category: str
    defect_type: str
    confidence: float
    bboxes: list[dict]        # [{box_id, x, y, w, h}, ...]
    box_crops: list[bytes]    # JPEG crops per box (with 15% padding)

@dataclass
class VlmEnrichmentOutput:
    observation: str
    severity_reason: str
    accepted_box_ids: list[int]
    raw_response: str

class VlmProvider(ABC):
    @abstractmethod
    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        """Call VLM and return parsed, validated output. Raises on error."""
        ...
```

### 5.2 Cloud VLM Provider (first implementation)

Uses DashScope / Alibaba Cloud VLM API (compatible with Qwen-VL models). The exact API endpoint and model are configured via environment variables.

**Required credentials (from user, not guessed):**

- `CLOUD_VLM_API_KEY` — DashScope API key
- `CLOUD_VLM_MODEL` — model identifier (e.g. `qwen-vl-plus`, `qwen2.5-vl-7b-instruct`)
- `CLOUD_VLM_BASE_URL` — API base URL

**Important:** If these credentials are not configured, the provider raises at startup and enrichment is effectively disabled (even if `enrichment_enabled=true`). No fallback to guessing endpoints.

**Request format:** The provider sends the full image as base64 (API-side only, not edge transmission) plus the structured prompt from Section 6.

**Do NOT commit credentials.** Use `.env` / environment variables only. Add `backend/.env` to `.gitignore` if not already present.

### 5.3 Edge VLM Provider (future, not implemented now)

Stub only. Same `VlmProvider` interface, but would read from RK3588 VLM subprocess or HTTP endpoint. Deferred to Phase 10.1c.

---

## 6. Prompt Design

### Prompt Version: `phase10_1_obs_v1`

**System prompt:**

```
You are an industrial inspection note generator.
The detector has already produced the canonical category, defect_type, confidence, and bbox.
You must not change, infer, correct, or output any bbox, category, defect_type, confidence, or mask.
Your job is only to write a short visual observation and a severity_reason.
Return JSON only. No markdown, no prose prefix, no extra keys.
```

**User payload (JSON):**

```json
{
  "task": "phase10.1_vlm_enrichment",
  "category": "cable",
  "defect_type": "cut_outer_insulation",
  "label_source": "yolo_class_head",
  "localization_source": "ort_yolov8n_cpu",
  "confidence": 0.9028,
  "bbox_format": "normalized_top_left_xywh",
  "boxes": [
    {
      "box_id": 0,
      "x": 0.4688,
      "y": 0.7106,
      "w": 0.0755,
      "h": 0.2303
    }
  ],
  "allowed_output_fields": ["observation", "severity_reason", "accepted_box_ids"],
  "forbidden_output_fields": ["bbox", "bboxes", "mask", "category", "defect_type", "confidence", "anomaly_score"],
  "language": "zh-CN",
  "style": "concise inspector note, no speculation"
}
```

**Expected output:**

```json
{
  "observation": "线缆外层绝缘区域可见局部切伤，缺陷集中在检测框标出的下侧区域。",
  "severity_reason": "缺陷位于绝缘层表面，可能影响防护完整性；当前检测范围较集中，建议复检确认。",
  "accepted_box_ids": [0]
}
```

**Prompt file location:** `backend/prompts/phase10_1_obs_v1.txt` (system prompt) and `backend/prompts/phase10_1_obs_v1_user.json` (user payload template with `{category}`, `{defect_type}`, etc. placeholders).

---

## 7. Validation / Hallucination Guard

### 7.1 Output Schema Validation

```python
FORBIDDEN_KEYS = {
    "bbox", "bboxes", "mask", "category", "defect_type",
    "confidence", "anomaly_score", "geometry_correction",
}

ALLOWED_KEYS = {"observation", "severity_reason", "accepted_box_ids"}
```

**Validation rules:**

1. Response must be valid JSON (no markdown fences, no prose wrapper).
2. Reject if any key in `FORBIDDEN_KEYS` is present at top level.
3. Reject if `observation` is empty or > 1024 chars.
4. Reject if `severity_reason` is empty or > 512 chars.
5. Reject if `accepted_box_ids` contains IDs not in the input `boxes` list.
6. Reject if extra keys not in `ALLOWED_KEYS` are present (strict mode).

**On rejection:** Set enrichment status to `"rejected"`, store raw response in `raw_response` field (debug only), set `error_message` to the rejection reason.

### 7.2 Immutable Field Protection

The worker **never** writes to these `defects` columns from VLM output:

- `bboxes`
- `defect_type`
- `category`
- `confidence`
- `anomaly_score`
- `localization_source`
- `label_source`

Only these are updated on success:

- `defects.observation`
- `defects.severity_reason`
- `defects.observation_source` (set to `"cloud_vlm"` or `"edge_vlm"`)

---

## 8. Frontend Design

### 8.1 Rename Misleading "VLM 输出" Label

Current `FrameInspector.tsx:146` shows `"VLM 输出"` as the right pane header. For ORT/template records where no VLM was called, this is misleading.

**Change:**

| `observation_source` | Right pane header |
|---|---|
| `"template"` | `"检测输出 · Template"` |
| `"cloud_vlm"` | `"云端 VLM 增强 · Cloud VLM"` |
| `"edge_vlm"` | `"边缘 VLM 增强 · Edge VLM"` |
| `null` / undefined | `"检测输出 · Detector"` (fallback) |

The tab labels "JSON", "指标", "溯源" remain unchanged.

### 8.2 Show Enrichment Status

In `DetailDrawer.tsx` and `ProvenanceTab`, add enrichment status display:

```
Observation source: template / cloud_vlm / edge_vlm
Enrichment status: none / pending / running / complete / failed
```

### 8.3 Display Logic

```tsx
// In observation display area:
if (enrichment_status === "pending" || enrichment_status === "running") {
  show template observation + small badge "VLM 增强处理中..."
}
if (observation_source === "cloud_vlm" && enrichment_status === "complete") {
  show enriched observation + badge "云端 VLM"
}
if (enrichment_status === "failed") {
  show template observation + warning "VLM 增强失败，使用模板描述"
}
```

### 8.4 WebSocket Update

When `defect_enriched` event arrives, update the matching defect in the defects list:

```typescript
interface DefectEnrichedEvent {
  type: "defect_enriched";
  defect_id: number;
  observation: string;
  severity_reason: string;
  observation_source: string;
  enrichment_status: "complete";
}
```

The frontend `useDefectWebSocket` hook (in `lib/ws.ts`) needs a handler for this new event type to update the in-memory defects array.

### 8.5 Type Updates

Add to `frontend/src/types/defect.ts`:

```typescript
export type EnrichmentStatus = "none" | "pending" | "running" | "complete" | "failed" | "rejected";
export type EnrichmentProvider = "template" | "cloud_vlm" | "edge_vlm";
```

Add optional fields to `DefectRead`:

```typescript
enrichment_status?: EnrichmentStatus;
enrichment_provider?: EnrichmentProvider;
enriched_at?: string;
```

### 8.6 VlmDefectTooltip Update

`DataSourceBadge.tsx:104-113`: The `VlmDefectTooltip` says "VLM 生成的结构化描述". For ORT records, this should be conditional:

- If `label_source === "yolo_class_head"`: "YOLO 分类头输出 / YOLO class head output"
- If `observation_source === "cloud_vlm"`: "云端 VLM 生成的检查描述 / Cloud VLM inspection note"
- Fallback: current text

---

## 9. Tests

### 9.1 Contract Tests (new file)

`backend/tests/contract/test_enrichment_contract.py`:

| Test | What it verifies |
|---|---|
| `test_enrich_creates_pending_job` | POST /api/defects/{id}/enrich → 202 + pending status |
| `test_enrich_nonexistent_defect_404` | POST /api/defects/99999/enrich → 404 |
| `test_enrich_empty_bboxes_400` | Defect with empty bboxes → 400 |
| `test_enrich_zero_confidence_400` | Fallback placeholder defect → 400 |
| `test_enrich_duplicate_active_409` | Enrichment already pending/running → 409 |
| `test_get_enrichment_status` | GET /api/defects/{id}/enrichment → 200 with status |
| `test_get_enrichment_not_found_404` | GET /api/defects/99999/enrichment → 404 |
| `test_retry_failed_enrichments` | POST /api/enrich/retry-failed → 200 with count |

### 9.2 Hallucination Guard Tests (new file)

`backend/tests/unit/test_enrichment_parser.py`:

| Test | What it verifies |
|---|---|
| `test_valid_output_accepted` | Valid {observation, severity_reason, accepted_box_ids} → accepted |
| `test_forbidden_bbox_key_rejected` | Output contains "bbox" → rejected |
| `test_forbidden_defect_type_key_rejected` | Output contains "defect_type" → rejected |
| `test_forbidden_confidence_key_rejected` | Output contains "confidence" → rejected |
| `test_forbidden_mask_key_rejected` | Output contains "mask" → rejected |
| `test_invalid_accepted_box_ids_rejected` | accepted_box_ids not in input → rejected |
| `test_empty_observation_rejected` | Empty observation string → rejected |
| `test_oversized_observation_rejected` | observation > 1024 chars → rejected |
| `test_markdown_wrapper_rejected` | ```json ... ``` wrapper → rejected or stripped |
| `test_extra_keys_rejected` | Extra unknown keys → rejected |

### 9.3 Worker Tests (new file)

`backend/tests/unit/test_enrichment_worker.py`:

| Test | What it verifies |
|---|---|
| `test_pending_to_running_to_complete` | Happy path lifecycle |
| `test_pending_to_failed_on_provider_error` | Provider raises → status=failed |
| `test_pending_to_rejected_on_hallucination` | Forbidden keys → status=rejected |
| `test_retry_failed_job` | failed → pending on retry |
| `test_duplicate_job_prevented` | Same defect_id + provider + prompt_version → 409 |
| `test_provider_timeout` | Provider hangs → timeout → failed |
| `test_display_fields_updated_on_complete` | defects.observation etc. updated |

### 9.4 Non-blocking Upload Tests

Modify existing `test_post_report_happy_path.py` or add to `test_enrichment_contract.py`:

| Test | What it verifies |
|---|---|
| `test_upload_returns_before_enrichment` | POST /api/edge/report returns 200 without calling VLM |
| `test_enrichment_failure_does_not_affect_upload` | Provider down + auto_enqueue=true → upload still 200 |

### 9.5 Existing Regression Tests

All existing contract tests must continue to pass:

- 83/83 existing tests (v1.3 contract)
- `schema_version` remains `"v1"`
- Phase 10 v1 fields unchanged

### 9.6 Frontend State Tests (manual)

| Check | Expected |
|---|---|
| Template record renders | Right pane says "检测输出 · Template" |
| Pending enrichment record | "VLM 增强处理中..." badge visible |
| Enriched record | Enriched observation shown, "云端 VLM" badge |
| Failed enrichment | Template observation + warning |
| YOLO bbox labels unchanged | BBox overlay still shows "Model bbox from YOLOv8n localizer" |
| Phase 10 ORT snapshot still loads | `phase10_ort_latest` snapshot renders correctly |

---

## 10. File-Level Plan

### 10.1 New Files

| File | Purpose |
|---|---|
| `backend/app/models/enrichment.py` | SQLAlchemy `DefectEnrichment` model |
| `backend/app/schemas/enrichment.py` | Pydantic schemas: `EnrichmentCreate`, `EnrichmentRead`, `EnrichmentTriggerResponse` |
| `backend/app/routers/enrichment.py` | FastAPI router: `POST /api/defects/{id}/enrich`, `GET /api/defects/{id}/enrichment`, `POST /api/enrich/retry-failed` |
| `backend/app/services/__init__.py` | Package init |
| `backend/app/services/enrichment_worker.py` | Async worker loop: poll pending → call provider → validate → update |
| `backend/app/services/vlm_provider.py` | `VlmProvider` ABC + `CloudVlmProvider` implementation |
| `backend/app/services/enrichment_guard.py` | Hallucination guard: `validate_vlm_output()` with forbidden key check |
| `backend/prompts/phase10_1_obs_v1_system.txt` | System prompt text |
| `backend/prompts/phase10_1_obs_v1_user.json` | User payload template with placeholders |
| `backend/tests/contract/test_enrichment_contract.py` | Contract tests for enrichment API routes |
| `backend/tests/unit/test_enrichment_parser.py` | Hallucination guard unit tests |
| `backend/tests/unit/test_enrichment_worker.py` | Worker lifecycle unit tests |
| `docs/experiments/phase10_1_execution_plan.md` | This document |

### 10.2 Modified Files

| File | Change | Reason |
|---|---|---|
| `backend/app/main.py` | Import enrichment router; start enrichment worker task in lifespan; register router | Wire up enrichment endpoints and worker |
| `backend/app/models/__init__.py` | Import `DefectEnrichment` model | Ensure model is registered with `Base.metadata` for `create_all` |
| `backend/app/routers/edge.py` | After defect flush, if `enrichment_enabled AND enrichment_auto_enqueue`: enqueue enrichment job (non-blocking, in background task) | Auto-enqueue on upload (10.1b stage, behind flag) |
| `backend/app/ws/manager.py` | No code change needed — existing `broadcast()` method is sufficient for new event types | Already supports arbitrary dict messages |
| `backend/app/schemas/defect.py` | Add optional `enrichment_status`, `enrichment_provider` to `DefectRead` | Surface enrichment state in defect list |
| `docs/API_CONTRACT.md` | Document new routes, new `defect_enrichments` table, enrichment WebSocket event, new `DefectRead` fields | Contract authority |
| `frontend/src/types/defect.ts` | Add `EnrichmentStatus`, `EnrichmentProvider` types; add optional fields to `DefectRead` | Type safety for enrichment fields |
| `frontend/src/components/v4/FrameInspector.tsx` | Rename "VLM 输出" to context-aware header based on `observation_source`; add enrichment status display in ProvenanceTab | Fix misleading label for ORT/template records |
| `frontend/src/components/v4/DetailDrawer.tsx` | Add enrichment status in JSON/溯源 sections; update "VLM 指标" heading | Consistent enrichment display |
| `frontend/src/components/v4/DataSourceBadge.tsx` | Update `VlmDefectTooltip` to be source-aware (YOLO vs VLM vs template) | Accurate provenance labeling |
| `frontend/src/lib/ws.ts` | Add handler for `defect_enriched` WS event type to update in-memory defects | Real-time enrichment status update |

### 10.3 Unchanged Files (explicit)

| File | Why unchanged |
|---|---|
| `frontend/public/demo-data/phase10_ort_latest/` | Phase 10 v1 snapshot must not be overwritten |
| `edge/config.yaml` | Edge config unchanged — enrichment is backend-only in 10.1a |
| `edge/src/pipeline/localizer_worker.cpp` | Edge code unchanged |
| `scripts/phase10/ort_localizer.py` | ORT localizer unchanged |
| `backend/app/models/defect.py` | No new columns needed — v1.3 fields sufficient |
| `backend/app/routers/defects.py` | Existing list/detail routes pass through enrichment fields via `DefectRead` automatically |
| `backend/app/routers/stats.py` | No enrichment stats in v1 (future: enrichment success rate) |
| `backend/app/db.py` | No change — `create_all` picks up new model automatically |

---

## 11. Acceptance Criteria

### Must-Pass Gates Before PR Merge

| Gate | Criterion |
|---|---|
| **G1: Existing tests** | All 83/83 existing contract tests pass unchanged |
| **G2: New contract tests** | 8/8 new enrichment contract tests pass |
| **G3: Hallucination guard** | 10/10 guard tests pass (all forbidden keys rejected) |
| **G4: Worker tests** | 7/7 worker lifecycle tests pass |
| **G5: Non-blocking upload** | POST /api/edge/report returns 200 in same time regardless of enrichment config |
| **G6: Manual trigger** | POST /api/defects/{id}/enrich returns 202, worker processes to complete |
| **G7: Display field update** | After enrichment complete, GET /api/defects/{id} returns updated observation/severity_reason/observation_source |
| **G8: Frontend renders** | `npm run build` succeeds, `tsc` 0 errors |
| **G9: Frontend state** | Template/pending/enriched/failed states render correctly in FrameInspector |
| **G10: Snapshot intact** | Phase 10 ORT snapshot at `frontend/public/demo-data/phase10_ort_latest/` unchanged and loads correctly |
| **G11: schema_version** | Payload `schema_version` remains `"v1"` — no bump to v2 |
| **G12: No secrets** | `git diff` contains no API keys, passwords, raw IPs, sshpass commands, tokens, or private keys |
| **G13: Rollback config** | With `ENRICHMENT_ENABLED=false`, all existing behavior is identical to Phase 10 v1 |

### CI Expectations

```bash
# Backend
pytest backend/tests/contract/ -v          # all contract tests
pytest backend/tests/unit/test_enrichment* -v  # enrichment unit tests

# Frontend
cd frontend && npm run build               # static export succeeds
cd frontend && npx tsc --noEmit            # type check

# Secret scan
git diff main...HEAD | grep -iE '(api.key|password|sshpass|token=|secret)'  # should return nothing
```

---

## 12. Out of Scope

Explicitly **NOT** in Phase 10.1:

| Item | Status |
|---|---|
| RKNN integration restart | BLOCKED — not restarted |
| RKNN threshold tuning | Not touched |
| INT8 main path | Not touched |
| YOLOv8s retraining | Not touched |
| `capsule` expansion | Not touched |
| Additional categories beyond metal_nut + cable | Not touched |
| Segmentation / mask output | Not implemented |
| VLM bbox output | Forbidden |
| VLM defect_type output | Forbidden |
| VLM category output | Forbidden |
| VLM confidence output | Forbidden |
| VLM anomaly_score output | Forbidden |
| VLM geometry correction | Forbidden |
| Phase 10 v1 snapshot overwrite | `phase10_ort_latest/` untouched |
| Credential commits | All credentials via env vars only |
| Edge VLM provider | Stub only, not implemented |
| `schema_version` bump to v2 | Stays `"v1"` |
| New edge-side code changes | Enrichment is backend-only |
| Frontend unit test framework setup | Manual frontend checks only (no Jest/Vitest setup in this phase) |

---

## 13. Rollback Plan

If enrichment causes problems after merge:

1. Set `ENRICHMENT_ENABLED=false` in backend `.env`.
2. Restart backend — worker task not started, no enrichment polling.
3. All existing behavior identical to Phase 10 v1.
4. `defect_enrichments` table rows preserved for debugging.
5. Frontend gracefully hides enrichment panels when fields are absent (null-safe).
6. Phase 10 v1 snapshot untouched.

---

## 14. Open Questions for Review

1. **Cloud VLM provider choice:** DashScope Qwen-VL API? OpenAI-compatible endpoint? Other? Need API key + endpoint from user before implementation.

2. **Crop strategy:** Send full image + per-box crop (with 15% padding) as separate images? Or send full image + overlay with numbered boxes? The plan text suggests both; recommend **full image + per-box crops** for simplicity.

3. **Rate limiting:** `enrichment_max_per_minute: 10` — is this sufficient? Or should we use token-budget-based limiting?

4. **Auto-enqueue default:** Should `enrichment_auto_enqueue` be enabled by default in 10.1b, or require explicit opt-in? Recommend opt-in (default false).

5. **Enrichment for historical records:** Should `POST /api/enrich/retry-failed` also support enriching pre-Phase 10.1 records (those with `observation_source="template"`)? Recommend yes, with batch limit.

6. **Frontend test framework:** Currently no Jest/Vitest setup. Should we add one in this phase, or rely on manual checks + contract tests? Recommend manual checks for now, test framework in a separate cleanup phase.

7. **Prompt language:** Current prompt defaults to `zh-CN` for observation output. Should we support English as well, or is Chinese-only acceptable for the portfolio?
