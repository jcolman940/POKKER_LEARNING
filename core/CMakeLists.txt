cmake_minimum_required(VERSION 3.20)

project(pokercore VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

option(POKERCORE_BUILD_TESTS "Build C++ unit tests" ON)
option(POKERCORE_BUILD_PYTHON "Build pybind11 Python module" OFF)

# When built through scikit-build-core, default to the Python module only.
if(SKBUILD)
  set(POKERCORE_BUILD_PYTHON ON)
  set(POKERCORE_BUILD_TESTS OFF)
endif()

configure_file(src/version.hpp.in ${CMAKE_CURRENT_BINARY_DIR}/generated/pokercore/version_info.hpp @ONLY)

add_library(pokercore STATIC
  src/version.cpp
)
target_include_directories(pokercore
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_BINARY_DIR}/generated
)
if(MSVC)
  target_compile_options(pokercore PRIVATE /W4)
else()
  target_compile_options(pokercore PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(POKERCORE_BUILD_TESTS)
  include(FetchContent)
  FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.7.1
    GIT_SHALLOW TRUE
  )
  FetchContent_MakeAvailable(Catch2)

  enable_testing()
  add_executable(pokercore_tests
    tests/test_version.cpp
  )
  target_link_libraries(pokercore_tests PRIVATE pokercore Catch2::Catch2WithMain)

  list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
  include(Catch)
  catch_discover_tests(pokercore_tests)
endif()

if(POKERCORE_BUILD_PYTHON)
  set(PYBIND11_FINDPYTHON ON)
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(_core bindings/module.cpp)
  target_link_libraries(_core PRIVATE pokercore)
  install(TARGETS _core LIBRARY DESTINATION pokercore)
endif()
