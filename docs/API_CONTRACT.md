# API 接口契约 v1.3

本文档是 RK3588 边缘端、Python 模拟器、FastAPI 后端、Next.js 前端之间的**唯一权威接口定义**。任何字段或语义变更必须先改本文档（bump 版本），再改实现。模拟器是契约测试客户端，覆盖所有路径。

> **v1.3 变更摘要**（2026-05-25）：
> - Phase 10 localization refactor: 新增 `localization_source`、`label_source`、`observation_source`、`defect_family`、`observation`、`severity_reason` 可选字段
> - `pipeline_ms` 接受新 stage key `localizer` / `upload`（旧 key `fastsam` / `qwen3vl` 仍向下兼容）
> - `bboxes` 语义从 FastSAM/VLM proposal 改为 primary localizer output（YOLOv8n-detect）
> - `defect_type` 语义从 VLM 输出改为 YOLO class head 输出
> - `confidence` 语义从 VLM confidence 改为 YOLO detection score
> - **Phase 10.1a**（v1.3 enrichment addendum）: 新增 enrichment API 路由 + `defect_enrichments` 表；`schema_version` 保持 `"v1"`

> **v1.2 变更摘要**（2026-05-19）：
> - 新增 `TraceEvent` schema，`DefectCreate` / `DefectRead` 增加可选 `trace_events` 字段
> - `/api/stats` 顶层增加 `today_defects`、`today_high`
> - `/api/stats` 的 `ab_compare` 每个 variant 增加 `avg_output_tokens`
> - WebSocket `defect_created` 说明补充 `trace_events` 可选携带

> **v1.1 变更摘要**（2026-05-12）：
> - `variant` 字段：`Literal["A", "B"]` → `str`，白名单 `{"2B_base", "2B_lora", "4B_base", "4B_lora"}`，保留 A/B 向下兼容
> - `category` 字段：扩展到 MVTec AD 全 15 类
> - `/api/stats` 的 `ab_compare`：支持按 variant 值动态分组（4 变体）
> - 原因：VLM 实验方案从 2 变体扩展为 4 变体 2×2 矩阵（方案 Y）

## 1. URL 总览

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| POST | `/api/edge/report` | RK3588 / 模拟器 | 上报单次缺陷（multipart） |
| GET | `/api/defects` | 前端 | 列表（分页 / 过滤 / 排序） |
| GET | `/api/defects/{id}` | 前端 | 单条详情 |
| GET | `/api/stats` | 前端 | 聚合统计 + AB 对比 |
| GET | `/api/health` | 全部 | 存活探针 |
| WS | `/ws/dashboard` | 前端 | 实时事件流 |
| GET | `/static/defects/{date}/{file}` | 前端 | 图片静态文件 |
| POST | `/api/defects/{id}/enrich` | 前端 / 手动 | 创建 pending enrichment job（不调用 VLM） |
| GET | `/api/defects/{id}/enrichment` | 前端 | 获取最新 enrichment 记录 |
| POST | `/api/enrich/{id}/process?provider=` | 手动 / 测试 | 手动处理单个 pending job |
| POST | `/api/enrich/process-next?provider=` | 手动 / 测试 | 处理最早的 pending job |

Base URL：开发 `http://localhost:8000`，生产 `https://vision.example.com`。所有请求/响应 JSON 字段统一 `snake_case`。

## 2. 数据 Schema（Pydantic v2）

```python
# backend/app/schemas/defect.py
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high"]
Variant  = Literal["2B_base", "2B_lora", "4B_base", "4B_lora", "A", "B"]  # v1.1: 新增 4 变体，保留 A/B 向下兼容
Stage    = Literal["efficientad", "fastsam", "qwen3vl", "localizer", "upload", "enrichment"]  # v1.3: 新增 localizer/upload/enrichment

class BBox(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0.0, le=1.0)         # 归一化 [0,1]
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)

class VlmMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ttft_ms:        float = Field(ge=0)
    decode_tps:     float = Field(ge=0)      # tokens per second
    prompt_tokens:  int   = Field(ge=0)
    output_tokens:  int   = Field(ge=0)
    rss_mb:         float = Field(ge=0)
    json_parse_ok:  bool

class TraceEvent(BaseModel):
    """Chrome Trace 格式的单条完整事件。

    ts/dur 单位为微秒，origin=0 对应本帧开始时刻。
    使用 extra="ignore" 以兼容未来 C++ 端或 Perfetto 导出的 args/pid 等扩展字段。
    """
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=128)   # e.g. EfficientAD_infer, VLM_decode
    ts:   float = Field(ge=0)                          # start time, microseconds
    dur:  float = Field(ge=0)                          # duration, microseconds
    tid:  str = Field(min_length=1, max_length=64)     # thread/core ID, e.g. T2.pipeline, NPU.core2
    ph:   Literal["X"]                                 # Chrome Trace complete event
    cat:  str = Field(default="", max_length=64)       # category, e.g. infer, vlm-prompt, vlm-decode, io

class DefectCreate(BaseModel):
    """随 multipart 一同提交的 JSON 字段（form 字段名 'meta'）"""
    model_config = ConfigDict(extra="forbid")
    line_id:        str           = Field(min_length=1, max_length=32)
    category:       Literal["bottle", "cable", "capsule", "carpet", "grid", "hazelnut",
                            "leather", "metal_nut", "pill", "screw", "tile", "toothbrush",
                            "transistor", "wood", "zipper"]  # v1.1: 扩展到 MVTec AD 全 15 类
    defect_type:    str           = Field(min_length=1, max_length=64)
    severity:       Severity
    confidence:     float         = Field(ge=0, le=1)
    anomaly_score:  float         = Field(ge=0)
    bboxes:         list[BBox]    = Field(default_factory=list, max_length=16)
    description:    str           = Field(default="", max_length=1024)
    variant:        Variant
    edge_ts:        datetime
    pipeline_ms:    dict[Stage, float]
    vlm_metrics:    Optional[VlmMetrics] = None
    trace_events:   Optional[list[TraceEvent]] = Field(default=None, max_length=64)  # v1.2: Chrome Trace 时序事件
    schema_version: Literal["v1"] = "v1"

    # v1.3: Phase 10 source fields (all optional for backward compat)
    localization_source: Optional[str] = Field(default=None, max_length=64)  # e.g. "yolov8n_detect_rknn"
    label_source:       Optional[str] = Field(default=None, max_length=64)  # e.g. "yolo_class_head"
    observation_source:  Optional[str] = Field(default=None, max_length=64)  # e.g. "template", "edge_vlm", "cloud_vlm"
    defect_family:      Optional[str] = Field(default=None, max_length=64)  # e.g. "surface_damage"
    observation:        Optional[str] = Field(default=None, max_length=1024)  # replaces description in v1.3
    severity_reason:    Optional[str] = Field(default=None, max_length=512)

    @field_validator("edge_ts")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("edge_ts must be timezone-aware (ISO 8601 with offset)")
        return v

    @field_validator("pipeline_ms")
    @classmethod
    def all_stages_required(cls, v: dict) -> dict:
        # v1.3: accept either old (fastsam/qwen3vl) or new (localizer) stage keys
        old_required = {"efficientad", "fastsam", "qwen3vl"}
        new_required = {"efficientad", "localizer", "upload"}
        if old_required <= v.keys():
            return v
        if new_required <= v.keys():
            return v
        # Backward compat: efficientad + fastsam without qwen3vl (VLM disabled)
        if "efficientad" in v and "fastsam" in v:
            return v
        missing = new_required - v.keys()
        raise ValueError(f"pipeline_ms missing stages: {missing}")

class DefectRead(DefectCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id:           int
    image_url:    str             # /static/defects/20260502/abc.jpg
    server_ts:    datetime

class DefectCreatedResponse(BaseModel):
    """POST /api/edge/report 200 响应（仅 3 字段）"""
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id:        int
    image_url: str
    server_ts: datetime
```

## 3. POST `/api/edge/report`

**Content-Type**：`multipart/form-data`

**Form 字段**：

| 名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `image` | file（image/jpeg） | ✅ | 原图，建议 q85，≤ 2 MB |
| `meta` | string（JSON） | ✅ | 序列化 `DefectCreate`，UTF-8 |
| `crop` | file（image/jpeg） | ❌ | 缺陷裁剪图，可选 |

**curl 示例**（C++ 端 libcurl 等价）：

```bash
curl -X POST https://vision.example.com/api/edge/report \
  -F "image=@/tmp/frame.jpg;type=image/jpeg" \
  -F 'meta={"line_id":"L1","category":"metal_nut","defect_type":"scratch",
            "severity":"high","confidence":0.92,"anomaly_score":3.41,
            "bboxes":[{"x":0.31,"y":0.42,"w":0.18,"h":0.12}],
            "description":"长条划痕",
            "variant":"2B_base","edge_ts":"2026-05-02T10:23:11Z",
            "pipeline_ms":{"efficientad":4.2,"fastsam":48.1,"qwen3vl":2310.5},
            "vlm_metrics":{"ttft_ms":2100,"decode_tps":11.4,"prompt_tokens":820,
                           "output_tokens":48,"rss_mb":3120,"json_parse_ok":true},
            "schema_version":"v1"};type=application/json'
```

**响应 200**：

```json
{ "id": 12345, "image_url": "/static/defects/20260502/9e3f...jpg", "server_ts": "2026-05-02T10:23:12.301Z" }
```

**错误响应**（统一格式）：

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": { "field": "..." } } }
```

后端实现要点：用 `UploadFile.read(1024*1024)` 流式落盘到 `static/defects/{YYYYMMDD}/{uuid4}.jpg`，避免一次性读入 OOM；写 DB 后 `await ws_manager.broadcast("dashboard", {"type": "defect_created", ...})`。

**实现补充**：
- 响应 schema 为 `DefectCreatedResponse`（id / image_url / server_ts 三字段），不返回 `DefectCreate` 的全部字段
- `schema_version` 检查必须在 Pydantic `model_validate` **之前**执行（先 `json.loads` 获取原始值检查，否则 Pydantic 会先拦截返回 400 而非 422）
- BBox 二次校验：路由层显式验证 `x+w ≤ 1` 与 `y+h ≤ 1`（Pydantic 只验证单字段范围，不验证叠加）
- 图片写入必须用 `aiofiles`（async），同步 `open()` 会阻塞 event loop

## 4. GET `/api/defects`

**Query 参数**：

| 名称 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `page` | int ≥ 1 | 1 | |
| `page_size` | int ∈ [1, 100] | 20 | |
| `category` | enum | — | MVTec AD 全 15 类（见 §2 DefectCreate.category） |
| `severity` | enum | — | low / medium / high |
| `variant` | enum | — | 2B_base / 2B_lora / 4B_base / 4B_lora（兼容 A / B） |
| `line_id` | string | — | |
| `since` | ISO8601 | — | edge_ts ≥ since |
| `until` | ISO8601 | — | edge_ts < until |
| `sort` | string | `-edge_ts` | 字段名前缀 `-` 表示降序 |

**响应 200**：

```json
{
  "items": [ /* DefectRead[] */ ],
  "total": 1248,
  "page": 1,
  "page_size": 20
}
```

## 5. GET `/api/defects/{id}`

返回单条 `DefectRead`；不存在返回 404 + `{ "error": { "code": "NOT_FOUND" } }`。

> 404 响应必须使用统一错误格式 `{"error": {"code": "NOT_FOUND", "message": "..."}}`，不得使用 FastAPI `HTTPException` 的默认 `{"detail": "..."}` 格式。

## 6. GET `/api/stats`

聚合统计，前端仪表盘卡片直接消费。

**Query 参数**：`since`（默认 24h 前）、`until`（默认 now）、`bucket`（`hour` / `day`，默认 `hour`）。

**响应 200**：

```json
{
  "total": 1248,
  "today_defects": 87,
  "today_high": 12,
  "by_category": { "metal_nut": 412, "screw": 380, "pill": 456 },
  "by_severity": { "low": 800, "medium": 320, "high": 128 },
  "timeline":   [ { "ts": "2026-05-02T09:00:00Z", "count": 23 } ],
  "ab_compare": {
    "2B_base": { "count": 312, "json_ok_rate": 0.812, "avg_ttft_ms": 2240, "avg_decode_tps": 11.2, "avg_rss_mb": 3110, "avg_prompt_tokens": 78, "avg_output_tokens": 98 },
    "2B_lora": { "count": 312, "json_ok_rate": 0.946, "avg_ttft_ms": 1180, "avg_decode_tps": 11.8, "avg_rss_mb": 3080, "avg_prompt_tokens": 78, "avg_output_tokens": 98 },
    "4B_base": { "count": 312, "json_ok_rate": 0.850, "avg_ttft_ms": 5500, "avg_decode_tps": 5.7, "avg_rss_mb": 8900, "avg_prompt_tokens": 78, "avg_output_tokens": 98 },
    "4B_lora": { "count": 312, "json_ok_rate": 0.960, "avg_ttft_ms": 5200, "avg_decode_tps": 5.8, "avg_rss_mb": 8700, "avg_prompt_tokens": 78, "avg_output_tokens": 98 }
  },
  "avg_pipeline_ms": {
    "efficientad": 12.3,
    "fastsam": 48.1,
    "qwen3vl": 2310.5,
    "localizer": 0,
    "upload": 0,
    "enrichment": 0
  },
  "category_severity_matrix": { "metal_nut": { "low": 300, "high": 112 } }
}
```

> **v1.3**: `avg_pipeline_ms` 新增 `localizer`、`upload`、`enrichment` 三个键。旧数据中这些键为 0。

## 7. GET `/api/health`

```json
{ "status": "ok", "version": "v1.1", "uptime_s": 3601, "db": "ok", "ws_clients": 3 }
```

## 8. WebSocket `/ws/dashboard`

**握手**：标准 `Upgrade: websocket`；无鉴权（演示项目）。生产可加 `?token=...`。

> **⚠️ 消息字段名必须严格按本表，不得自行扩展或替换字段名。**
> `hello` payload 只含 `ws_id` 和 `server_ts`；`ping` payload 只含 `ts`（非 `timestamp`）。
> WS 路由不能注入 `Request` 参数，访问 `app.state` 须用 `websocket.app.state`。
> 路由路径固定为 `/ws/dashboard`，不使用 `/{room}` 动态参数。

**消息类型**（服务端 → 客户端）：

| `type` | payload | 触发时机 |
|---|---|---|
| `hello` | `{ "ws_id": "...", "server_ts": "..." }` | 连接建立后立即发送 |
| `defect_created` | DefectRead | 新缺陷入库后广播；`data` 为完整 `DefectRead`，包含 `pipeline_ms`、`vlm_metrics`，并在可用时包含 `trace_events`。前端不得假设 `trace_events` 必然存在，必须按可选字段处理 |
| `metrics_tick` | `{ "ws_clients": int, "qps": float }` | 每 5 s |
| `ping` | `{ "ts": "..." }` | 每 30 s（保活） |

**客户端 → 服务端**：

| `type` | payload | 说明 |
|---|---|---|
| `pong` | `{}` | 响应服务端 ping |
| `subscribe` | `{ "rooms": ["dashboard"] }` | 预留，多房间扩展用 |

**心跳**：30 s 服务端发 `ping`，60 s 内无 `pong` 关闭连接。客户端断线后采用指数退避重连（1/2/4/8/15 s）。

**ConnectionManager 实现要点**：进程内单例，存于 `app.state.ws_manager`；支持按房间名过滤广播（当前只有 `"dashboard"` 房间，预留多房间扩展）；`asyncio.Lock` 保护连接集合；`broadcast` 用 `asyncio.gather(..., return_exceptions=True)` 避免单连接异常影响广播。多 worker 部署需引入 Redis pub/sub（v1 单 worker，留扩展点）。

## 9. 静态文件 `/static/defects/{date}/{file}`

- `date` 格式 `YYYYMMDD`，由后端落盘时按 `edge_ts` 计算。
- `file` 格式 `{uuid4}.jpg`。
- 生产环境由 Nginx / CDN 直接服务，不经 FastAPI；后端只暴露 URL。
- 开发环境由 FastAPI `StaticFiles(directory="static")` 挂载。

## 10. CORS 策略

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://vision.example.com"],
    allow_credentials=True,                  # 与 "*" 互斥
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=3600,
)
```

CORSMiddleware 必须最早注册以处理 OPTIONS 预检。

## 11. 错误码定义

| HTTP | code | 含义 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Pydantic 字段校验失败 |
| 400 | `INVALID_IMAGE` | 图片解码失败 / 超过 2 MB |
| 400 | `EMPTY_BBOXES` | bboxes 为空，无法 enrichment |
| 400 | `ZERO_CONFIDENCE` | confidence=0（回退占位），无法 enrichment |
| 400 | `FALLBACK_PLACEHOLDER` | 回退占位 defect，无法 enrichment |
| 400 | `INVALID_PROVIDER` | 未知 provider 名称 |
| 400 | `PROVIDER_CONFIG_ERROR` | provider 配置无效 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 404 | `NO_PENDING_ENRICHMENT` | process-next 无 pending job |
| 409 | `DUPLICATE_REPORT` | `(line_id, edge_ts)` 重复（幂等） |
| 409 | `DUPLICATE_ENRICHMENT` | 同一 defect + provider + prompt_version 已有 pending/running job |
| 409 | `ENRICHMENT_NOT_PENDING` | enrichment 不在 pending 状态，无法处理 |
| 413 | `PAYLOAD_TOO_LARGE` | multipart 总大小超限 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Content-Type 不是 multipart |
| 422 | `SCHEMA_MISMATCH` | `schema_version` 不被支持 |
| 500 | `INTERNAL_ERROR` | 服务端异常（落库失败等） |
| 501 | `PROVIDER_NOT_IMPLEMENTED` | provider 尚未实现（如 cloud_vlm） |
| 503 | `SERVICE_UNAVAILABLE` | DB / 磁盘探针失败 |

边缘端针对 408 / 429 / 5xx / 网络超时执行指数退避重试（500 ms × 2ⁿ + jitter，最多 5 次）。

## 12. 字段验证规则要点

- 所有 BBox 坐标为归一化 [0, 1]；`x+w ≤ 1` 与 `y+h ≤ 1` 由后端二次校验。
- `bboxes` 最多 16 个（与 vlm_bbox_ref.py 五级净化一致）。
- `description` ≤ 1024 字符（Qwen3-VL 输出 ~50–200 token，留余量）。
- `pipeline_ms` 三个键缺一不可。
- `edge_ts` 必须含时区（ISO 8601 with offset）；裸 naive datetime 拒绝。
- 图片尺寸建议 ≤ 2048×2048；后端解码后超过则压缩到 1280 长边。

## 13. 接口契约的可测试性

模拟器 `simulator/line_runner.py` 同时是**契约测试客户端**，必须在 `backend/tests/contract/` 提供：

1. `test_post_report_happy_path.py`
2. `test_post_report_validation.py`
3. `test_post_report_retry.py`
4. `test_get_defects_pagination.py`
5. `test_get_stats_ab_compare.py`
6. `test_ws_dashboard_broadcast.py`

CI 中跑 `pytest backend/tests/contract/` 必须全绿才允许 merge。轨道 B 上板时，C++ 客户端通过同一组测试即视为契约合规。

---

## 14. Phase 10.1 Enrichment API（v1.3 addendum）

> **`schema_version` 保持 `"v1"`** — enrichment 路由不改变 payload schema 版本号。

### 14.1 Non-blocking Rule

- `POST /api/edge/report` **不调用 VLM**，不启动 enrichment 处理。
- `POST /api/edge/report` **不自动创建 enrichment job**（无 auto-enqueue）。
- enrichment 处理完全由手动路由触发（Phase 10.1a）。
- auto-enqueue 将在 Phase 10.1b 实现，受 `ENRICHMENT_ENABLED` / `ENRICHMENT_AUTO_ENQUEUE` 环境变量控制。

### 14.2 `defect_enrichments` Table

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK | 自增 |
| `defect_id` | INTEGER FK → defects.id | 索引 |
| `provider` | VARCHAR(32) | `"edge_vlm"` / `"template"` / `"cloud_vlm"` |
| `provider_model` | VARCHAR(128) | 如 `"qwen3-vl-2b-base"` / `"template"` |
| `prompt_version` | VARCHAR(64) | 如 `"phase10_1_obs_v1"` |
| `status` | VARCHAR(16) | 状态机，见 §14.3 |
| `observation` | TEXT | VLM 输出观察描述 |
| `severity_reason` | TEXT | VLM 输出严重性依据 |
| `accepted_box_ids` | JSON | VLM 确认的 box ID 列表 |
| `input_digest` | VARCHAR(128) | 输入摘要（sha256） |
| `raw_response` | TEXT | VLM 原始 JSON 响应（调试用） |
| `error_message` | VARCHAR(512) | 错误信息 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 最后更新时间 |
| `completed_at` | DATETIME | 完成时间（终态） |

唯一约束：`(defect_id, provider, prompt_version)`

### 14.3 Enrichment Status Machine

```
pending → running → complete
                  → failed
                  → rejected
```

| 状态 | 含义 |
|---|---|
| `pending` | 等待处理 |
| `running` | 正在调用 provider |
| `complete` | 成功，observation 已更新到 defects 表 |
| `failed` | provider 错误 / 超时 / 异常 |
| `rejected` | hallucination guard 拒绝（禁止键或格式错误） |
| `skipped` | 预留（Phase 10.1b 跳过逻辑） |

### 14.4 Providers

| provider | 说明 | 可用性 |
|---|---|---|
| `template` | 确定性模板，无外部调用 | 始终可用 |
| `edge_vlm` | RK3588 VLM（subprocess/http） | Phase 10.1a 为 disabled shell |
| `cloud_vlm` | 云端 VLM（provider-neutral） | 未实现，返回 501 |

### 14.5 Hallucination Guard

enrichment worker 在写入 defects 表前，通过 `validate_vlm_output()` 校验 provider 原始响应。

**允许输出键（ALLOWED_KEYS）**：

| 键 | 说明 |
|---|---|
| `observation` | 短观察描述（≤ 1024 字符） |
| `severity_reason` | 严重性依据（≤ 512 字符） |
| `accepted_box_ids` | VLM 确认的 box ID 列表（可选） |

**禁止输出键（FORBIDDEN_KEYS）** — 出现任一即拒绝：

| 键 | 所有者 |
|---|---|
| `bbox` / `bboxes` | YOLO/ORT localizer |
| `mask` | 未使用 |
| `category` | YOLO class head |
| `defect_type` | YOLO class head |
| `confidence` | YOLO detection score |
| `anomaly_score` | EfficientAD |
| `geometry_correction` | 不适用 |
| `localization_source` | YOLO/ORT localizer |
| `label_source` | YOLO class head |

### 14.6 Immutable Field Protection

enrichment 成功时，**只更新** defects 表的以下三个字段：

- `observation`
- `severity_reason`
- `observation_source`（设为 provider 名称）

**永远不更新**的 YOLO/ORT 拥有字段：

- `bboxes`
- `defect_type`
- `category`
- `confidence`
- `anomaly_score`
- `localization_source`
- `label_source`

### 14.7 POST `/api/defects/{id}/enrich`

创建 pending enrichment job。**不调用 VLM，不处理 job。**

**响应 202**：
```json
{ "enrichment_id": 42, "defect_id": 123, "status": "pending" }
```

**错误**：

| HTTP | code | 条件 |
|---|---|---|
| 404 | `NOT_FOUND` | defect 不存在 |
| 400 | `EMPTY_BBOXES` | bboxes 为空 |
| 400 | `ZERO_CONFIDENCE` | confidence=0 |
| 400 | `FALLBACK_PLACEHOLDER` | 回退占位 defect |
| 409 | `DUPLICATE_ENRICHMENT` | 同 defect + provider + prompt 已有 pending/running |

### 14.8 GET `/api/defects/{id}/enrichment`

返回最新 enrichment 记录。

**响应 200**：
```json
{
  "id": 42,
  "defect_id": 123,
  "provider": "template",
  "provider_model": "template",
  "prompt_version": "phase10_1_obs_v1",
  "status": "complete",
  "observation": "[Template] metal_nut: scratch detected...",
  "severity_reason": "[Template] Severity assigned by default rule.",
  "accepted_box_ids": [0],
  "error_message": null,
  "created_at": "2026-05-26T10:00:00Z",
  "updated_at": "2026-05-26T10:00:01Z",
  "completed_at": "2026-05-26T10:00:01Z"
}
```

**错误**：404 `NOT_FOUND` — 无 enrichment 记录。

### 14.9 POST `/api/enrich/{enrichment_id}/process?provider=`

手动处理单个 pending enrichment job。

**Query 参数 `provider`**：

| 值 | 行为 |
|---|---|
| 省略 / 空 | 使用环境变量默认（默认 `edge_vlm disabled`） |
| `template` | 确定性 TemplateProvider |
| `edge_vlm` | 使用环境变量配置的 EdgeVlmProvider |
| `cloud_vlm` | 501 `PROVIDER_NOT_IMPLEMENTED` |
| 其他 | 400 `INVALID_PROVIDER` |

**不接受**：command、endpoint、token、credentials、model path 等 query 参数。

**成功响应 200**：`DefectEnrichmentRead`（含更新后的 status / observation / severity_reason）。

**错误**：

| HTTP | code | 条件 |
|---|---|---|
| 404 | `NOT_FOUND` | enrichment 不存在 |
| 409 | `ENRICHMENT_NOT_PENDING` | enrichment 不在 pending 状态 |
| 400 | `INVALID_PROVIDER` | 未知 provider |
| 400 | `PROVIDER_CONFIG_ERROR` | provider 配置错误 |
| 501 | `PROVIDER_NOT_IMPLEMENTED` | cloud_vlm 未实现 |

### 14.10 POST `/api/enrich/process-next?provider=`

手动处理最早的 pending enrichment job。

**响应 200**：`DefectEnrichmentRead`。
**错误 404**：`NO_PENDING_ENRICHMENT` — 无 pending job。

provider query 参数行为同 §14.9。

### 14.11 Frontend Display Behavior

- `observation_source` 控制右侧面板标题：
  - `"template"` → "检测输出 · Template"
  - `"edge_vlm"` → "边缘 VLM 增强 · Edge VLM"
  - `"cloud_vlm"` → "云端 VLM 增强 · Cloud VLM"
  - null / 缺失 → "检测输出 · Detector"
- observation / severity_reason 面板始终可见（null 时显示模板 fallback 文案）
- 溯源 tab 显示 BBox 来源、标签来源、观察来源 + VLM safety caveat
- JSON tab 文件名按 observation_source 变化（`template_output.json` / `edge_vlm_enrichment.json` / `detector_output.json`）
