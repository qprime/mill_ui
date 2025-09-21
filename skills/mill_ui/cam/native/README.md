# Native CAM Core

Owner path: skills/mill_ui/cam/native/

## 1. What this is

The native CAM core provides the C++17 planners compiled via pybind11 for heavy operations.
Python shims map project data structures into the compiled engine for deterministic toolpaths.

## 2. When to use it

- Produce performant pocket, profile, drilling, or bore toolpaths.
- Validate native builds on a new platform or toolchain.
- Extend the CAM kernel with additional geometry primitives or optimisations.

## 3. How to run

Build through the project install; use explicit CMake invocations when debugging.

```bash
python -m pip install --upgrade pip
pip install .
cmake -S skills/mill_ui/cam/native/cpp -B build/native_cam && cmake --build build/native_cam
```

## 4. Inputs & outputs (for AI & humans)

- `skills/mill_ui/cam/native/cpp/` — CMake project for the native CAM engine.
- `skills/mill_ui/cam/native/core.py` — Python shims gating native access.
- `skills/mill_ui/cam/model/` — dataclasses converted before hitting the native bindings.
- `skills/mill_ui/cam/ops/` — callers that delegate heavy work to the native layer.
- `pyproject.toml` — scikit-build-core configuration that builds the extension during install.

## 5. Public surface

- `skills.mill_ui.cam.native.core.is_native_available()` — detect whether the extension loaded.
- `skills.mill_ui.cam.native.core.pocket_raster(...)` — plan raster pockets via the native engine.
- `skills.mill_ui.cam.native.core.profile_outline(...)` — generate profile passes.
- `skills.mill_ui.cam.native.core.post_gcode(moves, ...)` — emit G-code strings natively.
- `skills.mill_ui.cam.native.core.fit_arcs(paths, tol_mm)` — smooth moves with arc fitting.

## 6. Invariants & guardrails

- Requires a modern C++17 compiler and pybind11 headers.
- Native API raises `RuntimeError` when accessed before a successful build; callers must guard with `is_native_available()`.
- All geometry uses millimetres and matches the winding expected by composition templates.
- Bindings remain deterministic; avoid introducing randomised behaviour inside C++ code.

## 7. Extension points

- Add planners by implementing pybind11 bindings under `cpp/bindings` and exposing them in `core.py`.
- Vendor extra geometry helpers under `cpp/geom2d` and wire them into Python wrappers.
- Surface additional configuration by extending dataclasses in `skills.mill_ui.cam.model`.

## 8. AI reading order

- `skills/mill_ui/cam/native/core.py` — Python facade around the native engine.
- `skills/mill_ui/cam/native/cpp/src/facade.cpp` — C++ entry point that bridges planners.
- `skills/mill_ui/cam/native/cpp/algo/plan_2d.cpp` — Core pocket/profile planning logic.
- `skills/mill_ui/cam/native/cpp/algo/post_gcode.cpp` — Native G-code emitter implementation.
- `skills/mill_ui/cam/native/cpp/CMakeLists.txt` — Build configuration for the CAM extension.
