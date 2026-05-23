// edge/tests/test_vlm_watchdog.cpp
// Standalone x86 unit test for VLM JSON watchdog repeated-pattern detection.
// Compile: g++ -std=c++20 -O2 -o test_vlm_watchdog test_vlm_watchdog.cpp
// Run:     ./test_vlm_watchdog

#include <cassert>
#include <cstdio>
#include <string>
#include <string_view>

// Replicate the watchdog functions from qwen3vl_runner.cpp (no RKNN dependency).
static bool detect_repeated_chars(const std::string& s, int limit) {
  if (static_cast<int>(s.size()) < limit) return false;
  char last = s.back();
  int run = 1;
  for (int i = static_cast<int>(s.size()) - 2; i >= 0 && run < limit; --i) {
    if (s[i] == last) ++run;
    else break;
  }
  return run >= limit;
}

static bool detect_repeated_ngram(const std::string& s, int limit) {
  int window = limit * 2;
  if (static_cast<int>(s.size()) < window) return false;
  std::string_view tail{s.data() + s.size() - window, static_cast<size_t>(window)};
  for (int ngram_len = 1; ngram_len <= 16; ++ngram_len) {
    if (ngram_len > static_cast<int>(tail.size()) / 2) break;
    std::string_view ngram{tail.data(), static_cast<size_t>(ngram_len)};
    int repeats = 1;
    for (size_t pos = ngram_len; pos + ngram_len <= tail.size(); pos += ngram_len) {
      if (tail.substr(pos, ngram_len) == ngram) ++repeats;
      else break;
    }
    if (repeats >= limit / ngram_len) return true;
  }
  return false;
}

void test_repeated_char_detect() {
  // Short string — no detection.
  assert(!detect_repeated_chars("hello", 64));

  // Exactly at limit.
  std::string s(64, ']');
  assert(detect_repeated_chars(s, 64));

  // Just under limit.
  std::string s2(63, ']');
  assert(!detect_repeated_chars(s2, 64));

  // With prefix text.
  std::string s3 = "{\"key\": \"value\"";
  s3.append(64, '}');
  assert(detect_repeated_chars(s3, 64));

  std::fprintf(stderr, "PASS: test_repeated_char_detect\n");
}

void test_repeated_ngram_detect() {
  // Short string — no detection.
  assert(!detect_repeated_ngram("abc", 32));

  // Repeated bracket pair: "]]]]..." with limit 32.
  // ngram_len=1, ']' repeated 64 times.
  std::string s(64, ']');
  assert(detect_repeated_ngram(s, 32));

  // Repeated 2-char pattern: "ababab..."
  std::string s2;
  for (int i = 0; i < 32; ++i) s2 += "ab";
  assert(detect_repeated_ngram(s2, 32));

  // Repeated 3-char pattern: "xyz" * 32
  std::string s3;
  for (int i = 0; i < 32; ++i) s3 += "xyz";
  assert(detect_repeated_ngram(s3, 32));

  // Not repeated — alternating.
  std::string s4;
  for (int i = 0; i < 64; ++i) s4 += (i % 2 == 0) ? '[' : ']';
  // This should be detected as ngram "[]" repeated 32 times.
  assert(detect_repeated_ngram(s4, 32));

  // JSON-like with normal content — no false positive.
  std::string s5 = R"({"category":"bottle","defect_type":"scratch","severity":"medium","confidence":0.85})";
  assert(!detect_repeated_ngram(s5, 32));

  std::fprintf(stderr, "PASS: test_repeated_ngram_detect\n");
}

void test_empty_and_short() {
  assert(!detect_repeated_chars("", 64));
  assert(!detect_repeated_chars("a", 64));
  assert(!detect_repeated_ngram("", 32));
  assert(!detect_repeated_ngram("abc", 32));

  std::fprintf(stderr, "PASS: test_empty_and_short\n");
}

void test_mixed_content_with_tail_repetition() {
  // Good JSON followed by bracket spam.
  std::string s = R"({"category":"pill","defect_type":"anomaly","severity":"low"})";
  s.append(80, ']');
  assert(detect_repeated_chars(s, 64));
  assert(detect_repeated_ngram(s, 32));

  std::fprintf(stderr, "PASS: test_mixed_content_with_tail_repetition\n");
}

int main() {
  test_repeated_char_detect();
  test_repeated_ngram_detect();
  test_empty_and_short();
  test_mixed_content_with_tail_repetition();

  std::fprintf(stderr, "\nAll VLM watchdog tests PASSED.\n");
  return 0;
}
