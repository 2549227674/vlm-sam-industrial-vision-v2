#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <variant>

namespace vlm_industrial::edge::common {

enum class ErrorCode : uint8_t {
  kNone = 0,
  kFileNotFound,
  kInvalidConfig,
  kRknnInitFailed,
  kRknnQueryFailed,
  kRkllmInitFailed,
  kRkllmInferFailed,
  kJsonParseFailed,
  kUploadFailed,
  kQueueDropped,
  kTimeout,
  kCancelled,
};

inline const char* error_code_str(ErrorCode ec) noexcept {
  switch (ec) {
    case ErrorCode::kNone:            return "none";
    case ErrorCode::kFileNotFound:    return "file_not_found";
    case ErrorCode::kInvalidConfig:   return "invalid_config";
    case ErrorCode::kRknnInitFailed:  return "rknn_init_failed";
    case ErrorCode::kRknnQueryFailed: return "rknn_query_failed";
    case ErrorCode::kRkllmInitFailed: return "rkllm_init_failed";
    case ErrorCode::kRkllmInferFailed:return "rkllm_infer_failed";
    case ErrorCode::kJsonParseFailed: return "json_parse_failed";
    case ErrorCode::kUploadFailed:   return "upload_failed";
    case ErrorCode::kQueueDropped:   return "queue_dropped";
    case ErrorCode::kTimeout:        return "timeout";
    case ErrorCode::kCancelled:      return "cancelled";
  }
  return "unknown";
}

// Lightweight Result<T> for GCC 11 (no std::expected).
// Holds either a value of type T or an ErrorCode.
template <typename T>
class Result {
 public:
  Result(T val) : data_(std::move(val)) {}        // NOLINT implicit
  Result(ErrorCode ec) : data_(ec) {}              // NOLINT implicit

  [[nodiscard]] bool ok() const noexcept {
    return std::holds_alternative<T>(data_);
  }
  explicit operator bool() const noexcept { return ok(); }

  [[nodiscard]] const T& value() const& { return std::get<T>(data_); }
  [[nodiscard]] T& value() & { return std::get<T>(data_); }
  [[nodiscard]] T&& value() && { return std::get<T>(std::move(data_)); }

  [[nodiscard]] ErrorCode error() const noexcept {
    return std::get<ErrorCode>(data_);
  }

  [[nodiscard]] const char* error_str() const noexcept {
    return error_code_str(error());
  }

 private:
  std::variant<T, ErrorCode> data_;
};

// Specialization for void (operation with no return value).
template <>
class Result<void> {
 public:
  Result() : err_(ErrorCode::kNone) {}
  Result(ErrorCode ec) : err_(ec) {}               // NOLINT implicit

  [[nodiscard]] bool ok() const noexcept { return err_ == ErrorCode::kNone; }
  explicit operator bool() const noexcept { return ok(); }

  [[nodiscard]] ErrorCode error() const noexcept { return err_; }
  [[nodiscard]] const char* error_str() const noexcept {
    return error_code_str(err_);
  }

 private:
  ErrorCode err_;
};

}  // namespace vlm_industrial::edge::common
