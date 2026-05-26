cmake_minimum_required(VERSION 3.16)
project(edge_pipeline LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Suppress hardware_destructive_interference_size warning — we always use 64.
add_compile_options(-Wno-interference-size)

# -- Third-party include paths (RKNN, RKLLM, librga, stb headers) --
set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
include_directories(${THIRD_PARTY_DIR}/rknn_api)
include_directories(${THIRD_PARTY_DIR}/rkllm_api)
include_directories(${THIRD_PARTY_DIR}/librga)
include_directories(${THIRD_PARTY_DIR})

# -- Project include path --
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# -- System libraries (RK3588 board: /usr/lib/) --
# Search order: /usr/lib/ (board real libs) → system default → /usr/lib/stub_libs/ (x86 dev).
set(_BOARD_LIB_DIR "/usr/lib")
set(_STUB_LIB_DIR "/usr/lib/stub_libs")

foreach(_lib rknnrt rkllmrt rga)
  find_library(${_lib}_LIBRARY ${_lib}
    PATHS ${_BOARD_LIB_DIR}
    NO_DEFAULT_PATH)
  if(NOT ${_lib}_LIBRARY)
    # Fallback to system search, then stubs for local x86 compilation testing.
    find_library(${_lib}_LIBRARY ${_lib}
      PATHS ${_STUB_LIB_DIR})
  endif()
  if(${_lib}_LIBRARY)
    add_library(${_lib} SHARED IMPORTED)
    set_target_properties(${_lib} PROPERTIES IMPORTED_LOCATION ${${_lib}_LIBRARY})
    message(STATUS "Found ${_lib}: ${${_lib}_LIBRARY}")
  else()
    message(FATAL_ERROR "Could not find lib${_lib}.so")
  endif()
endforeach()

# -- libcurl (required for T4 Upload) --
find_package(CURL REQUIRED)

# -- Common infrastructure sources --
set(COMMON_SOURCES
    src/common/config_loader.cpp
    src/common/http_client.cpp
    src/common/image_utils.cpp
)

# -- Worker sources (Prompt 2D: T1 + T2 EfficientAD + T3 FastSAM+VLM + T4) --
set(WORKER_SOURCES
    src/capture/capture_worker.cpp
    src/pipeline/ead_worker.cpp
    src/pipeline/fastsam_worker.cpp       # Prompt 2D: real FastSAM + VLM T3
    src/pipeline/localizer_worker.cpp     # Phase 10: ORT CPU localizer T3
    src/pipeline/mock_vlm_worker.cpp      # kept for reference; not used in main
    src/upload/upload_worker.cpp
    src/vlm/qwen3vl_runner.cpp            # Prompt 2D: Qwen3-VL RKLLM runner
)

# -- Main executable --
add_executable(edge_pipeline
    src/main.cpp
    ${COMMON_SOURCES}
    ${WORKER_SOURCES}
)

target_link_libraries(edge_pipeline PRIVATE
    rknnrt rkllmrt rga
    CURL::libcurl
    pthread
)

# -- Install --
install(TARGETS edge_pipeline DESTINATION bin)
