#pragma once

#include <cstdint>
#include <memory>
#include <string>

namespace vlm_industrial::edge {

// Pixel buffers come from two allocators: stbi_load (malloc) and new[].
// The deleter remembers which one, so each is released by its own free.
struct PixelDeleter {
  bool from_stb{false};
  void operator()(uint8_t* p) const noexcept;
};
using PixelBuffer = std::unique_ptr<uint8_t[], PixelDeleter>;

// Decoded image in RGB8 format.
struct Image {
  // Loads and decodes a JPEG/PNG file to 3-channel RGB.
  // Returns nullptr on failure.
  static Image* load(const std::string& path);

  ~Image();

  int width{0};
  int height{0};
  int channels{0};  // always 3 (RGB)
  PixelBuffer data;
};

// CPU bilinear resize (stb_image_resize2 fallback).
// Returns nullptr on failure. Output is always 3-channel RGB.
Image* resize_bilinear(const Image& src, int dst_w, int dst_h);

}  // namespace vlm_industrial::edge
