#include "edge/pipeline/ead_worker.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <vector>

#include "rknn_api.h"

namespace fs = std::filesystem;

namespace vlm_industrial::edge {

EadWorker::EadWorker(const common::Config& cfg,
                     common::BoundedQueue<CaptureFrame>& in,
                     common::BoundedQueue<EadResult>& out,
                     common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), out_(out), m_(m) {}

void EadWorker::release_model() {
  ctx_.reset();
  cached_category_.clear();
  n_input_ = 0;
  n_output_ = 0;
}

bool EadWorker::load_model(const std::string& category) {
  if (category == cached_category_ && ctx_.valid()) return true;

  release_model();

  // Model path: {efficientad_model_dir}/{category}/model.rknn
  fs::path model_path = fs::path(cfg_.efficientad_model_dir) / category / "model.rknn";
  if (!fs::exists(model_path)) {
    std::fprintf(stderr, "[T2] model not found: %s\n", model_path.c_str());
    return false;
  }

  // Load model file into memory.
  std::ifstream ifs(model_path, std::ios::binary | std::ios::ate);
  if (!ifs.is_open()) {
    std::fprintf(stderr, "[T2] cannot open: %s\n", model_path.c_str());
    return false;
  }
  auto file_size = ifs.tellg();
  ifs.seekg(0);
  std::vector<uint8_t> model_data(static_cast<size_t>(file_size));
  ifs.read(reinterpret_cast<char*>(model_data.data()), file_size);
  ifs.close();

  // Init RKNN context.
  rknn_context raw_ctx = 0;
  int ret = rknn_init(&raw_ctx, model_data.data(),
                      static_cast<uint32_t>(model_data.size()),
                      0, nullptr);
  if (ret != RKNN_SUCC) {
    std::fprintf(stderr, "[T2] rknn_init failed for '%s': %d\n",
                 category.c_str(), ret);
    return false;
  }
  ctx_ = common::UniqueRknnCtx(raw_ctx);

  // Query input/output count.
  rknn_input_output_num io_num{};
  ret = rknn_query(ctx_.get(), RKNN_QUERY_IN_OUT_NUM, &io_num, sizeof(io_num));
  if (ret != RKNN_SUCC) {
    std::fprintf(stderr, "[T2] RKNN_QUERY_IN_OUT_NUM failed: %d\n", ret);
    release_model();
    return false;
  }
  n_input_ = io_num.n_input;
  n_output_ = io_num.n_output;

  std::fprintf(stderr, "[T2] model '%s' loaded: %u inputs, %u outputs\n",
               category.c_str(), n_input_, n_output_);

  // Query and print input attributes.
  for (uint32_t i = 0; i < n_input_; ++i) {
    rknn_tensor_attr attr{};
    attr.index = i;
    rknn_query(ctx_.get(), RKNN_QUERY_INPUT_ATTR, &attr, sizeof(attr));
    std::fprintf(stderr,
                 "  input[%u]: name='%s' dims=[%u,%u,%u,%u] type=%d fmt=%d "
                 "qnt_type=%d zp=%d scale=%.6f\n",
                 i, attr.name,
                 attr.n_dims > 0 ? attr.dims[0] : 0,
                 attr.n_dims > 1 ? attr.dims[1] : 0,
                 attr.n_dims > 2 ? attr.dims[2] : 0,
                 attr.n_dims > 3 ? attr.dims[3] : 0,
                 attr.type, attr.fmt, attr.qnt_type, attr.zp, attr.scale);
  }

  // Query and print output attributes.
  for (uint32_t i = 0; i < n_output_; ++i) {
    rknn_tensor_attr attr{};
    attr.index = i;
    rknn_query(ctx_.get(), RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr));
    std::fprintf(stderr,
                 "  output[%u]: name='%s' dims=[%u,%u,%u,%u] type=%s(%d) "
                 "qnt_type=%d zp=%d scale=%.6f n_elems=%u size=%u\n",
                 i, attr.name,
                 attr.n_dims > 0 ? attr.dims[0] : 0,
                 attr.n_dims > 1 ? attr.dims[1] : 0,
                 attr.n_dims > 2 ? attr.dims[2] : 0,
                 attr.n_dims > 3 ? attr.dims[3] : 0,
                 get_type_string(attr.type), attr.type,
                 attr.qnt_type, attr.zp, attr.scale, attr.n_elems, attr.size);
  }

  cached_category_ = category;
  return true;
}

PixelBuffer EadWorker::preprocess(const std::string& image_path,
                                  int& out_w, int& out_h) {
  // Decode image to RGB.
  std::unique_ptr<Image> img(Image::load(image_path));
  if (!img) return nullptr;

  // Resize to model input size (256x256).
  int target = cfg_.efficientad_input_size;  // 256
  if (img->width == target && img->height == target) {
    out_w = target;
    out_h = target;
    return std::move(img->data);
  }

  // CPU bilinear resize (stb_image_resize2).
  std::unique_ptr<Image> resized(resize_bilinear(*img, target, target));
  if (!resized) return nullptr;

  out_w = target;
  out_h = target;
  return std::move(resized->data);
}

// Find output index by name. Returns -1 if not found.
static int find_output_by_name(rknn_context ctx, uint32_t n_output,
                               const char* target_name) {
  for (uint32_t i = 0; i < n_output; ++i) {
    rknn_tensor_attr attr{};
    attr.index = i;
    rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr));
    if (std::string(attr.name) == target_name) {
      return static_cast<int>(i);
    }
  }
  return -1;
}

// Return human-readable parse mode string for a given tensor type.
static const char* parse_mode_for_type(rknn_tensor_type type) {
  switch (type) {
    case RKNN_TENSOR_INT8:    return "int8_manual_dequant";
    case RKNN_TENSOR_UINT8:   return "uint8_manual_dequant";
    case RKNN_TENSOR_FLOAT16: return "fp16_want_float";
    case RKNN_TENSOR_FLOAT32: return "fp32_direct";
    default:                  return "unknown";
  }
}

// Check if tensor type is quantized integer (needs manual dequant).
static bool is_quantized_type(rknn_tensor_type type) {
  return type == RKNN_TENSOR_INT8 || type == RKNN_TENSOR_UINT8;
}

// Dequantize INT8 buffer to float array.
// out[i] = (raw_int8[i] - zero_point) * scale
static void dequantize_int8(const void* raw_buf, uint32_t n_elems,
                            int32_t zero_point, float scale,
                            float* out) {
  const auto* src = static_cast<const int8_t*>(raw_buf);
  for (uint32_t i = 0; i < n_elems; ++i) {
    out[i] = (static_cast<float>(src[i]) - static_cast<float>(zero_point)) * scale;
  }
}

// Dequantize UINT8 buffer to float array.
static void dequantize_uint8(const void* raw_buf, uint32_t n_elems,
                             int32_t zero_point, float scale,
                             float* out) {
  const auto* src = static_cast<const uint8_t*>(raw_buf);
  for (uint32_t i = 0; i < n_elems; ++i) {
    out[i] = (static_cast<float>(src[i]) - static_cast<float>(zero_point)) * scale;
  }
}

// Extract a single float value from an output buffer (after want_float=1).
static float extract_float_scalar(const void* buf) {
  if (!buf) return 0.0f;
  return static_cast<const float*>(buf)[0];
}

// Compute top-k mean: mean of the k largest values in arr[0..n).
static float top_k_mean(const float* arr, uint32_t n, uint32_t k) {
  if (k == 0 || n == 0) return 0.0f;
  if (k > n) k = n;
  // Partial sort: bring top-k to front.
  std::vector<float> tmp(arr, arr + n);
  std::partial_sort(tmp.begin(), tmp.begin() + k, tmp.end(),
                    std::greater<float>{});
  double sum = 0.0;
  for (uint32_t i = 0; i < k; ++i) sum += tmp[i];
  return static_cast<float>(sum / k);
}

void EadWorker::operator()(std::stop_token st) {
  const char* sm_str = common::score_mode_str(cfg_.efficientad_score_mode);
  const char* gm_str = common::gate_mode_str(cfg_.efficientad_gate_mode);
  std::fprintf(stderr, "[T2] EadWorker started | score_mode=%s gate_mode=%s\n",
               sm_str, gm_str);
  if (cfg_.efficientad_gate_mode == common::GateMode::kPassAll) {
    std::fprintf(stderr,
                 "[T2] *** WARNING: gate_mode=pass_all is DEBUG-ONLY. "
                 "All frames will enter Q2 regardless of score. ***\n");
  }

  while (!st.stop_requested()) {
    auto frame_opt = in_.pop(st);
    if (!frame_opt) break;

    auto& frame = *frame_opt;
    auto t0 = std::chrono::steady_clock::now();

    // Load model for this category (cached if same category).
    if (!load_model(frame.category)) {
      std::fprintf(stderr, "[T2] skip frame %zu: model load failed for '%s'\n",
                   static_cast<std::size_t>(frame.frame_id),
                   frame.category.c_str());
      continue;
    }

    // Preprocess image: decode + resize to 256x256.
    int img_w = 0, img_h = 0;
    auto rgb_data = preprocess(frame.image_path, img_w, img_h);
    if (!rgb_data) {
      std::fprintf(stderr, "[T2] skip frame %zu: decode/resize failed: %s\n",
                   static_cast<std::size_t>(frame.frame_id),
                   frame.image_path.c_str());
      continue;
    }

    // Set input: pass uint8 RGB, let RKNN driver do quantization conversion.
    uint32_t input_size = img_w * img_h * 3;

    rknn_input inputs[1]{};
    inputs[0].index = 0;
    inputs[0].buf = rgb_data.get();
    inputs[0].size = input_size;
    inputs[0].pass_through = 0;  // driver handles uint8→INT8 conversion
    inputs[0].type = RKNN_TENSOR_UINT8;
    inputs[0].fmt = RKNN_TENSOR_NHWC;

    int ret = rknn_inputs_set(ctx_.get(), 1, inputs);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T2] rknn_inputs_set failed: %d\n", ret);
      continue;
    }

    // Run inference.
    ret = rknn_run(ctx_.get(), nullptr);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T2] rknn_run failed: %d\n", ret);
      continue;
    }

    // --- Query ALL output attributes BEFORE rknn_outputs_get ---
    // This determines want_float per output: quantized types get raw INT8
    // for manual dequant; float types get want_float=1 for runtime conversion.
    struct OutputInfo {
      rknn_tensor_attr attr{};
      int   want_float{0};
    };
    std::vector<OutputInfo> out_info(n_output_);
    for (uint32_t i = 0; i < n_output_; ++i) {
      out_info[i].attr.index = i;
      rknn_query(ctx_.get(), RKNN_QUERY_OUTPUT_ATTR,
                 &out_info[i].attr, sizeof(rknn_tensor_attr));
      out_info[i].want_float = is_quantized_type(out_info[i].attr.type) ? 0 : 1;
    }

    // Get outputs with per-tensor want_float.
    std::vector<rknn_output> outputs(n_output_);
    for (uint32_t i = 0; i < n_output_; ++i) {
      outputs[i].want_float = out_info[i].want_float;
      outputs[i].is_prealloc = 0;
      outputs[i].index = i;
      outputs[i].buf = nullptr;
      outputs[i].size = 0;
    }
    ret = rknn_outputs_get(ctx_.get(), n_output_, outputs.data(), nullptr);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T2] rknn_outputs_get failed: %d\n", ret);
      continue;
    }

    auto t1 = std::chrono::steady_clock::now();
    float inference_ms = std::chrono::duration<float, std::milli>(t1 - t0).count();

    // --- Locate raw_score and raw_anomaly_map outputs by name ---
    int score_idx = find_output_by_name(ctx_.get(), n_output_, "raw_score");
    int map_idx   = find_output_by_name(ctx_.get(), n_output_, "raw_anomaly_map");

    // Fallback: try legacy names for backward compatibility.
    if (score_idx < 0)
      score_idx = find_output_by_name(ctx_.get(), n_output_, "pred_score");
    if (map_idx < 0)
      map_idx = find_output_by_name(ctx_.get(), n_output_, "anomaly_map");

    // Fallback: positional — score is smallest n_elems, map is largest.
    if (score_idx < 0 || map_idx < 0) {
      uint32_t min_elems = UINT32_MAX, max_elems = 0;
      for (uint32_t i = 0; i < n_output_; ++i) {
        if (score_idx < 0 && out_info[i].attr.n_elems < min_elems) {
          min_elems = out_info[i].attr.n_elems;
          score_idx = static_cast<int>(i);
        }
        if (map_idx < 0 && out_info[i].attr.n_elems > max_elems) {
          max_elems = out_info[i].attr.n_elems;
          map_idx = static_cast<int>(i);
        }
      }
    }

    if (score_idx < 0 || map_idx < 0 || !outputs[score_idx].buf || !outputs[map_idx].buf) {
      std::fprintf(stderr,
                   "[T2] ERROR: cannot locate score/map outputs "
                   "(score_idx=%d map_idx=%d). Dropping frame %zu.\n",
                   score_idx, map_idx,
                   static_cast<std::size_t>(frame.frame_id));
      rknn_outputs_release(ctx_.get(), n_output_, outputs.data());
      continue;
    }

    // --- Parse raw_score based on tensor type ---
    float raw_score_val = 0.0f;
    const auto& si = out_info[score_idx];
    {
      const char* pm = parse_mode_for_type(si.attr.type);
      if (is_quantized_type(si.attr.type)) {
        // INT8/UINT8: manual dequant from raw integer buffer.
        if (si.attr.type == RKNN_TENSOR_INT8) {
          int8_t raw = static_cast<int8_t*>(outputs[score_idx].buf)[0];
          raw_score_val = (static_cast<float>(raw) -
                           static_cast<float>(si.attr.zp)) * si.attr.scale;
        } else {
          uint8_t raw = static_cast<uint8_t*>(outputs[score_idx].buf)[0];
          raw_score_val = (static_cast<float>(raw) -
                           static_cast<float>(si.attr.zp)) * si.attr.scale;
        }
      } else {
        // FLOAT16/FLOAT32: RKNN runtime already converted to float.
        raw_score_val = extract_float_scalar(outputs[score_idx].buf);
      }
      std::fprintf(stderr,
                   "  output raw_score: type=%s parse_mode=%s "
                   "n_elems=%u size=%u val=%.4f\n",
                   get_type_string(si.attr.type), pm,
                   si.attr.n_elems, outputs[score_idx].size, raw_score_val);
    }

    // --- Parse raw_anomaly_map based on tensor type ---
    const auto& mi = out_info[map_idx];
    const uint32_t map_elems = mi.attr.n_elems;
    std::vector<float> map_float(map_elems);
    {
      const char* pm = parse_mode_for_type(mi.attr.type);
      if (is_quantized_type(mi.attr.type)) {
        // INT8/UINT8: manual dequant.
        if (mi.attr.type == RKNN_TENSOR_INT8) {
          dequantize_int8(outputs[map_idx].buf, map_elems,
                          mi.attr.zp, mi.attr.scale, map_float.data());
        } else {
          dequantize_uint8(outputs[map_idx].buf, map_elems,
                           mi.attr.zp, mi.attr.scale, map_float.data());
        }
      } else {
        // FLOAT16/FLOAT32: buffer is already float after want_float=1.
        const float* src = static_cast<const float*>(outputs[map_idx].buf);
        std::memcpy(map_float.data(), src, map_elems * sizeof(float));
      }
      std::fprintf(stderr,
                   "  output raw_anomaly_map: type=%s parse_mode=%s "
                   "n_elems=%u size=%u\n",
                   get_type_string(mi.attr.type), pm,
                   map_elems, outputs[map_idx].size);
    }

    // --- Compute multi-metric scores (Task 5) ---
    float map_max_val = 0.0f;
    float map_mean_val = 0.0f;
    float map_top1_val = 0.0f;
    float map_top01_val = 0.0f;

    if (map_elems > 0) {
      double sum = 0.0;
      float  mx = map_float[0];
      for (uint32_t i = 0; i < map_elems; ++i) {
        float v = map_float[i];
        sum += v;
        if (v > mx) mx = v;
      }
      map_max_val = mx;
      map_mean_val = static_cast<float>(sum / map_elems);

      uint32_t top1_k  = std::max(1u, map_elems / 100);   // top 1%
      uint32_t top01_k = std::max(1u, map_elems / 1000);   // top 0.1%
      map_top1_val  = top_k_mean(map_float.data(), map_elems, top1_k);
      map_top01_val = top_k_mean(map_float.data(), map_elems, top01_k);
    }

    // Release output buffers (map_float is a copy, safe to release).
    rknn_outputs_release(ctx_.get(), n_output_, outputs.data());

    // --- Select final_score based on score_mode (Task 5) ---
    float final_score = 0.0f;
    switch (cfg_.efficientad_score_mode) {
      case common::ScoreMode::kRawScore: final_score = raw_score_val; break;
      case common::ScoreMode::kMapMax:   final_score = map_max_val;   break;
      case common::ScoreMode::kMapMean:  final_score = map_mean_val;  break;
      case common::ScoreMode::kMapTop1:  final_score = map_top1_val;  break;
      case common::ScoreMode::kMapTop01: final_score = map_top01_val; break;
    }

    // --- Threshold lookup ---
    float threshold = cfg_.efficientad_threshold_default;
    auto it = cfg_.per_category_threshold.find(frame.category);
    if (it != cfg_.per_category_threshold.end()) {
      threshold = it->second;
    }

    // --- Gate decision (Task 6) ---
    bool would_anomaly = final_score > threshold;
    bool push_to_q2 = false;
    const char* decision = "DROP";

    if (cfg_.efficientad_gate_mode == common::GateMode::kPassAll) {
      push_to_q2 = true;
      decision = would_anomaly ? "PASS_ALL_WOULD_UPLOAD" : "PASS_ALL_WOULD_DROP";
    } else {
      push_to_q2 = would_anomaly;
      decision = would_anomaly ? "UPLOAD" : "DROP";
    }

    // --- Enhanced per-frame log (Task 7) ---
    std::fprintf(stderr,
                 "[T2] frame %zu | cat=%s | score_mode=%s | gate_mode=%s\n"
                 "     raw_score=%.2f map_max=%.2f map_mean=%.2f "
                 "map_top1=%.2f map_top01=%.2f\n"
                 "     final_score=%.2f thr=%.2f decision=%s infer_ms=%.1f\n",
                 static_cast<std::size_t>(frame.frame_id),
                 frame.category.c_str(),
                 common::score_mode_str(cfg_.efficientad_score_mode),
                 common::gate_mode_str(cfg_.efficientad_gate_mode),
                 raw_score_val, map_max_val, map_mean_val,
                 map_top1_val, map_top01_val,
                 final_score, threshold, decision, inference_ms);

    m_.ead_count.fetch_add(1, std::memory_order_relaxed);

    if (push_to_q2) {
      m_.ead_gate_pass.fetch_add(1, std::memory_order_relaxed);
    } else {
      m_.ead_gate_drop.fetch_add(1, std::memory_order_relaxed);
      continue;
    }

    // Build EadResult and push to Q2.
    EadResult result;
    result.image_path = frame.image_path;
    result.category = frame.category;
    result.device_id = frame.device_id;
    result.line_id = frame.line_id;
    result.frame_id = frame.frame_id;
    result.frame_timestamp_us = frame.timestamp_us;
    result.raw_score = raw_score_val;
    result.map_max = map_max_val;
    result.map_mean = map_mean_val;
    result.map_top1 = map_top1_val;
    result.map_top01 = map_top01_val;
    result.final_score = final_score;
    result.threshold = threshold;
    result.is_anomaly = would_anomaly;
    result.score_mode = static_cast<int8_t>(cfg_.efficientad_score_mode);
    result.gate_mode = static_cast<int8_t>(cfg_.efficientad_gate_mode);
    result.inference_ms = inference_ms;

    out_.push_drop_oldest(std::move(result));
  }

  release_model();
  std::fprintf(stderr, "[T2] EadWorker stopped\n");
}

}  // namespace vlm_industrial::edge
