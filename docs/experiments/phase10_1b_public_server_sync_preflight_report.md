# Phase 10.1b-5: Public Server Sync + Enrichment Preflight Report

> **Date**: 2026-05-27
> **Branch**: `phase10.1b/public-server-sync-preflight-report`
> **Status**: Preflight only — full 200/500 live soak NOT run. Public snapshot NOT captured.

---

## 1. Server Sync Summary

### Pre-Sync State

| Item | Value |
|---|---|
| Server path | `/opt/vision-demo/` |
| Git repo | No (deployed via prior rsync/manual copy) |
| Backend PID | 49342 |
| Health before sync | `{"status":"ok","version":"v1","uptime_s":130352}` |
| Enrichment files present | No (`backend/app/services/` missing, `routers/enrichment.py` missing) |
| Enrichment env vars | None |
| `.env` backup | Created on server (timestamped) |

### Sync Action

Rsync'd `backend/` directory from local `main` (commit `1155a6e`, PR #16 merged) to server, excluding `.env`, `.venv`, `__pycache__`, `*.db`, `*.db.bak`, and `static/defects`.

### Post-Sync Verification

| File | Status |
|---|---|
| `backend/app/services/enrichment_worker.py` | Present |
| `backend/app/services/enrichment_enqueue.py` | Present |
| `backend/app/services/enrichment_worker_loop.py` | Present |
| `backend/app/services/enrichment_ws_events.py` | Present |
| `backend/app/routers/enrichment.py` | Present |
| `backend/app/main.py` (enrichment router import) | Confirmed |

Import checks on server:
- `from backend.app.services.enrichment_config import load_enrichment_config` — OK
- `from backend.app.services.enrichment_worker_loop import enrichment_worker_loop` — OK
- `from backend.app.routers.enrichment import router` — OK

### Post-Sync Health

```json
{"status":"ok","version":"v1","uptime_s":0,"db":"ok","ws_clients":0}
```

Enrichment routes registered:
- `/api/defects/{defect_id}/enrichment`
- `/api/enrich/{enrichment_id}/process`

### Issue Encountered and Resolved

After first restart, `GET /api/defects` returned 500 due to stale Python `__pycache__` containing old model bytecode. Resolved by clearing `__pycache__` directories and restarting.

---

## 2. Runtime Configuration

Environment variables added to server `.env`:

```
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=true
ENRICHMENT_PROVIDER=template
ENRICHMENT_TIMEOUT_S=30
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_WORKER_IDLE_SLEEP_S=5
ENRICHMENT_WORKER_POLL_INTERVAL_S=2
```

> **Note**: `ENRICHMENT_PROVIDER=template` was used because the server does not have VLM model files for `edge_vlm` subprocess mode. The template provider exercises the full enrichment pipeline (auto-enqueue, worker lifecycle, WS events, guard validation) without requiring a real VLM model.

> `EDGE_VLM_COMMAND` and `EDGE_VLM_MODEL_NAME` are NOT set in this preflight. Full soak with real `edge_vlm` subprocess requires VLM model availability on the server.

---

## 3. Validation Matrix

### L1 — Public Backend Health

| Item | Result |
|---|---|
| `GET /api/health` | `{"status":"ok"}` |
| **Verdict** | **PASS** |

### L2 — Single Upload Smoke

| Item | Result |
|---|---|
| Category | `metal_nut` |
| Defect type | `scratch` |
| Defect ID | 4109 |
| Upload latency | 1355ms |
| HTTP status | 200 |
| **Verdict** | **PASS** |

### L3 — Auto-Enqueue + Worker Path

| Item | Result |
|---|---|
| Enrichment created | Yes (ID=1, defect_id=4109) |
| Initial status | `pending` |
| Terminal status | `complete` |
| Provider | `template` |
| Time pending→complete | ~5s |
| **Verdict** | **PASS** |

### L4 — Real EdgeVLM Complete Path

| Item | Result |
|---|---|
| Provider used | `template` (not `edge_vlm`) |
| `observation_source` | `template` |
| Reason | Server lacks VLM model files for subprocess mode |
| **Verdict** | **PARTIAL** — pipeline exercised, real VLM inference not tested |

### L5 — Upload Non-Blocking

| Item | Result |
|---|---|
| Upload latency (defect 4109) | 1355ms |
| Upload latency (defect 4110) | 1332ms |
| Threshold | < 5000ms |
| **Verdict** | **PASS** |

### L6 — Large-Volume Stream

| Item | Result |
|---|---|
| **Verdict** | **NOT RUN** — per preflight limits |

### L7 — Ineligible Defects

| Item | Result |
|---|---|
| Defect ID | 4111 |
| Bboxes | `[]` (empty) |
| Auto-enqueue | Skipped (correct) |
| **Verdict** | **PASS** |

### L8 — Worker Stability

| Item | Result |
|---|---|
| Backend crash | None |
| Worker death | None |
| **Verdict** | **PASS** (2 defects processed, no errors) |

### L9 — WebSocket UX

| Item | Result |
|---|---|
| **Verdict** | **NOT TESTED** — requires live frontend connection |

### L10 — Snapshot Capture

| Item | Result |
|---|---|
| **Verdict** | **NOT RUN** — per preflight limits |

---

## 4. Canonical Field Immutability

Verified on defect 4109 (enrichment `complete`):

| Field | Before Enrichment | After Enrichment | Mutated? |
|---|---|---|---|
| `bboxes` | `[{"x":0.3,"y":0.3,"w":0.1,"h":0.1}]` | Same | No |
| `category` | `metal_nut` | Same | No |
| `defect_type` | `scratch` | Same | No |
| `confidence` | `0.95` | Same | No |
| `anomaly_score` | `42.0` | Same | No |
| `localization_source` | `null` | Same | No |
| `label_source` | `null` | Same | No |

Enrichment-only fields written:
- `observation`: `[Template] metal_nut: scratch detected (confidence=0.95)...`
- `severity_reason`: `[Template] Severity assigned by default rule...`
- `observation_source`: `template`

**Verdict**: **PASS** — zero canonical field mutations.

---

## 5. Enrichment API Verification

`GET /api/defects/4109/enrichment` returned:

```json
{
    "id": 1,
    "defect_id": 4109,
    "provider": "template",
    "provider_model": "template",
    "prompt_version": "phase10_1_obs_v1",
    "status": "complete",
    "observation": "[Template] metal_nut: scratch detected (confidence=0.95)...",
    "severity_reason": "[Template] Severity assigned by default rule...",
    "accepted_box_ids": [0],
    "error_message": null,
    "created_at": "2026-05-27T08:35:59.924384Z",
    "updated_at": "2026-05-27T08:36:04.056628Z",
    "completed_at": "2026-05-27T08:36:04.053087Z"
}
```

---

## 6. Rollback Procedure

Available if needed:

```bash
# Level 1: Stop worker
ENRICHMENT_WORKER_ENABLED=false

# Level 2: Disable enrichment entirely
ENRICHMENT_ENABLED=false
```

No rollback was required during this preflight.

---

## 7. Explicit Statements

- **Full 200/500 live soak was NOT run.**
- **Public snapshot was NOT captured.**
- **No existing snapshots were overwritten.**
- **No deployment configuration was changed beyond adding enrichment env vars.**
- **No backend or frontend code was modified.**
- **`ENRICHMENT_PROVIDER=template` was used** because the server does not have VLM model files for `edge_vlm` subprocess mode. Full soak requires either:
  - VLM model files deployed to the server, or
  - `edge_vlm` HTTP mode wired to an external VLM endpoint, or
  - `edge_vlm` subprocess with a wrapper script that calls the RK3588

---

## 8. Security Scan

```bash
grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}" \
  docs/experiments/phase10_1b_public_server_sync_preflight_report.md || true
```

**Result**: No secrets, no raw private IPs, no credentials committed. All server paths use the documented `/opt/vision-demo/` prefix only. The `EDGE_UPLOAD_TOKEN` value is NOT included in this report.

---

## 9. Files Changed

| File | Action |
|---|---|
| `docs/experiments/phase10_1b_public_server_sync_preflight_report.md` | Created |

No application code, config, or snapshot files were changed.
