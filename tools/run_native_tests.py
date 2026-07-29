#!/usr/bin/env python3
"""Configure, build, and run the native (C++) unit tests via CTest.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
without needing per-flag permission prompts, mirroring tools/run_tests.py.

The native extension is built manually (not via pip); this wrapper drives the
CMake project in cam/native/cpp, building both the pybind module and the test
target so every translation unit is compiled under -Werror, then runs CTest.

Examples:
    python tools/run_native_tests.py
    python tools/run_native_tests.py --sanitize    # ASan + UBSan
    python tools/run_native_tests.py --build-dir build/native_tests
    python tools/run_native_tests.py -v
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "cam" / "native" / "cpp"


def pybind11_cmake_dir() -> str | None:
    try:
        import pybind11

        return str(pybind11.get_cmake_dir())
    except Exception:
        return None


def run(cmd: list[str]) -> int:
    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_native_tests.py",
        description="Build and run the native C++ unit tests via CTest.",
    )
    parser.add_argument("--build-dir", help="CMake build directory.")
    parser.add_argument("--sanitize", action="store_true", help="Build and run under ASan + UBSan.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose CTest output.")
    ns = parser.parse_args(argv)

    default_build_dir = "build/native_tests_asan" if ns.sanitize else "build/native_tests"
    build_dir = REPO_ROOT / (ns.build_dir or default_build_dir)

    configure = [
        "cmake",
        "-S",
        str(SOURCE_DIR),
        "-B",
        str(build_dir),
        "-DMILLUI_NATIVE_TESTS=ON",
        f"-DMILLUI_NATIVE_SANITIZE={'ON' if ns.sanitize else 'OFF'}",
    ]
    cmake_dir = pybind11_cmake_dir()
    if cmake_dir is not None:
        configure.append(f"-Dpybind11_DIR={cmake_dir}")

    rc = run(configure)
    if rc != 0:
        return rc

    rc = run(["cmake", "--build", str(build_dir), "--target", "_native", "native_tests"])
    if rc != 0:
        return rc

    ctest = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
    if ns.verbose:
        ctest.append("-V")
    return run(ctest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
