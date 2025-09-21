cmake_minimum_required(VERSION 3.21)
project(millui_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(pybind11 CONFIG REQUIRED)

set(SRC
  src/facade.cpp
  backends/occt/occt_backend.cpp
  geom2d/clipper2_wrap.cpp
  algo/plan_2d.cpp
  algo/post_gcode.cpp
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

target_compile_options(_native PRIVATE -Wall -Wextra -Werror)

install(TARGETS _native DESTINATION "skills/mill_ui/cam/native")
