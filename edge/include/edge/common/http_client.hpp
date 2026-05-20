#pragma once

#include <curl/curl.h>
#include <string>
#include <string_view>
#include <utility>

namespace vlm_industrial::edge::common {

// libcurl HTTP client for T4 Upload.
// Each Upload thread owns one instance; NOT thread-safe (CURL easy handle).
// curl_global_init MUST be called once in main() before constructing.
class HttpClient {
 public:
  HttpClient();
  ~HttpClient();

  HttpClient(const HttpClient&) = delete;
  HttpClient& operator=(const HttpClient&) = delete;
  HttpClient(HttpClient&& o) noexcept : curl_(std::exchange(o.curl_, nullptr)) {}
  HttpClient& operator=(HttpClient&& o) noexcept {
    if (this != &o) {
      if (curl_) curl_easy_cleanup(curl_);
      curl_ = std::exchange(o.curl_, nullptr);
    }
    return *this;
  }

  // POST multipart (image file + meta JSON) to url.
  // Returns HTTP status code (200 = success).
  // Retries up to max_retries times with exponential back-off.
  long post_report(std::string_view url,
                   const std::string& image_path,
                   const std::string& meta_json,
                   int max_retries = 5,
                   int timeout_s = 30);

 private:
  CURL* curl_{nullptr};
};

}  // namespace vlm_industrial::edge::common
