cmake_minimum_required(VERSION 3.16)
project(edge_pipeline LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Suppress hardware_destructive_interference_size warning — we always use 64.
add_compile_options(-Wno-interference-size)

# -- Third-party include paths (RKNN, RKLLM, librga headers) --
set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
include_directories(${THIRD_PARTY_DIR}/rknn_api)
include_directories(${THIRD_PARTY_DIR}/rkllm_api)
include_directories(${THIRD_PARTY_DIR}/librga)

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

# -- Common infrastructure sources (Phase 7 foundation) --
set(COMMON_SOURCES
    src/common/config_loader.cpp
    src/common/http_client.cpp
)

# -- Main executable --
add_executable(edge_pipeline
    src/main.cpp
    ${COMMON_SOURCES}
)

target_link_libraries(edge_pipeline PRIVATE
    rknnrt rkllmrt rga
    CURL::libcurl
    pthread
)

# -- Install --
install(TARGETS edge_pipeline DESTINATION bin)
