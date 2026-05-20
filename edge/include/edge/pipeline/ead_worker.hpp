#pragma once

#include <stop_token>
#include <string>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/ead_result.hpp"
#include "edge/common/image_utils.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"
#include "edge/common/unique_rknn.hpp"

namespace vlm_industrial::edge {

// T2 EfficientAD Worker: loads per-category RKNN model, runs inference,
// outputs EadResult to Q2 if anomaly_score > threshold.
class EadWorker {
 public:
  EadWorker(const common::Config& cfg,
            common::BoundedQueue<CaptureFrame>& in,
            common::BoundedQueue<EadResult>& out,
            common::PipelineMetrics& m);

  void operator()(std::stop_token st);

 private:
  bool load_model(const std::string& category);
  void release_model();

  // Decode + resize image to model input size; returns RGB uint8 buffer.
  std::unique_ptr<uint8_t[]> preprocess(const std::string& image_path,
                                        int& out_w, int& out_h);

  const common::Config& cfg_;
  common::BoundedQueue<CaptureFrame>& in_;
  common::BoundedQueue<EadResult>& out_;
  common::PipelineMetrics& m_;

  common::UniqueRknnCtx ctx_;
  std::string cached_category_;

  uint32_t n_input_{0};
  uint32_t n_output_{0};
};

}  // namespace vlm_industrial::edge
