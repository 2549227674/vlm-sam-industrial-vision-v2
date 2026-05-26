# phase10_localization_refactor_review_and_final_plan.md

> 复审对象：`Phase 10 Localization Refactor Discussion — vlm-sam-industrial-vision-v2` 以及用户上传的本地仓库 zip。  
> 复审方式：优先读取本地上传仓库，不把 GitHub 仓库首页当普通网页反复访问。  
> 结论分级：文中用 **[Repo]** 表示来自上传仓库文件，**[Claude]** 表示来自待复审 Claude 文档，**[Review]** 表示本次独立评审推理与建议。

---

## 1. Executive Summary

Phase 10 应该停止把 FastSAM/VLM/EfficientAD heatmap 包装成“真实缺陷定位”。当前系统已经很好地证明了 RK3588 工程闭环、队列、量化排障、API、Dashboard 和可观测性，但 Phase 9 的 bbox 与 defect_type 链路在技术上不适合继续作为主定位方案。

我的最终建议是：

1. **新增一个轻量 supervised localizer，第一版用 YOLOv8n-detect。**  
   用 MVTec `ground_truth` mask 转 bbox 训练一个 category-specific / defect-specific detector。bbox 和 `defect_type` 都由 localizer 输出，不再由 VLM 输出。YOLOv8n-detect 是 Phase 10 最合适的第一落点：数据准备低、RKNN 后处理相对简单、C++ 集成可控、延迟相对 VLM 几乎不是瓶颈。

2. **EfficientAD-S 保留，但只作为 gate / score / diagnostic。**  
   Phase 9 已经证明 EfficientAD `raw_anomaly_map` 对 capsule、cable 的部分 defect 有一定定位能力，但对 carpet、metal_nut、pill、screw 等不可靠；因此它不能继续承担 user-visible localization。它仍可作为 T2 load-shedding gate、anomaly score 和 heatmap debug。

3. **FastSAM 从主链路删除或默认禁用，降级为 debug proposal。**  
   仓库代码明确显示 FastSAM mask prototype decode 仍未完成，主链路实际上是 bbox proposal。Phase 9 前端也已把 bbox 标注为 proposal-level。它可以保留在调试页，用于展示“object/saliency proposal vs defect localization”的差异，但不应再进入主结果。

4. **Qwen3-VL 2B W8A8 不再输出 bbox，也不再输出 closed-set `defect_type`。**  
   仓库文档记录 PC bf16 LoRA 对 defect type 有效果，但 RK3588 W8A8 LoRA defect_type 精确率塌缩到 0%。这不是 prompt 小修能解决的主线问题。VLM 应改为 observation / severity_reason / explanation 生成器，最好异步执行；7 天 demo 版甚至可以先用模板替代。

5. **类别选择：我同意 Claude 的 3 类方向，但不同意 7 天内直接压满 17 类作为第一版验收。**  
   最推荐 3 类组合是 **`metal_nut + cable + capsule`**，不推荐把 `wood` 放进第一版。最推荐 2 类快速 demo 是 **`metal_nut + cable`**；若目标偏小目标严谨评估，可用 **`metal_nut + capsule`**。Claude 的 `metal_nut + capsule + cable` 是合理的最终 3 类组合，但需要分阶段引入。

6. **必须诚实表述：这是 supervised proof-of-concept，不是标准 MVTec unsupervised benchmark。**  
   如果使用 MVTec `test/ground_truth` 训练 localizer，就不能再把结果和 PatchCore / EfficientAD / PaDiM 的标准 MVTec AD 指标并列比较。README、Dashboard、demo manifest 和实验文档都必须明确这个口径。

最小推荐架构：

```text
T1 Capture
T2 EfficientAD-S FP16 gate / score / diagnostic, optional for benchmark mode
T3 YOLOv8n-detect RKNN localizer, primary bbox + defect_type + confidence
T4 Observation enrichment, template first, edge/cloud VLM async later
T5 Upload through API v1.3
T6 Frontend overlay: model bbox / debug proposal / GT reference clearly separated
```

---

## 2. Review of Claude's Proposal

### 2.1 我同意的建议

**同意 1：停止把 EAD heatmap 或 FastSAM proposal 当 user-visible localization。**  
**依据：[Repo] + [Claude]。** 仓库 `docs/ENGINEERING_FINDINGS.md` 的 F-EAD-05 明确记录：EAD bbox 在 6 个类别中只有 capsule mean IoU≈0.24、cable≈0.22 勉强可用，carpet≈0.0006、metal_nut≈0.01、pill≈0.04、screw≈0.009 基本失败；该文件还要求 public demo 把 bbox overlay 标注为 proposal-level。`docs/experiments/phase9_ead_localization_reliability.md` 的 per-category 表和结论也支持这一点。Claude 把 EAD/FastSAM 从主定位信号降级，是正确方向。

**同意 2：引入 supervised localizer。**  
**依据：[Review]。** 当前失败不是后处理阈值或 prompt 能解决的，而是模型任务错配：FastSAM 是 class-agnostic object/saliency proposal，VLM 是语言/视觉理解模型，不是可靠坐标回归器，EAD 是 image-level anomaly/gate 模型。真正要证明“缺陷定位”，需要一个以 bbox 或 mask 为监督目标的 localizer。

**同意 3：VLM 不再承担 bbox 与 closed-set `defect_type`。**  
**依据：[Repo]。** `docs/ENGINEERING_FINDINGS.md` F-VLM-04 记录 PC bf16 LoRA `defect_type_exact` 可到 51.8%，但 RK3588 W8A8 LoRA 为 0%；`docs/reports/edge_deployment_summary.md` 也记录 board 2B base 与 2B LoRA defect_type 均为 0/7。`edge/src/vlm/qwen3vl_runner.cpp` 当前 prompt 仍要求 VLM 输出 category、defect_type、severity、confidence、bboxes、description，这正是 Phase 10 需要拆掉的责任混合。

**同意 4：几何真值只能来自 MVTec GT mask 或人工标注，不能来自 cloud VLM。**  
**依据：[Review]。** Cloud VLM 可以生成语言描述、QA、severity_reason，但不能作为 geometry label 的来源。训练 localizer 的 bbox/mask 必须来自 `ground_truth` mask 转换或人工 gold set。

**同意 5：FastSAM 从主链路删除或降级。**  
**依据：[Repo]。** `edge/src/pipeline/fastsam_worker.cpp` 明确写到 output1 prototype masks are not decoded / mask decode deferred；代码实际使用 detection proposal + fallback + VLM bbox fusion。`frontend/src/components/v4/FrameInspector.tsx` tooltip 已写 “Proposal bbox from FastSAM/VLM. Not verified ground-truth localization.” 这说明项目自身已经承认 FastSAM/VLM bbox 不是可靠定位。

**同意 6：必须在 README / Dashboard 诚实说明训练口径。**  
**依据：[Repo] + [Review]。** 现有 README 已经有不少诚实 caveat；Phase 10 如果用 MVTec `test/ground_truth` 训练 localizer，必须进一步明确“supervised proof-of-concept, not standard MVTec AD benchmark”。

### 2.2 Claude 方案可能过度复杂的地方

1. **第一阶段直接做 3 类 17 个 defect type，风险偏高。**  
   `metal_nut + capsule + cable` 是合理终局，但 7 天 demo 同时处理 17 类、YOLO 训练、ONNX/RKNN、C++ 后处理、API v1.3、前端 overlay、文档诚实口径，容易变成 scope creep。建议 7 天 demo 先做 `metal_nut + cable`，第三类 `capsule` 作为扩展阈值。

2. **同时引入 edge VLM observation 和 cloud enrichment，容易遮蔽核心目标。**  
   Phase 10 的主目标是“定位效果明显改善”。VLM observation 可以做，但 7 天内最好先用模板生成 observation，避免 VLM 延迟、prompt、JSON fallback 和 cloud source 标注把主线复杂化。

3. **过早讨论 YOLOv8n-seg / U-Net 作为并行路线会分散资源。**  
   可以保留 mask 数据转换脚本，但第一版不要同时实现 detect、seg、U-Net 三条链路。先用 YOLOv8n-detect 建立端到端可信闭环，再决定是否上 segmentation。

4. **用大量外部 RKNN benchmark 数字支撑判断，但本次复审没有在线核验这些数字。**  
   本次评审不把 GitHub/网页作为主要访问方式，因此 Claude 文档中关于外部论文、社区 FPS、Roboflow/AIMultiple 等说法只能作为背景，不作为本报告的强证据。这里的核心决策主要基于仓库现状和工程可行性。

### 2.3 Scope creep 风险

高风险项：

- 同时做 3 类 17 defect types。
- 同时支持 bbox、mask、GT reference、proposal、cloud enrichment、edge VLM async。
- 同时改 API v2、数据库 schema、前端所有卡片、C++ pipeline、训练脚本。
- 继续维护 FastSAM 主链路兼容，同时又新增 YOLO localizer。
- 继续尝试 LoRA / SFT 在 W8A8 上恢复 exact defect_type。

Scope 控制建议：

- 7 天 demo 只验收 **YOLO bbox + YOLO class + dashboard overlay + honesty docs**。
- VLM 在 7 天 demo 只做模板或异步可选，不作为验收阻塞项。
- FastSAM 默认关闭，只允许 debug profile 打开。
- API v1.3 只加最少字段，不做 v2 大重构。

### 2.4 RK3588 上不现实或不应押注的建议

1. **继续押注板端 LoRA 解决 fine-grained defect_type。**  
   仓库已有结论：W8A8 量化会破坏 LoRA delta；RK3588 LLM runtime 主线只有 W8A8。Phase 10 不应继续把这个作为主路径。

2. **让 VLM 做坐标回归。**  
   现有 `parse_vlm_bboxes` 只是把 pixel-like 坐标尽量归一化并 clamp 单个字段，不能保证 `x+w<=1`、`y+h<=1`。API route 又会拒绝越界 bbox，Phase 9 soak 中已经出现 HTTP 400。坐标必须来自 localizer 后处理，而不是语言模型。

3. **第一版上 YOLOv8n-seg 或 U-Net 并要求完整 RKNN C++ mask 后处理。**  
   不是绝对不可行，但相对 YOLO detect 增加 mask decode、connected component、mask API、前端透明 overlay、性能验证等工作。Phase 10 v1 不应把它作为必选。

4. **把 FastSAM 继续作为 defect localizer。**  
   它本质上输出显著对象/区域 proposal；对 metal_nut 案例很容易框住整个螺母。缺陷局部化不应再依赖它。

### 2.5 对作品集最有价值的建议

优先级最高：

1. **从“工程闭环”升级到“有监督、可复现、可量化的缺陷定位闭环”。**
2. **清晰解释为什么 Phase 9 的 bbox 失败，以及如何用 Phase 10 修正模型职责。**
3. **在前端把 model bbox、debug proposal、GT reference 明确区分。**
4. **提供 mini-benchmark 表：per-class AP、bbox IoU、ONNX→RKNN delta、RK3588 latency、HTTP 400=0。**
5. **README 里坦诚说 supervised proof-of-concept，不冒充标准 MVTec benchmark。**

### 2.6 关于 `metal_nut + capsule + cable`

我**部分同意** Claude 推荐。

- **同意作为最终 3 类组合：** `metal_nut + cable + capsule` 比 `metal_nut + cable + wood` 更合理。它覆盖刚性件、线束结构件和小目标医疗/胶囊表面缺陷，作品集叙事清楚，也能显示 localizer 对不同缺陷尺度的能力。
- **不同意作为 7 天第一版的硬目标：** 3 类 17 defect types 容易拖慢训练、评估、RKNN 和前端集成。7 天 demo 建议先做 `metal_nut + cable`；若 Day 3 PC 指标达标，再把 capsule 加入扩展训练。
- **不推荐第一版上 wood：** wood 属于纹理背景，color/liquid/scratch 与木纹混杂，bbox 检测可解释性弱，容易出现“看起来像在框木纹”的 demo 观感。它更适合作为后续 challenge category，而不是第一版作品主角。

### 2.7 关于 YOLOv8n-detect vs YOLOv8n-seg / U-Net

我同意 Claude 推荐 **YOLOv8n-detect 作为第一版主 localizer**，但理由要收敛得更工程化：

- 当前项目的前端、API、C++ 后处理都已经以 bbox 为核心，YOLO detect 集成成本最低。
- YOLO detect 的输出可以直接承担 `bboxes`、`defect_type`、`confidence`，减少 API 语义混乱。
- Segmentation 的展示更漂亮，但第一版需要额外解决 mask decode、mask API、前端 mask overlay、RKNN 后处理和延迟评估；这些不是 7 天内的核心风险最小路线。
- U-Net 更符合 GT mask，但会引入 per-pixel multi-class / binary mask、连通域、类别映射和多实例分离问题；它适合作为 Phase 10.2 或 wood/capsule tiny-defect 专项，不适合作为 Phase 10 v1。

---

## 3. Repository Access Notes

### 3.1 访问方式

- 使用用户上传的本地仓库 zip：`/mnt/data/vlm-sam-industrial-vision-v2-main.zip`。
- 解压后读取本地路径：`/mnt/data/repo/vlm-sam-industrial-vision-v2-main`。
- 没有把 GitHub 仓库 URL 当普通网页反复打开。
- 因为本地 zip 可用，所以本报告不是“只读 Claude 文档”的 limited review，而是 **基于本地仓库快照 + Claude 文档的复审**。

### 3.2 已读取的关键仓库文件

已重点读取：

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/ENGINEERING_FINDINGS.md`
- `docs/reports/edge_deployment_summary.md`
- `docs/experiments/phase8_execution_report.md`
- `docs/experiments/phase8b_vlm_ab_plan.md`
- `docs/experiments/phase9_ead_localization_reliability.md`
- `docs/experiments/phase9_experiment_validation_release_gates.md`
- `edge/src/pipeline/ead_worker.cpp`
- `edge/src/pipeline/fastsam_worker.cpp`
- `edge/src/vlm/qwen3vl_runner.cpp`
- `edge/include/edge/common/types.hpp`
- `backend/app/schemas/defect.py`
- `frontend/src/lib/data-source.ts`
- `frontend/src/components/v4/FrameInspector.tsx`
- `frontend/src/components/v4/CaveatBanner.tsx`
- `frontend/public/demo-data/real_run_latest/manifest.json`
- `frontend/public/demo-data/real_run_latest/defects_snapshot.json`
- `frontend/public/demo-data/real_run_latest/localization_annotations.json`
- `scripts/mvtec_mask_to_json.py`
- `scripts/split_lora_data.py`
- `scripts/format_llama_factory_data.py`
- `scripts/eval_ab_test.py`

### 3.3 未在 zip 中找到的请求文件

在上传的仓库快照中没有找到以下用户列出的文件或通配结果：

- `docs/experiments/claude08_curated_real_demo_snapshot_plan*.md`
- `docs/experiments/CLAUDE_07_EAD_BBOX_LOCALIZATION*.md`

因此本报告没有编造这些文件内容。相关结论改由以下文件支撑：

- `docs/experiments/phase9_ead_localization_reliability.md`
- `docs/experiments/phase9_experiment_validation_release_gates.md`
- `frontend/public/demo-data/real_run_latest/manifest.json`
- `frontend/public/demo-data/real_run_latest/localization_annotations.json`

### 3.4 关键仓库证据摘要

- **当前主线架构。** README 记录当前主线是 EfficientAD-S FP16 raw RKNN → FastSAM FP16/no-quant bbox proposal → Qwen3-VL-2B base W8A8 → FastAPI → Dashboard。
- **EAD 只是 gate，不是 reliable localizer。** `docs/ENGINEERING_FINDINGS.md` F-EAD-05 和 `phase9_ead_localization_reliability.md` 都说明 EAD heatmap localization 只能在少数类别/缺陷上勉强有效。
- **FastSAM mask decode 未完成。** `fastsam_worker.cpp` 中 output1 prototype masks not decoded，mask decode deferred；实际主链路输出 bbox proposal。
- **VLM 当前 prompt 仍要求输出 bbox 和 defect_type。** `qwen3vl_runner.cpp` prompt 明确要求 JSON 包含 category、defect_type、severity、confidence、bboxes、description。
- **W8A8 LoRA closed-set classification 塌缩。** 文档记录 PC bf16 LoRA 有提升，但 RK3588 W8A8 defect_type 精确率为 0%。
- **API v1.2 对 bbox 越界有硬校验。** `docs/API_CONTRACT.md` 说明 route layer 校验 `x+w<=1`、`y+h<=1`，否则 400。
- **前端已经诚实标注 proposal-level bbox。** `FrameInspector.tsx` tooltip 写明 FastSAM/VLM bbox 不是 GT localization。
- **真实 demo snapshot 是 curated showcase。** `manifest.json` 标明 `snapshot_type=curated_real_showcase`、records=11、不是完整 benchmark；`defects_snapshot.json` 中 11 条里 9 条 `defect_type` 是 `anomaly`；`localization_annotations.json` 中 11 条 `localization_source` 都是 `fastsam_vlm_proposal`，其中 7 条 bbox_visual=good，4 条 miss。

---

## 4. Current Pipeline Failure Analysis

### 4.1 EfficientAD-S

**当前适合做什么：**

- image-level anomaly score
- load-shedding gate
- good/defect thresholding aid
- heatmap diagnostic
- trace/debug signal

**当前不适合做什么：**

- primary defect bbox localizer
- user-visible precise localization
- per-defect-type classifier

**证据与解释：**

`phase9_ead_localization_reliability.md` 使用板端 EfficientAD-S FP16/no-quant RKNN，对 MVTec test split 每个 defect type 取样，用 GT mask bbox 算 IoU。结果显示：capsule mean IoU≈0.2425、cable≈0.2186 勉强有可用片段；carpet≈0.0006、metal_nut≈0.0103、pill≈0.0419、screw≈0.0091 基本失败。文档结论已经写明：EAD bbox cannot serve as global primary localization。

**Phase 10 处置：保留，但降级为 gate / score / diagnostic。**

- 默认作为 T2 gate 放在 YOLO localizer 前，用于减少流入后续重链路的帧数。
- 在 benchmark 模式可关闭 gate，让 YOLO 跑完整测试集，避免 gate 误杀影响 localizer 指标。
- 前端可显示 EAD heatmap/score，但必须标注为 diagnostic，不与 model bbox 混淆。

### 4.2 FastSAM

**当前实际角色：** object/saliency proposal，不是 defect localizer。

**为什么会框住整个 metal_nut / capsule / cable：**

FastSAM 是 class-agnostic proposal 模型，它倾向于分割显著对象或大区域。在 metal_nut 上，最显著对象是螺母本体，不是 scratch/color/bent 的局部缺陷。当前代码又没有完成 mask decode，主要输出 detection bbox proposal，这会进一步把主物体框当作缺陷框。

**仓库证据：**

- `fastsam_worker.cpp` 中 output1 prototype masks are not decoded，mask decode deferred。
- `FrameInspector.tsx` tooltip 已把 overlay 标为 FastSAM/VLM proposal，不是 verified GT localization。
- real_run_latest 的 `localization_annotations.json` 中所有 11 条 `localization_source` 都是 `fastsam_vlm_proposal`，且有 4 条 `bbox_visual=miss`。

**Phase 10 处置：从主 pipeline 删除或默认禁用。**

保留价值只剩：

- debug overlay
- object proposal 对照
- 历史 Phase 9 能力展示
- 失败案例教学：object proposal ≠ defect localization

不建议继续投入 FastSAM mask decode 作为 Phase 10 v1 主线；这会消耗工程时间，但仍不能保证缺陷级定位。

### 4.3 Qwen3-VL 2B base W8A8

**适合做什么：**

- 自然语言 observation
- severity_reason / explanation
- 检验员风格报告
- 对 YOLO 输出的局部框进行语言化描述
- 异步 enrichment

**不适合继续做什么：**

- bbox 坐标回归
- normalized bbox 校验责任
- closed-set MVTec `defect_type` 精确分类
- 作为实时主链路的必经重模块

**仓库证据：**

- 文档记录 PC bf16 2B LoRA defect_type 有明显提升，但 RK3588 W8A8 LoRA defect_type 为 0%。
- `qwen3vl_runner.cpp` 当前 prompt 要求输出 bbox 与 defect_type，但 fallback 经常写 `defect_type: anomaly`。
- `parse_vlm_bboxes` 虽然支持 pixel-like 坐标归一化，但只 clamp 单项字段，不能保证 `x+w<=1`；API route 会返回 HTTP 400。
- Phase 9 soak 已出现 HTTP 400 上传失败。

**Phase 10 处置：改造。**

- 取消 VLM bbox 输出。
- 取消 VLM closed-set defect_type 输出。
- VLM 输入应包含 localizer 的 bbox、class label、crop 或 overlay 图。
- VLM 输出仅限：`observation`、`severity_reason`、可选 `accepted_box_ids`。
- 推荐异步运行。7 天 demo 可直接用模板 observation，避免 VLM 阻塞主效果。

### 4.4 当前 bbox 链路

当前 bbox 来源混杂：

1. **FastSAM bbox。**  
   从检测输出 decode，再经 NMS、cleanup、fallback。实际是 proposal bbox。

2. **VLM bbox。**  
   Prompt 要求输出 normalized bbox；代码会尝试解析 pixel-like bbox 并归一化。

3. **Fusion bbox。**  
   如果 VLM bbox 与 FastSAM bbox IoU>0.3，会保守替换；否则保留 FastSAM。

4. **Fallback bbox。**  
   无候选时使用中心 placeholder bbox。

根因问题：

- bbox 不来自缺陷监督模型。
- VLM 可能输出 pixel coordinate 或越界归一化坐标。
- API v1.2 route 校验 `x+w<=1`、`y+h<=1`，因此越界会造成 HTTP 400。
- `defect_type`、`confidence`、`bbox` 语义混在 VLM/FastSAM/EAD 之间，前端无法明确哪个字段是主模型定位。

Phase 10 应把 `report.bboxes` 重新定义为 **primary model localization**。FastSAM/VLM proposal 必须移到 debug 字段，例如：

```json
{
  "localization_source": "yolov8n_detect_rknn",
  "geometry_source": "model",
  "defect_bboxes": [...],
  "object_proposals": [...],
  "gt_reference_bboxes": [...],
  "debug_overlays": {...}
}
```

为了兼容旧前端，可以 v1.3 里继续保留 `bboxes`，但语义改为 primary localizer bbox；proposal 类输出不得继续塞进同一字段。

### 4.5 一个必须修的评估坐标风险

仓库里存在一个值得优先修正的坐标语义风险：

- `scripts/mvtec_mask_to_json.py` 从 mask contour 生成的是 **top-left xywh normalized bbox**。
- API、前端 overlay、FastSAM decode 也都按 top-left xywh 使用。
- 但 `scripts/eval_ab_test.py` 的 `compute_iou` 注释和实现把 bbox 当作 **center xywh**，先转成 `cx-w/2`。

这会污染或扭曲历史 VLM bbox IoU 评估。Phase 10 在训练和评估前必须统一：

- YOLO label 文件使用 center xywh。
- API/前端 payload 使用 top-left xywh。
- evaluator 明确输入格式，禁止混用。
- 所有转换函数命名为 `xywh_top_left_to_xyxy`、`xywh_center_to_xyxy`，不要再用模糊的 `xywh_to_xyxy`。

---

## 5. Category Selection Review

### 5.1 总体选择原则

Phase 10 的类别不是挑几个好看的 defect type，而是选择 2–3 个完整 MVTec category，并覆盖每个 category 下全部 defect types。

选择标准：

- GT mask 是否清晰。
- 缺陷是否适合 bbox detection。
- 小目标/细长缺陷比例是否可控。
- 类别内部形态是否稳定。
- 是否适合 RK3588 轻量 localizer。
- Dashboard 展示是否容易让人理解。
- 是否适合 mini-benchmark。
- VLM 是否容易生成自然语言 observation。
- 数据泄漏口径是否能诚实解释。

### 5.2 Category 对比表

| Category | 完整 defect types | GT mask 清晰度 | 小目标/细长缺陷 | bbox vs seg | RK3588 部署友好度 | Demo 表现 | Mini-benchmark 价值 | VLM 描述难度 | 过拟合/泄漏风险 | 是否第一版推荐 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| `metal_nut` | `bent`, `color`, `flip`, `scratch` | 高，多数边界清楚 | 中，scratch 较细；flip 偏全局/姿态 | bbox 可做；flip 需解释为 object-level defect | 高：刚性、背景稳定 | 高：金属件工业感强 | 高：少类别但多形态 | 易 | 中：样本少但形态稳定 | **强烈推荐第一类** |
| `wood` | `color`, `combined`, `hole`, `liquid`, `scratch` | 中；纹理/液体/颜色可能扩散 | 中到高；scratch 细，color/liquid diffuse | 更偏 segmentation；bbox 可解释性弱 | 中低：纹理背景易过拟合 | 中低：框木纹观感差 | 中：可作为挑战类 | 中：可描述但容易泛化 | 高：木纹/颜色易记忆 | **不推荐第一版** |
| `cable` | `bent_wire`, `cable_swap`, `combined`, `cut_inner_insulation`, `cut_outer_insulation`, `missing_cable`, `missing_wire`, `poke_insulation` | 中高；结构型缺陷多 | 中高；线缆细长、多组件 | bbox 可做；seg 对细长/多组件更好 | 中：类别多、形态变 | 高：线束场景直观 | 高：8 类更有说服力 | 易 | 中高：每类样本少 | **推荐第二类** |
| `capsule` | `crack`, `faulty_imprint`, `poke`, `scratch`, `squeeze` | 高，但 tiny defect 多 | 高：crack/scratch/poke 小且细 | bbox 可做但 stress 较大；seg 更漂亮 | 中：小目标可能要求高分辨率 | 高：医药质检感强 | 高：小目标压力测试 | 中高：容易描述 | 中高：小样本小目标 | **推荐第三类/严谨版** |

### 5.3 metal_nut

**优点：**

- 刚性物体，姿态/背景相对稳定。
- `bent`、`scratch`、`color` 都容易让人理解。
- 工业零件 demo 观感强。
- EAD heatmap 在 metal_nut 上失败，不影响 supervised localizer；反而能说明 Phase 10 的改进是模型职责重构，不是调阈值。

**风险：**

- `flip` 更像全局姿态/装配错误，不是局部缺陷。GT mask 可能覆盖较大区域或对象级区域；前端必须把它称为 “object-level pose/flip anomaly”，不要假装它是局部 scratch。
- 金属反光和颜色缺陷可能导致过拟合。

**结论：** 第一版必须选。

### 5.4 wood

**优点：**

- 纹理场景有挑战性。
- `hole`、`scratch`、`liquid` 在部分样例上视觉明显。

**问题：**

- wood 是纹理类，容易重蹈 carpet 的问题：背景纹理本身复杂，bbox 框出来不一定有说服力。
- `color`、`liquid`、`combined` 可能是 diffuse mask，bbox 会覆盖较大纹理区，Dashboard 上不一定像“精准定位”。
- 对 YOLO detect 而言，缺陷的边界和类别语义比 metal_nut/cable 弱。

**结论：** 不推荐 Phase 10 第一版。后续如果要证明泛化到纹理类，可以在 YOLO detect 稳定后，用 U-Net/segmentation 专项处理 wood。

### 5.5 cable

**优点：**

- 线束质检场景很工业，作品集价值高。
- `cut_outer_insulation`、`cut_inner_insulation`、`missing_wire`、`missing_cable`、`cable_swap` 等 defect type 与实际质检语义接近。
- 包含局部 cut、缺失、交换、弯曲等多种异常，mini-benchmark 有说服力。

**风险：**

- 8 个 defect type，单类样本少，类别不均衡明显。
- `bent_wire`、`cable_swap` 等有语义/结构属性，bbox 不一定能完全表达。
- 细长、多组件缺陷可能需要多个 bbox 或更适合 mask。

**结论：** 推荐作为第二类。它比 capsule 更复杂，但 demo 叙事强；7 天 demo 如果只选 2 类，建议 `metal_nut + cable`。

### 5.6 capsule

**优点：**

- 医药/胶囊质检叙事很清楚。
- `squeeze`、`faulty_imprint` 等容易描述。
- 对小目标裂纹、划痕、压痕有挑战，适合严谨 mini-benchmark。

**风险：**

- `crack`、`scratch`、`poke` 可能非常小，YOLOv8n 640 输入可能 AP 低，需要 768/1024、多尺度、copy-paste 或 tiling。
- 仓库 `scripts/mvtec_mask_to_json.py` 的中文 defect mapping 中没有完整覆盖 capsule 的 `poke`，Phase 10 如果选 capsule，必须先修映射表。

**结论：** 推荐作为第三类，或作为严谨 mini-benchmark 的小目标压力测试。7 天第一版不建议和 cable 同时压满，除非 PC baseline 很快达标。

### 5.7 推荐组合

**最推荐 2 类组合：`metal_nut + cable`。**

- 偏 demo 和作品集。
- 工业叙事强：金属零件 + 线束。
- bbox detection 够直观。
- 缺陷类型覆盖 4+8=12 类，已足够证明不是 cherry-pick defect type。

**严谨 mini-benchmark 2 类替代：`metal_nut + capsule`。**

- 覆盖刚性件 + 小目标表面缺陷。
- 类别数较少，便于 per-class 指标做扎实。
- 缺点是线束工业故事少一些。

**最推荐 3 类组合：`metal_nut + cable + capsule`。**

- 我同意 Claude 的最终 3 类组合。
- 但建议分阶段：先 2 类过端到端验收，再加 capsule。

**不推荐第一版：`wood`。**

- 纹理和 diffuse defect 增大 bbox demo 风险。
- 更适合作为 Phase 10.2 segmentation/challenge 类别。

**demo 优先组合：`metal_nut + cable`。**

**mini-benchmark 优先组合：`metal_nut + cable + capsule`，若时间不足则 `metal_nut + capsule`。**

---

## 6. Localizer Architecture Decision

### 6.1 方案对比表

| 方案 | 数据准备成本 | 训练成本 | 标注来源 | RKNN 导出难度 | C++ 后处理难度 | RK3588 延迟 | 可视化效果 | 细长缺陷适应性 | 多实例/多组件适应性 | 作品集说服力 | 主要风险 | 推荐程度 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| A. YOLOv8n-detect | 低：mask→bbox | 低 | MVTec GT mask / 人工 bbox | 低到中 | 中：decode+NMS+坐标转换 | 低，相对 VLM 可忽略 | 中高：bbox 清楚 | 中：细线会框粗 | 中：可多 bbox | 高 | 小目标 AP、类别不均衡、坐标格式 | **主推荐** |
| B. YOLOv8n-seg | 中：mask polygon/bitmap | 中 | MVTec GT mask | 中 | 高：proto mask decode/crop/resize | 中 | 高：mask 漂亮 | 高 | 中高 | 高 | RKNN/CPU mask 后处理、API/前端复杂 | 第二阶段备选 |
| C. U-Net-small / MobileNet-UNet | 中 | 中 | MVTec GT mask | 中到高 | 中高：argmax/threshold/CC | 中 | 高：pixel mask | 高 | 中：实例分离需后处理 | 中高 | 多类别/多实例/导出维护 | 延后研究 |
| D. EAD heatmap postprocess | 低 | 无 | 无监督/good train | 已部署 | 低 | 0 额外 | 低到中 | 低 | 低 | 中：展示诊断价值 | 已验证不稳定 | debug/gate only |
| E. FastSAM proposal | 无到低 | 无 | 无监督 proposal | 已部署 FP16 | 中 | 中 | 中：对象框显眼 | 低 | 中 | 中：可解释失败 | 框对象不框缺陷，mask decode 未完成 | debug only |
| F. VLM bbox | 低 | 高/不可控 | 文本/伪标签 | 已部署 W8A8 | 低 | 高，秒级 | 低 | 低 | 低 | 低 | 坐标错位、HTTP 400、不可复现 | **删除** |

### 6.2 最终推荐

**Phase 10 v1：YOLOv8n-detect。**

原因：

1. 与当前 API/前端 bbox 模型最兼容。
2. 训练数据可直接从 MVTec GT mask 生成。
3. 输出同时覆盖 bbox、class id、confidence。
4. C++ 后处理和 RKNN 验证复杂度最低。
5. 能在 7 天内把“看起来很差的定位”变成“可解释、可量化、可复现的定位”。

**Phase 10.2：YOLOv8n-seg 或轻量 U-Net。**

触发条件：

- YOLOv8n-detect 对 capsule crack/scratch、cable thin wire 缺陷 AP 明显不够。
- 前端需要 mask 而不是 bbox 才能说服观众。
- 已经完成 detect 主链路和 v1.3 API，不再有基础工程债。

**不再推荐：EAD/FastSAM/VLM 作为主 localization。**

它们可以作为 score/proposal/observation，但不应拥有最终几何真值地位。

---

## 7. Dataset and Labeling Strategy

### 7.1 是否继续使用 MVTec 目录名作为 VLM 输出的 `defect_type`？

不应该。

MVTec 目录名适合作为：

- hidden evaluation label
- YOLO class id 的来源
- dataset manifest 中的 canonical label
- 后端筛选和 benchmark 分组字段

不适合作为：

- RK3588 W8A8 VLM 必须精确输出的字符串
- 面向用户的一线展示文案
- Cloud VLM 可自由生成的标签

原因：

- 目录名如 `cut_outer_insulation`、`faulty_imprint`、`bent_wire`、`improper_labeling` 是数据集内部 label，不是自然语言观察。
- 当前 VLM 在板端已经证明无法可靠输出 exact defect_type。
- `color`、`combined`、`scratch` 等 label 在不同 category 中语义不同，强迫 VLM 输出 exact label 会引入不必要失败。

### 7.2 是否把 MVTec 目录名作为 hidden evaluation label？

是。

建议字段：

```json
{
  "canonical_label": "cable/cut_outer_insulation",
  "category": "cable",
  "defect_type": "cut_outer_insulation",
  "defect_family": "insulation_damage",
  "display_name_zh": "外层绝缘切伤"
}
```

其中：

- `canonical_label` 用于训练和评估。
- `defect_type` 由 YOLO class id 映射得到。
- `defect_family` 用于面向用户的稳定分组。
- `display_name_zh` / `observation` 用于前端。

### 7.3 是否引入 `defect_family` / `observation` / `severity_reason`？

是。

推荐 schema：

```json
{
  "category": "cable",
  "defect_type": "cut_outer_insulation",
  "defect_family": "insulation_damage",
  "observation": "线缆外层绝缘局部切开，缺陷位于右侧弯折区域附近。",
  "severity": "medium",
  "severity_reason": "缺陷区域较集中，可能暴露内层材料。",
  "label_source": "yolo_class_head",
  "observation_source": "template|edge_vlm|cloud_vlm|human"
}
```

### 7.4 YOLO class id 是否可以使用 `category/defect_type` flat class？

可以，且第一版推荐。

示例：

```text
0 metal_nut/bent
1 metal_nut/color
2 metal_nut/flip
3 metal_nut/scratch
4 cable/bent_wire
...
11 cable/poke_insulation
12 capsule/crack
...
16 capsule/squeeze
```

优点：

- YOLO head 简单。
- 避免跨 category 的 `scratch` / `color` 混淆。
- category 可由 class prefix 派生。
- 后端只需一张 class map。

缺点：

- 每个 class 样本少，必须做 per-class AP 和混淆矩阵。
- 后续扩到更多 category 时 class 数会膨胀。

第一版完全可接受。

### 7.5 是否从 GT mask 转 bbox？

是。Phase 10 detect 路线必须从 MVTec GT mask 转 bbox。

但要注意：这表示使用了 supervised geometry label，因此不是标准 MVTec unsupervised benchmark。

### 7.6 mask-to-bbox 规则

推荐规则：

1. 读取 `ground_truth/{defect_type}/*_mask.png`。
2. 二值化：`mask > 0`。
3. 使用 8-connected connected components 或 `cv2.findContours(..., RETR_EXTERNAL, ...)`。
4. 对每个连通域计算 `xyxy` bbox。
5. 过滤噪声：
   - 绝对面积 `< 16 px²` 或 `< 32 px²` 可先丢弃；阈值要写进 config。
   - 也可加相对面积阈值，例如 `< 0.00002 * image_area`。
6. bbox padding：
   - 默认 padding 3–5 px。
   - 或 `max(3 px, 0.02 * max(w,h))`。
   - clamp 到图像边界。
7. 多连通域：
   - 默认每个连通域一个 bbox。
   - 如果同一缺陷被 mask 切成很多碎片，可按距离/IoU 合并近邻组件。
   - 限制每图最多 K 个 bbox，例如 K=16，与 API v1.2 一致。
8. YOLO label 输出 center normalized：`class cx cy w h`。
9. API payload 输出 top-left normalized：`x y w h`。
10. 保存 debug 可视化：原图 + mask + generated bbox，人工抽查。

### 7.7 多连通域怎么处理？

默认每个连通域作为一个 instance，但需要按 defect type 做例外策略：

- `scratch` / `crack`：细长单连通域，保留单 bbox。
- `color` / `liquid`：可能有碎片，优先合并近邻碎片，避免一张图几十个小框。
- `cable_swap` / `missing_cable`：可能是结构级异常，允许较大 bbox。
- `combined`：允许多个 bbox，但 capped top-K。

所有合并规则必须写入 dataset manifest，以保证可复现。

### 7.8 小缺陷怎么过滤？

不要简单把所有小缺陷过滤掉，因为 capsule crack/poke 可能正是小缺陷。建议：

- 过滤明显 annotation noise：面积 <16 px²。
- 对 capsule/小目标类别使用更低阈值，但启用高分辨率训练或 copy-paste augmentation。
- 报告被过滤组件数量和占比。
- 每个 defect type 抽样可视化，确认没有删掉真实缺陷。

### 7.9 如果使用 MVTec test GT 训练，如何诚实说明？

README、Dashboard、报告必须写：

> Phase 10 localizer is a supervised proof-of-concept trained from MVTec AD ground-truth masks for selected complete categories. It is not evaluated under the standard unsupervised MVTec AD protocol. Reported mAP/IoU numbers are internal localization metrics on a held-out split derived from the labeled MVTec defect images and are not comparable to PatchCore/EfficientAD/PaDiM standard MVTec image-AUROC results.

中文展示可写：

> Phase 10 使用 MVTec 缺陷图及其 GT mask 训练轻量定位器，用于证明 RK3588 可部署缺陷定位闭环；这不是标准 MVTec 无监督异常检测 benchmark。

### 7.10 是否需要人工 gold set？

需要，至少两类 gold set：

1. **Geometry gold QA：**  
   每个 selected category 抽 20–30 张，人工检查 mask-to-bbox 是否合理，尤其是多连通域、小缺陷、`flip`、`combined`。

2. **Language gold QA：**  
   50–100 条人工审查 observation / severity_reason，检查 cloud VLM 或模板是否 hallucinate，比如把金属划痕写成锈蚀、烧焦、污染等。

### 7.11 Cloud VLM 可以生成哪些字段？

可以生成：

- `observation`
- `severity_reason`
- `defect_family` 建议，但需规则映射审核
- crop-level description
- full-image inspection note
- QA pairs / ShareGPT messages
- 中文报告话术

### 7.12 Cloud VLM 不应该生成哪些字段？

不应该生成或覆盖：

- bbox
- mask
- canonical `defect_type`
- train/val/test split
- geometry confidence
- ground-truth severity label
- 任何用于 localizer 训练的几何真值

### 7.13 如何避免伪标签污染？

- 所有 generated 字段必须有 `source`：`gt_mask`、`yolo_model`、`template`、`edge_vlm`、`cloud_vlm`、`human`。
- Cloud VLM 输出只进入 language target，不进入 geometry target。
- 训练 localizer 的 manifest 只读取 `gt_mask`/`human` 几何字段。
- Cloud VLM 生成的 observation 先进入 pending pool，通过 gold set QA 后才能用于 LoRA/SFT。
- 保留原始 MVTec label，不让 VLM 反向改写 canonical label。

---

## 8. VLM Role Redesign

### 8.1 新角色定义

Qwen3-VL 2B W8A8 不再是 classifier/localizer，而是 narrative layer。

旧角色：

```text
image + FastSAM proposal + EAD score
→ VLM JSON: category, defect_type, severity, confidence, bboxes, description
```

新角色：

```text
image/crop + YOLO class + YOLO bbox + optional EAD score
→ VLM JSON: observation, severity_reason, accepted_box_ids
```

### 8.2 是否彻底取消 VLM bbox 输出？

是。

VLM 不再输出 `bboxes`，也不允许在 prompt 中“修正 bbox”。如果要让 VLM 选择可见区域，只能输出 `accepted_box_ids`，且不改变坐标。

### 8.3 VLM 是否还应该输出 closed-set `defect_type`？

不应该。

`defect_type` 由 YOLO class head 输出。VLM 可以在 observation 中自然描述，但不能作为 canonical label 来源。

### 8.4 VLM 是否改成 observation / severity_reason？

是。

推荐输出：

```json
{
  "observation": "金属螺母边缘可见局部划痕，缺陷集中在右上侧。",
  "severity_reason": "缺陷区域较小但位于边缘功能面，建议复检。",
  "accepted_box_ids": [0]
}
```

### 8.5 VLM 是否从实时主链路改成 async enrichment？

推荐改成 async。

原因：

- 当前 VLM 总延迟在秒级，Phase 9 soak 中 average 可到 15s 级别。
- YOLO localizer 延迟相对小很多，不应被 VLM 阻塞。
- Dashboard 可以先显示 “Detected now”，后续 enrichment 到达后显示 “Analysis updated”。
- 7 天 demo 可以完全不跑 VLM，用 template observation，先把定位做好。

### 8.6 LoRA / SFT 处置

- **板端 W8A8 LoRA 主线：暂停。** 仓库已有塌缩证据。
- **PC bf16 LoRA：保留为离线研究。** 可用于生成更好 language observation，但不要承诺上板 exact classification。
- **Cloud/PC SFT 目标：改为 observation / severity_reason / structured report。** 不再以精确 MVTec defect_type 和 bbox 为目标。

---

## 9. Recommended Phase 10 Architecture

### 9.1 推荐 pipeline

```text
T1 Capture
  - 输出 frame_id, image_path, timestamp, optional category_hint

T2 EfficientAD-S FP16 RKNN gate / score / diagnostic
  - 输出 anomaly_score, gate_pass, optional heatmap_debug
  - benchmark mode 可关闭 gate

T3 YOLOv8n-detect RKNN localizer
  - 输入原图或统一 resize/letterbox 图
  - 输出 detections: bbox, class_id, class_label, score
  - 这是 primary bbox + defect_type + confidence 来源

T3b Optional debug proposal
  - FastSAM disabled by default
  - 仅在 debug profile 输出 object_proposals

T4 Observation enrichment
  - v1: template generator
  - v1.1: edge Qwen3-VL async observation
  - v1.2: cloud VLM async enrichment

T5 Upload
  - API v1.3: explicit source fields
  - reject invalid bbox before HTTP call, avoid 400

T6 Frontend overlay
  - primary model bbox
  - proposal bbox optional hidden layer
  - GT reference bbox/mask only in offline evaluation/demo mode
```

### 9.2 字段责任划分

| 字段 | Phase 10 来源 | 说明 |
|---|---|---|
| `bbox` / `bboxes` | YOLOv8n-detect | primary model localization；top-left normalized xywh for API |
| `mask` | v1 无模型 mask；GT reference 只用于 eval | 若后续 YOLO-seg/U-Net，再加入 model mask |
| `defect_type` | YOLO class head | flat class `category/defect_type` 映射 |
| `category` | YOLO class prefix / simulator metadata consistency check | 不由 VLM 决定 |
| `defect_family` | rule map from defect_type | 面向用户分组 |
| `observation` | template / edge VLM / cloud VLM | 必须标注 source |
| `severity` | rule from defect_type + bbox area + optional EAD score | VLM 可解释，不应单独决定 |
| `severity_reason` | template / VLM | narrative only |
| `confidence` | YOLO detection score | VLM confidence 不再作为主置信度 |
| `anomaly_score` | EfficientAD raw_score/final_score | 与 YOLO confidence 分开 |
| `localization_source` | fixed string/config | 例如 `yolov8n_detect_rknn` |

### 9.3 API contract 是否需要 v1.3 / v2？

推荐 **v1.3 最小演进**，不要直接 v2 大改。

当前 v1.2 问题：

- `pipeline_ms` 要求 `efficientad`、`fastsam`、`qwen3vl`，不适合 YOLO localizer。
- `bboxes` 没有 source 字段。
- `Stage` 只包含 `efficientad|fastsam|qwen3vl`。
- `defect_type` 语义默认像 VLM 输出，但 Phase 10 要改为 YOLO class。

v1.3 最小新增：

```json
{
  "schema_version": "v1.3",
  "localization_source": "yolov8n_detect_rknn",
  "label_source": "yolo_class_head",
  "observation_source": "template|edge_vlm|cloud_vlm|human",
  "defect_family": "insulation_damage",
  "observation": "...",
  "severity_reason": "...",
  "pipeline_ms": {
    "efficientad": 12.3,
    "localizer": 24.1,
    "enrichment": 0.0,
    "upload": 5.0
  },
  "debug": {
    "object_proposals": [],
    "gt_reference_bboxes": []
  }
}
```

兼容策略：

- `bboxes` 仍保留，但定义为 primary localizer bbox。
- 旧前端读取 `description` 的地方可映射到 `observation`。
- 如果后端暂时不能改 `pipeline_ms`，短期可把 YOLO latency 写到 `fastsam` 字段，但必须在文档中标注这是兼容 hack；正式版应改 schema。

### 9.4 前端如何区分 model bbox、proposal bbox、GT reference

推荐 UI：

- **Model bbox：** 默认显示，标签 `Localizer detection`。
- **Proposal bbox：** 默认隐藏，调试开关显示，标签 `Debug proposal: FastSAM/VLM`。
- **GT reference：** 只在 offline evaluation snapshot 显示，标签 `GT reference, not model output`。
- **Mask：** 只有当模型实际输出 mask 时显示；GT mask 不应伪装成模型 mask。
- **Badge：** `defect_type` badge 标注 `source: YOLO class head`。
- **Observation：** 标注 `template` / `edge VLM` / `cloud VLM` / `human curated`。

---

## 10. 7-Day Fast Demo Plan

目标：7 天内让前端定位效果明显改善，但诚实说明不是 benchmark。

推荐范围：`metal_nut + cable`。若 Day 3 PC baseline 很好，再加入 capsule 作为 stretch goal。

### Day 1 — 数据与标签脚本

任务：

- 新增 `scripts/phase10/mvtec_mask_to_yolo.py`。
- 新增 `scripts/phase10/split_mvtec_localization.py`。
- 新增 `scripts/phase10/visualize_yolo_labels.py`。
- 选择完整 category：`metal_nut + cable`。
- 从 MVTec GT mask 生成 YOLO labels。
- 输出 class map：`phase10_classes.yaml`。
- 生成 label QA 图：原图 + GT mask + bbox。

必须修复：

- 明确 top-left xywh、center xywh、xyxy 转换函数。
- 不复用 `eval_ab_test.py` 中 center/top-left 混淆的 IoU 逻辑。

PC 完成：全部。

验收标准：

- 每个 defect type 都有 label。
- 每张有 mask 的 defect image 至少生成一个 bbox，除非被明确记录为过滤。
- 50 张可视化抽查无明显坐标错位。

### Day 2 — PC 训练 YOLOv8n-detect baseline

任务：

- 训练 YOLOv8n-detect 640 输入 baseline。
- 固定 random seed 和 split manifest。
- 记录 per-class sample count。
- 输出 ONNX 前的 PC validation metrics。

需要新增：

- `configs/phase10_yolov8n_metal_nut_cable.yaml`
- `docs/experiments/phase10_dataset_manifest.md`

PC 完成：训练与初评。

验收标准：

- mAP@0.5 达到可演示阈值，例如 overall ≥0.55。
- 关键可视类如 `metal_nut/scratch`、`cable/cut_outer_insulation` 有可见正确框。
- 每个 defect type 都输出 AP，不允许只报平均值。

### Day 3 — PC 评估与可视化筛查

任务：

- 新增 `scripts/phase10/eval_yolo_localization.py`。
- 生成 confusion matrix、per-class AP、bbox IoU 分布。
- 生成 dashboard-ready static snapshot：`phase10_pc_predictions.json`。
- 决定是否加入 capsule。

PC 完成：全部。

验收标准：

- 至少 80% 抽样图中 bbox 视觉上覆盖缺陷区域，而非整个对象。
- 不把低 AP 类藏起来；低 AP 类写入 risk section。
- 若某个 defect type AP<0.20，必须分析是小目标、语义 anomaly、mask 多组件还是数据不足。

### Day 4 — ONNX / RKNN 导出与校验

任务：

- 导出 ONNX。
- 新增 `scripts/phase10/export_yolo_rknn.sh`。
- 新增 `scripts/phase10/compare_onnx_rknn.py`。
- 准备 calibration set，覆盖 selected categories、good/defect、不同 defect types。
- 在 PC 或 RKNN toolkit 环境导出 RKNN FP16/INT8 候选。

PC 完成：ONNX export、转换脚本。

RK3588 完成：RKNN runtime smoke test。

验收标准：

- ONNX 与 RKNN 对同一批图的 bbox/class 结果差异可解释。
- 如果 INT8 AP delta >10%，回滚到 FP16/no-quant。
- 单帧 localizer runtime 远低于 VLM，目标 <100ms；若更高也要记录。

### Day 5 — Edge pipeline 集成

任务：

- 新增 `edge/src/pipeline/yolov8_worker.cpp` 或 `localizer_worker.cpp`。
- 新增 `edge/include/edge/common/localizer_types.hpp`。
- 修改 `edge/include/edge/common/types.hpp`，加入 source 字段。
- 修改 `upload_worker.cpp` payload：`defect_type`、`confidence`、`bboxes` 来自 YOLO。
- FastSAM 默认禁用，保留 debug flag。
- VLM 默认不阻塞主链路。

RK3588 完成：C++ runtime 和 pipeline smoke test。

验收标准：

- 30 分钟 smoke test 无 crash。
- HTTP 400 = 0。
- 所有 bbox 在上传前通过 `0<=x,y,w,h<=1` 且 `x+w<=1`、`y+h<=1`。
- `defect_type` 不再大量是 `anomaly`，而是 class map 输出。

### Day 6 — Backend / Frontend v1.3 最小改造

任务：

- 修改 `backend/app/schemas/defect.py`：新增 `localization_source`、`label_source`、`observation_source`、`defect_family`、`severity_reason`，放宽/扩展 pipeline stage。
- 修改 contract tests。
- 修改 `FrameInspector.tsx`：label 从 `Proposal bbox` 改为 `Localizer detection`。
- 增加 debug overlay toggle：proposal / GT reference 默认关闭。
- 修改 `CaveatBanner.tsx`：新增 Phase 10 supervised localizer 口径。

PC 完成：后端/前端开发和 contract tests。

验收标准：

- 旧 snapshot 仍能显示。
- 新 snapshot 明确显示 `source: yolo localizer`。
- Dashboard 不再把 GT reference 或 debug proposal 误标为模型输出。

### Day 7 — 文档、demo snapshot、验收

任务：

- 生成 `frontend/public/demo-data/phase10_localizer_snapshot/`。
- 新增 `docs/experiments/phase10_localization_demo_report.md`。
- 更新 README methodology caveat。
- 写 release note：Phase 9 proposal bbox → Phase 10 supervised localizer bbox。
- 固化 config：`edge/config_phase10_yolo.yaml`。

验收标准：

- 前端定位视觉明显优于 Phase 9 curated snapshot。
- 完整类别覆盖，不是挑单个 defect type。
- 公开文档说明不是标准 benchmark。
- 所有指标表包含 per-class，而不是只给平均数。
- 可回放 demo snapshot。

### 快速 demo 风险与回滚

| 风险 | 回滚方案 |
|---|---|
| YOLOv8n 对 cable 某些类 AP 很低 | 先发布 `metal_nut + cable`，但标注低 AP 类；或切到 `metal_nut + capsule` |
| RKNN INT8 精度掉太多 | 用 FP16/no-quant RKNN；localizer 延迟仍可接受 |
| C++ worker 来不及 | 先用 PC/RK Python prototype 生成 snapshot，边端 C++ 标为 in-progress；但文档不能声称 realtime edge 完成 |
| API v1.3 来不及 | 短期复用 `bboxes` 和 `description`，但 manifest 加 `localization_source`；下一天补 schema |
| VLM observation 质量差 | 用模板 observation，VLM async 不作为 demo blocker |

---

## 11. Rigorous Mini-Benchmark Plan

目标：可复现实验、完整类别覆盖、留出验证集、定量指标。推荐范围：`metal_nut + cable + capsule`；若资源不足，用 `metal_nut + capsule` 做更扎实的小目标/刚性件基准。

### Day 1 — 固定数据协议

任务：

- 写 `docs/experiments/phase10_benchmark_protocol.md`。
- 定义 selected categories 和全部 defect types。
- 生成不可变 split manifest：train/val/test 或 5-fold split。
- 记录所有 image ids，禁止重叠。
- 明确：这是 supervised localization benchmark，不是 standard MVTec AD benchmark。

新增脚本：

- `scripts/phase10/build_split_manifest.py`
- `scripts/phase10/check_split_leakage.py`

验收：

- split manifest 可复现。
- 每个 defect type 至少有 held-out 样本。
- 输出 class imbalance 表。

### Day 2 — Geometry label QA

任务：

- mask-to-bbox 生成 labels。
- 每类每 defect type 抽样可视化。
- 人工标注 QA 结果：OK / merge-needed / tiny / ambiguous / object-level。
- 修正规则并冻结。

新增脚本：

- `scripts/phase10/audit_generated_bboxes.py`
- `scripts/phase10/export_label_qa_html.py`

验收：

- 100 张以上 QA 可视化。
- ambiguous 类如 `metal_nut/flip`、`cable_swap` 有明确说明。
- 过滤规则写进 manifest。

### Day 3 — Baseline 训练矩阵

任务：

- 训练 YOLOv8n 640 baseline。
- 可选训练 768/1024 或 YOLOv8s 对比，但不要影响主线。
- 记录 augmentation、epochs、batch、seed、image size。

新增文档：

- `docs/experiments/phase10_training_runs.md`

PC 完成：训练。

验收：

- 每个 run 有 config、commit/hash、class map、split manifest。
- 不只保存 best.pt，也保存 metrics JSON。

### Day 4 — 指标评估

任务：

- 计算 mAP@0.5、mAP@0.5:0.95、per-class AP、precision、recall。
- 计算 bbox IoU 分布、per-category confusion matrix。
- 统计 false positive on good images。
- 统计 small/medium/large defect AP。

新增脚本：

- `scripts/phase10/report_metrics.py`
- `scripts/phase10/error_gallery.py`

验收：

- 报告包含低分失败案例 gallery。
- 每个类别都有结论，不能只给 aggregate。
- 低 AP 类有下一步策略。

### Day 5 — ONNX/RKNN 一致性评估

任务：

- 导出 ONNX、RKNN FP16/INT8。
- 同一 held-out test subset 上比较 PyTorch、ONNX、RKNN 输出。
- 记录 per-class AP delta。
- 记录 latency 和内存。

RK3588 完成：runtime benchmark。

验收：

- ONNX→RKNN mAP delta <5% 为优，<10% 可接受。
- 如果 INT8 不达标，记录 FP16/no-quant 作为发布模型。
- latency、RSS、NPU/CPU 负载进入报告。

### Day 6 — 端到端 pipeline benchmark

任务：

- 在 RK3588 上跑固定回放集。
- 分别测试 gate on / gate off。
- 记录 trace_events、pipeline_ms、HTTP 成功率。
- 前端加载 benchmark snapshot。

指标：

- HTTP 400 = 0。
- contract tests pass。
- gate off 模式 localizer recall 不受 EAD gate 影响。
- gate on 模式报告 EfficientAD 误杀率。

### Day 7 — 报告与复现实验打包

任务：

- 完成 `docs/experiments/phase10_mini_benchmark_report.md`。
- 更新 README。
- 更新 `docs/API_CONTRACT.md` v1.3。
- 保存 model card：训练数据、限制、license、部署口径。
- 生成 demo snapshot 和 benchmark snapshot 两套数据，避免混淆。

验收：

- 任意 reviewer 能从 split manifest、class map、config、metrics 重现实验。
- README 明确不是 standard MVTec AD benchmark。
- Dashboard 明确区分 demo/benchmark/source。

### 严谨版必须在 PC 完成的任务

- 数据 split、label 生成、label QA。
- 模型训练、PyTorch/ONNX 初评。
- 文档和指标表生成。
- 前端/后端 schema 开发和测试。

### 严谨版必须在 RK3588 完成的任务

- RKNN runtime 推理。
- ONNX/RKNN 结果一致性抽样。
- 端到端 pipeline soak。
- latency/RSS/HTTP 400/trace_events 验证。

### 严谨版风险与回滚

| 风险 | 缓解/回滚 |
|---|---|
| 每类样本太少，split 不稳定 | 使用 stratified k-fold，报告均值和方差 |
| cable 8 类 per-class AP 波动大 | 合并显示层 `defect_family`，但 hidden label 仍保留；不要篡改 benchmark label |
| capsule tiny defects AP 很低 | 提升输入分辨率、copy-paste、tiling；或将 capsule 放入 Phase 10.2 |
| EAD gate 误杀缺陷 | benchmark mode 关闭 gate；production mode 报告 gate recall |
| reviewer 质疑 test GT 训练 | README 明确 supervised POC；不与无监督 AD SOTA 比 |

---

## 12. What to Keep / Downgrade / Remove

| 模块 | 处置 | 理由 | Phase 10 具体动作 |
|---|---|---|---|
| EfficientAD-S | **保留但降级** | 适合 gate/score，不适合 global bbox localization | T2 gate + anomaly_score + heatmap debug；benchmark 可关闭 gate |
| FastSAM | **从主链路删除/默认禁用** | class-agnostic proposal，mask decode 未完成，常框对象 | 仅 debug profile 输出 `object_proposals` |
| Qwen3-VL 2B base W8A8 | **改造** | 不适合 bbox/class，适合语言解释 | async observation / severity_reason；不阻塞主 localizer |
| LoRA / SFT | **暂停板端主线，保留离线研究** | W8A8 LoRA defect_type 塌缩 | SFT 目标改为 observation，不再训练 bbox/defect_type exact |
| VLM bbox output | **删除** | 坐标不稳、HTTP 400 风险、任务错配 | Prompt 和 parser 不再接受/上传 VLM bbox |
| VLM defect_type output | **删除 canonical 角色** | W8A8 exact 分类不可用 | `defect_type` 来自 YOLO；VLM 只写自然语言 |
| API contract v1.2 `bboxes` | **保留字段，重定义语义** | 前后端已依赖 bbox | v1.3 中 `bboxes` = primary localizer bbox；proposal 另放 debug |
| Frontend bbox overlay | **保留并改造** | 可视化很有价值 | 标签改为 `Localizer detection`；增加 proposal/GT toggles |
| trace_events / dashboard | **保留** | 工程作品集强项 | 增加 `yolo_localizer`/`enrichment` trace stage |
| curated snapshot | **归档/降级** | Phase 9 展示，不是 benchmark | 保留为 historical Phase 9；Phase 10 新建 supervised localizer snapshot |
| Backend / FastAPI | **保留并小改** | 工程闭环成熟 | schema v1.3 + source fields + contract tests |
| Upload worker | **改造** | 当前 payload 来源混合 | bbox/class/confidence 来自 localizer；upload 前强校验 |

明确回答：

1. **EfficientAD 是否只保留为 gate？** 是，附带 score/diagnostic，但不是 localizer。
2. **FastSAM 是否应从主链路删除？** 是，默认禁用；debug-only。
3. **VLM 是否彻底取消 bbox 输出？** 是。
4. **VLM 是否还应该输出 closed-set defect_type？** 不应该。
5. **defect_type 是否应改由 YOLO class head 产生？** 是。
6. **VLM 是否改成 observation / severity_reason？** 是。
7. **VLM 是否应从实时主链路改成 async enrichment？** 推荐是；7 天 demo 可先模板化。

---

## 13. API and Frontend Changes

### 13.1 API v1.3 最小改动

新增字段：

```python
localization_source: str
label_source: str
observation_source: str | None
defect_family: str | None
severity_reason: str | None
model_bboxes: list[BBox] | None        # optional alias/debug; bboxes remains primary
object_proposals: list[BBox] | None    # debug only
gt_reference_bboxes: list[BBox] | None # offline/eval only
```

修改字段语义：

- `bboxes`: primary localizer output，不再是 FastSAM/VLM proposal。
- `defect_type`: YOLO class map 的 canonical defect type。
- `confidence`: YOLO detection confidence。
- `description`: 兼容旧字段，可映射 observation；新字段优先 `observation`。

修改 trace stage：

```text
efficientad
yolo_localizer
upload
enrichment_template
enrichment_edge_vlm
enrichment_cloud_vlm
```

如果为了兼容必须保留旧 stage：

- `fastsam` 可以临时写 0 或 localizer latency，但必须标注 deprecated。
- 不建议长期这样做；会污染 telemetry。

### 13.2 后端校验

必须新增：

- upload 前和后端 route 都校验 `x+w<=1`、`y+h<=1`。
- class id 必须存在于 `phase10_classes.yaml`。
- `defect_type` 不允许是空字符串；如果无检测，应使用 explicit `no_detection` 状态，而不是 `anomaly`。
- `source` 字段必填，防止前端误解。

### 13.3 前端变更

`FrameInspector.tsx`：

- Overlay tooltip 从 `Proposal bbox from FastSAM/VLM` 改为：
  - `Model bbox from YOLOv8n localizer`。
- 增加 checkbox：
  - `Show debug proposals`
  - `Show GT reference`，只在 evaluation snapshot 可见。
- 缺陷卡片显示：
  - `Defect Type: cable/cut_outer_insulation (source: YOLO)`
  - `Observation: ... (source: template/edge VLM/cloud VLM)`

`CaveatBanner.tsx`：

- 新增 Phase 10 caveat：supervised localizer trained from MVTec GT masks, not standard benchmark。
- 保留 Phase 9 caveat 作为 historical mode。

`data-source.ts`：

- 新增 `phase10_localizer_snapshot` source preset。
- 明确区分 `historical_phase9_showcase` 和 `phase10_supervised_localizer_demo`。

---

## 14. README / Demo Honesty Guidelines

### 14.1 README 必须写清楚的内容

建议原文：

```md
### Phase 10 Localization Caveat

Phase 10 introduces a supervised YOLOv8n defect localizer for selected complete MVTec categories. Labels are derived from MVTec AD ground-truth masks by converting defect masks into bounding boxes. This is a deployable localization proof-of-concept for RK3588, not the standard unsupervised MVTec AD benchmark. Reported mAP/IoU metrics are computed on an internal held-out split from the labeled defect images and are not comparable to PatchCore/EfficientAD/PaDiM image-AUROC results under the standard protocol.
```

中文版本：

```md
Phase 10 使用 MVTec AD 缺陷图及其 ground-truth mask 训练轻量定位器，用于证明 RK3588 上可部署的缺陷定位闭环。该实验不是标准 MVTec 无监督异常检测 benchmark；报告的 mAP/IoU 仅表示所选完整类别内的有监督定位验证结果，不能与 PatchCore/EfficientAD/PaDiM 的标准 image-AUROC 直接比较。
```

### 14.2 Dashboard 必须标注

- `Localizer detection: YOLOv8n RKNN`
- `Label source: YOLO class head`
- `Observation source: template / edge VLM / cloud VLM / human`
- `GT reference: evaluation only, not model output`
- `Debug proposal: FastSAM/VLM historical proposal, not primary localization`

### 14.3 如何避免误导面试官

不要说：

- “MVTec 15 类 defect detection 已解决”。
- “标准 MVTec benchmark 达到 xx%”。
- “VLM 能可靠定位缺陷”。
- “FastSAM 负责精准缺陷分割”。
- “Cloud VLM 生成了 bbox 真值”。

应该说：

- “Phase 9 证明了 RK3588 工程闭环，但暴露出 proposal/VLM bbox 不可靠。”
- “Phase 10 针对 2–3 个完整 MVTec category 引入 supervised localizer，解决用户可见定位问题。”
- “几何标签来自 MVTec GT mask，VLM 只做语言解释。”
- “这是 focused proof-of-concept，不是全 15 类无监督 benchmark。”

### 14.4 Phase 9 价值如何表述

Phase 9 不是失败，而是提供了：

- RK3588 多模型 pipeline。
- EfficientAD RKNN gate。
- FastSAM RKNN integration 经验。
- Qwen3-VL RKLLM/W8A8 量化排障。
- FastAPI + Next.js dashboard。
- contract tests、trace_events、soak testing。
- 真实约束下的诚实 failure analysis。

Phase 10 的价值是把 Phase 9 发现的问题收敛成正确的模型职责划分。

---

## 15. Risks and Open Questions

### 15.1 技术风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| YOLOv8n 对 tiny/elongated defects AP 不够 | capsule crack/scratch, cable thin defects 失败 | 提高输入分辨率、copy-paste、tiling、YOLOv8s、后续 seg |
| 多组件 mask 转 bbox 规则不稳定 | label 噪声，训练混乱 | QA 可视化、合并规则、top-K 限制、manifest 固化 |
| `metal_nut/flip` 不是局部缺陷 | bbox 看起来像框全物体 | 标注为 object-level anomaly，单独报告 |
| RKNN INT8 精度漂移 | 上板结果差 | FP16/no-quant fallback；ONNX/RKNN delta 报告 |
| API v1.2 stage 固化 | 新 worker 难接入 telemetry | v1.3 加 `localizer` stage；不要长期借用 `fastsam` 字段 |
| VLM async 复杂度 | 延迟、JSON、source 混乱 | 7 天 demo 先模板化，VLM 后置 |
| Existing bbox IoU evaluator 坐标混淆 | 历史指标不可信 | 重写 evaluator 并加单元测试 |

### 15.2 数据风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 使用 MVTec test GT 训练 | 不是标准 benchmark | README/Dashboard 明确 supervised POC |
| 每 defect type 样本少 | per-class AP 不稳定 | stratified split/k-fold，报告方差 |
| Cloud VLM 伪标签污染 | 语言 hallucination 进入训练 | source 字段、gold set、人审 |
| MVTec license | 商用受限 | 文档标注 CC BY-NC-SA；只做 portfolio/demo |

### 15.3 开放问题

1. YOLOv8n 640 是否足够处理 capsule crack/poke？需要 PC baseline 证明。
2. `cable_swap`、`missing_cable` 等结构性异常是否用 bbox 足够表达？还是需要 object-level/global label？
3. `metal_nut/flip` 是否应作为 localizable defect，还是单独的 object-level classification？
4. 是否需要把 `severity` 从 VLM 输出改成规则：bbox area ratio + defect_family + class prior？我建议是。
5. v1.3 API 是否要继续兼容旧 `pipeline_ms.fast_sam/qwen3vl`？短期可兼容，长期应迁移。
6. 是否未来引入 segmentation？建议等 detect baseline 和 RKNN 部署完成后再决策。

---

## 16. Final Recommendation

我的最终建议如下：

1. **采纳 Claude 的核心方向，但缩小第一版 scope。**  
   不再包装 FastSAM/VLM/EAD bbox；引入 supervised YOLOv8n-detect localizer。Claude 的方向正确，但 7 天第一版不要直接压满 3 类 17 defect types、cloud enrichment、edge VLM 和 mask pipeline。

2. **Phase 10 v1 选择 `metal_nut + cable`。**  
   这是最适合作品 demo 的 2 类组合：金属零件 + 线束，工业感强，bbox 检测可解释。`capsule` 作为第三类和严谨版小目标压力测试加入。`wood` 暂不进第一版。

3. **Phase 10 v1 localizer 使用 YOLOv8n-detect。**  
   先输出 bbox，不输出 mask。mask 数据转换可以预留，但不要作为 v1 验收项。后续如果 capsule/wood 需要更精细可视化，再引入 YOLOv8n-seg 或 U-Net-small。

4. **字段职责彻底重排。**  
   `bbox`、`defect_type`、`confidence` 来自 YOLO；`anomaly_score` 来自 EAD；`observation`、`severity_reason` 来自模板/edge VLM/cloud VLM；GT reference 只用于 evaluation，不作为模型输出。

5. **FastSAM 默认退出主链路。**  
   保留 debug-only，不再写入主 `bboxes`。

6. **VLM 从主实时链路改为 async enrichment。**  
   7 天 demo 可以不用 VLM，直接模板 observation；后续再接 edge/cloud VLM。

7. **API 升级到 v1.3。**  
   最少新增 source 字段和 `localizer` telemetry。不要让旧字段继续掩盖 bbox 来源。

8. **文档必须诚实。**  
   使用 MVTec GT mask 训练 localizer 是 supervised proof-of-concept，不是标准 MVTec AD benchmark。这个 caveat 应放在 README、Dashboard、实验报告和 demo manifest 中。

最小可交付定义：

```text
Selected complete categories: metal_nut + cable
Model: YOLOv8n-detect RKNN
Geometry: GT mask → bbox labels, YOLO output as primary bbox
Label: YOLO class head → category/defect_type
EAD: gate/score only
FastSAM: debug-only
VLM: no bbox, no canonical defect_type; observation async or template
Frontend: source-aware overlay
Docs: supervised POC caveat
Acceptance: no HTTP 400, per-class metrics, visible bbox improvement, reproducible split
```

这条路线既能快速改善前端定位效果，又不会伪装成标准 benchmark；同时保留 Phase 9 工程闭环的价值，并把 Phase 10 的贡献聚焦在“真正可部署的缺陷定位器”。
