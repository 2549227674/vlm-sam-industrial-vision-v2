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

需额外配置（阶段 3 前完成）：
- **playwright 插件**：从插件列表安装，用于前端视觉验证
- **shadcn MCP**：在项目根 `.mcp.json` 添加：
  ```json
  {"mcpServers": {"shadcn": {"command": "npx", "args": ["-y", "shadcn@latest", "mcp"]}}}
  ```
  启动 Claude Code 后运行 `/mcp` 验证 Connected

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

> **⚠️ 实践注意事项**
> - Pydantic v2 子类 `model_config` 不继承父类，`DefectRead` 必须显式写 `ConfigDict(from_attributes=True, extra="forbid")`
> - §12 的字段规则（时区、三键校验）须在 Schema 层通过 `field_validator` 强制，不能只靠路由层

### 1.3 SQLAlchemy 2.0 数据库模型

**执行人**：Claude Code
**文档依据**：ARCHITECTURE.md §2.2、§9.1

- 使用 `aiosqlite` 异步驱动
- SQLite WAL 模式
- `defects` 表字段与 `DefectCreate` 一一对应
- `variant` 字段为 `Literal["A", "B"]`（API_CONTRACT.md §2）

**完成标志**：`alembic` 或启动时自动建表成功，`vision.db` 文件生成。

> **⚠️ 实践注意事项**
> - `DATABASE_URL` 用 `Path(__file__)` 动态解析，避免 uvicorn 启动目录影响路径
> - `get_db()` 需包含 try/commit/except rollback/raise 完整模式
> - 必须加 `UniqueConstraint("line_id","edge_ts")` 和 `CheckConstraint("variant IN ('A','B')")`
> - SQLite 不保留 timezone，须用 `TZDateTime` TypeDecorator 自动恢复 UTC

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

> **⚠️ 实践注意事项**
> - `response_model` 必须用 `DefectCreatedResponse`，不得用 `DefectRead`（否则泄露全量字段）
> - `schema_version` 检查顺序：`json.loads` → 检查 `schema_version` → `model_validate`（否则 422 逻辑永远触发不到）
> - 图片写入用 `aiofiles`（async），同步 `open()` 会阻塞 event loop

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

> **⚠️ 实践注意事项**
> - `sort` 参数需白名单校验，防止任意属性注入
> - `until` 过滤为严格小于（`edge_ts < until`），不含边界值
> - 404 响应用 `JSONResponse` 返统一格式，不用 `HTTPException`
> - `stats.py` 必须实现 `since`/`until`/`bucket` query params 和 `timeline` 字段

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

> **⚠️ 实践注意事项**
> - WebSocket 路由不能用 `Request` 参数，访问 `app.state` 用 `websocket.app.state`
> - `ConnectionManager` 内部结构：`dict[str, set[WebSocket]]` rooms
> - 心跳双间隔：`metrics_tick` 每 5s，`ping` 每 30s（一个 loop，计数器区分）
> - 路由固定为 `/ws/dashboard`（不要 `/{room}` 开放任意房间）

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
- 同时发 variant="2B_base" 和 variant="2B_lora" 的数据（模拟 2B 双变体；4B 变体在 eval_ab_test.py 中按顺序评估，不并发发送）

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

### 3.0 Claude Design 视觉设计（已完成）

**执行人**：Claude Design（已迭代两轮，定稿 V2）

**产出目录**：`design-reference/`（不在 frontend/ 内，避免 Next.js 构建扫描）
```
design-reference/
├── Industrial_Vision_Dashboard_v2.html   ← 整体结构参考
└── src/
    ├── v2-primitives.jsx    ← 颜色变量与语义（最重要）
    ├── v2-waterfall.jsx     ← 瀑布图组件逻辑
    ├── v2-ab.jsx            ← AB 对比面板
    ├── v2-charts.jsx        ← 其他图表
    ├── v2-stream.jsx        ← Live Stream 表格
    ├── v2-detail.jsx        ← 单帧详情
    └── v2-app.jsx           ← 页面组织
    └── data.jsx
    └── tweaks-panel.jsx
```

**V2 定稿设计规格（Claude Code 必须遵守）**：
- 字体：JetBrains Mono（数字/ID/代码） + Inter（标签/文案）
- 背景色系：`--bg-0:#0a0c10` → `--bg-4:#262c39`（5 级深色阶）
- 信号色（来自 v2-primitives.jsx）：
  - `--sig-cyan:#5ad6ff`（主色调，参照 Nsight）
  - `--sev-low:#4ade80` / `--sev-med:#fbbf24` / `--sev-high:#f87171`
  - `--stage-1:#4ade80`（EfficientAD，快）/ `--stage-2:#fbbf24`（FastSAM，中）
    / `--stage-3:#f87171`（Qwen3-VL，瓶颈），这套颜色有叙事含义，不可修改
  - `--sig-violet:#a78bfa`（方案 A）/ `--sig-teal:#2dd4bf`（方案 B）

**所有 CSS 变量映射到 Tailwind v4 `@theme` 块，不使用 tailwind.config.ts**

**完成标志**：`design-reference/` 目录存在，`v2-primitives.jsx` 可读取。

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

**V2 新增**：表格为 8 列 profiler 风格（列含 NPU Core 负载色块），点击行侧边弹出 DetailDrawer（而非跳转新页），可并行浏览流水。

**完成标志**：启动模拟器后，DataTable 实时出现新行。

> **⚠️ 实践变更**
> - WebSocket 逻辑抽离到 `frontend/src/lib/ws.ts`，组件通过 hook 调用
> - useRef 持有最新回调，deps=[] 保证 WS 只建立一次
> - 消息解析：ws.ts 负责解包 `msg.data`，业务层只处理 `DefectRead` 对象

### 3.3 统计聚合图 — ECharts AB 对比

**执行人**：Claude Code

**数据源**：`GET /api/stats`

**V2 定稿图表清单**：
- 顶部 6 联 KPI 条：24h 缺陷数 / 平均流水线延迟 / NPU Core2 负载 /
  JSON OK 率 / TTFT / 稳态 RSS（数据来自 GET /api/stats 扩展字段）
- Hero 瀑布图：三段流水线延迟（EfficientAD→FastSAM→Qwen3-VL），
  用 ECharts custom 系列实现，参考 `design-reference/src/v2-waterfall.jsx`
  右上角 callout 写 "→ opportunity: LoRA short-prompt → -45% TTFT"
- Category × Severity 热力矩阵（替代原计划的饼图+柱图）
- AB 对比 5 轴面板：TTFT / JSON Parse / Decode tps / RSS / Prompt tokens，
  每行带方向箭头 ↓/↑ + Δ%，底部一句 "→ DECISION: ship variant B"
  参考 `design-reference/src/v2-ab.jsx`

**注意**：`design-reference/` 里的代码是原生 React + Babel CDN，不可直接使用，
只作视觉规格参考，用 Next.js App Router + Tailwind v4 + ECharts 5.6 重新实现。

**完成标志**：`/api/stats` 有数据后，图表正确渲染。

> **⚠️ 后端扩展（Phase 3.3 执行时发现）**
> `/api/stats` 原始实现缺少前端所需字段，实际执行时补充了：
> - `avg_pipeline_ms`：SQLite json_extract 聚合三段均值
> - `category_severity_matrix`：笛卡尔积 group by(category, severity)
> - `ab_compare.avg_prompt_tokens`：vlm_metrics JSON 字段聚合

### 3.4 单帧详情页

**执行人**：Claude Code

**功能**：
- 点击 DataTable 行 → 跳转详情
- 显示原图（`<img src="/static/defects/...">`）
- bbox overlay（canvas 或 SVG 叠加，坐标从归一化 [0,1] 转像素）
- JSON metadata 完整展示

**完成标志**：点击 DataTable 行，右侧弹出 **DetailDrawer（Sheet 侧滑）**，包含：
图片 + BBox Overlay / Metadata 8 格 / Pipeline Profiler 色条 /
NPU Trace 占位区（Phase 7 填充）/ VLM Raw JSON

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

### 3.7 视觉精修 — 对齐 V2 设计稿

**执行人**：Claude Code（非原计划，Phase 3.6 后发现视觉差距，补加）

**触发原因**：Phase 3.1-3.6 的组件实现参考 Gemini 回答，
未直接读取 design-reference/src/*.jsx，导致视觉效果与 V2 设计稿差距较大。

**产出**：
- `frontend/src/components/v2/`（12 个新组件）：
  TopBar / BottomStatus / KPIStrip / PipelineWaterfall（SVG甘特）/
  NPUUtilization / CategorySeverityMatrix / ABCompare /
  LiveStream / DetailDrawer / ThroughputChart / primitives / index
- `frontend/src/lib/mock-data.ts`（API 离线时 fallback，与 data.jsx 量级一致）
- `.claude/agents/visual-verify.md`（haiku 子 agent，playwright 截图对比）

**工作流**：通读所有 design-reference/src/*.jsx → 逐组件翻译 → visual-verify agent 截图对比 → 迭代

**完成标志**：npm run build 通过，visual-verify 报告 10/11 视觉匹配。

---

### 3.8 功能完整性验证 + 旧组件清理

**执行人**：Claude Code

**触发原因**：3.7 视觉精修创建了新的 v2/ 组件体系，但旧组件系统（DefectStream / WaterfallChart / KpiCards 等）未同步清理，存在两套并行实现。

**执行内容**：
- 确认 v2/ 组件继承了 Phase 3.2-3.4 的全部功能（BBox/Trace/Toast/API_BASE/断线重连）
- 删除 5 个旧组件文件（-800 行）
- 修复 Hydration 错误（NPUUtilization / CategorySeverityMatrix 的 Math.random()
  移入 useEffect，useState(EMPTY_STATS) + mounted 模式）

**完成标志**：npm run build 通过 + 浏览器控制台无 Hydration 错误。

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

> **⚠️ 重做说明（2026-05-11 决策）**：
> 本阶段已完成「v1 初版」（3 类别：metal_nut/screw/pill，240 train/113 eval，2 变体 A/B）。
> 当前执行「v2 重做」，目标：全 15 类别 + 4 变体 2×2 矩阵（2B_base/2B_lora/4B_base/4B_lora）。
> v1 实测数据保留在各子节末尾，标注为「v1 初版结果」。

**时间预估**：v1 已完成；v2 重做估计 5-10 天（15 类训练 ~2-3h + 4B LoRA 云端 ~2h + 评估）
**前置依赖**：MVTec AD 数据集已下载（阶段 0.2）
**可与阶段 1-4 并行**：训练不依赖后端/前端
**文档依据**：ARCHITECTURE.md §3.2/§7.2、CLAUDE.md AB 测试方案

### 5.1 EfficientAD-S 训练（三个类别）

**执行人**：Claude Code 写脚本 → 你在 PC 上跑

**脚本**：`scripts/train_efficientad.py`

```
给 Claude Code 的指令：
帮我写 scripts/train_efficientad.py，
用 Anomalib 2.x 对 MVTec AD 全 15 个类别（见上方列表）
分别训练 EfficientAD-S 模型（model_size="s"），
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

**实测结果**（RTX 4060 Laptop GPU，seed=42，20 epochs）：
- metal_nut: AUROC=0.9721  ref=0.979  训练时间 388s
- screw:     AUROC=0.9102  ref=0.960  训练时间 571s
- pill:      AUROC=0.9558  ref=0.987  训练时间 498s
- 总时长：约 24 分钟

> **v1 初版结果**（3 类，seed=42，20 epochs，RTX 4060 Laptop）：
> metal_nut AUROC=0.9721 / screw AUROC=0.9102 / pill AUROC=0.9558 / 总训练时长约 24 分钟

**v2 重做目标（15 类全量）**：
将上方脚本 `categories` 列表扩展为全部 15 类：
`["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
  "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
  "wood", "zipper"]`
（执行前运行 `ls simulator/mvtec/` 确认实际目录名，以磁盘上目录名为准）

**v2 实测结果**（15 类，RTX 4060 Laptop GPU，seed=42，20 epochs）：
- 15/15 ONNX 导出成功
- `convert_efficientad_rknn.py --dry-run` 显示 15/15 convertible
- 低分类别 capsule(0.70)/transistor(0.78)/toothbrush(0.84)/hazelnut(0.87)/screw(0.89) 进入 targeted retrain
- 详细结果见 `docs/experiments/phase5_efficientad_15cls_results.md`
- 低分类别 run1 备份在 `models/efficientad_models_v2_run1_20ep_low_auroc_backup/`

预计总训练时间：~2-3 小时（15 类 × 每类约 8-12 分钟，RTX 4060 Laptop）
产出目录：`models/efficientad_models/{15个类别}/model.onnx`

**ONNX 实际输出 4 个张量**（非原计划 2 个）：
- `pred_score`, `pred_label`, `anomaly_map`, `pred_mask`
- RKNN 转换只需 `pred_score` + `anomaly_map`，其余两路忽略

**两个实操陷阱**：
1. imagenette 路径必须是 `datasets/imagenette/imagenette2-320/`（不是 `datasets/imagenette2-320/`，Anomalib 期望多一层目录）
2. ONNX 保存路径是 `weights/onnx/model.onnx`（不是直接在 export_root 下，已在脚本中修正）

### 5.2 FastSAM-s 权重下载

**执行人**：你手动

- 从 GitHub 或 HuggingFace 下载 FastSAM-s.pt
- 导出 ONNX：`scripts/convert_fastsam.py`（Claude Code 写）
- 存放：`models/fastsam_models/fastsam_s.onnx`

**完成标志**：ONNX 文件存在。

**脚本**：`scripts/convert_fastsam.py`（已完成）

**三处工程改进**：
1. export 后 `shutil.move` 重命名为 `fastsam_s.onnx`
2. `check_onnxsim()` 探测是否安装，未装则 `simplify=False`
3. shape 硬断言：`output0=(1,37,8400)`, `output1=(1,32,160,160)`

**实测结果**：
- `fastsam_s.onnx` 46MB
- input: `images` [1, 3, 640, 640]
- output0: [1, 37, 8400] — 4+1+32（bbox+cls+mask 系数）
- output1: [1, 32, 160, 160] — mask prototypes（1/4 分辨率）
- CPU 推理：~108ms
- 关键：Ultralytics ONNX export 默认不含 NMS，输出为原始张量，C++ T3 需自行实现 NMS + mask 合并

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

**实际产出**：240 条训练样本，113 条 eval 样本

> **v1 初版**（3 类）：240 train / 113 eval

**v2 重做目标（15 类）**：
脚本扩展到 15 类后，预计产出：~1200 train / ~540 eval（15 类 × 约 80/36 样本）（实际：train=849, eval=409）。
实际数量以脚本输出为准（各类别图片数量不均匀）。

**文件命名**：加缺陷类型前缀（如 `scratch_000.png`）
原因：MVTec 各缺陷子目录图片均命名为 `000.png`-`015.png`，拍平复制会互相覆盖，前缀可规避冲突

### 5.4 自动生成标注 JSON + 数据格式转换

**执行方式**：自动化脚本（非手动标注）

**脚本**：`scripts/mvtec_mask_to_json.py`

**逻辑**：读取 MVTec 官方 Ground Truth Mask（PNG 二值图），
用 OpenCV `connectedComponentsWithStats` 提取连通域，
转换为归一化 bbox 坐标，自动生成 DefectCreate 格式 JSON。
**必须同时处理 train 和 eval 两个 split**，eval JSON 是 method_control 评估
（category_exact / defect_type_exact / bbox_iou）的前提。

**三处关键改进（相比参考版）**：
- `confidence` 改为面积反推（`min(0.99, 0.60+(rel_area/0.05)*0.39)`），非随机值
- `description` 统一全中文（`DEFECT_CN` 映射表）
- `bboxes` 加 `[:16]` 截断，符合 API_CONTRACT.md `max_length=16` 约束

**数据格式转换**：`scripts/format_llama_factory_data.py`
将图片+JSON 转为 LLaMA-Factory ShareGPT 多模态格式，
system/user/assistant 三条消息，images 字段用相对路径。
含 dry-run 模式，若 train 或 eval 任一为 0 则报错退出（可用 `--allow-empty-eval` 调试例外）。

**产出**：240 条训练样本，113 条 eval 样本

**完成标志**：`datasets/lora_split/` 下 ShareGPT 格式 JSONL 文件存在，条数正确。

**v2 重做**：脚本已同步扩展到 15 类，`DEFECT_CN` 映射表已补充全部类别中文描述。
脚本同时处理 train 和 eval 两个 split，支持 `--dry-run` 预览计数。

**v2 修复要求**（已完成）：
- 从 3 类硬编码扩展到 15 类自动发现（扫描 `datasets/lora_split/` 目录）
- 同时输出 `datasets/industrial_vision_train.json` 和 `datasets/industrial_vision_eval.json`
- `dataset_info.json` 注册两个数据集（train + eval），均包含 `system_tag: "system"`
- README 模板改为 `qwen3_vl`（不再出现 `qwen2_vl`）
- 增加基础校验：样本数统计、图片是否存在、JSON 是否可解析、category 是否在 15 类白名单内
- `--dry-run` 模式支持预览不写文件

### 5.5 LLaMA-Factory LoRA 微调 ✅ 已完成

**执行人**：Claude Code 写脚本/配置 → 你在 PC 上跑

**脚本**：`scripts/train_qwen3vl_lora.py` 或 LLaMA-Factory YAML 配置

**关键参数**（ARCHITECTURE.md §7.2）：
- 模型：Qwen3-VL-2B-Instruct
- LoRA rank: 32, alpha: 32, target: q_proj,k_proj,v_proj,o_proj
- Epoch: 5
- 数据格式：ShareGPT（多模态图文对话）
- GPU：RTX 4060 8GB（2B 模型 LoRA 完全够用）

**实际训练平台**：AutoDL vGPU-32GB（RTX 4080 32GB），非本地 RTX 4060

**关键发现**：`dataset_info.json` 的 tags 必须声明 `system_tag: "system"`，
否则 LLaMA-Factory 无法识别 system 角色消息，
240 条样本全部被丢弃（`Cannot find valid samples`）

**实际训练结果**：train_loss=1.073，耗时 4 分 44 秒，5 epoch，150 steps

**产出**：`models/qwen3vl_lora_adapter/`（LoRA adapter 权重）

**完成标志**：adapter 文件存在，可以合并回 base 模型。

**v2 实测结果**（15 类，RTX 4090 48GB，AutoDL）：
- 训练配置：rank=32, alpha=32, target=q_proj/k_proj/v_proj/o_proj, gradient_checkpointing=false
- train_loss：0.5233（含前期高值平均），收敛值约 0.33
- 训练时长：11 分 37 秒，535 步，5 epoch
- 产出：models/qwen3vl_lora_adapter_15cls/

### 5.5b Qwen3-VL-4B LoRA 微调（v2 新增）✅ 已完成

**执行时机**：Qwen3-VL-2B v2 重做完成后执行
**训练平台**：AutoDL RTX 4090 48GB（实测）
**配置文件**：`qwen3vl_lora_4b.yaml`

**与 2B 的关键差异**：
- `per_device_train_batch_size: 1`（4B 显存压力更大）
- `gradient_accumulation_steps: 8`（维持等效 batch=8）
- 其余超参与 2B 保持一致（控制变量原则）
- `freeze_vision_tower: true`（1200 样本不足以微调 ViT，同 2B 策略）

**预计成本**：~2 小时训练，3.32 元；含评估和 buffer 约 6.6 元

**实测结果**（15 类，RTX 4090 48GB，AutoDL）：
- 训练配置：与 2B 保持一致（控制变量），batch_size=1, grad_accum=8
- train_loss：0.411，收敛值约 0.24（优于 2B 的 0.33）
- 训练时长：20 分 32 秒，535 步，5 epoch
- 实际成本：~1.04 元（含 4B 模型下载，hf-mirror 6.35MB/s）
- 产出：models/qwen3vl_lora_4b_adapter/

**已知注意事项**（继承自 2B 经验，无需重复踩坑）：
- `dataset_info.json` 必须声明 `system_tag: "system"`（否则 240/1200 条全被丢弃）
- `template: qwen3_vl`（不是 `qwen2_vl`）
- 不加 liger-kernel（对 Qwen3-VL 已知有问题）

**产出**：`models/qwen3vl_lora_4b_adapter/`

**完成标志**：adapter 文件存在，合并后可送入 RKLLM 转换链路。

### 5.6 PC 端 AB 评估 ✅ Deployment Benchmark 已完成

**执行人**：Claude Code 写评估脚本 → 你跑

**脚本**：`scripts/eval_ab_test.py`

**评估内容**（ARCHITECTURE.md §7.1-7.2）：

| 变体 | 模型 | 配置 | 评估集 |
|---|---|---|---|
| `2B_base` | Qwen3-VL-2B | Base + 工程化 Prompt (~300 tokens) | datasets/lora_split/*/eval/ (30%) |
| `2B_lora` | Qwen3-VL-2B | LoRA 合并后 + 极简 Prompt (~50 tokens) | 同上 |
| `4B_base` | Qwen3-VL-4B | Base + 工程化 Prompt (~300 tokens) | 同上 |
| `4B_lora` | Qwen3-VL-4B | LoRA 合并后 + 极简 Prompt (~50 tokens) | 同上 |

**PC 阶段 8 项指标**（max_tokens=200 主实验口径）：
- json_parse_ok / schema_ok / category_exact / defect_type_exact
- severity_valid / bbox_iou_at_0_5
- prompt_tokens / output_tokens

> ⚠️ `max_tokens=200` 是主实验口径，所有论文/报告数据以此为准。
> `max_tokens=300` 仅用于截断敏感性补测，不替代主实验。

**Deployment Benchmark 主结果**（409 eval samples, max_tokens=200）：

| 变体 | JSON OK | Schema OK | Cat Exact | DefType Exact | Sev Valid | BBox IoU≥0.5 |
|---|---|---|---|---|---|---|
| 2B_base | 96.1% | 96.1% | 53.1% | 11.2% | 96.1% | 1.5% |
| 2B_lora | 95.6% | 95.6% | 94.4% | 53.1% | 95.6% | 48.9% |
| 4B_base | 98.0% | 98.0% | 59.2% | 10.5% | 98.0% | 0.0% |
| 4B_lora | 95.8% | 95.8% | 95.8% | 64.8% | 95.8% | 64.5% |

**关键发现**：
1. Qwen3 系列内置思维链，推理输出带 `<think>` 前缀，
   必须用 `text.find('{') + text.rfind('}')` 提取纯 JSON 后再解析
2. JSON 解析成功率四变体均 >95%，不是区分维度
3. LoRA 微调带来 category_exact 大幅提升（53%→94% / 59%→96%）
4. defect_type_exact 是主要区分维度：2B_lora 53.1% vs 2B_base 11.2%
5. 4B_lora 在所有指标上优于 2B_lora（DefType 64.8% vs 53.1%, BBox 64.5% vs 48.9%）

**辅助分析**：
- `defect_group_exact`（alias 分组粗粒度）：4B_lora 77.3%, 2B_lora 67.4%
  → 模型已学会大类方向，精确子类型仍需提升
- 截断样本（output_tokens≥200）：2B_lora 18 个, 4B_lora 17 个
  → `--image-filter scripts/truncated_2b_lora.txt` 可单独补测

**产出文件**：
- `results/ab_eval_report_v2_deployment.json`（聚合报告）
- `results/ab_eval_predictions_{size}_{variant}_deployment.jsonl`（per-sample 详情）

> **v1 初版结果**（3 类，2 变体）：方案A JSON OK=100%，方案B JSON OK=100%
> 说明：3 类小样本 + 高质量标注下，2B 两变体均达满分，无法区分优劣——这正是扩展到 15 类 + 4 变体的动机

### 5.7 Method Control Benchmark（v2 新增）⬅️ 下一步，尚未执行

**目标**：消除 prompt 差异，隔离 LoRA 微调的真实收益。

**与 Deployment Benchmark 的区别**：
- Deployment：base + 工程化长 prompt vs LoRA + 极简短 prompt（混合了 prompt 效应和 LoRA 效应）
- Method Control：base + 极简短 prompt vs LoRA + 极简短 prompt（仅 LoRA 效应）

**变体**：

| 变体 | 模型 | Prompt |
|---|---|---|
| `2B_base_same_prompt` | Qwen3-VL-2B base | 极简 Prompt (~50 tokens) |
| `2B_lora_same_prompt` | Qwen3-VL-2B LoRA | 极简 Prompt (~50 tokens) |
| `4B_base_same_prompt` | Qwen3-VL-4B base | 极简 Prompt (~50 tokens)（可选） |
| `4B_lora_same_prompt` | Qwen3-VL-4B LoRA | 极简 Prompt (~50 tokens)（可选） |

**评估指标**（8 项，比 Deployment 更细）：
- json_parse_ok / schema_ok / category_exact / defect_type_exact
- severity_valid / bbox_iou_at_0_5
- prompt_tokens / output_tokens

**运行命令**：
```bash
python scripts/eval_ab_test.py --model-size 2B --mode method_control
python scripts/eval_ab_test.py --model-size 2B --mode both  # 同时跑 deployment + method_control
```

**产出**：`results/ab_eval_report_v2_method_control.json`

### 5.8 OPRO Prompt-only Baseline（v2 新增，可选）

**目标**：量化 prompt engineering 的单独贡献，作为 LoRA 的方法学对照。

**原理**：用 LLM 自身搜索更优 prompt（OPRO 风格），不修改模型参数。
- 用少量 train 子集（~30 samples/category）迭代搜索 prompt
- eval 集严格隔离，不参与搜索过程
- 输出 best prompt + 评估分数

**运行命令**：
```bash
python scripts/optimize_prompt_opro.py --model-size 2B
python scripts/optimize_prompt_opro.py --model-size 2B --num-iterations 5 --num-candidates 8
```

**产出**：`results/prompt_opro_best.json`

**价值**：与 LoRA 形成三方对照：
1. base + 长 prompt（Deployment Benchmark）
2. LoRA + 短 prompt（Deployment Benchmark）
3. base + OPRO 最优 prompt（本实验）

如果 (2) 和 (3) 接近，说明 LoRA 的收益主要来自 prompt 优化而非参数适应。

**注意**：OPRO 结果不进入 RK3588 部署链路，仅作为 PC 阶段方法学分析。

**完成标志**：4 变体在所有 15 类的 JSON 解析成功率对比表完成。

---

## 阶段 6：轨道B — 模型转换

**时间预估**：1-2 天
**前置依赖**：阶段 5 模型训练完成 + rknn-toolkit2 环境搭好
**文档依据**：SKILL.md 模型路径、ARCHITECTURE.md §3.2

### 6.1 搭建 rknn-toolkit2 环境

**执行人**：你手动

- **实际使用系统**：Ubuntu 24.04（WSL2）
- **Python 版本**：必须用 3.11（非 3.12）。Ubuntu 24.04 默认 Python 3.12 不兼容，需通过 deadsnakes PPA 安装：
  ```bash
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt install python3.11 python3.11-venv python3.11-dev
  ```
- **环境名称**：`.venv_rknn`（项目内虚拟环境，已加入 .gitignore）
- **仓库地址**：`https://github.com/airockchip/rknn-toolkit2`（原 rockchip-linux/ 已迁移）
- **onnx 版本陷阱**：rknn-toolkit2 v2.3.2 内部调用 `onnx.mapping`（已在 onnx>=1.16.0 删除），
  安装后必须强制降级：
  ```bash
  pip install onnx==1.15.0
  ```
- **rknn-llm 工具链**（6.4 用）是独立环境 `.venv_rkllm`，与 `.venv_rknn` 完全隔离：
  `https://github.com/airockchip/rknn-llm`

### 6.2 EfficientAD-S ONNX → RKNN INT8

**执行人**：Claude Code 写脚本 → 你跑

**脚本**：`scripts/convert_efficientad_rknn.py`（已扩展到 MVTec 全 15 类）

**关键约束**（SKILL.md）：
- 量化后必须跑 `accuracy_analysis` 验证 cosine sim > 0.99
- `rknn_core_num=3` **不是** `config()` 参数，是板子上运行时的 C++ 参数（`rknn_set_core_mask`），转换脚本中不要出现
- accuracy_analysis 报告路径：rknn-toolkit2 v2.3.2 改为 `{analysis_dir}/error_analysis.txt`（旧版路径 `simulator_error/simulator_error.txt` 已失效）
- 校准集：从 `simulator/mvtec/{category}/train/good/` 取，**至少 50 张**（默认 100 张）
- 10 个算子 fallback 到 CPU（`Unknown op target: 0`），属正常现象，不影响转换
- 输入目录：`models/efficientad_models/{category}/weights/onnx/model.onnx`
- 旧 v1 归档 `models/efficientad_models_v1_3cls/` 不参与 v2 转换
- 支持 `--dry-run` 做前置检查（不调用 RKNN）

**产出**：
```
models/efficientad_models/
├── {category}/model.rknn              # 15 类，每类一个
└── {category}/accuracy_analysis/error_analysis.txt
```

### 6.3 FastSAM-s ONNX → RKNN INT8

**脚本**：类似，输入 640×640

**关键约束**：
- **归一化**：YOLOv8 风格（`mean=[0,0,0], std=[255,255,255]`），不是 ImageNet 参数
- **校准集**：三个类别各取约 33 张**混合**（`random.seed(42)` 打乱），共 100 张
  （FastSAM 是通用模型，单类别校准会导致其他类别量化偏差）
- **输入尺寸**：`load_onnx` 时必须指定 `input_size_list=[[1, 3, 640, 640]]`
- 无 CPU fallback 算子（整图跑在 NPU 上）
- **精度提示**：output1（prototype masks）整体 cosine = 0.966，低于 0.99 阈值，
  但 single cosine = 0.99989，属深层误差累积，需上板实测确认分割质量

**产出**：`models/fastsam_models/fastsam_s.rknn`

### 6.4 Qwen3-VL → RKLLM W8A8

**执行人**：你操作

**关键约束**（SKILL.md）：
- W8A8 是 RK3588 LLM 路径**唯一**支持的量化
- W4A16 仅 RK3576 支持，**禁止使用**

#### 方案 A（2B Base + 长 Prompt）**[2B 路径]**

**直接下载社区预转换的 .rkllm** ✅ 推荐

- 来源：airockchip 或 Qengineering 社区
- 无需自行转换，下载即用

#### 方案 B（2B LoRA + 极简 Prompt）**[2B 路径]**

**必须自己转**，步骤如下：

**Step 1**：用 LLaMA-Factory `export_model` 将 LoRA adapter 合并回 base 权重
- 输入：`models/qwen3vl_models/base/` + `models/qwen3vl_lora_adapter/`
- 输出：`models/qwen3vl_models/merged/`

**Step 2**：搭 airockchip/rknn-llm 工具链环境（独立于 `.venv_rknn`）

**transformers 版本冲突处理**：
- `rkllm-toolkit 1.2.3` 锁定 `transformers==4.55.2`
- 生成校准数据需要 `transformers==4.57.0`（支持 Qwen3-VL）
- 操作顺序：生成校准数据前临时升级，转换前降回
  ```bash
  # 生成校准数据前
  pip install "transformers==4.57.0"

  # 运行 export_rkllm.py 前降回
  pip install "transformers==4.55.2" "tokenizers==0.21.4"
  ```

**make_input_embeds_for_quantize.py 需要四处补丁**（Qwen2-VL → Qwen3-VL 迁移）：
1. 模型类：`Qwen2VLForConditionalGeneration` → `Qwen3VLForConditionalGeneration`
2. embed_tokens 路径：`model.model.embed_tokens` → `model.model.language_model.embed_tokens`
3. dtype 获取：`model.visual.get_dtype()` → `next(model.visual.parameters()).dtype`
4. visual 输出：`model.visual(...).to(...)` → `model.visual(...)[0].to(...)`（返回 tuple）

**merged/config.json 需手动补充两个字段**（LLaMA-Factory 合并时丢失）：
- `rope_scaling`（顶层 + `text_config` 子节点）：`{"rope_type": "default", "mrope_section": [24, 20, 20]}`
- `tokenizer_config.json` 中 `extra_special_tokens` 格式：list → dict

**export_rkllm.py 已知 bug**：`--savepath` 参数不生效，
文件实际保存到 `./rkllm/merged_w8a8_rk3588.rkllm`，需手动移动到项目目录。

**Vision encoder 分辨率**：448×448（来自 Qengineering 社区预转换，两方案共用）

**Step 3**：运行 `scripts/convert_qwen3vl.py` 转 W8A8
- 输入：`models/qwen3vl_models/merged/`
- 输出：`models/qwen3vl_models/qwen3vl_2b_w8a8_lora.rkllm`

#### 方案 C/D（4B Base + 4B LoRA）—— Qwen3-VL-4B

**4B Base（方案C）**：直接使用 Qengineering 预转换文件 ✅ 强烈推荐，不自转换

来源：`https://github.com/Qengineering/Qwen3-VL-4B-NPU`（Sync.com 镜像，总 5.4 GB）

文件清单：
- `qwen3-vl-4b-instruct_w8a8_rk3588.rkllm`（~4.51 GB，来自 rknn-llm v1.2.3 model zoo）
- `qwen3-vl-4b_vision_fp16_rk3588_v1.2.2.rknn`（~670 MB，**优先使用 v1.2.2**，见下方说明）

⚠️ **视觉 encoder 版本选择（Issue #421）**：
- v1.2.3 视觉文件（827 MB）在 OCR/描述任务精度不如 v1.2.2（670 MB）
- 推荐混搭：**v1.2.2 视觉 .rknn + v1.2.3 runtime**（社区验证可行）
- v1.2.2 文件同样在 rkllm_model_zoo/1.2.2 目录可找到

⚠️ **已知坑（Issue #388）**：
- 自行从 HuggingFace 转换 4B 成功率低（报错 "Catch exception when loading model: 'qwen3'"）
- `image_enc.cc` 行 80-81 存在段错误，需应用 wangjl1993 社区 patch
- 多图输入不支持（本项目单图输入，不受影响）

**4B LoRA（方案D）**：
- 前置：§5.5b 的 4B LoRA adapter 完成
- 合并流程与 2B 方案B 相同（LLaMA-Factory export_model）
- 转换命令与 2B 相同，输入换为 `models/qwen3vl_models/4b_merged/`
- 输出：`models/qwen3vl_models/qwen3vl_4b_w8a8_lora.rkllm`

**产出**：
```
models/qwen3vl_models/
├── qwen3vl_2b_w8a8_base.rkllm       （方案A：2B 基座，社区下载）
├── qwen3vl_2b_w8a8_lora.rkllm       （方案B：2B LoRA，自转换）
├── qwen3vl_4b_w8a8_base.rkllm       （方案C：4B 基座，Qengineering 预转换）
├── qwen3vl_4b_w8a8_lora.rkllm       （方案D：4B LoRA，自转换）
├── qwen3vl_vision_2b.rknn            （2B Vision encoder，FP16，两个 2B 方案共用）
└── qwen3vl_vision_4b_v122.rknn       （4B Vision encoder，v1.2.2，两个 4B 方案共用）
```
**完成标志**：六个模型文件均存在（或至少 2B 全部 + 4B base），`config.yaml` 中路径按 `vlm_model_size` 字段分支填写完毕。

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
- `max_context=4096`（16GB 板约束）

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

### 7.x 前端 — 系统拓扑视图（与 C++ 同步实现）

**执行人**：Claude Code（待 C++ metrics_tick 有真实数据后）

**触发条件**：C++ 流水线稳定运行，`metrics_tick` 能推送以下字段：
- `npu_core_0_pct`、`npu_core_1_pct`、`npu_core_2_pct`（当前帧各核占用率）
- `current_stage`：`"efficientad" | "fastsam" | "qwen3vl" | "idle"`（当前正在处理的 Stage）

**组件**：`frontend/src/components/v2/SystemTopology.tsx`

**视觉规格**：
- 放置位置：DashboardStats 顶部，KPIStrip 下方，PipelineWaterfall 上方，作为 Hero 入口
- 呈现：RK3588 Edge Device 框体内，左侧摄像头图标 → 三个 NPU Core 卡片 → 右侧上传图标
- 三个 Core 卡片：模型名 + INT8 badge + 实时利用率条 + 当前帧延迟（来自 metrics_tick）
- 数据流动画：当 current_stage 变化时，对应 Core 卡片高亮脉动，
  左→右方向有粒子流动效果（CSS animation，纯前端，不依赖后端帧率）
- mock fallback：C++ 未运行时，显示静态占位版本（沿用 NPUUtilization 的 mock 数据）

**注意**：
- 不需要新增后端路由，metrics_tick 已通过 WebSocket 推送（CLAUDE.md §1.6）
- 仅需在 lib/ws.ts 中解析 `msg.type === "metrics_tick"` 分支并分发给组件
- Phase 3 的 v2/NPUUtilization.tsx 可作为该组件的子组件复用

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

| 指标 | 2B_base | 2B_lora | 4B_base | 4B_lora | 来源 |
|---|---|---|---|---|---|
| JSON 解析成功率 | X'% | Y'% | P'% | Q'% | `vlm_metrics.json_parse_ok` |
| TTFT（首 token 延迟） | ms | ms | ms | ms | `vlm_metrics.ttft_ms` |
| Decode tokens/s | tps | tps | tps | tps | `vlm_metrics.decode_tps` |
| 运行时 RAM | GB | GB | GB | GB | `vlm_metrics.rss_mb` |

**参考基线**（Qengineering 实测，RK3588 16GB，ctx=4096）：
- 2B：11.5 tps / 3.1 GB RAM / TTFT 热 ~2-3s
- 4B：5.7 tps / 8.7 GB RAM / TTFT 热 ~5-6s（Pipeline 总峰值 ~11.4 GB，余 ~3.1 GB）

### 8.2 量化前后对比

| 对比组 | PC fp16 JSON 成功率 | RK3588 W8A8 JSON 成功率 | 量化损失 |
|---|---|---|---|
| 2B_base | X% | X'% | Δ pp |
| 2B_lora | Y% | Y'% | Δ pp |
| 4B_base | P% | P'% | Δ pp |
| 4B_lora | Q% | Q'% | Δ pp |

### 8.3 最终方案选择

综合四维指标在 4 个变体上的 Pareto 前沿，选定最终部署变体。
决策维度：精度（JSON 解析成功率）× 吞吐（tps）× 内存（GB）。
决策写入 `edge/config.yaml` 的 `vlm_model_size`（"2B" 或 "4B"）和 `vlm_variant`（"base" 或 "lora"）两个字段组合。
综合判断维度：精度提升是否值得 2.8× 内存代价（8.7GB vs 3.1GB）和 2× 延迟代价（5.7 vs 11.5 tps）。

### 8.4 前端仪表盘展示 AB 对比

前端 `/api/stats` 的 `ab_compare` 字段直接聚合两个变体的数据，ECharts 图表展示。

**阶段 8 完成标志**：全链路稳定运行 + AB 数据对比完成 + 方案选定 → **项目完成**。

---

## 附录：备选降级方案

如果 Qwen3-VL-2B 在 RK3588 上部署失败，按以下顺序降级（ARCHITECTURE.md §3.2）：

| 优先级 | 模型 | 推荐场景 | 预期 tps | RAM | 备注 |
|---|---|---|---|---|---|
| 主选 | **Qwen3-VL-4B** | 精度优先，内存充足 | 5.7 | 8.7 GB | rknn-llm v1.2.3 官方支持，Qengineering 有预转换 |
| 备选1 | **Qwen3-VL-2B** | 低延迟，内存紧张 | 11.5 | 3.1 GB | 已完成转换，开箱即用 |
| 备选2 | Qwen2.5-VL-3B | 4B 部署失败时 | ~7 | ~4.8 GB | 社区资料最丰富，happyme531 有预转换 |
| 备选3 | InternVL3.5-2B | 超低延迟需求 | ~11 | ~3 GB | rknn-llm v1.2.3 官方支持 |
| 备选4 | Qwen2-VL-2B | 最稳定保底 | ~12 | ~3 GB | 最老牌稳定 |
| **排除** | ~~Qwen3.5 系列~~ | 不可用 | — | — | rknn-llm #472：Gated DeltaNet 架构不支持 |

**只改 `edge/config.yaml`，不改 C++ 代码**。
