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

  // Multi-metric scores from raw anomaly map.
  float raw_score{0.0f};    // ReduceMax scalar output
  float map_max{0.0f};      // max of raw_anomaly_map
  float map_mean{0.0f};     // mean of raw_anomaly_map
  float map_top1{0.0f};     // mean of top-1% pixels
  float map_top01{0.0f};    // mean of top-0.1% pixels

  // Gate decision.
  float final_score{0.0f};  // selected by score_mode
  float threshold{0.0f};
  bool  is_anomaly{false};

  // Mode strings for logging (kept as char for zero-alloc).
  // 0=raw_score, 1=map_max, 2=map_mean, 3=map_top1, 4=map_top01
  int8_t score_mode{2};     // default map_mean
  // 0=threshold, 1=pass_all
  int8_t gate_mode{0};      // default threshold

  float inference_ms{0.0f};
};

}  // namespace vlm_industrial::edge
