# Phase 10.1b-5: RK3588 Live Stream Soak + Public Snapshot Capture — Execution Plan

> **Status**: Plan only — no execution, no deployment, no snapshot capture in this PR.
> **Branch**: `phase10.1b/live-stream-soak-plan`
> **Date**: 2026-05-27

---

## 1. Purpose

Phase 10.1b-5 validates the full live demo path end-to-end:

```
RK3588 edge pipeline
  -> POST /api/edge/report on vision.hanlab.app
  -> auto-enqueue (ENRICHMENT_AUTO_ENQUEUE=true)
  -> worker loop (ENRICHMENT_WORKER_ENABLED=true)
  -> real EdgeVLM subprocess (EDGE_VLM_MODE=subprocess)
  -> WebSocket enrichment UX (defect_enrichment_updated events)
  -> public snapshot capture
```

This soak test exercises every layer of the enrichment stack under sustained load from the real edge device against the public demo backend. It confirms that:

- The upload path remains non-blocking under volume.
- The enrichment worker processes defects through all terminal states (complete / rejected / failed).
- The frontend WebSocket enrichment UX correctly reflects lifecycle transitions.
- A sanitized public snapshot can be captured from live data.

---

## 2. Category Boundary

The live stream soak uses **only** YOLO-supported production categories:

- **metal_nut**
- **cable**

**Excluded from this live soak**:

| Excluded Category | Reason |
|---|---|
| zipper | Not in YOLO production label space |
| pill | Non-production smoke category |
| screw | Non-production smoke category |
| All other MVTec classes | Not Phase-10 hardware smoke categories |

**Hard constraints**:

- No category expansion.
- No schema expansion.
- No YOLO label-space expansion.
- Only `metal_nut` and `cable` may appear in upload payloads, enrichment results, and public snapshot data.

---

## 3. Dataset / Data Volume

### Volume Targets

| Tier | Upload Count | Notes |
|---|---|---|
| Minimum | 200 | Sufficient for statistical confidence on success rate and latency |
| Preferred | 500+ | If the system is stable after the first 200; exercises backlog and worker recovery |

### Category Balance

- **metal_nut**: 50%
- **cable**: 50%

### Image Content Guidelines

- Include normal and defect-like examples if available from the MVTec test set.
- Include controlled edge cases:
  - **Empty bbox** — should not enqueue enrichment.
  - **Zero confidence** — should not enqueue enrichment.
  - **Valid bbox** — should enqueue and proceed through worker lifecycle.
- Do **not** include private or identifiable images.
- All images must come from the public MVTec AD dataset or the project's existing test image pool.

### Dataset Location

```
<LOCAL_DATASET_ROOT>/metal_nut/test/
<LOCAL_DATASET_ROOT>/cable/test/
```

---

## 4. Environment Placeholders

All hostnames, paths, and credentials below use placeholders. **Do not replace with real values in committed files.**

| Placeholder | Description |
|---|---|
| `<RK3588_HOST>` | Orange Pi 5 Plus 16GB hostname or IP |
| `<VISION_PUBLIC_URL>` | `https://vision.hanlab.app` |
| `<PUBLIC_API_BASE>` | `https://vision.hanlab.app` |
| `<PUBLIC_SNAPSHOT_DIR>` | Server filesystem path for public snapshot serving |
| `<DEPLOY_USER>` | SSH user for the public server |
| `<REMOTE_PROJECT_DIR>` | Absolute project root on the public server |
| `<EDGE_VLM_WRAPPER_PATH>` | Absolute path to the EdgeVLM wrapper script on the public server |
| `<MODEL_NAME_LABEL>` | Label for the VLM model variant (e.g., `edge_vlm_qwen3vl_2b`) |
| `<LOCAL_DATASET_ROOT>` | Local path to MVTec AD dataset |

---

## 5. Runtime Configuration

### Enrichment Environment Variables

Set these on the public backend before starting the soak:

```bash
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=true
ENRICHMENT_PROVIDER=edge_vlm
EDGE_VLM_MODE=subprocess
EDGE_VLM_COMMAND="<REDACTED_REAL_COMMAND>"
EDGE_VLM_MODEL_NAME="<MODEL_NAME_LABEL>"
ENRICHMENT_TIMEOUT_S=30
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_WORKER_IDLE_SLEEP_S=5
ENRICHMENT_WORKER_POLL_INTERVAL_S=2
```

> **Note**: `EDGE_VLM_COMMAND` must be redacted. Never commit the real command.

### Rollback

If the soak causes instability, disable enrichment in order of least to most disruptive:

```bash
# Level 1: Stop processing new enrichments (existing jobs finish)
ENRICHMENT_WORKER_ENABLED=false

# Level 2: Disable enrichment entirely (no enqueue, no worker)
ENRICHMENT_ENABLED=false
```

---

## 6. Live Stream Validation Matrix

### L1 — Public Backend Health

| Item | Detail |
|---|---|
| Action | `GET https://vision.hanlab.app/api/health` |
| Expected | `{"status": "healthy"}` |
| Gate | Must pass before proceeding to L2 |

### L2 — RK3588 Single Upload Smoke

| Item | Detail |
|---|---|
| Action | Upload one `metal_nut` sample via POST `/api/edge/report` from RK3588 |
| Expected | Defect created (HTTP 201) |
| Expected | Frontend receives `defect_created` WebSocket event |
| Gate | Must pass before proceeding to L3 |

### L3 — Auto-Enqueue + Worker Path

| Item | Detail |
|---|---|
| Action | Observe the defect from L2 |
| Expected | Eligible defect creates a `pending` enrichment |
| Expected | Worker transitions: `pending` -> `running` -> terminal state (`complete` / `rejected` / `failed`) |
| Expected | Frontend receives `defect_enrichment_updated` WebSocket events for each transition |
| Gate | Must confirm full lifecycle |

### L4 — Real EdgeVLM Complete Path

| Item | Detail |
|---|---|
| Action | Inspect a `complete` enrichment from L3 |
| Expected | `observation_source` = `edge_vlm` |
| Expected | `observation` and `severity_reason` are non-empty |
| Expected | Frontend DetailDrawer shows values after terminal WS event triggers re-fetch |
| Gate | Confirms real VLM inference path, not template fallback |

### L5 — Upload Non-Blocking

| Item | Detail |
|---|---|
| Action | Measure POST `/api/edge/report` response time during enrichment activity |
| Expected | Upload returns quickly (independent of VLM processing time) |
| Expected | No provider calls in the upload path |
| Gate | Upload latency must not degrade when worker is under load |

### L6 — Large-Volume Stream

| Item | Detail |
|---|---|
| Action | Run 200-500+ uploads from RK3588, balanced across `metal_nut` and `cable` |
| Expected | Record throughput, success count, rejected count, failed count |
| Expected | No backend crash, no worker death |
| Gate | Success rate >= 95%, crash count = 0 |

### L7 — Ineligible Defects

| Item | Detail |
|---|---|
| Action | Upload defects with empty bbox, zero confidence, or fallback placeholder values |
| Expected | No auto-enqueue for ineligible defects |
| Gate | Zero enrichment records created for ineligible uploads |

### L8 — Worker Stability

| Item | Detail |
|---|---|
| Action | Monitor worker throughout the soak |
| Expected | No backend crash |
| Expected | No worker death |
| Expected | If tested: clean cancellation and restart |
| Gate | Crash count = 0, worker_restart_count = 0 (unless intentional restart test) |

### L9 — WebSocket UX

| Item | Detail |
|---|---|
| Action | Observe frontend enrichment UI throughout the soak |
| Expected | All lifecycle badges visible: `pending`, `running`, `complete`, `rejected`, `failed` |
| Expected | Terminal event triggers enrichment re-fetch |
| Expected | DetailDrawer shows correct `observation` / `severity_reason` after re-fetch |
| Gate | All 5 status badges observed; re-fetch confirmed |

### L10 — Snapshot Capture

| Item | Detail |
|---|---|
| Action | After soak completes, capture sanitized public snapshot |
| Expected | Snapshot contains only `metal_nut` and `cable` defects |
| Expected | Include `complete` / `rejected` / `failed` examples if safe (no sensitive data) |
| Expected | No private paths or server data in snapshot |
| Gate | Secret scan passes on snapshot files |

---

## 7. Metrics to Collect

Record the following metrics during and after the soak:

| Metric | Description |
|---|---|
| `run_id` | Unique identifier for this soak run (e.g., `soak_20260527_001`) |
| `started_at` | ISO-8601 timestamp when soak began |
| `ended_at` | ISO-8601 timestamp when soak ended |
| `total_uploads` | Total POST /api/edge/report attempts |
| `metal_nut_count` | Uploads in metal_nut category |
| `cable_count` | Uploads in cable category |
| `upload_success_count` | HTTP 201 responses |
| `upload_error_count` | Non-201 responses |
| `p50_upload_ms` | Median upload latency |
| `p95_upload_ms` | 95th percentile upload latency |
| `enrichment_created_count` | Total enrichment records created |
| `enrichment_complete_count` | Enrichments reaching `complete` state |
| `enrichment_rejected_count` | Enrichments reaching `rejected` state |
| `enrichment_failed_count` | Enrichments reaching `failed` state |
| `p50_enrichment_s` | Median time from enqueue to terminal state |
| `p95_enrichment_s` | 95th percentile time from enqueue to terminal state |
| `timeout_count` | Enrichments that hit ENRICHMENT_TIMEOUT_S |
| `invalid_json_count` | VLM outputs that failed JSON parsing |
| `forbidden_key_count` | Payloads that contained forbidden field mutations |
| `websocket_event_count` | Total `defect_enrichment_updated` events received by frontend |
| `ws_disconnect_count` | WebSocket disconnections during soak |
| `backend_crash_count` | Backend process crashes |
| `worker_restart_count` | Worker loop restarts (intentional or otherwise) |
| `snapshot_record_count` | Number of records in the final public snapshot |

---

## 8. Acceptance Criteria

### Must Pass

| Criterion | Verification |
|---|---|
| Public backend remains healthy | L1 passes throughout soak |
| Upload path remains non-blocking | L5: upload latency independent of VLM load |
| Zero provider calls in upload path | No enrichment worker invocation from POST handler |
| WebSocket events visible for enrichment lifecycle | L9: all 5 statuses observed |
| Terminal events update frontend observation/severity_reason | L9: DetailDrawer shows correct values after re-fetch |
| Only metal_nut and cable used | L6, L10: no other categories in uploads or snapshot |
| Zero canonical field mutations | All enrichment results verified against the forbidden-fields list |
| No credentials or private paths committed | Secret scan on plan + snapshot |
| Public snapshot contains sanitized data only | L10: scan for paths, IPs, tokens |

### Canonical Fields — Never Mutated by Enrichment

The enrichment pipeline must **never** modify these fields:

- `bbox`
- `category`
- `defect_type`
- `confidence`
- `anomaly_score`
- `localization_source`
- `label_source`

### Suggested Thresholds

| Metric | Threshold |
|---|---|
| Upload success rate | >= 95% |
| Backend crash count | = 0 |
| Canonical field mutation count | = 0 |
| Forbidden key acceptance count | = 0 |
| Valid enrichment terminal state rate | Recorded (not necessarily gated for first soak) |
| p95 upload latency | Recorded and reviewed (no hard gate for first soak) |

---

## 9. Public Snapshot Capture Requirements

### Target Snapshot Name

```
phase10_1b_live_edge_vlm_latest
```

### Repo / Static Structure

```
frontend/public/demo-data/phase10_1b_live_edge_vlm_latest/
  README.md
  snapshot_meta.json
  defects.json
  stats.json
  images/
    <uuid>.jpg
    ...
```

### Public Server Path (Placeholder)

```
<PUBLIC_SNAPSHOT_DIR>/phase10_1b_live_edge_vlm_latest/
```

### Rules

- **Do not overwrite** `phase10_ort_latest`.
- **Do not overwrite** `phase10_1b_edge_vlm_latest`.
- **Do not include** private server paths.
- **Do not include** raw upload source paths.
- **Do not include** raw `EDGE_VLM_COMMAND`.
- **Do not include** credentials.
- **Include only** `metal_nut` and `cable` defects.
- **Include** snapshot metadata and a safety note in `README.md`.
- **Mark** as live soak snapshot, not benchmark dataset.

### snapshot_meta.json Template

```json
{
  "snapshot_name": "phase10_1b_live_edge_vlm_latest",
  "type": "live_soak",
  "generated_at": "<ISO-8601>",
  "run_id": "<run_id>",
  "categories": ["metal_nut", "cable"],
  "total_defects": 0,
  "enrichment_complete": 0,
  "enrichment_rejected": 0,
  "enrichment_failed": 0,
  "safety_note": "This snapshot was captured from a live soak test. All data is sanitized. No private paths, credentials, or server-specific information are included."
}
```

---

## 10. vision.hanlab.app Deployment Note

- **This plan does not deploy.** It prepares the execution procedure only.
- The actual execution PR / report must record whether deployment was performed manually.
- If the public snapshot is saved on `vision.hanlab.app`, record only the sanitized public path or URL — never the server filesystem path.
- Any `.env` changes on the public server must be documented in the execution report with redacted values.

---

## 11. Failure Handling

| Failure | Response |
|---|---|
| **Upload latency high** (p95 > 2x baseline) | Pause soak; check backend CPU/memory; check network; resume after root cause addressed |
| **Worker backlog grows** (pending count rising) | Check `ENRICHMENT_MAX_PER_MINUTE`; check EdgeVLM subprocess health; consider temporarily increasing limit |
| **EdgeVLM timeout rate high** (> 10%) | Check model health on the server; increase `ENRICHMENT_TIMEOUT_S` if model is slow but functional; check for OOM |
| **WebSocket disconnects** | Check frontend network; check backend ConnectionManager health; reconnect is automatic (exponential backoff) |
| **Bad JSON increases** (> 5% invalid) | Check EdgeVLM subprocess output; may indicate model degradation or prompt issue |
| **Backend memory grows** | Check for leaks in worker loop; restart backend if necessary; record memory over time |
| **Public server becomes unstable** | Stop soak immediately; disable enrichment (`ENRICHMENT_ENABLED=false`); investigate |
| **Snapshot contains private paths** | Do not publish; re-sanitize; re-capture; re-run secret scan |
| **Categories outside metal_nut/cable appear** | Stop soak; investigate source; these must not reach the public snapshot |

---

## 12. Security / Secret Scan

Before committing this plan, run:

```bash
grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}" \
  docs/experiments/phase10_1b_live_stream_soak_plan.md || true
```

**Expected result**: No secrets, no raw private IPs. Only benign text matches (e.g., the word "secret" in this scan instruction itself) are acceptable.

After the soak, before publishing the public snapshot, run the same scan against all snapshot files:

```bash
grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}" \
  frontend/public/demo-data/phase10_1b_live_edge_vlm_latest/ || true
```

---

## 13. Out of Scope

The following are explicitly **out of scope** for this plan and its execution:

- No execution in this PR.
- No deployment.
- No server upload.
- No public snapshot write.
- No backend feature changes.
- No frontend redesign.
- No `cloud_vlm` provider.
- No HTTP mode (`EDGE_VLM_MODE=http`).
- No retry schema.
- No PostgreSQL locking.
- No worker status endpoint (`GET /api/enrichment/worker/status`).
- No YOLO / ORT / RKNN / LoRA changes.
- No category expansion beyond `metal_nut` and `cable`.
- No snapshot overwrite of existing snapshots (`phase10_ort_latest`, `phase10_1b_edge_vlm_latest`).

---

## 14. Execution Checklist (For Future Use)

When this plan is executed in a follow-up PR:

- [ ] Set environment variables on public server (Section 5)
- [ ] Confirm backend health (L1)
- [ ] Run single upload smoke test (L2)
- [ ] Confirm auto-enqueue + worker lifecycle (L3)
- [ ] Confirm real EdgeVLM complete path (L4)
- [ ] Measure upload non-blocking (L5)
- [ ] Run large-volume stream (L6)
- [ ] Test ineligible defects (L7)
- [ ] Monitor worker stability (L8)
- [ ] Observe WebSocket UX (L9)
- [ ] Collect all metrics (Section 7)
- [ ] Capture sanitized public snapshot (L10)
- [ ] Run secret scan on snapshot (Section 12)
- [ ] Verify acceptance criteria (Section 8)
- [ ] Write execution report with real metrics (redacted env)
- [ ] Rollback env vars if needed (Section 5)
