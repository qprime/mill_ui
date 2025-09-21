# Native CAM Core

The `skills.mill_ui.cam.native` package houses the C++ implementation of the
CAM toolpath generators, exposed to Python via pybind11.  All internal CAM
modules now require the native extension — build failures will surface early so
they can be addressed rather than silently falling back to the retired
pure-Python paths.

## Dependencies

| Component | Purpose | Notes |
|-----------|---------|-------|
| C++17 toolchain | Build the extension | clang ≥14 or gcc ≥11 recommended |
| [pybind11] | Python bindings | Pulled in automatically by `pip install .` |
| [OpenCascade (OCCT)] | STEP/B-rep handling | Install system packages (`brew install opencascade` or `apt install libocct-dev`) |
| [Clipper2] | 2D offsetting/booleans | A minimal adapter ships in-tree; replace with the full library when enabling advanced geometry |

> **Note**: The current implementation vendors lightweight stubs for the OCCT
> and Clipper integrations so the module can build without those libraries in a
> constrained environment.  Link against the real vendor libraries to unlock
> STEP feature support and production-grade 2D offsetting.

## Quick start

```bash
# From the repository root
python -m pip install --upgrade pip
pip install .
```

`pip install .` uses [scikit-build-core] to configure CMake, compile the native
module, and install the package in editable form.  Wheels are produced for the
current platform as part of the build.

### Platform setup

- **macOS (Apple Silicon / Intel)**
  ```bash
  brew install opencascade ninja cmake
  # optional: brew install llvm   # for a recent clang
  pip install .
  ```

- **Ubuntu 22.04+**
  ```bash
  sudo apt update
  sudo apt install build-essential cmake ninja-build libocct-dev
  pip install .
  ```

If OCCT is not available the build succeeds with stub functionality so the
extension can still be compiled, but the native module remains the execution
path for all CAM operations.

## Running tests

```bash
pytest skills/mill_ui/tests/unit
```

When the native extension is present these tests exercise the pybind11 shims
and algorithms.  Add platform-specific tests under
`skills/mill_ui/cam/native/cpp/tests` and register them with `ctest` to extend
coverage.

[pybind11]: https://pybind11.readthedocs.io/
[OpenCascade (OCCT)]: https://www.opencascade.com/
[Clipper2]: https://www.angusj.com/clipper2/Docs/Overview.htm
[scikit-build-core]: https://scikit-build-core.readthedocs.io/
