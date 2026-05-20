#pragma once

#include <cstdint>
#include <memory>
#include <string>

namespace vlm_industrial::edge {

// Decoded image in RGB8 format.
struct Image {
  // Loads and decodes a JPEG/PNG file to 3-channel RGB.
  // Returns nullptr on failure.
  static Image* load(const std::string& path);

  ~Image();

  int width{0};
  int height{0};
  int channels{0};  // always 3 (RGB)
  std::unique_ptr<uint8_t[]> data;
};

// CPU bilinear resize (stb_image_resize2 fallback).
// Returns nullptr on failure. Output is always 3-channel RGB.
Image* resize_bilinear(const Image& src, int dst_w, int dst_h);

}  // namespace vlm_industrial::edge
