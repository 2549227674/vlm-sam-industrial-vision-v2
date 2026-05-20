#pragma once

// Pull in LLMHandle typedef (void*) and rkllm_destroy declaration.
#include "rkllm.h"

#include <utility>

namespace vlm_industrial::edge::common {

// RAII wrapper for LLMHandle (RKLLM inference handle).
// LLMHandle is void*; null is the empty state.
// Move-only; calls rkllm_destroy on destruction.
class UniqueRkllmHandle {
 public:
  UniqueRkllmHandle() = default;
  explicit UniqueRkllmHandle(LLMHandle h) noexcept : handle_(h) {}

  UniqueRkllmHandle(const UniqueRkllmHandle&) = delete;
  UniqueRkllmHandle& operator=(const UniqueRkllmHandle&) = delete;

  UniqueRkllmHandle(UniqueRkllmHandle&& o) noexcept
      : handle_(std::exchange(o.handle_, nullptr)) {}
  UniqueRkllmHandle& operator=(UniqueRkllmHandle&& o) noexcept {
    if (this != &o) {
      reset();
      handle_ = std::exchange(o.handle_, nullptr);
    }
    return *this;
  }

  ~UniqueRkllmHandle() { reset(); }

  [[nodiscard]] LLMHandle get() const noexcept { return handle_; }
  [[nodiscard]] bool valid() const noexcept { return handle_ != nullptr; }

  // Destroy current handle (if valid) and adopt h.
  void reset(LLMHandle h = nullptr) noexcept {
    if (handle_ != nullptr) rkllm_destroy(handle_);
    handle_ = h;
  }

  // Release ownership without destroying.
  [[nodiscard]] LLMHandle release() noexcept {
    return std::exchange(handle_, nullptr);
  }

 private:
  LLMHandle handle_{nullptr};
};

}  // namespace vlm_industrial::edge::common
