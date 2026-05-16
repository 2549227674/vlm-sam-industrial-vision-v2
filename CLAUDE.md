# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

端云分离架构的工业视觉 AI 检测项目：边缘端 RK3588 16GB 跑三段式异步推理流水线（EfficientAD-S → FastSAM → Qwen3-VL-2B/4B），后端 FastAPI 收单与广播，前端 Next.js 仪表盘做可视化。本文档是 Claude Code 在本仓库的总入口，定义全局约束与导航。

## 当前实现状态

**Phase 1-3 完成，Phase 4（轨道A 联调验收）为下一步，Phase 5/6 v1 初版已完成，v2 重做准备中**

已完成：
- Phase 1.1：项目骨架初始化（FastAPI + Next.js 15 + SQLAlchemy 2.0）
- Phase 1.2：Pydantic v2 Schema（DefectCreate/DefectRead/DefectCreatedResponse + field_validators）
- Phase 1.3：SQLAlchemy 2.0 Defect 模型（WAL 模式 + UniqueConstraint + TZDateTime）
- Phase 1.4：POST `/api/edge/report` 路由（multipart 落盘 + 全量错误码）
- Phase 1.5：GET 查询路由（defects 分页 + stats 聚合 + health 探针）
- Phase 1.6：WebSocket `/ws/dashboard`（ConnectionManager + 心跳 metrics_tick/ping）
- Phase 2.1：模拟器 `simulator/line_runner.py`（PNG→JPEG 内存转换 + 指数退避重试 + Session 复用 + 路径绝对化）
- Phase 2.2：6 个契约测试，31 passed（`pytest backend/tests/contract/ -v`），同步修复后端两处潜在 bug：`edge.py` `_error()` 对 Pydantic `errors()` 做 `json.dumps(default=str)` 防序列化崩溃；`main.py` 注册 `RequestValidationError` 全局 handler 返回契约规定的 `{"error": {"code": ..., "message": ...}}` 格式
- Phase 3.1：Next.js 15 骨架（App Router + shadcn/ui + Tailwind v4 @theme + output:'export'）
- Phase 3.2：实时缺陷流水 DataTable（TanStack Table v8 + 9 列 + 指数退避 WebSocket）
  - 网络层抽离为 frontend/src/lib/ws.ts（useRef 模式防重连）
  - 环境变量抽离为 frontend/src/lib/api.ts（API_BASE）
- Phase 3.3：统计聚合图（KPI 6 联 / 瀑布图 / Category×Severity 矩阵 / AB 5 轴对比）
  - 后端同步扩展 stats.py：avg_pipeline_ms / category_severity_matrix / avg_prompt_tokens
- Phase 3.4：DetailDrawer（Sheet 侧滑，非跳转新页）+ CSS 百分比 BBox Overlay + NPU Trace 占位区
  - 新增 frontend/src/types/defect.ts 中的 TraceEvent 接口（Phase 7 预留）
  - 模拟器新增 generate_trace_events() 函数（暂不上报，供前端联调）
- Phase 3.5：WebSocket Toast（Sonner，已随 3.2/3.4 完成）
- Phase 3.6：静态导出验证（npm run build 通过，out/ 目录存在）
- Phase 3.7：视觉精修 — 对齐 V2 设计稿（新增 12 个 v2/ 组件，mock-data.ts fallback，visual-verify subagent 截图对比，10/11 视觉匹配）
- Phase 3.8：功能完整性验证 + 旧组件清理（5 个旧组件删除，约 -800 行，BBox/Trace/Toast/API_BASE 全部迁移到 v2/ 组件，Hydration 错误修复）
- Phase 5.1-5.6 v1 初版：3 类（metal_nut/screw/pill）EfficientAD-S 训练 + FastSAM ONNX + LoRA 数据划分 + GT Mask 标注 + Qwen3-VL-2B LoRA 微调 + PC 端 AB 评估（方案A=100%，方案B=100%）
- Phase 6 v1 初版：3 类模型转换（EfficientAD RKNN / FastSAM RKNN / Qwen3-VL .rkllm）
- Phase 5.5 v2：Qwen3-VL-2B LoRA 15 类微调完成（rank=32，train_loss=0.5233，11m37s，RTX 4090 48GB）
- Phase 5.5b：Qwen3-VL-4B LoRA 15 类微调完成（rank=32，train_loss=0.411，20m32s，RTX 4090 48GB）
- Phase 5.6 Deployment Benchmark 已完成：4 变体 15 类评估，409 samples，max_tokens=200，详见 `docs/experiments/phase5_6_deployment_benchmark_report.md`
- Phase 5.7 Method Control Benchmark 已完成：相同 minimal prompt 隔离 LoRA 净贡献，结论见 `docs/experiments/phase5_7_method_control_benchmark_report.md`

Phase 5 v2 进行中：
- `scripts/format_llama_factory_data.py`：已扩展到 15 类自动发现 + train/eval 双输出 + 基础校验
- `scripts/eval_ab_test.py`：已扩展 deployment + method_control 双基准 + 8 项评估指标
- `scripts/optimize_prompt_opro.py`：新增 OPRO prompt-only baseline（PC 阶段方法学对照）
- `qwen3vl_lora.yaml`：已更新为 15 类 v2 配置（output_dir 隔离，freeze_vision_tower + freeze_multi_modal_projector）
- `qwen3vl_lora_4b.yaml`：已与 2B 保持控制变量一致
- `docs/experiments/phase5_method_matrix.md`：双轨评估设计（deployment benchmark vs method_control benchmark）

尚未开始（下一步）：
- Phase 4：轨道A 联调验收（模拟器 + 后端 + 前端全链路端到端验证）
  见 `docs/PROJECT_TIMELINE.md` 阶段 4
- Phase 6 v2 重做：Qwen3-VL-4B 模型转换（方案 C/D）+ 2B 重做

## 一句话定义

**RK3588 16GB 边缘端做异常检测 + 分割 + VLM 结构化描述，HTTP 上报到云端 FastAPI，WebSocket 实时推送给 Next.js 仪表盘**；面向本科课程设计 / 求职作品集，方向是端侧 AI 部署推理优化。

## 技术栈一览

| 分层 | 关键技术 | 版本/备注 |
|---|---|---|
| 边缘端硬件 | **RK3588 16GB**（Orange Pi 5 Plus 16GB） | 6 TOPS NPU，三核并行 |
| 边缘端运行时 | C++17/20、librknnrt、librkllmrt、librga、libcurl、V4L2 | rknn-llm v1.2.3+、rknn-toolkit2 v2.2+、GCC ≥ 11 |
| Stage 1 异常检测 | EfficientAD-S（PDN, 256×256, INT8） | Anomalib 2.x → 单一 ONNX → 单个 RKNN |
| Stage 2 分割 | FastSAM-s（640×640, INT8） | YOLOv8-seg 衍生 |
| Stage 3 VLM | Qwen3-VL-2B/4B-Instruct W8A8 | airockchip 官方 + Qengineering 镜像 |
| 后端 | Python 3.12、FastAPI 0.115+、SQLAlchemy 2.0 async、aiosqlite、Pydantic v2 | 生产单 worker（ConnectionManager 进程内单例）|
| 前端 | Next.js 15 App Router（`output: 'export'` 纯静态导出）、React 19、Tailwind v4、shadcn/ui | sonner / TanStack Table v8 / v2/ 原生 SVG 组件 |
| 模拟器 | Python 多线程 + 静态图片集循环 | 充当 RK3588 替身做契约测试 |
| 数据集 | MVTec AD：全 15 类（Phase 5 重做目标） | CC BY-NC-SA 4.0 |
| 通信 | HTTP `multipart/form-data`（边缘→后端）、WebSocket（后端↔前端） | 严禁 Base64 |

## Development Commands

### 后端（FastAPI）

```bash
# 启动开发服务器（hot reload）
cd backend && uvicorn app.main:app --reload --port 8000

# 运行契约测试
pytest backend/tests/contract/ -v

# 运行单个测试
pytest backend/tests/contract/test_post_report_happy_path.py -v
```

### 前端（Next.js 15）

```bash
cd frontend
npm run dev          # 开发服务器 localhost:3000
npm run build        # 静态导出到 out/（next build + output:'export'，不再需要 next export）
npm run lint         # ESLint
```

### 模拟器

```bash
cd simulator && python line_runner.py
```

### C++ 边缘端（轨道 B，板子到货后）

```bash
# 交叉编译
cd edge
cmake -DCMAKE_TOOLCHAIN_FILE=aarch64-toolchain.cmake -B build
cmake --build build -j$(nproc)

# 部署到板子
scp build/edge_pipeline ubuntu@<rk3588-ip>:/home/ubuntu/
ssh ubuntu@<rk3588-ip> './edge_pipeline --config config.yaml'
```

### 环境初始化

```bash
# Python（venv 已在 .venv/，Python 3.12）
source .venv/bin/activate
pip install -e "backend[dev]"   # 待 pyproject.toml 创建后可用

# 前端
cd frontend && npm install
```

## 仓库目录总览

> **注意**：`.gitignore` 已配置（见仓库根目录），忽略大文件模型权重（`models/`、`datasets/`）、构建产物和临时目录。本地开发需自行下载数据集和模型文件。

```
vlm-sam-industrial-vision-v2/
├── CLAUDE.md                       # 本文件
├── README.md
├── docs/
│   ├── ARCHITECTURE.md             # 系统架构详细设计
│   ├── API_CONTRACT.md             # 接口契约（轨道 A/B 解耦核心）
│   ├── PROJECT_TIMELINE.md         # 8 阶段执行指南（含每步指令示例）
│   └── DEPLOYMENT.md               # 上板部署手册（后期补充）
├── edge/                           # 轨道 B：RK3588 C++ 推理流水线
│   ├── CMakeLists.txt
│   ├── config.yaml                 # 边缘端配置（替代旧 configs/）
│   ├── include/
│   ├── src/
│   │   ├── main.cpp
│   │   ├── capture/                # T1 线程：V4L2 / 图片集循环
│   │   ├── pipeline/               # T2 线程：RGA + EfficientAD-S
│   │   ├── vlm_worker/             # T3 线程：FastSAM + Qwen3-VL-2B/4B
│   │   ├── upload/                 # T4 线程：libcurl multipart
│   │   ├── common/                 # BoundedQueue / UniqueFd / metrics
│   │   └── vlm_bbox_ref.py         # 五级 bbox 净化逻辑参考（仅迁移此一个 _ref 文件）
│   └── third_party/                # rknn-llm-runtime、librga 头文件
├── models/
│   ├── efficientad_models/         # EfficientAD-S 模型 ONNX/RKNN（15 类重做目标）
│   │   ├── metal_nut/
│   │   ├── screw/
│   │   └── pill/  …（共 15 类）
│   ├── fastsam_models/
│   ├── qwen3vl_models/             # *.rkllm + vision *.rknn
│   ├── qwen3vl_lora_adapter/       # Qwen3-VL-2B LoRA adapter 权重（v1 初版 3 类）
│   │   ├── adapter_config.json
│   │   ├── adapter_model.safetensors
│   │   ├── checkpoint-50/           # 训练中间检查点
│   │   ├── checkpoint-100/
│   │   └── checkpoint-150/
│   └── qwen3vl_lora_4b_adapter/    # Qwen3-VL-4B LoRA adapter 权重（Phase 5.5b 产出）
├── backend/                        # 轨道 A：FastAPI
│   ├── app/
│   │   ├── main.py                 # lifespan + ConnectionManager 注入
│   │   ├── db.py                   # SQLAlchemy async engine + session + TZDateTime
│   │   ├── routers/{edge,defects,stats,health,ws}.py
│   │   ├── models/                 # SQLAlchemy 2.0
│   │   ├── schemas/                # Pydantic v2
│   │   └── ws/manager.py
│   ├── static/defects/             # 缺陷图片落盘目录（按日期分子目录）
│   ├── vision.db                   # SQLite WAL 模式
│   └── tests/contract/             # pytest 契约测试
├── frontend/                       # 轨道 A：Next.js 15 App Router
│   ├── app/
│   ├── components/{ui,v2}/         # ui=shadcn 基础组件，v2=Phase 3.7 V2 设计稿组件
│   ├── lib/{mock-data,ws,api,utils}.ts
│   ├── types/{defect,stats}.ts
│   └── tailwind / postcss config
├── simulator/                      # 轨道 A：Python 模拟器（契约测试客户端）
│   ├── line_runner.py              # 多线程模拟多产线 + 静态图片集循环
│   └── mvtec/                      # MVTec AD 解压目录（gitignore）
├── scripts/
│   ├── train_efficientad.py         # EfficientAD-S 训练（Anomalib 2.x）
│   ├── convert_efficientad_rknn.py  # EfficientAD ONNX → RKNN INT8（原 convert_efficientad.py）
│   ├── convert_fastsam_onnx.py      # FastSAM PyTorch → ONNX
│   ├── convert_fastsam_rknn.py      # FastSAM ONNX → RKNN INT8
│   ├── mvtec_mask_to_json.py        # MVTec GT Mask → DefectCreate JSON 标注
│   ├── format_llama_factory_data.py # JSON 标注 → LLaMA-Factory ShareGPT 格式
│   ├── split_lora_data.py           # MVTec test 集 70/30 分层划分（LoRA 训练/评估隔离）
│   └── eval_ab_test.py              # PC 端 AB 方案评估（JSON 成功率对比）
├── datasets/                        # LoRA 数据集（dataset_info.json + lora_split/）
├── debug/                           # 临时调试脚本，如 debug_lora.py（gitignore）
├── imagenette/                      # EfficientAD-S 训练用辅助数据集（gitignore，~1.5GB）
├── logs/                            # 训练/转换日志输出（gitignore）
├── results/                         # AB 评估结果（ab_eval_report.json + ab_eval_report_v2.json）
├── temp_docs/                       # 过程文档与脚本修改意见草稿（gitignore）
├── qwen3vl_lora.yaml               # LLaMA-Factory LoRA 训练配置（2B）
├── qwen3vl_lora_4b.yaml            # LLaMA-Factory LoRA 训练配置（4B，Phase 5.5b）
├── .claude/
│   └── skills/
│       └── rk3588-deployment/SKILL.md
└── pyproject.toml
```

> 旧仓库 `vlm-sam-industrial-vision` 的 `configs/`、`datasets/`、`padim_ref.py`、`feature_extractor_ref.py`、Streamlit UI 全部**不复制**，只迁移 `edge/src/vlm_bbox_ref.py`。

## 全局核心约束

### MUST（必须遵守）

1. **三段式流水线顺序固定**：Stage 1 EfficientAD-S → Stage 2 FastSAM → Stage 3 Qwen3-VL-2B/4B。Stage 3 通过 `edge/config.yaml` 的 `vlm_model_size` 切换 2B/4B。
2. **数据集**：MVTec AD 全 15 类（Phase 5 重做目标）；扩展类别需经评审。
3. **图片传输**：所有边缘→后端图片走 `multipart/form-data`；后端落盘到 `static/defects/{YYYYMMDD}/{uuid}.jpg`，前端用 `<img src>` 直接引用。
4. **WebSocket 范围**：仅存在于「后端 ↔ 前端」一段；RK3588 端只做 HTTP POST 客户端。
5. **配置分离**：边缘端配置写在 `edge/config.yaml`，后端配置写在 `backend/.env`，不复用。
6. **C++ 异步模型**：固定 4 线程（Capture / Pipeline / VLM Worker / Upload），线程间用 `BoundedQueue<T>` + drop-oldest 解耦。
7. **现代 C++**：使用 `std::jthread` + `std::stop_token` + `std::condition_variable_any` 协作式取消；GCC ≥ 11；`#pragma once`；成员变量 trailing underscore。
8. **VLM 输出契约**：Qwen3-VL-2B 必须输出可解析 JSON（含 `bbox` / `category` / `severity` / `confidence`）；解析失败计入 metrics 并丢弃。
9. **AB 测试 4 变体 2×2 矩阵**：4 个变体（`2B_base` / `2B_lora` / `4B_base` / `4B_lora`）按模型尺寸 × 微调模式组合评估，每条样本记录 JSON 解析成功率、TTFT、tokens/s、内存占用，落库 `defects.variant` 字段。
10. **接口契约优先**：任何 RK3588 端字段变化必须先改 `docs/API_CONTRACT.md` 并同步模拟器，再改 C++ 代码。

### MUST NOT（必须避免）

1. **不使用 Base64** 传图，任何场景。
2. **不生成检测报告**（PDF / Markdown / LLM 综述都不做），项目范围只到「单帧 JSON + 图片」上报。
3. **不引入 Streamlit / Gradio** 或任何旧 UI 残留。
4. **不使用视频流模拟产线**，不用 iPad 投影 / OBS 虚拟摄像头（引入光学退化干扰算法验证）。
5. **不复制旧仓库的 `configs/`、`datasets/`、`padim_ref.py`、`feature_extractor_ref.py`**。
6. **不在 RK3588 端起 WebSocket 服务**或 Web 服务器（FastAPI/Flask 等）；**边缘端只跑 C++ 推理引擎**。
7. **不在边缘端做 PaDiM/PatchCore 类位置敏感方法**（已被 EfficientAD-S 替代）。
8. **不混用 Pydantic v1 写法**（`orm_mode` / `parse_obj` / `dict()` 全部禁用）。
9. **不使用 Tailwind v3 配置**（`tailwind.config.ts` 不再使用，全部走 CSS `@theme`）。
10. **不在 `'use client'` 文件中导入服务端独占模块**；浏览器 API 必须有 `typeof window` 守卫。

## 阶段感知约束

- **轨道 A（Python：后端 / 前端 / 模拟器）**：
  板子到货前先跑通端到端契约，功能正确优先，性能不是重点。模拟器充当 RK3588 替身，完整覆盖所有接口路径。

- **轨道 B（C++：RK3588 推理流水线）**：
  板子到货后直接按**性能版**开发，无原型阶段。C++ 代码从一开始就按零拷贝、INT8/W8A8 量化、三核 NPU 并行的标准写。具体约束见 `.claude/skills/rk3588-deployment/SKILL.md`。

## 16GB 板约束（实际硬件：香橙派 5 16GB）

- **`max_context` 上限 4096**。
- **不在 RK3588 上同时跑模拟器**：模拟器只在 PC 端运行；上板后真机直接跑 C++ 推理引擎。
- **单进程共享同一套模型实例**：T1 线程可循环读取多个类别的图片集模拟多产线节拍，内存占用不变；**禁止**开多个独立进程各自加载 VLM（每个 Qwen3-VL-2B 实例 ~3.1 GB）。含 4B 时 Pipeline 总峰值约 11.4 GB，裕度 ~3.1 GB；**禁止**同时加载 2B 和 4B。

## AB 测试方案概要（4 变体 2×2 矩阵）

| 变体 ID | 模型 | 模式 | Prompt 策略 |
|---|---|---|---|
| `2B_base` | Qwen3-VL-2B | 基座 W8A8 | 工程化 Prompt (~300 tokens) |
| `2B_lora` | Qwen3-VL-2B | LoRA W8A8 | 极简 Prompt (~50 tokens) |
| `4B_base` | Qwen3-VL-4B | 基座 W8A8 | 工程化 Prompt (~300 tokens) |
| `4B_lora` | Qwen3-VL-4B | LoRA W8A8 | 极简 Prompt (~50 tokens) |

四维评估：JSON 解析成功率（%）、TTFT（首 token 延迟，ms）、decode tokens/s、运行时 RAM 占用（GB）。后端 `/api/stats` 直接聚合四变体对比。PC 阶段先用 transformers 测精度上界（仅比较 JSON 解析成功率，GPU 延迟不作为指标），RK3588 阶段实测全部四维指标。

## 两轨道并行开发

| 轨道 | 主导 | 范围 | 时机 |
|---|---|---|---|
| A | Claude Code | 后端 + 前端 + 模拟器 + 接口契约 | 板子到货之前 |
| B | Claude Code（开发者测试验收） | RKNN/RKLLM 模型转换 + C++ 四线程流水线 | 板子到货之后 |

解耦机制：`docs/API_CONTRACT.md` 是唯一权威接口。模拟器在轨道 A 期间充当 RK3588 替身，跑通完整链路；轨道 B 落地时只需让 C++ 实现匹配同一份契约即可替换。

## 参考文件说明

仅迁移 **`edge/src/vlm_bbox_ref.py`**（约 200 行 Python，包含五级 bbox 净化逻辑：归一化范围裁剪 → 面积过滤 → 长宽比过滤 → IoU 去重 → 置信度阈值）。C++ 端按此逻辑等价重写；不要逐行翻译，理解算法后用 `std::span<float>` + `<ranges>` 重构。

`padim_ref.py`、`feature_extractor_ref.py` **不复制**——PaDiM 路线已废弃。

## 进一步阅读入口

- 8 阶段执行指南（按顺序读，含指令示例）：`docs/PROJECT_TIMELINE.md`
- 系统架构与时序图：`docs/ARCHITECTURE.md`
- HTTP / WebSocket 接口契约：`docs/API_CONTRACT.md`
- RK3588 部署专家指令（按需触发）：`.claude/skills/rk3588-deployment/SKILL.md`
- 上板手册（编译、烧录、调试）：`docs/DEPLOYMENT.md`（后期补充）
