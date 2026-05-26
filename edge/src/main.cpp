// edge_pipeline — RK3588 edge inference pipeline.
// Prompt 2C: T1 image_loop + T2 EfficientAD + T3 FastSAM + T4 Upload.
// Phase 9: queue metrics, VLM watchdog counters.

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
#include "edge/pipeline/fastsam_worker.hpp"   // Prompt 2C: real FastSAM T3
#include "edge/pipeline/localizer_worker.hpp" // Phase 10: ORT localizer T3
#include "edge/upload/upload_worker.hpp"

namespace {
using namespace vlm_industrial::edge::common;
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
  std::fprintf(stderr, "ead_score_mode:    %s\n",
               score_mode_str(cfg.efficientad_score_mode));
  std::fprintf(stderr, "ead_gate_mode:     %s\n",
               gate_mode_str(cfg.efficientad_gate_mode));
  std::fprintf(stderr, "fastsam_model:     %s\n",
               cfg.fastsam_model_path.c_str());
  std::fprintf(stderr, "fastsam_input_sz:  %d\n", cfg.fastsam_input_size);
  std::fprintf(stderr, "fastsam_conf:      %.2f\n", cfg.fastsam_conf);
  std::fprintf(stderr, "fastsam_enabled:   %s\n",
               cfg.fastsam_enabled ? "true" : "false");
  std::fprintf(stderr, "localizer_backend: %s\n",
               cfg.localizer_backend.c_str());
  if (cfg.localizer_backend != "disabled") {
    std::fprintf(stderr, "localizer_model:   %s\n",
                 cfg.localizer_model_path.c_str());
    std::fprintf(stderr, "localizer_classes: %s\n",
                 cfg.localizer_classes_path.c_str());
    std::fprintf(stderr, "localizer_conf:    %.2f\n", cfg.localizer_conf_thresh);
    std::fprintf(stderr, "localizer_script:  %s\n",
                 cfg.localizer_script_path.c_str());
  }
  std::fprintf(stderr, "model_variant:     %s_%s\n",
               cfg.vlm_model_size.c_str(), cfg.vlm_variant.c_str());
  std::fprintf(stderr, "vlm_watchdog:      %s (max_decode_ms=%d "
               "char_limit=%d ngram_limit=%d)\n",
               cfg.vlm_json_watchdog_enabled ? "enabled" : "disabled",
               cfg.vlm_json_watchdog_max_decode_ms,
               cfg.vlm_json_watchdog_repeated_char_limit,
               cfg.vlm_json_watchdog_repeated_ngram_limit);
}

void print_queue_stats(const char* name, const QueueStats& qs) {
  std::fprintf(stderr, "  %s: push=%zu pop=%zu drop=%zu high_watermark=%zu\n",
               name,
               qs.push_count.load(std::memory_order_relaxed),
               qs.pop_count.load(std::memory_order_relaxed),
               qs.drop_count.load(std::memory_order_relaxed),
               qs.high_watermark.load(std::memory_order_relaxed));
}

void print_metrics(const vlm_industrial::edge::common::PipelineMetrics& m,
                   const QueueStats& q1s, const QueueStats& q2s,
                   const QueueStats& q3s) {
  std::fprintf(stderr, "\n--- Pipeline Metrics ---\n");
  std::fprintf(stderr, "capture:           %zu\n",
               m.capture_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "ead:               %zu\n",
               m.ead_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "vlm:               %zu\n",
               m.vlm_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "upload_ok:         %zu\n",
               m.upload_count.load(std::memory_order_relaxed));
  std::fprintf(stderr, "upload_fail:       %zu\n",
               m.upload_failed.load(std::memory_order_relaxed));
  std::fprintf(stderr, "upload_retry:      %zu\n",
               m.upload_retry.load(std::memory_order_relaxed));
  std::fprintf(stderr, "ead_gate_pass:     %zu\n",
               m.ead_gate_pass.load(std::memory_order_relaxed));
  std::fprintf(stderr, "ead_gate_drop:     %zu\n",
               m.ead_gate_drop.load(std::memory_order_relaxed));
  std::fprintf(stderr, "vlm_watchdog_abort: %zu\n",
               m.vlm_watchdog_abort.load(std::memory_order_relaxed));
  std::fprintf(stderr, "dropped (total):   %zu\n",
               m.dropped_count.load(std::memory_order_relaxed));

  std::fprintf(stderr, "\n--- Queue Stats ---\n");
  print_queue_stats("Q1 (T1->T2)", q1s);
  print_queue_stats("Q2 (T2->T3)", q2s);
  print_queue_stats("Q3 (T3->T4)", q3s);
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

  // Per-queue stats for observability.
  QueueStats q1_stats, q2_stats, q3_stats;

  // Queues: Q1(4) → T2 → Q2(2) → T3 → Q3(4) → T4
  using vlm_industrial::edge::CaptureFrame;
  using vlm_industrial::edge::EadResult;
  using vlm_industrial::edge::VlmReport;
  using vlm_industrial::edge::common::BoundedQueue;

  BoundedQueue<CaptureFrame> q1(4, &q1_stats);
  BoundedQueue<EadResult>    q2(2, &q2_stats);
  BoundedQueue<VlmReport>    q3(4, &q3_stats);

  std::fprintf(stderr, "\n--- Starting pipeline ---\n");

  {
    vlm_industrial::edge::CaptureWorker  t1(cfg, q1, metrics);
    vlm_industrial::edge::EadWorker      t2(cfg, q1, q2, metrics);
    vlm_industrial::edge::UploadWorker   t4(cfg, q3, metrics);

    // T3: config-driven worker selection.
    if (cfg.localizer_backend == "ort") {
      std::fprintf(stderr, "[T3] using LocalizerWorker (ORT CPU fallback)\n");
      vlm_industrial::edge::LocalizerWorker t3(cfg, q2, q3, metrics);
      std::jthread t1_th{std::move(t1)};
      std::jthread t2_th{std::move(t2)};
      std::jthread t3_th{std::move(t3)};
      std::jthread t4_th{std::move(t4)};

      // Periodic metrics dump every ~10 seconds.
      int tick = 0;
      while (!g_shutdown_requested.load(std::memory_order_acquire)) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        if (++tick >= 50) {
          tick = 0;
          std::fprintf(stderr, "\n--- Periodic Metrics (10s) ---\n");
          print_metrics(metrics, q1_stats, q2_stats, q3_stats);
        }
      }
      std::fprintf(stderr, "\n--- Shutdown requested ---\n");

    } else {
      // Legacy path: FastSamWorker (FastSAM + VLM).
      if (cfg.localizer_backend != "disabled") {
        std::fprintf(stderr, "[T3] WARNING: unknown localizer_backend='%s', "
                     "falling back to FastSamWorker\n",
                     cfg.localizer_backend.c_str());
      }
      std::fprintf(stderr, "[T3] using FastSamWorker (FastSAM + VLM)\n");
      vlm_industrial::edge::FastSamWorker t3(cfg, q2, q3, metrics);
      std::jthread t1_th{std::move(t1)};
      std::jthread t2_th{std::move(t2)};
      std::jthread t3_th{std::move(t3)};
      std::jthread t4_th{std::move(t4)};

      // Periodic metrics dump every ~10 seconds.
      int tick = 0;
      while (!g_shutdown_requested.load(std::memory_order_acquire)) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        if (++tick >= 50) {
          tick = 0;
          std::fprintf(stderr, "\n--- Periodic Metrics (10s) ---\n");
          print_metrics(metrics, q1_stats, q2_stats, q3_stats);
        }
      }
      std::fprintf(stderr, "\n--- Shutdown requested ---\n");
    }
  }  // jthreads join here via RAII

  // Collect queue drop counts from BoundedQueues (after jthreads join).
  metrics.dropped_count.store(
      q1.dropped() + q2.dropped() + q3.dropped(),
      std::memory_order_relaxed);

  print_metrics(metrics, q1_stats, q2_stats, q3_stats);
  std::fprintf(stderr, "\nedge_pipeline: clean exit.\n");

  curl_global_cleanup();
  return 0;
}
