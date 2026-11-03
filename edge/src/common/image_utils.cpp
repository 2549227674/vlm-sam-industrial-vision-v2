// stb_image implementation unit + CPU bilinear resize fallback.
// stb_image handles JPEG/PNG decode; resize is a simple bilinear interpolation.

#define STB_IMAGE_IMPLEMENTATION
#include "stb/stb_image.h"

#include "edge/common/image_utils.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>

namespace vlm_industrial::edge {

void PixelDeleter::operator()(uint8_t* p) const noexcept {
  if (from_stb) {
    stbi_image_free(p);
  } else {
    delete[] p;
  }
}

Image::~Image() = default;

Image* Image::load(const std::string& path) {
  int w = 0, h = 0, ch = 0;
  unsigned char* pixels = stbi_load(path.c_str(), &w, &h, &ch, 3);
  if (!pixels) {
    std::fprintf(stderr, "[Image] stbi_load failed: %s (%s)\n",
                 path.c_str(), stbi_failure_reason());
    return nullptr;
  }
  auto* img = new Image();
  img->width = w;
  img->height = h;
  img->channels = 3;
  img->data = PixelBuffer(pixels, PixelDeleter{.from_stb = true});
  return img;
}

// CPU bilinear resize fallback.
// Used when RGA im2d resize is not available (x86 dev) or fails.
Image* resize_bilinear(const Image& src, int dst_w, int dst_h) {
  auto* dst = new Image();
  dst->width = dst_w;
  dst->height = dst_h;
  dst->channels = 3;
  dst->data = PixelBuffer(new uint8_t[dst_w * dst_h * 3]());

  const float sx = static_cast<float>(src.width) / dst_w;
  const float sy = static_cast<float>(src.height) / dst_h;
  const int src_stride = src.width * 3;
  const int dst_stride = dst_w * 3;
  const auto* sp = src.data.get();
  auto* dp = dst->data.get();

  for (int dy = 0; dy < dst_h; ++dy) {
    float fy = (dy + 0.5f) * sy - 0.5f;
    int y0 = std::max(0, static_cast<int>(std::floor(fy)));
    int y1 = std::min(src.height - 1, y0 + 1);
    float wy = fy - y0;

    for (int dx = 0; dx < dst_w; ++dx) {
      float fx = (dx + 0.5f) * sx - 0.5f;
      int x0 = std::max(0, static_cast<int>(std::floor(fx)));
      int x1 = std::min(src.width - 1, x0 + 1);
      float wx = fx - x0;

      const uint8_t* p00 = sp + y0 * src_stride + x0 * 3;
      const uint8_t* p10 = sp + y0 * src_stride + x1 * 3;
      const uint8_t* p01 = sp + y1 * src_stride + x0 * 3;
      const uint8_t* p11 = sp + y1 * src_stride + x1 * 3;

      for (int c = 0; c < 3; ++c) {
        float v = (1 - wy) * ((1 - wx) * p00[c] + wx * p10[c]) +
                  wy * ((1 - wx) * p01[c] + wx * p11[c]);
        dp[dy * dst_stride + dx * 3 + c] =
            static_cast<uint8_t>(std::clamp(v + 0.5f, 0.0f, 255.0f));
      }
    }
  }
  return dst;
}

}  // namespace vlm_industrial::edge
