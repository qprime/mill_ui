# Native CAD Exporter

Owner path: skills/mill_ui/cad/native/

## 1. What this is

The native CAD exporter provides C++ helpers that summarise sheet geometry and emit STEP/STL data.
Python shims wrap the compiled module so compose_cam can produce previews without extra dependencies.

## 2. When to use it

- Export lightweight geometry summaries for downstream CAD tools.
- Generate STEP or STL previews directly from sheet templates.
- Extend CAD coverage with OCCT-backed operations or richer tessellation.

## 3. How to run

Build via the project install; use explicit CMake builds when diagnosing toolchain issues.

```bash
python -m pip install --upgrade pip
pip install .
cmake -S skills/mill_ui/cad/native/cpp -B build/native_cad && cmake --build build/native_cad
```

## 4. Inputs & outputs (for AI & humans)

- `skills/mill_ui/cad/native/cpp/` — CMake project for the CAD exporter.
- `skills/mill_ui/cad/native/core.py` — Python dataclasses and wrapper API.
- `skills/mill_ui/api/cad.py` — Public CAD API that relies on the native exporter.
- `memories/cam_projects/` — panel definitions used when exporting geometry.
- `pyproject.toml` — scikit-build-core configuration used during installation.

## 5. Public surface

- `skills.mill_ui.cad.native.core.is_native_available()` — detect whether the CAD extension loaded.
- `skills.mill_ui.cad.native.core.build_model(sheet, shapes)` — summarise sheet, parts, and pockets.
- `skills.mill_ui.cad.native.core.export_stl(sheet, shapes, output_path)` — write STL meshes.
- `skills.mill_ui.cad.native.core.export_step(sheet, shapes, output_path)` — emit STEP manifests.
- `skills.mill_ui.cad.native.core.Model` — dataclass capturing sheet, parts, and pockets.

## 6. Invariants & guardrails

- Requires C++17 plus pybind11; exporters raise `RuntimeError` when missing.
- All lengths are millimetres so CAD and CAM outputs stay aligned.
- Native exporter writes files under the requested output directory only.
- Model summaries remain deterministic; maintain stable dataclass field ordering.

## 7. Extension points

- Add exporters by binding new C++ functions under `cpp/bindings` and exposing them in `core.py`.
- Augment geometry shims by extending dataclasses or helper conversions.
- Integrate OCCT features by linking against system libraries in the CMake project.

## 8. AI reading order

- `skills/mill_ui/cad/native/core.py` — Python shims over the native exporter.
- `skills/mill_ui/cad/native/cpp/bindings/cad_native_pybind.cpp` — pybind11 binding layer.
- `skills/mill_ui/cad/native/cpp/CMakeLists.txt` — Build configuration for the CAD extension.
- `skills/mill_ui/cad/export/step.py` — High-level STEP/STL helpers hitting the native core.
- `skills/mill_ui/api/cad.py` — Public API exposing CAD exporters to callers.
