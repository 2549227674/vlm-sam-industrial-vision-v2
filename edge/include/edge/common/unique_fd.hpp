#pragma once

#include <unistd.h>

#include <utility>

namespace vlm_industrial::edge::common {

// RAII wrapper for POSIX file descriptors (dma_buf fd, V4L2 fd, etc.).
// Move-only; closes fd on destruction.
class UniqueFd {
 public:
  UniqueFd() = default;
  explicit UniqueFd(int fd) noexcept : fd_(fd) {}

  UniqueFd(const UniqueFd&) = delete;
  UniqueFd& operator=(const UniqueFd&) = delete;

  UniqueFd(UniqueFd&& o) noexcept : fd_(std::exchange(o.fd_, -1)) {}
  UniqueFd& operator=(UniqueFd&& o) noexcept {
    if (this != &o) {
      reset();
      fd_ = std::exchange(o.fd_, -1);
    }
    return *this;
  }

  ~UniqueFd() { reset(); }

  [[nodiscard]] int get() const noexcept { return fd_; }
  [[nodiscard]] bool valid() const noexcept { return fd_ >= 0; }

  // Close current fd (if valid) and adopt new_fd.
  void reset(int fd = -1) noexcept {
    if (fd_ >= 0) ::close(fd_);
    fd_ = fd;
  }

  // Release ownership without closing.
  [[nodiscard]] int release() noexcept { return std::exchange(fd_, -1); }

 private:
  int fd_{-1};
};

}  // namespace vlm_industrial::edge::common
