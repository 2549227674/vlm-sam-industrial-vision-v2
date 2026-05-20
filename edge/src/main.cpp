// edge_pipeline — RK3588 16GB edge inference pipeline.
// Phase 7 foundation: config loading + common infrastructure.
// Worker threads (T1-T4) will be added in subsequent phases.

#include <curl/curl.h>
#include <cstdio>

#include "edge/common/config.hpp"
#include "edge/common/config_loader.hpp"
#include "edge/common/http_client.hpp"
#include "edge/common/metrics.hpp"
#include "edge/common/types.hpp"

namespace {

void print_config(const vlm_industrial::edge::common::Config& cfg) {
  std::printf("device_id:         %s\n", cfg.device_id.c_str());
  std::printf("line_id:           %s\n", cfg.line_id.c_str());
  std::printf("backend_url:       %s\n", cfg.backend_url.c_str());
  std::printf("vlm_variant:       %s\n", cfg.vlm_variant.c_str());
  std::printf("vlm_model_size:    %s\n", cfg.vlm_model_size.c_str());
  std::printf("capture_mode:      %s\n", cfg.capture_mode.c_str());
  std::printf("image_loop_dir:    %s\n", cfg.image_loop_dir.c_str());
  std::printf("categories (%zu):  ", cfg.image_loop_categories.size());
  for (const auto& c : cfg.image_loop_categories) {
    std::printf("%s ", c.c_str());
  }
  std::printf("\n");
  std::printf("efficientad_dir:   %s\n", cfg.efficientad_model_dir.c_str());
  std::printf("fastsam_path:      %s\n", cfg.fastsam_model_path.c_str());
  std::printf("vlm_2b_base:       %s\n", cfg.vlm_model_path.c_str());
  std::printf("vlm_2b_lora:       %s\n", cfg.vlm_2b_lora_model_path.c_str());
  std::printf("vlm_4b_base:       %s\n", cfg.vlm_4b_model_path.c_str());
  std::printf("vlm_4b_lora:       %s\n", cfg.vlm_4b_lora_model_path.c_str());
  std::printf("vlm_max_context:   %d\n", cfg.vlm_max_context);
  std::printf("per_category_thresholds:\n");
  for (const auto& [cat, thr] : cfg.per_category_threshold) {
    std::printf("  %s: %.2f\n", cat.c_str(), thr);
  }
}

}  // namespace

int main(int argc, char* argv[]) {
  // curl_global_init must be called once, before any threads start.
  curl_global_init(CURL_GLOBAL_DEFAULT);

  const char* config_path =
      (argc > 1) ? argv[1] : "edge/config.yaml";

  auto result = vlm_industrial::edge::common::load_config(config_path);
  if (!result.ok()) {
    std::fprintf(stderr, "Failed to load config '%s': %s\n",
                 config_path, result.error_str());
    curl_global_cleanup();
    return 1;
  }

  const auto& cfg = result.value();
  print_config(cfg);

  // PipelineMetrics shared across T1-T4 (will be wired up later).
  vlm_industrial::edge::common::PipelineMetrics metrics;
  (void)metrics;

  // HttpClient instantiation test (does not post anything).
  vlm_industrial::edge::common::HttpClient http;
  (void)http;

  std::printf("\nedge_pipeline: foundation OK. Workers not yet implemented.\n");

  curl_global_cleanup();
  return 0;
}
