# Native CAM Core

Path: `cam/native/`

## 1. What this is

The native CAM core provides C++20 planners compiled via pybind11 for the
heavy toolpath operations (pocket, profile, drill, bore) and the G-code
emitter. Python shims in `core.py` map project data structures into the
compiled engine and translate the results back into `cam.moves` dataclasses.

The move IR crossing the FFI is a list of dicts with a `kind` discriminator;
on the C++ side it is a `std::variant<Comment, SetRpm, SetFeed, Rapid, Cut,
Retract, Dwell>`. Absence is `None` / `std::nullopt` (never NaN). The dict
schema is the versioned contract — a change requires both sides plus the
recipe goldens to move together.

## 2. When to use it

- Produce pocket, profile, drilling, or bore toolpaths.
- Validate native builds on a new platform or toolchain.
- Extend the CAM kernel with additional planners or geometry primitives.

## 3. How to build

The extension is built manually with CMake — it is **not** installed via
`pip`, and the compiled `.so` is gitignored. A C++20 toolchain and the
pybind11 headers (from the project venv) are required.

```bash
source .venv/bin/activate
PYBIND11_DIR=$(python -c "import pybind11; print(pybind11.get_cmake_dir())")
cmake -S cam/native/cpp -B build/native_cam -Dpybind11_DIR="$PYBIND11_DIR"
cmake --build build/native_cam
cp build/native_cam/python/_native.cpython-*.so cam/native/
```

`core.is_native_available()` returns `False` until the `.so` sits next to
`core.py`; every wrapper raises `RuntimeError` if called before then.

## 4. Layout

- `cam/native/cpp/algo/geom2d.{hpp,cpp}` — geometry primitives (convex
  inset, scanline, winding, z-levels). No planner or emission logic.
- `cam/native/cpp/algo/plan_2d.cpp` — pocket / profile / drill / bore
  planners; consumes `geom2d`.
- `cam/native/cpp/algo/post_gcode.cpp` — the G-code emitter (`std::visit`
  over the move variant).
- `cam/native/cpp/include/millui/native/types.hpp` — shared FFI types and
  the `Move` variant.
- `cam/native/cpp/bindings/py/cam_native_pybind.cpp` — dict ↔ struct
  conversion and module init.
- `cam/native/core.py` — Python facade gating native access.

## 5. Public surface

- `is_native_available()` — detect whether the extension loaded.
- `pocket_raster(shape, setup, ...)` — plan a pocket (spiral or raster).
- `profile_outline(shape, setup, ...)` — plan profile passes.
- `drill_peck(points, setup, ...)` — plan peck drilling.
- `bore_helical(center, hole_d, setup, ...)` — plan a helical bore.
- `post_gcode(moves, ...)` — emit G-code from a move-dict sequence.

## 6. Tests

Native unit tests use doctest (fetched via CMake `FetchContent`) and run
under CTest:

```bash
python tools/run_native_tests.py
```

This configures with `-DMILLUI_NATIVE_TESTS=ON`, builds the `native_tests`
target, and runs CTest. `cpp/tests/test_geometry.cpp` covers the `geom2d`
primitives; `cpp/tests/test_post_gcode.cpp` covers emitter behavior. The
end-to-end equivalence gate is the Python recipe suite
(`python -m tests.test_recipes`), which byte-compares every recipe's `.nc`
output.

## 7. Invariants & guardrails

- Requires a C++20 compiler and pybind11 headers.
- Native API raises `RuntimeError` when accessed before a successful build;
  callers guard with `is_native_available()`.
- All geometry is in millimetres.
- Bindings are deterministic; no randomised behaviour inside C++ code.
- The build compiles clean under `-Wall -Wextra -Wpedantic -Werror`.
