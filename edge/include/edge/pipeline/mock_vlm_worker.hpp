#pragma once

#include <stop_token>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/ead_result.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"

namespace vlm_industrial::edge {

// Mock T3: consumes EadResult from Q2, produces mock VlmReport to Q3.
// Does NOT call FastSAM or Qwen3-VL. Uses real anomaly_score from T2.
class MockVlmWorker {
 public:
  MockVlmWorker(const common::Config& cfg,
                common::BoundedQueue<EadResult>& in,
                common::BoundedQueue<VlmReport>& out,
                common::PipelineMetrics& m);

  void operator()(std::stop_token st);

 private:
  const common::Config& cfg_;
  common::BoundedQueue<EadResult>& in_;
  common::BoundedQueue<VlmReport>& out_;
  common::PipelineMetrics& m_;
};

}  // namespace vlm_industrial::edge
