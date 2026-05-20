#pragma once

#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>
#include <stop_token>

namespace vlm_industrial::edge::common {

// Thread-safe bounded queue with drop-oldest back-pressure.
// Q1/Q3 capacity 4, Q2 capacity 2 (see ARCHITECTURE.md  3.1).
template <class T>
class BoundedQueue {
 public:
  explicit BoundedQueue(std::size_t cap) : cap_(cap) {}

  // Push an item; if at capacity, drop the oldest and increment dropped_count.
  void push_drop_oldest(T v) {
    {
      std::scoped_lock lk(mu_);
      if (q_.size() >= cap_) {
        q_.pop_front();
        ++dropped_;
      }
      q_.push_back(std::move(v));
    }
    cv_.notify_one();
  }

  // Blocking pop with cooperative cancellation via stop_token.
  // Returns std::nullopt if stop was requested before an item was available.
  [[nodiscard]] std::optional<T> pop(std::stop_token st) {
    std::unique_lock lk(mu_);
    if (!cv_.wait(lk, st, [&] { return !q_.empty(); })) {
      return std::nullopt;
    }
    T v = std::move(q_.front());
    q_.pop_front();
    return v;
  }

  [[nodiscard]] std::size_t size() const noexcept {
    std::scoped_lock lk(mu_);
    return q_.size();
  }

  [[nodiscard]] std::size_t capacity() const noexcept { return cap_; }

  [[nodiscard]] std::size_t dropped() const noexcept {
    std::scoped_lock lk(mu_);
    return dropped_;
  }

 private:
  std::deque<T> q_;
  mutable std::mutex mu_;
  std::condition_variable_any cv_;
  const std::size_t cap_;
  std::size_t dropped_{0};
};

}  // namespace vlm_industrial::edge::common
