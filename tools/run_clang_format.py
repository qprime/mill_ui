#!/usr/bin/env python3
"""Minimal wrapper around clang-format for the mill_ui native sources.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
without needing per-flag permission prompts, mirroring tools/run_ruff.py.
Style configuration lives in the repo-root .clang-format.

Nothing is rewritten unless the formatter is invoked without --check.

Examples:
    python tools/run_clang_format.py --check    # verify, exit non-zero on drift
    python tools/run_clang_format.py --diff     # show what would change
    python tools/run_clang_format.py            # apply formatting in place
    python tools/run_clang_format.py cam/native/cpp/algo/plan_2d.cpp
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NATIVE_ROOT = REPO_ROOT / "cam" / "native" / "cpp"
SOURCE_SUFFIXES = (".cpp", ".hpp")


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
        prog="run_clang_format.py",
        description="Wrapper around clang-format for the mill_ui native sources.",
    )
    parser.add_argument("targets", nargs="*", help="Files or dirs (default: cam/native/cpp).")
    parser.add_argument("--check", action="store_true", help="Verify without writing.")
    parser.add_argument("--diff", action="store_true", help="Show the reformatting diff.")
    ns = parser.parse_args(argv)

    binary = shutil.which("clang-format")
    if binary is None:
        print(
            "clang-format not found. Install it with:\n    sudo apt-get install -y clang-format",
            file=sys.stderr,
        )
        return 1

    sources = discover_sources(ns.targets)
    if not sources:
        print("No C++ sources found.", file=sys.stderr)
        return 1

    cmd = [binary]
    if ns.check or ns.diff:
        cmd.extend(["--dry-run", "--Werror"])
    else:
        cmd.append("-i")
    cmd.extend(str(p.relative_to(REPO_ROOT)) for p in sources)

    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
