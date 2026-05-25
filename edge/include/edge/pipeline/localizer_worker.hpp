#pragma once

// T3 Worker — Phase 10: ORT CPU localizer (subprocess-based).
// Replaces FastSamWorker when localizer_backend="ort".
// Spawns ort_localizer.py, sends image paths, reads JSON results.

#include <stop_token>
#include <string>
#include <vector>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/ead_result.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"

namespace vlm_industrial::edge {

class LocalizerWorker {
 public:
  LocalizerWorker(const common::Config& cfg,
                  common::BoundedQueue<EadResult>& in,
                  common::BoundedQueue<VlmReport>& out,
                  common::PipelineMetrics& m);

  void operator()(std::stop_token st);

 private:
  // Spawn the Python subprocess. Returns true on success (ready line received).
  bool spawn_subprocess();

  // Send an image path to the subprocess and read the JSON result.
  // Returns empty string on timeout/error.
  std::string infer_one(const std::string& image_path);

  // Kill the subprocess if running.
  void kill_subprocess();

  // Build a fallback VlmReport when inference fails.
  VlmReport make_fallback_report(const EadResult& ead,
                                 const char* reason) const;

  // Parse JSON result from Python into a VlmReport.
  VlmReport parse_result(const EadResult& ead,
                         const std::string& json_line) const;

  const common::Config& cfg_;
  common::BoundedQueue<EadResult>& in_;
  common::BoundedQueue<VlmReport>& out_;
  common::PipelineMetrics& m_;

  // Subprocess state.
  int proc_stdin_fd_{-1};
  int proc_stdout_fd_{-1};
  pid_t proc_pid_{-1};
};

}  // namespace vlm_industrial::edge
