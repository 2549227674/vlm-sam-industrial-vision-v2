#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace vlm_industrial::edge {

struct EadResult {
  std::string image_path;
  std::string category;
  std::string device_id;
  std::string line_id;
  uint64_t    frame_id{0};
  int64_t     frame_timestamp_us{0};

  float anomaly_score{0.0f};
  float threshold{0.0f};
  bool  is_anomaly{false};
  float inference_ms{0.0f};
};

}  // namespace vlm_industrial::edge
