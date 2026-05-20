#pragma once

#include <stop_token>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"

namespace vlm_industrial::edge {

// Mock T2+T3: consumes CaptureFrame from Q1, produces mock VlmReport to Q3.
// Does NOT call EfficientAD, FastSAM, or Qwen3-VL.
// Replaced by real PipelineWorker + VlmWorker in Prompt 2B/2C.
class MockPipelineWorker {
 public:
  MockPipelineWorker(const common::Config& cfg,
                     common::BoundedQueue<CaptureFrame>& in,
                     common::BoundedQueue<VlmReport>& out,
                     common::PipelineMetrics& m);

  void operator()(std::stop_token st);

 private:
  const common::Config& cfg_;
  common::BoundedQueue<CaptureFrame>& in_;
  common::BoundedQueue<VlmReport>& out_;
  common::PipelineMetrics& m_;
};

}  // namespace vlm_industrial::edge
