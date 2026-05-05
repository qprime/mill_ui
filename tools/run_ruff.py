#!/usr/bin/env python3
"""Minimal wrapper around ruff for the mill_ui codebase.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
without needing per-flag permission prompts. Forwards a small set of explicit
flags and positional targets to ruff.

Examples:
    python tools/run_ruff.py                    # lint the repo
    python tools/run_ruff.py --fix              # lint + autofix
    python tools/run_ruff.py --format           # run the formatter
    python tools/run_ruff.py --format --check   # check formatting without writing
    python tools/run_ruff.py cam/ generators/   # lint specific paths
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_ruff_args(ns: argparse.Namespace) -> list[str]:
    subcommand = "format" if ns.format else "check"
    args: list[str] = [subcommand]

    if ns.format:
        if ns.check:
            args.append("--check")
        if ns.diff:
            args.append("--diff")
    else:
        if ns.fix:
            args.append("--fix")
        if ns.unsafe_fixes:
            args.append("--unsafe-fixes")
        if ns.select:
            args.extend(["--select", ns.select])
        if ns.ignore:
            args.extend(["--ignore", ns.ignore])
        if ns.statistics:
            args.append("--statistics")

    args.extend(ns.targets or ["."])
    return args


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_ruff.py",
        description="Wrapper around ruff (lint + format) for mill_ui.",
    )
    parser.add_argument("targets", nargs="*", help="Paths to check (default: repo root).")
    parser.add_argument("--format", action="store_true", help="Run `ruff format` instead of `ruff check`.")
    parser.add_argument("--check", action="store_true", help="With --format, verify without writing.")
    parser.add_argument("--diff", action="store_true", help="With --format, show diff.")
    parser.add_argument("--fix", action="store_true", help="Apply autofixes (lint mode).")
    parser.add_argument("--unsafe-fixes", action="store_true", help="Include unsafe autofixes.")
    parser.add_argument("--select", help="Rule codes to enable (lint mode).")
    parser.add_argument("--ignore", help="Rule codes to ignore (lint mode).")
    parser.add_argument("--statistics", action="store_true", help="Show per-rule violation counts.")
    ns = parser.parse_args(argv)

    cmd = [sys.executable, "-m", "ruff", *build_ruff_args(ns)]
    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
