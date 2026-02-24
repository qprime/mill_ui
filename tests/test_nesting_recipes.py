#!/usr/bin/env python3

from __future__ import annotations

import time
from pathlib import Path

import pytest

from nesting import nest_and_generate
from pml.nest_parser import nest_job_to_api_params
from pml.yaml_parser import parse_nest_yaml


def discover_nest_files() -> list[Path]:
    recipes_dir = Path(__file__).parent.parent / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    nest_files = list(recipes_dir.glob("*/*.nest.yml"))
    return sorted(nest_files)


def _run_nest_file(nest_path: Path) -> tuple[bool, str, dict]:
    try:
        source = nest_path.read_text()
        job = parse_nest_yaml(source)

        params = nest_job_to_api_params(job)

        start = time.perf_counter()
        result = nest_and_generate(**params, output_format="ast")
        elapsed = time.perf_counter() - start

        metrics = {
            "algorithm": job.algorithm,
            "total_parts": sum(p.quantity for p in job.parts),
            "total_sheets": result["total_sheets"],
            "utilization": f"{result['utilization'] * 100:.1f}%",
            "time_ms": round(elapsed * 1000, 2),
        }

        if result["total_sheets"] == 0:
            return False, "Nesting produced 0 sheets", metrics

        if result["utilization"] < 0.3:
            return False, f"Utilization too low: {metrics['utilization']}", metrics

        return True, "OK", metrics

    except Exception as e:
        return False, str(e), {}


NEST_FILES = discover_nest_files()


@pytest.mark.skipif(not NEST_FILES, reason="No .nest.yml files found in docs/recipes/")
@pytest.mark.parametrize("nest_path", NEST_FILES, ids=lambda p: p.stem)
def test_nest_file(nest_path: Path):
    success, message, _metrics = _run_nest_file(nest_path)
    if not success:
        pytest.fail(message)


def run_nesting_recipe_tests():
    print("=" * 60)
    print("Nesting Recipe Tests (.nest files)")
    print("=" * 60)

    nest_files = discover_nest_files()

    if not nest_files:
        print("No .nest.yml files found in docs/recipes/")
        return True

    print(f"Found {len(nest_files)} .nest.yml file(s)\n")

    passed = 0
    failed = 0

    for nest_path in nest_files:
        rel_path = nest_path.relative_to(Path(__file__).parent.parent)
        print(f"Testing: {rel_path}")

        success, message, metrics = _run_nest_file(nest_path)

        if success:
            print(
                f"  ✓ PASS - {metrics['algorithm']}: {metrics['total_parts']} parts → {metrics['total_sheets']} sheets ({metrics['utilization']} util, {metrics['time_ms']}ms)"
            )
            passed += 1
        else:
            print(f"  ✗ FAIL - {message}")
            failed += 1

    print()
    print(f"Results: {passed}/{passed + failed} passed")

    return failed == 0


if __name__ == "__main__":
    import sys

    success = run_nesting_recipe_tests()
    sys.exit(0 if success else 1)
