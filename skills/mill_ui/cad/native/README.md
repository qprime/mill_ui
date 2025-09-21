# Native CAD Exporter

This directory contains the native (C++/pybind11) helper used to build the
simplified geometry model that powers STEP and STL export in `skills.mill_ui`.

The current implementation captures high-level metadata for sheets, floating
parts, and pockets and hands it back to Python for lightweight file writing.
It is structured so that we can swap in an OCCT-backed solid kernel without
changing the public Python API.

## Building

The module is built automatically as part of `pip install .` using
`scikit-build-core`.  A modern C++17 compiler and `pybind11` headers are
required.

```bash
python -m pip install --upgrade pip
pip install .
```

## Future work

- Replace the simplified geometry summariser with an OCCT-backed modeller.
- Emit true B-rep STEP data instead of the current high-level summary files.
- Generate tessellations directly in C++ once the modeller is in place.
