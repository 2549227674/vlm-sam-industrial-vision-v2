# Phase 10.1b — Real RK3588 EdgeVLM Hardware Validation Plan

> Branch: `phase10.1b/real-rk3588-edge-vlm-validation-plan`
> Main baseline: `655b5ce` (Merge PR #11, fake subprocess smoke validation)
> Date: 2026-05-26
> Purpose: **docs-only** planning runbook for moving from fake subprocess validation to real RK3588 EdgeVLM hardware validation.
>
> **No application code changes. No credentials or private deployment values.**
> This validates the already-merged async enrichment pipeline with a real RK3588 EdgeVLM subprocess.
> It does not implement new features.

---

## 1. Merged Baseline

| PR | Commit | Content |
|---|---|---|
| PR #4 | `dffaf2c` | Enrichment scaffold: model, schemas, routes, worker, guard, provider ABC, TemplateProvider, EdgeVlmProvider stubs |
| PR #5 | `d7a2c34` | EdgeVlmProvider subprocess wiring: image_resolver, async subprocess, fake subprocess tests |
| PR #6 | `6949771` | Phase 10.1a EdgeVlmProvider subprocess manual runbook |
| PR #7 | `494828e` | Phase 10.1b auto-enqueue / worker loop execution plan |
| PR #8 | `184dadf` | Optional enrichment auto-enqueue on defect creation |
| PR #9 | `68b6aaa` | Optional enrichment worker loop behind flags |
| PR #10 | `5dc4ea4` | Phase 10.1 docs sync |
| PR #11 | `655b5ce` | Fake subprocess smoke validation report |

**Fake subprocess smoke (PR #11) already validated:**

- S1: default flags false → defect created, no enrichment, no provider call
- S2: auto-enqueue only → pending enrichment, no processing
- S3: worker + template → pending→complete, template observation populated
- S4a: edge_vlm subprocess valid JSON → complete, edge_vlm observation, accepted_box_ids valid
- S4b: forbidden keys → rejected, "Forbidden keys present"
- S4c: timeout → failed, "timed out after 3s", backend healthy
- S4d: bad JSON → rejected, "Invalid JSON", backend healthy
- YOLO/ORT immutable fields: unchanged across all scenarios
- Contract tests: 311/311 passed before and after

---

## 2. Objective

Prove that the **already-merged** async enrichment pipeline works with a **real RK3588 EdgeVLM subprocess**.

Must demonstrate:

1. Real RK3588 EdgeVLM subprocess can be launched through existing `EdgeVlmProvider`.
2. It reads stdin JSON and writes strict stdout JSON.
3. It returns **only**:
   - `observation`
   - `severity_reason`
   - `accepted_box_ids`
4. It **never** returns or modifies:
   - `bbox` / `bboxes`
   - `mask`
   - `category`
   - `defect_type`
   - `confidence`
   - `anomaly_score`
   - `geometry_correction`
   - `localization_source`
   - `label_source`
   - training labels
5. Worker loop processes jobs asynchronously.
6. `/api/edge/report` remains non-blocking and never calls provider directly.
7. On valid output, enrichment becomes `complete` and only observation fields are denormalized.
8. On invalid output / timeout / provider error, enrichment fails or rejects cleanly and backend remains healthy.

---

## 3. Environment / Prerequisites

| Prerequisite | Placeholder | Notes |
|---|---|---|
| RK3588 board or secure deployment environment | `<RK3588_HOST>` | Orange Pi 5 Plus 16GB or equivalent |
| Remote project directory | `<REMOTE_PROJECT_DIR>` | Where model files and wrapper script live |
| Edge VLM wrapper script | `<EDGE_VLM_WRAPPER_PATH>` | Python script conforming to stdin/stdout JSON protocol |
| Model label | `<MODEL_NAME_LABEL>` | e.g. `qwen3-vl-2b-base` or `qwen3-vl-4b-base` |
| Local test image | `<LOCAL_TEST_IMAGE_PATH>` | JPEG image accessible to backend upload path |
| Qwen3-VL runtime | — | RKLLM runtime >= 1.2.3, model loaded and responsive |
| Python 3.10+ on RK3588 | — | For running the wrapper script |
| Sufficient RAM | — | Qwen3-VL-2B ~3.3 GB RSS, 4B ~7 GB RSS |
| Test images available locally | — | MVTec AD subset or equivalent |

**Do NOT include in this document:**
- Real IP addresses
- Private paths
- Usernames
- Passwords
- API keys
- Tokens
- `sshpass` commands
- Private keys
- Model license paths
- Raw `EDGE_VLM_COMMAND` values from a private environment

---

## 4. Subprocess Protocol

### 4.1 Stdin JSON Contract

The existing `EdgeVlmProvider._build_payload()` produces this JSON on subprocess stdin:

```json
{
  "task": "phase10.1_vlm_enrichment",
  "prompt_version": "phase10_1_obs_v1",
  "image_path": "/ABSOLUTE/LOCAL/PATH/TO/IMAGE.jpg",
  "category": "metal_nut",
  "defect_type": "scratch",
  "confidence": 0.87,
  "bbox_format": "normalized_top_left_xywh",
  "boxes": [
    {"box_id": 0, "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.15}
  ],
  "localization_source": "ort_yolov8n_cpu",
  "label_source": "yolo_class_head",
  "allowed_output_fields": ["observation", "severity_reason", "accepted_box_ids"],
  "forbidden_output_fields": [
    "bbox", "bboxes", "mask", "category", "defect_type",
    "confidence", "anomaly_score", "geometry_correction",
    "localization_source", "label_source"
  ],
  "language": "zh-CN",
  "style": "concise inspector note, no speculation"
}
```

**Key fields the wrapper should use:**
- `image_path`: absolute path to the image file on the machine running the subprocess
- `category` / `defect_type`: read-only context for the prompt
- `boxes`: read-only reference for `accepted_box_ids` mapping
- `language` / `style`: prompt formatting hints

### 4.2 Stdout JSON Contract

Valid stdout must be **strict JSON only**:

```json
{
  "observation": "检测区域可见局部表面划痕，位置与检测框一致。",
  "severity_reason": "划痕可能破坏表面涂层，建议复检确认。",
  "accepted_box_ids": [0]
}
```

**Rules:**
- stdout must contain JSON only — no markdown fences, no prose prefix or suffix
- No extra keys beyond `observation`, `severity_reason`, `accepted_box_ids`
- No forbidden keys (`bbox`, `bboxes`, `mask`, `category`, `defect_type`, `confidence`, `anomaly_score`, `geometry_correction`, `localization_source`, `label_source`)
- `observation`: 1–1024 chars, non-empty string
- `severity_reason`: 1–512 chars, non-empty string
- `accepted_box_ids`: list of ints, each must be a valid `box_id` from input
- stderr may contain logs but is **not** parsed as output
- Nonzero exit code = provider failure
- Timeout = failed enrichment (backend kills process)

### 4.3 Guard Validation

The hallucination guard (`enrichment_guard.py`) validates:

1. JSON parseable (no markdown fences)
2. No forbidden keys present
3. No extra keys outside `{observation, severity_reason, accepted_box_ids}`
4. `observation` is non-empty string, ≤ 1024 chars
5. `severity_reason` is non-empty string, ≤ 512 chars
6. `accepted_box_ids` are ints within input box IDs

Violation → `EnrichmentValidationError` → enrichment status = `rejected`.

---

## 5. Wrapper Script Expectations

The real wrapper script must conform to this protocol. Pseudocode only:

```python
#!/usr/bin/env python3
"""Real RK3588 EdgeVLM wrapper — stdin/stdout JSON protocol."""
import json
import sys
import <rkllm_runtime_module>

def main():
    # 1. Read JSON from stdin
    inp = json.load(sys.stdin)

    # 2. Extract read-only context
    image_path = inp["image_path"]
    category = inp["category"]
    defect_type = inp["defect_type"]
    boxes = inp["boxes"]

    # 3. Load image (for vision encoder or crop)
    image = load_image(image_path)

    # 4. Build prompt using category/defect_type/boxes as READ-ONLY context
    #    Do NOT ask the VLM to locate defects or correct boxes.
    #    The detector has already done localization.
    prompt = build_observation_prompt(category, defect_type, boxes)

    # 5. Run real RK3588 EdgeVLM inference
    result = rkllm_infer(image, prompt)

    # 6. Parse model output into strict JSON
    output = {
        "observation": result.observation_text,
        "severity_reason": result.severity_text,
        "accepted_box_ids": [b["box_id"] for b in boxes],
    }

    # 7. Write strict JSON to stdout — nothing else
    json.dump(output, sys.stdout, ensure_ascii=False)

    # 8. Exit 0 on success
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Write diagnostics to stderr ONLY
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
```

**Critical rules:**
- The wrapper must **not** ask the VLM to locate defects or correct boxes
- The prompt should state the detector already localized the defect
- stdout must contain JSON only — no logs, no debug prints
- stderr is for diagnostics only
- Exit 0 on success, nonzero on failure
- Handle model/runtime errors with nonzero exit or valid error JSON

---

## 6. Backend Environment Configuration

### Production smoke config

```bash
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=true
ENRICHMENT_PROVIDER=edge_vlm
EDGE_VLM_MODE=subprocess
EDGE_VLM_COMMAND="<python3 /path/to/real_edge_vlm_wrapper.py --model <MODEL_NAME_LABEL>>"
EDGE_VLM_MODEL_NAME="<MODEL_NAME_LABEL>"
ENRICHMENT_TIMEOUT_S=30
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_WORKER_IDLE_SLEEP_S=5
ENRICHMENT_WORKER_POLL_INTERVAL_S=2
```

### Fallback configs

```bash
# Worker disabled (auto-enqueue creates pending jobs, no processing)
ENRICHMENT_WORKER_ENABLED=false

# Full rollback (no enrichment at all, template observation only)
ENRICHMENT_ENABLED=false
```

**Important:**
- Do **not** commit real `EDGE_VLM_COMMAND` values
- Do **not** commit private model paths or raw IPs
- Store real env values only in local shell, deployment config, or ignored `.env`
- Use placeholders in all committed documentation

---

## 7. Validation Matrix

### R1 — Real wrapper direct CLI smoke

**Goal:** Verify the wrapper script emits strict JSON when called directly.

```bash
echo '{"task":"phase10.1_vlm_enrichment","image_path":"<LOCAL_TEST_IMAGE_PATH>","category":"metal_nut","defect_type":"scratch","confidence":0.87,"bbox_format":"normalized_top_left_xywh","boxes":[{"box_id":0,"x":0.1,"y":0.2,"w":0.3,"h":0.15}],"localization_source":"ort_yolov8n_cpu","label_source":"yolo_class_head","allowed_output_fields":["observation","severity_reason","accepted_box_ids"],"forbidden_output_fields":[],"language":"zh-CN","style":"concise inspector note"}' \
  | python3 <EDGE_VLM_WRAPPER_PATH>
```

**Expected:**
- Strict JSON stdout with `observation`, `severity_reason`, `accepted_box_ids`
- Exit code 0
- No logs on stdout
- stderr may contain diagnostics

### R2 — Backend worker + real edge_vlm happy path

**Goal:** Full end-to-end through the merged pipeline.

**Steps:**
1. Start backend with production smoke config
2. `POST /api/edge/report` with eligible defect (non-empty bboxes, confidence > 0)
3. Auto-enqueue creates pending enrichment
4. Worker picks up pending job, calls real subprocess
5. Guard validates output
6. Enrichment status → `complete`

**Verify:**
- `observation_source` = `edge_vlm`
- `provider` = `edge_vlm`
- `provider_model` = `<MODEL_NAME_LABEL>`
- `accepted_box_ids` valid
- `observation` and `severity_reason` populated with real VLM output
- All YOLO/ORT canonical fields unchanged

### R3 — Forbidden key defense

**Goal:** Confirm hallucination guard rejects forbidden keys from real model.

**Option A:** Create a test wrapper that injects forbidden keys into output.
**Option B:** If the real model occasionally hallucinates forbidden keys, observe rejection.

**Verify:**
- Enrichment status = `rejected`
- Error message contains "Forbidden keys"
- Canonical defect fields unchanged
- Backend healthy

### R4 — Bad JSON defense

**Goal:** Confirm guard handles malformed JSON from wrapper.

**Approach:** Create a test wrapper variant that emits truncated JSON, or test with `EDGE_VLM_COMMAND="python3 -c 'import sys; sys.stdout.write(\"truncated\")'"`

**Verify:**
- Enrichment status = `rejected`
- Error message contains "Invalid JSON"
- Backend healthy

### R5 — Timeout defense

**Goal:** Confirm timeout kills long-running subprocess.

**Approach:** Create a test wrapper that sleeps beyond `ENRICHMENT_TIMEOUT_S`.

**Verify:**
- Enrichment status = `failed`
- Error message contains "timed out"
- Backend healthy
- POST /api/edge/report unaffected

### R6 — Nonzero exit defense

**Goal:** Confirm nonzero exit code is handled as provider failure.

**Approach:** `EDGE_VLM_COMMAND="python3 -c 'import sys; sys.exit(1)'"`

**Verify:**
- Enrichment status = `failed`
- Error message recorded
- Backend healthy

### R7 — Upload path non-blocking

**Goal:** Confirm POST /api/edge/report never calls provider.

**Approach:** Compare POST response time and behavior with worker enabled vs disabled. Provider must not be called during upload.

**Verify:**
- POST returns 200 immediately regardless of worker state
- No provider log entries during upload
- Enrichment created as pending (not processed during upload)

### R8 — Multiple sequential jobs

**Goal:** Confirm worker processes multiple jobs correctly.

**Steps:**
1. Upload 3–5 eligible defects rapidly
2. Worker processes sequentially (single-process)
3. Check all enrichments reach `complete` or `rejected`

**Verify:**
- No duplicate processing
- Rate limit respected (`ENRICHMENT_MAX_PER_MINUTE`)
- All YOLO/ORT fields unchanged across all defects

### R9 — Ineligible defects

**Goal:** Confirm auto-enqueue skips ineligible defects.

**Test with:**
- Empty bboxes (`"bboxes": []`)
- Confidence ≤ 0 (`"confidence": 0`)
- Fallback placeholder defect

**Verify:**
- No enrichment row created
- Defect still created normally

### R10 — Backend restart / shutdown

**Goal:** Confirm clean shutdown and restart.

**Steps:**
1. Start backend with worker enabled
2. Upload a defect (pending job created)
3. Send SIGINT (Ctrl+C) to backend
4. Restart backend
5. Verify pending job still exists and can be processed

**Verify:**
- Worker cancels cleanly (no orphaned processes)
- Backend restarts healthy
- Pending jobs survive restart (SQLite persistence)

---

## 8. Metrics to Collect

### Per-job metrics table

| Field | Source | Notes |
|---|---|---|
| `defect_id` | Defect table | Auto-increment |
| `enrichment_id` | Enrichment table | Auto-increment |
| `provider` | Enrichment table | `edge_vlm` |
| `provider_model` | Enrichment table | `<MODEL_NAME_LABEL>` |
| `status` | Enrichment table | `complete` / `rejected` / `failed` |
| Total processing time | `completed_at - created_at` | Wall clock |
| Subprocess wall time | Logs or trace | From subprocess launch to exit |
| TTFT if available | Wrapper stderr | First token latency |
| Decode tokens/sec if available | Wrapper stderr | Output generation speed |
| RSS / memory if available | Wrapper stderr or system monitor | Process memory |
| Stdout JSON valid? | Guard result | `true` / `false` |
| Guard result | Enrichment status | `complete` / `rejected` |
| `error_message` | Enrichment table | null if complete |
| `observation_source` | Defect table | `edge_vlm` after denormalization |
| `accepted_box_ids` | Enrichment table | Must be subset of input box IDs |
| YOLO fields unchanged? | Manual check | category/defect_type/confidence/anomaly_score/bboxes/localization_source/label_source |
| Backend healthy? | `/api/health` | `ok` |

### Acceptance thresholds

| Metric | Threshold | Action if missed |
|---|---|---|
| Valid JSON rate | >= 90% on small smoke set | Improve wrapper prompt/sanitizer |
| Forbidden key rate | **0** accepted forbidden outputs | Guard must reject all |
| Upload path provider calls | **0** | Must never call during upload |
| Canonical field mutation | **0** | Guard must prevent all writes |
| Backend crash | **0** | Investigate immediately |
| Timeout rate | Record, do not gate unless excessive | Tune timeout or model |
| Median subprocess wall time | Record only, no strict gate in first smoke | Baseline for future optimization |

---

## 9. Sample Commands

### Direct wrapper CLI test

```bash
# Test wrapper directly with sample payload (placeholder path)
echo '{
  "task": "phase10.1_vlm_enrichment",
  "prompt_version": "phase10_1_obs_v1",
  "image_path": "<LOCAL_TEST_IMAGE_PATH>",
  "category": "metal_nut",
  "defect_type": "scratch",
  "confidence": 0.87,
  "bbox_format": "normalized_top_left_xywh",
  "boxes": [{"box_id": 0, "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.15}],
  "localization_source": "ort_yolov8n_cpu",
  "label_source": "yolo_class_head",
  "allowed_output_fields": ["observation", "severity_reason", "accepted_box_ids"],
  "forbidden_output_fields": ["bbox", "bboxes", "mask", "category", "defect_type", "confidence", "anomaly_score", "geometry_correction", "localization_source", "label_source"],
  "language": "zh-CN",
  "style": "concise inspector note, no speculation"
}' | python3 <EDGE_VLM_WRAPPER_PATH>
```

### Backend start with env vars

```bash
source .venv/bin/activate && \
ENRICHMENT_ENABLED=true \
ENRICHMENT_AUTO_ENQUEUE=true \
ENRICHMENT_WORKER_ENABLED=true \
ENRICHMENT_PROVIDER=edge_vlm \
EDGE_VLM_MODE=subprocess \
EDGE_VLM_COMMAND="<python3 /path/to/wrapper.py>" \
EDGE_VLM_MODEL_NAME="<MODEL_NAME_LABEL>" \
ENRICHMENT_TIMEOUT_S=30 \
ENRICHMENT_MAX_PER_MINUTE=10 \
ENRICHMENT_WORKER_IDLE_SLEEP_S=5 \
ENRICHMENT_WORKER_POLL_INTERVAL_S=2 \
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

### Upload defect via curl

```bash
curl -X POST http://127.0.0.1:8000/api/edge/report \
  -F "image=@<LOCAL_TEST_IMAGE_PATH>;type=image/jpeg" \
  -F 'meta={
    "line_id": "validation-line-1",
    "category": "metal_nut",
    "defect_type": "scratch",
    "severity": "medium",
    "confidence": 0.87,
    "anomaly_score": 0.42,
    "bboxes": [{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.15}],
    "description": "real hardware validation",
    "variant": "2B_base",
    "edge_ts": "2026-05-26T14:00:00+08:00",
    "pipeline_ms": {"efficientad": 350, "localizer": 120, "upload": 50},
    "schema_version": "v1",
    "localization_source": "ort_yolov8n_cpu",
    "label_source": "yolo_class_head",
    "observation_source": "template"
  }'
```

### Poll enrichment status

```bash
# Check enrichment status for defect ID 1
curl -s http://127.0.0.1:8000/api/defects/1/enrichment | python3 -m json.tool

# Check defect with denormalized fields
curl -s http://127.0.0.1:8000/api/defects/1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('status:', d.get('observation_source'))
print('observation:', d.get('observation'))
print('severity_reason:', d.get('severity_reason'))
print('category:', d.get('category'), '(must be unchanged)')
print('defect_type:', d.get('defect_type'), '(must be unchanged)')
print('confidence:', d.get('confidence'), '(must be unchanged)')
"
```

### Health check

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

### Secret scan (post-validation, before any commit)

```bash
grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\\.){3}[0-9]{1,3}" \
  docs/experiments/phase10_1b_real_rk3588_edge_vlm_validation_plan.md || echo "No secrets found"
```

---

## 10. Acceptance Criteria

Must pass:

- [ ] Real wrapper direct CLI emits strict JSON (R1)
- [ ] Backend worker can process at least one real edge_vlm job to `complete` (R2)
- [ ] Forbidden keys rejected, canonical fields unchanged (R3)
- [ ] Bad JSON rejected, backend healthy (R4)
- [ ] Timeout failed, backend healthy, no upload blockage (R5)
- [ ] Nonzero exit failed, error recorded (R6)
- [ ] POST /api/edge/report does not block on VLM (R7)
- [ ] Multiple sequential jobs processed correctly (R8)
- [ ] Ineligible defects not enqueued (R9)
- [ ] Backend restart clean, pending jobs survive (R10)
- [ ] YOLO/ORT canonical fields unchanged in all scenarios
- [ ] No snapshot changes
- [ ] No credentials committed
- [ ] Contract tests still pass: `pytest backend/tests/contract/ -v`

---

## 11. Known Limitations

1. **Single-process worker only.** No PostgreSQL SKIP LOCKED or multi-process locking. Production multi-worker needs DB-level advisory locks.

2. **No WebSocket enrichment events.** Frontend does not receive real-time enrichment updates. Must poll `GET /api/defects/{id}/enrichment`.

3. **No worker status endpoint.** Cannot query worker loop health or queue depth via API.

4. **No cloud_vlm.** CloudVlmProvider remains stub-only (`ProviderUnavailableError`).

5. **No LoRA requirement.** Phase 10.1 uses base model only. LoRA for observation/severity is optional research, not a merge gate.

6. **No RKNN localizer fix.** ORT CPU fallback is the current localizer. RKNN numeric consistency remains blocked.

7. **No performance optimization.** First hardware smoke validates correctness, not latency. Median subprocess wall time is recorded but not gated.

8. **Small sample smoke does not prove production stability.** Full stability testing requires extended runs with diverse defect types and images.

---

## 12. Decision Gate After Validation

| Outcome | Next Step |
|---|---|
| **All scenarios pass** | Proceed to Phase 10.1b-3b (frontend/WebSocket enrichment UX) or real demo packaging |
| **JSON instability** | Improve wrapper prompt / output sanitizer; do **not** weaken hallucination guard |
| **Latency too high** | Tune timeout / rate limit / model size; consider smaller model or batching strategy |
| **Memory unstable** | Reduce concurrency to one worker; keep worker disabled by default |
| **Field hallucination** | Keep guard strict; reject outputs; revise prompt/wrapper |
| **Wrapper crashes** | Fix wrapper runtime errors; add error handling; ensure nonzero exit on failure |

---

## 13. Out of Scope Checklist

Explicitly **not** part of this validation:

- [ ] Application code changes
- [ ] Production feature implementation
- [ ] Cloud VLM provider
- [ ] HTTP mode for EdgeVlmProvider
- [ ] Retry schema / `retry_count` / `last_error_at` / `next_attempt_at`
- [ ] WebSocket enrichment events
- [ ] Worker status endpoint
- [ ] Frontend changes
- [ ] YOLO / ORT / RKNN localizer changes
- [ ] LoRA training or adapter changes
- [ ] Segmentation / masks
- [ ] Category expansion
- [ ] Snapshot overwrite (`frontend/public/demo-data/phase10_ort_latest/`)
- [ ] Credentials / raw IPs / private paths / tokens / passwords / `sshpass` / private keys

---

## 14. References

| Document | Path |
|---|---|
| Fake subprocess smoke report | `docs/experiments/phase10_1b_edge_vlm_subprocess_smoke_validation.md` |
| Phase 10.1 research plan | `docs/experiments/phase10_1_vlm_async_enrichment_plan.md` |
| Phase 10.1 execution plan | `docs/experiments/phase10_1_execution_plan.md` |
| Phase 10.1b auto-enqueue plan | `docs/experiments/phase10_1b_auto_enqueue_worker_loop_plan.md` |
| EdgeVlmProvider source | `backend/app/services/vlm_provider.py` |
| Hallucination guard | `backend/app/services/enrichment_guard.py` |
| Auto-enqueue helper | `backend/app/services/enrichment_enqueue.py` |
| Worker loop | `backend/app/services/enrichment_worker_loop.py` |
| Enrichment worker | `backend/app/services/enrichment_worker.py` |
| API contract §14 | `docs/API_CONTRACT.md` |
