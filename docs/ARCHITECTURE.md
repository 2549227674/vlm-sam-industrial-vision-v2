# 系统架构

本文档定义 vlm-sam-industrial-vision-v2 的端云分离架构、三段式异步推理流水线、数据流时序、AB 测试方案与性能预算。所有数字基于 2026 年 5 月公开资料；标注「TBD-上板实测」的为推算值，等真机部署后回填。

## 1. 全局拓扑

```
┌──────────────────────────┐         ┌────────────────────────┐         ┌────────────────────────┐
│   RK3588 8GB Edge        │         │  Backend (FastAPI)     │         │  Frontend (Next.js 15) │
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

### 2.1 边缘端（RK3588 8GB）

- 取帧（V4L2 真机模式 / 图片集循环测试模式），经 RGA resize/colorspace 转换，输入 EfficientAD-S 计算异常分数。
- 异常分数高于阈值时，触发 FastSAM 分割 + Qwen3-VL-2B 生成 JSON 描述。
- 每个上报包含原图、缺陷裁剪图、JSON 元数据，HTTP multipart 上传，失败指数退避重试。
- **不**存储历史数据、**不**做 UI、**不**做 WebSocket 服务、**不**跑 Python Web 框架。

### 2.2 后端（FastAPI）

- 接收 multipart 报文，落盘图片到 `static/defects/{YYYYMMDD}/{uuid}.jpg`，元数据写入 SQLite（`defects` 表）。
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

### 3.2 三段模型定位

| Stage | 模型 | 输入 | 输出 | RK3588 INT8 延迟 | 备注 |
|---|---|---|---|---|---|
| 1 | EfficientAD-S | 256×256 RGB | anomaly_map + score | 6–12 ms（单核）/ 3–5 ms（三核）TBD-上板实测 | Anomalib 将 Teacher/Student/AE 三子网络封装为**单一 ONNX**，转**单个 RKNN**文件 |
| 2 | FastSAM-s | **640×640** | mask + bbox | ~30–60 ms | 仅 Stage 1 触发后跑；分辨率固定 640（MVTec 900×900 降采样对厘米级缺陷无影响；如需检测微米级特征可调至 1024，延迟约增 2–3 倍） |
| 3 | Qwen3-VL-2B | 448×448 + prompt | JSON 文本 | TTFT 2–3 s（短 prompt）/ 5–10 s（长 prompt），decode 11.5 tokens/s，RAM 3.1 GB | 异步 worker，drop-oldest |

**EfficientAD-S 选型理由**：替代 PaDiM 解决位置敏感性问题（PaDiM 对像素位置敏感，工业件轻微平移即误报）；PDN 全卷积、平移等变；MVTec AD image-AUROC 平均 98.8%（论文 5 次平均），三类基准 metal_nut 0.979 / pill 0.987 / screw 0.960（Anomalib benchmark）。

**Qwen3-VL-2B 备选降级顺序**（部署失败时按此顺序，**只改 `edge/config.yaml`，不改 C++ 代码**）：

1. Qwen2.5-VL-3B（~7 tps，社区资料最丰富）
2. InternVL3.5-2B（~11 tps，rknn-llm v1.2.3 官方支持）
3. InternVL3-1B（~30 tps，质量略弱但延迟极低）
4. Qwen2-VL-2B（~12 tps，最老牌稳定）

### 3.3 关键算子与零拷贝

- T1 拿到 V4L2 dma_buf fd → 包装 `UniqueFd` → 入 Q1。
- T2 用 `importbuffer_fd` 导入 RGA → `imresize` → 输出张量直接 `rknn_create_mem_from_fd` 喂入 NPU，避免一次 memcpy。
- T3 异步：异常分数高才触发；FastSAM 与 Qwen3-VL 串行（共享 NPU 资源）。
- T4 libcurl 复用 easy handle，只 `curl_easy_reset` 不 `cleanup`，TLS 连接池命中率接近 100%。

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
| 运行时 RAM | GB | 不记录 | **核心指标**，8GB 板上分给 VLM ≤ 3.5 GB |

### 7.2 PC 阶段重点

- 用 HuggingFace transformers 跑 fp16 Qwen3-VL-2B，验证两个变体的 JSON 解析成功率上界。
- **LoRA 训练数据划分**：MVTec AD `test/` 中的缺陷图（`train/` 只有正常图无法用于标注）按缺陷类型分层抽样，**70% 用于人工标注 JSON + LoRA 训练，30% 严格隔离只用于最终评估，训练集与评估集不得有任何重叠**。划分脚本见 `scripts/split_lora_data.py`（固定 `random.seed(42)` 保证可复现）。LoRA 超参：rank 16，5 epoch。
- 输出：方案 A/B 在 metal_nut / screw / pill 上的 JSON 解析成功率对比表。

### 7.3 RK3588 阶段重点

- 量化后 W8A8 .rkllm 文件大小 ~1.9 GB；运行时总 RAM ~3.1 GB（含 KV cache，`max_context=3072`）。
- TTFT 用 `rkllm_load_prompt_cache()` 复用方案 A 的长 system prompt 后，预期可降至 1 s 以内（**TBD-上板实测**）。
- 对比落库于 `defects` 表的 `variant ∈ {"A","B"}` 字段，前端聚合卡片直接读 `/api/stats`。

## 8. 性能预算（RK3588 8GB）

### 8.1 延迟预算

| 阶段 | 目标 | 实测 / 估算来源 |
|---|---|---|
| V4L2 取帧 | < 5 ms | dma_buf 零拷贝 |
| RGA resize | < 3 ms | RGA3 双核 |
| EfficientAD-S | 6–12 ms（单核）/ 3–5 ms（三核） | TBD，类比 ResNet18 INT8 ≈ 4 ms |
| FastSAM-s | 30–60 ms | 类比 YOLOv8 INT8（640 输入） |
| Qwen3-VL-2B TTFT | 2–3 s（cache 命中后 ~1 s） | Qengineering benchmark + cache preload 推算 |
| Qwen3-VL decode | ~11.5 tokens/s | Qengineering 实测 |
| HTTP 上传 | < 200 ms（局域网） | libcurl HTTP/2 |
| **端到端（异常帧）** | **2.5–4 s（首帧）** | 节拍以 EfficientAD 为准（~10 ms），VLM 异步 |

### 8.2 内存预算（8GB 板，关键约束）

| 项目 | 占用 | 备注 |
|---|---|---|
| OS + 系统服务 | ~1.5 GB | Ubuntu 22.04 minimal |
| EfficientAD-S RKNN | ~50 MB | 模型 + 工作内存 |
| FastSAM RKNN | ~80 MB | |
| Qwen3-VL-2B RKLLM + Vision | ~3.1 GB | LLM 1.9 GB + Vision 0.4 GB + KV (max_context=3072) |
| C++ 进程其他 | ~250 MB | 队列、线程栈、libcurl、JPEG buffer |
| 缓冲帧（Q1/Q2/Q3） | ~50 MB | 4+2+4 帧 × ~5 MB |
| **总计** | **~5.0 GB / 8 GB** | 余量 ~3 GB，紧张但可用 |

**8GB 板的硬约束**：

- `max_context` **上限 3072**（不是 4096），KV cache 加大会触顶。
- **不能在边缘端跑任何 Python 服务**（FastAPI / rkllama / Flask）——这些至少各占 0.5–1 GB。
- 单进程共享同一套模型实例；T1 可多类别循环，内存占用不变；**禁止**多进程各自加载 VLM。
- 编译时建议配 4 GB zram swap 防 OOM；运行时基本不用到 swap。

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
