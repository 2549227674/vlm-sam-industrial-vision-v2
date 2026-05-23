#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>
#include <stop_token>

namespace vlm_industrial::edge::common {

// Per-queue runtime metrics (optional, passed by caller).
struct QueueStats {
  std::atomic<uint64_t> push_count{0};
  std::atomic<uint64_t> pop_count{0};
  std::atomic<uint64_t> drop_count{0};
  std::atomic<uint64_t> high_watermark{0};

  void record_push(std::size_t depth) {
    push_count.fetch_add(1, std::memory_order_relaxed);
    update_high_watermark(depth);
  }

  void record_pop() {
    pop_count.fetch_add(1, std::memory_order_relaxed);
  }

  void record_drop() {
    drop_count.fetch_add(1, std::memory_order_relaxed);
  }

  void update_high_watermark(std::size_t depth) {
    auto prev = high_watermark.load(std::memory_order_relaxed);
    while (depth > prev &&
           !high_watermark.compare_exchange_weak(prev, depth,
                                                 std::memory_order_relaxed)) {
    }
  }
};

// Thread-safe bounded queue with drop-oldest back-pressure.
// Q1/Q3 capacity 4, Q2 capacity 2 (see ARCHITECTURE.md §3.1).
template <class T>
class BoundedQueue {
 public:
  explicit BoundedQueue(std::size_t cap, QueueStats* stats = nullptr)
      : cap_(cap), stats_(stats) {}

  // Push an item; if at capacity, drop the oldest and increment dropped_count.
  void push_drop_oldest(T v) {
    {
      std::scoped_lock lk(mu_);
      if (q_.size() >= cap_) {
        q_.pop_front();
        ++dropped_;
        if (stats_) stats_->record_drop();
      }
      q_.push_back(std::move(v));
      if (stats_) stats_->record_push(q_.size());
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
    if (stats_) stats_->record_pop();
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
  QueueStats* stats_;  // optional, owned by caller
};

}  // namespace vlm_industrial::edge::common
