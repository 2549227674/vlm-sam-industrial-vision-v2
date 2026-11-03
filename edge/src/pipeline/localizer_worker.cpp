// edge/src/pipeline/localizer_worker.cpp
// Phase 10: T3 ORT CPU localizer via Python subprocess.

#include "edge/pipeline/localizer_worker.hpp"
#include "edge/common/unique_fd.hpp"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

namespace vlm_industrial::edge {

using std::chrono::steady_clock;
using std::chrono::duration;
using std::chrono::milliseconds;

static constexpr int kSubprocessTimeoutMs = 5000;

// ── Minimal JSON value extraction (no external dependency) ──────────────────

namespace {

// Extract a string value for a given key from a flat JSON object.
// Handles both "key":"val" and "key": "val" (optional space after colon).
// Returns empty string if key not found.
std::string json_str(const std::string& json, const char* key) {
  std::string needle = "\"";
  needle += key;
  needle += "\"";
  auto key_pos = json.find(needle);
  if (key_pos == std::string::npos) return {};
  auto colon = json.find(':', key_pos + needle.size());
  if (colon == std::string::npos) return {};
  auto quote = json.find('"', colon + 1);
  if (quote == std::string::npos) return {};
  auto end = json.find('"', quote + 1);
  if (end == std::string::npos) return {};
  return json.substr(quote + 1, end - quote - 1);
}

// Find the position just after "key": (with optional space).
// Returns std::string::npos if not found.
static size_t find_value_pos(const std::string& json, const char* key) {
  std::string needle = "\"";
  needle += key;
  needle += "\"";
  auto key_pos = json.find(needle);
  if (key_pos == std::string::npos) return std::string::npos;
  auto colon = json.find(':', key_pos + needle.size());
  if (colon == std::string::npos) return std::string::npos;
  // Skip optional whitespace after colon.
  size_t pos = colon + 1;
  while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t')) ++pos;
  return pos;
}

float json_float(const std::string& json, const char* key, float default_val) {
  auto pos = find_value_pos(json, key);
  if (pos == std::string::npos) return default_val;
  return std::strtof(json.c_str() + pos, nullptr);
}

int json_int(const std::string& json, const char* key, int default_val) {
  auto pos = find_value_pos(json, key);
  if (pos == std::string::npos) return default_val;
  return static_cast<int>(std::strtol(json.c_str() + pos, nullptr, 10));
}

bool json_bool(const std::string& json, const char* key, bool default_val) {
  auto pos = find_value_pos(json, key);
  if (pos == std::string::npos) return default_val;
  return json.compare(pos, 4, "true") == 0;
}

// Extract bboxes array from JSON. Simple parser for
// "bboxes":[{"x":0.1,"y":0.2,"w":0.3,"h":0.4}, ...]
std::vector<VlmReport::BBox> json_bboxes(const std::string& json) {
  std::vector<VlmReport::BBox> result;
  auto arr_start = json.find("\"bboxes\":[");
  if (arr_start == std::string::npos) return result;
  arr_start = json.find('[', arr_start);
  if (arr_start == std::string::npos) return result;

  size_t pos = arr_start + 1;
  while (pos < json.size()) {
    auto obj_start = json.find('{', pos);
    if (obj_start == std::string::npos) break;
    auto obj_end = json.find('}', obj_start);
    if (obj_end == std::string::npos) break;

    std::string obj = json.substr(obj_start, obj_end - obj_start + 1);
    VlmReport::BBox b;
    b.x = json_float(obj, "x", 0.0f);
    b.y = json_float(obj, "y", 0.0f);
    b.w = json_float(obj, "w", 0.0f);
    b.h = json_float(obj, "h", 0.0f);
    if (b.w > 0.0f && b.h > 0.0f) {
      result.push_back(b);
    }
    pos = obj_end + 1;
  }
  return result;
}

// Read a line from fd with timeout. Returns empty on timeout/error.
std::string read_line_timeout(int fd, int timeout_ms) {
  std::string line;
  line.reserve(512);

  auto deadline = steady_clock::now() + milliseconds(timeout_ms);

  while (steady_clock::now() < deadline) {
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(fd, &fds);

    struct timeval tv;
    auto remaining = deadline - steady_clock::now();
    auto rem_ms = std::chrono::duration_cast<milliseconds>(remaining).count();
    if (rem_ms <= 0) break;
    tv.tv_sec = rem_ms / 1000;
    tv.tv_usec = (rem_ms % 1000) * 1000;

    int sel = select(fd + 1, &fds, nullptr, nullptr, &tv);
    if (sel < 0) {
      if (errno == EINTR) continue;
      break;
    }
    if (sel == 0) continue;  // timeout for this iteration

    char c;
    ssize_t n = ::read(fd, &c, 1);
    if (n <= 0) break;  // EOF or error
    if (c == '\n') {
      if (!line.empty()) return line;
      continue;  // skip empty lines
    }
    line += c;
  }
  return line;
}

}  // namespace

// ── Constructor ─────────────────────────────────────────────────────────────

LocalizerWorker::LocalizerWorker(const common::Config& cfg,
                                 common::BoundedQueue<EadResult>& in,
                                 common::BoundedQueue<VlmReport>& out,
                                 common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), out_(out), m_(m) {}

// ── Subprocess management ───────────────────────────────────────────────────

bool LocalizerWorker::spawn_subprocess() {
  int stdin_pipe[2];   // parent writes to stdin_pipe[1], child reads from stdin_pipe[0]
  int stdout_pipe[2];  // child writes to stdout_pipe[1], parent reads from stdout_pipe[0]

  // Parent-side owners: any early return below closes all four ends.
  if (pipe(stdin_pipe) != 0) {
    std::fprintf(stderr, "[T3-ort] pipe() failed: %s\n", strerror(errno));
    return false;
  }
  common::UniqueFd stdin_rd(stdin_pipe[0]), stdin_wr(stdin_pipe[1]);
  if (pipe(stdout_pipe) != 0) {
    std::fprintf(stderr, "[T3-ort] pipe() failed: %s\n", strerror(errno));
    return false;
  }
  common::UniqueFd stdout_rd(stdout_pipe[0]), stdout_wr(stdout_pipe[1]);

  pid_t pid = fork();
  if (pid < 0) {
    std::fprintf(stderr, "[T3-ort] fork() failed: %s\n", strerror(errno));
    return false;
  }

  if (pid == 0) {
    // Child: redirect stdin/stdout.
    ::close(stdin_pipe[1]);
    ::close(stdout_pipe[0]);
    dup2(stdin_pipe[0], STDIN_FILENO);
    dup2(stdout_pipe[1], STDOUT_FILENO);
    ::close(stdin_pipe[0]);
    ::close(stdout_pipe[1]);

    // Build argv.
    std::string model = cfg_.localizer_model_path;
    std::string classes = cfg_.localizer_classes_path;
    std::string conf = std::to_string(cfg_.localizer_conf_thresh);
    std::string iou = std::to_string(cfg_.localizer_iou_thresh);
    std::string img_sz = std::to_string(cfg_.localizer_img_size);

    execlp("python3", "python3",
           cfg_.localizer_script_path.c_str(),
           "--model", model.c_str(),
           "--classes", classes.c_str(),
           "--conf", conf.c_str(),
           "--iou", iou.c_str(),
           "--img-size", img_sz.c_str(),
           nullptr);

    // If execlp returns, it failed.
    _exit(1);
  }

  // Parent: close child ends, keep ours.
  stdin_rd.reset();
  stdout_wr.reset();

  proc_stdin_fd_ = stdin_wr.release();
  proc_stdout_fd_ = stdout_rd.release();
  proc_pid_ = pid;

  // Read the "ready" line from Python.
  std::string ready = read_line_timeout(proc_stdout_fd_, 30000);
  if (ready.empty() || ready.find("\"ready\": true") == std::string::npos) {
    std::fprintf(stderr, "[T3-ort] subprocess did not send ready line: '%s'\n",
                 ready.c_str());
    kill_subprocess();
    return false;
  }

  std::fprintf(stderr, "[T3-ort] subprocess ready: %s\n", ready.c_str());
  return true;
}

void LocalizerWorker::kill_subprocess() {
  if (proc_stdin_fd_ >= 0) { ::close(proc_stdin_fd_); proc_stdin_fd_ = -1; }
  if (proc_stdout_fd_ >= 0) { ::close(proc_stdout_fd_); proc_stdout_fd_ = -1; }
  if (proc_pid_ > 0) {
    kill(proc_pid_, SIGTERM);
    waitpid(proc_pid_, nullptr, 0);
    proc_pid_ = -1;
  }
}

std::string LocalizerWorker::infer_one(const std::string& image_path) {
  if (proc_stdin_fd_ < 0 || proc_stdout_fd_ < 0) return {};

  // Write image path + newline to stdin.
  std::string msg = image_path + "\n";
  ssize_t written = ::write(proc_stdin_fd_, msg.c_str(), msg.size());
  if (written != static_cast<ssize_t>(msg.size())) {
    std::fprintf(stderr, "[T3-ort] write failed: %s\n", strerror(errno));
    return {};
  }

  // Read result line with timeout.
  return read_line_timeout(proc_stdout_fd_, kSubprocessTimeoutMs);
}

// ── Fallback report ─────────────────────────────────────────────────────────

VlmReport LocalizerWorker::make_fallback_report(const EadResult& ead,
                                                const char* reason) const {
  VlmReport r;
  r.image_path         = ead.image_path;
  r.device_id          = ead.device_id;
  r.line_id            = ead.line_id;
  r.category           = ead.category;
  r.defect_type        = "anomaly";
  r.severity           = "medium";
  r.confidence         = 0.0f;
  r.anomaly_score      = ead.final_score;
  r.variant            = "ort_fallback";
  r.frame_timestamp_us = ead.frame_timestamp_us;
  r.bboxes.push_back({0.3f, 0.3f, 0.4f, 0.4f});

  r.localization_source = "ort_fallback";
  r.label_source        = "template";
  r.observation_source  = "template";

  r.pipeline_ms.efficientad = ead.inference_ms;
  r.pipeline_ms.fastsam     = 0.0f;
  r.pipeline_ms.qwen3vl     = 0.0f;
  r.pipeline_ms.localizer   = 0.0f;
  r.pipeline_ms.upload      = 0.0f;

  r.vlm_metrics.json_parse_ok = false;

  std::fprintf(stderr, "[T3-ort] fallback | reason=%s\n", reason);
  return r;
}

// ── Parse JSON result ───────────────────────────────────────────────────────

VlmReport LocalizerWorker::parse_result(const EadResult& ead,
                                        const std::string& json) const {
  VlmReport r;
  r.image_path         = ead.image_path;
  r.device_id          = ead.device_id;
  r.line_id            = ead.line_id;
  r.category           = ead.category;
  r.frame_timestamp_us = ead.frame_timestamp_us;

  r.defect_type   = json_str(json, "defect_type");
  if (r.defect_type.empty()) r.defect_type = "anomaly";

  r.severity      = "medium";  // template default
  r.confidence    = json_float(json, "confidence", 0.0f);
  r.anomaly_score = ead.final_score;
  r.variant       = cfg_.localizer_backend + "_" + cfg_.vlm_model_size;

  r.bboxes = json_bboxes(json);
  if (r.bboxes.empty()) {
    r.bboxes.push_back({0.3f, 0.3f, 0.4f, 0.4f});
  }

  r.localization_source = cfg_.localizer_backend == "ort" ? "ort_yolov8n_cpu"
                                                          : "yolov8n_detect_rknn";
  r.label_source        = "yolo_class_head";
  r.observation_source  = "template";

  // Pipeline timing.
  float pre_ms  = json_float(json, "preprocess_ms", 0.0f);
  float inf_ms  = json_float(json, "inference_ms", 0.0f);
  float post_ms = json_float(json, "postprocess_ms", 0.0f);

  r.pipeline_ms.efficientad = ead.inference_ms;
  r.pipeline_ms.fastsam     = 0.0f;
  r.pipeline_ms.qwen3vl     = 0.0f;
  r.pipeline_ms.localizer   = pre_ms + inf_ms + post_ms;
  r.pipeline_ms.upload      = 0.0f;  // filled by T4

  // VLM metrics: not applicable (no VLM called).
  r.vlm_metrics.json_parse_ok = json_bool(json, "ok", false);
  r.vlm_metrics.ttft_ms       = 0.0f;
  r.vlm_metrics.decode_tps    = 0.0f;
  r.vlm_metrics.prompt_tokens = 0;
  r.vlm_metrics.output_tokens = 0;
  r.vlm_metrics.rss_mb        = 0.0f;

  // Trace events.
  float ts = 0.0f;
  r.trace_events.push_back(
      {"efficientad_infer", ts, ead.inference_ms * 1000.0f,
       "T2.pipeline", 'X', "pipeline"});
  ts += ead.inference_ms * 1000.0f;
  r.trace_events.push_back(
      {"localizer_preprocess", ts, pre_ms * 1000.0f,
       "T3.localizer", 'X', "localizer"});
  ts += pre_ms * 1000.0f;
  r.trace_events.push_back(
      {"localizer_infer", ts, inf_ms * 1000.0f,
       "T3.localizer", 'X', "localizer"});
  ts += inf_ms * 1000.0f;
  r.trace_events.push_back(
      {"localizer_postprocess", ts, post_ms * 1000.0f,
       "T3.localizer", 'X', "localizer"});

  return r;
}

// ── Main loop ───────────────────────────────────────────────────────────────

void LocalizerWorker::operator()(std::stop_token st) {
  std::fprintf(stderr, "[T3-ort] starting | backend=%s model=%s\n",
               cfg_.localizer_backend.c_str(),
               cfg_.localizer_model_path.c_str());

  if (!spawn_subprocess()) {
    std::fprintf(stderr, "[T3-ort] subprocess spawn failed, using fallback for all frames\n");
    while (!st.stop_requested()) {
      auto ead_opt = in_.pop(st);
      if (!ead_opt) break;
      out_.push_drop_oldest(make_fallback_report(*ead_opt, "spawn_failed"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
    }
    return;
  }

  uint64_t total_frames = 0;
  uint64_t fallback_frames = 0;
  uint64_t restart_count = 0;

  while (!st.stop_requested()) {
    auto ead_opt = in_.pop(st);
    if (!ead_opt) break;
    const auto& ead = *ead_opt;
    ++total_frames;

    auto t_frame = steady_clock::now();

    std::fprintf(stderr,
                 "[T3-ort] frame %zu | cat=%s | ead_score=%.3f\n",
                 static_cast<size_t>(ead.frame_id),
                 ead.category.c_str(),
                 ead.final_score);

    // Send image to subprocess.
    std::string result_json = infer_one(ead.image_path);

    if (result_json.empty()) {
      // Timeout or subprocess died — restart and fallback.
      std::fprintf(stderr, "[T3-ort] subprocess timeout/error, restarting\n");
      kill_subprocess();
      ++restart_count;

      out_.push_drop_oldest(make_fallback_report(ead, "subprocess_timeout"));
      m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
      ++fallback_frames;

      // Restart subprocess for next frame.
      if (!spawn_subprocess()) {
        std::fprintf(stderr, "[T3-ort] restart failed\n");
      }
      continue;
    }

    // Parse result.
    bool ok = json_bool(result_json, "ok", false);
    VlmReport report;

    if (ok) {
      report = parse_result(ead, result_json);
    } else {
      std::string err = json_str(result_json, "error");
      std::fprintf(stderr, "[T3-ort] inference error: %s\n", err.c_str());
      report = make_fallback_report(ead, "inference_error");
      ++fallback_frames;
    }

    float total_ms = duration<float, std::milli>(
        steady_clock::now() - t_frame).count();

    std::fprintf(stderr,
                 "     defect_type=%s conf=%.3f bboxes=%zu total_ms=%.1f\n",
                 report.defect_type.c_str(),
                 report.confidence,
                 report.bboxes.size(),
                 total_ms);

    out_.push_drop_oldest(std::move(report));
    m_.vlm_count.fetch_add(1, std::memory_order_relaxed);
  }

  // Shutdown: tell subprocess to exit.
  if (proc_stdin_fd_ >= 0) {
    const char* exit_cmd = "__EXIT__\n";
    ::write(proc_stdin_fd_, exit_cmd, strlen(exit_cmd));
  }
  kill_subprocess();

  std::fprintf(stderr,
               "[T3-ort] stopped | total=%zu fallback=%zu restarts=%zu\n",
               static_cast<size_t>(total_frames),
               static_cast<size_t>(fallback_frames),
               static_cast<size_t>(restart_count));
}

}  // namespace vlm_industrial::edge
