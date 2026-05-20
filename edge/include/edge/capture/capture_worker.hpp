#pragma once

#include <stop_token>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"

namespace vlm_industrial::edge {

// T1 CaptureWorker: image_loop mode.
// Scans MVTec test/ directories for each configured category,
// produces CaptureFrame at the configured beat/jitter cadence.
class CaptureWorker {
 public:
  CaptureWorker(const common::Config& cfg,
                common::BoundedQueue<CaptureFrame>& out,
                common::PipelineMetrics& m);

  // Thread entry point; call from std::jthread constructor.
  void operator()(std::stop_token st);

 private:
  // Scan one category's test/ directory for image files.
  void scan_category(const std::string& category);

  const common::Config& cfg_;
  common::BoundedQueue<CaptureFrame>& out_;
  common::PipelineMetrics& m_;

  // Pre-scanned image paths grouped by category.
  std::vector<std::pair<std::string, std::vector<std::string>>> catalog_;
  std::size_t cat_idx_{0};
  std::size_t img_idx_{0};
  uint64_t    frame_counter_{0};
};

}  // namespace vlm_industrial::edge
