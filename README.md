# vlm-sam-industrial-vision-v2

端云分离架构的工业视觉 AI 检测流水线：**RK3588 边缘端**（三阶段异步推理）-> **FastAPI 后端** -> **Next.js 仪表盘**（实时可观测性）。

## 当前状态：Phase 10 v1

Phase 10 v1 引入有监督 YOLOv8n-detect localizer（ORT CPU fallback），替代 FastSAM/VLM 作为 T3 定位方案。

```text
RK3588 16GB 边缘端 (Orange Pi 5 Plus)
  T1: V4L2 图像采集
  T2: EfficientAD-S (FP16 raw RKNN) -> 负载削减门控
  T3: YOLOv8n-detect (ORT CPU) -> defect_type + confidence + bbox
  T4: libcurl multipart 上传
```

| 阶段 | 模型 | 角色 | 运行时 |
|------|------|------|--------|
| T2 | EfficientAD-S | 负载削减门控（anomaly score 阈值） | FP16/no-quant RKNN |
| T3 | YOLOv8n-detect | 缺陷定位 + 分类（12 类） | ONNX Runtime CPU FP32 |

**Scope**: metal_nut + cable（2 类，12 defect type）。不支持的类别产生 fallback 报告。

**ORT CPU fallback 说明**: 这是 ONNX Runtime CPUExecutionProvider 在 RK3588 上的推理，不是 RKNN/NPU。RKNN numeric consistency 仍为 BLOCKED（rknn-toolkit2 2.3.2 issue）。

**VLM 状态**: Phase 10 v1 不调用 VLM。observation_source="template"，severity 固定 "medium"。observation/severity_reason enrichment 属于 Phase 10.1 范围。

**Extended RK3588 Soak**: 27m27s, 2082 frames, 0 crashes, 0 HTTP 400, RSS=34MB stable, localizer avg=187.7ms, p95=215.0ms。

**API**: contract v1.3，schema_version 保持 "v1"，新增可选 source tracking 字段（localization_source, label_source, observation_source）。

**Snapshot**: 40 curated records from soak backend，仅包含真实 YOLO 检测（confidence > 0，无 fallback 框）。

**Caution**: supervised POC trained from MVTec GT masks, not standard unsupervised MVTec benchmark.

## Phase 9 历史主线

Phase 9 主线（已由 Phase 10 v1 替代 T3）：

```text
T3: FastSAM (FP16 RKNN) bbox 提案 + Qwen3-VL-2B (W8A8 RKLLM) 结构化 JSON
```

Phase 9 发布验证：2B base threshold 模式通过 30.2 分钟 soak test，0 崩溃、0 队列丢帧、100% json_parse_ok。详见 `docs/reports/edge_deployment_summary.md`。

## 系统架构

```text
RK3588 16GB 边缘端 (Orange Pi 5 Plus)
  T1: V4L2 图像采集
  T2: EfficientAD-S (FP16 raw RKNN) -> 负载削减门控
  T3*: YOLOv8n-detect (ORT CPU) 或 FastSAM+VLM (RKNN/RKLLM)
  T4: libcurl multipart 上传
      |
      v
FastAPI 后端 (Python 3.12, SQLAlchemy 2.0, SQLite WAL)
      |
      v
Next.js 15 仪表盘 (纯静态导出, WebSocket 实时推送, TanStack Table, SVG 图表)
```

## 核心设计决策

- **四线程异步流水线**：BoundedQueue + drop-oldest 背压（Q1=4, Q2=2, Q3=4）
- **API contract v1.3** 作为边缘端与后端的唯一权威接口（`docs/API_CONTRACT.md`）
- **Multipart/form-data** 传输图片，禁止 Base64
- **MVTec AD** 数据集，Phase 10 v1 覆盖 metal_nut + cable（2 类 12 defect type）
- **AB 测试 4 变体**：2×2 矩阵（模型尺寸 × 微调模式），评估 JSON 解析率、TTFT、decode TPS、RSS

## 公网 Demo

- **前端**：https://vision.hanlab.app/
- **API**：https://vision.hanlab.app/api/health
- **数据来源**：Live 后端 API + Phase 10 ORT snapshot fallback（40 条 curated 记录，metal_nut + cable）

## 项目结构

| 目录 | 说明 |
|------|------|
| `edge/` | C++17 四线程推理流水线（RKNN + ORT + librga + libcurl + V4L2） |
| `backend/` | FastAPI 服务端（REST + WebSocket + SQLAlchemy 2.0 async） |
| `frontend/` | Next.js 15 静态仪表盘（App Router + shadcn/ui + Tailwind v4） |
| `simulator/` | Python 多线程模拟器（RK3588 替身，用于契约测试） |
| `scripts/phase10/` | ORT localizer 脚本、训练、评估 |
| `docs/` | 架构设计、API 契约、部署手册、实验报告 |

## 快速开始

### 后端

```bash
cd backend && uvicorn app.main:app --reload --port 8000
pytest backend/tests/contract/ -v
```

### 前端

```bash
cd frontend && npm install && npm run dev
NEXT_PUBLIC_API_BASE=https://vision.hanlab.app npm run build  # 部署到远程
```

### 模拟器

```bash
cd simulator && python line_runner.py
```

## 文档导航

- [系统架构](docs/ARCHITECTURE.md)
- [API 契约 v1.3](docs/API_CONTRACT.md)
- [Phase 10 ORT 集成计划](docs/experiments/phase10_ort_integration_plan.md)
- [Phase 10 Snapshot Demo](docs/experiments/phase10_snapshot_demo_plan.md)
- [工程发现](docs/ENGINEERING_FINDINGS.md)
- [项目时间线](docs/PROJECT_TIMELINE.md)

## 技术栈

| 层级 | 技术 |
|------|------|
| 边缘硬件 | Orange Pi 5 Plus 16GB（RK3588, 6 TOPS NPU ×3） |
| 边缘运行时 | C++17, librknnrt, ONNX Runtime, librga, libcurl, V4L2 |
| 后端 | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2 |
| 前端 | Next.js 15, React 19, Tailwind v4, shadcn/ui, TanStack Table v8 |
| 数据集 | MVTec AD（CC BY-NC-SA 4.0） |

## 许可

本项目用于课程设计与求职作品集展示。
