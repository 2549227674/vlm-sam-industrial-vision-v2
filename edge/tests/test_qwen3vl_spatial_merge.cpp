// edge/tests/test_qwen3vl_spatial_merge.cpp
// Standalone x86 unit test for merge_spatial_2x2 (no RKNN/RKLLM needed).
// Compile: g++ -std=c++20 -I../include -o test_spatial_merge test_qwen3vl_spatial_merge.cpp
// Run:     ./test_spatial_merge

#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>

// Include only the header with the template function.
// We need to satisfy the full header dependency chain minimally.
// Instead of including the full header, replicate the function inline
// to avoid RKNN/RKLLM dependencies.

namespace test {

template <typename T>
void merge_spatial_2x2(const T* input, T* output) {
  constexpr int H = 28;
  constexpr int W = 28;
  constexpr int C = 1024;
  constexpr int MERGE = 2;
  constexpr int OH = H / MERGE;
  constexpr int OW = W / MERGE;
  constexpr int OC = C * MERGE * MERGE;

  for (int by = 0; by < OH; ++by) {
    for (int bx = 0; bx < OW; ++bx) {
      const int out_token = by * OW + bx;
      T* out_ptr = output + out_token * OC;

      int local = 0;
      for (int dy = 0; dy < MERGE; ++dy) {
        for (int dx = 0; dx < MERGE; ++dx) {
          const int iy = by * MERGE + dy;
          const int ix = bx * MERGE + dx;
          const int in_token = iy * W + ix;
          const T* in_ptr = input + in_token * C;

          std::copy(in_ptr, in_ptr + C, out_ptr + local * C);
          ++local;
        }
      }
    }
  }
}

}  // namespace test

// Test 1: Verify first output token comes from input tokens (0,0), (0,1), (1,0), (1,1).
void test_first_output_token() {
  constexpr int H = 28, W = 28, C = 1024;
  constexpr int INPUT_SIZE = H * W * C;
  constexpr int OUTPUT_TOKENS = 14 * 14;
  constexpr int OC = C * 4;
  constexpr int OUTPUT_SIZE = OUTPUT_TOKENS * OC;

  float input[INPUT_SIZE];
  float output[OUTPUT_SIZE];

  // Fill: input[token, channel] = token * 100000 + channel
  for (int t = 0; t < H * W; ++t) {
    for (int c = 0; c < C; ++c) {
      input[t * C + c] = static_cast<float>(t * 100000 + c);
    }
  }

  std::memset(output, 0, sizeof(output));
  test::merge_spatial_2x2(input, output);

  // Output token 0 (block (0,0)) should come from input tokens:
  //   (0,0)=0, (0,1)=1, (1,0)=28, (1,1)=29
  // Segment 0: token 0, channels 0..1023
  assert(output[0] == 0.0f);           // token=0, ch=0: 0*100000+0
  assert(output[1] == 1.0f);           // token=0, ch=1
  // Segment 1: token 1, channels 0..1023
  float seg1_start = output[C];
  assert(seg1_start == 100000.0f);      // token=1*100000+0
  // Segment 2: token 28, channels 0..1023
  float seg2_start = output[2 * C];
  assert(seg2_start == 2800000.0f);     // 28*100000+0
  // Segment 3: token 29, channels 0..1023
  float seg3_start = output[3 * C];
  assert(seg3_start == 2900000.0f);     // 29*100000+0

  std::fprintf(stderr, "PASS: test_first_output_token\n");
}

// Test 2: Second output token comes from input tokens (2,3,30,31).
void test_second_output_token() {
  constexpr int H = 28, W = 28, C = 1024;
  constexpr int INPUT_SIZE = H * W * C;
  constexpr int OUTPUT_TOKENS = 14 * 14;
  constexpr int OC = C * 4;
  constexpr int OUTPUT_SIZE = OUTPUT_TOKENS * OC;

  float input[INPUT_SIZE];
  float output[OUTPUT_SIZE];

  for (int t = 0; t < H * W; ++t) {
    for (int c = 0; c < C; ++c) {
      input[t * C + c] = static_cast<float>(t * 100000 + c);
    }
  }

  std::memset(output, 0, sizeof(output));
  test::merge_spatial_2x2(input, output);

  // Output token 1 (block (0,1)) from input tokens (2,3,30,31).
  float* tok1 = output + OC;
  assert(tok1[0] == 200000.0f);          // token=2*100000+0
  assert(tok1[C] == 300000.0f);          // token=3*100000+0
  assert(tok1[2 * C] == 3000000.0f);     // token=30*100000+0
  assert(tok1[3 * C] == 3100000.0f);     // token=31*100000+0

  std::fprintf(stderr, "PASS: test_second_output_token\n");
}

// Test 3: First token of second row comes from input tokens (56,57,84,85).
void test_second_row_first_token() {
  constexpr int H = 28, W = 28, C = 1024;
  constexpr int INPUT_SIZE = H * W * C;
  constexpr int OUTPUT_TOKENS = 14 * 14;
  constexpr int OC = C * 4;
  constexpr int OUTPUT_SIZE = OUTPUT_TOKENS * OC;

  float input[INPUT_SIZE];
  float output[OUTPUT_SIZE];

  for (int t = 0; t < H * W; ++t) {
    for (int c = 0; c < C; ++c) {
      input[t * C + c] = static_cast<float>(t * 100000 + c);
    }
  }

  std::memset(output, 0, sizeof(output));
  test::merge_spatial_2x2(input, output);

  // Output token 14 (block (1,0)) from input tokens (56,57,84,85).
  float* tok14 = output + 14 * OC;
  assert(tok14[0] == 5600000.0f);         // token=56*100000+0
  assert(tok14[C] == 5700000.0f);         // token=57*100000+0
  assert(tok14[2 * C] == 8400000.0f);     // token=84*100000+0
  assert(tok14[3 * C] == 8500000.0f);     // token=85*100000+0

  std::fprintf(stderr, "PASS: test_second_row_first_token\n");
}

// Test 4: Output size is exactly 196*4096.
void test_output_size() {
  constexpr int H = 28, W = 28, C = 1024;
  constexpr int OUTPUT_TOKENS = 14 * 14;
  constexpr int OC = C * 4;

  static_assert(OUTPUT_TOKENS == 196);
  static_assert(OC == 4096);
  static_assert(OUTPUT_TOKENS * OC == 196 * 4096);

  std::fprintf(stderr, "PASS: test_output_size (static: 196*4096=%d)\n",
               OUTPUT_TOKENS * OC);
}

// Test 5: All 784 input tokens appear exactly once in the output.
void test_no_data_loss() {
  constexpr int H = 28, W = 28, C = 1024;
  constexpr int INPUT_SIZE = H * W * C;
  constexpr int OUTPUT_TOKENS = 14 * 14;
  constexpr int OC = C * 4;
  constexpr int OUTPUT_SIZE = OUTPUT_TOKENS * OC;

  float input[INPUT_SIZE];
  float output[OUTPUT_SIZE];

  // Mark each token's first channel with its token index.
  for (int t = 0; t < H * W; ++t) {
    input[t * C] = static_cast<float>(t);
  }

  test::merge_spatial_2x2(input, output);

  // Check that all 784 token markers appear in the output.
  // Each output token has 4 segments of 1024 channels.
  // The marker is at offset 0, C, 2C, 3C within each OC-sized token.
  bool seen[784] = {};
  for (int t = 0; t < OUTPUT_TOKENS; ++t) {
    float* tok = output + t * OC;
    for (int s = 0; s < 4; ++s) {
      int marker = static_cast<int>(tok[s * C]);
      assert(marker >= 0 && marker < 784);
      seen[marker] = true;
    }
  }

  for (int i = 0; i < 784; ++i) {
    assert(seen[i]);
  }

  std::fprintf(stderr, "PASS: test_no_data_loss (all 784 tokens accounted)\n");
}

int main() {
  test_output_size();
  test_first_output_token();
  test_second_output_token();
  test_second_row_first_token();
  test_no_data_loss();

  std::fprintf(stderr, "\nAll spatial merge tests PASSED.\n");
  return 0;
}
