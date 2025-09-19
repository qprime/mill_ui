"""CLI to run cliff_ai tests consistently.

Examples:
  python -m tools.test_runner                 # unit tests only (default markers)
  python -m tools.test_runner --api           # include API/network tests
  python -m tools.test_runner --module cortex # only cortex tests
  python -m tools.test_runner -k diff         # filter by keyword
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List


from vitals.module_registry import discover_modules, resolve_modules


def build_marker_expr(include_api: bool, include_expensive: bool) -> str:
    parts: List[str] = []
    if not include_api:
        parts.append("not api")
        parts.append("not network")
    if not include_expensive:
        parts.append("not expensive")
    # If no filters requested, return empty so pytest.ini addopts remain in effect
    return " and ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run cliff_ai tests")
    parser.add_argument(
        "--module",
        dest="modules",
        action="append",
        help="Limit to one or more modules (repeatable). Known: "
        + ", ".join(m.name for m in discover_modules()),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List known modules and their test paths",
    )
    parser.add_argument("-k", dest="keyword", help="pytest -k expression", default=None)
    parser.add_argument("-v", dest="verbose", action="store_true", help="Verbose output")
    parser.add_argument("--api", action="store_true", help="Include API/network tests")
    parser.add_argument(
        "--expensive", action="store_true", help="Include expensive/slow tests"
    )

    args = parser.parse_args(argv)

    if args.list:
        for spec in discover_modules():
            tests = ", ".join(str(p) for p in spec.tests) or "<none>"
            print(f"{spec.name:12s} | tests: {tests}")
        return 0

    # Resolve module test paths
    specs = resolve_modules(args.modules)
    test_paths: List[str] = []
    for spec in specs:
        for p in spec.tests:
            test_paths.append(str(p))
    # Fallback to repo root if nothing explicit found
    if not test_paths:
        test_paths = [str(Path(__file__).resolve().parent.parent)]

    # Marker expression overrides pytest.ini defaults when passed explicitly
    marker_expr = build_marker_expr(include_api=args.api, include_expensive=args.expensive)

    pytest_args: List[str] = []
    # Only pass -m if we want to override pytest.ini addopts
    if marker_expr:
        pytest_args += ["-m", marker_expr]
    if args.keyword:
        pytest_args += ["-k", args.keyword]
    if args.verbose:
        pytest_args.append("-vv")
    pytest_args += test_paths

    # Lazy import pytest to allow --list without pytest installed
    import pytest  # type: ignore
    return pytest.main(pytest_args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
