# 系统架构

本文档定义 vlm-sam-industrial-vision-v2 的端云分离架构、三段式异步推理流水线、数据流时序、AB 测试方案与性能预算。所有数字基于 2026 年 5 月公开资料；标注「TBD-上板实测」的为推算值，等真机部署后回填。

## 1. 全局拓扑

```
┌──────────────────────────┐         ┌────────────────────────┐         ┌────────────────────────┐
│   RK3588 16GB Edge       │         │  Backend (FastAPI)     │         │  Frontend (Next.js 15) │
│                          │         │                        │         │                        │
│  ┌────────────────────┐  │  HTTPS  │  POST /api/edge/report │  WS     │  Dashboard             │
│  │ T1 Capture         │  │ ───────►│  multipart/form-data   │ ───────►│  - DataTable (defects) │
│  │ T2 Pipeline (EAD)  │  │         │                        │         │  - ECharts AB charts   │
│  │ T3 VLM Worker      │  │         │  GET /api/defects      │         │  - Sonner toast        │
│  │   (FastSAM+Qwen3VL)│  │         │  GET /api/stats        │         │  - Realtime panel      │
│  │ T4 Upload (curl)   │  │ ◄───────│  GET /api/health       │◄─────── │                        │
│  └────────────────────┘  │  200 OK │                        │  static │                        │
│   librknnrt librkllmrt   │         │  /static/defects/...   │  imgs   │                        │
│   librga libcurl V4L2    │         │  WS /ws/dashboard      │         │                        │
└──────────────────────────┘         │                        │         └────────────────────────┘
                                     │  SQLAlchemy 2.0 async  │
                                     │  aiosqlite vision.db   │
                                     └────────────────────────┘
```

边缘端只做客户端角色（HTTP POST + 静态文件读）；后端是唯一的 WebSocket 服务方；前端纯静态导出（`output: 'export'`）部署到任意 CDN/Nginx。

## 2. 三组件职责

### 2.1 边缘端（RK3588 16GB）

- 取帧（V4L2 真机模式 / 图片集循环测试模式），经 RGA resize/colorspace 转换，输入 EfficientAD-S 计算异常分数。
- 异常分数高于阈值时，触发 FastSAM 分割 + Qwen3-VL-2B 生成 JSON 描述。
- 每个上报包含原图、缺陷裁剪图、JSON 元数据，HTTP multipart 上传，失败指数退避重试。
- **不**存储历史数据、**不**做 UI、**不**做 WebSocket 服务、**不**跑 Python Web 框架。

### 2.2 后端（FastAPI）

- 接收 multipart 报文，落盘图片到 `static/defects/{YYYYMMDD}/{uuid}.jpg`，元数据写入 SQLite（`defects` 表，含 `trace_events` JSON 列用于前端 ProfilePage 性能追踪）。
- 提供 REST 查询接口（分页、过滤、AB 聚合）与静态文件服务（开发模式由 FastAPI StaticFiles，生产模式由 Nginx 直接 serve）。
- 维护 WebSocket `ConnectionManager` 进程内单例，向前端实时广播 `defect_created` / `metrics_tick` 事件。
- **不**做模型推理、**不**调用云端 LLM、**不**生成报告。

### 2.3 前端（Next.js 15）

- App Router + `output: 'export'` 纯静态导出，部署到 Nginx / Vercel / Cloudflare Pages 静态托管。
- 仪表盘三大模块：实时缺陷流水（DataTable + WebSocket 推送）、统计聚合图（ECharts AB 对比柱状图、缺陷类别分布）、单帧详情（图片 + bbox overlay + JSON）。
- 仅消费后端 REST + WebSocket，**不**直接连 RK3588。
- `app/layout.tsx` 保持 Server Component（提供 `<html><body>`），其余业务页面/组件全部 `'use client'`。

## 3. 三段式推理流水线设计

### 3.1 C++ 四线程模型

```
┌─────────────┐  Q1  ┌──────────────────┐  Q2  ┌──────────────────────┐  Q3  ┌──────────────┐
│ T1 Capture  ├─────►│ T2 Pipeline      ├─────►│ T3 VLM Worker        ├─────►│ T4 Upload    │
│  V4L2 /     │ cap  │  RGA resize      │ cap  │  FastSAM + Qwen3-VL  │ cap  │  libcurl     │
│  Image loop │ =4   │  EfficientAD-S   │ =2   │  bbox 净化 + JSON    │ =4   │  multipart   │
└─────────────┘ drop └──────────────────┘ drop └──────────────────────┘ drop └──────────────┘
                old                       old                            old
```

- **Q1 / Q3** 容量 4，缓冲短时抖动。
- **Q2** 容量 2 + drop-oldest，VLM 慢于异常检测时主动丢弃旧帧（保延迟优先）。
- 所有线程使用 `std::jthread` + `std::stop_token`，主线程析构时自动 `request_stop()` + `join()`。

```mermaid
flowchart TD
  subgraph Edge["EDGE DEVICE | RK3588 16GB (Orange Pi 5 Plus) | 6 TOPS NPU x3"]
    subgraph Pipeline["4-Thread C++ Pipeline"]
      T1["T1: Capture\nV4L2 / Image Loop"]
      Q1["Q1\ncap=4"]
      T2["T2: Pipeline\nEfficientAD-S FP16\n256x256 + RGA"]
      Q2["Q2\ncap=2"]
      T3["T3: VLM Worker\nFastSAM FP16 640x640\nQwen3-VL-2B/4B W8A8"]
      Q3["Q3\ncap=4"]
      T4["T4: Upload\nlibcurl"]
      T1 -->|frame| Q1 -->|frame| T2 -->|frame + score| Q2 -->|candidates| T3 -->|defect JSON + img| Q3 -->|result| T4
    end
    subgraph ModelZoo["Model Zoo (RKNN / RKLLM)"]
      EAD["EfficientAD-S\nFP16 RKNN (no-quant)"]
      FS["FastSAM-s\nFP16 RKNN (no-quant)"]
      QV["Qwen3-VL-2B/4B\nW8A8 RKLLM + Vision RKNN"]
    end
    EAD -.-> T2
    FS -.-> T3
    QV -.-> T3
  end

  T4 -->|multipart POST\n(no Base64)| Backend

  subgraph Backend["BACKEND SERVER | Python 3.12 + FastAPI"]
    POST["POST /api/edge/report\nmultipart/form-data\nimages -> static/defects/"]
    SF["Static Files\nstatic/defects/*.jpg"]
    POST -->|save| SF
    subgraph APILayer["API Layer"]
      GD["GET /api/defects\npagination"]
      GS["GET /api/stats\nmatrix / ab_compute"]
      GH["GET /api/health"]
    end
    SQL["SQLite WAL\nSQLAlchemy 2.0"]
    WS["WebSocket Manager\n/ws/dashboard\nheartbeat + broadcast"]
    APILayer -->|REST JSON| SQL
    WS --> Frontend
  end

  subgraph Frontend["FRONTEND | Next.js 15 | output: export"]
    WSC["WebSocket Client\nreconnect + Sonner toast"]
    TABS["5 Tabs\nOverview | Profile\nAB Matrix | Models | Logs"]
    TAB["TanStack Table v8\nReal-time defect streams"]
    SVG["v4 SVG Charts\nKPI / Waterfall /\nMatrix / AB 5-axis"]
    IMG["img src from\nbackend static/*.jpg"]
    WSC -->|WS subscribe| TABS
  end

  SF -->|HTTP img| IMG
```

![系统全局拓扑](figures/fig1_topology.png)

```mermaid
flowchart LR
  subgraph Metrics["Atomic Metric Counters"]
    m1["capture"]
    m2["ead_gate_pass"]
    m3["ead_gate_drop"]
    m4["vlm_ok"]
    m5["vlm_fallback"]
    m6["upload_ok"]
    m7["upload_fail"]
    m8["queue_drop"]
  end

  subgraph T1S["T1 Capture Thread"]
    T1C["V4L2 / ioctl\nor Image-Set Loop"]
  end

  T1S -->|raw frames| Q1

  Q1[("Q1\nBoundedQueue\ncapacity=4\ndrop-oldest")]

  Q1 -->|frame| T2S

  subgraph T2S["T2 Pipeline Thread"]
    direction LR
    EAD["EfficientAD-S\nRKNN Inference\n256x256 FP16"] --> GD{{"Gate Decision\nThreshold Mode"}}
    GD -->|PASS| ATT["Attach Score\n+ Metadata"]
    GD -->|DROP| DROP["DROP\nead_gate_drop++"]
  end

  T2S -->|frame + score| Q2

  Q2[("Q2\nBoundedQueue\ncapacity=2\ndrop-oldest")]

  Q2 -->|frame + score| T3S

  subgraph T3S["T3 VLM Worker Thread"]
    direction LR
    R1["RGA Resize\nto 640x640"] --> FS["FastSAM\nRKNN Inference\n640x640 FP16"] --> BBOX["5-Level Bbox\nPurification"] --> R2["RGA Resize\nto 448x448"] --> VE["Qwen3-VL Vision\nEncoder RKNN\n448x448"] --> LLM["Qwen3-VL LLM\nRKLLM Inference\nW8A8"] --> JSON["Structured\nJSON Output"]
  end

  T3S -->|result| Q3

  Q3[("Q3\nBoundedQueue\ncapacity=4\ndrop-oldest")]

  Q3 -->|result| T4S

  subgraph T4S["T4 Upload Thread"]
    CURL["libcurl\nmultipart POST"] --> BE["FastAPI\nBackend"]
  end
```

![四线程流水线详图](figures/fig2_pipeline.png)

### 3.2 三段模型定位

| Stage | 模型 | 输入 | 输出 | RK3588 延迟 | 备注 |
|---|---|---|---|---|---|
| 1 | EfficientAD-S | 256×256 RGB | anomaly_map + score (FP16 raw) | 6–12 ms（单核）/ 3–5 ms（三核）TBD-上板实测 | Anomalib 将 Teacher/Student/AE 三子网络封装为**单一 ONNX**，转**单个 RKNN**文件；FP16/no-quant（INT8 分布失真，已弃用） |
| 2 | FastSAM-s | **640×640** | bbox proposal (mask decode TODO) | ~30–60 ms | 仅 Stage 1 触发后跑；FP16/no-quant；分辨率固定 640（MVTec 900×900 降采样对厘米级缺陷无影响；如需检测微米级特征可调至 1024，延迟约增 2–3 倍） |
| 3 | Qwen3-VL-2B | 448×448 + prompt | JSON 文本 | TTFT 2–3 s（短 prompt）/ 5–10 s（长 prompt），decode 11.5 tokens/s，RAM 3.1 GB | 异步 worker，drop-oldest |
| 3 | Qwen3-VL-4B | 448×448 + prompt | JSON 文本 | TTFT 热 ~5–6 s，decode 5.7 tokens/s，RAM 8.7 GB，Pipeline 总峰值 ~11.4 GB | 异步 worker，drop-oldest；rknn-llm v1.2.3 支持 |

**EfficientAD-S 选型理由**：替代 PaDiM 解决位置敏感性问题（PaDiM 对像素位置敏感，工业件轻微平移即误报）；PDN 全卷积、平移等变；MVTec AD image-AUROC 平均 98.8%（论文 5 次平均），三类基准 metal_nut 0.979 / pill 0.987 / screw 0.960（Anomalib benchmark）。

#### EfficientAD Raw Output Deployment Update（Phase 7 Prompt 2B）

Phase 7 上板实测后，EfficientAD-S 不再直接使用 Anomalib ONNX 的 post_processor 输出 `pred_score/anomaly_map` 作为 T2 gate。

原因：

1. `pred_score/anomaly_map` 是 post_processor 后的 Clip 输出，good/defect 均可能饱和到接近 1.0。
2. `pred_label/pred_mask` 中的 Greater 节点在 RKNN Runtime 上触发 INT8/FLOAT 类型不支持。
3. raw INT8 RKNN 对 raw anomaly map 的分布造成明显失真。

当前主路线：

- 导出 post_processor 前 raw tensor：
  - `raw_score` (`/model/ReduceMax_output_0`)
  - `raw_anomaly_map` (`/model/Add_output_0`)
- 转换为 FP16/no-quant RKNN：
  - `model_raw_noquant.rknn`
- C++ T2 根据 `efficientad_score_mode` 计算 final_score：
  - raw_score / map_max / map_mean / map_top1 / map_top01
- C++ T2 根据 `efficientad_gate_mode` 决策：
  - threshold：正式默认
  - pass_all：debug only

说明：

- `efficientad_threshold_default: 0.50` 是旧 post_processor 输出 [0,1] 尺度的占位值，不适用于 raw output。
- per-category threshold 将在 Phase 8 系统校准。
- 原始 INT8 量化 RKNN（Phase 6 产出的 `model.rknn`）仍保留，但当前 T2 主路线使用 FP16/no-quant `model_raw_noquant.rknn`。
- 详细排错过程见 `docs/experiments/phase7_prompt2b_efficientad_edge_report.md`。

#### FastSAM FP16/no-quant Deployment（Phase 7 Prompt 2C/2C-Fix）

Phase 7 Prompt 2C 发现 FastSAM-s INT8 量化存在严重精度问题：

- INT8 per-tensor quantization（scale=2.82, zp=-119）将 YOLOv8 置信度压缩到近零范围。
- INT8 模式下 8400 个 anchor 全部 conf < 0.25，raw candidates=0，100% fallback。
- FP16 top-1 conf = 0.8794，INT8 top-1 conf ≈ 0.003。

解决方案：`do_quantization=False` 导出 FP16/no-quant RKNN（`fastsam_s_noquant.rknn`, 26MB）。

Prompt 2C-Fix 新增 5 级 bbox cleanup 管线：

| 级别 | 过滤 | 阈值 |
|---|---|---|
| L1 | 边界裁剪 | clamp to [0,1] |
| L2 | 最小面积 | 0.001 |
| L3 | 最大面积 | 0.95 |
| L4 | IoU 去重 | 0.70 |
| L5 | 数量限制 | max 5 |

FP16 模式 fallback 率：0%（0/31 帧）。

详细报告：`docs/experiments/phase7_prompt2c_fastsam_edge_report.md`

#### Qwen3-VL 2B Base RKLLM Integration（Phase 7 Prompt 2D/2D-Fix）

Qwen3-VL 2B W8A8 base 在 RK3588 上完成 vision encoder + RKLLM 完整链路：

- Vision encoder：448×448 输入，196 image tokens，2048 embed dim，4 头并行输出
- RKLLM：W8A8 量化，callback 流式输出，enable_thinking=false
- Compact JSON prompt 设计：`[[x,y,w,h]]` 格式将输出从 196 tokens 降至 ~89 tokens
- 3 级 fallback：VLM init 失败 → JSON 解析失败 → bbox fallback

Prompt 2D-Fix 修补：

- VLM bbox 归一化（像素坐标 / orig_w × orig_h）+ 保守融合（IoU>0.3 才替换 FastSAM）
- severity 白名单统一为 low/medium/high（移除 critical）
- LoRA/variant 路径通过 config 切换（2B base / 2B lora / 4B TODO）
- upload trace_event 作为第 6 个事件追加到 trace_events 数组

关键性能数据（2B base W8A8）：

| 指标 | 实测值 |
|---|---|
| RSS | 3321-3324 MB |
| Vision encoder | ~2380 ms |
| TTFT | ~2100 ms |
| Decode speed | ~10 tok/s |
| Output tokens | 54-92 |
| json_parse_ok | 100% |

详细报告：`docs/experiments/phase7_prompt2d_qwen3vl_edge_report.md`、`phase7_prompt2d_fix_report.md`

#### True E2E 与 Threshold 验证（Phase 7 Prompt 2E/2F）

Prompt 2E 完成四线程全链路端到端验收（8 图 4 类，24 帧全部成功上传）。
Prompt 2F 完成 threshold 模式工程验证（覆盖型 vs 过滤型对比）。

新增 PipelineMetrics 可观测指标：

```cpp
alignas(kCacheLine) std::atomic<uint64_t> ead_gate_pass{};  // T2 推入 Q2
alignas(kCacheLine) std::atomic<uint64_t> ead_gate_drop{};  // T2 阈值拦截
```

queue dropped_count 语义：退出前收集 q1+q2+q3 的 `dropped()` 总和。

详细报告：`docs/experiments/phase7_prompt2e_e2e_acceptance_report.md`、`phase7_prompt2f_threshold_report.md`

**Qwen3-VL 降级备选**（部署失败时按此顺序，**只改 `edge/config.yaml`，不改 C++ 代码**）：

| 优先级 | 模型 | 推荐场景 | 预期 tps | RAM | 备注 |
|---|---|---|---|---|---|
| 主选 | **Qwen3-VL-4B** | 精度优先，内存充足 | 5.7 | 8.7 GB | rknn-llm v1.2.3 官方支持，Qengineering 有预转换 |
| 备选1 | **Qwen3-VL-2B** | 低延迟，内存紧张 | 11.5 | 3.1 GB | 已完成转换，开箱即用 |
| 备选2 | Qwen2.5-VL-3B | 4B 部署失败时 | ~7 | ~4.8 GB | 社区资料最丰富，happyme531 有预转换 |
| 备选3 | InternVL3.5-2B | 超低延迟需求 | ~11 | ~3 GB | rknn-llm v1.2.3 官方支持 |
| 备选4 | Qwen2-VL-2B | 最稳定保底 | ~12 | ~3 GB | 最老牌稳定 |
| **排除** | ~~Qwen3.5 系列~~ | 不可用 | — | — | rknn-llm #472：Gated DeltaNet 架构不支持 |

### 3.3 Qwen3-VL-4B 已知部署问题

**rknn-llm Issue #421（视觉精度回退）**：
- v1.2.3 视觉 encoder（827 MB）在 OCR/描述任务精度不如 v1.2.2（670 MB）
- 推荐混搭：**v1.2.2 视觉 .rknn + v1.2.3 runtime**（社区验证可行）

**rknn-llm Issue #388（自转换不稳定）**：
- `image_enc.cc` 行 80-81 存在段错误，需应用 wangjl1993 社区 patch
- 自行从 HuggingFace 转换 4B 成功率低，推荐直接使用 Qengineering 预转换文件

**多图输入不支持**：本项目单图输入，不受影响。

**视觉 encoder 分辨率编译时固定为 448×448**：MVTec crop 做 letterbox 上采样。

### 3.4 关键算子与零拷贝

- T1 拿到 V4L2 dma_buf fd → 包装 `UniqueFd` → 入 Q1。
- T2 用 `importbuffer_fd` 导入 RGA → `imresize` → 输出张量直接 `rknn_create_mem_from_fd` 喂入 NPU，避免一次 memcpy。
- T3 异步：异常分数高才触发；FastSAM 与 Qwen3-VL 串行（共享 NPU 资源）。
- T4 libcurl 复用 easy handle，只 `curl_easy_reset` 不 `cleanup`，TLS 连接池命中率接近 100%。

**EfficientAD-S INT8 量化实测发现（阶段 6.2，rknn-toolkit2 v2.3.2 — Phase 6 初始转换结果，Phase 7 已调整主路线，见下方 Raw Output Update）**：

build 阶段确认 dtype 变更：
- 输入 `input`：float32 → int8
- 输出 `anomaly_map`：float32 → int8
- 输出 `pred_score`：float32 → int8

T2 Pipeline Worker C++ 实现必须注意：
1. 喂入 RKNN 的输入张量类型为 INT8，RGA 输出后需做类型转换
2. 读出的 anomaly_map 和 pred_score 为 INT8，必须用 `rknn_query(RKNN_QUERY_OUTPUT_ATTR)` 获取 scale/zero_point，再做反量化：`real_val = (int8_val - zero_point) * scale`
3. 反量化后的 pred_score 再与 `config.yaml` 中的阈值比较决定是否触发 FastSAM

**FastSAM-s INT8 量化实测发现（阶段 6.3，rknn-toolkit2 v2.3.2）**：

- 输入 `images` / 输出 `output0`（det）/ 输出 `output1`（proto）均为 INT8
- 两路输出的 scale/zero_point **独立**，必须分别用 `rknn_query(RKNN_QUERY_OUTPUT_ATTR)` 获取，禁止共用同一组量化参数
- `output1`（prototype masks）entire cosine = **0.966**，低于 0.99 阈值，需上板实测确认分割质量是否可接受
- 无 CPU fallback 算子，整图跑在 NPU 上

代码模板（BoundedQueue、UniqueFd、libcurl HTTP client、Worker）见本文档 §11 代码生成规范。

## 4. 数据流时序

### 4.1 PC 模拟器模式（轨道 A 期间）

```
simulator (Python)            backend (FastAPI)            frontend (Next.js)
     │                             │                              │
     │ POST /api/edge/report       │                              │
     │ (multipart: image+meta)     │                              │
     ├────────────────────────────►│                              │
     │                             │ 落盘图片 + 写 SQLite          │
     │                       200 OK│                              │
     │◄────────────────────────────┤ broadcast(defect_created)    │
     │                             ├─────────────────────────────►│
     │                             │                              │ <img src="/static/...">
     │ sleep(beat=1.5s, jitter)    │                              │ DataTable 新增行
     │ next image from MVTec set   │                              │ Sonner toast
     ▼                             ▼                              ▼
（PC 端开多线程模拟多产线，每条独立节拍）
```

```mermaid
sequenceDiagram
  participant V4L2 as V4L2 Camera
  participant T1 as T1 Capture
  participant Q1 as Q1 Queue
  participant T2 as T2 Pipeline
  participant Q2 as Q2 Queue
  participant T3 as T3 VLM Worker
  participant Q3 as Q3 Queue
  participant T4 as T4 Upload
  participant BE as Backend FastAPI
  participant DB as SQLite
  participant FE as Frontend Next.js

  Note over V4L2,FE: End-to-End Data Flow | Total ~12s/frame

  rect rgb(220, 252, 231)
    Note over V4L2,T1: Stage 1: Frame Capture
    T1->>T1: raw frame (V4L2 ioctl / image-set read)
    T1->>Q1: enqueue frame
  end

  rect rgb(255, 237, 213)
    Note over Q1,T2: Stage 2: Anomaly Detection (~350ms)
    Q1-->>T2: dequeue frame
    T2->>T2: RGA resize: 256x256
    T2->>T2: EfficientAD-S RKNN infer
    T2->>T2: score + gate check
    alt gate PASS
      T2->>Q2: enqueue (frame + score)
    else gate DROP
      T2->>T2: drop frame (skip T3/T4)
    end
  end

  rect rgb(219, 234, 254)
    Note over Q2,Q3: Stage 3: VLM Analysis (~11s)
    Q2-->>T3: dequeue frame
    T3->>T3: RGA resize: 640x640
    T3->>T3: FastSAM RKNN (~250ms)
    T3->>T3: bbox purification (5-level)
    T3->>T3: RGA resize: 448x448
    T3->>T3: Qwen3-VL vision RKNN (~2.5s)
    T3->>T3: LLM RKLLM decode (~6s)
    T3->>T3: JSON output (category/severity/confidence/bbox)
    T3->>Q3: enqueue result (image + JSON + trace_events)
  end

  rect rgb(220, 252, 231)
    Note over Q3,T4: Stage 4: Upload (~50ms)
    Q3-->>T4: dequeue result
    T4->>BE: HTTP POST multipart/form-data
  end

  rect rgb(251, 207, 232)
    Note over BE,DB: Backend Processing
    BE->>DB: INSERT defect (SQLite WAL)
    BE->>FE: WebSocket push (new defect)
  end

  rect rgb(251, 207, 232)
    Note over FE,FE: Dashboard Update
    FE->>FE: DataTable + KPI + charts refresh
  end

  Note over V4L2,FE: 4 Threads + 3 BoundedQueues | Async Pipeline
```

![端云数据流时序图](figures/fig3_sequence.png)

### 4.2 RK3588 真机模式（轨道 B 落地后）

```
RK3588 C++ pipeline                              backend                  frontend
  │                                                │                         │
  │ T1: V4L2 DQBUF (dma_buf fd) 或 图片集循环      │                         │
  │ T2: RGA resize → EfficientAD-S NPU             │                         │
  │     score > thr ? 是 → Q2                      │                         │
  │ T3: FastSAM mask → bbox 净化 → Qwen3-VL JSON   │                         │
  │ T4: libcurl multipart POST ───────────────────►│                         │
  │                                       200 / err│ broadcast ─────────────►│
  │  (失败入 retry 队列，指数退避 0.5/1/2/4/8 s)    │                         │
  ▼                                                ▼                         ▼
```

两种模式对后端报文**完全相同**，靠 API 契约保证可替换性。

## 5. 静态图片集循环测试方案

**为什么不用视频流 / iPad 投影 / OBS 虚拟摄像头**：

1. 视频编解码引入光学退化与压缩损失，混淆推理时延的归因。
2. iPad 投影 + 摄像头会引入摩尔纹、反光、过曝、帧同步问题，使 EfficientAD-S 把光学伪影当成异常特征。
3. 静态图集循环可控、可复现、可基准化，便于跑回归测试。

**实现**：模拟器和 C++ 端均提供「Image Loop Capture」模式：

- 输入：`MVTec/{category}/test/{defect_type}/*.png`
- 节拍：可配置 `beat_ms`（默认 1500ms）+ jitter（±200ms）
- 多产线模拟：
  - **PC 端模拟器**：开 N 个 `threading.Thread`（推荐 N=3，三个类别各一条），每个独立 `line_id` + 独立图片队列。
  - **RK3588 真机版本**：单进程，T1 线程循环读取 metal_nut / screw / pill 多个类别的图片集模拟多产线节拍，模型实例只加载一份；**禁止**开多个独立进程各自加载 VLM（每实例 ~3.1 GB，两个即 OOM）。

## 6. 摄像头链路验证方案

仅做**最小可行验证**：拍一张手边物体（任意螺丝 / 螺母 / 瓶盖）走通整条流水线，证明：

1. V4L2 → RGA → EfficientAD-S 链路无 dma_buf fd 泄漏。
2. NPU 推理输出 anomaly_map 形状与 PC 端一致。
3. 上传至后端图片可在前端正常显示。

不要求摄像头分辨率、不要求工业相机、不要求精度对齐 MVTec AD——这一步是**链路验证**，不是**精度验证**。精度验证全部在静态图片集上完成。

## 7. AB 测试方案详细

### 7.1 评估维度

| 维度 | 单位 | PC 阶段意义 | RK3588 阶段意义 |
|---|---|---|---|
| JSON 解析成功率 | % | **核心指标**（精度上界，base vs LoRA） | 量化损失下的实际成功率 |
| TTFT（首 token 延迟） | ms | 不记录（PC GPU 速度与 RK3588 不可比） | **核心指标**，影响产线节拍 |
| Decode tokens/s | tokens/s | 不记录 | **核心指标**，影响 JSON 长度上限 |
| 运行时 RAM | GB | 不记录 | **核心指标**，16GB 板上 VLM 占 ~3.1 GB，余量充裕 |

### 7.2 PC 阶段重点

- 用 HuggingFace transformers 跑 fp16 Qwen3-VL-2B/4B，验证四个变体（`2B_base` / `2B_lora` / `4B_base` / `4B_lora`）的 JSON 解析成功率上界。
- **LoRA 训练数据划分**：MVTec AD `test/` 中的缺陷图（`train/` 只有正常图无法用于标注）按缺陷类型分层抽样，**70% 用于人工标注 JSON + LoRA 训练，30% 严格隔离只用于最终评估，训练集与评估集不得有任何重叠**。划分脚本见 `scripts/split_lora_data.py`（固定 `random.seed(42)` 保证可复现）。LoRA 超参：rank 32，alpha 32，target q/k/v/o，5 epoch。15 类预估 ~1200 train / ~540 eval（实际：train=849, eval=409）。
- 输出：4 变体在全 15 类上的 JSON 解析成功率对比表。
- **PC 阶段实测发现**：方案 B（LoRA）的 `category` 字段出现幻觉（输出 `"industrial"` 而非有效类别）。评估脚本仅校验字段存在性，不校验字段值；实际部署时需在 C++ 侧对 `category` 值做白名单过滤 `{"metal_nut", "screw", "pill"}`，非法值丢弃或归为 `"other"`。

### 7.4 双轨评估设计（v2 新增）

Phase 5 v2 重做采用双轨评估，两条线路目标不同、产出不同：

**Deployment Benchmark**（部署基准）：回答「最终 ship 哪个组合？」
- 4 变体使用各自最优 prompt（base + 工程化长 prompt，LoRA + 极简短 prompt）
- 评估指标：JSON 解析成功率 + RK3588 四维指标
- 产出：`results/ab_eval_report_v2_deployment.json`

**Method Control Benchmark**（方法控制基准）：回答「LoRA 的真实收益？」
- base 与 LoRA 使用完全相同的极简 prompt，消除 prompt 差异干扰
- 评估指标：json_parse_ok / schema_ok / category_exact / defect_type_exact / severity_valid / bbox_iou_at_0_5 / prompt_tokens / output_tokens（8 项）
- 产出：`results/ab_eval_report_v2_method_control.json`

**OPRO Prompt-only Baseline**（可选）：量化 prompt engineering 的单独贡献
- 不修改模型参数，用 LLM 搜索更优 prompt
- 产出：`results/prompt_opro_best.json`
- 不进入 RK3588 部署链路，仅作 PC 阶段方法学对照

详细方法学矩阵见 `docs/experiments/phase5_method_matrix.md`。

### 7.3 RK3588 阶段重点

- 2B 量化后 W8A8 .rkllm 文件大小 ~1.9 GB；运行时总 RAM ~3.1 GB（含 KV cache，`max_context=4096`）。
- 4B 量化后 W8A8 .rkllm 文件大小 ~4.51 GB；运行时总 RAM ~8.7 GB（含 KV cache，`max_context=4096`）；Pipeline 总峰值 ~11.4 GB，裕度 ~3.1 GB。
- TTFT 用 `rkllm_load_prompt_cache()` 复用工程化 Prompt 的长 system prompt 后，预期可降至 1 s 以内（2B）/ 5–6 s（4B）。
- 对比落库于 `defects` 表的 `variant ∈ {"2B_base","2B_lora","4B_base","4B_lora"}` 字段，前端聚合卡片直接读 `/api/stats`。

## 8. 性能预算（RK3588 16GB）

> 以下实测数据来自 Phase 7 Prompt 2E/2F（Orange Pi 5 16GB，2B base W8A8）。

### 8.1 延迟预算

| 阶段 | 目标 | 实测（Phase 7） | 备注 |
|---|---|---|---|
| EfficientAD-S (T2) | 6–12 ms（单核） | **avg 350 ms**（含预处理 + RKNN 推理 + 后处理） | FP16/no-quant raw RKNN，map_mean 模式 |
| FastSAM-s (T3 pre) | 30–60 ms | **avg 250 ms**（preprocess ~95ms + infer ~140ms + post ~7ms） | FP16/no-quant，640×640 |
| Qwen3-VL-2B Vision | — | **avg 2380 ms** | 448×448，4 头并行输出 |
| Qwen3-VL-2B TTFT | 2–3 s | **avg 2174 ms** | W8A8，max_context=4096 |
| Qwen3-VL-2B decode | ~11.5 tokens/s | **avg 9.97 tok/s** | 实测略低于 benchmark |
| Qwen3-VL-2B total | — | **avg 11350 ms** | 含 vision + LLM 全链路 |
| HTTP 上传 (T4) | < 200 ms | **16–47 ms** | 局域网，libcurl multipart |
| 端到端（单帧） | — | **~12 s**（T2+T3+T4） | 节拍以 VLM 为准 |

### 8.2 内存预算（16GB 板）

| 项目 | 目标 | 实测（Phase 7） | 备注 |
|---|---|---|---|
| OS + 系统服务 | ~1.5 GB | — | Ubuntu 22.04 |
| EfficientAD-S RKNN | ~50 MB | ~50 MB | 每次切换类别重新加载 |
| FastSAM RKNN | ~80 MB | ~80 MB | 常驻 |
| Qwen3-VL-2B RKLLM + Vision | ~3.1 GB | **3324 MB** | LLM + Vision + KV cache |
| C++ 进程其他 | ~250 MB | — | 队列、线程栈、libcurl、JPEG buffer |
| **总计（2B）** | **~5.0 GB** | **~3.4 GB RSS**（不含 OS） | 余量 ~12.6 GB |
| **总计（含 4B）** | **~11.4 GB** | — | 余量 ~3.1 GB；**禁止**同时加载 2B 和 4B |

> **备注**：实际硬件为 16GB 版香橙派 5。2B 方案余量 ~11 GB，`max_context` 可放开至 4096，无需配置 zram swap。4B 方案余量 ~3.1 GB，`max_context` 固定 4096，需严格控制其他内存占用。

**16GB 板约束**：

- `max_context` 上限 **4096**。
- **不能在边缘端跑任何 Python 服务**（FastAPI / rkllama / Flask）——这些至少各占 0.5–1 GB。
- 单进程共享同一套模型实例；T1 可多类别循环，内存占用不变；**禁止**多进程各自加载 VLM。

### 8.3 带宽预算

- 单次上报：原图 ~150 KB（700×700 JPEG q85）+ JSON ~2 KB ≈ 152 KB。
- 假设峰值 5 帧/秒异常率：5 × 152 KB ≈ 760 KB/s ≈ 6 Mbps。
- 千兆局域网完全无压力；4G 也够。

## 9. 部署拓扑

### 9.1 开发环境

- 模拟器 + 后端 + 前端在同一台 Mac/Linux 工作机：`localhost:8000`（FastAPI uvicorn）+ `localhost:3000`（Next.js dev）+ 模拟器进程。
- SQLite 文件 `backend/vision.db`，前端代理 WebSocket 走 Next.js dev proxy。

### 9.2 生产 / 演示环境

- 后端：单台云主机或工控机（2C4G 足够），`uvicorn --workers 1`（单 worker，因 ConnectionManager 是进程内单例）。
- 前端：`next build` 后产物（`out/` 目录）丢到 Nginx / Vercel / Cloudflare Pages。（`next.config.ts` 已配 `output: 'export'`，`next build` 自动静态导出，**无需再跑 `next export`**，该命令在 Next.js 14+ 已移除。）
- RK3588：`systemd` 服务自启 C++ 二进制；`config.yaml` 中写后端 URL。
- SQLite WAL 模式；图片存 `/var/lib/vision/static/defects/`，Nginx 直接 alias 暴露，不走 FastAPI。

## 10. 两轨道并行开发的接口契约解耦

`docs/API_CONTRACT.md` 是轨道 A 与轨道 B 的**唯一接口**。具体机制：

1. 轨道 A 起步时先冻结契约 v1（含字段类型、错误码、字段验证规则）。
2. 模拟器作为**契约测试客户端**：用 pytest + httpx 跑端到端测试，覆盖正常路径、字段缺失、超大文件、网络中断重试。
3. 轨道 B 上板后，C++ 客户端只要通过同一组 pytest 契约测试，就视为可替换模拟器。
4. 任何契约变更（哪怕加一个可选字段）必须 bump 版本号，Pydantic schema 与 Skill 中的检查清单同步更新。

这套机制让模型转换、C++ 编码、前后端开发可完全并行，不需要硬件就绪即可推进 80% 工作量。

## 11. 代码生成规范（C++ 端）

### 11.1 命名与文件

- 头文件 `.hpp`、源文件 `.cpp`；`#pragma once`。
- 命名空间 `vlm_industrial::edge::{capture, pipeline, vlm, upload, common}`。
- 类名 `PascalCase`；函数 `snake_case`；常量 `kPascalCase`；宏 `SCREAMING_SNAKE`。
- 成员变量 trailing underscore（`member_`），struct 公有字段不加。

### 11.2 Cache Line 对齐 metrics

```cpp
#pragma once
#include <atomic>
#include <new>

namespace vlm_industrial::edge::common {

#ifdef __cpp_lib_hardware_interference_size
inline constexpr std::size_t kCacheLine = std::hardware_destructive_interference_size;
#else
inline constexpr std::size_t kCacheLine = 64;       // RK3588 Cortex-A76/A55
#endif

struct PipelineMetrics {
  alignas(kCacheLine) std::atomic<uint64_t> capture_count{};
  alignas(kCacheLine) std::atomic<uint64_t> ead_count{};
  alignas(kCacheLine) std::atomic<uint64_t> vlm_count{};
  alignas(kCacheLine) std::atomic<uint64_t> upload_count{};
  alignas(kCacheLine) std::atomic<uint64_t> dropped_count{};
  alignas(kCacheLine) std::atomic<uint64_t> retry_count{};
};

}  // namespace vlm_industrial::edge::common
```

### 11.3 RAII 句柄

```cpp
// common/unique_fd.hpp
class UniqueFd {
  int fd_{-1};
 public:
  UniqueFd() = default;
  explicit UniqueFd(int fd) noexcept : fd_(fd) {}
  UniqueFd(const UniqueFd&) = delete;
  UniqueFd& operator=(const UniqueFd&) = delete;
  UniqueFd(UniqueFd&& o) noexcept : fd_(std::exchange(o.fd_, -1)) {}
  UniqueFd& operator=(UniqueFd&& o) noexcept {
    if (this != &o) { reset(); fd_ = std::exchange(o.fd_, -1); }
    return *this;
  }
  ~UniqueFd() { reset(); }
  [[nodiscard]] int get() const noexcept { return fd_; }
  void reset(int fd = -1) noexcept { if (fd_ >= 0) ::close(fd_); fd_ = fd; }
};

// common/unique_rknn.hpp
struct RknnDeleter {
  void operator()(rknn_context* p) const noexcept {
    if (p && *p) rknn_destroy(*p);
    delete p;
  }
};
using UniqueRknnCtx = std::unique_ptr<rknn_context, RknnDeleter>;
```

### 11.4 BoundedQueue（drop-oldest）

```cpp
template <class T>
class BoundedQueue {
  std::deque<T> q_;
  mutable std::mutex mu_;
  std::condition_variable_any cv_;
  const std::size_t cap_;
  std::size_t dropped_{0};
 public:
  explicit BoundedQueue(std::size_t cap) : cap_(cap) {}

  void push_drop_oldest(T v) {
    {
      std::scoped_lock lk(mu_);
      if (q_.size() >= cap_) { q_.pop_front(); ++dropped_; }
      q_.push_back(std::move(v));
    }
    cv_.notify_one();
  }

  [[nodiscard]] std::optional<T> pop(std::stop_token st) {
    std::unique_lock lk(mu_);
    if (!cv_.wait(lk, st, [&]{ return !q_.empty(); })) return std::nullopt;
    T v = std::move(q_.front()); q_.pop_front();
    return v;
  }
};
```

### 11.5 Worker 模板（jthread + cooperative cancel）

```cpp
class CaptureWorker {
  BoundedQueue<DmaFrame>& out_;
  PipelineMetrics& m_;
  std::jthread th_;
 public:
  CaptureWorker(BoundedQueue<DmaFrame>& q, PipelineMetrics& m)
    : out_(q), m_(m), th_([this](std::stop_token st){ run(st); }) {}
 private:
  void run(std::stop_token st) {
    while (!st.stop_requested()) {
      auto frame = dequeue_v4l2_buffer();      // 内部 select(timeout) + DQBUF
      if (!frame) continue;
      out_.push_drop_oldest(std::move(*frame));
      m_.capture_count.fetch_add(1, std::memory_order_relaxed);
    }
  }
};
```

### 11.6 libcurl multipart

> **重要**：`curl_global_init(CURL_GLOBAL_DEFAULT)` 必须在 `main()` 最开头、**所有线程启动之前**调用一次；`curl_global_cleanup()` 在 `main()` 末尾、**所有线程结束之后**调用一次。`HttpClient` 构造函数中**不调用**这两个全局函数——它们不是线程安全的，放在类构造里会导致多线程竞态。

```cpp
// main.cpp
int main() {
    curl_global_init(CURL_GLOBAL_DEFAULT);   // ← 最开头，单次调用
    // ... 启动四个 jthread ...
    // ... 等待退出信号 ...
    curl_global_cleanup();                    // ← 最末尾，单次调用
}

// upload/http_client.hpp
class HttpClient {
  CURL* curl_{};
 public:
  HttpClient()  { curl_ = curl_easy_init(); }    // 不调用 curl_global_init
  ~HttpClient() { curl_easy_cleanup(curl_); }    // 不调用 curl_global_cleanup

  long post_report(std::string_view url,
                   const std::string& image_path,
                   const std::string& meta_json) {
    curl_easy_reset(curl_);                    // 保留连接池，清 opts
    curl_easy_setopt(curl_, CURLOPT_URL, std::string{url}.c_str());
    curl_easy_setopt(curl_, CURLOPT_CONNECTTIMEOUT_MS, 3000L);
    curl_easy_setopt(curl_, CURLOPT_TIMEOUT_MS, 15000L);
    curl_easy_setopt(curl_, CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_2TLS);
    curl_easy_setopt(curl_, CURLOPT_NOSIGNAL, 1L);  // 多线程必备

    curl_mime* mime = curl_mime_init(curl_);
    auto* p = curl_mime_addpart(mime);
    curl_mime_name(p, "image");
    curl_mime_filedata(p, image_path.c_str());
    curl_mime_type(p, "image/jpeg");

    p = curl_mime_addpart(mime);
    curl_mime_name(p, "meta");
    curl_mime_data(p, meta_json.data(), meta_json.size());
    curl_mime_type(p, "application/json");

    curl_easy_setopt(curl_, CURLOPT_MIMEPOST, mime);

    long status = 0;
    for (int n = 0; n < 5; ++n) {
      CURLcode rc = curl_easy_perform(curl_);
      curl_easy_getinfo(curl_, CURLINFO_RESPONSE_CODE, &status);
      bool retry = (rc == CURLE_OPERATION_TIMEDOUT) ||
                   (rc == CURLE_COULDNT_CONNECT) ||
                   (status == 408 || status == 429 ||
                    (status >= 500 && status < 600));
      if (!retry) break;
      auto delay_ms = (1 << n) * 500 + (std::rand() % 250);
      std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
    }
    curl_mime_free(mime);
    return status;
  }
};
// 注意：CURL handle 不是线程安全——T4 Upload 单线程独占一个 HttpClient 实例。
```

## 12. Phase 8 架构认知修正

Phase 8 系统实验（threshold calibration、VLM A/B 评估、beat 扫频）揭示了多项对 Phase 7 架构假设的修正。

### 12.1 T2 gate 定位修正：负载脱落门控

Phase 8A 对 15 类 MVTec test split（1725 张图，FP16/no-quant raw RKNN）测试了 5 种 score mode：

| Score Mode | Mean AUROC | 排名 |
|---|---|---|
| raw_score | 0.5320 | 1（最优）|
| map_max | 0.5320 | 2 |
| map_top01 | 0.5223 | 3 |
| map_top1 | 0.5061 | 4 |
| map_mean | 0.4561 | 5（最差）|

14/15 类 best AUROC < 0.80（例外：tile 使用 map_top1 达到 0.8488）。所有类别均存在 good/defect 分布重叠。

**架构结论**：在当前 EfficientAD raw output 尺度下，T2 gate 是**负载脱落门控（load shedding gate）**，不是精确检测分类器。设置 good_p95 阈值意味着约 5% good 帧进入 T3（false positive），而大量 defect 帧也被 drop（因 AUROC 低，排序能力弱）。这是 FP16 raw RKNN 下 EfficientAD 的根本限制，不是工程实现问题。

**改善方向**：实现 C++ post-processor（Clip+Normalize+Sigmoid），恢复 [0,1] 校准分数尺度，但需绕过 RKNN 的 Greater 节点类型限制。

### 12.2 score mode 选择

当前部署使用 `raw_score`（ReduceMax 输出）。选择依据：
- `raw_score` 和 `map_max` 数学等价（均取 anomaly map 全局最大像素值）
- `raw_score` mean AUROC = 0.5320，优于 `map_mean`（0.4561），delta = +0.0759
- `map_mean` 被大面积正常背景稀释，不适合局部缺陷检测
- 对 grid 类（局部细线缺陷），`raw_score` AUROC 改善最大（+0.3241）

### 12.3 Qwen3-VL LoRA 部署结论

**PC bf16 LoRA 有效**：defect_type_exact 51.8%，category_exact 95.1%，bbox_iou>=0.5 47.7%（409 eval 样本）。

**RKLLM/W8A8 板端 LoRA 坍塌**：defect_type_exact 0%，category_exact ~93%。LoRA adapter 已正确 merge 后再做 RKLLM 转换（SHA256 跨平台一致 + 合并后 key 检验通过）。坍塌由 W8A8 量化破坏 rank-32 delta 权重导致。

**当前部署选择**：RK3588 使用 2B base W8A8。LoRA 保留 PC 端 bf16 推理价值。

### 12.4 4B vision encoder spatial patch merge

4B vision encoder 输出维度：
- output[0]：[784, 1024]（spatial merge 前，4× token 数）
- output[1-4]：[196, 2560]

RKLLM 运行时要求 n_image_tokens = patch_h × patch_w = 14 × 14 = 196，embed_dim = 1024 × merge_factor² = 1024 × 4 = 4096。

当前实现（C++ qwen3vl_runner.cpp）：
- 检测 output[0] 的 4× 因子，自动修正 n_image_tokens 和 embed_dim
- 使用 contiguous reshape [784,1024]→[196,4096]
- 已知限制：正确做法需要空间排列 `[28,28,1024] → permute[14,2,14,2,1024] → [196,4096]`
- 当前 contiguous reshape 对 6/7 类别有效；carpet 触发静默 VLM 失败
- 2B vision encoder 无 spatial merge，代码路径独立，不受影响

### 12.5 beat_ms 设计约束（Phase 8C 实测）

```
安全：  beat_ms > VLM_p99_latency
推荐：  beat_ms >= VLM_avg_ms / 0.85（预留 15% buffer）
```

实测数据（pass_all 模式，2B base W8A8）：

| 条件 | 数值 |
|---|---|
| 最小稳定 beat | 10000ms |
| 推荐安全 beat | 13000ms（VLM_avg/beat = 0.83）|
| 临界比值 | VLM_avg/beat ≈ 1.0 |
| 4B base 推荐 | >= 35000ms（实测最大 VLM = 28.9s）|

生产 threshold 模式：T2 gate 过滤约 95% good 帧。等效 T3 入队间隔 = beat_ms / gate_pass_rate。5000ms beat 在 threshold 模式下约等效 100s 入队间隔，充分满足 VLM 10.7s 的处理需求。

**反压效应**：beat=5000ms 下 VLM avg 延迟增加 21.9%，原因是 Q2 满载时 NPU 资源争用。系统在 Q2 饱和状态下加速退化，而非线性退化。
