#pragma once

#include <chrono>
#include <cstdint>
#include <string>
#include <vector>

namespace vlm_industrial::edge {

// Frame produced by T1 Capture (V4L2 or image-loop).
struct CaptureFrame {
  // -- image_loop fields --
  std::string image_path;        // absolute path to the image file
  std::string category;          // MVTec class (e.g. "metal_nut")
  std::string device_id;         // from config
  std::string line_id;           // from config
  int64_t     timestamp_us{0};   // monotonic microseconds since epoch
  uint64_t    frame_id{0};       // monotonic counter per worker

  // -- V4L2/dma_buf fields (TODO: populate in real capture mode) --
  int      fd{-1};
  uint32_t width{0};
  uint32_t height{0};
  uint32_t format{0};            // V4L2 pixfmt / RK_FORMAT_*
};

// Output from T3 VLM Worker (or mock), ready for T4 Upload.
// Fields map to DefectCreate in docs/API_CONTRACT.md.
struct VlmReport {
  std::string image_path;        // image file to upload
  std::string device_id;
  std::string line_id;
  std::string category;          // MVTec 15-class
  std::string defect_type;       // e.g. "scratch", "bent"
  std::string severity;          // "low" | "medium" | "high"
  float       confidence{0.0f};  // [0, 1]
  float       anomaly_score{0.0f};

  // Bounding boxes: each bbox is {x, y, w, h} normalized [0,1].
  struct BBox { float x, y, w, h; };
  std::vector<BBox> bboxes;

  std::string variant;           // "2B_base", "4B_lora", etc.

  // Per-stage timing (milliseconds).
  struct PipelineMs {
    float efficientad{0.0f};
    float fastsam{0.0f};
    float qwen3vl{0.0f};
  } pipeline_ms;

  // VLM performance metrics (see API_CONTRACT.md VlmMetrics).
  struct VlmMetrics {
    float   ttft_ms{0.0f};
    float   decode_tps{0.0f};
    int32_t prompt_tokens{0};
    int32_t output_tokens{0};
    float   rss_mb{0.0f};
    bool    json_parse_ok{true};
  } vlm_metrics;

  // Chrome Trace events for frontend ProfilePage.
  struct TraceEvent {
    std::string name;
    float       ts{0.0f};   // microseconds from frame start
    float       dur{0.0f};  // microseconds
    std::string tid;        // e.g. "T1.capture"
    char        ph{'X'};    // Chrome Trace complete event
    std::string cat;        // e.g. "capture", "pipeline"
  };
  std::vector<TraceEvent> trace_events;

  int64_t frame_timestamp_us{0};  // original CaptureFrame timestamp
};

}  // namespace vlm_industrial::edge
