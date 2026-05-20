// edge_pipeline — RK3588 16GB edge inference pipeline.
// Prompt 2B: T1 image_loop + T2 EfficientAD + T3 MockVlm + T4 Upload.

#include <csignal>
#include <cstdio>
#include <stop_token>
#include <thread>

#include <curl/curl.h>

#include "edge/capture/capture_worker.hpp"
#include "edge/common/bounded_queue.hpp"
#include "edge/common/config.hpp"
#include "edge/common/config_loader.hpp"
#include "edge/common/ead_result.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"
#include "edge/pipeline/ead_worker.hpp"
#include "edge/pipeline/mock_vlm_worker.hpp"
#include "edge/upload/upload_worker.hpp"

namespace {
std::atomic<bool> g_shutdown_requested{false};

void signal_handler(int /*sig*/) {
  g_shutdown_requested.store(true, std::memory_order_release);
}

void install_signal_handlers() {
  struct sigaction sa{};
  sa.sa_handler = signal_handler;
  sigemptyset(&sa.sa_mask);
  sa.sa_flags = 0;
  sigaction(SIGINT, &sa, nullptr);
  sigaction(SIGTERM, &sa, nullptr);
}

void print_config(const vlm_industrial::edge::common::Config& cfg) {
  std::fprintf(stderr, "device_id:         %s\n", cfg.device_id.c_str());
  std::fprintf(stderr, "line_id:           %s\n", cfg.line_id.c_str());
  std::fprintf(stderr, "backend_url:       %s\n", cfg.backend_url.c_str());
  std::fprintf(stderr, "vlm_variant:       %s\n", cfg.vlm_variant.c_str());
  std::fprintf(stderr, "vlm_model_size:    %s\n", cfg.vlm_model_size.c_str());
  std::fprintf(stderr, "capture_mode:      %s\n", cfg.capture_mode.c_str());
  std::fprintf(stderr, "image_loop_dir:    %s\n", cfg.image_loop_dir.c_str());
  std::fprintf(stderr, "categories (%zu):  ",
               cfg.image_loop_categories.size());
  for (const auto& c : cfg.image_loop_categories) {
    std::fprintf(stderr, "%s ", c.c_str());
  }
  std::fprintf(stderr, "\n");
  std::fprintf(stderr, "beat_ms:           %d\n", cfg.image_loop_beat_ms);
  std::fprintf(stderr, "jitter_ms:         %d\n", cfg.image_loop_jitter_ms);
  std::fprintf(stderr, "ead_model_dir:     %s\n",
               cfg.efficientad_model_dir.c_str());
  std::fprintf(stderr, "ead_threshold_def: %.2f\n",
               cfg.efficientad_threshold_default);
  std::fprintf(stderr, "model_variant:     %s_%s\n",
               cfg.vlm_model_size.c_str(), cfg.vlm_variant.c_str());
}

void print_metrics(const vlm_industrial::edge::common::PipelineMetrics& m) {
  std::fprintf(stderr, "\n--- Pipeline Metrics ---\n");
  std::fprintf(stderr, "capture:      %zu\n",
               m.capture_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "ead:          %zu\n",
               m.ead_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "vlm:          %zu\n",
               m.vlm_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "upload_ok:    %zu\n",
               m.upload_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "upload_fail:  %zu\n",
               m.upload_failed.load(std::memory_order_relaxed));
  std::fprintf(stderr, "upload_retry: %zu\n",
               m.upload_retry.load(std::memory_order_relaxed));
  std::fprintf(stderr, "dropped:      %zu\n",
               m.dropped_count.load(std::memory_order_relaxed));
}

}  // namespace

int main(int argc, char* argv[]) {
  curl_global_init(CURL_GLOBAL_DEFAULT);
  install_signal_handlers();

  const char* config_path = (argc > 1) ? argv[1] : "edge/config.yaml";

  auto cfg_result = vlm_industrial::edge::common::load_config(config_path);
  if (!cfg_result.ok()) {
    std::fprintf(stderr, "Failed to load config '%s': %s\n",
                 config_path, cfg_result.error_str());
    curl_global_cleanup();
    return 1;
  }
  const auto& cfg = cfg_result.value();
  print_config(cfg);

  vlm_industrial::edge::common::PipelineMetrics metrics;

  // Queues: Q1(4) → T2 → Q2(2) → T3 → Q3(4) → T4
  using vlm_industrial::edge::CaptureFrame;
  using vlm_industrial::edge::EadResult;
  using vlm_industrial::edge::VlmReport;
  using vlm_industrial::edge::common::BoundedQueue;

  BoundedQueue<CaptureFrame> q1(4);
  BoundedQueue<EadResult>    q2(2);
  BoundedQueue<VlmReport>    q3(4);

  std::fprintf(stderr, "\n--- Starting pipeline (Prompt 2B: real EfficientAD) ---\n");

  {
    vlm_industrial::edge::CaptureWorker t1(cfg, q1, metrics);
    vlm_industrial::edge::EadWorker t2(cfg, q1, q2, metrics);
    vlm_industrial::edge::MockVlmWorker t3(cfg, q2, q3, metrics);
    vlm_industrial::edge::UploadWorker t4(cfg, q3, metrics);

    std::jthread t1_th{std::move(t1)};
    std::jthread t2_th{std::move(t2)};
    std::jthread t3_th{std::move(t3)};
    std::jthread t4_th{std::move(t4)};

    while (!g_shutdown_requested.load(std::memory_order_acquire)) {
      std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    std::fprintf(stderr, "\n--- Shutdown requested ---\n");
  }

  print_metrics(metrics);
  std::fprintf(stderr, "\nedge_pipeline: clean exit.\n");

  curl_global_cleanup();
  return 0;
}
