#include "edge/pipeline/mock_pipeline_worker.hpp"

#include <chrono>
#include <cstdio>

namespace vlm_industrial::edge {

MockPipelineWorker::MockPipelineWorker(
    const common::Config& cfg,
    common::BoundedQueue<CaptureFrame>& in,
    common::BoundedQueue<VlmReport>& out,
    common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), out_(out), m_(m) {}

void MockPipelineWorker::operator()(std::stop_token st) {
  std::fprintf(stderr, "[MockPipeline] started (mock mode, no real inference)\n");

  while (!st.stop_requested()) {
    auto frame_opt = in_.pop(st);
    if (!frame_opt) break;  // stop requested

    auto& frame = *frame_opt;
    auto t0 = std::chrono::steady_clock::now();

    // Construct mock VlmReport matching API_CONTRACT.md DefectCreate semantics.
    VlmReport report;
    report.image_path     = frame.image_path;
    report.device_id      = frame.device_id;
    report.line_id        = frame.line_id;
    report.category       = frame.category;
    report.defect_type    = "mock_defect";
    report.severity       = "medium";
    report.confidence     = 0.75f;
    report.anomaly_score  = 0.75f;
    report.variant        = cfg_.vlm_model_size + "_" + cfg_.vlm_variant;
    report.frame_timestamp_us = frame.timestamp_us;

    // One mock bbox: centered, 20% of image.
    report.bboxes.push_back({0.4f, 0.4f, 0.2f, 0.2f});

    // Mock pipeline timing.
    report.pipeline_ms.efficientad = 5.0f;
    report.pipeline_ms.fastsam     = 40.0f;
    report.pipeline_ms.qwen3vl    = 2000.0f;

    // Mock VLM metrics.
    report.vlm_metrics.ttft_ms       = 1500.0f;
    report.vlm_metrics.decode_tps    = 11.5f;
    report.vlm_metrics.prompt_tokens = 50;
    report.vlm_metrics.output_tokens = 30;
    report.vlm_metrics.rss_mb        = 3100.0f;
    report.vlm_metrics.json_parse_ok = true;

    // Trace events.
    auto frame_us = static_cast<float>(frame.timestamp_us);

    VlmReport::TraceEvent ev_capture;
    ev_capture.name = "capture";
    ev_capture.ts   = 0.0f;
    ev_capture.dur  = 1.0f;
    ev_capture.tid  = "T1.capture";
    ev_capture.cat  = "capture";
    report.trace_events.push_back(ev_capture);

    VlmReport::TraceEvent ev_pipeline;
    ev_pipeline.name = "mock_pipeline";
    ev_pipeline.ts   = 1.0f;
    ev_pipeline.dur  = 5.0f + 40.0f;  // ead + fastsam
    ev_pipeline.tid  = "T2.pipeline";
    ev_pipeline.cat  = "pipeline";
    report.trace_events.push_back(ev_pipeline);

    VlmReport::TraceEvent ev_vlm;
    ev_vlm.name = "mock_vlm";
    ev_vlm.ts   = 46.0f;
    ev_vlm.dur  = 2000.0f;
    ev_vlm.tid  = "T3.vlm";
    ev_vlm.cat  = "vlm";
    report.trace_events.push_back(ev_vlm);

    (void)frame_us;  // used for trace ts calculation in real mode

    out_.push_drop_oldest(std::move(report));
    m_.ead_count.fetch_add(1, std::memory_order_relaxed);
    m_.vlm_count.fetch_add(1, std::memory_order_relaxed);

    auto dt = std::chrono::steady_clock::now() - t0;
    auto us = std::chrono::duration_cast<std::chrono::microseconds>(dt).count();
    if (frame.frame_id % 50 == 0) {
      std::fprintf(stderr, "[MockPipeline] frame %zu processed in %ld us\n",
                   static_cast<std::size_t>(frame.frame_id), us);
    }
  }

  std::fprintf(stderr, "[MockPipeline] stopped\n");
}

}  // namespace vlm_industrial::edge
