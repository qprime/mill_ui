#!/usr/bin/env python3
"""Minimal wrapper around pytest for the mill_ui test suite.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
without needing per-flag permission prompts. Forwards positional targets
and a small set of explicit flags to pytest.

Examples:
    python tools/run_tests.py
    python tools/run_tests.py tests/test_basic_shapes.py
    python tools/run_tests.py -k finger_joint
    python tools/run_tests.py tests/test_assembly_beam_integration.py -x -q
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_pytest_args(ns: argparse.Namespace) -> list[str]:
    args: list[str] = []
    if ns.exitfirst:
        args.append("-x")
    if ns.quiet:
        args.append("-q")
    if ns.verbose:
        args.append("-v")
    if ns.last_failed:
        args.append("--lf")
    if ns.failed_first:
        args.append("--ff")
    if ns.keyword:
        args.extend(["-k", ns.keyword])
    if ns.marker:
        args.extend(["-m", ns.marker])
    if ns.maxfail is not None:
        args.append(f"--maxfail={ns.maxfail}")
    args.extend(ns.targets)
    return args


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_tests.py",
        description="Wrapper around pytest for mill_ui.",
    )
    parser.add_argument("targets", nargs="*", help="Test files, directories, or node ids.")
    parser.add_argument("-k", "--keyword", help="Only run tests matching the keyword expression.")
    parser.add_argument("-m", "--marker", help="Only run tests matching the marker expression.")
    parser.add_argument("-x", "--exitfirst", action="store_true", help="Stop at first failure.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet output.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    parser.add_argument("--lf", dest="last_failed", action="store_true", help="Rerun only last failed.")
    parser.add_argument("--ff", dest="failed_first", action="store_true", help="Run failed first.")
    parser.add_argument("--maxfail", type=int, help="Stop after N failures.")
    ns = parser.parse_args(argv)

    cmd = [sys.executable, "-m", "pytest", *build_pytest_args(ns)]
    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
