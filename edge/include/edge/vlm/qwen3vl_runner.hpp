#pragma once

// Qwen3-VL RKLLM runner — Prompt 2D.
// Runs vision encoder (RKNN) + LLM (RKLLM) to produce structured JSON from
// an image + EfficientAD score + FastSAM bboxes.
//
// 2B base, 2B LoRA, and 4B base are supported. 4B LoRA is not implemented.

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "edge/common/config.hpp"
#include "edge/common/unique_rknn.hpp"

namespace vlm_industrial::edge {

// 2x2 spatial merge for Qwen3-VL-4B vision encoder output.
// Input: [28*28*1024] flat buffer (pre-merge spatial tokens).
// Output: [14*14*4096] flat buffer (post-merge tokens).
// Correctly groups 2x2 spatial neighbours before flattening the channel dim.
template <typename T>
void merge_spatial_2x2(const T* input, T* output);

}  // namespace vlm_industrial::edge (forward decl)

// Forward-declare RKLLM types to avoid pulling rkllm.h into every TU.
typedef void* LLMHandle;

namespace vlm_industrial::edge {

struct VlmResult {
  std::string raw_text;
  float       ttft_ms{0.0f};
  float       decode_tps{0.0f};
  int32_t     prefill_tokens{0};
  int32_t     output_tokens{0};
  float       rss_mb{0.0f};
  bool        json_parse_ok{false};
  bool        watchdog_abort{false};
  std::string error_message;
  float       vision_ms{0.0f};
  float       llm_ms{0.0f};
  std::vector<std::array<float,4>> vlm_bboxes;  // Parsed VLM bboxes [0,1].
};

class Qwen3VLRunner {
 public:
  explicit Qwen3VLRunner(const common::Config& cfg);
  ~Qwen3VLRunner();

  // Non-copyable, move-only (RKLLM handle ownership transferred).
  Qwen3VLRunner(const Qwen3VLRunner&) = delete;
  Qwen3VLRunner& operator=(const Qwen3VLRunner&) = delete;
  Qwen3VLRunner(Qwen3VLRunner&& o) noexcept;
  Qwen3VLRunner& operator=(Qwen3VLRunner&& o) noexcept;

  // Initialize vision encoder (RKNN) + LLM (RKLLM).
  // Returns true on success.
  bool init();

  // Run inference on a single image.
  // category, final_score, bboxes are used to construct the prompt.
  // Each bbox is {x, y, w, h} normalized [0,1].
  VlmResult infer(const std::string& image_path,
                  const std::string& category,
                  float final_score,
                  const std::vector<std::array<float,4>>& bboxes);

  // Check if initialized.
  bool ready() const { return initialized_; }

  // JSON extraction from VLM raw text.
  // Strips thinking tags, markdown fences, extracts first JSON object.
  // Validates schema fields and returns true if valid JSON was extracted.
  static bool extract_json(const std::string& raw_text,
                           const std::string& expected_category,
                           std::string& out_defect_type,
                           std::string& out_severity,
                           float& out_confidence,
                           std::string& out_description,
                           int orig_w = 0,
                           int orig_h = 0,
                           bool* severity_corrected = nullptr);

  // Build a rule-based fallback VLM result when JSON extraction fails.
  static std::string build_fallback_json(const std::string& category,
                                         float final_score,
                                         const std::string& reason);

  // Parse VLM bbox array from JSON text.
  // Handles [[x,y,w,h]] compact format, single and multi-bbox.
  // Detects pixel vs normalized coordinates and normalizes to [0,1].
  static std::vector<std::array<float,4>> parse_vlm_bboxes(
      const std::string& json_str,
      int orig_w, int orig_h);

 private:
  // Preprocess image: decode + expand-to-square + resize to 448x448.
  // Returns RGB uint8 buffer or nullptr on failure.
  std::unique_ptr<uint8_t[]> preprocess_image(const std::string& path,
                                               int& out_w, int& out_h);

  // Run vision encoder, return concatenated image embeddings.
  // Output size = n_image_tokens * n_outputs * embed_dim floats.
  std::vector<float> run_vision_encoder(const uint8_t* rgb_data,
                                        int img_w, int img_h);

  // Construct prompt with image placeholder + context.
  std::string build_prompt(const std::string& category,
                           float final_score,
                           const std::vector<std::array<float,4>>& bboxes,
                           const std::string& image_basename);

  const common::Config& cfg_;

  // Vision encoder (RKNN)
  common::UniqueRknnCtx vision_ctx_;
  uint32_t vision_n_input_{0};
  uint32_t vision_n_output_{0};
  int vision_model_width_{0};
  int vision_model_height_{0};
  int vision_image_token_{0};
  int vision_embed_dim_{0};
  bool needs_spatial_merge_{false};
  int merge_factor_{1};

  // LLM (RKLLM)
  LLMHandle llm_handle_{nullptr};

  bool initialized_{false};
};

// ── 2x2 spatial merge implementation ─────────────────────────────────────────
// Qwen3-VL-4B vision encoder outputs [28,28,1024] pre-merge spatial tokens.
// RKLLM expects [196,4096] post-merge tokens where each output token is the
// concatenation of a 2x2 spatial block (merge_size=2).
// This implementation correctly groups spatial neighbours before flattening.

template <typename T>
void merge_spatial_2x2(const T* input, T* output) {
  constexpr int H = 28;
  constexpr int W = 28;
  constexpr int C = 1024;
  constexpr int MERGE = 2;
  constexpr int OH = H / MERGE;
  constexpr int OW = W / MERGE;
  constexpr int OC = C * MERGE * MERGE;

  for (int by = 0; by < OH; ++by) {
    for (int bx = 0; bx < OW; ++bx) {
      const int out_token = by * OW + bx;
      T* out_ptr = output + out_token * OC;

      int local = 0;
      for (int dy = 0; dy < MERGE; ++dy) {
        for (int dx = 0; dx < MERGE; ++dx) {
          const int iy = by * MERGE + dy;
          const int ix = bx * MERGE + dx;
          const int in_token = iy * W + ix;
          const T* in_ptr = input + in_token * C;

          std::copy(in_ptr, in_ptr + C, out_ptr + local * C);
          ++local;
        }
      }
    }
  }
}

}  // namespace vlm_industrial::edge
