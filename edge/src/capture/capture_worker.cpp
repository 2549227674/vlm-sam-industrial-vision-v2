#include "edge/capture/capture_worker.hpp"

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <random>
#include <thread>

namespace fs = std::filesystem;

namespace vlm_industrial::edge {

CaptureWorker::CaptureWorker(const common::Config& cfg,
                             common::BoundedQueue<CaptureFrame>& out,
                             common::PipelineMetrics& m)
    : cfg_(cfg), out_(out), m_(m) {}

void CaptureWorker::scan_category(const std::string& category) {
  // MVTec layout: {image_loop_dir}/{category}/test/
  fs::path test_dir = fs::path(cfg_.image_loop_dir) / category / "test";
  if (!fs::is_directory(test_dir)) {
    std::fprintf(stderr, "[T1] skip category '%s': %s not found\n",
                 category.c_str(), test_dir.c_str());
    return;
  }

  std::vector<std::string> paths;
  for (auto& entry : fs::recursive_directory_iterator(test_dir)) {
    if (!entry.is_regular_file()) continue;
    auto ext = entry.path().extension().string();
    // lowercase
    for (auto& c : ext) c = static_cast<char>(std::tolower(c));
    if (ext == ".jpg" || ext == ".jpeg" || ext == ".png") {
      paths.push_back(entry.path().string());
    }
  }

  if (paths.empty()) {
    std::fprintf(stderr, "[T1] skip category '%s': no images in %s\n",
                 category.c_str(), test_dir.c_str());
    return;
  }

  catalog_.emplace_back(category, std::move(paths));
}

void CaptureWorker::operator()(std::stop_token st) {
  // Pre-scan all categories.
  for (const auto& cat : cfg_.image_loop_categories) {
    scan_category(cat);
  }

  if (catalog_.empty()) {
    std::fprintf(stderr, "[T1] no images found in any category, exiting\n");
    return;
  }

  // Count total images.
  std::size_t total = 0;
  for (auto& [_, v] : catalog_) total += v.size();
  std::fprintf(stderr, "[T1] scanned %zu images across %zu categories\n",
               total, catalog_.size());

  // Per-thread RNG for jitter.
  thread_local std::mt19937 rng{std::random_device{}()};

  while (!st.stop_requested()) {
    auto& [category, paths] = catalog_[cat_idx_];
    const auto& img_path = paths[img_idx_];

    // Build CaptureFrame.
    CaptureFrame frame;
    frame.image_path  = img_path;
    frame.category    = category;
    frame.device_id   = cfg_.device_id;
    frame.line_id     = cfg_.line_id;
    frame.frame_id    = frame_counter_++;
    frame.timestamp_us =
        std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count();

    out_.push_drop_oldest(std::move(frame));
    m_.capture_count.fetch_add(1, std::memory_order_relaxed);

    // Advance to next image, wrapping around.
    ++img_idx_;
    if (img_idx_ >= paths.size()) {
      img_idx_ = 0;
      cat_idx_ = (cat_idx_ + 1) % catalog_.size();
    }

    // Sleep for beat + jitter.
    int jitter_range = cfg_.image_loop_jitter_ms;
    std::uniform_int_distribution<int> dist(-jitter_range, jitter_range);
    int sleep_ms = cfg_.image_loop_beat_ms + dist(rng);
    if (sleep_ms < 100) sleep_ms = 100;  // floor

    auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::milliseconds(sleep_ms);
    while (!st.stop_requested() &&
           std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
  }

  std::fprintf(stderr, "[T1] stopped after %zu frames\n",
               static_cast<std::size_t>(frame_counter_));
}

}  // namespace vlm_industrial::edge
