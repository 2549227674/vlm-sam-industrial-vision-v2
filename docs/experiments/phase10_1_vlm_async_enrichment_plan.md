# Phase 10.1 — VLM Async Enrichment Implementation / Research Plan

> Repository: `2549227674/vlm-sam-industrial-vision-v2`  
> Baseline: `main` after Phase 10 v1 merge  
> Recommended branch: `phase10.1/vlm-async-enrichment`  
> Document purpose: planning / control document for Claude Code and reviewer workflow  
> Status: plan only — do not write implementation code until reviewed
>
> **Primary route:** edge_vlm async observation on RK3588.  
> **Fallback:** template observation.  
> **Optional:** cloud_vlm comparison / fallback only (provider-neutral, not default).

---

## 0. Remote Baseline and Current State

Phase 10 v1 has already been merged into `main`. Phase 10.1 should therefore start from `main`, not from the old `phase10/localization-refactor-v1` branch.

Current Phase 10 v1 baseline:

- Scope: `metal_nut + cable`, 2 categories, 12 defect types.
- Localizer: YOLOv8n-detect.
- Runtime: ONNX Runtime CPUExecutionProvider on RK3588.
- This is ORT CPU fallback, not RKNN/NPU deployment.
- RKNN numeric consistency remains BLOCKED.
- VLM is not called in Phase 10 v1.
- `observation_source="template"`.
- Severity is fixed/template default.
- API contract v1.3 optional source fields exist, while payload `schema_version` remains `"v1"`.
- `bboxes`, `defect_type`, and `confidence` come from YOLO/ORT localizer:
  - `localization_source="ort_yolov8n_cpu"`
  - `label_source="yolo_class_head"`
  - `observation_source="template"`
- API/frontend bbox format is normalized top-left `xywh`.
- Phase 10 v1 snapshot must not be overwritten.

Phase 10.1 goal:

```text
YOLO/ORT already produces stable bbox + defect_type + confidence
        ↓
Async VLM enrichment generates observation / severity_reason only
        ↓
VLM must not modify bbox, defect_type, category, confidence, or geometry
```

---

## 1. Recommended Workflow for Claude Code

This document should **not** be treated as a direct instruction to immediately implement code.

Recommended workflow:

1. Claude Code reads this document and the current remote `main` branch.
2. Claude Code produces a **Phase 10.1 Execution Plan** before making code changes.
3. The execution plan must include:
   - files to create
   - files to modify
   - DB/schema strategy
   - exact API routes
   - worker design
   - frontend UI changes
   - tests to add or update
   - out-of-scope checklist
   - rollback plan
4. Reviewer checks that the execution plan does not violate hard constraints.
5. Only after approval should Claude Code implement code.
6. After implementation, reviewer verifies remote branch, PR, commits, tests, and changed files using GitHub connector.

Recommended prompt to Claude Code:

```text
Read docs/experiments/phase10_1_vlm_async_enrichment_plan.md.
Do not write code yet.
First produce docs/experiments/phase10_1_execution_plan.md with a file-by-file implementation plan, test plan, DB migration strategy, API contract impact, frontend impact, rollback plan, and explicit out-of-scope checklist.
Do not modify RKNN, localizer, YOLO training, segmentation, or Phase 10 v1 snapshot files.
Wait for review before implementation.
```

---

## 2. Hard Constraints

Phase 10.1 must not do the following:

- Do not restart RKNN integration.
- Do not tune RKNN thresholds.
- Do not make INT8 the main path.
- Do not retrain YOLOv8s.
- Do not expand to `capsule` or additional categories.
- Do not implement segmentation or masks.
- Do not let VLM output bbox, mask, canonical `defect_type`, `category`, `confidence`, or geometry correction.
- Do not let VLM replace YOLO class head.
- Do not remove Phase 10 v1 ORT fallback path.
- Do not overwrite `frontend/public/demo-data/phase10_ort_latest/`.
- Do not commit credentials, raw IPs, passwords, `sshpass` commands, tokens, or private keys.

---

## 3. Edge-side, Backend-side Cloud, or Both?

Recommendation: **edge_vlm async enrichment as primary path, with template as fallback.**

Reasoning:

- Edge VLM runs on RK3588 alongside the existing pipeline — no external API dependency.
- The same hardware already runs Qwen3-VL-2B base (W8A8) for Phase 7/8/9 experiments.
- Edge VLM processes observation/severity_reason only — a much simpler task than full defect JSON.
- No cloud API latency, no credential management, no vendor lock-in.
- Template fallback is always available when edge VLM is disabled or fails.
- Cloud VLM can be added later as an optional comparison/fallback provider without changing the schema.

Recommended staging:

```text
10.1a: edge_vlm async provider + manual trigger + template fallback + frontend display
10.1b: auto-enqueue / auto-run edge_vlm enrichment after defect insert, behind config flags and rate limit
10.1c: optional cloud_vlm comparison/fallback provider, provider-neutral and not enabled by default
```

Cloud VLM is provider-neutral: no specific vendor (DashScope, OpenAI, Claude, Gemini, etc.) is assumed or hardcoded. If cloud VLM implementation is requested, the developer must ask the user for provider choice and credentials before proceeding.

---

## 4. Minimal v1.3-compatible Schema Addition

Current v1.3 already has these fields:

```text
localization_source
label_source
observation_source
defect_family
observation
severity_reason
```

These are sufficient for the final display value.

Recommended minimal addition for Phase 10.1:

```text
enrichment_status: "none" | "pending" | "running" | "complete" | "failed" | "skipped"
enrichment_provider: "template" | "edge_vlm" | "cloud_vlm"
enrichment_error: optional short string
enriched_at: datetime | null
```

If the team wants to avoid touching the existing `defects` table too much, these fields can live in a separate enrichment table and only denormalize the accepted result back into:

```text
defects.observation
defects.severity_reason
defects.observation_source
```

Do not bump payload `schema_version` to `v2`. Keep `schema_version="v1"` and treat Phase 10.1 as v1.3-compatible optional enrichment.

---

## 5. Storage Design: New DB Columns or Separate Table?

Recommendation: **use a separate `defect_enrichments` table** and keep the current `defects` row as the display state.

Why a separate table is better:

- Enrichment is asynchronous and may fail or be retried.
- Multiple providers may exist later: `cloud_vlm`, `edge_vlm`, maybe human-reviewed.
- Prompt versions must be auditable.
- Raw model responses should not overwrite the canonical defect row.
- It allows comparing prompt/provider versions without corrupting Phase 10 v1 data.

Recommended table:

```text
defect_enrichments
- id
- defect_id
- provider                 # edge_vlm (primary) | template (fallback) | cloud_vlm (optional future)
- provider_model           # e.g. "qwen3-vl-2b" for edge, "template" for template
- prompt_version           # e.g. phase10_1_obs_v1
- status                   # pending | running | complete | failed | rejected | skipped
- observation
- severity_reason
- accepted_box_ids         # JSON list[int], optional
- input_digest             # hash of image_url + bbox + defect_type + prompt_version
- raw_response_json        # optional, internal/debug only
- error_message
- created_at
- updated_at
- completed_at
```

On successful validation, update the current display fields on `defects`:

```text
defects.observation = enrichment.observation
defects.severity_reason = enrichment.severity_reason
defects.observation_source = enrichment.provider
```

---

## 6. Non-blocking Upload / Localizer Path

Hard rule:

```text
POST /api/edge/report must never call VLM directly.
```

Recommended flow:

```text
Edge T1/T2/T3/T4 upload
  ↓
Backend writes defect row immediately
  ↓
Backend returns 200 to edge
  ↓
Optional enqueue enrichment job
  ↓
Worker reads defect + image + bbox
  ↓
VLM returns observation / severity_reason only
  ↓
Backend validates and stores enrichment
  ↓
WebSocket event updates frontend
```

Implementation options:

- Minimal demo: FastAPI `BackgroundTasks` or in-process queue.
- Better for this repo: SQLite-backed job table plus worker loop.
- Production-like: Celery/RQ/Arq + Redis.

Recommended first implementation: **SQLite-backed job table + backend worker loop**. This avoids adding Redis and is more robust than ephemeral background tasks.

Suggested config:

```yaml
enrichment_enabled: false
enrichment_provider: edge_vlm
enrichment_auto_enqueue: false
enrichment_max_per_minute: 10
```

Start with manual trigger; enable auto-enqueue only after tests pass.

---

## 7. Preventing VLM Hallucination or Label Mutation

Use a schema firewall.

The VLM input may contain immutable YOLO facts:

- `category`
- `defect_type`
- `confidence`
- `bbox_id`
- bbox coordinates
- full image / crop / overlay image

The VLM output must only contain:

```text
observation
severity_reason
accepted_box_ids
```

Reject output if it contains any forbidden field:

```text
bbox
bboxes
mask
category
defect_type
confidence
anomaly_score
geometry_correction
```

Additional validation rules:

- Reject if `accepted_box_ids` contains IDs not present in input.
- Reject or flag if the text names a different category than the YOLO category.
- Reject or flag if the text names a different canonical defect type than YOLO `defect_type`.
- Never update `category`, `defect_type`, `confidence`, `anomaly_score`, or `bboxes` from VLM output.
- Store rejected raw response only in internal debug fields, not in public frontend fields.

---

## 8. Prompt Format

Use strict JSON-only prompting.

System prompt:

```text
You are an industrial inspection note generator.
The detector has already produced the canonical category, defect_type, confidence, and bbox.
You must not change, infer, correct, or output any bbox, category, defect_type, confidence, or mask.
Your job is only to write a short visual observation and a severity_reason.
Return JSON only.
```

User payload example:

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
  "allowed_output_fields": [
    "observation",
    "severity_reason",
    "accepted_box_ids"
  ],
  "forbidden_output_fields": [
    "bbox",
    "bboxes",
    "mask",
    "category",
    "defect_type",
    "confidence",
    "anomaly_score"
  ],
  "language": "zh-CN",
  "style": "concise inspector note, no speculation"
}
```

Expected output:

```json
{
  "observation": "线缆外层绝缘区域可见局部切伤，缺陷集中在检测框标出的下侧区域。",
  "severity_reason": "缺陷位于绝缘层表面，可能影响防护完整性；当前检测范围较集中，建议复检确认。",
  "accepted_box_ids": [0]
}
```

Do not allow markdown, prose prefix, or extra keys.

---

## 9. VLM Input Design

Recommended inputs:

| Input | Use? | Reason |
|---|---:|---|
| Full image | Yes | Provides object and scene context. |
| Crop around YOLO bbox | Yes | Focuses the VLM on the defect area. |
| Overlay image with numbered boxes | Optional but recommended | Helps map `accepted_box_ids` without asking for new boxes. |
| YOLO class string | Yes | Immutable canonical label. |
| Bbox coordinates | Yes, read-only | Used for reference and accepted_box_ids, not correction. |

Crop rule:

- Crop each YOLO bbox with 10–20% padding.
- Clamp crop to image boundaries.
- Preserve `box_id` mapping.
- For multiple boxes, either send a composite overlay or send per-box crops with IDs.

Do not ask the VLM to locate the defect. The prompt should say the detector already located it.

---

## 10. API Route and Background Worker Design

Recommended routes:

```text
POST /api/defects/{id}/enrich
GET  /api/defects/{id}/enrichment
POST /api/enrich/retry-failed        # optional admin/dev route
```

Recommended WebSocket event:

```json
{
  "type": "defect_enriched",
  "defect_id": 123,
  "observation_source": "edge_vlm",
  "enrichment_status": "complete"
}
```

Manual trigger flow:

```text
POST /api/defects/{id}/enrich
  - check defect exists
  - check bboxes non-empty
  - check confidence > 0
  - create defect_enrichment row with status=pending
  - return 202 Accepted
```

Worker loop:

```text
- SELECT pending job
- mark running
- load defect row
- load image from image_url
- build full image + crop / overlay
- call configured provider
- parse strict JSON
- reject forbidden fields
- validate accepted_box_ids
- mark complete or failed
- update defects display fields if complete
- broadcast WebSocket event
```

---

## 11. Frontend Display Requirements

The frontend should show four states clearly:

1. Template observation
2. Pending enrichment
3. Edge/cloud VLM enriched observation
4. Failed enrichment with template fallback

Recommended UI copy:

```text
BBox source: YOLO/ORT localizer
Label source: YOLO class head
Observation source: template | edge VLM | cloud VLM
VLM does not modify geometry or canonical label
```

Recommended display logic:

```text
if observation_source == "template":
    show template note and badge "template"

if enrichment_status == "pending" or "running":
    show "VLM enrichment pending..." but keep template observation visible

if observation_source == "edge_vlm" and enrichment_status == "complete":
    show enriched note and badge "edge VLM"

if observation_source == "cloud_vlm" and enrichment_status == "complete":
    show enriched note and badge "cloud VLM"  (optional cloud comparison)

if enrichment_status == "failed" or "rejected":
    show template note plus small warning "enrichment failed, using template"

Source labels always visible:
  BBox source: YOLO/ORT localizer
  Label source: YOLO class head
  Observation source: template / edge_vlm / cloud_vlm
  VLM does not modify geometry or canonical label
```

Important frontend cleanup:

- Avoid labeling Phase 10/10.1 ORT/template records as “VLM output” if no VLM was called.
- Rename the right pane from “VLM 输出” to a more general term such as:
  - `Inspection JSON`
  - `Enrichment`
  - `Provenance`

---

## 12. Acceptance Tests

### 12.1 Schema and Parser Tests

Must pass:

- Valid output with `observation`, `severity_reason`, `accepted_box_ids` is accepted.
- Output containing `bbox` or `bboxes` is rejected.
- Output containing `defect_type`, `category`, or `confidence` is rejected.
- Invalid `accepted_box_ids` is rejected.
- Markdown or extra prose around JSON is rejected or sanitized only if deterministic.

### 12.2 API Tests

Must pass:

- `POST /api/defects/{id}/enrich` returns 202 and creates pending job.
- Nonexistent defect returns 404.
- Defect with empty bbox or confidence 0 is skipped or returns a clear error.
- Existing Phase 10 v1 records still pass contract.
- `/api/defects/{id}` returns enrichment fields without breaking old records.

### 12.3 Worker Tests

Must pass:

- pending → running → complete.
- pending → failed on provider error.
- failed job can be retried.
- Duplicate active jobs are prevented for same `defect_id + provider + prompt_version`.
- VLM provider failure does not affect defect upload path.

### 12.4 Non-blocking Tests

Must pass:

- `POST /api/edge/report` never calls provider directly.
- Upload latency is unchanged when enrichment is enabled.
- Enrichment failure does not break defect creation.

### 12.5 Hallucination Guard Tests

Must pass:

- Provider returns bbox correction → reject.
- Provider returns changed `defect_type` → reject.
- Provider returns changed `category` → reject.
- Provider returns changed `confidence` → reject.
- Provider mentions an unsupported category → flag/reject or keep template.

### 12.6 Frontend Tests

Must pass:

- Template state renders.
- Pending state renders.
- Enriched state renders with correct source badge.
- Failed state falls back to template.
- YOLO bbox/source labels remain unchanged.
- Phase 10 ORT snapshot still loads.
- `phase10_ort_latest` snapshot is not overwritten.

---

## 13. Files Claude Code Should Propose Before Implementation

Claude Code should first generate an execution plan that explicitly names files.

Likely new files:

```text
docs/experiments/phase10_1_execution_plan.md
prompts/phase10_1_observation_v1.md
backend/app/models/enrichment.py
backend/app/schemas/enrichment.py
backend/app/routers/enrichment.py
backend/app/services/enrichment_worker.py
backend/app/services/vlm_provider.py        # VlmProvider ABC + EdgeVlmProvider (primary) + TemplateProvider (fallback)
backend/tests/contract/test_enrichment_contract.py
backend/tests/unit/test_enrichment_parser.py
```

Likely modified files:

```text
backend/app/main.py
backend/app/models/defect.py            # only if denormalized status fields are needed
backend/app/routers/edge.py             # only enqueue hook behind config, no blocking call
backend/app/routers/defects.py          # expose enrichment state if needed
backend/app/ws/manager.py               # defect_enriched event if needed
frontend/src/types/defect.ts
frontend/src/components/v4/FrameInspector.tsx
frontend/src/components/v4/DataSourceBadge.tsx or related provenance UI
docs/API_CONTRACT.md
```

Claude Code must explain why each file is changed before implementing.

---

## 14. Rollback Plan

If enrichment causes problems:

1. Disable via config:

```yaml
enrichment_enabled: false
enrichment_auto_enqueue: false
```

2. Keep Phase 10 v1 ORT localizer unchanged.
3. Keep existing `template` observation behavior.
4. Do not delete `defect_enrichments`; leave rows for debugging.
5. Frontend should gracefully hide pending/enrichment panels if fields are absent.
6. Phase 10 v1 snapshot remains intact.

---

## 15. Review Checklist Before Coding

Before Claude Code writes implementation code, reviewer should verify:

- The proposed plan starts from `main`.
- The plan does not modify RKNN integration.
- The plan does not retrain YOLO or expand categories.
- The plan does not add mask/segmentation output.
- The plan does not let VLM output or overwrite bbox/category/defect_type/confidence.
- The plan keeps upload path non-blocking.
- The plan preserves Phase 10 v1 snapshot.
- The plan includes tests for forbidden VLM fields.
- The plan includes frontend source/caveat display.
- The plan has rollback config (template fallback).
- The plan contains no secrets or credential-specific commands.
- The plan uses edge_vlm as primary provider, not cloud_vlm.
- The plan does not hardcode any cloud vendor (DashScope, OpenAI, etc.).
- The plan does not require LoRA for Phase 10.1 delivery.

---

## 16. Final Recommendation

Phase 10.1 should be treated as a controlled asynchronous enrichment layer, not a new localization phase.

**Primary route:** edge_vlm async observation on RK3588.
**Fallback:** template observation.
**Optional:** cloud_vlm comparison/fallback (provider-neutral, not default).

**Base / LoRA policy:** Phase 10.1 uses edge_vlm_base (Qwen3-VL-2B base W8A8). No LoRA required. edge_vlm_lora is optional research only — not a merge gate. If LoRA is evaluated later, its target must be observation/severity_reason only, and must pass the same hallucination guard.

The correct responsibility split remains:

| Field | Source |
|---|---|
| bbox | YOLO/ORT detector output (immutable) |
| defect_type | YOLO class head (immutable) |
| confidence | YOLO detection score (immutable) |
| anomaly_score | EfficientAD (immutable) |
| observation | **edge_vlm** (primary) / template (fallback) / cloud_vlm (optional) |
| severity_reason | **edge_vlm** (primary) / template (fallback) / cloud_vlm (optional) |
| localization_source | `ort_yolov8n_cpu` (immutable) |
| label_source | `yolo_class_head` (immutable) |
| observation_source | `edge_vlm` / `template` / `cloud_vlm` |

Rollback path: set `ENRICHMENT_ENABLED=false` → system falls back to template observation. Phase 10 v1 ORT localizer path is untouched.

The safest next step is for Claude Code to generate `docs/experiments/phase10_1_execution_plan.md` from this planning document, then wait for review before implementation.
