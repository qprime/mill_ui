#!/usr/bin/env python3
"""Minimal wrapper around clang-tidy for the mill_ui native sources.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
without needing per-flag permission prompts, mirroring tools/run_ruff.py.
Check selection lives in the repo-root .clang-tidy.

clang-tidy needs a compilation database; this configures the CMake project
into a dedicated build directory when compile_commands.json is absent.

Examples:
    python tools/run_clang_tidy.py                  # full native tree
    python tools/run_clang_tidy.py --fix            # apply the mechanical fixes
    python tools/run_clang_tidy.py cam/native/cpp/algo/plan_2d.cpp
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from clang_toolchain import resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
NATIVE_ROOT = REPO_ROOT / "cam" / "native" / "cpp"
DEFAULT_BUILD_DIR = REPO_ROOT / "build" / "native_tidy"
SOURCE_SUFFIXES = (".cpp",)


def pybind11_cmake_dir() -> str | None:
    try:
        import pybind11

        return str(pybind11.get_cmake_dir())
    except Exception:
        return None


def run(cmd: list[str]) -> int:
    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


def ensure_compile_commands(build_dir: Path) -> int:
    database = build_dir / "compile_commands.json"
    cmake_lists = NATIVE_ROOT / "CMakeLists.txt"
    if database.exists() and database.stat().st_mtime >= cmake_lists.stat().st_mtime:
        dedupe_compile_commands(database)
        return 0

    configure = [
        "cmake",
        "-S",
        str(NATIVE_ROOT),
        "-B",
        str(build_dir),
        "-DMILLUI_NATIVE_TESTS=ON",
    ]
    cmake_dir = pybind11_cmake_dir()
    if cmake_dir is not None:
        configure.append(f"-Dpybind11_DIR={cmake_dir}")
    rc = run(configure)
    if rc == 0:
        dedupe_compile_commands(database)
    return rc


def dedupe_compile_commands(database: Path) -> None:
    """Keep one compile command per file.

    CORE_SRC builds into both _native and native_tests, so every core source
    appears twice and clang-tidy would analyze it once per entry. The two
    commands differ only in target-specific flags that do not affect analysis.
    """
    entries = json.loads(database.read_text())
    unique: dict[str, dict[str, str]] = {}
    for entry in entries:
        unique.setdefault(entry["file"], entry)
    if len(unique) != len(entries):
        database.write_text(json.dumps(list(unique.values()), indent=2))


def discover_sources(targets: list[str]) -> list[Path]:
    if not targets:
        return sorted(p for p in NATIVE_ROOT.rglob("*") if p.suffix in SOURCE_SUFFIXES)

    found: list[Path] = []
    for target in targets:
        path = Path(target)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.is_dir():
            found.extend(p for p in path.rglob("*") if p.suffix in SOURCE_SUFFIXES)
        else:
            found.append(path)
    return sorted(set(found))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_clang_tidy.py",
        description="Wrapper around clang-tidy for the mill_ui native sources.",
    )
    parser.add_argument("targets", nargs="*", help="Files or dirs (default: cam/native/cpp).")
    parser.add_argument("--fix", action="store_true", help="Apply suggested fixes in place.")
    parser.add_argument(
        "--build-dir",
        default=str(DEFAULT_BUILD_DIR.relative_to(REPO_ROOT)),
        help="Build directory holding compile_commands.json.",
    )
    ns = parser.parse_args(argv)

    binary, error = resolve("clang-tidy")
    if binary is None:
        print(error, file=sys.stderr)
        return 1

    build_dir = REPO_ROOT / ns.build_dir
    rc = ensure_compile_commands(build_dir)
    if rc != 0:
        return rc

    sources = discover_sources(ns.targets)
    if not sources:
        print("No C++ sources found.", file=sys.stderr)
        return 1

    cmd = [binary, "-p", str(build_dir), "--warnings-as-errors=*", "--quiet"]
    if ns.fix:
        cmd.append("--fix")
    cmd.extend(str(p.relative_to(REPO_ROOT)) for p in sources)

    return run(cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
