# Phase 10.1b — Auto-Enqueue / Optional Worker Loop Execution Plan

> **Planning-only PR. No implementation code.**

---

## 1. Status / Baseline

- Phase 10.1a subprocess manual path is complete and merged (PR #5, commit `d7a2c34`).
- Phase 10.1a runbook is merged (PR #6, commit `6949771`).
- Phase 10.1b starts from `main` after PR #6.
- The current system is **manual-only**: enrichment jobs are created and processed by explicit API calls.
- This document is the execution plan for Phase 10.1b. No code changes are included in this PR.

**Current manual-only flow:**

```
POST /api/edge/report          -> defect created, no enrichment
POST /api/defects/{id}/enrich  -> pending enrichment created
POST /api/enrich/{id}/process  -> provider called, guard validates, defect updated
```

---

## 2. Goals

Phase 10.1b adds two optional features, both **disabled by default**:

1. **Auto-enqueue**: After a defect is successfully inserted via `POST /api/edge/report`, automatically create a `pending` enrichment job if configured.
2. **Worker loop**: An async background task that polls for `pending` enrichment jobs and processes them through the provider + guard pipeline.

**Design constraints:**

- Both features are disabled by default (`ENRICHMENT_ENABLED=false`).
- The upload path (`POST /api/edge/report`) must stay non-blocking.
- Auto-enqueue creates a `pending` job only — no provider call, no VLM wait.
- Worker loop processes jobs asynchronously, only when enabled.
- Same provider interface and hallucination guard as Phase 10.1a.
- Same immutable YOLO/ORT field boundaries.

---

## 3. Non-Goals

The following are explicitly **out of scope** for Phase 10.1b:

- No default auto-enqueue (defaults remain `false`)
- No upload-path VLM call
- No blocking upload path
- No HTTP mode implementation (`EDGE_VLM_MODE=http` remains stubbed)
- No `cloud_vlm` provider
- No LoRA
- No RKNN
- No YOLO/ORT localizer changes
- No segmentation/masks
- No category expansion
- No snapshot overwrite
- No credentials, raw IPs, private paths, tokens, passwords, sshpass, private keys

---

## 4. Config Flags

### New environment variables

| Variable | Default | Description |
|---|---|---|
| `ENRICHMENT_ENABLED` | `false` | Master switch. When `false`, all enrichment features are inactive. |
| `ENRICHMENT_AUTO_ENQUEUE` | `false` | When `true` (and master is `true`), `POST /api/edge/report` creates a pending enrichment job after defect insert. |
| `ENRICHMENT_WORKER_ENABLED` | `false` | When `true` (and master is `true`), a background async worker loop is started in the FastAPI lifespan. |
| `ENRICHMENT_MAX_PER_MINUTE` | `10` | Rate limit: max enrichment jobs processed per minute by the worker. |
| `ENRICHMENT_MAX_RETRIES` | `2` | Reserved for future retry logic. Not active in first implementation. |
| `ENRICHMENT_WORKER_IDLE_SLEEP_S` | `5` | Seconds to sleep when no pending jobs found. |
| `ENRICHMENT_WORKER_POLL_INTERVAL_S` | `2` | Seconds between poll cycles when jobs exist. |

### Existing environment variables (unchanged from Phase 10.1a)

| Variable | Default | Description |
|---|---|---|
| `ENRICHMENT_PROVIDER` | `edge_vlm` | Default provider name. |
| `ENRICHMENT_PROMPT_VERSION` | `phase10_1_obs_v1` | Default prompt version. |
| `ENRICHMENT_TIMEOUT_S` | `30` | Per-call timeout for provider subprocess. |
| `EDGE_VLM_MODE` | `disabled` | `disabled` / `subprocess` / `http`. |
| `EDGE_VLM_COMMAND` | *(none)* | Subprocess command. Must remain local/deployment config only, never committed. |

### Flag semantics

- `ENRICHMENT_ENABLED` is the master switch. When `false`, no enrichment behavior is active regardless of other flags.
- `ENRICHMENT_AUTO_ENQUEUE` controls creation of pending jobs after defect insert only. It does not trigger processing.
- `ENRICHMENT_WORKER_ENABLED` controls background worker loop startup. It does not affect manual process routes.
- Even if auto-enqueue is enabled, the upload path only creates a pending row and returns immediately.
- Worker loop may be enabled independently for local/dev testing. Production defaults remain `false`.
- Real `EDGE_VLM_COMMAND` values must remain local/deployment config only and never committed to the repository.

---

## 5. Proposed Flow

### A. Default behavior (all flags false)

This is identical to Phase 10.1a. No change in behavior.

```
POST /api/edge/report
  -> save image to disk
  -> write defect row
  -> broadcast defect_created via WebSocket
  -> return 201 response
  -> no enrichment job created
  -> no VLM call
```

### B. Auto-enqueue enabled, worker disabled

```
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=false

POST /api/edge/report
  -> save image to disk
  -> write defect row
  -> if defect qualifies (bboxes non-empty, confidence > 0, not placeholder):
       -> create DefectEnrichment row with status="pending"
       -> if duplicate exists (same defect_id + provider + prompt_version, status pending/running):
            -> skip, do not create duplicate
  -> broadcast defect_created via WebSocket
  -> return 201 response
  -> no VLM call
  -> no processing until manual /api/enrich/{id}/process or worker is enabled
```

### C. Auto-enqueue enabled, worker enabled

```
ENRICHMENT_ENABLED=true
ENRICHMENT_AUTO_ENQUEUE=true
ENRICHMENT_WORKER_ENABLED=true

POST /api/edge/report
  -> save image to disk
  -> write defect row
  -> create pending DefectEnrichment row (if qualified)
  -> return 201 response quickly (no VLM wait)

# Separately, in background:
Worker loop (async task in lifespan):
  -> poll for oldest pending DefectEnrichment
  -> mark status="running"
  -> resolve image path
  -> call provider (EdgeVlmProvider subprocess)
  -> validate through hallucination guard
  -> on success: status="complete", denormalize observation fields
  -> on guard violation: status="rejected"
  -> on provider error/timeout: status="failed"
  -> optional: broadcast defect_enriched / defect_enrichment_failed
  -> sleep ENRICHMENT_WORKER_POLL_INTERVAL_S
  -> if no jobs: sleep ENRICHMENT_WORKER_IDLE_SLEEP_S
  -> rate limit: ENRICHMENT_MAX_PER_MINUTE
  -> cancel on shutdown via asyncio.Event or stop_token
```

---

## 6. Upload Path Constraints

- `POST /api/edge/report` must **not** call any provider.
- `POST /api/edge/report` must **not** wait for VLM completion.
- `POST /api/edge/report` should return as quickly as possible.

**Enqueue failure handling — preferred design:**

- Defect insert remains canonical. The defect row is the primary artifact.
- If auto-enqueue fails (e.g., DB constraint violation, unexpected error), the failure should be **logged** and should **not** prevent defect creation if architecturally possible.
- However, if defect and enrichment are in the same DB transaction, a commit/rollback boundary decision must be made:
  - **Option A (recommended)**: Defect insert and enrichment insert share the same transaction. If enrichment insert fails, the defect is also rolled back. This is simpler but means a duplicate-key error on enrichment could block the defect.
  - **Option B**: Defect insert commits first, enrichment insert is attempted in a separate step. If enrichment fails, defect exists but has no enrichment. This is more robust but requires careful handling of the dual-transaction boundary.
- For the first implementation, recommend **Option A** with the duplicate-prevention check done *before* `db.add()` to avoid constraint violations. If a duplicate already exists, simply skip — no error, no rollback.
- `pipeline_ms.upload` sequencing caveat remains unchanged.
- No image snapshot overwrite.

---

## 7. Auto-Enqueue Design

After successful defect flush/refresh in `POST /api/edge/report`:

**Eligibility check** — create a pending enrichment row if ALL of:

1. `ENRICHMENT_ENABLED=true`
2. `ENRICHMENT_AUTO_ENQUEUE=true`
3. Defect has non-empty `bboxes`
4. Defect `confidence > 0`
5. Defect is not a known fallback placeholder (same check as `trigger_enrichment` route)
6. No existing active job for the same `defect_id` + provider + `prompt_version` with status `pending` or `running`

**Enrichment row fields:**

| Field | Value |
|---|---|
| `defect_id` | From new defect |
| `provider` | `ENRICHMENT_PROVIDER` env var (default `edge_vlm`) |
| `provider_model` | `""` (set when provider runs) |
| `prompt_version` | `ENRICHMENT_PROMPT_VERSION` env var |
| `status` | `pending` |
| All other fields | `None` / default |

**Duplicate prevention:**

- The existing `UniqueConstraint("defect_id", "provider", "prompt_version")` on `defect_enrichments` prevents DB-level duplicates.
- However, the constraint only works for exact matches. A `pending` or `running` row for the same defect + provider + prompt already blocks a new insert.
- Pre-check query: `SELECT ... WHERE defect_id=? AND provider=? AND prompt_version=? AND status IN ('pending','running')` — skip if exists.
- On duplicate: skip silently, log at DEBUG level. Do not error. Response remains "defect created."

**No provider call, no raw_response, no observation write at this stage.**

---

## 8. Worker Loop Design

### Startup

The worker loop is an `asyncio.Task` started in the FastAPI `lifespan` context manager, only when:

```
ENRICHMENT_ENABLED=true AND ENRICHMENT_WORKER_ENABLED=true
```

If either is `false`, no worker task is created. The lifespan behaves identically to Phase 10.1a.

### Shutdown

- Worker loop listens for a shutdown signal (`asyncio.Event` or `anyio.Event`).
- On shutdown, the worker cancels the current poll/sleep cycle and exits cleanly.
- In-progress job processing completes before exit (or is left in `running` state for manual recovery).

### Poll cycle

```
while not shutdown_event.is_set():
    job = await process_next_pending_enrichment(db, provider=provider)
    if job is None:
        await asyncio.sleep(ENRICHMENT_WORKER_IDLE_SLEEP_S)
    else:
        # rate limit
        await asyncio.sleep(ENRICHMENT_WORKER_POLL_INTERVAL_S)
```

### Rate limiting

- `ENRICHMENT_MAX_PER_MINUTE` limits jobs processed per 60-second sliding window.
- Implementation: track timestamps of last N completions, sleep if at limit.
- Simple approach: `collections.deque` of timestamps, prune entries older than 60s.

### Failure statuses

| Condition | Status |
|---|---|
| Provider config error | `failed` |
| Provider unavailable | `failed` |
| Provider timeout | `failed` |
| Nonzero subprocess exit | `failed` |
| Guard violation (forbidden key, invalid JSON, etc.) | `rejected` |
| Success | `complete` |

### Reuse of existing logic

- Worker should call `process_next_pending_enrichment()` or `process_enrichment_job()` from `enrichment_worker.py`.
- Worker must **not** introduce a second safety path that bypasses the hallucination guard.
- Provider injection: worker creates a single provider instance from env vars at startup.

---

## 9. Concurrency / Locking Design

### Risks

1. **Multiple worker instances**: If multiple uvicorn workers or processes run, each may pick the same pending job.
2. **Duplicate job pickup**: Two concurrent callers (manual route + worker) may both attempt to process the same enrichment.
3. **SQLite limitations**: SQLite does not support `SELECT ... FOR UPDATE`. Concurrent writes are serialized at the database level.

### Proposed approach for first implementation

- **Single-process worker loop only.** The worker runs as one async task within the single FastAPI process.
- Worker picks the oldest pending job via `process_next_pending_enrichment()`.
- Worker sets `status = "running"` before calling the provider.
- Manual `POST /api/enrich/{id}/process` returns `409` if the job is not `pending`.
- This provides a basic safety net: manual route rejects non-pending jobs, and worker skips non-pending jobs.

### Known limitations

- Cross-process locking is **not** fully solved in Phase 10.1b. If the backend is deployed with multiple workers (e.g., gunicorn with multiple uvicorn workers), duplicate processing is possible.
- For production DB (PostgreSQL), use `SELECT ... FOR UPDATE SKIP LOCKED` or equivalent.
- Document this limitation in the implementation PR.

---

## 10. Retry Model

### Current state

The `DefectEnrichment` model does not have `retry_count`, `last_error_at`, or `next_attempt_at` fields.

### Options

**Option A: Add retry fields now**

- Add `retry_count: int = 0`, `last_error_at: datetime | None`, `next_attempt_at: datetime | None` to `DefectEnrichment`.
- Worker retries failed jobs up to `ENRICHMENT_MAX_RETRIES` times.
- Requires schema migration (Alembic or `Base.metadata.create_all` for SQLite).

**Option B: Defer retries (recommended for first implementation)**

- Keep retry out of Phase 10.1b first implementation.
- Document `ENRICHMENT_MAX_RETRIES` for future use but do not activate.
- Failed jobs remain `failed` and can be manually retried via `POST /api/enrich/{id}/process` or a future retry endpoint.
- No schema migration needed.

### Recommendation

Use **Option B** for Phase 10.1b. Retry logic adds complexity (schema migration, backoff, dead-letter handling) that is not justified by the current manual-first workflow. If retry is needed, it can be a separate PR (`10.1b-retry`) that adds the fields and modifies the worker loop.

---

## 11. API Behavior

### Existing routes (unchanged)

| Route | Behavior |
|---|---|
| `POST /api/defects/{id}/enrich` | Creates pending enrichment job (manual trigger) |
| `GET /api/defects/{id}/enrichment` | Returns latest enrichment record |
| `POST /api/enrich/{id}/process?provider=` | Manually processes one job by ID |
| `POST /api/enrich/process-next?provider=` | Manually processes oldest pending job |

### Changed behavior

| Route | Change |
|---|---|
| `POST /api/edge/report` | May auto-create pending enrichment job if `ENRICHMENT_ENABLED=true` AND `ENRICHMENT_AUTO_ENQUEUE=true`. Response format unchanged. |

### Optional future endpoints (not required for first 10.1b)

| Route | Purpose |
|---|---|
| `GET /api/enrich/worker/status` | Worker health, queue depth, last processed timestamp |
| `POST /api/enrich/retry-failed` | Re-queue failed jobs for retry |

These are not required for the first Phase 10.1b implementation.

---

## 12. WebSocket / Frontend Behavior

### Existing events

- `defect_created`: Broadcast when a defect is inserted. Unchanged.

### Optional new events

When the worker completes an enrichment, the backend may optionally broadcast:

- `defect_enriched`: Enrichment completed successfully. Payload includes `defect_id`, `enrichment_id`, `observation`.
- `defect_enrichment_failed`: Enrichment failed or rejected. Payload includes `defect_id`, `enrichment_id`, `status`, `error_message`.

### Scope decision

- If WebSocket enrichment events are out of scope for the first 10.1b implementation, document that the frontend can poll `GET /api/defects/{id}/enrichment` for status updates.
- No frontend UI changes are required for the first implementation unless already supported by Phase 10.1a enrichment display (`FrameInspector.tsx` observation panel).

---

## 13. Observability

### Log events (structured, at INFO/WARNING level)

| Event | Level | Fields |
|---|---|---|
| Enqueue created | INFO | defect_id, enrichment_id, provider |
| Enqueue skipped (duplicate) | DEBUG | defect_id, provider, existing_enrichment_id |
| Enqueue skipped (placeholder) | DEBUG | defect_id |
| Enqueue skipped (flags disabled) | DEBUG | defect_id |
| Worker started | INFO | provider, model, poll_interval, idle_sleep |
| Worker stopped | INFO | reason (shutdown) |
| Job picked | INFO | enrichment_id, defect_id |
| Provider complete | INFO | enrichment_id, duration_ms |
| Provider failed | WARNING | enrichment_id, error_message |
| Guard rejected | WARNING | enrichment_id, error_message |
| Timeout | WARNING | enrichment_id, timeout_s |
| Rate limit sleep | DEBUG | jobs_this_minute, limit |

### Do NOT log

- Full `EDGE_VLM_COMMAND` value
- Private paths beyond sanitized image basename
- Credentials, secrets, tokens, raw IPs

---

## 14. Test Plan

### Auto-enqueue tests

| Test | Expected |
|---|---|
| Default flags false → `POST /api/edge/report` creates no enrichment | No enrichment rows |
| `ENRICHMENT_ENABLED=true` but `AUTO_ENQUEUE=false` → no enrichment | No enrichment rows |
| `ENRICHMENT_ENABLED=true` and `AUTO_ENQUEUE=true` → pending enrichment created | Enrichment row with status=pending |
| No VLM call during `POST /api/edge/report` | No provider invocation |
| Duplicate prevention (same defect + provider + prompt) | Second enqueue skipped |
| Placeholder/fallback defect not enqueued | No enrichment row |
| Empty bboxes defect not enqueued | No enrichment row |
| Zero confidence defect not enqueued | No enrichment row |
| Enqueue failure does not mutate YOLO-owned fields | Defect fields unchanged |
| Upload response remains fast / does not wait for provider | Response latency unchanged |

### Worker loop tests

| Test | Expected |
|---|---|
| Default flags false → no worker task started | No background task |
| Worker enabled → processes pending job using fake provider | Job status=complete |
| Worker disabled + pending job → no processing | Job remains pending |
| Worker shutdown cancels cleanly | No crash, clean exit |
| Provider timeout → failed | status=failed |
| Guard violation → rejected | status=rejected |
| Success → complete, denormalizes only observation fields | observation_source=edge_vlm |
| YOLO/ORT fields unchanged after worker processing | category, defect_type, etc. immutable |
| Rate limit behavior with multiple jobs | Jobs throttled per MAX_PER_MINUTE |
| Manual route conflict with non-pending job → 409 | Expected error code |

### Regression tests

| Test | Expected |
|---|---|
| Phase 10.1a manual process route still works | Unchanged |
| TemplateProvider still skips image resolution | Unchanged |
| EdgeVlmProvider subprocess still works | Unchanged |
| HTTP mode still unavailable | Unchanged |
| `cloud_vlm` still not implemented | Unchanged |
| Snapshot directory unchanged | No diff |

---

## 15. Rollout / Acceptance Gates

Before the implementation PR is merged, the following must hold:

- [ ] Backend contract suite passes (230/230 or more)
- [ ] Manual fake subprocess validation still passes
- [ ] No snapshot diff
- [ ] No raw IP / credentials / private paths in code or config
- [ ] `POST /api/edge/report` latency not materially increased when auto-enqueue is `false`
- [ ] With all defaults `false`, behavior is identical to Phase 10.1a
- [ ] With `ENRICHMENT_AUTO_ENQUEUE=true` + `ENRICHMENT_WORKER_ENABLED=false`, pending job is created but not processed
- [ ] With `ENRICHMENT_AUTO_ENQUEUE=true` + `ENRICHMENT_WORKER_ENABLED=true`, job is processed asynchronously
- [ ] Failure modes are fail-closed: no YOLO-owned field mutation under any condition

---

## 16. Implementation Staging Recommendation

Split implementation into smaller PRs to reduce review surface and risk:

### PR 10.1b-1: Auto-enqueue (core)

- Config parsing helper (`get_enrichment_config_from_env()` or similar)
- Auto-enqueue logic in `POST /api/edge/report` behind flags
- Defaults `false`
- Tests: auto-enqueue happy path, flags disabled, duplicate prevention, eligibility checks

### PR 10.1b-2: Worker loop (core)

- Worker async task in `lifespan` behind `ENRICHMENT_WORKER_ENABLED`
- Poll cycle, idle sleep, rate limiting
- Reuse `process_next_pending_enrichment()` / `process_enrichment_job()`
- Shutdown cancellation
- Tests: worker happy path, disabled, shutdown, timeout, guard rejection

### PR 10.1b-3 (optional): Events / status / retries

- WebSocket enrichment events (`defect_enriched`, `defect_enrichment_failed`)
- Worker status endpoint (`GET /api/enrich/worker/status`)
- Retry model (schema migration + retry logic)
- Tests for all additions

**Do not combine all optional features into one oversized PR.** Keep each PR focused on one concern.

---

## 17. Open Questions

The following should be answered before implementation begins:

1. **Enqueue failure and upload path**: Should a failed enrichment enqueue ever cause `POST /api/edge/report` to return an error, or should it always be logged silently? *(Recommendation: log silently, never fail the defect creation.)*

2. **Retry fields now or later**: Should `retry_count` / `last_error_at` / `next_attempt_at` be added to the model now, or deferred to a future PR? *(Recommendation: defer, no schema migration in first 10.1b.)*

3. **Worker provider scope**: Should the worker loop support multiple providers, or only process jobs matching `ENRICHMENT_PROVIDER`? *(Recommendation: single provider for simplicity.)*

4. **TemplateProvider in dev mode**: Should the worker process `TemplateProvider` jobs in dev/test environments? *(Recommendation: yes, for testability, but only if `ENRICHMENT_PROVIDER=template`.)*

5. **WebSocket events in first implementation**: Should `defect_enriched` / `defect_enrichment_failed` events be included in the first worker PR, or deferred to 10.1b-3? *(Recommendation: defer. Frontend can poll.)*

6. **SQLite vs production DB**: SQLite serializes writes, so concurrent worker + manual route is safe within one process. How to document the multi-process limitation for production? *(Recommendation: document as known limitation, solve with `FOR UPDATE SKIP LOCKED` when PostgreSQL is adopted.)*

7. **Auto-enqueue latency overhead**: What is acceptable max latency overhead for `POST /api/edge/report` when auto-enqueue is enabled? *(Recommendation: < 5ms additional for the insert query. If the DB is local SQLite, this is negligible.)*
