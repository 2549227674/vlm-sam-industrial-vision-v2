#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <string_view>
#include <vector>

namespace vlm_industrial::edge::common {

// Which metric from the raw anomaly map to use as final anomaly score.
enum class ScoreMode {
  kRawScore,   // ReduceMax output (scalar)
  kMapMax,     // max of raw_anomaly_map
  kMapMean,    // mean of raw_anomaly_map
  kMapTop1,    // mean of top-1% pixels
  kMapTop01,   // mean of top-0.1% pixels
};

// How T2 decides whether to push a frame to Q2.
enum class GateMode {
  kThreshold,  // production: final_score > threshold → push
  kPassAll,    // debug only: all frames pushed regardless of score
};

inline ScoreMode parse_score_mode(std::string_view s) {
  if (s == "raw_score") return ScoreMode::kRawScore;
  if (s == "map_max")   return ScoreMode::kMapMax;
  if (s == "map_mean")  return ScoreMode::kMapMean;
  if (s == "map_top1")  return ScoreMode::kMapTop1;
  if (s == "map_top01") return ScoreMode::kMapTop01;
  return ScoreMode::kMapMean;  // default fallback
}

inline GateMode parse_gate_mode(std::string_view s) {
  if (s == "threshold") return GateMode::kThreshold;
  if (s == "pass_all")  return GateMode::kPassAll;
  return GateMode::kThreshold;  // default fallback
}

inline const char* score_mode_str(ScoreMode m) {
  switch (m) {
    case ScoreMode::kRawScore: return "raw_score";
    case ScoreMode::kMapMax:   return "map_max";
    case ScoreMode::kMapMean:  return "map_mean";
    case ScoreMode::kMapTop1:  return "map_top1";
    case ScoreMode::kMapTop01: return "map_top01";
  }
  return "unknown";
}

inline const char* gate_mode_str(GateMode m) {
  switch (m) {
    case GateMode::kThreshold: return "threshold";
    case GateMode::kPassAll:   return "pass_all";
  }
  return "unknown";
}

// Runtime configuration loaded from edge/config.yaml.
struct Config {
  // -- Device --
  std::string device_id{"rk3588-line-A-cam01"};
  std::string line_id{"L1"};

  // -- Backend connection --
  std::string backend_url{"http://192.168.1.100:8000"};
  int32_t     upload_timeout_s{30};
  int32_t     upload_max_retries{5};

  // -- AB test --
  std::string vlm_variant{"base"};     // "base" | "lora"
  std::string vlm_model_size{"4B"};    // "2B" | "4B"

  // -- Capture mode --
  std::string capture_mode{"image_loop"};  // "v4l2" | "image_loop"

  // V4L2 mode
  std::string camera_device{"/dev/video0"};
  int32_t     camera_width{1920};
  int32_t     camera_height{1080};

  // Image loop mode
  std::string              image_loop_dir;
  std::vector<std::string> image_loop_categories;
  int32_t                  image_loop_beat_ms{1500};
  int32_t                  image_loop_jitter_ms{200};

  // -- Stage 1: EfficientAD-S --
  std::string efficientad_model_dir;
  float       efficientad_threshold{0.5f};
  int32_t     efficientad_input_size{256};
  float       efficientad_threshold_default{0.50f};
  ScoreMode   efficientad_score_mode{ScoreMode::kMapMean};
  GateMode    efficientad_gate_mode{GateMode::kThreshold};
  std::map<std::string, float> per_category_threshold;

  // -- Stage 2: FastSAM --
  std::string fastsam_model_path;
  int32_t     fastsam_input_size{640};
  float       fastsam_conf{0.5f};
  bool        fastsam_enabled{true};    // false when localizer replaces FastSAM

  // -- Phase 10: Localizer (ORT / RKNN) --
  std::string localizer_backend{"disabled"};   // "ort" | "rknn" | "disabled"
  std::string localizer_model_path;
  std::string localizer_classes_path;
  float       localizer_conf_thresh{0.25f};
  float       localizer_iou_thresh{0.45f};
  std::string localizer_script_path;           // Python script for ORT backend
  int32_t     localizer_img_size{640};

  // -- Stage 3: Qwen3-VL --
  // Base model paths (vlm_variant == "base")
  std::string vlm_model_path;
  std::string vlm_vision_model_path;
  std::string vlm_4b_model_path;
  std::string vlm_4b_vision_model_path;
  // LoRA model paths (vlm_variant == "lora")
  std::string vlm_2b_lora_model_path;
  std::string vlm_4b_lora_model_path;
  int32_t     vlm_max_new_tokens{200};
  int32_t     vlm_max_context{4096};
  int32_t     vlm_npu_core_num{3};

  // -- VLM JSON watchdog --
  bool        vlm_json_watchdog_enabled{true};
  int32_t     vlm_json_watchdog_max_decode_ms{45000};
  int32_t     vlm_json_watchdog_repeated_char_limit{64};
  int32_t     vlm_json_watchdog_repeated_ngram_limit{32};

  // -- Image output --
  int32_t     jpeg_quality{85};
};

}  // namespace vlm_industrial::edge::common
