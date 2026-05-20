#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace vlm_industrial::edge {

// Frame from T1 Capture (V4L2 DQBUF or image-loop).
// fd is a dma_buf file descriptor; ownership transferred via UniqueFd.
struct CaptureFrame {
  int      fd{-1};
  uint32_t width{0};
  uint32_t height{0};
  uint32_t format{0};  // V4L2 pixfmt / RK_FORMAT_*
};

// Output from T2 Pipeline (EfficientAD-S).
struct EadResult {
  CaptureFrame frame;          // pass-through for downstream
  float        anomaly_score{0.0f};
  bool         is_anomaly{false};
  std::string  category;       // detected category (image-loop sets this)
};

// Output from T3 VLM Worker (FastSAM + Qwen3-VL).
// Ready for T4 Upload.
struct VlmReport {
  CaptureFrame frame;
  std::string  category;
  std::string  defect_type;
  std::string  severity;
  float        confidence{0.0f};
  std::vector<float> bbox;     // [x1, y1, x2, y2] normalized [0,1]
  std::string  vlm_raw_json;   // raw VLM output
  std::string  variant;        // "2B_base", "2B_lora", "4B_base", "4B_lora"
};

}  // namespace vlm_industrial::edge
