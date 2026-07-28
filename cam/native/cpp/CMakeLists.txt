cmake_minimum_required(VERSION 3.21)
project(millui_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(pybind11 CONFIG REQUIRED)

set(CORE_SRC
  algo/geom2d.cpp
  algo/plan_2d.cpp
  algo/post_gcode.cpp
)

set(SRC
  ${CORE_SRC}
  bindings/py/cam_native_pybind.cpp
)

add_library(_native MODULE ${SRC})

pybind11_extension(_native)
pybind11_strip(_native)

set_target_properties(_native PROPERTIES
  OUTPUT_NAME "_native"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/python"
)

target_include_directories(_native
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(_native
  PRIVATE
    pybind11::module
)

target_compile_options(_native PRIVATE -Wall -Wextra -Wpedantic -Werror)

install(TARGETS _native DESTINATION "cam/native")

option(MILLUI_NATIVE_TESTS "Build native unit tests" OFF)
option(MILLUI_NATIVE_SANITIZE "Build native unit tests with ASan and UBSan" OFF)

if(MILLUI_NATIVE_TESTS)
  include(FetchContent)
  FetchContent_Declare(
    doctest
    GIT_REPOSITORY https://github.com/doctest/doctest.git
    GIT_TAG v2.4.11
    SOURCE_SUBDIR do_not_configure_doctest_cmake
  )
  FetchContent_MakeAvailable(doctest)

  enable_testing()

  add_executable(native_tests
    tests/test_geometry.cpp
    tests/test_plan_2d.cpp
    tests/test_post_gcode.cpp
    ${CORE_SRC}
  )
  target_include_directories(native_tests
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/include
      ${CMAKE_CURRENT_SOURCE_DIR}
      ${doctest_SOURCE_DIR}
  )
  target_compile_options(native_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)

  if(MILLUI_NATIVE_SANITIZE)
    target_compile_options(native_tests PRIVATE
      -fsanitize=address,undefined
      -fno-omit-frame-pointer
    )
    target_link_options(native_tests PRIVATE -fsanitize=address,undefined)
  endif()

  add_test(NAME native_tests COMMAND native_tests)
endif()
