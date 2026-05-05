#!/usr/bin/env python3
"""Wrapper around `pylint --enable=duplicate-code` for mill_ui.

Exists so agent invocations stay within the allowed `Bash(python:*)` prefix
and so the command can be run without constructing a long find-piped shell
invocation by hand. Walks the repo, collects Python sources, and runs pylint
with only the duplicate-code checker enabled.

Examples:
    python tools/run_duplication.py                          # full repo
    python tools/run_duplication.py --min-lines 10           # looser threshold
    python tools/run_duplication.py generators/ assembly/    # subset
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCLUDES = (".venv", "tests", "docs", "build", ".git", "__pycache__")


def collect_sources(roots: list[Path], excludes: tuple[str, ...]) -> list[str]:
    files: list[str] = []
    for root in roots:
        start = (REPO_ROOT / root).resolve() if not root.is_absolute() else root
        if start.is_file() and start.suffix == ".py":
            files.append(str(start))
            continue
        if not start.is_dir():
            continue
        for path in start.rglob("*.py"):
            if any(part in excludes for part in path.parts):
                continue
            files.append(str(path))
    return sorted(set(files))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_duplication.py",
        description="Run pylint duplicate-code check across the mill_ui source tree.",
    )
    parser.add_argument("targets", nargs="*", help="Paths to scan (default: repo root).")
    parser.add_argument("--min-lines", type=int, default=6, help="Minimum duplicated lines to report (default: 6).")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional path part to exclude (repeatable).",
    )
    ns = parser.parse_args(argv)

    excludes = DEFAULT_EXCLUDES + tuple(ns.exclude)
    roots = [Path(t) for t in ns.targets] if ns.targets else [REPO_ROOT]
    sources = collect_sources(roots, excludes)
    if not sources:
        print("run_duplication.py: no Python sources found", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        "-m",
        "pylint",
        "--disable=all",
        "--enable=duplicate-code",
        f"--min-similarity-lines={ns.min_lines}",
        *sources,
    ]
    print("+", shlex.join(cmd[:6]), f"<{len(sources)} files>", flush=True)
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
