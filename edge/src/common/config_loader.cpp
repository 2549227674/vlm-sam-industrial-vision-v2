#include "edge/common/config_loader.hpp"

#include <algorithm>
#include <fstream>
#include <sstream>
#include <string>

namespace vlm_industrial::edge::common {
namespace {

// Strip leading/trailing whitespace and inline comments (# not inside quotes).
std::string strip(std::string_view s) {
  auto start = s.find_first_not_of(" \t\r\n");
  if (start == std::string_view::npos) return {};
  auto end = s.find_last_not_of(" \t\r\n");
  return std::string{s.substr(start, end - start + 1)};
}

// Strip inline YAML comment (unquoted #).
std::string strip_comment(const std::string& line) {
  bool in_quotes = false;
  for (std::size_t i = 0; i < line.size(); ++i) {
    char c = line[i];
    if (c == '"') in_quotes = !in_quotes;
    if (c == '#' && !in_quotes) {
      return strip(std::string_view{line.data(), i});
    }
  }
  return strip(line);
}

// Remove surrounding quotes if present.
std::string unquote(const std::string& s) {
  if (s.size() >= 2 &&
      ((s.front() == '"' && s.back() == '"') ||
       (s.front() == '\'' && s.back() == '\''))) {
    return s.substr(1, s.size() - 2);
  }
  return s;
}

}  // namespace

Result<Config> load_config(std::string_view path) {
  std::ifstream ifs{std::string{path}};
  if (!ifs.is_open()) {
    return ErrorCode::kFileNotFound;
  }

  Config cfg;
  std::string current_list_key;  // key that owns the current list
  std::string current_section;   // parent key for nested map

  std::string line;
  while (std::getline(ifs, line)) {
    std::string trimmed = strip_comment(line);
    if (trimmed.empty() || trimmed[0] == '#') continue;

    // Count leading spaces for indentation.
    std::size_t indent = 0;
    while (indent < line.size() && line[indent] == ' ') ++indent;

    // List item: "- value"
    if (trimmed.starts_with("- ")) {
      std::string val = unquote(strip(trimmed.substr(2)));
      if (!current_list_key.empty()) {
        // Collect into a temporary storage keyed by list key.
        // We handle specific known list keys below.
      }
      // For image_loop_categories, we collect values directly.
      if (current_list_key == "image_loop_categories") {
        cfg.image_loop_categories.push_back(val);
      }
      continue;
    }

    // Key: value
    auto colon = trimmed.find(':');
    if (colon == std::string::npos) continue;

    std::string key = strip(std::string_view{trimmed.data(), colon});
    std::string val = strip(std::string_view{trimmed.data() + colon + 1,
                                             trimmed.size() - colon - 1});

    // Determine if this starts a new section (nested map).
    if (val.empty()) {
      current_section = key;
      current_list_key.clear();
      continue;
    }

    // If indented under a section, treat as nested key.
    std::string full_key;
    if (indent >= 2 && !current_section.empty()) {
      full_key = current_section + "." + key;
    } else {
      full_key = key;
      current_section.clear();
    }

    // Check if value starts a list (just whitespace before next "- ").
    // We handle this on the NEXT iteration, so set current_list_key.
    // A colon followed by nothing on this line = section header.
    // A colon followed by value = scalar assignment.
    current_list_key.clear();

    // Scalar assignment.
    val = unquote(val);

    // -- Device --
    if (full_key == "device_id")    cfg.device_id = val;
    else if (full_key == "line_id") cfg.line_id = val;

    // -- Backend --
    else if (full_key == "backend_url")       cfg.backend_url = val;
    else if (full_key == "upload_timeout_s")  cfg.upload_timeout_s = std::stoi(val);
    else if (full_key == "upload_max_retries") cfg.upload_max_retries = std::stoi(val);

    // -- AB test --
    else if (full_key == "vlm_variant")    cfg.vlm_variant = val;
    else if (full_key == "vlm_model_size") cfg.vlm_model_size = val;

    // -- Capture --
    else if (full_key == "capture_mode")   cfg.capture_mode = val;
    else if (full_key == "camera_device")  cfg.camera_device = val;
    else if (full_key == "camera_width")   cfg.camera_width = std::stoi(val);
    else if (full_key == "camera_height")  cfg.camera_height = std::stoi(val);

    // -- Image loop --
    else if (full_key == "image_loop_dir")      cfg.image_loop_dir = val;
    else if (full_key == "image_loop_beat_ms")  cfg.image_loop_beat_ms = std::stoi(val);
    else if (full_key == "image_loop_jitter_ms") cfg.image_loop_jitter_ms = std::stoi(val);

    // -- EfficientAD --
    else if (full_key == "efficientad_model_dir")
      cfg.efficientad_model_dir = val;
    else if (full_key == "efficientad_threshold")
      cfg.efficientad_threshold = std::stof(val);
    else if (full_key == "efficientad_input_size")
      cfg.efficientad_input_size = std::stoi(val);
    else if (full_key == "efficientad_threshold_default")
      cfg.efficientad_threshold_default = std::stof(val);

    // -- per_category_threshold --
    else if (full_key.starts_with("per_category_threshold."))
      cfg.per_category_threshold[full_key.substr(23)] = std::stof(val);

    // -- FastSAM --
    else if (full_key == "fastsam_model_path")
      cfg.fastsam_model_path = val;
    else if (full_key == "fastsam_input_size")
      cfg.fastsam_input_size = std::stoi(val);
    else if (full_key == "fastsam_conf")
      cfg.fastsam_conf = std::stof(val);

    // -- Qwen3-VL --
    else if (full_key == "vlm_model_path")
      cfg.vlm_model_path = val;
    else if (full_key == "vlm_vision_model_path")
      cfg.vlm_vision_model_path = val;
    else if (full_key == "vlm_4b_model_path")
      cfg.vlm_4b_model_path = val;
    else if (full_key == "vlm_4b_vision_model_path")
      cfg.vlm_4b_vision_model_path = val;
    else if (full_key == "vlm_2b_lora_model_path")
      cfg.vlm_2b_lora_model_path = val;
    else if (full_key == "vlm_4b_lora_model_path")
      cfg.vlm_4b_lora_model_path = val;
    else if (full_key == "vlm_max_new_tokens")
      cfg.vlm_max_new_tokens = std::stoi(val);
    else if (full_key == "vlm_max_context")
      cfg.vlm_max_context = std::stoi(val);
    else if (full_key == "vlm_npu_core_num")
      cfg.vlm_npu_core_num = std::stoi(val);

    // -- Output --
    else if (full_key == "jpeg_quality")
      cfg.jpeg_quality = std::stoi(val);

    // After parsing a scalar key, check if it's a list header.
    // (We detect this on the NEXT line, but store the key here.)
  }

  // Second pass: detect list keys (key followed by "- " lines).
  // Reset and re-parse to handle list detection.
  // Simpler: just re-scan for "image_loop_categories:" followed by "- ".
  {
    ifs.clear();
    ifs.seekg(0);
    bool in_categories = false;
    while (std::getline(ifs, line)) {
      std::string trimmed = strip_comment(line);
      if (trimmed.empty() || trimmed[0] == '#') {
        in_categories = false;
        continue;
      }
      if (trimmed.starts_with("image_loop_categories:")) {
        in_categories = true;
        cfg.image_loop_categories.clear();  // reset from first pass
        continue;
      }
      if (in_categories && trimmed.starts_with("- ")) {
        cfg.image_loop_categories.push_back(
            unquote(strip(trimmed.substr(2))));
      } else if (!trimmed.starts_with("- ") && !trimmed.empty()) {
        in_categories = false;
      }
    }
  }

  return cfg;
}

}  // namespace vlm_industrial::edge::common
