# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

端云分离架构的工业视觉 AI 检测项目：边缘端 RK3588 16GB 跑三段式异步推理流水线（EfficientAD-S → FastSAM → Qwen3-VL-2B），后端 FastAPI 收单与广播，前端 Next.js 仪表盘做可视化。本文档是 Claude Code 在本仓库的总入口，定义全局约束与导航。

## 当前实现状态

**Phase 5-6 已完成，Phase 1-4（轨道A）尚未开始**

已完成：
- Phase 5.1：EfficientAD-S 训练 + ONNX 导出（三类别全部完成）
- Phase 5.2：FastSAM-s ONNX 导出（fastsam_s.onnx 46MB）
- Phase 5.3：LoRA 数据划分（240 train / 113 eval）
- Phase 5.4：MVTec GT Mask 自动标注（mvtec_mask_to_json.py）
- Phase 5.5：Qwen3-VL-2B LoRA 微调（AutoDL，train_loss=1.073）
- Phase 5.6：PC 端 AB 评估（方案A=100%，方案B=100%）
- Phase 6：全部模型转换（EfficientAD RKNN / FastSAM RKNN / Qwen3-VL .rkllm）

尚未开始（下一步）：
- Phase 1-4：轨道A——后端 FastAPI + 模拟器 + 前端 Next.js + 契约测试全绿
  见 `docs/PROJECT_TIMELINE.md` 阶段 1-4

## 一句话定义

**RK3588 16GB 边缘端做异常检测 + 分割 + VLM 结构化描述，HTTP 上报到云端 FastAPI，WebSocket 实时推送给 Next.js 仪表盘**；面向本科课程设计 / 求职作品集，方向是端侧 AI 部署推理优化。

## 技术栈一览

| 分层 | 关键技术 | 版本/备注 |
|---|---|---|
| 边缘端硬件 | **RK3588 16GB**（Orange Pi 5 Plus 16GB） | 6 TOPS NPU，三核并行 |
| 边缘端运行时 | C++17/20、librknnrt、librkllmrt、librga、libcurl、V4L2 | rknn-llm v1.2.3+、rknn-toolkit2 v2.2+、GCC ≥ 11 |
| Stage 1 异常检测 | EfficientAD-S（PDN, 256×256, INT8） | Anomalib 2.x → 单一 ONNX → 单个 RKNN |
| Stage 2 分割 | FastSAM-s（640×640, INT8） | YOLOv8-seg 衍生 |
| Stage 3 VLM | Qwen3-VL-2B-Instruct W8A8 | airockchip 官方 + Qengineering 镜像 |
| 后端 | Python 3.12、FastAPI 0.115+、SQLAlchemy 2.0 async、aiosqlite、Pydantic v2 | 生产单 worker（ConnectionManager 进程内单例）|
| 前端 | Next.js 15 App Router（`output: 'export'` 纯静态导出）、React 19、Tailwind v4、shadcn/ui、ECharts 5.6 | sonner / TanStack Table v8 |
| 模拟器 | Python 多线程 + 静态图片集循环 | 充当 RK3588 替身做契约测试 |
| 数据集 | MVTec AD：metal_nut / screw / pill | CC BY-NC-SA 4.0 |
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

> **注意**：需要创建 `.gitignore`（当前缺失）。至少应忽略：`.venv/`、`.idea/`、`simulator/mvtec/`（大数据集）、`backend/vision.db`、`backend/static/defects/`、`*.pyc`、`__pycache__/`、`node_modules/`、`frontend/out/`、`build/`。



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
│   │   ├── vlm_worker/             # T3 线程：FastSAM + Qwen3-VL-2B
│   │   ├── upload/                 # T4 线程：libcurl multipart
│   │   ├── common/                 # BoundedQueue / UniqueFd / metrics
│   │   └── vlm_bbox_ref.py         # 五级 bbox 净化逻辑参考（仅迁移此一个 _ref 文件）
│   └── third_party/                # rknn-llm-runtime、librga 头文件
├── models/
│   ├── efficientad_models/         # EfficientAD-S 三类模型 ONNX/RKNN
│   │   ├── metal_nut/
│   │   ├── screw/
│   │   └── pill/
│   ├── fastsam_models/
│   └── qwen3vl_models/             # *.rkllm + vision *.rknn
├── backend/                        # 轨道 A：FastAPI
│   ├── app/
│   │   ├── main.py                 # lifespan + ConnectionManager 注入
│   │   ├── routers/{edge,defects,stats,health,ws}.py
│   │   ├── models/                 # SQLAlchemy 2.0
│   │   ├── schemas/                # Pydantic v2
│   │   └── ws/manager.py
│   ├── static/defects/             # 缺陷图片落盘目录（按日期分子目录）
│   ├── vision.db                   # SQLite WAL 模式
│   └── tests/contract/             # pytest 契约测试
├── frontend/                       # 轨道 A：Next.js 15 App Router
│   ├── app/
│   ├── components/{ui,charts,layout,data-table}/
│   ├── lib/{echarts,ws,api}.ts
│   └── tailwind / postcss config
├── simulator/                      # 轨道 A：Python 模拟器（契约测试客户端）
│   ├── line_runner.py              # 多线程模拟多产线 + 静态图片集循环
│   └── mvtec/                      # MVTec AD 解压目录（gitignore）
├── scripts/
│   ├── convert_efficientad.py      # ONNX → RKNN INT8
│   ├── convert_qwen3vl.py          # HF → RKLLM W8A8
│   ├── mvtec_mask_to_yolo.py       # MVTec ground_truth/ 像素掩码 → YOLO bbox
│   └── split_lora_data.py          # MVTec test 集 70/30 分层划分（LoRA 训练/评估隔离）
├── .claude/
│   └── skills/
│       └── rk3588-deployment/SKILL.md
└── pyproject.toml
```

> 旧仓库 `vlm-sam-industrial-vision` 的 `configs/`、`datasets/`、`padim_ref.py`、`feature_extractor_ref.py`、Streamlit UI 全部**不复制**，只迁移 `edge/src/vlm_bbox_ref.py`。

## 全局核心约束

### MUST（必须遵守）

1. **三段式流水线顺序固定**：Stage 1 EfficientAD-S → Stage 2 FastSAM → Stage 3 Qwen3-VL-2B。
2. **数据集**：MVTec AD 三类（metal_nut / screw / pill）；扩展类别需经评审。
3. **图片传输**：所有边缘→后端图片走 `multipart/form-data`；后端落盘到 `static/defects/{YYYYMMDD}/{uuid}.jpg`，前端用 `<img src>` 直接引用。
4. **WebSocket 范围**：仅存在于「后端 ↔ 前端」一段；RK3588 端只做 HTTP POST 客户端。
5. **配置分离**：边缘端配置写在 `edge/config.yaml`，后端配置写在 `backend/.env`，不复用。
6. **C++ 异步模型**：固定 4 线程（Capture / Pipeline / VLM Worker / Upload），线程间用 `BoundedQueue<T>` + drop-oldest 解耦。
7. **现代 C++**：使用 `std::jthread` + `std::stop_token` + `std::condition_variable_any` 协作式取消；GCC ≥ 11；`#pragma once`；成员变量 trailing underscore。
8. **VLM 输出契约**：Qwen3-VL-2B 必须输出可解析 JSON（含 `bbox` / `category` / `severity` / `confidence`）；解析失败计入 metrics 并丢弃。
9. **AB 测试两轴评估**：每条样本同时记录方案 A（Base + Prompt 工程）与方案 B（LoRA + 极简 Prompt）的 JSON 解析成功率、TTFT、tokens/s、内存占用，落库 `defects.variant` 字段。
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
- **单进程共享同一套模型实例**：T1 线程可循环读取 metal_nut / screw / pill 多个类别的图片集模拟多产线节拍，内存占用不变；**禁止**开多个独立进程各自加载 VLM（每个 Qwen3-VL-2B 实例 ~3.1 GB）。

## AB 测试方案概要

两个变体并行评估，同一组测试图分别走两条路径：

- **方案 A**：Qwen3-VL-2B-Instruct **base 模型** + 工程化 Prompt（含 few-shot 示例、JSON schema、严格指令），prompt 长度约 800–1500 tokens。
- **方案 B**：Qwen3-VL-2B-Instruct **LoRA 微调**（rank 16，MVTec AD 工业 JSON 标注数据集）+ 极简 Prompt（≤ 100 tokens）。

四维评估：JSON 解析成功率（%）、TTFT（首 token 延迟，ms）、decode tokens/s、运行时 RAM 占用（GB）。后端 `/api/stats` 直接聚合两变体对比。PC 阶段先用 transformers 测精度上界（仅比较 JSON 解析成功率，GPU 延迟不作为指标），RK3588 阶段实测全部四维指标。

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
