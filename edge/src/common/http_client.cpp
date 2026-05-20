#include "edge/common/http_client.hpp"

#include <cstdlib>
#include <string>
#include <thread>

namespace vlm_industrial::edge::common {

HttpClient::HttpClient() {
  // curl_global_init MUST be called once in main() before any HttpClient
  // is constructed. We only create the per-thread easy handle here.
  curl_ = curl_easy_init();
}

HttpClient::~HttpClient() {
  if (curl_) curl_easy_cleanup(curl_);
}

long HttpClient::post_report(std::string_view url,
                             const std::string& image_path,
                             const std::string& meta_json,
                             int max_retries,
                             int timeout_s) {
  curl_easy_reset(curl_);

  // URL
  std::string url_str{url};
  curl_easy_setopt(curl_, CURLOPT_URL, url_str.c_str());
  curl_easy_setopt(curl_, CURLOPT_CONNECTTIMEOUT_MS, 3000L);
  curl_easy_setopt(curl_, CURLOPT_TIMEOUT_MS,
                   static_cast<long>(timeout_s) * 1000L);
  curl_easy_setopt(curl_, CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_2TLS);
  curl_easy_setopt(curl_, CURLOPT_NOSIGNAL, 1L);  // required for multi-thread

  // Build multipart form: image file + meta JSON.
  curl_mime* mime = curl_mime_init(curl_);

  auto* img_part = curl_mime_addpart(mime);
  curl_mime_name(img_part, "image");
  curl_mime_filedata(img_part, image_path.c_str());
  curl_mime_type(img_part, "image/jpeg");

  auto* meta_part = curl_mime_addpart(mime);
  curl_mime_name(meta_part, "meta");
  curl_mime_data(meta_part, meta_json.data(), meta_json.size());
  curl_mime_type(meta_part, "application/json");

  curl_easy_setopt(curl_, CURLOPT_MIMEPOST, mime);

  long status = 0;
  for (int attempt = 0; attempt < max_retries; ++attempt) {
    CURLcode rc = curl_easy_perform(curl_);
    curl_easy_getinfo(curl_, CURLINFO_RESPONSE_CODE, &status);

    bool should_retry =
        (rc == CURLE_OPERATION_TIMEDOUT) ||
        (rc == CURLE_COULDNT_CONNECT) ||
        (status == 408 || status == 429 ||
         (status >= 500 && status < 600));

    if (!should_retry) break;

    // Exponential back-off: 500ms * 2^attempt + jitter.
    auto delay_ms =
        (1 << attempt) * 500 + (std::rand() % 250);  // NOLINT rand()
    std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
  }

  curl_mime_free(mime);
  return status;
}

}  // namespace vlm_industrial::edge::common
