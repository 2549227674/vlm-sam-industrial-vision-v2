# vlm-sam-industrial-vision-v2

端云分离架构的工业视觉 AI 检测流水线：**RK3588 边缘端**（三阶段异步推理）-> **FastAPI 后端** -> **Next.js 仪表盘**（实时可观测性）。

## 系统架构

```text
RK3588 16GB 边缘端 (Orange Pi 5 Plus)
  T1: V4L2 图像采集
  T2: EfficientAD-S (FP16 raw RKNN) -> 负载削减门控
  T3: FastSAM (FP16 RKNN) bbox 提案 + Qwen3-VL-2B (W8A8 RKLLM) 结构化 JSON
  T4: libcurl multipart 上传
      |
      v
FastAPI 后端 (Python 3.12, SQLAlchemy 2.0, SQLite WAL)
      |
      v
Next.js 15 仪表盘 (纯静态导出, WebSocket 实时推送, TanStack Table, SVG 图表)
```

| 阶段 | 模型 | 角色 | 量化 |
|------|------|------|------|
| T2 | EfficientAD-S | 负载削减门控（anomaly score 阈值） | FP16/no-quant RKNN |
| T3 | FastSAM-s | bbox 提案（mask decode 待实现） | FP16/no-quant RKNN |
| T3 | Qwen3-VL-2B | 结构化 JSON 描述（defect_type, severity, confidence, bbox） | W8A8 RKLLM |

## 核心设计决策

- **四线程异步流水线**：BoundedQueue + drop-oldest 背压（Q1=4, Q2=2, Q3=4）
- **API contract v1.2** 作为边缘端与后端的唯一权威接口（`docs/API_CONTRACT.md`）
- **Multipart/form-data** 传输图片，禁止 Base64
- **MVTec AD 全 15 类**覆盖多种工业缺陷类型
- **AB 测试 2×2 矩阵**：模型尺寸 (2B/4B) × 微调模式 (base/LoRA)，评估 JSON 解析率、TTFT、decode TPS、RSS

## 项目展示能力

- 在资源受限硬件（16GB RAM, 6 TOPS NPU）上实现端到端边缘-云流水线
- 三阶段推理编排与背压管理
- 量化感知工程（FP16 vs W8A8 权衡，详见 `docs/ENGINEERING_FINDINGS.md`）
- 结构化 VLM 输出与 JSON schema 校验
- 实时可观测仪表盘，逐帧 trace_events 与四变体指标

## 当前状态

- **主线**：EfficientAD-S FP16 raw RKNN -> FastSAM FP16/no-quant RKNN -> Qwen3-VL-2B base W8A8 RKLLM
- **发布验证**：2B base threshold 模式通过 30.2 分钟 soak test——0 崩溃、0 队列丢帧、100% json_parse_ok、RSS 稳定（~3322 MB）
- **契约测试**：74/74 通过；前端 typecheck/build 无错误
- **4B base**：spatial merge 已修复（2x2 permute），carpet 回归 5/5 json_ok。因延迟（1.8×）和回归覆盖有限，仍为扩展候选
- **EfficientAD-S**：负载削减门控，非精确缺陷分类器（raw_score mean AUROC 0.5320）
- **LoRA**：PC bf16 有效；RK3588 W8A8 下细粒度 defect_type 增益坍塌
- **FastSAM**：仅输出 bbox 提案；mask decode 仍为未来工作
- **BBox overlay**：proposal-level，非 verified ground-truth localization。EAD heatmap 定位已评估，发现对类别/缺陷类型有依赖性（详见 `docs/experiments/phase9_ead_localization_reliability.md`）
- **前端 Demo**：优先 Live API → 真实 RK3588 快照 → Mock 回退。数字孪生 NPU/CPU 面板为架构可视化，非实时硬件监控

## 数据源真实性说明

仪表盘采用三级数据优先级：

1. **Live API** — 从运行中的 FastAPI 后端获取 `GET /api/defects` + `GET /api/stats`（RK3588 上传时为实时数据）
2. **真实 RK3588 快照** — 来自真实 RK3588 soak test 的历史记录（`/demo-data/real_run_latest/`），包含真实图片、pipeline_ms、vlm_metrics 和 trace_events
3. **Mock 回退** — 客户端生成的合成数据（无真实图片，无真实流水线时序）

**非实时硬件监控**：RK3588Twin 数字孪生的 NPU/CPU 负载条是架构可视化，展示三阶段流水线结构，不是实时硬件利用率遥测。真实可观测数据来自逐帧 `pipeline_ms`、`vlm_metrics`（TTFT、decode_tps、RSS）和 `trace_events`。

## 公网 Demo

- **前端**：https://vision.hanlab.app/
- **API 探针**：https://api.vision.hanlab.app/api/health
- **数据来源**：Live 后端 API，已 seed 真实 RK3588 测试快照（20 条记录，3 个 MVTec AD 类别）。后续 RK3588 上传会追加到同一后端。

仪表盘明确标注当前展示的是 Live 后端数据、真实 RK3588 历史快照、模拟器数据还是 Mock 回退数据（中英双语）。

## 项目结构

| 目录 | 说明 |
|------|------|
| `edge/` | C++17 四线程推理流水线（RKNN + RKLLM + librga + libcurl + V4L2） |
| `backend/` | FastAPI 服务端（REST + WebSocket + SQLAlchemy 2.0 async） |
| `frontend/` | Next.js 15 静态仪表盘（App Router + shadcn/ui + Tailwind v4） |
| `simulator/` | Python 多线程模拟器（RK3588 替身，用于契约测试） |
| `scripts/` | 训练、模型转换、评估与 prompt 优化脚本 |
| `docs/` | 架构设计、API 契约、部署手册、实验报告 |

## 快速开始

### 后端

```bash
cd backend && uvicorn app.main:app --reload --port 8000
pytest backend/tests/contract/ -v    # 契约测试
```

### 前端

```bash
cd frontend && npm install && npm run dev    # localhost:3000
npm run build                                 # 静态导出到 out/
```

### 模拟器

```bash
cd simulator && python line_runner.py
```

### 边缘端（RK3588 交叉编译）

```bash
cd edge
cmake -DCMAKE_TOOLCHAIN_FILE=aarch64-toolchain.cmake -B build
cmake --build build -j$(nproc)
scp build/edge_pipeline orangepi@192.168.137.66:/home/orangepi/
```

## 文档导航

- [系统架构](docs/ARCHITECTURE.md) — 组件图、数据流、模型细节
- [API 契约 v1.2](docs/API_CONTRACT.md) — 边缘端-后端接口规范
- [工程发现](docs/ENGINEERING_FINDINGS.md) — 量化问题、排障、解决方案
- [边缘部署总结](docs/reports/edge_deployment_summary.md) — Phase 7/8/9 全量板端结果
- [项目时间线](docs/PROJECT_TIMELINE.md) — 8 阶段执行计划

## 技术栈

| 层级 | 技术 |
|------|------|
| 边缘硬件 | Orange Pi 5 Plus 16GB（RK3588, 6 TOPS NPU ×3） |
| 边缘运行时 | C++17, librknnrt, librkllmrt, librga, libcurl, V4L2 |
| 后端 | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2 |
| 前端 | Next.js 15, React 19, Tailwind v4, shadcn/ui, TanStack Table v8 |
| 数据集 | MVTec AD（15 类, CC BY-NC-SA 4.0） |

## 许可

本项目用于课程设计与求职作品集展示。
