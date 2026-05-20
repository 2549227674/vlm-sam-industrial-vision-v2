#include "edge/pipeline/mock_vlm_worker.hpp"

#include <cstdio>

namespace vlm_industrial::edge {

MockVlmWorker::MockVlmWorker(const common::Config& cfg,
                             common::BoundedQueue<EadResult>& in,
                             common::BoundedQueue<VlmReport>& out,
                             common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), out_(out), m_(m) {}

void MockVlmWorker::operator()(std::stop_token st) {
  std::fprintf(stderr, "[T3] MockVlmWorker started (mock, no FastSAM/RKLLM)\n");

  while (!st.stop_requested()) {
    auto ead_opt = in_.pop(st);
    if (!ead_opt) break;

    auto& ead = *ead_opt;

    // Build mock VlmReport using real anomaly_score from EfficientAD.
    VlmReport report;
    report.image_path = ead.image_path;
    report.device_id = ead.device_id;
    report.line_id = ead.line_id;
    report.category = ead.category;
    report.defect_type = "anomaly";
    report.severity = "medium";
    report.confidence = 0.75f;
    report.anomaly_score = ead.final_score;
    report.variant = cfg_.vlm_model_size + "_" + cfg_.vlm_variant;
    report.frame_timestamp_us = ead.frame_timestamp_us;

    // One mock bbox.
    report.bboxes.push_back({0.3f, 0.3f, 0.4f, 0.4f});

    // Pipeline timing: real ead inference + mock fastsam/vlm.
    report.pipeline_ms.efficientad = ead.inference_ms;
    report.pipeline_ms.fastsam = 40.0f;   // mock
    report.pipeline_ms.qwen3vl = 2000.0f; // mock

    // Mock VLM metrics.
    report.vlm_metrics.ttft_ms = 1500.0f;
    report.vlm_metrics.decode_tps = 11.5f;
    report.vlm_metrics.prompt_tokens = 50;
    report.vlm_metrics.output_tokens = 30;
    report.vlm_metrics.rss_mb = 3100.0f;
    report.vlm_metrics.json_parse_ok = true;

    // Trace events.
    report.trace_events.push_back({
        "efficientad_infer", 0.0f, ead.inference_ms * 1000.0f,
        "T2.pipeline", 'X', "pipeline"});
    report.trace_events.push_back({
        "mock_fastsam", ead.inference_ms * 1000.0f, 40.0f * 1000.0f,
        "T3.fastsam", 'X', "pipeline"});
    report.trace_events.push_back({
        "mock_vlm", (ead.inference_ms + 40.0f) * 1000.0f, 2000.0f * 1000.0f,
        "T3.vlm", 'X', "vlm"});

    out_.push_drop_oldest(std::move(report));
    m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
  }

  std::fprintf(stderr, "[T3] MockVlmWorker stopped\n");
}

}  // namespace vlm_industrial::edge
