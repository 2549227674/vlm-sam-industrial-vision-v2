// edge/src/pipeline/fastsam_worker.cpp
// Prompt 2C-Fix: T3 FastSAM real bbox extraction with 5-level cleanup, mock VLM JSON.
// output1 mask decode is NOT implemented — see TODO at end of decode_bboxes.
// Qwen3-VL is NOT called in this phase; VLM fields remain mocked.

#include "edge/pipeline/fastsam_worker.hpp"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <vector>

#include "rknn_api.h"

namespace vlm_industrial::edge {

using std::chrono::steady_clock;
using std::chrono::duration;

// ── constants ────────────────────────────────────────────────────────────────

static constexpr uint32_t kAnchors  = 8400u;   // YOLOv8 detection anchors
static constexpr uint32_t kChannels = 37u;      // 4(bbox) + 1(conf) + 32(mask)
static constexpr uint32_t kDetElems = kChannels * kAnchors;

static constexpr float kNmsIouThreshold = 0.45f;

// 5-level cleanup constants
static constexpr size_t kMaxBboxes       = 5;
static constexpr float  kMinAreaRatio    = 0.001f;   // 0.1% of image
static constexpr float  kMaxAreaRatio    = 0.95f;    // 95% of image
static constexpr float  kDedupIouThresh  = 0.7f;     // merge highly overlapping

// ── helpers ──────────────────────────────────────────────────────────────────

static bool is_quantized_type(rknn_tensor_type t) {
  return t == RKNN_TENSOR_INT8 || t == RKNN_TENSOR_UINT8;
}

static float dequant_int8(int8_t raw, int32_t zp, float scale) {
  return (static_cast<float>(raw) - static_cast<float>(zp)) * scale;
}

static float sigmoid(float x) {
  return 1.0f / (1.0f + std::exp(-x));
}

static float iou_xywh(float ax, float ay, float aw, float ah,
                       float bx, float by, float bw, float bh) {
  float ax2 = ax + aw, ay2 = ay + ah;
  float bx2 = bx + bw, by2 = by + bh;
  float ix1 = std::max(ax, bx), iy1 = std::max(ay, by);
  float ix2 = std::min(ax2, bx2), iy2 = std::min(ay2, by2);
  if (ix2 <= ix1 || iy2 <= iy1) return 0.0f;
  float inter = (ix2 - ix1) * (iy2 - iy1);
  float ua = aw * ah + bw * bh - inter;
  return (ua > 0.0f) ? (inter / ua) : 0.0f;
}

static float clamp01(float v) {
  return std::max(0.0f, std::min(1.0f, v));
}

// Print top-N values from a float array (descending).
static void print_top_n(const float* arr, uint32_t n, int top_n,
                        const char* label) {
  if (n == 0) return;
  std::vector<float> sorted(arr, arr + n);
  std::sort(sorted.begin(), sorted.end(), std::greater<float>());
  int count = std::min(top_n, static_cast<int>(sorted.size()));
  std::fprintf(stderr, "  [T3] %s top-%d:", label, count);
  for (int i = 0; i < count; ++i)
    std::fprintf(stderr, " %.4f", sorted[i]);
  std::fprintf(stderr, "\n");
}

// Print min/max/mean of a float array.
static void print_stats(const float* arr, uint32_t n, const char* label) {
  if (n == 0) return;
  float mn = arr[0], mx = arr[0];
  double sum = 0.0;
  for (uint32_t i = 0; i < n; ++i) {
    if (arr[i] < mn) mn = arr[i];
    if (arr[i] > mx) mx = arr[i];
    sum += arr[i];
  }
  std::fprintf(stderr, "  [T3] %s min=%.4f max=%.4f mean=%.4f (n=%u)\n",
               label, mn, mx, sum / n, n);
}

// ── constructor ───────────────────────────────────────────────────────────────

FastSamWorker::FastSamWorker(const common::Config& cfg,
                             common::BoundedQueue<EadResult>& in,
                             common::BoundedQueue<VlmReport>& out,
                             common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), out_(out), m_(m), vlm_runner_(cfg) {}

// ── load_model ────────────────────────────────────────────────────────────────

bool FastSamWorker::load_model() {
  const std::string& path = cfg_.fastsam_model_path;
  std::fprintf(stderr, "[T3] loading FastSAM RKNN: %s\n", path.c_str());

  rknn_context ctx = 0;
  int ret = rknn_init(&ctx, const_cast<char*>(path.c_str()), 0, 0, nullptr);
  if (ret != RKNN_SUCC) {
    std::fprintf(stderr, "[T3] rknn_init failed: %d  path=%s\n", ret, path.c_str());
    return false;
  }
  ctx_.reset(ctx);

  rknn_input_output_num io{};
  rknn_query(ctx_.get(), RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io));
  n_input_  = io.n_input;
  n_output_ = io.n_output;
  std::fprintf(stderr, "[T3] FastSAM loaded: %u inputs, %u outputs\n",
               n_input_, n_output_);

  for (uint32_t i = 0; i < n_input_; ++i) {
    rknn_tensor_attr a{};
    a.index = i;
    rknn_query(ctx_.get(), RKNN_QUERY_INPUT_ATTR, &a, sizeof(a));
    std::fprintf(stderr,
                 "  input[%u]: name='%s' dims=[%u,%u,%u,%u] "
                 "type=%s(%d) fmt=%d qnt_type=%d zp=%d scale=%.6f\n",
                 i, a.name,
                 a.n_dims > 0 ? a.dims[0] : 0,
                 a.n_dims > 1 ? a.dims[1] : 0,
                 a.n_dims > 2 ? a.dims[2] : 0,
                 a.n_dims > 3 ? a.dims[3] : 0,
                 get_type_string(a.type), a.type,
                 a.fmt, a.qnt_type, a.zp, a.scale);
  }

  // Identify detection output by n_elems == 37 * 8400.
  // output1 (prototype masks) n_elems == 32 * 160 * 160 = 819200.
  for (uint32_t i = 0; i < n_output_; ++i) {
    rknn_tensor_attr a{};
    a.index = i;
    rknn_query(ctx_.get(), RKNN_QUERY_OUTPUT_ATTR, &a, sizeof(a));
    std::fprintf(stderr,
                 "  output[%u]: name='%s' dims=[%u,%u,%u,%u] "
                 "type=%s(%d) qnt_type=%d zp=%d scale=%.6f n_elems=%u size=%u\n",
                 i, a.name,
                 a.n_dims > 0 ? a.dims[0] : 0,
                 a.n_dims > 1 ? a.dims[1] : 0,
                 a.n_dims > 2 ? a.dims[2] : 0,
                 a.n_dims > 3 ? a.dims[3] : 0,
                 get_type_string(a.type), a.type,
                 a.qnt_type, a.zp, a.scale,
                 a.n_elems, a.size);

    if (det_out_idx_ < 0 && a.n_elems == kDetElems) {
      det_out_idx_ = static_cast<int>(i);
    }
  }

  if (det_out_idx_ < 0) {
    std::fprintf(stderr,
                 "[T3] WARNING: detection output (n_elems=%u) not found, "
                 "falling back to output index 0\n", kDetElems);
    det_out_idx_ = 0;
  }
  std::fprintf(stderr, "[T3] detection output index: %d\n", det_out_idx_);
  std::fprintf(stderr, "[T3] prototype output index: %d (mask decode TODO)\n",
               1 - det_out_idx_);

  model_loaded_ = true;
  return true;
}

// ── preprocess ────────────────────────────────────────────────────────────────

PixelBuffer FastSamWorker::preprocess(const std::string& image_path,
                                      int& out_orig_w,
                                      int& out_orig_h) {
  std::unique_ptr<Image> img(Image::load(image_path));
  if (!img) return nullptr;

  out_orig_w = img->width;
  out_orig_h = img->height;

  int target = cfg_.fastsam_input_size;

  // MVTec AD images are 900x900 (square), so simple resize == letterbox.
  // TODO: add proper letterbox + grey padding for non-square inputs,
  //       and thread scale/pad_x/pad_y into decode_bboxes for coord recovery.
  if (img->width == target && img->height == target) {
    return std::move(img->data);
  }

  std::unique_ptr<Image> resized(resize_bilinear(*img, target, target));
  if (!resized) return nullptr;
  return std::move(resized->data);
}

// ── decode_bboxes ─────────────────────────────────────────────────────────────

std::vector<VlmReport::BBox> FastSamWorker::decode_bboxes(
    const void* buf,
    uint32_t n_elems,
    rknn_tensor_type out_type,
    int32_t zp_q,
    float scale_q) {

  if (n_elems != kChannels * kAnchors) {
    std::fprintf(stderr,
                 "[T3] decode_bboxes: unexpected n_elems=%u (expected %u)\n",
                 n_elems, kChannels * kAnchors);
    return {};
  }

  // Step 1: convert output0 to float buffer.
  // Layout (NCHW): data[ch * kAnchors + j] -> channel ch, anchor j
  //   ch 0-3: cx, cy, w, h (640-pixel space)
  //   ch 4:   class/object confidence
  //   ch 5-36: mask coefficients (unused — see TODO below)
  //
  // CRITICAL: zp_q / scale_q are output0's EXCLUSIVE params.
  std::vector<float> fdata(n_elems);

  if (is_quantized_type(out_type)) {
    const auto* src = static_cast<const int8_t*>(buf);
    for (uint32_t i = 0; i < n_elems; ++i) {
      fdata[i] = dequant_int8(src[i], zp_q, scale_q);
    }
    std::fprintf(stderr,
                 "  [T3] output0 INT8 dequant: zp=%d scale=%.6f\n",
                 zp_q, scale_q);
  } else {
    // FP16/FP32: want_float=1 already converted to FP32 by RKNN runtime.
    const auto* src = static_cast<const float*>(buf);
    std::memcpy(fdata.data(), src, n_elems * sizeof(float));
    std::fprintf(stderr, "  [T3] output0 FP32 (want_float=1)\n");
  }

  // Step 2: diagnostics — conf channel stats and top-10 values.
  const float* conf_ptr = fdata.data() + 4 * kAnchors;
  print_stats(conf_ptr, kAnchors, "conf_channel");
  print_top_n(conf_ptr, kAnchors, 10, "conf_channel");

  // Determine if sigmoid is needed (Ultralytics ONNX may already apply it).
  bool need_sigmoid = false;
  {
    float max_abs = 0.0f;
    for (uint32_t j = 0; j < std::min(kAnchors, 100u); ++j) {
      float c = std::abs(conf_ptr[j]);
      if (c > max_abs) max_abs = c;
    }
    need_sigmoid = (max_abs > 4.0f);
    if (need_sigmoid) {
      std::fprintf(stderr,
                   "  [T3] max_abs_conf=%.3f > 4.0 -> applying sigmoid\n",
                   max_abs);
    } else {
      std::fprintf(stderr,
                   "  [T3] max_abs_conf=%.3f <= 4.0 -> values already in [0,1]\n",
                   max_abs);
    }
  }

  // Step 3: extract candidates above conf threshold.
  float conf_threshold = cfg_.fastsam_conf;
  float input_sz = static_cast<float>(cfg_.fastsam_input_size);

  struct Candidate {
    float x, y, w, h;  // normalized [0,1]
    float conf;
  };
  std::vector<Candidate> candidates;

  for (uint32_t j = 0; j < kAnchors; ++j) {
    float raw_conf = conf_ptr[j];
    float conf = need_sigmoid ? sigmoid(raw_conf) : raw_conf;
    if (conf < conf_threshold) continue;

    float cx = fdata[0 * kAnchors + j];
    float cy = fdata[1 * kAnchors + j];
    float bw = fdata[2 * kAnchors + j];
    float bh = fdata[3 * kAnchors + j];

    float x = clamp01((cx - bw * 0.5f) / input_sz);
    float y = clamp01((cy - bh * 0.5f) / input_sz);
    float w = clamp01(bw / input_sz);
    float h = clamp01(bh / input_sz);

    if (w < 0.001f || h < 0.001f) continue;
    candidates.push_back({x, y, w, h, conf});
  }

  uint32_t raw_candidate_count = static_cast<uint32_t>(candidates.size());
  std::fprintf(stderr, "  [T3] raw candidates after conf>%.2f: %u\n",
               conf_threshold, raw_candidate_count);

  // Step 3b: if 0 candidates, diagnose and fall back to top-5.
  bool used_top5_fallback = false;
  if (candidates.empty()) {
    // Print bbox channel stats for diagnosis.
    print_stats(fdata.data() + 0 * kAnchors, kAnchors, "cx_channel");
    print_stats(fdata.data() + 1 * kAnchors, kAnchors, "cy_channel");
    print_stats(fdata.data() + 2 * kAnchors, kAnchors, "w_channel");
    print_stats(fdata.data() + 3 * kAnchors, kAnchors, "h_channel");

    std::fprintf(stderr,
                 "  [T3] WARNING: 0 candidates above conf %.2f\n"
                 "  [T3]   Decode assumption may be wrong — check output layout.\n"
                 "  [T3]   Falling back to top-5 anchors by raw conf.\n",
                 conf_threshold);

    struct RawCand { uint32_t j; float conf; };
    std::vector<RawCand> all_raw;
    all_raw.reserve(kAnchors);
    for (uint32_t j = 0; j < kAnchors; ++j) {
      float raw_conf = conf_ptr[j];
      float conf = need_sigmoid ? sigmoid(raw_conf) : raw_conf;
      float bw = fdata[2 * kAnchors + j];
      float bh = fdata[3 * kAnchors + j];
      if (bw > 1.0f && bh > 1.0f) {
        all_raw.push_back({j, conf});
      }
    }
    std::partial_sort(
        all_raw.begin(),
        all_raw.begin() + std::min((size_t)5, all_raw.size()),
        all_raw.end(),
        [](const RawCand& a, const RawCand& b){ return a.conf > b.conf; });

    size_t pick = std::min((size_t)5, all_raw.size());
    for (size_t i = 0; i < pick; ++i) {
      uint32_t j = all_raw[i].j;
      float cx = fdata[0 * kAnchors + j];
      float cy = fdata[1 * kAnchors + j];
      float bw = fdata[2 * kAnchors + j];
      float bh = fdata[3 * kAnchors + j];
      float x = clamp01((cx - bw * 0.5f) / input_sz);
      float y = clamp01((cy - bh * 0.5f) / input_sz);
      float w = clamp01(bw / input_sz);
      float h = clamp01(bh / input_sz);
      if (w >= 0.001f && h >= 0.001f) {
        candidates.push_back({x, y, w, h, all_raw[i].conf});
      }
    }
    used_top5_fallback = true;
    std::fprintf(stderr, "  [T3]   top-5 fallback produced %zu candidates\n",
                 candidates.size());
  }

  // Step 4: greedy NMS.
  std::sort(candidates.begin(), candidates.end(),
            [](const Candidate& a, const Candidate& b){ return a.conf > b.conf; });

  std::vector<bool> suppressed(candidates.size(), false);
  std::vector<VlmReport::BBox> nms_result;

  for (size_t i = 0; i < candidates.size() && nms_result.size() < kMaxBboxes; ++i) {
    if (suppressed[i]) continue;
    const auto& ca = candidates[i];
    nms_result.push_back({ca.x, ca.y, ca.w, ca.h});
    for (size_t k = i + 1; k < candidates.size(); ++k) {
      if (suppressed[k]) continue;
      const auto& ck = candidates[k];
      if (iou_xywh(ca.x, ca.y, ca.w, ca.h,
                   ck.x, ck.y, ck.w, ck.h) > kNmsIouThreshold) {
        suppressed[k] = true;
      }
    }
  }
  std::fprintf(stderr, "  [T3] after NMS (iou=%.2f): %zu bboxes\n",
               kNmsIouThreshold, nms_result.size());

  // Step 5: 5-level bbox cleanup.
  auto cleanup_result = cleanup_bboxes(nms_result, used_top5_fallback);
  return cleanup_result;
}

// ── cleanup_bboxes ────────────────────────────────────────────────────────────
// 5-level cleanup per vlm_bbox_ref.py:
//   1. Remove out-of-bounds (clamp to [0,1])
//   2. Remove too-small area
//   3. Remove too-large area
//   4. Deduplicate high-overlap bboxes
//   5. Limit max count

std::vector<VlmReport::BBox> FastSamWorker::cleanup_bboxes(
    std::vector<VlmReport::BBox> bboxes,
    bool from_fallback) const {

  size_t input_count = bboxes.size();

  // Level 1: clamp to [0,1] and remove degenerate.
  {
    std::vector<VlmReport::BBox> valid;
    for (auto& b : bboxes) {
      b.x = clamp01(b.x);
      b.y = clamp01(b.y);
      b.w = clamp01(b.w);
      b.h = clamp01(b.h);
      if (b.w > 0.0f && b.h > 0.0f) valid.push_back(b);
    }
    bboxes = std::move(valid);
  }
  std::fprintf(stderr, "  [T3] cleanup L1 bounds: %zu -> %zu\n",
               input_count, bboxes.size());

  // Level 2: remove too-small (< 0.1% of image area).
  {
    std::vector<VlmReport::BBox> valid;
    for (const auto& b : bboxes) {
      float area = b.w * b.h;
      if (area >= kMinAreaRatio) valid.push_back(b);
    }
    std::fprintf(stderr, "  [T3] cleanup L2 min_area(%.3f): %zu -> %zu\n",
                 kMinAreaRatio, bboxes.size(), valid.size());
    bboxes = std::move(valid);
  }

  // Level 3: remove too-large (> 95% of image area).
  {
    std::vector<VlmReport::BBox> valid;
    for (const auto& b : bboxes) {
      float area = b.w * b.h;
      if (area <= kMaxAreaRatio) valid.push_back(b);
    }
    std::fprintf(stderr, "  [T3] cleanup L3 max_area(%.2f): %zu -> %zu\n",
                 kMaxAreaRatio, bboxes.size(), valid.size());
    bboxes = std::move(valid);
  }

  // Level 4: deduplicate high-overlap bboxes (greedy by area descending).
  {
    std::sort(bboxes.begin(), bboxes.end(),
              [](const VlmReport::BBox& a, const VlmReport::BBox& b) {
                return (a.w * a.h) > (b.w * b.h);
              });
    std::vector<bool> sup(bboxes.size(), false);
    std::vector<VlmReport::BBox> deduped;
    for (size_t i = 0; i < bboxes.size(); ++i) {
      if (sup[i]) continue;
      deduped.push_back(bboxes[i]);
      for (size_t k = i + 1; k < bboxes.size(); ++k) {
        if (sup[k]) continue;
        if (iou_xywh(bboxes[i].x, bboxes[i].y, bboxes[i].w, bboxes[i].h,
                     bboxes[k].x, bboxes[k].y, bboxes[k].w, bboxes[k].h)
            > kDedupIouThresh) {
          sup[k] = true;
        }
      }
    }
    std::fprintf(stderr, "  [T3] cleanup L4 dedup(iou=%.2f): %zu -> %zu\n",
                 kDedupIouThresh, bboxes.size(), deduped.size());
    bboxes = std::move(deduped);
  }

  // Level 5: limit max count.
  if (bboxes.size() > kMaxBboxes) {
    std::fprintf(stderr, "  [T3] cleanup L5 max_count(%zu): %zu -> %zu\n",
                 kMaxBboxes, bboxes.size(), kMaxBboxes);
    bboxes.resize(kMaxBboxes);
  }

  // Log final summary.
  std::fprintf(stderr, "  [T3] after_cleanup: %zu bboxes%s\n",
               bboxes.size(),
               from_fallback ? " (from top-5 fallback — NOT valid detections)" : "");

  return bboxes;
}

// ── make_fallback_report ──────────────────────────────────────────────────────

VlmReport FastSamWorker::make_fallback_report(const EadResult& ead,
                                              const char* reason) const {
  VlmReport r;
  r.image_path         = ead.image_path;
  r.device_id          = ead.device_id;
  r.line_id            = ead.line_id;
  r.category           = ead.category;
  r.defect_type        = "anomaly";
  r.severity           = "medium";
  r.confidence         = ead.final_score;
  r.anomaly_score      = ead.final_score;
  r.variant            = cfg_.vlm_model_size + "_" + cfg_.vlm_variant;
  r.frame_timestamp_us = ead.frame_timestamp_us;
  r.bboxes.push_back({0.3f, 0.3f, 0.4f, 0.4f});  // center placeholder
  r.pipeline_ms.efficientad = ead.inference_ms;
  r.pipeline_ms.fastsam     = 0.0f;
  r.pipeline_ms.qwen3vl     = 0.0f;
  r.vlm_metrics.json_parse_ok = false;
  std::fprintf(stderr, "[T3] fallback report | reason=%s\n", reason);
  return r;
}

// ── operator() ───────────────────────────────────────────────────────────────

void FastSamWorker::operator()(std::stop_token st) {
  if (!load_model()) {
    std::fprintf(stderr, "[T3] FastSamWorker: model load failed, thread exits\n");
    while (!st.stop_requested()) {
      auto ead_opt = in_.pop(st);
      if (!ead_opt) break;
      out_.push_drop_oldest(make_fallback_report(*ead_opt, "model_load_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
    }
    return;
  }

  // Init Qwen3-VL runner (Prompt 2D).
  bool vlm_ready = vlm_runner_.init();
  if (!vlm_ready) {
    std::fprintf(stderr, "[T3] WARNING: Qwen3-VL init failed, VLM will use fallback JSON\n");
  }

  std::fprintf(stderr,
               "[T3] FastSamWorker started | model=%s input_size=%d conf=%.2f\n",
               cfg_.fastsam_model_path.c_str(),
               cfg_.fastsam_input_size,
               cfg_.fastsam_conf);

  bool first_frame = true;
  uint64_t total_frames = 0;
  uint64_t fallback_frames = 0;

  while (!st.stop_requested()) {
    auto ead_opt = in_.pop(st);
    if (!ead_opt) break;
    const auto& ead = *ead_opt;
    ++total_frames;

    auto t_frame = steady_clock::now();

    std::fprintf(stderr,
                 "[T3] frame %zu | cat=%s | model=%s\n"
                 "     image=%s\n"
                 "     ead_final_score=%.3f ead_infer_ms=%.1f\n",
                 static_cast<std::size_t>(ead.frame_id),
                 ead.category.c_str(),
                 cfg_.fastsam_model_path.c_str(),
                 ead.image_path.c_str(),
                 ead.final_score,
                 ead.inference_ms);

    // Preprocess image (capture orig dimensions for VLM bbox normalization).
    int orig_w_img = 0, orig_h_img = 0;
    {
      std::unique_ptr<Image> tmp_img(Image::load(ead.image_path));
      if (tmp_img) { orig_w_img = tmp_img->width; orig_h_img = tmp_img->height; }
    }

    // ── Preprocess ─────────────────────────────────────────────────────────
    auto t0 = steady_clock::now();
    int orig_w = 0, orig_h = 0;
    auto rgb_data = preprocess(ead.image_path, orig_w, orig_h);
    float preprocess_ms = duration<float, std::milli>(steady_clock::now() - t0).count();

    if (!rgb_data) {
      std::fprintf(stderr, "[T3] preprocess failed: %s\n", ead.image_path.c_str());
      out_.push_drop_oldest(make_fallback_report(ead, "preprocess_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
      ++fallback_frames;
      continue;
    }

    std::fprintf(stderr,
                 "     orig_size=%dx%d  input_size=%d  preprocess_ms=%.1f\n",
                 orig_w, orig_h, cfg_.fastsam_input_size, preprocess_ms);

    // ── Set input ──────────────────────────────────────────────────────────
    // Task 2: pass_through=0 with UINT8 input — RKNN driver handles
    // uint8->model_input_type conversion with mean/std normalization.
    // This works for both INT8 (quantized) and FP16 (no-quant) models.
    uint32_t input_bytes = static_cast<uint32_t>(
        cfg_.fastsam_input_size * cfg_.fastsam_input_size * 3);

    rknn_input inputs[1]{};
    inputs[0].index        = 0;
    inputs[0].buf          = rgb_data.get();
    inputs[0].size         = input_bytes;
    inputs[0].pass_through = 0;
    inputs[0].type         = RKNN_TENSOR_UINT8;
    inputs[0].fmt          = RKNN_TENSOR_NHWC;

    int ret = rknn_inputs_set(ctx_.get(), 1, inputs);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T3] rknn_inputs_set failed: %d\n", ret);
      out_.push_drop_oldest(make_fallback_report(ead, "rknn_inputs_set_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
      ++fallback_frames;
      continue;
    }

    // ── Run inference ──────────────────────────────────────────────────────
    auto t1 = steady_clock::now();
    ret = rknn_run(ctx_.get(), nullptr);
    float infer_ms = duration<float, std::milli>(steady_clock::now() - t1).count();

    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T3] rknn_run failed: %d\n", ret);
      out_.push_drop_oldest(make_fallback_report(ead, "rknn_run_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
      ++fallback_frames;
      continue;
    }
    std::fprintf(stderr, "     infer_ms=%.1f\n", infer_ms);

    // ── Query output attrs (per-tensor; must NOT share between outputs) ────
    struct OutInfo {
      rknn_tensor_attr attr{};
      int want_float{0};
    };
    std::vector<OutInfo> out_info(n_output_);
    for (uint32_t i = 0; i < n_output_; ++i) {
      out_info[i].attr.index = i;
      rknn_query(ctx_.get(), RKNN_QUERY_OUTPUT_ATTR,
                 &out_info[i].attr, sizeof(rknn_tensor_attr));
      // Quantized -> want_float=0 (manual dequant per output).
      // Float (FP16/FP32) -> want_float=1 (runtime converts to FP32).
      out_info[i].want_float = is_quantized_type(out_info[i].attr.type) ? 0 : 1;
    }

    if (first_frame) {
      for (uint32_t i = 0; i < n_output_; ++i) {
        const auto& a = out_info[i].attr;
        std::fprintf(stderr,
                     "  [T3][first_frame] output[%u] name='%s' "
                     "type=%s zp=%d scale=%.6f n_elems=%u "
                     "want_float=%d  <- %s output\n",
                     i, a.name, get_type_string(a.type), a.zp, a.scale,
                     a.n_elems, out_info[i].want_float,
                     (static_cast<int>(i) == det_out_idx_) ? "DETECTION" : "prototype(mask TODO)");
      }
      first_frame = false;
    }

    // ── Get outputs ────────────────────────────────────────────────────────
    std::vector<rknn_output> outputs(n_output_);
    for (uint32_t i = 0; i < n_output_; ++i) {
      outputs[i].want_float  = out_info[i].want_float;
      outputs[i].is_prealloc = 0;
      outputs[i].index       = i;
      outputs[i].buf         = nullptr;
      outputs[i].size        = 0;
    }
    ret = rknn_outputs_get(ctx_.get(), n_output_, outputs.data(), nullptr);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T3] rknn_outputs_get failed: %d\n", ret);
      out_.push_drop_oldest(make_fallback_report(ead, "rknn_outputs_get_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
      ++fallback_frames;
      continue;
    }

    // ── Decode bboxes from detection output ────────────────────────────────
    auto t2 = steady_clock::now();
    std::vector<VlmReport::BBox> bboxes;

    const int di = det_out_idx_;
    if (di >= 0 && static_cast<uint32_t>(di) < n_output_ && outputs[di].buf) {
      const auto& da = out_info[di].attr;
      bboxes = decode_bboxes(outputs[di].buf, da.n_elems, da.type, da.zp, da.scale);
    } else {
      std::fprintf(stderr, "[T3] detection output %d unavailable\n", di);
    }

    // output1 (prototype masks): NOT decoded in this phase.
    // output1 attrs: [1,32,160,160] — 32 mask prototypes at 1/4 input res.
    // Mask decode would combine output1 with output0 ch 5-36 mask coefficients
    // to produce per-instance segmentation masks. Deferred to future work.

    rknn_outputs_release(ctx_.get(), n_output_, outputs.data());

    float postprocess_ms = duration<float, std::milli>(steady_clock::now() - t2).count();

    // ── No-bbox fallback (emergency only) ──────────────────────────────────
    bool bbox_fallback = false;
    if (bboxes.empty()) {
      std::fprintf(stderr,
                   "  [T3] NO VALID BBOX after cleanup -> using center placeholder\n");
      bboxes.push_back({0.3f, 0.3f, 0.4f, 0.4f});
      bbox_fallback = true;
      ++fallback_frames;
    }

    // ── Qwen3-VL inference (Prompt 2D) ─────────────────────────────────────
    auto t_vlm = steady_clock::now();
    std::string vlm_defect_type = "anomaly";
    std::string vlm_severity = "medium";
    float vlm_confidence = 0.5f;
    std::string vlm_description;
    bool vlm_json_ok = false;
    bool vlm_severity_corrected = false;
    VlmResult vlm_result;

    if (vlm_ready && !bbox_fallback) {
      // Convert bboxes to VLM input format.
      std::vector<std::array<float,4>> vlm_bboxes;
      for (const auto& b : bboxes) {
        vlm_bboxes.push_back({b.x, b.y, b.w, b.h});
      }

      vlm_result = vlm_runner_.infer(
          ead.image_path, ead.category, ead.final_score, vlm_bboxes);

      vlm_json_ok = Qwen3VLRunner::extract_json(
          vlm_result.raw_text, ead.category,
          vlm_defect_type, vlm_severity, vlm_confidence, vlm_description,
          orig_w_img, orig_h_img, &vlm_severity_corrected);

      if (vlm_result.watchdog_abort) {
        m_.vlm_watchdog_abort.fetch_add(1, std::memory_order_relaxed);
        std::fprintf(stderr, "[T3] VLM watchdog abort detected, "
                     "text_len=%zu\n", vlm_result.raw_text.size());
      }

      if (vlm_severity_corrected) {
        std::fprintf(stderr, "[T3] severity_corrected=true\n");
      }

      // Parse VLM bboxes from JSON raw_text.
      if (vlm_json_ok) {
        vlm_result.vlm_bboxes = Qwen3VLRunner::parse_vlm_bboxes(
            vlm_result.raw_text, orig_w_img, orig_h_img);
      }

      if (!vlm_json_ok) {
        // Fallback: use rule-based JSON.
        std::string fb = Qwen3VLRunner::build_fallback_json(
            ead.category, ead.final_score, "invalid VLM JSON");
        bool tmp_sc = false;
        vlm_json_ok = Qwen3VLRunner::extract_json(
            fb, ead.category,
            vlm_defect_type, vlm_severity, vlm_confidence, vlm_description,
            0, 0, &tmp_sc);
        vlm_description = "fallback: invalid VLM JSON";
        std::fprintf(stderr, "[T3] VLM JSON parse failed, using fallback\n");
      }
    } else if (!vlm_ready) {
      // VLM not available — use rule-based fallback.
      std::string fb = Qwen3VLRunner::build_fallback_json(
          ead.category, ead.final_score, "VLM not initialized");
      bool tmp_sc = false;
      Qwen3VLRunner::extract_json(
          fb, ead.category,
          vlm_defect_type, vlm_severity, vlm_confidence, vlm_description,
          0, 0, &tmp_sc);
      vlm_description = "fallback: VLM not initialized";
    } else {
      // bbox_fallback — use rule-based.
      std::string fb = Qwen3VLRunner::build_fallback_json(
          ead.category, ead.final_score, "no valid FastSAM bbox");
      bool tmp_sc = false;
      Qwen3VLRunner::extract_json(
          fb, ead.category,
          vlm_defect_type, vlm_severity, vlm_confidence, vlm_description,
          0, 0, &tmp_sc);
      vlm_description = "fallback: no valid FastSAM bbox";
    }

    float vlm_total_ms = duration<float, std::milli>(steady_clock::now() - t_vlm).count();

    // ── VLM bbox fusion (conservative: prefer FastSAM) ─────────────────────
    std::string bbox_source = "fastsam";
    std::string bbox_merge_reason = "default: FastSAM bboxes";
    {
      const auto& vlm_bboxes_parsed = vlm_result.vlm_bboxes;
      std::fprintf(stderr, "  [T3] vlm_bbox_raw: parsed %zu bboxes from VLM\n",
                   vlm_bboxes_parsed.size());
      for (size_t bi = 0; bi < vlm_bboxes_parsed.size(); ++bi) {
        const auto& vb = vlm_bboxes_parsed[bi];
        std::fprintf(stderr, "    vlm_bbox_normalized[%zu]: x=%.4f y=%.4f w=%.4f h=%.4f\n",
                     bi, vb[0], vb[1], vb[2], vb[3]);
      }

      if (!vlm_bboxes_parsed.empty() && !bbox_fallback) {
        // Check if any VLM bbox has IoU > 0.3 with any FastSAM bbox.
        bool vlm_aligned = false;
        for (const auto& vb : vlm_bboxes_parsed) {
          for (const auto& fb : bboxes) {
            if (iou_xywh(vb[0], vb[1], vb[2], vb[3],
                         fb.x, fb.y, fb.w, fb.h) > 0.3f) {
              vlm_aligned = true;
              break;
            }
          }
          if (vlm_aligned) break;
        }

        if (vlm_aligned) {
          // VLM bboxes valid and aligned with FastSAM — use them.
          std::vector<VlmReport::BBox> vlm_bb;
          for (const auto& vb : vlm_bboxes_parsed) {
            vlm_bb.push_back({clamp01(vb[0]), clamp01(vb[1]),
                              clamp01(vb[2]), clamp01(vb[3])});
          }
          bboxes = std::move(vlm_bb);
          bbox_source = "vlm";
          bbox_merge_reason = "VLM bbox aligned with FastSAM (IoU>0.3)";
          std::fprintf(stderr, "  [T3] bbox_source=vlm\n");
        } else {
          bbox_source = "fastsam_fallback";
          bbox_merge_reason = "VLM bbox not aligned with FastSAM (IoU<0.3)";
          std::fprintf(stderr,
                       "  [T3] bbox_source=fastsam_fallback "
                       "(VLM bbox IoU<0.3 with FastSAM)\n");
        }
      }
      std::fprintf(stderr, "  [T3] bbox_merge_reason: %s\n",
                   bbox_merge_reason.c_str());
    }

    float total_ms = duration<float, std::milli>(steady_clock::now() - t_frame).count();

    // ── Log summary ────────────────────────────────────────────────────────
    std::fprintf(stderr,
                 "     postprocess_ms=%.1f  bbox_count=%zu%s  total_ms=%.1f\n"
                 "     vlm: defect_type=%s severity=%s conf=%.2f json_ok=%d\n"
                 "     vlm: vision_ms=%.1f llm_ms=%.1f vlm_total_ms=%.1f\n"
                 "     vlm: raw_text(%.300s)\n",
                 postprocess_ms,
                 bboxes.size(),
                 bbox_fallback ? " (EMERGENCY_FALLBACK)" : "",
                 total_ms,
                 vlm_defect_type.c_str(), vlm_severity.c_str(),
                 vlm_confidence, vlm_json_ok,
                 vlm_result.vision_ms, vlm_result.llm_ms, vlm_total_ms,
                 vlm_result.raw_text.c_str());
    for (size_t i = 0; i < bboxes.size(); ++i) {
      std::fprintf(stderr,
                   "     bbox[%zu] x=%.3f y=%.3f w=%.3f h=%.3f\n",
                   i, bboxes[i].x, bboxes[i].y, bboxes[i].w, bboxes[i].h);
    }
    std::fprintf(stderr, "     [stats] total_frames=%zu fallback_frames=%zu\n",
                 static_cast<size_t>(total_frames),
                 static_cast<size_t>(fallback_frames));

    // Output tokens warning.
    if (vlm_result.output_tokens > 120) {
      std::fprintf(stderr, "  [T3] WARNING: output_tokens=%d > 120, "
                   "consider shortening prompt/description\n",
                   vlm_result.output_tokens);
    }

    // ── Build VlmReport ────────────────────────────────────────────────────
    VlmReport report;
    report.image_path         = ead.image_path;
    report.device_id          = ead.device_id;
    report.line_id            = ead.line_id;
    report.category           = ead.category;
    report.defect_type        = vlm_defect_type;
    report.severity           = vlm_severity;
    report.confidence         = vlm_confidence;
    report.anomaly_score      = ead.final_score;
    report.variant            = cfg_.vlm_model_size + "_" + cfg_.vlm_variant;
    report.frame_timestamp_us = ead.frame_timestamp_us;
    report.bboxes             = std::move(bboxes);

    report.pipeline_ms.efficientad = ead.inference_ms;
    report.pipeline_ms.fastsam     = preprocess_ms + infer_ms + postprocess_ms;
    report.pipeline_ms.qwen3vl     = vlm_total_ms;

    report.vlm_metrics.ttft_ms       = vlm_result.ttft_ms;
    report.vlm_metrics.decode_tps    = vlm_result.decode_tps;
    report.vlm_metrics.prompt_tokens = vlm_result.prefill_tokens;
    report.vlm_metrics.output_tokens = vlm_result.output_tokens;
    report.vlm_metrics.rss_mb        = vlm_result.rss_mb;
    report.vlm_metrics.json_parse_ok = vlm_json_ok;

    // Trace events.
    float ts = 0.0f;
    report.trace_events.push_back(
        {"efficientad_infer", ts, ead.inference_ms * 1000.0f,
         "T2.pipeline", 'X', "pipeline"});
    ts += ead.inference_ms * 1000.0f;
    report.trace_events.push_back(
        {"fastsam_preprocess", ts, preprocess_ms * 1000.0f,
         "T3.fastsam", 'X', "pipeline"});
    ts += preprocess_ms * 1000.0f;
    report.trace_events.push_back(
        {"fastsam_infer", ts, infer_ms * 1000.0f,
         "T3.fastsam", 'X', "pipeline"});
    ts += infer_ms * 1000.0f;
    report.trace_events.push_back(
        {"fastsam_postprocess", ts, postprocess_ms * 1000.0f,
         "T3.fastsam", 'X', "pipeline"});
    ts += postprocess_ms * 1000.0f;
    report.trace_events.push_back(
        {"qwen3vl_generate", ts, vlm_total_ms * 1000.0f,
         "T3.vlm", 'X', "vlm"});
    if (vlm_result.watchdog_abort) {
      float wd_ts = ts + vlm_total_ms * 1000.0f;
      report.trace_events.push_back(
          {"vlm_watchdog_abort", wd_ts, 0.0f,
           "T3.vlm", 'X', "watchdog"});
    }

    out_.push_drop_oldest(std::move(report));
    m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
  }

  std::fprintf(stderr,
               "[T3] FastSamWorker stopped | total_frames=%zu fallback_frames=%zu\n",
               static_cast<size_t>(total_frames),
               static_cast<size_t>(fallback_frames));
}

}  // namespace vlm_industrial::edge
