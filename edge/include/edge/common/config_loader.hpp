#pragma once

#include "edge/common/config.hpp"
#include "edge/common/error.hpp"

namespace vlm_industrial::edge::common {

// Load Config from edge/config.yaml.
Result<Config> load_config(std::string_view path);

}  // namespace vlm_industrial::edge::common
