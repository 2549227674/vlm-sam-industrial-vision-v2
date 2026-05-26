# Phase 10.1a — EdgeVlmProvider Subprocess Manual Runbook

> **Documentation-only.** No code, test, config, or snapshot changes.

---

## 1. Status / Scope

Phase 10.1a subprocess wiring is merged into `main` via **PR #5** (merge commit `d7a2c34`).

This runbook covers manual validation and operation of the EdgeVlmProvider subprocess mode only.

**What this flow does:**

- `POST /api/edge/report` creates a defect only. It does **not** call VLM. It does **not** create enrichment jobs.
- `POST /api/defects/{id}/enrich` creates a pending enrichment job only. It does **not** execute VLM.
- `POST /api/enrich/{enrichment_id}/process?provider=edge_vlm` is the manual execution path: resolves the image, spawns a subprocess, reads its JSON output, validates through the hallucination guard, and writes results.

**What is NOT included in Phase 10.1a:**

- No auto-enqueue
- No worker auto-start
- No HTTP mode (`EDGE_VLM_MODE=http` is stubbed, raises `ProviderUnavailableError`)
- No cloud_vlm provider
- No LoRA
- No RKNN
- No YOLO/ORT localizer changes
- No segmentation/masks
- No category expansion
- No snapshot overwrite

---

## 2. Architecture Summary

```
POST /api/edge/report
  -> multipart image saved to disk
  -> defect row created in DB
  -> no enrichment row created
  -> WebSocket broadcast to frontend

POST /api/defects/{id}/enrich
  -> validates defect exists, has bboxes, has confidence > 0
  -> creates DefectEnrichment row with status="pending"
  -> returns 202 with enrichment_id

POST /api/enrich/{enrichment_id}/process?provider=edge_vlm
  -> loads enrichment + defect from DB
  -> marks enrichment status="running"
  -> resolves /static/defects/... image_url to local absolute path
  -> builds stdin JSON payload from defect fields
  -> spawns subprocess via asyncio.create_subprocess_exec
  -> sends payload on stdin, reads stdout/stderr
  -> passes stdout through hallucination guard (validate_vlm_output)
  -> on success updates ONLY:
       defects.observation
       defects.severity_reason
       defects.observation_source
  -> on guard violation: status="rejected"
  -> on provider error/timeout: status="failed"
```

**Key files:**

| File | Role |
|---|---|
| `backend/app/routers/enrichment.py` | API routes for enrich, process, status |
| `backend/app/services/enrichment_worker.py` | Orchestration: load job -> resolve image -> call provider -> validate -> write |
| `backend/app/services/vlm_provider.py` | `EdgeVlmProvider`, `TemplateProvider`, `CloudVlmProvider` ABC |
| `backend/app/services/enrichment_guard.py` | Hallucination guard: allowlist + forbidden key check |
| `backend/app/services/image_resolver.py` | Resolves `image_url` to local absolute `Path` |
| `backend/app/services/provider_factory.py` | Builds providers from env vars |
| `backend/app/models/enrichment.py` | `DefectEnrichment` SQLAlchemy model |
| `backend/app/schemas/enrichment.py` | Pydantic schemas for enrichment API |
| `backend/prompts/phase10_1_obs_v1.txt` | Prompt template (sent to subprocess for reference) |

---

## 3. Safety Boundaries

### Provider/VLM output MAY only contain:

| Field | Type | Constraint |
|---|---|---|
| `observation` | string | 1..1024 chars |
| `severity_reason` | string | 1..512 chars |
| `accepted_box_ids` | list[int] | Must be subset of input box IDs |

### Provider/VLM MUST NEVER output or modify:

- `bbox` / `bboxes`
- `mask`
- `category`
- `defect_type`
- `confidence`
- `anomaly_score`
- `geometry_correction`
- `localization_source`
- `label_source`
- Any training label field

If any forbidden key appears in stdout JSON, the hallucination guard raises `EnrichmentValidationError` and the enrichment is marked `status="rejected"`. The defect is **not** updated.

### Worker MUST NEVER update:

- `defects.bboxes`
- `defects.category`
- `defects.defect_type`
- `defects.confidence`
- `defects.anomaly_score`
- `defects.localization_source`
- `defects.label_source`

These fields are owned by the upstream detector (YOLO/ORT) and are immutable after initial report.

---

## 4. Environment Variables

Set these in your local shell before starting the backend. **Do not commit real values.**

```bash
# Required for subprocess mode
export ENRICHMENT_PROVIDER=edge_vlm
export EDGE_VLM_MODE=subprocess
export EDGE_VLM_COMMAND="<command that reads stdin JSON and prints stdout JSON>"
export EDGE_VLM_MODEL_NAME="<model label only, e.g. qwen3-vl-2b-base>"
export ENRICHMENT_TIMEOUT_S=30

# Optional: override default storage directory
# export DEFECT_STORAGE_DIR=/path/to/defects
```

**Rules:**

- Do not commit real `EDGE_VLM_COMMAND` values to the repository.
- Do not commit raw IPs, private model paths, tokens, passwords, private keys, `sshpass`, or credentials.
- Use local shell / `.env` / deployment config only.
- `EDGE_VLM_MODEL_NAME` is a label only — it does not select a model file.

---

## 5. Subprocess stdin JSON Contract

When `EDGE_VLM_MODE=subprocess`, the backend sends the following JSON to the subprocess's **stdin**:

```json
{
  "task": "phase10.1_vlm_enrichment",
  "prompt_version": "phase10_1_obs_v1",
  "image_path": "/ABSOLUTE/LOCAL/PATH/TO/IMAGE.jpg",
  "category": "metal_nut",
  "defect_type": "scratch",
  "confidence": 0.95,
  "bbox_format": "normalized_top_left_xywh",
  "boxes": [
    {"box_id": 0, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
  ],
  "localization_source": "ort_yolov8n_cpu",
  "label_source": "yolo_class_head",
  "allowed_output_fields": ["observation", "severity_reason", "accepted_box_ids"],
  "forbidden_output_fields": [
    "bbox",
    "bboxes",
    "mask",
    "category",
    "defect_type",
    "confidence",
    "anomaly_score",
    "geometry_correction",
    "localization_source",
    "label_source"
  ],
  "language": "zh-CN",
  "style": "concise inspector note, no speculation"
}
```

**Notes:**

- `image_path` is an absolute local path resolved from the defect's `image_url`. The subprocess must be able to read this file.
- `boxes` always includes a `box_id` field (0-indexed) added by the backend.
- `bbox_format` is always `normalized_top_left_xywh` (x, y, w, h in [0, 1]).
- `allowed_output_fields` and `forbidden_output_fields` are informational hints for the subprocess; enforcement is done by the backend hallucination guard regardless of subprocess compliance.

---

## 6. Subprocess stdout JSON Contract

The subprocess must print exactly one JSON object to **stdout** and exit with code 0.

**Valid stdout:**

```json
{
  "observation": "检测区域可见局部表面划痕，位置与检测框一致。",
  "severity_reason": "划痕可能破坏表面涂层，需复检确认。",
  "accepted_box_ids": [0]
}
```

**Rules:**

- stdout must be **JSON only** — no markdown fences, no prose prefix/suffix, no ` ```json ``` ` wrappers.
- No extra keys beyond `observation`, `severity_reason`, `accepted_box_ids`. Extra keys are rejected.
- Forbidden keys (`bbox`, `category`, `defect_type`, `confidence`, etc.) are rejected.
- `observation`: string, 1–1024 chars.
- `severity_reason`: string, 1–512 chars.
- `accepted_box_ids`: list of int, each must be a valid `box_id` from stdin `boxes`. If omitted, defaults to all input box IDs.
- stderr is captured for logging but not parsed as output.

---

## 7. Fake Subprocess Validation Scripts

For local testing without a real VLM model, create these scripts under `/tmp`. **Do not place in the repository.**

### `/tmp/vlm_validation_scripts/vlm_ok.py` — valid response

```python
#!/usr/bin/env python3
import sys, json
inp = json.load(sys.stdin)
out = {
    "observation": "Surface scratch detected on metal nut coating. Area appears localized.",
    "severity_reason": "Scratch depth suggests coating breach — may expose base metal.",
    "accepted_box_ids": [bid["box_id"] for bid in inp.get("boxes", [])],
}
print(json.dumps(out))
```

### `/tmp/vlm_validation_scripts/vlm_forbidden.py` — forbidden key

```python
#!/usr/bin/env python3
import sys, json
json.load(sys.stdin)
print(json.dumps({
    "observation": "Looks like a scratch.",
    "severity_reason": "Moderate.",
    "defect_type": "dent",
    "bbox": [0.1, 0.2, 0.3, 0.4],
}))
```

### `/tmp/vlm_validation_scripts/vlm_bad_json.py` — invalid JSON

```python
#!/usr/bin/env python3
import sys
sys.stdin.read()
print("This is not valid JSON at all.")
```

### `/tmp/vlm_validation_scripts/vlm_slow.py` — timeout trigger

```python
#!/usr/bin/env python3
import sys, time
sys.stdin.read()
time.sleep(60)
print("{}")
```

**Setup:**

```bash
mkdir -p /tmp/vlm_validation_scripts
# write each script, then:
chmod +x /tmp/vlm_validation_scripts/*.py
```

---

## 8. Manual Validation Commands

### 8.1 Pull latest main

```bash
git checkout main
git pull origin main
git log --oneline -3
```

Confirm PR #5 merge commit (`d7a2c34`) is present.

### 8.2 Run tests

```bash
source .venv/bin/activate

# Enrichment-specific tests
pytest backend/tests/contract/test_enrichment_api.py \
       backend/tests/contract/test_enrichment_guard.py \
       backend/tests/contract/test_enrichment_process_api.py \
       backend/tests/contract/test_enrichment_worker.py \
       backend/tests/contract/test_vlm_provider.py \
       backend/tests/contract/test_provider_factory.py \
       backend/tests/contract/test_edge_vlm_subprocess.py \
       backend/tests/contract/test_image_resolver.py \
       -v --tb=short

# Full backend contract suite
pytest backend/tests/contract/ -v --tb=short
```

### 8.3 Start backend with fake subprocess

```bash
# In one terminal:
EDGE_VLM_MODE=subprocess \
EDGE_VLM_COMMAND="python3 /tmp/vlm_validation_scripts/vlm_ok.py" \
ENRICHMENT_TIMEOUT_S=10 \
uvicorn backend.app.main:app --port 8000
```

### 8.4 Happy path

```bash
# Create a defect (adjust meta as needed; use a real small JPEG for image=)
curl -s -X POST http://localhost:8000/api/edge/report \
  -F 'image=@/tmp/tiny.jpg;type=image/jpeg' \
  -F 'meta={
    "schema_version": "v1",
    "line_id": "L1",
    "category": "metal_nut",
    "defect_type": "scratch",
    "severity": "high",
    "confidence": 0.95,
    "anomaly_score": 12.5,
    "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
    "description": "validation test",
    "variant": "ort_2B",
    "edge_ts": "2026-05-26T12:00:00Z",
    "localization_source": "ort_yolov8n_cpu",
    "label_source": "yolo_class_head",
    "pipeline_ms": {"efficientad": 350.0, "localizer": 25.0, "upload": 5.0}
  }'

# Capture the actual defect_id from the response (do NOT assume id=1)
DEFECT_ID=<actual_id>

# Create enrichment job
curl -s -X POST http://localhost:8000/api/defects/${DEFECT_ID}/enrich

# Capture actual enrichment_id from the response
ENRICH_ID=<actual_enrichment_id>

# Verify pending
curl -s http://localhost:8000/api/defects/${DEFECT_ID}/enrichment

# Process with edge_vlm
curl -s -X POST "http://localhost:8000/api/enrich/${ENRICH_ID}/process?provider=edge_vlm"

# Verify complete
curl -s http://localhost:8000/api/defects/${DEFECT_ID}/enrichment

# Verify defect updated
curl -s http://localhost:8000/api/defects/${DEFECT_ID}
```

**Verify:**

- enrichment status = `complete`
- provider = `edge_vlm`
- observation populated
- severity_reason populated
- accepted_box_ids = `[0]`
- defect `observation_source` = `edge_vlm`
- defect `category`, `defect_type`, `confidence`, `anomaly_score`, `bboxes`, `localization_source`, `label_source` are **unchanged**

**Warning:** Do not hardcode `id=1` or `enrichment_id=1`. Always use the actual returned IDs.

---

## 9. Failure Validation

| Failure mode | How to trigger | Expected enrichment status | Expected error contains |
|---|---|---|---|
| Invalid JSON | `vlm_bad_json.py` | `rejected` | `Invalid JSON` |
| Forbidden key | `vlm_forbidden.py` | `rejected` | `Forbidden keys present` |
| Timeout | `vlm_slow.py` + `ENRICHMENT_TIMEOUT_S=2` | `failed` | `timed out after 2s` |
| Missing image | Alter `image_url` in local DB to nonexistent path | `failed` | `Image file not found` |
| Provider disabled | `EDGE_VLM_MODE=disabled` (or unset) | `failed` | `EdgeVlmProvider is disabled` |
| Command not found | `EDGE_VLM_COMMAND="/nonexistent/path"` | `failed` | `subprocess command not found` |
| Nonzero exit code | Script that calls `sys.exit(1)` | `failed` | `exited with code 1` |

For each failure case: restart the backend with the relevant `EDGE_VLM_COMMAND`, create a fresh defect, create a fresh enrichment job, process, and verify.

---

## 10. Post-Merge Validation Record

**Validated:** 2026-05-26, on `main` at commit `d7a2c34`.

| Check | Result |
|---|---|
| Enrichment test subset | **147/147 passed** |
| Full backend contract suite | **230/230 passed** |
| Happy path | defect_id=4154, enrichment_id=1, status=**complete**, provider=edge_vlm, accepted_box_ids=[0], observation_source=edge_vlm |
| Invalid JSON | status=**rejected**, error=`Invalid JSON: Expecting value: line 1 column 1 (char 0)` |
| Forbidden key | status=**rejected**, error=`Forbidden keys present: ['bbox', 'defect_type']` |
| Timeout | status=**failed**, error=`timed out after 2s`, elapsed ~2s |
| Missing image | status=**failed**, error=`Image file not found` |
| YOLO/ORT immutable fields | `category`, `defect_type`, `confidence`, `anomaly_score`, `bboxes`, `localization_source`, `label_source` — all unchanged |

**Local DB note:** Validation created test defects and enrichments in the local SQLite database. These may need cleanup before a live demo. No repository files were modified during validation.

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Image not found | `image_resolver` expects `image_url` starting with `/static/defects/` and maps to `backend/static/defects/` (or `DEFECT_STORAGE_DIR` if set) | Check `DEFECT_STORAGE_DIR` env var and that the file exists at the resolved path |
| Subprocess command not found | `EDGE_VLM_COMMAND` path is wrong or script not executable | Check local env only; verify script is `chmod +x` |
| JSON rejected by guard | Subprocess stdout is not valid JSON or contains forbidden/extra keys | Inspect raw stdout; ensure JSON-only output with only `observation`, `severity_reason`, `accepted_box_ids` |
| Timeout on real model | Real VLM inference exceeds `ENRICHMENT_TIMEOUT_S` | Increase `ENRICHMENT_TIMEOUT_S` for real model testing |
| TemplateProvider skips image resolution | By design | `TemplateProvider` is deterministic and does not read image files |
| `enrichment.status` stuck at `pending` | `POST /api/enrich/{id}/process` was never called | This is expected — enrichment jobs are manual-only in Phase 10.1a |

---

## 12. Next Phases

- **Phase 10.1b** (separate PR): Optional auto-enqueue + worker loop.
  - Defaults must be disabled: `ENRICHMENT_ENABLED=false`, `ENRICHMENT_AUTO_ENQUEUE=false`.
  - Must not block the upload path (`POST /api/edge/report` must remain fast).
- **Phase 10.1c** (optional future): Cloud VLM provider.
  - Provider-neutral. No vendor hardcoded.
  - Credentials required from user and never committed.
