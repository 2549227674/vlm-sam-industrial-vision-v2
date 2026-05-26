# Phase 10 v1 Session Handoff Prompt

复制以下内容到新 Claude Code 会话：

---

你好，我正在继续 vlm-sam-industrial-vision-v2 项目的 Phase 10 v1 工作。

## 当前分支
branch: phase10/localization-refactor-v1（已推送到 origin）

## Phase 10 v1 目标
为 metal_nut + cable（2 类 12 个 defect type）引入有监督 YOLOv8n-detect localizer（ORT CPU fallback），替代 FastSAM/VLM bbox 作为主定位方案。

## 所有 Gate 已 PASS

| Gate | 状态 |
|------|------|
| Python subprocess smoke | **PASS** |
| C++ ORT integration | **PASS** |
| API contract (83/83) | **PASS** |
| Frontend smoke | **PASS** |
| Extended RK3588 soak (27m27s) | **PASS** — 2082 frames, 0 crashes, 0 HTTP 400, RSS=34MB, T3 avg=187.7ms |
| Snapshot demo | **PASS** — 40 curated records, 0 fallback, stats/manifest match |
| RKNN numeric consistency | **BLOCKED** (rknn-toolkit2 2.3.2) |
| VLM enrichment | **Phase 10.1** (not called in v1) |

## 关键架构决策

1. **Python subprocess 策略**：C++ LocalizerWorker 通过 stdin/stdout 与 `ort_localizer.py` 通信
2. **配置驱动 T3 选择**：`localizer_backend: "ort"` → LocalizerWorker
3. **schema_version 保持 "v1"**：v1.3 字段是可选附加字段
4. **FastSAM 默认禁用**：`fastsam_enabled: false`
5. **VLM 不调用**：`observation_source: "template"`，severity 固定 "medium"
6. **Bbox 格式**：normalized top-left xywh（x/y = 左上角，w/h = 宽高，[0,1]）
7. **C++ JSON 解析**：`json_bboxes()` 搜索 `"bboxes"` key 后找 `[`（处理冒号后空格）

## Bbox 坐标说明

- API/前端 bbox 使用 normalized top-left xywh
- YOLO 内部 decode 使用 center-xywh，但 `ort_localizer.py` 导出时已转换为 top-left
- bbox 坐标 clamp 到 [0,1] 防止 API 校验错误
- 前端 FrameInspector.tsx 有 fallback 检测（conf=0 + anomaly + center-box → 虚线边框 + "unsupported" 标签）

## 部署状态

- **远程前端**：https://vision.hanlab.app（API_BASE=https://vision.hanlab.app）
- **Orange Pi soak test**：已停止（tmux session "soak" 已结束）
- **Droplet 后端 auth**：临时禁用（测试用），生产环境需重新启用
- **Snapshot**：40 curated records from extended soak backend，已部署到 droplet 前端

## Phase 10.1 路线图

Phase 10 v1 范围：ORT localizer 做 bbox + defect_type + confidence。VLM 未调用。
- observation_source="template"，severity 固定 "medium"
- observation / severity_reason / defect_family enrichment 属于 Phase 10.1 范围

## 最近 Commit（最新在前）

```
b01929c docs: fix snapshot README — extended soak wording, 38 images
9b0dd9d docs/data: final Phase 10 v1 consistency cleanup — extended soak, snapshot, README
68ebbf0 docs: finalize Phase 10 v1 deliverables — soak PASS, snapshot PASS, roadmap note
482c714 fix: preload new image before swapping — no placeholder flash
66f7289 fix: top-left bbox + revert image key (no placeholder flash)
f57c07b revert: restore center-x/cy bbox format — top-left was less accurate
f710da9 docs: Gate 2 PASS — 30-min soak test results
1d76333 fix: unpad letterbox coordinates in ort_localizer.py
8a53e0c fix: image/bbox sync in latest frame — key image container to defect.id
ac28f0e docs: add bbox clamping fix to soak test notes
ac270bb fix: clamp bbox coordinates to [0,1] in ort_localizer.py
ce914f1 fix: fallback bbox detection + bbox convention fix + soak restart
08fce41 docs: mark snapshot as preliminary; distinguish soak test status
e9c5154 feat: Phase 10 ORT snapshot demo for static frontend export
7747ea7 docs: update session handoff — Gate 1 PASS, Gate 3 documented
7a8543d docs: Gate 3 — document pipeline_ms.upload sequencing constraint
ebd29d2 feat: Phase 10 frontend smoke test — ORT variant support + trace viewer localizer lane
1e2b647 docs: Phase 10 v2 session handoff prompt
6213154 docs: Phase 10 ORT integration test results
e8f59e7 fix: JSON parser whitespace handling + subprocess error logging
982dfc4 fix: ORT subprocess readline buffering + ready check + float32 JSON
1635378 feat: upload_worker emits v1.3 optional fields
4f3651a feat: Phase 10 C++ LocalizerWorker + config-driven T3 selection
81b5006 feat: Phase 10 ort_localizer.py — ORT CPU subprocess engine
```

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 集成计划 | `docs/experiments/phase10_ort_integration_plan.md` |
| Snapshot 计划 | `docs/experiments/phase10_snapshot_demo_plan.md` |
| ORT 推理脚本 | `scripts/phase10/ort_localizer.py` |
| C++ LocalizerWorker | `edge/src/pipeline/localizer_worker.cpp` |
| Edge config | `edge/config.yaml` |
| Snapshot 数据 | `frontend/public/demo-data/phase10_ort_latest/` |
| 前端 FrameInspector | `frontend/src/components/v4/FrameInspector.tsx` |
| 前端 ProfilePage | `frontend/src/components/v4/ProfilePage.tsx` |
| API 契约 | `docs/API_CONTRACT.md`（v1.3） |

## 约束

- 不做 RKNN localizer（RKNN BLOCKED）
- 不做 RKNN threshold tuning / INT8 主路径
- 不重训 YOLOv8s
- VLM 不调用
- schema_version 保持 "v1"
- 代码注释用英文
- 不提交密码/IP/sshpass 命令到仓库

## SSH 环境

- Orange Pi 5 和凭据在 `~/.claude/projects/.../memory/reference_ssh_credentials_phase10.md`
- **不要在代码或文档中提交密码/IP/sshpass 命令**

## 可能的下一步

1. merge-main：将 phase10/localization-refactor-v1 合并到 main
2. Phase 10.1：VLM enrichment（observation/severity_reason）
3. RKNN 方向：提交 GitHub issue 或等待 toolkit 更新
4. 生产准备：re-enable droplet auth，清理测试数据

请先确认你了解当前状态，然后我们可以继续。
