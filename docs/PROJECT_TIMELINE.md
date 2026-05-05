# vlm-sam-industrial-vision-v2 项目阶段步骤指导指南

> 基于 CLAUDE.md、ARCHITECTURE.md、API_CONTRACT.md、SKILL.md 四件套文档编写。
> 所有引用均标注出处文档和章节号。

---

## 全局时间线总览

```
阶段 0  准备工作（你手动）                    ← 你现在在这里
阶段 1  轨道A：后端 FastAPI                   ← Claude Code 主导
阶段 2  轨道A：模拟器 + 契约测试               ← Claude Code 主导
阶段 3  轨道A：前端 Next.js                   ← Claude Code 主导
阶段 4  轨道A 联调验收                        ← 你验证
阶段 5  PC 端模型训练与 AB 评估（可与 1-4 并行） ← 混合（脚本 Claude Code 写，训练你跑）
阶段 6  轨道B：模型转换                       ← 板子到货前后
阶段 7  轨道B：C++ 四线程流水线                ← Claude Code + 你上板测试
阶段 8  全链路验收 + 数据对比                  ← 你验证
```

---

## 阶段 0：准备工作

**时间预估**：0.5-1 天

### 0.1 创建仓库 + 放置四件套文档

**执行人**：你手动

```bash
mkdir vlm-sam-industrial-vision-v2
cd vlm-sam-industrial-vision-v2
git init

# 放置文档
cp CLAUDE.md ./
mkdir -p docs .claude/skills/rk3588-deployment
cp ARCHITECTURE.md docs/
cp API_CONTRACT.md docs/
cp SKILL.md .claude/skills/rk3588-deployment/
```

**完成标志**：四份文件在正确路径，`git status` 能看到。

### 0.2 下载 MVTec AD 数据集

**执行人**：你手动（需注册）

- 官网：https://www.mvtec.com/company/research/datasets/mvtec-ad
- 只需下载三个类别：**metal_nut**、**screw**、**pill**
- 解压到 `simulator/mvtec/` 目录

```
simulator/mvtec/
├── metal_nut/
│   ├── train/good/          ← EfficientAD-S 训练用（阶段5）
│   └── test/
│       ├── good/
│       ├── bent/
│       ├── color/
│       ├── flip/
│       └── scratch/         ← 模拟器读这些图发请求
├── screw/
│   ├── train/good/
│   └── test/...
└── pill/
    ├── train/good/
    └── test/...
```

**数据集许可**：CC BY-NC-SA 4.0（来源：CLAUDE.md 技术栈表）

**完成标志**：`ls simulator/mvtec/metal_nut/test/scratch/` 能看到 .png 文件。

### 0.3 确认本机环境

**执行人**：你手动

```bash
node --version     # ≥ 18（Next.js 15 要求）
python --version   # 3.11+（FastAPI + Anomalib 要求）
git --version      # 任意版本
nvidia-smi         # 确认 RTX 4060 可用（阶段5 训练用）
```

**完成标志**：三个命令都有正确输出。

### 0.4 安装 Claude Code 插件

**执行人**：你手动

根据前序对话已安装的：
- claude-md-management、code-review、context7、feature-dev、frontend-design、github（已装）
- pyright-lsp、typescript-lsp（推荐现在装）
- clangd-lsp（阶段7再装）

---

## 阶段 1：轨道A — 后端 FastAPI

**时间预估**：1-2 天（Claude Code 编写 + 你审查）
**前置依赖**：阶段 0 完成
**文档依据**：API_CONTRACT.md 全文、ARCHITECTURE.md §2.2、CLAUDE.md MUST#3/4/8

### 1.1 项目骨架初始化

**执行人**：Claude Code

**指令示例**：
```
读取 CLAUDE.md、docs/ARCHITECTURE.md、docs/API_CONTRACT.md，
按仓库目录结构初始化项目骨架，从轨道A开始：
建 backend/、frontend/、simulator/ 的完整目录结构，
生成 pyproject.toml、package.json 等依赖配置文件。
```

**预期产出**：
- `backend/app/main.py`（lifespan 骨架）
- `backend/app/routers/`（edge.py, defects.py, stats.py, health.py, ws.py 空文件）
- `backend/app/models/`（SQLAlchemy 2.0 模型骨架）
- `backend/app/schemas/`（Pydantic v2 schema 骨架）
- `backend/app/ws/manager.py`（ConnectionManager 骨架）
- `frontend/`（Next.js 15 初始化）
- `simulator/`（目录结构）
- `pyproject.toml`、`frontend/package.json`

**完成标志**：`tree -L 3` 输出与 CLAUDE.md 仓库目录总览一致。

### 1.2 Pydantic v2 Schema 实现

**执行人**：Claude Code
**文档依据**：API_CONTRACT.md §2

**具体要求**（逐字段对照 API_CONTRACT.md §2）：
- `BBox`：x/y/w/h 归一化 [0,1]，`extra="forbid"`
- `VlmMetrics`：ttft_ms / decode_tps / prompt_tokens / output_tokens / rss_mb / json_parse_ok
- `DefectCreate`：所有字段类型、约束、默认值严格按文档
- `DefectRead`：继承 `DefectCreate`，加 id / image_url / server_ts，`from_attributes=True`

**关键检查点**（CLAUDE.md MUST-NOT#8）：
- 不使用 `orm_mode`（v1 写法）→ 必须用 `model_config = ConfigDict(from_attributes=True)`
- 不使用 `.dict()` → 必须用 `.model_dump()`
- 不使用 `parse_obj` → 必须用 `model_validate`

**完成标志**：`python -c "from backend.app.schemas.defect import DefectCreate; print('OK')"` 无报错。

### 1.3 SQLAlchemy 2.0 数据库模型

**执行人**：Claude Code
**文档依据**：ARCHITECTURE.md §2.2、§9.1

- 使用 `aiosqlite` 异步驱动
- SQLite WAL 模式
- `defects` 表字段与 `DefectCreate` 一一对应
- `variant` 字段为 `Literal["A", "B"]`（API_CONTRACT.md §2）

**完成标志**：`alembic` 或启动时自动建表成功，`vision.db` 文件生成。

### 1.4 POST `/api/edge/report` 路由

**执行人**：Claude Code
**文档依据**：API_CONTRACT.md §3

**实现要点**（逐条对照文档）：
- Content-Type: `multipart/form-data`
- Form 字段：`image`（必填 JPEG）、`meta`（必填 JSON 字符串）、`crop`（可选 JPEG）
- 图片落盘：`UploadFile.read(1024*1024)` 流式写入 `static/defects/{YYYYMMDD}/{uuid4}.jpg`
- 落盘后写 DB
- 写 DB 后 `await ws_manager.broadcast("dashboard", {"type": "defect_created", ...})`

**错误处理**（API_CONTRACT.md §11）：
- 400 VALIDATION_ERROR / INVALID_IMAGE
- 413 PAYLOAD_TOO_LARGE
- 415 UNSUPPORTED_MEDIA_TYPE
- 422 SCHEMA_MISMATCH
- 409 DUPLICATE_REPORT（`line_id + edge_ts` 去重）

**完成标志**：`curl -X POST` 手动测试返回 200 + 正确 JSON。

### 1.5 GET 查询路由

**执行人**：Claude Code
**文档依据**：API_CONTRACT.md §4-7

| 路由 | 要点 |
|---|---|
| `GET /api/defects` | 分页（page/page_size）、过滤（category/severity/variant/line_id/since/until）、排序（`-edge_ts` 默认降序） |
| `GET /api/defects/{id}` | 单条返回 DefectRead，不存在 404 |
| `GET /api/stats` | 聚合统计：total / by_category / by_severity / timeline / ab_compare |
| `GET /api/health` | status/version/uptime_s/db/ws_clients |

**完成标志**：每个路由 curl 能返回正确格式的 JSON。

### 1.6 WebSocket `/ws/dashboard`

**执行人**：Claude Code
**文档依据**：API_CONTRACT.md §8

**ConnectionManager 实现**：
- 进程内单例，存于 `app.state.ws_manager`（ARCHITECTURE.md §2.2）
- 按房间名过滤广播（当前只有 `"dashboard"` 房间）
- `asyncio.Lock` 保护连接集合
- `broadcast` 用 `asyncio.gather(..., return_exceptions=True)`

**消息类型**：
- 服务端发：`hello` / `defect_created` / `metrics_tick`（每 5s）/ `ping`（每 30s）
- 客户端发：`pong` / `subscribe`
- 心跳：30s ping，60s 无 pong 关闭连接

**完成标志**：`websocat ws://localhost:8000/ws/dashboard` 能收到 `hello` 消息。

### 1.7 CORS + StaticFiles + Lifespan

**执行人**：Claude Code
**文档依据**：API_CONTRACT.md §10、ARCHITECTURE.md §9.1

- CORS：`allow_origins=["http://localhost:3000", ...]`，**必须最早注册**
- StaticFiles：开发模式挂载 `static/` 目录
- Lifespan：建表、初始化 ConnectionManager、关闭时清理

**完成标志**：`uvicorn backend.app.main:app --reload` 启动无报错。

---

## 阶段 2：轨道A — 模拟器 + 契约测试

**时间预估**：1 天
**前置依赖**：阶段 1 后端核心路由完成
**文档依据**：ARCHITECTURE.md §4.1/§5、API_CONTRACT.md §13

### 2.1 模拟器 `simulator/line_runner.py`

**执行人**：Claude Code
**文档依据**：ARCHITECTURE.md §4.1、§5

**功能**：
- 读取 `simulator/mvtec/{category}/test/{defect_type}/*.png`
- 每帧构造 `DefectCreate` JSON（fabricated metadata：随机 severity / confidence / anomaly_score 等）
- `multipart/form-data` POST 到后端
- 可配置节拍：`beat_ms=1500` + jitter ±200ms

**多产线模拟**（ARCHITECTURE.md §5）：
- 开 N=3 个 `threading.Thread`，三个类别各一条线
- 每条线独立 `line_id`（L1/L2/L3）+ 独立图片队列
- 同时发 variant="A" 和 variant="B" 的数据（模拟 AB 测试）

**关键约束**（CLAUDE.md MUST-NOT#1/4）：
- **不使用 Base64 传图**，只用 multipart
- **不使用视频流 / iPad 投影 / OBS**

**完成标志**：运行 `python simulator/line_runner.py`，后端日志显示收到请求并落库。

### 2.2 六个契约测试

**执行人**：Claude Code
**文档依据**：API_CONTRACT.md §13

**测试文件清单**（路径 `backend/tests/contract/`）：

| 测试文件 | 覆盖内容 |
|---|---|
| `test_post_report_happy_path.py` | 正常上报 → 200 + 返回 id/image_url/server_ts |
| `test_post_report_validation.py` | 字段缺失 → 400；图片过大 → 413；schema 版本错 → 422；重复 → 409 |
| `test_post_report_retry.py` | 模拟 5xx → 客户端指数退避重试（500ms × 2ⁿ + jitter，最多 5 次） |
| `test_get_defects_pagination.py` | 分页参数、过滤、排序正确性 |
| `test_get_stats_ab_compare.py` | 聚合统计 + AB 对比字段完整性 |
| `test_ws_dashboard_broadcast.py` | WebSocket 连接 → hello → POST 上报 → 收到 defect_created |

**工具**：pytest + httpx（异步 HTTP）+ websockets（WS 测试）

**完成标志**：`pytest backend/tests/contract/ -v` 全绿（6 个文件全 PASSED）。

---

## 阶段 3：轨道A — 前端 Next.js

**时间预估**：2-3 天
**前置依赖**：阶段 1 后端 API 可用
**文档依据**：ARCHITECTURE.md §2.3、CLAUDE.md 技术栈表

### 3.1 Next.js 15 项目初始化

**执行人**：Claude Code

**配置要点**（CLAUDE.md）：
- App Router
- `next.config.ts` 配置 `output: 'export'`（纯静态导出）
- React 19
- Tailwind v4（**不使用 v3 的 `tailwind.config.ts`**，全部走 CSS `@theme`）
- `app/layout.tsx` 保持 Server Component
- 其余业务页面/组件全部 `'use client'`

**完成标志**：`npm run dev` 启动，访问 `localhost:3000` 看到空白仪表盘骨架。

### 3.2 实时缺陷流水 — DataTable

**执行人**：Claude Code

**技术选型**：TanStack Table v8 + shadcn/ui
**数据源**：`GET /api/defects`（初始加载）+ WebSocket `defect_created`（实时追加）
**列**：id / category / defect_type / severity / confidence / variant / edge_ts / image 缩略图

**完成标志**：启动模拟器后，DataTable 实时出现新行。

### 3.3 统计聚合图 — ECharts AB 对比

**执行人**：Claude Code

**数据源**：`GET /api/stats`
**图表**：
- 缺陷类别分布饼图（by_category）
- 严重度分布柱状图（by_severity）
- 时间线折线图（timeline）
- AB 对比卡片（JSON 解析成功率 / avg_ttft_ms / avg_decode_tps / avg_rss_mb）

**完成标志**：`/api/stats` 有数据后，图表正确渲染。

### 3.4 单帧详情页

**执行人**：Claude Code

**功能**：
- 点击 DataTable 行 → 跳转详情
- 显示原图（`<img src="/static/defects/...">`）
- bbox overlay（canvas 或 SVG 叠加，坐标从归一化 [0,1] 转像素）
- JSON metadata 完整展示

**完成标志**：点击某条缺陷记录，能看到图片 + bbox 框 + 完整 JSON。

### 3.5 WebSocket 实时推送 + Sonner Toast

**执行人**：Claude Code

**实现**：
- 连接 `ws://localhost:8000/ws/dashboard`
- 收到 `defect_created` → DataTable 新增行 + Sonner toast 通知
- 断线重连：指数退避 1/2/4/8/15 s（API_CONTRACT.md §8）
- `typeof window` 守卫（CLAUDE.md MUST-NOT#10）

**完成标志**：模拟器运行时，前端实时弹 toast + 表格自动追加。

### 3.6 静态导出验证

**执行人**：你手动

```bash
cd frontend
npm run build    # next build 自动静态导出到 out/
npx serve out    # 本地预览静态产物
```

**注意**（ARCHITECTURE.md §9.2）：Next.js 14+ 已移除 `next export` 命令，`next build` + `output: 'export'` 自动完成。

**完成标志**：`out/` 目录存在，静态服务可访问。

---

## 阶段 4：轨道A 联调验收

**时间预估**：0.5 天
**前置依赖**：阶段 1-3 全部完成

### 4.1 全链路端到端运行

**执行人**：你手动操作 + 观察

```bash
# 终端 1：启动后端
cd backend && uvicorn app.main:app --reload --port 8000

# 终端 2：启动前端
cd frontend && npm run dev

# 终端 3：启动模拟器
cd simulator && python line_runner.py
```

**验证清单**：

| 检查项 | 预期结果 | 对应文档 |
|---|---|---|
| 模拟器日志 | 每 ~1.5s 发一次 POST，返回 200 | ARCHITECTURE.md §4.1 |
| 后端 `static/defects/` | 按日期子目录落盘 JPEG | API_CONTRACT.md §9 |
| `vision.db` | `defects` 表有数据 | ARCHITECTURE.md §9.1 |
| 前端 DataTable | 实时追加行 | — |
| 前端 ECharts | AB 对比卡片有数据 | — |
| 前端 Toast | 每条新缺陷弹通知 | — |
| 单帧详情 | 图片可加载 + bbox overlay 正确 | — |
| `/api/health` | `{"status": "ok", ...}` | API_CONTRACT.md §7 |

### 4.2 契约测试全绿

```bash
pytest backend/tests/contract/ -v
# 6 个文件全 PASSED
```

**阶段 4 完成标志**：上述所有检查项通过 + 契约测试全绿。这是轨道 A 的完成节点。

---

## 阶段 5：PC 端模型训练与 AB 评估

**时间预估**：3-7 天（训练快，手动标注慢）
**前置依赖**：MVTec AD 数据集已下载（阶段 0.2）
**可与阶段 1-4 并行**：训练不依赖后端/前端
**文档依据**：ARCHITECTURE.md §3.2/§7.2、CLAUDE.md AB 测试方案

### 5.1 EfficientAD-S 训练（三个类别）

**执行人**：Claude Code 写脚本 → 你在 PC 上跑

**脚本**：`scripts/train_efficientad.py`

```
给 Claude Code 的指令：
帮我写 scripts/train_efficientad.py，
用 Anomalib 2.x 对 MVTec AD 的 metal_nut、screw、pill
三个类别分别训练 EfficientAD-S 模型（model_size="s"），
数据集路径 simulator/mvtec/，
训练完后每个类别导出一个 ONNX 文件到
models/efficientad_models/{category}/model.onnx
```

**运行环境**：RTX 4060，每个类别约 10-20 分钟

**产出**：
```
models/efficientad_models/
├── metal_nut/model.onnx
├── screw/model.onnx
└── pill/model.onnx
```

**完成标志**：三个 ONNX 文件存在，可用 `onnxruntime` 推理。

**精度验证**（ARCHITECTURE.md §3.2）：
- MVTec AD image-AUROC 参考值：metal_nut 0.979 / pill 0.987 / screw 0.960

### 5.2 FastSAM-s 权重下载

**执行人**：你手动

- 从 GitHub 或 HuggingFace 下载 FastSAM-s.pt
- 导出 ONNX：`scripts/convert_fastsam.py`（Claude Code 写）
- 存放：`models/fastsam_models/fastsam_s.onnx`

**完成标志**：ONNX 文件存在。

### 5.3 LoRA 数据划分

**执行人**：Claude Code 写脚本 → 你跑

**脚本**：`scripts/split_lora_data.py`

```
给 Claude Code 的指令：
帮我写 scripts/split_lora_data.py，
读取 simulator/mvtec/{metal_nut,screw,pill}/test/ 下的缺陷图
（排除 good/ 子目录），按缺陷类型分层抽样，
70% 复制到 datasets/lora_split/{category}/train/，
30% 复制到 datasets/lora_split/{category}/eval/，
random.seed(42)，不移动原文件。
```

**文档依据**（ARCHITECTURE.md §7.2）：
> "训练集与评估集不得有任何重叠。划分脚本见 `scripts/split_lora_data.py`（固定 `random.seed(42)` 保证可复现）"

**完成标志**：`datasets/lora_split/` 下有 train/ 和 eval/ 子目录，图片数量比约 70:30。

### 5.4 手动标注 JSON

**执行人**：你手动（无法自动化）

对 `datasets/lora_split/{category}/train/` 中的每张缺陷图，写一个对应的 JSON：

```json
{
  "category": "metal_nut",
  "defect_type": "scratch",
  "severity": "high",
  "confidence": 0.92,
  "bboxes": [{"x": 0.31, "y": 0.42, "w": 0.18, "h": 0.12}],
  "description": "长条划痕，从左上延伸至右下"
}
```

**工作量估算**：三个类别各取 70% 缺陷图，大约 50-150 张，每张写一个 JSON。这是整个项目中**最耗人工时间**的一步。

**完成标志**：每张训练图都有对应的 JSON 标注文件。

### 5.5 LLaMA-Factory LoRA 微调

**执行人**：Claude Code 写脚本/配置 → 你在 PC 上跑

**脚本**：`scripts/train_qwen3vl_lora.py` 或 LLaMA-Factory YAML 配置

**关键参数**（ARCHITECTURE.md §7.2）：
- 模型：Qwen3-VL-2B-Instruct
- LoRA rank: 16
- Epoch: 5
- 数据格式：ShareGPT（多模态图文对话）
- GPU：RTX 4060 8GB（2B 模型 LoRA 完全够用）

**产出**：`models/qwen3vl_lora_adapter/`（LoRA adapter 权重）

**完成标志**：adapter 文件存在，可以合并回 base 模型。

### 5.6 PC 端 AB 评估

**执行人**：Claude Code 写评估脚本 → 你跑

**脚本**：`scripts/eval_ab_test.py`

**评估内容**（ARCHITECTURE.md §7.1-7.2）：

| 变体 | 配置 | 评估集 |
|---|---|---|
| 方案 A | Base Qwen3-VL-2B + 长 Prompt（800-1500 tokens） | datasets/lora_split/*/eval/ （30%） |
| 方案 B | LoRA 合并后 + 极简 Prompt（≤100 tokens） | 同上 |

**PC 阶段只比较一个指标**（ARCHITECTURE.md §7.1）：
- ✅ JSON 解析成功率（%）——核心
- ❌ TTFT——PC GPU 速度与 RK3588 不可比，不记录
- ❌ decode tps——不记录
- ❌ RAM——不记录

**产出**：方案 A vs B 在 metal_nut / screw / pill 上的 JSON 解析成功率对比表

**完成标志**：对比表完成，决定方案 A 或 B 哪个 JSON 成功率更高。

---

## 阶段 6：轨道B — 模型转换

**时间预估**：1-2 天
**前置依赖**：阶段 5 模型训练完成 + rknn-toolkit2 环境搭好
**文档依据**：SKILL.md 模型路径、ARCHITECTURE.md §3.2

### 6.1 搭建 rknn-toolkit2 环境

**执行人**：你手动

- Python 3.8-3.11（rknn-toolkit2 对 Python 版本有严格要求）
- 建议用独立 conda/venv 环境
- 安装 rknn-toolkit2（从 Rockchip 官方 GitHub 下载 wheel）

### 6.2 EfficientAD-S ONNX → RKNN INT8

**执行人**：Claude Code 写脚本 → 你跑

**脚本**：`scripts/convert_efficientad.py`（CLAUDE.md 目录已规划）

**关键约束**（SKILL.md）：
- 量化后必须跑 `accuracy_analysis` 验证 cosine sim > 0.99
- 三核 NPU 并行（`rknn_core_num=3`）

**产出**：
```
models/efficientad_models/
├── metal_nut/model.rknn
├── screw/model.rknn
└── pill/model.rknn
```

### 6.3 FastSAM-s ONNX → RKNN INT8

**脚本**：类似，输入 640×640

**产出**：`models/fastsam_models/fastsam_s.rknn`

### 6.4 Qwen3-VL-2B → RKLLM W8A8

**执行人**：你操作

**两条路**（来源：历史对话01）：

| 方式 | 步骤 | 推荐度 |
|---|---|---|
| 自己转 | HF 下载原始权重 → rknn-llm 工具链转 W8A8 | 可选 |
| 用现成的 | 下载 airockchip/Qengineering 社区预转换的 .rkllm | ✅ 推荐 |

**关键约束**（SKILL.md）：
- W8A8 是 RK3588 LLM 路径**唯一**支持的量化
- W4A16 仅 RK3576 支持，**禁止使用**

**产出**：
```
models/qwen3vl_models/
├── qwen3vl_2b_w8a8.rkllm
└── qwen3vl_vision.rknn    （Vision encoder 单独文件，FP16）
```

### 6.5 将模型文件传到板子

```bash
scp -r models/ ubuntu@<rk3588-ip>:/home/ubuntu/models/
```

然后更新 `edge/config.yaml` 中的路径（把 `/TBD/` 替换为真实路径）。

**阶段 6 完成标志**：所有模型文件在板子上对应路径，config.yaml 路径填写完毕。

---

## 阶段 7：轨道B — C++ 四线程流水线

**时间预估**：5-10 天（最复杂的阶段）
**前置依赖**：阶段 4（后端可用）+ 阶段 6（模型在板子上）
**文档依据**：SKILL.md 全文、ARCHITECTURE.md §3/§11、CLAUDE.md 轨道B

**此时安装 `clangd-lsp` 插件**。

### 7.1 CMake 项目搭建

**执行人**：Claude Code

**产出**：`edge/CMakeLists.txt`，链接 librknnrt / librkllmrt / librga / libcurl

### 7.2 公共组件

**执行人**：Claude Code
**文档依据**：ARCHITECTURE.md §11.2-11.4

| 组件 | 文件 | 来源 |
|---|---|---|
| `UniqueFd` | `edge/src/common/unique_fd.hpp` | §11.3 |
| `UniqueRknnCtx` | `edge/src/common/unique_rknn.hpp` | §11.3 |
| `BoundedQueue<T>` | `edge/src/common/bounded_queue.hpp` | §11.4（drop-oldest + condition_variable_any） |
| `PipelineMetrics` | `edge/src/common/metrics.hpp` | §11.2（alignas(64)） |
| `HttpClient` | `edge/src/upload/http_client.hpp` | §11.6 |

**硬约束检查清单**（SKILL.md 10 条）：
- [ ] `std::jthread` + `std::stop_token`，不用 `std::thread`
- [ ] `std::condition_variable_any` 三参数 wait，不用 `std::condition_variable`
- [ ] RAII 包装所有句柄，禁止裸 `int fd`
- [ ] BoundedQueue 导出 `dropped_count`
- [ ] `curl_global_init` 只在 main() 最开头调一次

### 7.3 T1 Capture Worker

**执行人**：Claude Code
**文档依据**：ARCHITECTURE.md §3.1/§3.3

- V4L2 模式：dma_buf fd → `UniqueFd` → 入 Q1
- Image Loop 模式：循环读取 config.yaml 中配置的类别图片集
- 按 `capture_mode` 配置切换

### 7.4 T2 Pipeline Worker（EfficientAD-S）

**执行人**：Claude Code

- RGA `importbuffer_fd` → `imresize` 256×256 → `rknn_create_mem_from_fd` 零拷贝
- 异常分数 > 阈值 → 入 Q2
- 否则丢弃

### 7.5 T3 VLM Worker（FastSAM + Qwen3-VL-2B）

**执行人**：Claude Code

- FastSAM 分割 → bbox 列表
- 五级 bbox 净化（参考 `edge/src/vlm_bbox_ref.py`，C++ 重写）
- Qwen3-VL-2B 生成 JSON
- KV cache preload（`rkllm_load_prompt_cache`）
- `max_context=3072`（8GB 板硬约束）

### 7.6 T4 Upload Worker

**执行人**：Claude Code

- libcurl multipart POST（ARCHITECTURE.md §11.6 模板）
- 指数退避重试：500ms × 2ⁿ + jitter，最多 5 次
- 针对 408/429/5xx/网络超时重试（API_CONTRACT.md §11）

### 7.7 main.cpp 串联

**执行人**：Claude Code
**文档依据**：ARCHITECTURE.md §11.5/§11.6

```cpp
int main() {
    curl_global_init(CURL_GLOBAL_DEFAULT);
    // 读取 config.yaml
    // 创建 Q1(cap=4), Q2(cap=2), Q3(cap=4)
    // 创建 PipelineMetrics
    // 启动 T1/T2/T3/T4 四个 jthread
    // 等待 SIGINT/SIGTERM
    curl_global_cleanup();
}
```

### 7.8 交叉编译 + 上板测试

**执行人**：你操作（Claude Code 辅助写 CMake toolchain）

```bash
# PC 交叉编译
cmake -DCMAKE_TOOLCHAIN_FILE=aarch64-toolchain.cmake ..
make -j$(nproc)

# 传到板子
scp edge_pipeline ubuntu@<rk3588-ip>:/home/ubuntu/

# 板子上运行
ssh ubuntu@<rk3588-ip>
./edge_pipeline --config config.yaml
```

**完成标志**：C++ 流水线运行，后端收到 POST 请求，前端能看到数据。

### 7.9 通过契约测试

C++ 客户端发出的报文必须通过阶段 2 的同一组 pytest 契约测试。

```bash
# 后端 + C++ 客户端运行时
pytest backend/tests/contract/ -v
# 全绿 → C++ 客户端契约合规，可替换模拟器
```

**阶段 7 完成标志**：契约测试全绿 + C++ 流水线稳定运行。

---

## 阶段 8：全链路验收 + 数据对比

**时间预估**：1-2 天
**前置依赖**：阶段 7 完成

### 8.1 RK3588 四维指标实测

**文档依据**：ARCHITECTURE.md §7.1/§7.3

在 RK3588 上跑完整流水线，收集 `PipelineMetrics` + `VlmMetrics` 数据：

| 指标 | 方案 A 值 | 方案 B 值 | 来源 |
|---|---|---|---|
| JSON 解析成功率 | X'% | Y'% | `vlm_metrics.json_parse_ok` |
| TTFT（首 token 延迟） | ms | ms | `vlm_metrics.ttft_ms` |
| Decode tokens/s | tps | tps | `vlm_metrics.decode_tps` |
| 运行时 RAM | GB | GB | `vlm_metrics.rss_mb` |

### 8.2 量化前后对比

| 对比组 | JSON 成功率 | 结论 |
|---|---|---|
| PC fp16 方案 A → RK3588 W8A8 方案 A | X% → X'% | 量化损失幅度 |
| PC fp16 方案 B → RK3588 W8A8 方案 B | Y% → Y'% | 量化损失幅度 |

### 8.3 最终方案选择

综合四维指标，决定生产部署用方案 A 还是方案 B。
决策写入 `edge/config.yaml` 的 `vlm_variant` 字段。

### 8.4 前端仪表盘展示 AB 对比

前端 `/api/stats` 的 `ab_compare` 字段直接聚合两个变体的数据，ECharts 图表展示。

**阶段 8 完成标志**：全链路稳定运行 + AB 数据对比完成 + 方案选定 → **项目完成**。

---

## 附录：备选降级方案

如果 Qwen3-VL-2B 在 RK3588 上部署失败，按以下顺序降级（ARCHITECTURE.md §3.2）：

| 优先级 | 模型 | 预期 tps | 备注 |
|---|---|---|---|
| 1 | Qwen2.5-VL-3B | ~7 | 社区资料最丰富 |
| 2 | InternVL3.5-2B | ~11 | rknn-llm v1.2.3 官方支持 |
| 3 | InternVL3-1B | ~30 | 质量略弱但延迟极低 |
| 4 | Qwen2-VL-2B | ~12 | 最老牌稳定 |

**只改 `edge/config.yaml`，不改 C++ 代码**。
