# Phase 9：仓库审计与优先级路线图

**日期**：2026-05-23
**Commit**：58a354e（基线）+ 审计修复
**分支**：main
**审计者**：Claude Code（自动化扫描 + 人工复核）

---

## 1. 基线事实（代码与板端数据确认）

| 维度 | 确认状态 |
|---|---|
| 边缘主线 | EfficientAD-S **FP16/no-quant** raw RKNN → FastSAM **FP16/no-quant** RKNN → Qwen3-VL-**2B base** W8A8 RKLLM |
| T2 EfficientAD 定位 | 负载卸载门控（load shedding gate），**不是**可靠检测器 |
| EfficientAD score mode | `raw_score`（ReduceMax），`map_mean` 最差 |
| 队列容量 | Q1=4, Q2=2, Q3=4（`edge/src/main.cpp:119-121` 确认） |
| VLM 主线 | 2B base W8A8 |
| LoRA 状态 | PC bf16 有效；RK3588 W8A8 下细粒度能力坍塌（F-VLM-04） |
| 4B 状态 | 运行路径已打通；速度慢；spatial merge **未正确实现**（F-VLM-06） |
| FastSAM mask decode | **未实现** — 仅 bbox proposal（`fastsam_worker.cpp:3` 有 TODO） |
| pass_all 安全节拍 | 推荐 13000ms，最小稳定 10000ms |
| API contract 版本 | v1.2（`docs/API_CONTRACT.md`） |
| 类别级阈值 | Phase 8A-Fix-Fix 校准（raw_score good_p95），工程起始值 |
| `edge/config.yaml` 默认值 | `vlm_model_size: "2B"`（主线默认，4B 为实验选项） |

---

## 2. 审计发现

### P0：文档/图表与事实不一致

#### F-P0-01：Mermaid 图中 EfficientAD INT8 过时引用

**状态**：已修复
**影响**：高 — 面试/展示可信度风险

多处 Mermaid 图此前仍将 `EfficientAD-S INT8` 作为部署配置，实际主线已切换为 FP16/no-quant：

| 文件 | 行号 | 修正前 | 修正后 |
|---|---|---|---|
| `docs/ARCHITECTURE.md` | 74 | `EfficientAD-S INT8` | `EfficientAD-S FP16` |
| `docs/ARCHITECTURE.md` | 82 | `INT8 RKNN` | `FP16 RKNN (no-quant)` |
| `docs/ARCHITECTURE.md` | 147 | `256x256 INT8` | `256x256 FP16` |
| `docs/reports/edge_deployment_summary.md` | 79 | `EfficientAD-S INT8` | `EfficientAD-S FP16` |
| `docs/reports/edge_deployment_summary.md` | 87 | `INT8 RKNN` | `FP16 RKNN (no-quant)` |
| `docs/reports/edge_deployment_summary.md` | 267 | `256x256 INT8` | `256x256 FP16` |

全部 6 处已修正。`model_raw_noquant.rknn` 为当前活跃模型。

#### F-P0-02：队列容量在多处图表中不一致

**状态**：已修复
**影响**：高 — 与代码矛盾，容易混淆

代码实际配置（`edge/src/main.cpp:119-121`）为 Q1=4, Q2=2, Q3=4。此前 4 处 Mermaid 图的 Q1/Q3 容量均错误标注为 `cap=2`。

| 文件 | 修正前 | 修正后 |
|---|---|---|
| `docs/ARCHITECTURE.md` 上方 Mermaid（行 73, 77） | Q1=2, Q3=2 | Q1=4, Q3=4 |
| `docs/ARCHITECTURE.md` 下方 Mermaid（行 141, 165） | capacity=2 | Q1=4, Q3=4 |
| `docs/reports/edge_deployment_summary.md` 第二个 Mermaid（行 78, 82） | cap=2 | Q1=4, Q3=4 |
| `docs/reports/edge_deployment_summary.md` 第四个 Mermaid（行 261, 285） | capacity=2 | Q1=4, Q3=4 |

#### F-P0-03：Beat Sweep 图题将 10000ms 称为"甜蜜点"

**状态**：已修复
**影响**：中 — 与同文件数据表矛盾

修正前：`beat_ms=10000 为甜蜜点`
修正后：`beat_ms=13000 推荐，10000 最小稳定边界`

数据表显示 10000ms 为"边界可用"（queue_drop=1，VLM_avg/beat=1.10），并非最优点。13000ms（ratio=0.83）才是推荐节拍。

#### F-P0-04：T2→Q2 连线标签写成 "anomaly + mask"

**状态**：已修复
**影响**：中 — FastSAM mask decode 未实现

`docs/ARCHITECTURE.md:79` 和 `docs/reports/edge_deployment_summary.md:84` 此前标注为 `anomaly + mask`。已修正为 `frame + score`（T2 仅输出异常分数 + 元数据；mask 来自 T3 FastSAM）。

#### F-P0-05：缺少 README.md

**状态**：已修复
**影响**：高 — 面试官/招聘方首先看到的文件

已在仓库根目录创建 `README.md`，包含：
- 如实的项目描述（不夸大）
- 架构概览
- 关键设计决策
- 当前状态（准确描述各项能力边界）
- 技术栈、目录结构、快速启动、文档链接

### P0：展示叙事防误导

`README.md` 中已落实所有叙事守卫要求：
- T2 描述为"load shedding gate"（非"检测器"或"分类器"）
- LoRA 描述明确标注 PC/RK3588 行为差异
- 4B 描述为"运行路径已打通，需修复 spatial merge"
- threshold 模式描述为"基于 pass_all 推算，soak test 待做"
- 无"板端 defect_type 精确分类已经成功"等夸大表述

### P1：契约与代码一致性

#### F-P1-01：`edge/config.yaml` 默认值为 4B，主线为 2B

**状态**：已修复
**影响**：低-中 — 配置混淆风险

将 `vlm_model_size: "4B"` 改为 `"2B"`，并添加注释说明 4B 为实验选项且 spatial merge 修复待完成。

#### F-P1-02：4B spatial merge 未正确实现（F-VLM-06）

**状态**：已知缺陷，未修复
**影响**：中高 — 4B 对纹理敏感类别（carpet）产生错误嵌入

`edge/src/vlm/qwen3vl_runner.cpp:419-422` 使用连续 memcpy 而非正确的 2x2 spatial merge 排列：`[28,28,1024] → permute[14,2,14,2,1024] → [196,4096]`。详见 `docs/ENGINEERING_FINDINGS.md:F-VLM-06`。

修复路径已记录但未实现，不阻塞 2B 主线。延后至 CLAUDE_04 处理。

#### F-P1-03：FastSAM Stage 2 输出标签写成"segmentation" / "mask"

**状态**：已修复
**影响**：低-中

`docs/ARCHITECTURE.md:181` Stage 2 输出已从"mask + bbox"修正为"bbox proposal (mask decode TODO)"。

#### F-P1-04：ARCHITECTURE.md §3.2 表头写"RK3588 INT8 延迟"

**状态**：已修复
**影响**：低

表头从"RK3588 INT8 延迟"修正为"RK3588 延迟"。EfficientAD 行已补充 FP16 raw 输出和 INT8 弃用说明。

#### F-P1-05：运行时指标暴露不充分

**状态**：部分实现
**影响**：中

`edge/src/main.cpp` 在进程关闭时将指标打印到 stderr。已有计数器：`ead_gate_pass`、`ead_gate_drop`、`queue_drop`。缺失项：
- 各队列当前深度 / 高水位线（实时）
- push/pop 等待时间（ms）
- T3 VLM 繁忙比
- 上传重试计数 / 最后错误 / 退避时间

延后至 CLAUDE_04 处理。

### P2：实验与验证空白

#### F-P2-01：无 threshold 模式 soak test

**状态**：未完成
**影响**：中

Phase 7 Prompt 2F 仅在短时间运行（~30s）下验证了 threshold 模式。无长时间（30 分钟以上）soak test。"threshold 模式吞吐边界"的说法是基于 pass_all 数据推算，非实测结论。

延后至 CLAUDE_05 处理。

#### F-P2-02：FastSAM mask decode 未实现

**状态**：TODO
**影响**：低（当前范围内）

`edge/src/pipeline/fastsam_worker.cpp:141` 注释说明 prototype mask decode 需要 output0 ch 5-36 系数。可增强演示效果，但需 contract 版本升级至 v1.3（新增字段）。

#### F-P2-03：校准集与评估集未分离

**状态**：已识别，未修复
**影响**：低

Phase 8A 使用 MVTec test split 同时进行阈值校准和 AUROC 评估。详见 `docs/ENGINEERING_FINDINGS.md` F-METHOD-02。AUROC 不受影响；recall@FPR/F1 存在轻微乐观偏差。

---

## 3. 优先级路线图

| 优先级 | 项目 | 涉及文件 | 工作量 | 影响 | 状态 |
|---|---|---|---|---|---|
| **P0** | 修正 6 处 Mermaid 图 EfficientAD INT8 → FP16 | ARCHITECTURE.md, edge_deployment_summary.md | 30 min | 高 | **已完成** |
| **P0** | 修正 4 处图表队列容量（cap=2 → Q1=4,Q2=2,Q3=4） | ARCHITECTURE.md, edge_deployment_summary.md | 20 min | 高 | **已完成** |
| **P0** | 修正 Beat Sweep 图题（甜蜜点 → 推荐/边界） | edge_deployment_summary.md:435 | 5 min | 中 | **已完成** |
| **P0** | 修正 T2→Q2 连线标签（anomaly+mask → frame+score） | ARCHITECTURE.md:79, edge_deployment_summary.md:84 | 5 min | 中 | **已完成** |
| **P0** | 创建 README.md | 根目录 | 1-2 hr | 高 | **已完成** |
| **P1** | config.yaml 默认值 4B → 2B | edge/config.yaml:12 | 2 min | 低 | **已完成** |
| **P1** | Stage 2 输出标签 mask+bbox → bbox | ARCHITECTURE.md:181 | 5 min | 低 | **已完成** |
| **P1** | 表头 "RK3588 INT8 延迟" → "RK3588 延迟" | ARCHITECTURE.md:178 | 5 min | 低 | **已完成** |
| **P1** | 性能表 map_mean → raw_score 注释 + ASCII 图 T3 标签 | ARCHITECTURE.md:527, :438 | 10 min | 低 | **已完成**（CLAUDE_02） |
| **P1** | 实现 4B spatial merge（2x2 permute） | qwen3vl_runner.cpp | 2-4 hr | 中高 | 待处理（CLAUDE_04） |
| **P1** | 增加实时队列深度 / 高水位线指标 | edge 代码 | 2-3 hr | 中 | 待处理（CLAUDE_04） |
| **P1** | API Contract schema 自动化 + CI + 跨端类型同步 | scripts/, tests/, .github/ | 3-4 hr | 中高 | **已完成**（CLAUDE_03） → `phase9_contract_ci_hardening.md` |
| **P2** | Threshold soak test（30 分钟以上） | 板端硬件 | 1 hr 运行时间 | 中 | 待处理（CLAUDE_05） |
| **P2** | FastSAM mask decode（可选 v1.3 contract） | fastsam_worker.cpp + contract | 4-6 hr | 低 | 待处理 |

---

## 4. 本次审计修改的文件

1. `docs/ARCHITECTURE.md` — 行 74, 77, 79, 82, 141, 147, 154, 165, 178, 180, 181（CLAUDE_01 工作树已修正）; 行 438, 527（CLAUDE_02 doc consistency patch）
2. `docs/reports/edge_deployment_summary.md` — 行 78-82, 84, 87, 261, 267, 274, 285, 435（CLAUDE_01 工作树已修正）
3. `edge/config.yaml` — 行 12：vlm_model_size "4B" → "2B"（CLAUDE_01）
4. `README.md` — 新建（CLAUDE_01）
5. `docs/experiments/phase9_repo_audit.md` — 本文件（CLAUDE_01 + CLAUDE_02 更新修复状态）
6. `docs/experiments/phase9_doc_consistency_patch.md` — CLAUDE_02 执行报告（新建）
7. `docs/experiments/phase9_contract_ci_hardening.md` — CLAUDE_03 执行报告（新建）
8. `scripts/export_contract_schema.py` — JSON Schema 导出（新建）
9. `scripts/check_contract_drift.py` — Schema 漂移检测（新建）
10. `scripts/validate_contract.py` — 单文件 contract 校验（新建）
11. `docs/schema/*.v1.2.schema.json` — 6 个 schema 文件（新建）
12. `backend/tests/contract/fixtures/*.json` — 9 个 fixture 文件（新建）
13. `backend/tests/contract/test_contract_fixtures.py` — fixture 验证测试（新建）
14. `backend/tests/contract/test_post_report_extended.py` — 扩展验证测试（新建）
15. `backend/tests/contract/test_golden_alignment.py` — golden sample 对齐测试（新建）
16. `.github/workflows/contract.yml` — GitHub Actions CI（新建）
17. `Makefile` — 本地 CI 快捷命令（新建）
18. `frontend/src/types/defect.ts` — +MvtecCategory, +Severity 类型（修改）
19. `frontend/src/lib/mock-data.ts` — category 类型对齐（修改）
20. `frontend/package.json` — +typecheck script（修改）

---

## 5. 已确认无需修改的项

- `docs/ENGINEERING_FINDINGS.md` — 准确记录了 Phase 7/8 所有发现（含 F-VLM-04、F-VLM-06）
- `docs/API_CONTRACT.md` v1.2 — 与代码一致
- `edge/config.yaml` 类别级阈值 — Phase 8A-Fix-Fix 校准值
- `edge/src/vlm/qwen3vl_runner.cpp` — spatial merge 检测逻辑正确（修复路径已知但排列未实现）
- Phase 7 实验报告（phase7_edge_pipeline_report.md, phase7_prompt2e, phase7_prompt2f）— map_mean 引用为历史准确记录，Phase 8 已说明切换原因
- Phase 8 实验报告（phase8_execution_report.md）— 内部自洽，正确区分 pass_all vs threshold、PC vs Board
- 后端 Pydantic schema — 与 contract 一致
- 前端 TypeScript 类型 — 与 contract 一致
- 前端源码（app/, components/, lib/, types/）— 无夸大 defect_type 分类、无 INT8 部署、无 mask 完成等误导表述
- `docs/PROJECT_TIMELINE.md` — 队列容量引用正确，W8A8 LoRA 坍塌描述准确
- `docs/reports/edge_deployment_summary.md` — threshold 推算明确标注 "推算不是实测"，FastSAM 明确标注 "bbox proposal"，前端截图明确标注 "Phase 4 模拟器数据驱动"
- `README.md` — 所有叙事守卫已落实（T2=load shedding gate, LoRA=W8A8 collapse, threshold=inferred, mask=TODO）
- 后端 contract tests 从 31 扩展到 74，覆盖全 15 类 category、extra field 拒绝、negative bbox、trace_events WS round-trip
- JSON Schema 快照已生成并可自动检测漂移
- 前端 TypeScript 类型已对齐（MvtecCategory union type、Severity type）
- CI workflow 和 Makefile 已建立

---

## 6. 后续工作（延后至后续文档）

| 文档 | 范围 | 状态 |
|---|---|---|
| `CLAUDE_02_DOC_CONSISTENCY_AND_REPORT_PATCH.md` | 实验报告中剩余文档不一致项深度扫描 | **已完成** → `phase9_doc_consistency_patch.md` |
| `CLAUDE_03_API_CONTRACT_AND_CI_HARDENING.md` | Contract schema 自动化、CI 检查、跨端类型同步 | **已完成** → `phase9_contract_ci_hardening.md` |
| `CLAUDE_04_EDGE_RUNTIME_AND_MODEL_FIXES.md` | 4B spatial merge 修复、队列指标、JSON watchdog | 待开始 |
| `CLAUDE_05_EXPERIMENT_VALIDATION_AND_RELEASE_GATES.md` | Threshold soak test、4B 修复后复测、校准集分离 | 待开始 |
| `CLAUDE_06_FRONTEND_DEMO_TRUTHFULNESS_GUARDRAILS.md` | 前端 mock/real 标识、AB matrix 口径控制 | 待开始 |
