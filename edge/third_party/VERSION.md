# Edge Third-Party Library Versions

## 板子环境（Orange Pi 5 16GB）

| 组件 | 版本 |
|---|---|
| OS | Ubuntu 22.04 Jammy |
| Kernel | 6.1.99-rockchip-rk3588 |
| RKNPU driver | v0.9.8 |
| GCC | 11.4.0 |
| CMake | 3.22.1 |
| librknnrt.so | rknn-toolkit2 v2.x |
| librkllmrt.so | v1.2.3 |
| librga.so | airockchip/librga |

## 头文件来源

- rknn_api/rknn_api.h — 从板子 /usr/include/ 拷贝
- rkllm_api/rkllm.h — 从板子 /usr/include/ 拷贝
- librga/rga.h, im2d.hpp, im2d_type.h — 从板子 /usr/include/ 拷贝

## 板子 IP（局域网）

192.168.137.66
