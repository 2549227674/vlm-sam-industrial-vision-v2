# Phase 10 v1 Session Handoff Prompt

复制以下内容到新 Claude Code 会话：

---

你好，我正在继续 vlm-sam-industrial-vision-v2 项目的 Phase 10 v1 工作。

## 当前分支
branch: phase10/localization-refactor-v1（已推送到 origin）

## Phase 10 v1 目标
为 metal_nut + cable（2 类 12 个 defect type）引入有监督 YOLOv8n-detect localizer，替代 FastSAM/VLM bbox 作为主定位方案。

## 已完成的工作（10 个 commit）

1. **f8a8439** — 执行计划文档
2. **f507799** — 第一阶段主体（数据转换、backend v1.3、frontend overlay）
3. **a6bc70b** — CI contract drift 修复
4. **f4cab38** — pipeline_ms v1.3 兼容修复
5. **bd57c1d** — stats avg_pipeline_ms 聚合修复
6. **6999594** — Preflight QA 结果文档
7. **9095921** — YOLOv8n 训练结果（mAP50=0.593 PASS）
8. **51ebd5b** — RKNN FP16 转换脚本 + artifact 清单
9. **4e980d2** — RKNN FP16 诊断报告（BLOCKED）
10. **188b15e** — airockchip 多输出尝试（也 FAIL）

## RKNN Numeric Consistency: BLOCKED

rknn-toolkit2 2.3.2 编译 YOLOv8 检测头存在根本性问题：

| 尝试 | 结果 |
|------|------|
| 标准 Ultralytics 单输出 [1,16,8400] | class score r≈0 |
| airockchip 多输出 9 tensors | class score r≈0, box r=0.6-0.7 |
| opset 12/19, opt_level 0, 各种输入格式 | 全部失败 |

**诊断文档**: `docs/experiments/phase10_rknn_fp16_diagnostic.md`
**airockchip 计划**: `docs/experiments/phase10_rknn_airockchip_reexport_plan.md`

## 待决策方向（推荐排序）

1. **ONNX Runtime CPU 推理** — 在 RK3588 上用 onnxruntime 做 CPU 推理，速度慢但数值正确
2. **升级 rknn-toolkit2** — 从 GitHub main 分支安装，可能有修复
3. **向 rknn-toolkit2 提 issue** — 提供可复现的测试用例
4. **尝试 INT8 量化** — 可能避开 FP16 精度问题
5. **尝试 YOLOv8s** — 不同 head 架构可能避开 bug
6. **暂搁 RKNN，继续 PC 端集成逻辑**

## 已完成但与 RKNN 无关的工作

- YOLOv8n 训练：mAP50=0.593, mAP50-95=0.432（PASS）
- ONNX 导出：opset=19, 11.7MB, checker PASS
- PyTorch 推理验证：top-1 class 正确，IoU=0.84
- RK3588 smoke test（旧单输出格式）：bbox valid PASS, 但 class 错误
- 所有 artifact sha256 已记录在 `docs/experiments/phase10_training_run_1.md`

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 执行计划 | `docs/experiments/phase10_v1_execution_plan.md` |
| 训练结果 | `docs/experiments/phase10_training_run_1.md` |
| RKNN 诊断 | `docs/experiments/phase10_rknn_fp16_diagnostic.md` |
| airockchip 计划 | `docs/experiments/phase10_rknn_airockchip_reexport_plan.md` |
| 数据集 manifest | `docs/experiments/phase10_dataset_manifest.md` |
| API 契约 | `docs/API_CONTRACT.md`（v1.3） |
| 训练脚本 | `scripts/phase10/` 目录 |
| 转换脚本 | `scripts/phase10/convert_yolov8n_rknn.py`（标准） |
| 转换脚本 | `scripts/phase10/convert_airockchip.py`（airockchip） |
| Smoke test | `scripts/phase10/smoke_test_rknn.py`（单输出） |
| Smoke test | `/tmp/smoke_test_airockchip.py`（多输出，未入库） |
| 本地权重 | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt`（gitignored） |
| ONNX | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best_airockchip.onnx`（gitignored） |
| RKNN | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best_airockchip_fp16.rknn`（gitignored） |

## Artifact SHA256

| 文件 | SHA256 |
|------|--------|
| best.pt | `36cdd96cf4b71422eebc2ff37f43955efd37744f702f15e653db596523455a26` |
| ONNX (airockchip) | `0c49a84633d40a4d1764ebd0e43fa8be78f2dc285845086f6ba21dfb1696678e` |
| RKNN FP16 (airockchip) | `ad169972d1c8c0e8fdfaaa8dd10359dab6cf5193e6cc69488fe4399d3ef4aefb` |

## SSH 环境

- **AutoDL**（RTX 4090 训练）：`ssh -p 28728 root@connect.westb.seetacloud.com`，密码 `Y0qZqSuy9xzp`
- **Orange Pi 5**（RK3588 推理）：`ssh orangepi@192.168.137.66`，密码 `orangepi`
- 详细凭据在 `~/.claude/projects/.../memory/reference_ssh_credentials_phase10.md`
- **不要在代码或文档中提交密码/IP/sshpass 命令**

## 约束

- FastSAM 代码保留不删，仅通过 config 禁用
- VLM v1 不调用，仅 template observation
- 不做 YOLO-seg / U-Net / cloud enrichment / API v2
- defect_type 来自 YOLO class head，bboxes/confidence 来自 YOLO detector
- 主模型无法处理视觉任务，需切换 visual agent
- 代码注释用英文

## Memory 条目

- `feedback_english_comments.md` — 代码注释用英文
- `feedback_autodl_ssh_reminder.md` — 训练前询问 SSH 信息
- `feedback_visual_agent_switch.md` — 视觉任务切换 agent
- `reference_ssh_credentials_phase10.md` — SSH 凭据（Phase 10 结束后删除）

请先确认你了解当前状态，然后等待我决策 RKNN 方向。
