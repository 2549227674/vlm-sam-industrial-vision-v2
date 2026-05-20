#pragma once

// Pull in rknn_context typedef and rknn_destroy declaration.
#include "rknn_api.h"

#include <utility>

namespace vlm_industrial::edge::common {

// RAII wrapper for rknn_context (NPU inference handle).
// On aarch64 rknn_context is uint64_t; on arm32 it is uint32_t.
// Move-only; calls rknn_destroy on destruction.
class UniqueRknnCtx {
 public:
  UniqueRknnCtx() = default;
  explicit UniqueRknnCtx(rknn_context ctx) noexcept : ctx_(ctx) {}

  UniqueRknnCtx(const UniqueRknnCtx&) = delete;
  UniqueRknnCtx& operator=(const UniqueRknnCtx&) = delete;

  UniqueRknnCtx(UniqueRknnCtx&& o) noexcept
      : ctx_(std::exchange(o.ctx_, 0)) {}
  UniqueRknnCtx& operator=(UniqueRknnCtx&& o) noexcept {
    if (this != &o) {
      reset();
      ctx_ = std::exchange(o.ctx_, 0);
    }
    return *this;
  }

  ~UniqueRknnCtx() { reset(); }

  [[nodiscard]] rknn_context get() const noexcept { return ctx_; }
  [[nodiscard]] bool valid() const noexcept { return ctx_ != 0; }

  // Destroy current context (if valid) and adopt new_ctx.
  void reset(rknn_context ctx = 0) noexcept {
    if (ctx_ != 0) rknn_destroy(ctx_);
    ctx_ = ctx;
  }

  // Release ownership without destroying.
  [[nodiscard]] rknn_context release() noexcept {
    return std::exchange(ctx_, 0);
  }

 private:
  rknn_context ctx_{0};
};

}  // namespace vlm_industrial::edge::common
