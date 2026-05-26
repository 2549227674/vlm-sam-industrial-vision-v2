#include "edge/upload/upload_worker.hpp"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>

namespace vlm_industrial::edge {

UploadWorker::UploadWorker(const common::Config& cfg,
                           common::BoundedQueue<VlmReport>& in,
                           common::PipelineMetrics& m)
    : cfg_(cfg), in_(in), m_(m) {}

std::string UploadWorker::build_meta_json(const VlmReport& r) {
  // Build JSON matching DefectCreate in docs/API_CONTRACT.md.
  std::string j;
  j.reserve(1024);
  j = "{";

  // string fields
  auto str = [&](const char* key, const std::string& val) {
    j += "\""; j += key; j += "\":\"";
    // Escape any embedded quotes in val (defensive).
    for (char c : val) {
      if (c == '"') j += "\\\"";
      else if (c == '\\') j += "\\\\";
      else j += c;
    }
    j += "\",";
  };

  auto num = [&](const char* key, auto val) {
    j += "\""; j += key; j += "\":";
    // Format with enough precision for floats.
    char buf[32];
    if constexpr (std::is_floating_point_v<decltype(val)>) {
      std::snprintf(buf, sizeof(buf), "%.6g", static_cast<double>(val));
    } else {
      std::snprintf(buf, sizeof(buf), "%d", static_cast<int>(val));
    }
    j += buf;
    j += ",";
  };

  auto bl = [&](const char* key, bool val) {
    j += "\""; j += key; j += "\":";
    j += val ? "true" : "false";
    j += ",";
  };

  // ISO 8601 timestamp from frame_timestamp_us (steady_clock → relative).
  // Use edge_ts as a placeholder since we don't have wall clock.
  auto make_iso_ts = [](int64_t us) -> std::string {
    auto dur = std::chrono::microseconds(us);
    auto tp = std::chrono::system_clock::time_point(
        std::chrono::duration_cast<std::chrono::system_clock::duration>(dur));
    auto tt = std::chrono::system_clock::to_time_t(tp);
    std::tm utc{};
    gmtime_r(&tt, &utc);
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02dZ",
                  utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday,
                  utc.tm_hour, utc.tm_min, utc.tm_sec);
    return buf;
  };

  // -- top-level fields --
  str("line_id",      r.line_id);
  str("category",     r.category);
  str("defect_type",  r.defect_type);
  str("severity",     r.severity);
  num("confidence",   r.confidence);
  num("anomaly_score", r.anomaly_score);

  // bboxes array
  j += "\"bboxes\":[";
  for (std::size_t i = 0; i < r.bboxes.size(); ++i) {
    auto& b = r.bboxes[i];
    char buf[128];
    std::snprintf(buf, sizeof(buf),
                  "{\"x\":%.4f,\"y\":%.4f,\"w\":%.4f,\"h\":%.4f}",
                  b.x, b.y, b.w, b.h);
    if (i > 0) j += ",";
    j += buf;
  }
  j += "],";

  str("description", "");  // empty for mock
  str("variant",     r.variant);

  // edge_ts
  j += "\"edge_ts\":\"";
  j += make_iso_ts(r.frame_timestamp_us);
  j += "\",";

  // pipeline_ms (v1.3: include localizer and upload stages)
  j += "\"pipeline_ms\":{";
  char buf[64];
  std::snprintf(buf, sizeof(buf), "%.1f", r.pipeline_ms.efficientad);
  j += "\"efficientad\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%.1f", r.pipeline_ms.fastsam);
  j += "\"fastsam\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%.1f", r.pipeline_ms.qwen3vl);
  j += "\"qwen3vl\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%.1f", r.pipeline_ms.localizer);
  j += "\"localizer\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%.1f", r.pipeline_ms.upload);
  j += "\"upload\":"; j += buf;
  j += "},";

  // vlm_metrics
  j += "\"vlm_metrics\":{";
  std::snprintf(buf, sizeof(buf), "%.1f", r.vlm_metrics.ttft_ms);
  j += "\"ttft_ms\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%.1f", r.vlm_metrics.decode_tps);
  j += "\"decode_tps\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%d", r.vlm_metrics.prompt_tokens);
  j += "\"prompt_tokens\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%d", r.vlm_metrics.output_tokens);
  j += "\"output_tokens\":"; j += buf; j += ",";
  std::snprintf(buf, sizeof(buf), "%.1f", r.vlm_metrics.rss_mb);
  j += "\"rss_mb\":"; j += buf; j += ",";
  bl("json_parse_ok", r.vlm_metrics.json_parse_ok);
  // Remove trailing comma from bl and close.
  if (j.back() == ',') j.pop_back();
  j += "},";

  // trace_events
  j += "\"trace_events\":[";
  for (std::size_t i = 0; i < r.trace_events.size(); ++i) {
    auto& te = r.trace_events[i];
    if (i > 0) j += ",";
    j += "{";
    str("name", te.name);
    std::snprintf(buf, sizeof(buf), "%.1f", te.ts);
    j += "\"ts\":"; j += buf; j += ",";
    std::snprintf(buf, sizeof(buf), "%.1f", te.dur);
    j += "\"dur\":"; j += buf; j += ",";
    str("tid", te.tid);
    j += "\"ph\":\"X\",";
    str("cat", te.cat);
    // Remove trailing comma.
    if (j.back() == ',') j.pop_back();
    j += "}";
  }
  j += "],";

  // v1.3 optional source tracking fields (only when non-empty).
  if (!r.localization_source.empty()) {
    str("localization_source", r.localization_source);
  }
  if (!r.label_source.empty()) {
    str("label_source", r.label_source);
  }
  if (!r.observation_source.empty()) {
    str("observation_source", r.observation_source);
  }

  // schema_version (remains "v1"; v1.3 fields are optional additions).
  j += "\"schema_version\":\"v1\"";

  // Remove trailing comma if any.
  if (j.back() == ',') j.pop_back();
  j += "}";

  return j;
}

void UploadWorker::operator()(std::stop_token st) {
  std::string upload_url = cfg_.backend_url + "/api/edge/report";
  std::fprintf(stderr, "[T4] uploading to %s\n", upload_url.c_str());

  while (!st.stop_requested()) {
    auto report_opt = in_.pop(st);
    if (!report_opt) break;  // stop requested

    auto& report = *report_opt;

    std::string meta_json = build_meta_json(report);

    // Append upload trace event placeholder to existing trace_events array.
    {
      // Find "trace_events":[ in the JSON and insert before the closing ].
      auto te_key = meta_json.rfind("\"trace_events\":[");
      if (te_key != std::string::npos) {
        // Find the matching ']' for the array.
        size_t arr_start = te_key + strlen("\"trace_events\":[");
        int depth = 1;
        size_t pos = arr_start;
        while (pos < meta_json.size() && depth > 0) {
          if (meta_json[pos] == '[') ++depth;
          else if (meta_json[pos] == ']') --depth;
          if (depth > 0) ++pos;
        }
        // pos now points to closing ']'.
        if (depth == 0) {
          std::string te = ",{\"name\":\"upload\",\"ts\":0.0,"
                           "\"dur\":0.0,\"tid\":\"T4.upload\","
                           "\"ph\":\"X\",\"cat\":\"upload\"}";
          meta_json.insert(pos, te);
        }
      }
    }

    // Log meta JSON for the first frame (verify construction).
    static bool first_frame = true;
    if (first_frame) {
      std::fprintf(stderr, "[T4] meta JSON (frame 0): %s\n",
                   meta_json.c_str());
      first_frame = false;
    }

    // Time the upload.
    auto t_upload_start = std::chrono::steady_clock::now();
    long status = http_.post_report(
        upload_url,
        report.image_path,
        meta_json,
        cfg_.upload_max_retries,
        cfg_.upload_timeout_s);
    float upload_ms = std::chrono::duration<float, std::milli>(
        std::chrono::steady_clock::now() - t_upload_start).count();

    // Record upload time in the report (for pipeline_ms.upload).
    // Note: this is after the fact, but the upload_ms is logged for observability.

    if (status == 200) {
      m_.upload_count.fetch_add(1, std::memory_order_relaxed);
    } else {
      m_.upload_failed.fetch_add(1, std::memory_order_relaxed);
      std::fprintf(stderr, "[T4] upload failed: HTTP %ld (frame from %s)\n",
                   status, report.category.c_str());
    }
    std::fprintf(stderr, "[T4] upload_ms=%.1f\n", upload_ms);
  }

  std::fprintf(stderr, "[T4] stopped\n");
}

}  // namespace vlm_industrial::edge
