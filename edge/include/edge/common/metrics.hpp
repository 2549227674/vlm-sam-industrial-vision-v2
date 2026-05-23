#pragma once

#include <atomic>
#include <cstdint>
#include <new>

namespace vlm_industrial::edge::common {

// Fixed at 64 bytes: correct for RK3588 Cortex-A76/A55 and x86-64.
// (std::hardware_destructive_interference_size varies per -mtune, avoid ABI issues.)
inline constexpr std::size_t kCacheLine = 64;

// Global pipeline counters; each atomic on its own cache line to prevent
// false sharing between T1-T4.
struct PipelineMetrics {
  // Per-stage frame counts.
  alignas(kCacheLine) std::atomic<uint64_t> capture_count{};
  alignas(kCacheLine) std::atomic<uint64_t> ead_count{};
  alignas(kCacheLine) std::atomic<uint64_t> vlm_count{};
  alignas(kCacheLine) std::atomic<uint64_t> upload_count{};
  alignas(kCacheLine) std::atomic<uint64_t> dropped_count{};

  // Upload retry/fail.
  alignas(kCacheLine) std::atomic<uint64_t> upload_retry{};
  alignas(kCacheLine) std::atomic<uint64_t> upload_failed{};

  // T2 gate.
  alignas(kCacheLine) std::atomic<uint64_t> ead_gate_pass{};
  alignas(kCacheLine) std::atomic<uint64_t> ead_gate_drop{};

  // VLM JSON watchdog aborts.
  alignas(kCacheLine) std::atomic<uint64_t> vlm_watchdog_abort{};

  // Queue Q1 (T1→T2) metrics.
  alignas(kCacheLine) std::atomic<uint64_t> q1_push{};
  alignas(kCacheLine) std::atomic<uint64_t> q1_pop{};
  alignas(kCacheLine) std::atomic<uint64_t> q1_drop{};
  alignas(kCacheLine) std::atomic<uint64_t> q1_high_watermark{};

  // Queue Q2 (T2→T3) metrics.
  alignas(kCacheLine) std::atomic<uint64_t> q2_push{};
  alignas(kCacheLine) std::atomic<uint64_t> q2_pop{};
  alignas(kCacheLine) std::atomic<uint64_t> q2_drop{};
  alignas(kCacheLine) std::atomic<uint64_t> q2_high_watermark{};

  // Queue Q3 (T3→T4) metrics.
  alignas(kCacheLine) std::atomic<uint64_t> q3_push{};
  alignas(kCacheLine) std::atomic<uint64_t> q3_pop{};
  alignas(kCacheLine) std::atomic<uint64_t> q3_drop{};
  alignas(kCacheLine) std::atomic<uint64_t> q3_high_watermark{};
};

}  // namespace vlm_industrial::edge::common
