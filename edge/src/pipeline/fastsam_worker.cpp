// edge/src/pipeline/fastsam_worker.cpp
// Prompt 2C: T3 FastSAM real bbox extraction, mock VLM JSON.

#include "edge/pipeline/fastsam_worker.hpp"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

#include "rknn_api.h"

namespace vlm_industrial::edge {

using std::chrono::steady_clock;
using std::chrono::duration;

// ── helpers ──────────────────────────────────────────────────────────────────

static bool is_quantized_type(rknn_tensor_type t) {
  return t == RKNN_TENSOR_INT8 || t == RKNN_TENSOR_UINT8;
}

// Dequantize a single INT8 value using this output's own scale/zp.
// MUST NOT use another output's zp/scale.
static float dequant_int8(int8_t raw, int32_t zp, float scale) {
  return (static_cast<float>(raw) - static_cast<float>(zp)) * scale;
}

// Sigmoid helper.
static float sigmoid(float x) {
  return 1.0f / (1.0f + std::exp(-x));
}

// IoU of two boxes in xywh format (all values in same coordinate space).
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

// ── constructor ───────────────────────────────────────────────────────────────

FastSamWorker::FastSamWorker(const common::Config& cfg,
                             common::BoundedQueue<EadResult>& in,
                             common::BoundedQueue<VlmReport>& out,
                             common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), out_(out), m_(m) {}

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

  // Query n_inputs / n_outputs.
  rknn_input_output_num io{};
  rknn_query(ctx_.get(), RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io));
  n_input_  = io.n_input;
  n_output_ = io.n_output;
  std::fprintf(stderr, "[T3] FastSAM loaded: %u inputs, %u outputs\n",
               n_input_, n_output_);

  // Print input attrs.
  for (uint32_t i = 0; i < n_input_; ++i) {
    rknn_tensor_attr a{};
    a.index = i;
    rknn_query(ctx_.get(), RKNN_QUERY_INPUT_ATTR, &a, sizeof(a));
    std::fprintf(stderr,
                 "  input[%u]: name='%s' dims=[%u,%u,%u,%u] "
                 "type=%d fmt=%d qnt_type=%d zp=%d scale=%.6f\n",
                 i, a.name,
                 a.n_dims > 0 ? a.dims[0] : 0,
                 a.n_dims > 1 ? a.dims[1] : 0,
                 a.n_dims > 2 ? a.dims[2] : 0,
                 a.n_dims > 3 ? a.dims[3] : 0,
                 a.type, a.fmt, a.qnt_type, a.zp, a.scale);
  }

  // Print output attrs and find detection output.
  // Detection output: [1, 37, 8400] -> n_elems = 37 * 8400 = 310800.
  // Prototype output: [1, 32, 160, 160] -> n_elems = 819200.
  // We identify by n_elems == 310800. Fallback to index 0.
  constexpr uint32_t kDetElems = 37u * 8400u;

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

  model_loaded_ = true;
  return true;
}

// ── preprocess ────────────────────────────────────────────────────────────────

std::unique_ptr<uint8_t[]> FastSamWorker::preprocess(const std::string& image_path,
                                                      int& out_orig_w,
                                                      int& out_orig_h) {
  std::unique_ptr<Image> img(Image::load(image_path));
  if (!img) return nullptr;

  out_orig_w = img->width;
  out_orig_h = img->height;

  int target = cfg_.fastsam_input_size;  // 640

  // MVTec AD images are 900x900 (square), so simple resize == letterbox.
  // TODO(Prompt-2C-Fix): add proper letterbox + grey padding for non-square
  // images, and thread scale/pad_x/pad_y into decode_bboxes for exact coords.
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

  // Expected: n_elems == 37 * 8400.
  constexpr uint32_t kAnchors  = 8400u;
  constexpr uint32_t kChannels = 37u;

  if (n_elems != kChannels * kAnchors) {
    std::fprintf(stderr,
                 "[T3] decode_bboxes: unexpected n_elems=%u (expected %u)\n",
                 n_elems, kChannels * kAnchors);
    return {};
  }

  // ── Step 1: dequant output0 into float buffer.
  //   Layout (channel-first / NCHW, batch=1):
  //     data[ch * kAnchors + j]  -> channel ch, anchor j
  //   ch 0: cx, ch 1: cy, ch 2: w, ch 3: h  (in 640-pixel space)
  //   ch 4: class confidence
  //   ch 5-36: mask coefficients (TODO: Prompt 2C-Fix)
  //
  // IMPORTANT: zp_q and scale_q are output0's EXCLUSIVE params, NOT output1's.
  std::vector<float> fdata(n_elems);

  if (is_quantized_type(out_type)) {
    // INT8: manual dequant using output0's own zp/scale.
    const auto* src = static_cast<const int8_t*>(buf);
    for (uint32_t i = 0; i < n_elems; ++i) {
      fdata[i] = dequant_int8(src[i], zp_q, scale_q);
    }
    std::fprintf(stderr,
                 "  [T3] det dequant INT8: zp=%d scale=%.6f "
                 "(NOTE: per-tensor quant may reduce conf precision)\n",
                 zp_q, scale_q);
  } else {
    // FLOAT16/FLOAT32: runtime already converted (want_float=1).
    const auto* src = static_cast<const float*>(buf);
    std::memcpy(fdata.data(), src, n_elems * sizeof(float));
  }

  // ── Step 2: extract candidates above conf threshold.
  //   Confidence at ch 4: Ultralytics ONNX export typically already applies
  //   sigmoid, so values are in [0,1]. If values are logits (|val|>>1), apply
  //   sigmoid. We detect this heuristically.
  float conf_threshold = cfg_.fastsam_conf;

  struct Candidate {
    float x, y, w, h;  // normalized [0,1]
    float conf;
  };
  std::vector<Candidate> candidates;

  // Peek at a few confidence values to decide sigmoid needed.
  bool need_sigmoid = false;
  {
    float max_conf_raw = 0.0f;
    for (uint32_t j = 0; j < std::min(kAnchors, 100u); ++j) {
      float c = fdata[4 * kAnchors + j];
      if (std::abs(c) > max_conf_raw) max_conf_raw = std::abs(c);
    }
    // If max raw conf > 4.0, assume logits and apply sigmoid.
    need_sigmoid = (max_conf_raw > 4.0f);
    if (need_sigmoid) {
      std::fprintf(stderr,
                   "  [T3] max_conf_raw=%.3f > 4.0 -> applying sigmoid\n",
                   max_conf_raw);
    }
  }

  float input_sz = static_cast<float>(cfg_.fastsam_input_size);  // 640.0

  for (uint32_t j = 0; j < kAnchors; ++j) {
    float raw_conf = fdata[4 * kAnchors + j];
    float conf = need_sigmoid ? sigmoid(raw_conf) : raw_conf;

    if (conf < conf_threshold) continue;

    float cx = fdata[0 * kAnchors + j];
    float cy = fdata[1 * kAnchors + j];
    float bw = fdata[2 * kAnchors + j];
    float bh = fdata[3 * kAnchors + j];

    // Convert cx,cy,w,h (640-pixel space) -> normalized [0,1] xywh.
    float x = clamp01((cx - bw * 0.5f) / input_sz);
    float y = clamp01((cy - bh * 0.5f) / input_sz);
    float w = clamp01(bw / input_sz);
    float h = clamp01(bh / input_sz);

    // Discard degenerate boxes.
    if (w < 0.001f || h < 0.001f) continue;

    candidates.push_back({x, y, w, h, conf});
  }

  std::fprintf(stderr,
               "  [T3] raw candidates after conf>%.2f: %zu\n",
               conf_threshold, candidates.size());

  // ── Step 3: if no candidates from conf filter, fall back to top-5 by conf.
  //   This handles the INT8 per-tensor precision issue gracefully.
  if (candidates.empty()) {
    std::fprintf(stderr,
                 "  [T3] WARNING: 0 candidates above conf threshold %.2f\n"
                 "  [T3]   Possible cause: INT8 per-tensor scale=%.6f "
                 "quantizes conf values to near-zero.\n"
                 "  [T3]   Falling back to top-5 anchors by raw conf score.\n",
                 conf_threshold, scale_q);

    // Collect all with w>0, h>0 and find top-5 by raw conf.
    struct RawCand { uint32_t j; float conf; };
    std::vector<RawCand> all_raw;
    all_raw.reserve(kAnchors);
    for (uint32_t j = 0; j < kAnchors; ++j) {
      float raw_conf = fdata[4 * kAnchors + j];
      float conf = need_sigmoid ? sigmoid(raw_conf) : raw_conf;
      float bw = fdata[2 * kAnchors + j];
      float bh = fdata[3 * kAnchors + j];
      if (bw > 1.0f && bh > 1.0f) {  // at least 1px
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
    std::fprintf(stderr, "  [T3]   top-5 fallback produced %zu candidates\n",
                 candidates.size());
  }

  // ── Step 4: greedy NMS (IoU threshold = 0.45, standard YOLOv8).
  constexpr float kNmsIouThreshold = 0.45f;
  constexpr size_t kMaxBboxes = 10;

  // Sort by conf descending.
  std::sort(candidates.begin(), candidates.end(),
            [](const Candidate& a, const Candidate& b){ return a.conf > b.conf; });

  std::vector<bool> suppressed(candidates.size(), false);
  std::vector<VlmReport::BBox> result;

  for (size_t i = 0; i < candidates.size() && result.size() < kMaxBboxes; ++i) {
    if (suppressed[i]) continue;
    const auto& ca = candidates[i];
    result.push_back({ca.x, ca.y, ca.w, ca.h});

    for (size_t k = i + 1; k < candidates.size(); ++k) {
      if (suppressed[k]) continue;
      const auto& ck = candidates[k];
      if (iou_xywh(ca.x, ca.y, ca.w, ca.h,
                   ck.x, ck.y, ck.w, ck.h) > kNmsIouThreshold) {
        suppressed[k] = true;
      }
    }
  }

  std::fprintf(stderr,
               "  [T3] after NMS (iou=%.2f): %zu bboxes\n",
               kNmsIouThreshold, result.size());

  // TODO(Prompt-2C-Fix): decode output1 mask prototypes to produce full SAM
  // masks and refine bbox coords from mask bounding boxes.

  return result;
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
    // Drain Q2 to prevent T2 from stalling on Q2 push.
    while (!st.stop_requested()) {
      auto ead_opt = in_.pop(st);
      if (!ead_opt) break;
      out_.push_drop_oldest(make_fallback_report(*ead_opt, "model_load_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
    }
    return;
  }

  std::fprintf(stderr,
               "[T3] FastSamWorker started | model=%s input_size=%d conf=%.2f\n",
               cfg_.fastsam_model_path.c_str(),
               cfg_.fastsam_input_size,
               cfg_.fastsam_conf);

  bool first_frame = true;  // print output attrs on first real frame

  while (!st.stop_requested()) {
    auto ead_opt = in_.pop(st);
    if (!ead_opt) break;
    const auto& ead = *ead_opt;

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

    // ── Preprocess ─────────────────────────────────────────────────────────
    auto t0 = steady_clock::now();
    int orig_w = 0, orig_h = 0;
    auto rgb_data = preprocess(ead.image_path, orig_w, orig_h);
    float preprocess_ms = duration<float, std::milli>(steady_clock::now() - t0).count();

    if (!rgb_data) {
      std::fprintf(stderr, "[T3] preprocess failed: %s\n", ead.image_path.c_str());
      out_.push_drop_oldest(make_fallback_report(ead, "preprocess_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
      continue;
    }

    std::fprintf(stderr,
                 "     orig_size=%dx%d  input_size=%d  preprocess_ms=%.1f\n",
                 orig_w, orig_h, cfg_.fastsam_input_size, preprocess_ms);

    // ── Set input ──────────────────────────────────────────────────────────
    uint32_t input_bytes = static_cast<uint32_t>(
        cfg_.fastsam_input_size * cfg_.fastsam_input_size * 3);

    rknn_input inputs[1]{};
    inputs[0].index        = 0;
    inputs[0].buf          = rgb_data.get();
    inputs[0].size         = input_bytes;
    inputs[0].pass_through = 0;          // driver handles uint8->INT8 conversion
    inputs[0].type         = RKNN_TENSOR_UINT8;
    inputs[0].fmt          = RKNN_TENSOR_NHWC;

    int ret = rknn_inputs_set(ctx_.get(), 1, inputs);
    if (ret != RKNN_SUCC) {
      std::fprintf(stderr, "[T3] rknn_inputs_set failed: %d\n", ret);
      out_.push_drop_oldest(make_fallback_report(ead, "rknn_inputs_set_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
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
      // Quantized -> want_float=0 (manual dequant with this output's own scale/zp).
      // Float     -> want_float=1 (runtime converts FP16->FP32 for us).
      out_info[i].want_float = is_quantized_type(out_info[i].attr.type) ? 0 : 1;
    }

    // Print on first frame so we can verify attrs in the log.
    if (first_frame) {
      for (uint32_t i = 0; i < n_output_; ++i) {
        const auto& a = out_info[i].attr;
        std::fprintf(stderr,
                     "  [T3][first_frame] output[%u] name='%s' "
                     "type=%s zp=%d scale=%.6f n_elems=%u "
                     "want_float=%d  <- %s output\n",
                     i, a.name, get_type_string(a.type), a.zp, a.scale,
                     a.n_elems, out_info[i].want_float,
                     (static_cast<int>(i) == det_out_idx_) ? "DETECTION" : "prototype/other");
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
      continue;
    }

    // ── Decode bboxes from detection output ────────────────────────────────
    auto t2 = steady_clock::now();
    std::vector<VlmReport::BBox> bboxes;

    const int di = det_out_idx_;
    if (di >= 0 && static_cast<uint32_t>(di) < n_output_ && outputs[di].buf) {
      const auto& da = out_info[di].attr;
      // CRITICAL: pass output[di]'s own zp/scale — NOT output[1-di]'s.
      bboxes = decode_bboxes(
          outputs[di].buf,
          da.n_elems,
          da.type,
          da.zp,
          da.scale);
    } else {
      std::fprintf(stderr, "[T3] detection output %d unavailable\n", di);
    }

    // TODO(Prompt-2C-Fix): decode outputs[1-di] (prototype masks) to refine bboxes.

    rknn_outputs_release(ctx_.get(), n_output_, outputs.data());

    float postprocess_ms = duration<float, std::milli>(steady_clock::now() - t2).count();

    // ── No-bbox fallback ───────────────────────────────────────────────────
    bool bbox_fallback = false;
    if (bboxes.empty()) {
      std::fprintf(stderr,
                   "  [T3] no bbox from FastSAM -> using center placeholder\n");
      bboxes.push_back({0.3f, 0.3f, 0.4f, 0.4f});
      bbox_fallback = true;
    }

    float total_ms = duration<float, std::milli>(steady_clock::now() - t_frame).count();

    // ── Log summary ────────────────────────────────────────────────────────
    std::fprintf(stderr,
                 "     postprocess_ms=%.1f  bbox_count=%zu%s  total_ms=%.1f\n",
                 postprocess_ms,
                 bboxes.size(),
                 bbox_fallback ? " (fallback)" : "",
                 total_ms);
    for (size_t i = 0; i < bboxes.size(); ++i) {
      std::fprintf(stderr,
                   "     bbox[%zu] x=%.3f y=%.3f w=%.3f h=%.3f\n",
                   i, bboxes[i].x, bboxes[i].y, bboxes[i].w, bboxes[i].h);
    }

    // ── Derive severity from EfficientAD final_score ───────────────────────
    // Placeholder: Phase 8 will calibrate per-category thresholds.
    const char* severity = "medium";
    {
      float ratio = (ead.threshold > 0.0f) ? (ead.final_score / ead.threshold) : 1.0f;
      if (ratio < 1.5f)      severity = "low";
      else if (ratio < 3.0f) severity = "medium";
      else                   severity = "high";
    }

    // ── Build VlmReport ────────────────────────────────────────────────────
    VlmReport report;
    report.image_path         = ead.image_path;
    report.device_id          = ead.device_id;
    report.line_id            = ead.line_id;
    report.category           = ead.category;
    report.defect_type        = "anomaly";          // TODO(2D): from VLM JSON
    report.severity           = severity;
    report.confidence         = ead.final_score;
    report.anomaly_score      = ead.final_score;
    report.variant            = cfg_.vlm_model_size + "_" + cfg_.vlm_variant;
    report.frame_timestamp_us = ead.frame_timestamp_us;
    report.bboxes             = std::move(bboxes);

    // Pipeline timing (ms).
    report.pipeline_ms.efficientad = ead.inference_ms;
    report.pipeline_ms.fastsam     = preprocess_ms + infer_ms + postprocess_ms;
    report.pipeline_ms.qwen3vl     = 0.0f;  // no VLM in Prompt 2C

    // Mock VLM metrics — TODO(Prompt-2D): replace with real RKLLM output.
    report.vlm_metrics.ttft_ms       = 0.0f;
    report.vlm_metrics.decode_tps    = 0.0f;
    report.vlm_metrics.prompt_tokens = 0;
    report.vlm_metrics.output_tokens = 0;
    report.vlm_metrics.rss_mb        = 0.0f;
    report.vlm_metrics.json_parse_ok = !bbox_fallback;

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

    out_.push_drop_oldest(std::move(report));
    m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
  }

  std::fprintf(stderr, "[T3] FastSamWorker stopped\n");
}

}  // namespace vlm_industrial::edge
