#pragma once

#include <cstdint>
#include <string>

namespace vlm_industrial::edge::common {

// Chrome Trace Event format — compatible with frontend ProfilePage.
// Serialized to JSON array and reported via vlm_metrics.trace_events.
struct TraceEvent {
  std::string name;       // e.g. "ead_infer", "fastsam_infer", "vlm_decode"
  std::string cat;        // category: "pipeline", "upload"
  char      ph{'X'};      // 'X' = complete event
  uint64_t  ts{0};        // timestamp (microseconds, monotonic)
  uint64_t  dur{0};       // duration (microseconds)
  uint32_t  pid{0};       // process id (fixed: 0 for edge)
  uint32_t  tid{0};       // thread id (T1=1, T2=2, T3=3, T4=4)
};

}  // namespace vlm_industrial::edge::common
