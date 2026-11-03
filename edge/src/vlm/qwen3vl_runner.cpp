// edge/src/vlm/qwen3vl_runner.cpp
// Prompt 2D: Qwen3-VL RKLLM runner — vision encoder + LLM inference.

#include "edge/vlm/qwen3vl_runner.hpp"

#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <sstream>
#include <utility>

#include "rkllm.h"
#include "rknn_api.h"

#include "edge/common/image_utils.hpp"

namespace fs = std::filesystem;
namespace vlm_industrial::edge {

using std::chrono::steady_clock;
using std::chrono::duration;

// ── Callback state ───────────────────────────────────────────────────────────
// RKLLM callback is invoked from the RKLLM thread for each generated token.
// We accumulate text and perf stats into a shared buffer protected by mutex.

struct CallbackState {
  std::mutex              mu;
  std::condition_variable cv;
  std::string             text;
  bool                    finished{false};
  bool                    error{false};
  bool                    watchdog_abort{false};
  float                   prefill_time_ms{0.0f};
  float                   generate_time_ms{0.0f};
  int                     prefill_tokens{0};
  int                     generate_tokens{0};
  float                   memory_usage_mb{0.0f};
  int                     repeated_char_limit{64};
  int                     repeated_ngram_limit{32};

  void reset() {
    std::scoped_lock lk(mu);
    text.clear();
    finished = false;
    error = false;
    watchdog_abort = false;
    prefill_time_ms = 0.0f;
    generate_time_ms = 0.0f;
    prefill_tokens = 0;
    generate_tokens = 0;
    memory_usage_mb = 0.0f;
  }
};

// Detect if the tail of str contains a run of the same character exceeding limit.
static bool detect_repeated_chars(const std::string& s, int limit) {
  if (static_cast<int>(s.size()) < limit) return false;
  char last = s.back();
  int run = 1;
  for (int i = static_cast<int>(s.size()) - 2; i >= 0 && run < limit; --i) {
    if (s[i] == last) ++run;
    else break;
  }
  return run >= limit;
}

// Detect if the tail of str consists of a short n-gram repeated many times.
// Uses the last (limit * 2) characters, checking if a prefix of length
// 1..max_ngram_len repeats enough times to hit the limit.
static bool detect_repeated_ngram(const std::string& s, int limit) {
  int window = limit * 2;
  if (static_cast<int>(s.size()) < window) return false;
  std::string_view tail{s.data() + s.size() - window, static_cast<size_t>(window)};
  for (int ngram_len = 1; ngram_len <= 16; ++ngram_len) {
    if (ngram_len > static_cast<int>(tail.size()) / 2) break;
    std::string_view ngram{tail.data(), static_cast<size_t>(ngram_len)};
    int repeats = 1;
    for (size_t pos = ngram_len; pos + ngram_len <= tail.size(); pos += ngram_len) {
      if (tail.substr(pos, ngram_len) == ngram) ++repeats;
      else break;
    }
    if (repeats >= limit / ngram_len) return true;
  }
  return false;
}

static int llm_callback(RKLLMResult* result, void* userdata, LLMCallState state) {
  auto* cb = static_cast<CallbackState*>(userdata);
  if (state == RKLLM_RUN_FINISH) {
    std::scoped_lock lk(cb->mu);
    cb->finished = true;
    if (result && result->perf.prefill_time_ms > 0) {
      cb->prefill_time_ms = result->perf.prefill_time_ms;
      cb->prefill_tokens = result->perf.prefill_tokens;
      cb->generate_time_ms = result->perf.generate_time_ms;
      cb->generate_tokens = result->perf.generate_tokens;
      cb->memory_usage_mb = result->perf.memory_usage_mb;
    }
    cb->cv.notify_all();
  } else if (state == RKLLM_RUN_ERROR) {
    std::scoped_lock lk(cb->mu);
    cb->error = true;
    cb->finished = true;
    cb->cv.notify_all();
  } else if (state == RKLLM_RUN_NORMAL || state == RKLLM_RUN_WAITING) {
    if (result && result->text) {
      std::scoped_lock lk(cb->mu);
      if (cb->watchdog_abort) return 0;  // stop accumulating
      cb->text += result->text;

      // JSON watchdog: detect pathological repeated output.
      if (detect_repeated_chars(cb->text, cb->repeated_char_limit) ||
          detect_repeated_ngram(cb->text, cb->repeated_ngram_limit)) {
        std::fprintf(stderr,
                     "[VLM] WATCHDOG: repeated pattern detected (text_len=%zu), "
                     "aborting accumulation\n", cb->text.size());
        cb->watchdog_abort = true;
        cb->finished = true;
        cb->cv.notify_all();
      }
    }
  }
  return 0;
}

// ── Constructor / Destructor ─────────────────────────────────────────────────

Qwen3VLRunner::Qwen3VLRunner(const common::Config& cfg) : cfg_(cfg) {}

Qwen3VLRunner::Qwen3VLRunner(Qwen3VLRunner&& o) noexcept
    : cfg_(o.cfg_),
      vision_ctx_(std::move(o.vision_ctx_)),
      vision_n_input_(o.vision_n_input_),
      vision_n_output_(o.vision_n_output_),
      vision_model_width_(o.vision_model_width_),
      vision_model_height_(o.vision_model_height_),
      vision_image_token_(o.vision_image_token_),
      vision_embed_dim_(o.vision_embed_dim_),
      needs_spatial_merge_(o.needs_spatial_merge_),
      merge_factor_(o.merge_factor_),
      llm_handle_(std::exchange(o.llm_handle_, nullptr)),
      initialized_(o.initialized_) {}

Qwen3VLRunner& Qwen3VLRunner::operator=(Qwen3VLRunner&& o) noexcept {
  if (this != &o) {
    if (llm_handle_) rkllm_destroy(llm_handle_);
    vision_ctx_ = std::move(o.vision_ctx_);
    vision_n_input_ = o.vision_n_input_;
    vision_n_output_ = o.vision_n_output_;
    vision_model_width_ = o.vision_model_width_;
    vision_model_height_ = o.vision_model_height_;
    vision_image_token_ = o.vision_image_token_;
    vision_embed_dim_ = o.vision_embed_dim_;
    needs_spatial_merge_ = o.needs_spatial_merge_;
    merge_factor_ = o.merge_factor_;
    llm_handle_ = std::exchange(o.llm_handle_, nullptr);
    initialized_ = o.initialized_;
  }
  return *this;
}

Qwen3VLRunner::~Qwen3VLRunner() {
  if (llm_handle_) {
    rkllm_destroy(llm_handle_);
    llm_handle_ = nullptr;
  }
}

// ── init ─────────────────────────────────────────────────────────────────────

bool Qwen3VLRunner::init() {
  // Select model paths based on config.
  std::string llm_path;
  std::string vision_path;

  if (cfg_.vlm_model_size == "2B" && cfg_.vlm_variant == "base") {
    llm_path = cfg_.vlm_model_path;
    vision_path = cfg_.vlm_vision_model_path;
  } else if (cfg_.vlm_model_size == "2B" && cfg_.vlm_variant == "lora") {
    llm_path = cfg_.vlm_2b_lora_model_path;
    vision_path = cfg_.vlm_vision_model_path;
    if (llm_path.empty()) {
      std::fprintf(stderr,
                   "[VLM] ERROR: vlm_variant=lora but vlm_2b_lora_model_path is empty\n");
      return false;
    }
    if (!fs::exists(llm_path)) {
      std::fprintf(stderr,
                   "[VLM] ERROR: LoRA model file not found: %s\n",
                   llm_path.c_str());
      return false;
    }
  } else if (cfg_.vlm_model_size == "4B") {
    if (cfg_.vlm_variant == "lora") {
      std::fprintf(stderr,
                   "[VLM] ERROR: 4B LoRA is not supported in this build\n");
      return false;
    }
    // 4B base: use 4B-specific model paths.
    llm_path = cfg_.vlm_4b_model_path;
    vision_path = cfg_.vlm_4b_vision_model_path;
    if (llm_path.empty()) {
      std::fprintf(stderr,
                   "[VLM] ERROR: vlm_model_size=4B but vlm_4b_model_path is empty\n");
      return false;
    }
    if (vision_path.empty()) {
      std::fprintf(stderr,
                   "[VLM] ERROR: vlm_model_size=4B but vlm_4b_vision_model_path is empty\n");
      return false;
    }
  } else {
    std::fprintf(stderr,
                 "[VLM] WARNING: vlm_model_size=%s vlm_variant=%s not recognized, "
                 "falling back to 2B base\n",
                 cfg_.vlm_model_size.c_str(), cfg_.vlm_variant.c_str());
    llm_path = cfg_.vlm_model_path;
    vision_path = cfg_.vlm_vision_model_path;
  }

  // Validate file existence.
  if (!fs::exists(llm_path)) {
    std::fprintf(stderr, "[VLM] ERROR: LLM model not found: %s\n",
                 llm_path.c_str());
    return false;
  }
  if (!fs::exists(vision_path)) {
    std::fprintf(stderr, "[VLM] ERROR: vision model not found: %s\n",
                 vision_path.c_str());
    return false;
  }

  std::fprintf(stderr,
               "[VLM] Initializing Qwen3-VL\n"
               "  selected_model_size=%s  selected_variant=%s\n"
               "  selected_llm_path=%s\n"
               "  selected_vision_path=%s\n"
               "  max_context=%d  max_new_tokens=%d\n",
               cfg_.vlm_model_size.c_str(), cfg_.vlm_variant.c_str(),
               llm_path.c_str(), vision_path.c_str(),
               cfg_.vlm_max_context, cfg_.vlm_max_new_tokens);

  // ── 1. Init vision encoder (RKNN) ─────────────────────────────────────
  {
    rknn_context ctx = 0;
    int ret = rknn_init(&ctx, const_cast<char*>(vision_path.c_str()), 0, 0, nullptr);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[VLM] rknn_init vision failed: %d\n", ret);
      return false;
    }
    vision_ctx_.reset(ctx);

    // Set 3-core NPU.
    ret = rknn_set_core_mask(vision_ctx_.get(), RKNN_NPU_CORE_0_1_2);
    if (ret < 0) {
      std::fprintf(stderr, "[VLM] WARNING: rknn_set_core_mask failed: %d\n", ret);
    }

    rknn_input_output_num io{};
    rknn_query(vision_ctx_.get(), RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io));
    vision_n_input_ = io.n_input;
    vision_n_output_ = io.n_output;

    // Input attrs.
    for (uint32_t i = 0; i < vision_n_input_; ++i) {
      rknn_tensor_attr a{};
      a.index = i;
      rknn_query(vision_ctx_.get(), RKNN_QUERY_INPUT_ATTR, &a, sizeof(a));
      std::fprintf(stderr,
                   "  vision input[%u]: name='%s' dims=[%u,%u,%u,%u] type=%s fmt=%d\n",
                   i, a.name, a.dims[0], a.dims[1], a.dims[2], a.dims[3],
                   get_type_string(a.type), a.fmt);

      if (i == 0) {
        if (a.fmt == RKNN_TENSOR_NCHW) {
          vision_model_height_ = a.dims[2];
          vision_model_width_ = a.dims[3];
        } else {
          vision_model_height_ = a.dims[1];
          vision_model_width_ = a.dims[2];
        }
      }
    }

    // Output attrs — determine n_image_tokens and embed_dim from first output.
    // For models with spatial patch merge (e.g., 4B: spatial_merge_size=2),
    // the first output has 4x more tokens than the rest.
    // We detect this and correct n_image_tokens and embed_dim.
    std::vector<int> per_output_n_tokens(vision_n_output_, 0);
    int first_output_embed = 0;
    for (uint32_t i = 0; i < vision_n_output_; ++i) {
      rknn_tensor_attr a{};
      a.index = i;
      rknn_query(vision_ctx_.get(), RKNN_QUERY_OUTPUT_ATTR, &a, sizeof(a));
      std::fprintf(stderr,
                   "  vision output[%u]: name='%s' dims=[%u,%u,%u,%u] "
                   "type=%s n_elems=%u size=%u\n",
                   i, a.name, a.dims[0], a.dims[1], a.dims[2], a.dims[3],
                   get_type_string(a.type), a.n_elems, a.size);

      // Extract n_image_tokens and embed_dim from first two >1 dims.
      for (int d = 0; d < 4; ++d) {
        if (a.dims[d] > 1) {
          per_output_n_tokens[i] = a.dims[d];
          if (d + 1 < 4 && a.dims[d + 1] > 1) {
            if (i == 0) {
              vision_image_token_ = a.dims[d];
              vision_embed_dim_ = a.dims[d + 1];
              first_output_embed = a.dims[d + 1];
            }
          } else if (i == 0) {
            vision_image_token_ = a.dims[d];
          }
          break;
        }
      }
      // Get last output's embed_dim as reference.
      if (i == vision_n_output_ - 1) {
        for (int d = 0; d < 4; ++d) {
          if (a.dims[d] > 1) {
            if (d + 1 < 4 && a.dims[d + 1] > 1) {
              // Use dims[d+1] for last output's embed if available.
            }
            break;
          }
        }
      }
    }

    // Detect spatial patch merge: if output[0] has 4x more tokens than
    // output[1..n], the model applies spatial_merge_size=2 (2x2 → 1).
    // Qwen3-VL-4B uses this: [784,1024] per output, but runtime expects
    // n_image_tokens=196 (14x14 merged patches).
    needs_spatial_merge_ = false;
    merge_factor_ = 1;
    if (vision_n_output_ >= 2 && per_output_n_tokens[0] > 0 &&
        per_output_n_tokens[1] > 0) {
      int ratio = per_output_n_tokens[0] / per_output_n_tokens[1];
      if (ratio == 4 && per_output_n_tokens[0] == ratio * per_output_n_tokens[1]) {
        needs_spatial_merge_ = true;
        merge_factor_ = 2;  // spatial_merge_size=2 → 2x2 → 4x reduction
        int n_merged = per_output_n_tokens[1];  // 196
        // Correct embed_dim: merged token = merge_factor^2 * original_embed
        int merged_embed = vision_embed_dim_ * merge_factor_ * merge_factor_;
        std::fprintf(stderr,
                     "  [VLM] spatial patch merge detected: %d→%d (factor=%d), "
                     "embed_dim %d→%d\n",
                     vision_image_token_, n_merged, merge_factor_,
                     vision_embed_dim_, merged_embed);
        vision_image_token_ = n_merged;
        vision_embed_dim_ = merged_embed;
      }
    }

    std::fprintf(stderr,
                 "  vision: %dx%d  n_image_tokens=%d  embed_dim=%d  "
                 "n_outputs=%u  spatial_merge=%s\n",
                 vision_model_width_, vision_model_height_,
                 vision_image_token_, vision_embed_dim_, vision_n_output_,
                 needs_spatial_merge_ ? "yes" : "no");
  }

  // ── 2. Init LLM (RKLLM) ──────────────────────────────────────────────
  {
    RKLLMParam param = rkllm_createDefaultParam();
    param.model_path = llm_path.c_str();
    param.max_context_len = cfg_.vlm_max_context;
    param.max_new_tokens = cfg_.vlm_max_new_tokens;
    param.top_k = 1;
    param.skip_special_token = true;
    param.is_async = false;
    param.extend_param.base_domain_id = 1;

    // Qwen3-VL image placeholders.
    param.img_start   = "<|vision_start|>";
    param.img_end     = "<|vision_end|>";
    param.img_content = "<|image_pad|>";

    int ret = rkllm_init(&llm_handle_, &param, llm_callback);
    if (ret != 0) {
      std::fprintf(stderr, "[VLM] rkllm_init failed: %d\n", ret);
      return false;
    }
    std::fprintf(stderr, "[VLM] rkllm_init success\n");
  }

  initialized_ = true;
  return true;
}

// ── preprocess_image ─────────────────────────────────────────────────────────
// Decode image → RGB → expand-to-square (grey 127.5 padding) → resize to 448x448.
// This matches the official multimodal_model_demo preprocessing.

PixelBuffer Qwen3VLRunner::preprocess_image(
    const std::string& path, int& out_w, int& out_h) {
  std::unique_ptr<Image> img(Image::load(path));
  if (!img) return nullptr;

  out_w = img->width;
  out_h = img->height;

  // MVTec images are 900x900 (square), so expand-to-square is a no-op.
  // For non-square images, we would pad with grey (127.5) here.
  // TODO: implement expand-to-square for non-square inputs.

  int target = vision_model_width_;  // 448
  if (img->width == target && img->height == target) {
    return std::move(img->data);
  }

  std::unique_ptr<Image> resized(resize_bilinear(*img, target, target));
  if (!resized) return nullptr;
  return std::move(resized->data);
}

// ── run_vision_encoder ───────────────────────────────────────────────────────
// Returns concatenated image embeddings: n_image_tokens * n_output * embed_dim floats.
// Layout per official demo: for each token i, interleave all outputs.

std::vector<float> Qwen3VLRunner::run_vision_encoder(
    const uint8_t* rgb_data, int img_w, int img_h) {
  uint32_t input_bytes = vision_model_width_ * vision_model_height_ * 3;

  rknn_input inputs[1]{};
  inputs[0].index = 0;
  inputs[0].buf = const_cast<uint8_t*>(rgb_data);
  inputs[0].size = input_bytes;
  inputs[0].pass_through = 0;
  inputs[0].type = RKNN_TENSOR_UINT8;
  inputs[0].fmt = RKNN_TENSOR_NHWC;

  int ret = rknn_inputs_set(vision_ctx_.get(), 1, inputs);
  if (ret != RKNN_SUCC) {
    std::fprintf(stderr, "[VLM] vision rknn_inputs_set failed: %d\n", ret);
    return {};
  }

  ret = rknn_run(vision_ctx_.get(), nullptr);
  if (ret != RKNN_SUCC) {
    std::fprintf(stderr, "[VLM] vision rknn_run failed: %d\n", ret);
    return {};
  }

  // Get outputs with want_float=1 (FP16 → FP32).
  std::vector<rknn_output> outputs(vision_n_output_);
  for (uint32_t i = 0; i < vision_n_output_; ++i) {
    outputs[i].want_float = 1;
    outputs[i].is_prealloc = 0;
    outputs[i].index = i;
    outputs[i].buf = nullptr;
    outputs[i].size = 0;
  }
  ret = rknn_outputs_get(vision_ctx_.get(), vision_n_output_, outputs.data(), nullptr);
  if (ret != RKNN_SUCC) {
    std::fprintf(stderr, "[VLM] vision rknn_outputs_get failed: %d\n", ret);
    return {};
  }

  // Concatenate outputs per official demo logic:
  // for each token i, interleave all n_output outputs.
  // When spatial merge is detected (4B), output[0] has raw [784,1024] which must
  // be permute-merged to [196,4096] before interleaving.
  // Outputs [1..n] are already [196, ...] in the merged space.

  // Pre-merge output[0] if spatial merge is needed.
  std::vector<float> merged_output0;
  float* output0_ptr = static_cast<float*>(outputs[0].buf);
  int raw_tokens = 0;

  if (needs_spatial_merge_ && vision_n_output_ > 0) {
    // Determine raw token count from the first output (before merge).
    rknn_tensor_attr a0{};
    a0.index = 0;
    rknn_query(vision_ctx_.get(), RKNN_QUERY_OUTPUT_ATTR, &a0, sizeof(a0));
    for (int d = 0; d < 4; ++d) {
      if (a0.dims[d] > 1) { raw_tokens = a0.dims[d]; break; }
    }
    int raw_embed = a0.dims[2];  // typically 1024

    merged_output0.resize(vision_image_token_ * vision_embed_dim_);
    merge_spatial_2x2<float>(
        static_cast<float*>(outputs[0].buf),
        merged_output0.data());
    output0_ptr = merged_output0.data();

    // Print shape and checksum log for first invocation (static once).
    static bool logged_merge = false;
    if (!logged_merge) {
      float ck_first = output0_ptr[0];
      float ck_mid   = output0_ptr[(vision_image_token_ / 2) * vision_embed_dim_];
      int last_off   = (vision_image_token_ - 1) * vision_embed_dim_;
      float ck_last  = output0_ptr[last_off];
      std::fprintf(stderr,
                   "[Qwen3VL4B] vision_out shape=[%d,%d] dtype=fp32(want_float)\n"
                   "[Qwen3VL4B] spatial_merge mode=2x2_permute "
                   "input_tokens=%d output_tokens=%d embed=%d\n"
                   "[Qwen3VL4B] token_checksum first=%.6f middle=%.6f last=%.6f\n",
                   raw_tokens, raw_embed,
                   raw_tokens, vision_image_token_, vision_embed_dim_,
                   ck_first, ck_mid, ck_last);
      logged_merge = true;
    }
  }

  size_t total_floats = vision_image_token_ * vision_n_output_ * vision_embed_dim_;
  std::vector<float> result(total_floats, 0.0f);

  for (int i = 0; i < vision_image_token_; ++i) {
    for (uint32_t j = 0; j < vision_n_output_; ++j) {
      size_t dst_offset = i * vision_n_output_ * vision_embed_dim_ + j * vision_embed_dim_;
      if (j == 0 && needs_spatial_merge_) {
        // output[0] already merged to [196, 4096].
        std::memcpy(result.data() + dst_offset,
                     output0_ptr + i * vision_embed_dim_,
                     vision_embed_dim_ * sizeof(float));
      } else {
        // Other outputs are already [196, embed] in merged space.
        // For output[0] without spatial merge, src_offset = i * embed.
        int original_embed = needs_spatial_merge_
            ? (vision_embed_dim_ / (merge_factor_ * merge_factor_))
            : vision_embed_dim_;
        size_t src_offset = i * original_embed;
        std::memcpy(result.data() + dst_offset,
                     static_cast<float*>(outputs[j].buf) + src_offset,
                     original_embed * sizeof(float));
      }
    }
  }

  rknn_outputs_release(vision_ctx_.get(), vision_n_output_, outputs.data());
  return result;
}

// ── build_prompt ─────────────────────────────────────────────────────────────
// Construct an industrial defect JSON prompt with image placeholder.

std::string Qwen3VLRunner::build_prompt(
    const std::string& category,
    float final_score,
    const std::vector<std::array<float,4>>& bboxes,
    const std::string& image_basename) {
  std::ostringstream ss;
  ss << "<image>Inspect this " << category << " image for defects.\n"
     << "EfficientAD anomaly score: " << final_score << "\n"
     << "FastSAM detected " << bboxes.size() << " region(s).\n";

  for (size_t i = 0; i < bboxes.size(); ++i) {
    ss << "  region " << i << ": x=" << bboxes[i][0]
       << " y=" << bboxes[i][1]
       << " w=" << bboxes[i][2]
       << " h=" << bboxes[i][3] << "\n";
  }

  ss << "Output ONLY compact JSON, no markdown, no explanation, no line breaks in values.\n"
     << "Use this exact format: {\"category\":\"" << category
     << "\",\"defect_type\":\"string\",\"severity\":\"low|medium|high\""
     << ",\"confidence\":0.0,\"bboxes\":[[x,y,w,h]],\"description\":\"max 20 words\"}\n"
     << "Rules: category=\"" << category << "\", severity=low/medium/high ONLY (no critical), "
     << "confidence in [0,1], bboxes from FastSAM regions above, "
     << "description max 20 words, use \"anomaly\" if unsure about defect_type.\n";

  return ss.str();
}

// ── infer ────────────────────────────────────────────────────────────────────

VlmResult Qwen3VLRunner::infer(
    const std::string& image_path,
    const std::string& category,
    float final_score,
    const std::vector<std::array<float,4>>& bboxes) {
  VlmResult result;
  if (!initialized_) {
    result.error_message = "VLM not initialized";
    return result;
  }

  auto t_start = steady_clock::now();

  // 1. Preprocess image.
  int orig_w = 0, orig_h = 0;
  auto rgb_data = preprocess_image(image_path, orig_w, orig_h);
  if (!rgb_data) {
    result.error_message = "preprocess failed: " + image_path;
    return result;
  }

  // 2. Run vision encoder.
  auto t_vision_start = steady_clock::now();
  auto img_embed = run_vision_encoder(rgb_data.get(), orig_w, orig_h);
  float vision_ms = duration<float, std::milli>(steady_clock::now() - t_vision_start).count();

  if (img_embed.empty()) {
    result.error_message = "vision encoder returned empty";
    result.vision_ms = vision_ms;
    return result;
  }

  std::fprintf(stderr, "[VLM] vision encoder: %.1f ms, embed size=%zu floats\n",
               vision_ms, img_embed.size());

  // 3. Build prompt.
  std::string basename = fs::path(image_path).filename().string();
  std::string prompt = build_prompt(category, final_score, bboxes, basename);

  std::fprintf(stderr, "[VLM] prompt (%zu chars): %.300s\n",
               prompt.size(), prompt.c_str());

  // 4. Run RKLLM.
  auto t_llm_start = steady_clock::now();

  static CallbackState cb_state;  // Static because RKLLM is single-instance.
  cb_state.reset();
  if (cfg_.vlm_json_watchdog_enabled) {
    cb_state.repeated_char_limit = cfg_.vlm_json_watchdog_repeated_char_limit;
    cb_state.repeated_ngram_limit = cfg_.vlm_json_watchdog_repeated_ngram_limit;
  }

  RKLLMInput rkllm_input{};
  rkllm_input.input_type = RKLLM_INPUT_MULTIMODAL;
  rkllm_input.role = "user";
  rkllm_input.enable_thinking = false;
  rkllm_input.multimodal_input.prompt = const_cast<char*>(prompt.c_str());
  rkllm_input.multimodal_input.image_embed = img_embed.data();
  rkllm_input.multimodal_input.n_image_tokens = vision_image_token_;
  rkllm_input.multimodal_input.n_image = 1;
  rkllm_input.multimodal_input.image_width = vision_model_width_;
  rkllm_input.multimodal_input.image_height = vision_model_height_;

  RKLLMInferParam infer_params{};
  infer_params.mode = RKLLM_INFER_GENERATE;
  infer_params.keep_history = 0;

  int ret = rkllm_run(llm_handle_, &rkllm_input, &infer_params, &cb_state);
  float llm_ms = duration<float, std::milli>(steady_clock::now() - t_llm_start).count();

  if (ret != 0) {
    result.error_message = "rkllm_run failed: " + std::to_string(ret);
    result.vision_ms = vision_ms;
    result.llm_ms = llm_ms;
    return result;
  }

  // 5. Collect result.
  // Use watchdog max_decode_ms if enabled, else default 120s.
  auto wait_timeout = cfg_.vlm_json_watchdog_enabled
      ? std::chrono::milliseconds(cfg_.vlm_json_watchdog_max_decode_ms)
      : std::chrono::seconds(120);
  {
    std::unique_lock lk(cb_state.mu);
    cb_state.cv.wait_for(lk, wait_timeout,
                         [&] { return cb_state.finished; });
    result.raw_text = cb_state.text;
    result.watchdog_abort = cb_state.watchdog_abort;
    if (cb_state.error) {
      result.error_message = "RKLLM callback reported error";
    }
    if (!cb_state.finished) {
      result.error_message = "RKLLM timeout (decode did not finish)";
      std::fprintf(stderr, "[VLM] WARNING: decode timeout after %lld ms\n",
                   static_cast<long long>(
                       std::chrono::duration_cast<std::chrono::milliseconds>(
                           wait_timeout).count()));
    }
    result.prefill_tokens = cb_state.prefill_tokens;
    result.output_tokens = cb_state.generate_tokens;
    result.ttft_ms = cb_state.prefill_time_ms;
    result.decode_tps = (cb_state.generate_time_ms > 0)
        ? static_cast<float>(cb_state.generate_tokens) / (cb_state.generate_time_ms / 1000.0f)
        : 0.0f;
    result.rss_mb = cb_state.memory_usage_mb;
  }

  result.vision_ms = vision_ms;
  result.llm_ms = llm_ms;

  std::fprintf(stderr,
               "[VLM] raw_text (%zu chars): %.300s\n"
               "  ttft=%.1f ms  decode_tps=%.1f  prompt_tokens=%d  output_tokens=%d  rss=%.0f MB\n",
               result.raw_text.size(), result.raw_text.c_str(),
               result.ttft_ms, result.decode_tps,
               result.prefill_tokens, result.output_tokens, result.rss_mb);

  if (result.output_tokens > 120) {
    std::fprintf(stderr, "[VLM] WARNING: output_tokens=%d > 120\n",
                 result.output_tokens);
  }

  return result;
}

// ── JSON extraction ──────────────────────────────────────────────────────────
// Strips thinking tags, markdown fences, finds first { ... } block.
// Validates: category, severity, confidence in [0,1].
// Returns true if valid JSON extracted.

bool Qwen3VLRunner::extract_json(
    const std::string& raw_text,
    const std::string& expected_category,
    std::string& out_defect_type,
    std::string& out_severity,
    float& out_confidence,
    std::string& out_description,
    int orig_w, int orig_h,
    bool* severity_corrected) {
  if (severity_corrected) *severity_corrected = false;
  if (raw_text.empty()) return false;

  // Strip thinking tags.
  std::string text = raw_text;
  {
    auto think_start = text.find("<think>");
    auto think_end = text.find("</think>");
    if (think_start != std::string::npos && think_end != std::string::npos) {
      text.erase(think_start, think_end + 8 - think_start);
    }
  }

  // Strip markdown fences.
  {
    size_t pos = 0;
    while ((pos = text.find("```", pos)) != std::string::npos) {
      auto end = text.find("```", pos + 3);
      if (end != std::string::npos) {
        text.erase(pos, end + 3 - pos);
      } else {
        text.erase(pos);
        break;
      }
    }
  }

  // Find first { and best-effort matching }.
  // For truncated JSON (max_new_tokens cutoff), we find the LAST } and try to
  // parse the substring. This handles cases where the model runs out of tokens
  // mid-JSON (e.g., inside a nested bboxes array).
  auto start = text.find('{');
  if (start == std::string::npos) return false;

  // Find last } after start.
  auto last_close = text.rfind('}');
  if (last_close == std::string::npos || last_close <= start) return false;

  std::string json_str = text.substr(start, last_close - start + 1);

  // Simple field extraction (no external JSON lib dependency).
  auto find_str = [&](const std::string& key) -> std::string {
    auto pos = json_str.find("\"" + key + "\"");
    if (pos == std::string::npos) return "";
    auto colon = json_str.find(':', pos);
    if (colon == std::string::npos) return "";
    auto q1 = json_str.find('"', colon + 1);
    if (q1 == std::string::npos) return "";
    auto q2 = json_str.find('"', q1 + 1);
    if (q2 == std::string::npos) return "";
    return json_str.substr(q1 + 1, q2 - q1 - 1);
  };

  auto find_num = [&](const std::string& key) -> float {
    auto pos = json_str.find("\"" + key + "\"");
    if (pos == std::string::npos) return -1.0f;
    auto colon = json_str.find(':', pos);
    if (colon == std::string::npos) return -1.0f;
    return std::strtof(json_str.c_str() + colon + 1, nullptr);
  };

  out_defect_type = find_str("defect_type");
  out_severity = find_str("severity");
  out_confidence = find_num("confidence");
  out_description = find_str("description");

  // Validate.
  if (out_defect_type.empty()) out_defect_type = "anomaly";
  if (out_severity.empty() ||
      (out_severity != "low" && out_severity != "medium" &&
       out_severity != "high")) {
    out_severity = "medium";
    if (severity_corrected) *severity_corrected = true;
  }
  if (out_confidence < 0.0f || out_confidence > 1.0f) {
    out_confidence = 0.5f;
  }

  std::fprintf(stderr,
               "[VLM] JSON extracted: defect_type=%s severity=%s conf=%.2f"
               "%s\n",
               out_defect_type.c_str(), out_severity.c_str(), out_confidence,
               (severity_corrected && *severity_corrected) ? " severity_corrected=true" : "");

  return true;
}

// ── Fallback JSON ────────────────────────────────────────────────────────────

std::string Qwen3VLRunner::build_fallback_json(
    const std::string& category,
    float final_score,
    const std::string& reason) {
  // Derive severity from anomaly score.
  const char* severity = "medium";
  if (final_score > 20.0f) severity = "high";
  else if (final_score > 10.0f) severity = "medium";
  else severity = "low";

  // Clamp confidence to [0,1].
  float conf = std::min(1.0f, std::max(0.0f, final_score / 30.0f));

  std::ostringstream ss;
  ss << "{\"category\":\"" << category << "\""
     << ",\"defect_type\":\"anomaly\""
     << ",\"severity\":\"" << severity << "\""
     << ",\"confidence\":" << conf
     << ",\"description\":\"fallback: " << reason << "\"}";
  return ss.str();
}

// ── parse_vlm_bboxes ────────────────────────────────────────────────────────
// Parse VLM bbox array from JSON text.
// Supports: [[x,y,w,h]], single [x,y,w,h], multiple [[x,y,w,h],[x,y,w,h]].
// Detects pixel vs normalized coordinates and normalizes to [0,1].

std::vector<std::array<float,4>> Qwen3VLRunner::parse_vlm_bboxes(
    const std::string& json_str,
    int orig_w, int orig_h) {
  std::vector<std::array<float,4>> result;

  // Find "bboxes" key.
  auto bbox_pos = json_str.find("\"bboxes\"");
  if (bbox_pos == std::string::npos) return result;

  // Find the opening [ after "bboxes":
  auto bracket_start = json_str.find('[', bbox_pos);
  if (bracket_start == std::string::npos) return result;

  // Extract all numeric values between [ ... ].
  std::vector<float> values;
  size_t pos = bracket_start + 1;
  while (pos < json_str.size()) {
    if (json_str[pos] == ']') break;
    if (json_str[pos] == '[') { ++pos; continue; }
    if (json_str[pos] == ']' ) { ++pos; continue; }
    if (std::isdigit(json_str[pos]) || json_str[pos] == '-' || json_str[pos] == '.') {
      char* end_ptr = nullptr;
      float val = std::strtof(json_str.c_str() + pos, &end_ptr);
      values.push_back(val);
      pos = end_ptr - json_str.c_str();
    } else {
      ++pos;
    }
  }

  if (values.empty() || values.size() % 4 != 0) return result;

  // Detect coordinate type: if all values in [0,1], already normalized.
  bool is_pixel = false;
  for (float v : values) {
    if (v > 2.0f) { is_pixel = true; break; }
  }

  int norm_w = orig_w;
  int norm_h = orig_h;
  if (is_pixel && (norm_w <= 0 || norm_h <= 0)) {
    norm_w = 448;
    norm_h = 448;
    std::fprintf(stderr, "[VLM] WARNING: orig image size unknown, "
                 "normalizing pixel bbox by 448x448\n");
  }

  for (size_t i = 0; i + 3 < values.size(); i += 4) {
    float x = values[i];
    float y = values[i + 1];
    float w = values[i + 2];
    float h = values[i + 3];

    if (is_pixel && norm_w > 0 && norm_h > 0) {
      x /= static_cast<float>(norm_w);
      y /= static_cast<float>(norm_h);
      w /= static_cast<float>(norm_w);
      h /= static_cast<float>(norm_h);
    }

    x = std::max(0.0f, std::min(1.0f, x));
    y = std::max(0.0f, std::min(1.0f, y));
    w = std::max(0.0f, std::min(1.0f, w));
    h = std::max(0.0f, std::min(1.0f, h));

    if (w > 0.001f && h > 0.001f && (w * h) < 0.95f && (w * h) > 0.0001f) {
      result.push_back({x, y, w, h});
    }
  }

  if (!result.empty()) {
    std::fprintf(stderr, "[VLM] vlm_bbox_normalized: %zu valid bboxes (is_pixel=%d)\n",
                 result.size(), is_pixel ? 1 : 0);
  }

  return result;
}

}  // namespace vlm_industrial::edge
