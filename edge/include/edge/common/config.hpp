#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace vlm_industrial::edge::common {

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
  std::map<std::string, float> per_category_threshold;

  // -- Stage 2: FastSAM --
  std::string fastsam_model_path;
  int32_t     fastsam_input_size{640};
  float       fastsam_conf{0.5f};

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

  // -- Image output --
  int32_t     jpeg_quality{85};
};

}  // namespace vlm_industrial::edge::common
