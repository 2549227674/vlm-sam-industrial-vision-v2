#include "edge/pipeline/ead_worker.hpp"

#include <chrono>
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
                 "  output[%u]: name='%s' dims=[%u,%u,%u,%u] type=%d "
                 "qnt_type=%d zp=%d scale=%.6f size=%u\n",
                 i, attr.name,
                 attr.n_dims > 0 ? attr.dims[0] : 0,
                 attr.n_dims > 1 ? attr.dims[1] : 0,
                 attr.n_dims > 2 ? attr.dims[2] : 0,
                 attr.n_dims > 3 ? attr.dims[3] : 0,
                 attr.type, attr.qnt_type, attr.zp, attr.scale, attr.size);
  }

  cached_category_ = category;
  return true;
}

std::unique_ptr<uint8_t[]> EadWorker::preprocess(const std::string& image_path,
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
  // TODO: RGA im2d virtualaddr path for zero-copy resize on RK3588.
  std::unique_ptr<Image> resized(resize_bilinear(*img, target, target));
  if (!resized) return nullptr;

  out_w = target;
  out_h = target;
  return std::move(resized->data);
}

void EadWorker::operator()(std::stop_token st) {
  std::fprintf(stderr, "[T2] EadWorker started\n");

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
      std::fprintf(stderr, "[T2] skip frame %zudecode/resize failed: %s\n",
                   static_cast<std::size_t>(frame.frame_id),
                   frame.image_path.c_str());
      continue;
    }

    // Set input: pass uint8 RGB, let RKNN driver do quantization conversion.
    // pass_through=0 means the driver applies the model's input quant params
    // (scale, zero_point, mean/std baked in during calibration).
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

    // Get outputs as raw INT8 (want_float=0). We dequantize manually.
    std::vector<rknn_output> outputs(n_output_);
    for (uint32_t i = 0; i < n_output_; ++i) {
      outputs[i].want_float = 0;
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

    // --- RGB input stats for debugging ---
    uint8_t rgb_min = 255, rgb_max = 0;
    uint64_t rgb_sum = 0;
    for (uint32_t i = 0; i < input_size; ++i) {
      uint8_t v = rgb_data[i];
      if (v < rgb_min) rgb_min = v;
      if (v > rgb_max) rgb_max = v;
      rgb_sum += v;
    }
    float rgb_mean = static_cast<float>(rgb_sum) / input_size;

    // --- Select score output: prefer name "pred_score", fallback to smallest n_elems ---
    int score_output_idx = -1;
    std::string selected_name;
    uint32_t selected_n_elems = 0;
    float selected_scale = 1.0f;
    int32_t selected_zp = 0;

    // First pass: look for output named "pred_score".
    for (uint32_t i = 0; i < n_output_; ++i) {
      rknn_tensor_attr attr{};
      attr.index = i;
      rknn_query(ctx_.get(), RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr));
      if (std::string(attr.name) == "pred_score") {
        score_output_idx = static_cast<int>(i);
        selected_name = attr.name;
        selected_n_elems = attr.n_elems;
        selected_scale = attr.scale;
        selected_zp = attr.zp;
        break;
      }
    }

    // Fallback: smallest n_elems.
    if (score_output_idx < 0) {
      uint32_t min_size = UINT32_MAX;
      for (uint32_t i = 0; i < n_output_; ++i) {
        rknn_tensor_attr attr{};
        attr.index = i;
        rknn_query(ctx_.get(), RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr));
        if (attr.n_elems < min_size) {
          min_size = attr.n_elems;
          score_output_idx = static_cast<int>(i);
          selected_name = attr.name;
          selected_n_elems = attr.n_elems;
          selected_scale = attr.scale;
          selected_zp = attr.zp;
        }
      }
    }

    // Manual INT8 dequantization: real_val = (raw_int8 - zero_point) * scale
    float anomaly_score = 0.0f;
    int8_t raw_score = 0;

    if (score_output_idx >= 0 && outputs[score_output_idx].buf) {
      raw_score = static_cast<int8_t*>(
          outputs[score_output_idx].buf)[0];
      anomaly_score = (static_cast<float>(raw_score) -
                       static_cast<float>(selected_zp)) * selected_scale;
      // Clamp to [0, +inf) — EfficientAD anomaly scores are non-negative.
      if (anomaly_score < 0.0f) anomaly_score = 0.0f;
    } else {
      std::fprintf(stderr, "[T2] WARNING: no score output found\n");
    }

    // Release output buffers.
    rknn_outputs_release(ctx_.get(), n_output_, outputs.data());

    // Threshold lookup.
    float threshold = cfg_.efficientad_threshold_default;
    auto it = cfg_.per_category_threshold.find(frame.category);
    if (it != cfg_.per_category_threshold.end()) {
      threshold = it->second;
    }

    bool is_anomaly = anomaly_score > threshold;

    // Enhanced per-frame log.
    std::fprintf(stderr,
                 "[T2] frame %zu | img=%s\n"
                 "      cat=%s | %dx%dx%d | rgb min/max/mean=%u/%u/%.1f\n"
                 "      out[%d]='%s' n_elems=%u | raw=%d zp=%d scale=%.6f\n"
                 "      dequant=%.4f | thr=%.2f | %s\n",
                 static_cast<std::size_t>(frame.frame_id),
                 frame.image_path.c_str(),
                 frame.category.c_str(),
                 img_w, img_h, 3,
                 rgb_min, rgb_max, rgb_mean,
                 score_output_idx, selected_name.c_str(), selected_n_elems,
                 static_cast<int>(raw_score), selected_zp, selected_scale,
                 anomaly_score, threshold,
                 is_anomaly ? "UPLOAD" : "drop");

    m_.ead_count.fetch_add(1, std::memory_order_relaxed);

    if (!is_anomaly) continue;

    // Push EadResult to Q2 for MockT3.
    EadResult result;
    result.image_path = frame.image_path;
    result.category = frame.category;
    result.device_id = frame.device_id;
    result.line_id = frame.line_id;
    result.frame_id = frame.frame_id;
    result.frame_timestamp_us = frame.timestamp_us;
    result.anomaly_score = anomaly_score;
    result.threshold = threshold;
    result.is_anomaly = true;
    result.inference_ms = inference_ms;

    out_.push_drop_oldest(std::move(result));
  }

  release_model();
  std::fprintf(stderr, "[T2] EadWorker stopped\n");
}

}  // namespace vlm_industrial::edge
