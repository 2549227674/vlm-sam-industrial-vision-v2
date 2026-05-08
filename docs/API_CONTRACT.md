# API 接口契约 v1

本文档是 RK3588 边缘端、Python 模拟器、FastAPI 后端、Next.js 前端之间的**唯一权威接口定义**。任何字段或语义变更必须先改本文档（bump 版本），再改实现。模拟器是契约测试客户端，覆盖所有路径。

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

Base URL：开发 `http://localhost:8000`，生产 `https://vision.example.com`。所有请求/响应 JSON 字段统一 `snake_case`。

## 2. 数据 Schema（Pydantic v2）

```python
# backend/app/schemas/defect.py
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high"]
Variant  = Literal["A", "B"]
Stage    = Literal["efficientad", "fastsam", "qwen3vl"]

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

class DefectCreate(BaseModel):
    """随 multipart 一同提交的 JSON 字段（form 字段名 'meta'）"""
    model_config = ConfigDict(extra="forbid")
    line_id:        str           = Field(min_length=1, max_length=32)
    category:       Literal["metal_nut", "screw", "pill"]
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
    schema_version: Literal["v1"] = "v1"

    @field_validator("edge_ts")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("edge_ts must be timezone-aware (ISO 8601 with offset)")
        return v

    @field_validator("pipeline_ms")
    @classmethod
    def all_stages_required(cls, v: dict) -> dict:
        required = {"efficientad", "fastsam", "qwen3vl"}
        if missing := required - v.keys():
            raise ValueError(f"pipeline_ms missing stages: {missing}")
        return v

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
            "variant":"A","edge_ts":"2026-05-02T10:23:11Z",
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
| `category` | enum | — | metal_nut / screw / pill |
| `severity` | enum | — | low / medium / high |
| `variant` | enum | — | A / B |
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
  "by_category": { "metal_nut": 412, "screw": 380, "pill": 456 },
  "by_severity": { "low": 800, "medium": 320, "high": 128 },
  "timeline":   [ { "ts": "2026-05-02T09:00:00Z", "count": 23 } ],
  "ab_compare": {
    "A": { "count": 624, "json_ok_rate": 0.812, "avg_ttft_ms": 2240, "avg_decode_tps": 11.2, "avg_rss_mb": 3110 },
    "B": { "count": 624, "json_ok_rate": 0.946, "avg_ttft_ms": 1180, "avg_decode_tps": 11.8, "avg_rss_mb": 3080 }
  }
}
```

## 7. GET `/api/health`

```json
{ "status": "ok", "version": "v1", "uptime_s": 3601, "db": "ok", "ws_clients": 3 }
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
| `defect_created` | DefectRead | 新缺陷入库后广播 |
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
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `DUPLICATE_REPORT` | `(line_id, edge_ts)` 重复（幂等） |
| 413 | `PAYLOAD_TOO_LARGE` | multipart 总大小超限 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Content-Type 不是 multipart |
| 422 | `SCHEMA_MISMATCH` | `schema_version` 不被支持 |
| 500 | `INTERNAL_ERROR` | 服务端异常（落库失败等） |
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
