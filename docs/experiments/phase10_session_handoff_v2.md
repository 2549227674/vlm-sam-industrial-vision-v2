# Phase 10 v2 Session Handoff Prompt

复制以下内容到新 Claude Code 会话：

---

你好，我正在继续 vlm-sam-industrial-vision-v2 项目的 Phase 10 工作。

## 当前分支
branch: phase10/localization-refactor-v1（已推送到 origin）

## Phase 10 目标
为 metal_nut + cable（2 类 12 个 defect type）引入有监督 YOLOv8n-detect localizer，替代 FastSAM/VLM bbox 作为主定位方案。

## 已完成的工作

### Track A — ORT CPU Fallback: PASS
- ORT smoke test 在 RK3588 通过：2/2 图像，class correctness，bbox validity，IoU gate
- 延迟：pre=44ms, infer=156ms, post=1ms, total=201ms
- `smoke_test_ort.py` 和 `ort_localizer.py` 已验证

### Track B — RKNN Issue Reproduction: Prepared
- `docs/experiments/phase10_rknn_issue_repro.md` 已完成，可直接用于 GitHub issue
- rknn-toolkit2 2.3.2 BLOCKED（class score r≈0）

### ORT Edge Demo Integration: IMPLEMENTED + TESTED
已实现并验证的文件：

| 文件 | 状态 |
|------|------|
| `scripts/phase10/ort_localizer.py` | Python subprocess 推理引擎 |
| `edge/src/pipeline/localizer_worker.hpp` | C++ T3 worker 头文件 |
| `edge/src/pipeline/localizer_worker.cpp` | C++ T3 worker 实现 |
| `edge/include/edge/common/types.hpp` | VlmReport 新增 v1.3 字段 |
| `edge/include/edge/common/config.hpp` | 新增 localizer_* 配置键 |
| `edge/src/common/config_loader.cpp` | 解析 localizer 配置 |
| `edge/src/upload/upload_worker.cpp` | 发射 v1.3 字段 |
| `edge/src/main.cpp` | 配置驱动 T3 选择 |
| `edge/config.yaml` | 新增 localizer 段，fastsam_enabled=false |
| `edge/CMakeLists.txt` | 新增 localizer_worker.cpp |

### 测试结果

| 测试 | 状态 |
|------|------|
| Python subprocess smoke test | **PASS** |
| C++ integration (RK3588 build+run) | **PASS** |
| API contract (83/83 tests) | **PASS** |
| Performance (T3=172ms < 500ms) | **PASS** |
| Frontend smoke test | **PASS** |
| 30-min soak test | PENDING |

### Commit 历史（最新在前）
```
7a8543d docs: Gate 3 — document pipeline_ms.upload sequencing constraint
ebd29d2 feat: Phase 10 frontend smoke test — ORT variant support + trace viewer localizer lane
1e2b647 docs: Phase 10 v2 session handoff prompt
6213154 docs: Phase 10 ORT integration test results
e8f59e7 fix: JSON parser whitespace handling + subprocess error logging
982dfc4 fix: ORT subprocess readline buffering + ready check + float32 JSON
1635378 feat: upload_worker emits v1.3 optional fields
4f3651a feat: Phase 10 C++ LocalizerWorker + config-driven T3 selection
81b5006 feat: Phase 10 ort_localizer.py — ORT CPU subprocess engine
c4833b3 docs: plan corrections — schema_version stays v1, frame handoff spec
8393ae3 docs: Phase 10 ORT fallback edge demo integration plan
```

## 关键架构决策

1. **Python subprocess 策略**：C++ LocalizerWorker 通过 stdin/stdout 与 `ort_localizer.py` 通信，不链接 C++ ORT 库
2. **配置驱动 T3 选择**：`localizer_backend: "ort"` → LocalizerWorker，否则 → FastSamWorker
3. **schema_version 保持 "v1"**：v1.3 字段是可选附加字段
4. **FastSAM 默认禁用**：`fastsam_enabled: false`
5. **VLM 不调用**：`observation_source: "template"`，severity 固定 "medium"
6. **JSON 解析器**：处理冒号后有无空格两种格式（`"key":"val"` 和 `"key": "val"`）

## 待完成

1. ~~**Frontend smoke test**~~：**PASS** (2026-05-26) — ORT variant rendering, YOLO Localizer Gantt, variant filter, bbox tooltip 全部验证通过
2. **30-min soak test**：需要在 RK3588 上长时间运行验证无 OOM/泄漏
3. **pipeline_ms.upload**：已文档化 — JSON 在 POST 前序列化，upload_ms 始终为 0.0，实际值记录在 stderr
4. **RKNN 方向**：Track B issue repro 已准备好，等用户决策是否提交 GitHub issue

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 集成计划 | `docs/experiments/phase10_ort_integration_plan.md` |
| ORT 验证结果 | `docs/experiments/phase10_onnxruntime_fallback_plan.md` |
| RKNN 诊断 | `docs/experiments/phase10_rknn_fp16_diagnostic.md` |
| RKNN issue repro | `docs/experiments/phase10_rknn_issue_repro.md` |
| 训练结果 | `docs/experiments/phase10_training_run_1.md` |
| API 契约 | `docs/API_CONTRACT.md`（v1.3） |
| ORT 推理脚本 | `scripts/phase10/ort_localizer.py` |
| ORT smoke test | `scripts/phase10/smoke_test_ort.py` |
| C++ LocalizerWorker | `edge/src/pipeline/localizer_worker.cpp` |
| Edge config | `edge/config.yaml` |
| Frontend smoke test screenshot | `screenshots/phase10_frontend_smoke_test_v2.png` |

## SSH 环境

- **Orange Pi 5**（RK3588 推理）：配置在 `~/.ssh/config`，密码在本地 memory 文件
- **AutoDL**（RTX 4090 训练）：配置在 `~/.ssh/config`
- 详细凭据在 `~/.claude/projects/.../memory/reference_ssh_credentials_phase10.md`
- **不要在代码或文档中提交密码/IP/sshpass 命令**
- 板上代理已配置在 `~/.bashrc` 和 `~/.profile`（`http_proxy=http://192.168.137.1:7890`，`no_proxy` 覆盖本地网段）

## 约束

- 不做 RKNN localizer_worker（RKNN BLOCKED）
- 不做 RKNN threshold tuning
- 不做 INT8 作为主路径
- 不重训 YOLOv8s
- VLM 不调用
- FastSAM 代码保留但通过 config 禁用
- schema_version 保持 "v1"
- 代码注释用英文

## Memory 条目

- `feedback_english_comments.md` — 代码注释用英文
- `feedback_autodl_ssh_reminder.md` — 训练前询问 SSH 信息
- `feedback_visual_agent_switch.md` — 视觉任务切换 agent
- `reference_ssh_credentials_phase10.md` — SSH 凭据（Phase 10 结束后删除）

请先确认你了解当前状态，然后我们可以继续 frontend smoke test 或 30-min soak test。
