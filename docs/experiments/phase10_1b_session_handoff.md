# Phase 10.1b Session Handoff — Post PR #9 Merge

复制以下内容到新 Claude Code 会话：

---

你好，我正在继续 vlm-sam-industrial-vision-v2 项目的 Phase 10.1 工作。

## 当前 main 状态

- **main HEAD**: `68b6aaa` — Merge PR #9 (worker loop behind flags)
- **后端测试**: 311/311 passed
- **分支**:
  - `phase10.1b/auto-enqueue-pending-only` — 已合并 (PR #8)
  - `phase10.1b/worker-loop-behind-flags` — 已合并 (PR #9)
  - `phase10.1b/postmerge-validation-doc-sync` — 已推送，**PR 未创建**，docs sync only

## 已合并的 PR（Phase 10.1 全部）

| PR | Commit | 内容 |
|---|---|---|
| PR #4 | `dffaf2c` | enrichment scaffold: DefectEnrichment 模型、schemas、routes、worker、guard、provider ABC、TemplateProvider、EdgeVlmProvider stubs、前端 enrichment 状态展示 |
| PR #5 | `d7a2c34` | EdgeVlmProvider subprocess wiring: image_resolver、asyncio.create_subprocess_exec、fake subprocess tests |
| PR #6 | `6949771` | Phase 10.1a EdgeVlmProvider subprocess manual runbook |
| PR #7 | `494828e` | Phase 10.1b auto-enqueue / worker loop execution plan doc |
| PR #8 | `184dadf` | Optional enrichment auto-enqueue on defect creation — config helper、enqueue helper、57 new tests |
| PR #9 | `68b6aaa` | Optional enrichment worker loop behind flags — poll cycle、rate limiter、lifespan wiring、hardening、19 new tests |

## 当前架构

```
VlmProvider (ABC)
├── TemplateProvider — 确定性 fallback，不需要 image 解析
├── EdgeVlmProvider — subprocess 已实现（stdin/stdout JSON），http 仍为 stub
└── CloudVlmProvider — stub (ProviderUnavailableError)

enrichment_config.py:
  load_enrichment_config() → EnrichmentConfig (frozen dataclass)
  10 个环境变量，全部默认关闭

enrichment_enqueue.py:
  maybe_auto_enqueue_enrichment(db, defect, config)
  5 个 eligibility gates: enabled → auto_enqueue → valid provider → eligible defect → duplicate prevention

enrichment_worker_loop.py:
  enrichment_worker_loop(config, create_session_factory, provider)
  - poll oldest pending job via process_next_pending_enrichment()
  - _RateLimiter sliding window
  - asyncio.CancelledError clean shutdown
  - provider construction fail-closed

enrichment_worker.py:
  process_enrichment_job(db, enrichment_id, provider)
  process_next_pending_enrichment(db, provider)

main.py lifespan:
  if enabled AND worker_enabled → asyncio.create_task(enrichment_worker_loop)
  shutdown: cancel + await, handle already-done task with exception

自动流程（全部默认关闭）:
  POST /api/edge/report → 创建 defect → 如果 flags on: 创建 pending enrichment
  Worker loop → 轮询 pending → process_enrichment_job → provider → guard → 更新 defect

手动流程（仍然可用）:
  POST /api/defects/{id}/enrich         → 创建 pending enrichment job
  POST /api/enrich/{id}/process?provider= → 手动处理
  POST /api/enrich/process-next?provider= → 处理最早的 pending job
  GET  /api/defects/{id}/enrichment      → 查看最新 enrichment 状态
```

## 环境变量（全部默认关闭，不影响现有行为）

```
ENRICHMENT_ENABLED=false
ENRICHMENT_AUTO_ENQUEUE=false
ENRICHMENT_WORKER_ENABLED=false
ENRICHMENT_PROVIDER=edge_vlm
ENRICHMENT_PROMPT_VERSION=phase10_1_obs_v1
ENRICHMENT_MAX_PER_MINUTE=10
ENRICHMENT_MAX_RETRIES=2
ENRICHMENT_WORKER_IDLE_SLEEP_S=5
ENRICHMENT_WORKER_POLL_INTERVAL_S=2
ENRICHMENT_TIMEOUT_S=30
EDGE_VLM_MODE=disabled
EDGE_VLM_COMMAND=
EDGE_VLM_ENDPOINT=
EDGE_VLM_MODEL_NAME=qwen3-vl-2b-base
```

## 下一步可选方向

| 方向 | 范围 | 备注 |
|---|---|---|
| PR #10: docs sync branch merge | `phase10.1b/postmerge-validation-doc-sync` 已推送，创建 PR 合并即可 | 仅文档更新，无代码变更 |
| Phase 10.1c: Cloud VLM provider | 实现 CloudVlmProvider | 需要用户提供 vendor/credentials，不硬编码 |
| WebSocket enrichment events | 前端实时更新 enrichment 状态 | Phase 10.1b-3 optional |
| Worker status endpoint | GET /api/enrichment/worker/status | Phase 10.1b-3 optional |
| Retry schema | retry_count / last_error_at / next_attempt_at | 需要 DB migration |
| PostgreSQL SKIP LOCKED | 多进程 worker 支持 | 当前 worker 是 single-process only |

## 关键约束（必须遵守）

- 代码注释用英文
- 不启用 cloud_vlm（除非用户提供 vendor/credentials）
- 不硬编码任何 cloud provider/vendor/API endpoint
- 不做 LoRA、不训练模型、不改 YOLO/ORT、不改 EfficientAD、不改 RKNN
- 不扩展类别、不做 segmentation/mask
- 不让 VLM 输出或修改 bbox/category/defect_type/confidence/anomaly_score
- 不覆盖 `frontend/public/demo-data/phase10_ort_latest/`
- 不提交 credentials、tokens、raw IP/password、private keys、sshpass
- schema_version 保持 "v1"
- Worker 是 single-process only，生产多 worker 需要 DB locking

## 关键文件位置

| 文件 | 路径 |
|---|---|
| Config helper | `backend/app/services/enrichment_config.py` |
| Auto-enqueue helper | `backend/app/services/enrichment_enqueue.py` |
| Worker loop | `backend/app/services/enrichment_worker_loop.py` |
| Enrichment worker (process job) | `backend/app/services/enrichment_worker.py` |
| VLM providers | `backend/app/services/vlm_provider.py` |
| Provider factory | `backend/app/services/provider_factory.py` |
| Hallucination guard | `backend/app/services/enrichment_guard.py` |
| Image resolver | `backend/app/services/image_resolver.py` |
| Enrichment routes | `backend/app/routers/enrichment.py` |
| Enrichment model | `backend/app/models/enrichment.py` |
| Enrichment schemas | `backend/app/schemas/enrichment.py` |
| Edge router (auto-enqueue hook) | `backend/app/routers/edge.py` |
| FastAPI lifespan | `backend/app/main.py` |
| Execution plan | `docs/experiments/phase10_1_execution_plan.md` |
| Research plan | `docs/experiments/phase10_1_vlm_async_enrichment_plan.md` |
| 10.1b plan | `docs/experiments/phase10_1b_auto_enqueue_worker_loop_plan.md` |
| Runbook | `docs/experiments/phase10_1a_edge_vlm_subprocess_runbook.md` |
| API contract | `docs/API_CONTRACT.md` §14 |

## 测试文件

| 测试 | 路径 | 数量 |
|---|---|---|
| Config | `backend/tests/contract/test_enrichment_config.py` | 35 |
| Auto-enqueue helper | `backend/tests/contract/test_enrichment_auto_enqueue.py` | 17 |
| Edge report auto-enqueue | `backend/tests/contract/test_edge_report_auto_enqueue.py` | 10 |
| Worker loop | `backend/tests/contract/test_enrichment_worker_loop.py` | 19 |
| Enrichment API | `backend/tests/contract/test_enrichment_api.py` | 9 |
| Process API | `backend/tests/contract/test_enrichment_process_api.py` | 14 |
| Enrichment guard | `backend/tests/contract/test_enrichment_guard.py` | 35 |
| Enrichment worker | `backend/tests/contract/test_enrichment_worker.py` | 25 |
| VLM provider | `backend/tests/contract/test_vlm_provider.py` | 25 |
| Provider factory | `backend/tests/contract/test_provider_factory.py` | 13 |
| Edge subprocess | `backend/tests/contract/test_edge_vlm_subprocess.py` | 14 |
| Image resolver | `backend/tests/contract/test_image_resolver.py` | 12 |
| 其他 | 各种 contract tests | 88 |

运行全量: `source .venv/bin/activate && pytest backend/tests/contract/ -v --tb=short`（expect 311/311）

## SSH 环境

- Orange Pi 5 和凭据在 `~/.claude/projects/.../memory/reference_ssh_credentials_phase10.md`
- **不要在代码或文档中提交密码/IP/sshpass 命令**

请先确认你了解当前状态，然后我们可以继续下一步。
