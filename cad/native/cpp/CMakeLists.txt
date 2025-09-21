cmake_minimum_required(VERSION 3.21)
project(millui_cad_native LANGUAGES CXX)

find_package(pybind11 CONFIG REQUIRED)
find_package(OpenCASCADE REQUIRED)

set(CAD_NATIVE_SRC
  bindings/cad_native_pybind.cpp
)

add_library(_cad_native MODULE ${CAD_NATIVE_SRC})

pybind11_extension(_cad_native)
pybind11_strip(_cad_native)

set_target_properties(_cad_native PROPERTIES
  OUTPUT_NAME "_cad_native"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/python"
)

target_include_directories(_cad_native
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${OpenCASCADE_INCLUDE_DIR}
)

target_compile_features(_cad_native PRIVATE cxx_std_17)
target_compile_options(_cad_native PRIVATE -Wall -Wextra)

target_link_libraries(_cad_native
  PRIVATE
    pybind11::module
    TKernel
    TKMath
    TKG2d
    TKG3d
    TKGeomBase
    TKBRep
    TKGeomAlgo
    TKTopAlgo
    TKPrim
    TKBO
    TKBool
    TKShHealing
    TKMesh
    TKSTEPBase
    TKSTEPAttr
    TKSTEP
    TKXSBase
    TKSTL
)

install(TARGETS _cad_native DESTINATION "skills/mill_ui/cad/native")
