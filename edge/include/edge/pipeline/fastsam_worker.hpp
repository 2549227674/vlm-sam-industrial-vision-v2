#pragma once

// T3 Worker — Prompt 2C: FastSAM real bbox extraction + mock VLM JSON.
// Qwen3-VL is NOT called in this phase; VLM fields remain mocked.
// TODO(Prompt-2D): Replace mock VLM section with real RKLLM inference.

#include <stop_token>
#include <vector>

#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/ead_result.hpp"
#include "edge/common/image_utils.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"
#include "edge/common/unique_rknn.hpp"

namespace vlm_industrial::edge {

class FastSamWorker {
 public:
  FastSamWorker(const common::Config& cfg,
                common::BoundedQueue<EadResult>& in,
                common::BoundedQueue<VlmReport>& out,
                common::PipelineMetrics& m);

  void operator()(std::stop_token st);

 private:
  // Load fastsam_s.rknn once; query + print input/output attrs.
  bool load_model();

  // Decode + resize image to 640x640 (simple resize; MVTec images are square
  // so letterbox == simple resize. TODO(Prompt-2C-Fix): add letterbox for
  // non-square inputs, and pass scale/pad to decode_bboxes for coord recovery).
  // Returns RGB uint8 buffer or nullptr on failure.
  std::unique_ptr<uint8_t[]> preprocess(const std::string& image_path,
                                        int& out_orig_w, int& out_orig_h);

  // Decode detection output (output0, shape [1,37,8400]):
  //   ch 0-3 : cx,cy,w,h  in 640-pixel space
  //   ch 4   : class confidence (already in [0,1] from Ultralytics export)
  //   ch 5-36: mask coefficients (TODO: full mask decode in Prompt 2C-Fix)
  //
  // CRITICAL: zp_q / scale_q come from output0's own rknn_tensor_attr.
  // They MUST NOT be shared with output1's parameters.
  //
  // Returns normalized [0,1] bboxes after conf filter + greedy NMS.
  std::vector<VlmReport::BBox> decode_bboxes(
      const void* buf,
      uint32_t n_elems,
      rknn_tensor_type out_type,
      int32_t zp_q,
      float scale_q);

  // Build a fallback VlmReport when inference or decode fails.
  VlmReport make_fallback_report(const EadResult& ead,
                                 const char* reason) const;

  const common::Config& cfg_;
  common::BoundedQueue<EadResult>& in_;
  common::BoundedQueue<VlmReport>& out_;
  common::PipelineMetrics& m_;

  common::UniqueRknnCtx ctx_;
  bool model_loaded_{false};
  uint32_t n_input_{0};
  uint32_t n_output_{0};

  // Index of the detection output (shape [1,37,8400]); resolved in load_model.
  int det_out_idx_{-1};
};

}  // namespace vlm_industrial::edge
