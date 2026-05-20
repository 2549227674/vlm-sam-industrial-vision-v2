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
  alignas(kCacheLine) std::atomic<uint64_t> capture_count{};
  alignas(kCacheLine) std::atomic<uint64_t> ead_count{};
  alignas(kCacheLine) std::atomic<uint64_t> vlm_count{};
  alignas(kCacheLine) std::atomic<uint64_t> upload_count{};
  alignas(kCacheLine) std::atomic<uint64_t> dropped_count{};
  alignas(kCacheLine) std::atomic<uint64_t> upload_retry{};
  alignas(kCacheLine) std::atomic<uint64_t> upload_failed{};
};

}  // namespace vlm_industrial::edge::common
