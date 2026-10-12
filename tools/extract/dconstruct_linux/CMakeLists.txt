# Minimal Linux build of the dconstruct CLI (disassembler/decompiler only).
# Used by build.sh, which copies this file next to a patched copy of the
# dconstruct sources (source/, include/) and configures it out of tree.
cmake_minimum_required(VERSION 3.16)
project(dconstruct_linux LANGUAGES CXX)

set(VERSION_NUMBER "2.2.0-linux" CACHE STRING "Version string baked into buildinfo.h")
set(CTRE_INCLUDE_DIR "" CACHE PATH "Directory containing ctre.hpp (single header)")

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/source")

find_package(TBB QUIET)   # libstdc++ parallel algorithms (std::execution::par_unseq)

# buildinfo.h (replaces scripts/buildinfo.py so no python needed at build time)
string(TIMESTAMP BUILD_DATE "%Y-%m-%d %H:%M:%S")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/buildinfo.h"
    "#pragma once\n"
    "#define COMPILER_VERSION \"${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\"\n"
    "#define BUILD_DATE \"${BUILD_DATE}\"\n"
    "#define VERSION \"${VERSION_NUMBER}\"\n")

file(GLOB_RECURSE LIB_SOURCES CONFIGURE_DEPENDS
    "${SOURCE_DIR}/disassembly/*.cpp"
    "${SOURCE_DIR}/decompilation/*.cpp"
    "${SOURCE_DIR}/compilation/*.cpp"
    "${SOURCE_DIR}/ast/*.cpp"
    "${SOURCE_DIR}/base/*.cpp"
)

add_library(dconstruct_lib STATIC ${LIB_SOURCES})
target_include_directories(dconstruct_lib PUBLIC
    "${CMAKE_CURRENT_BINARY_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${CTRE_INCLUDE_DIR}"
)
target_compile_options(dconstruct_lib PRIVATE -ftemplate-depth=4096)
# Graphviz is stubbed out (patch 0003): --graphs writes .dot text instead of .svg.
target_compile_definitions(dconstruct_lib PUBLIC DCONSTRUCT_NO_GRAPHVIZ)
if(TBB_FOUND)
    target_link_libraries(dconstruct_lib PUBLIC TBB::tbb)
endif()

add_executable(dconstruct "${SOURCE_DIR}/main_cli.cpp")
target_link_libraries(dconstruct PRIVATE dconstruct_lib)
