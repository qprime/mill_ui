#!/usr/bin/env python3
"""Minimal wrapper around mypy for the mill_ui codebase.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
without needing per-flag permission prompts. Forwards positional targets and
a small set of explicit flags to mypy. Configuration (strict mode, excludes,
ignored error codes) lives in pyproject.toml.

Examples:
    python tools/run_mypy.py                          # type-check the repo
    python tools/run_mypy.py cam/ generators/         # specific packages
    python tools/run_mypy.py --no-incremental         # force a full re-check
    python tools/run_mypy.py --show-error-codes       # include rule codes
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_mypy_args(ns: argparse.Namespace) -> list[str]:
    args: list[str] = []
    if ns.no_incremental:
        args.append("--no-incremental")
    if ns.show_error_codes:
        args.append("--show-error-codes")
    if ns.pretty:
        args.append("--pretty")
    if ns.strict:
        args.append("--strict")
    args.extend(ns.targets or ["."])
    return args


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_mypy.py",
        description="Wrapper around mypy for mill_ui.",
    )
    parser.add_argument("targets", nargs="*", help="Paths or modules to type-check (default: repo root).")
    parser.add_argument("--no-incremental", action="store_true", help="Disable mypy's incremental cache.")
    parser.add_argument("--show-error-codes", action="store_true", help="Show error codes in output.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print errors with source context.")
    parser.add_argument("--strict", action="store_true", help="Force --strict (pyproject.toml already sets this).")
    ns = parser.parse_args(argv)

    cmd = [sys.executable, "-m", "mypy", *build_mypy_args(ns)]
    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
