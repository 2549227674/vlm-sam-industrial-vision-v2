#pragma once

#include <stop_token>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/http_client.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"

namespace vlm_industrial::edge {

// T4 UploadWorker: consumes VlmReport from Q3, uploads via HttpClient.
class UploadWorker {
 public:
  UploadWorker(const common::Config& cfg,
               common::BoundedQueue<VlmReport>& in,
               common::PipelineMetrics& m);

  void operator()(std::stop_token st);

 private:
  // Serialize VlmReport to the meta JSON expected by POST /api/edge/report.
  static std::string build_meta_json(const VlmReport& r);

  const common::Config& cfg_;
  common::BoundedQueue<VlmReport>& in_;
  common::PipelineMetrics& m_;
  common::HttpClient http_;
};

}  // namespace vlm_industrial::edge
