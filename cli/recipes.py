#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from cli.mill import write_recipe_outputs
from cli.nest import nest_job
from pml.yaml_parser import parse_nest_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = REPO_ROOT / "docs" / "recipes"
MIN_NEST_UTILIZATION = 0.3


def find_pml_sources(recipes_dir: Path = RECIPES_DIR) -> list[Path]:
    return sorted(recipes_dir.glob("*/*.pml.yml"))


def find_nest_sources(recipes_dir: Path = RECIPES_DIR) -> list[Path]:
    return sorted(recipes_dir.glob("*/*.nest.yml"))


def _changed_line_count(committed: str, generated: str) -> tuple[int, int, int]:
    committed_lines = committed.split("\n")
    generated_lines = generated.split("\n")
    changed = sum(1 for c, g in zip(committed_lines, generated_lines, strict=False) if c != g)
    changed += abs(len(committed_lines) - len(generated_lines))
    return changed, len(generated_lines), len(committed_lines)


def compare_output_dirs(committed: Path, generated: Path) -> list[str]:
    if not committed.is_dir():
        return [f"Output directory does not exist: {committed}"]

    committed_names = {entry.name for entry in committed.iterdir()}
    generated_names = {entry.name for entry in generated.iterdir()}

    diffs = [f"Missing generated file: {name}" for name in sorted(generated_names - committed_names)]
    diffs += [f"File no longer generated: {name}" for name in sorted(committed_names - generated_names)]

    for name in sorted(committed_names & generated_names):
        committed_text = (committed / name).read_text(encoding="utf-8")
        generated_text = (generated / name).read_text(encoding="utf-8")
        if committed_text != generated_text:
            changed, generated_count, committed_count = _changed_line_count(committed_text, generated_text)
            diffs.append(
                f"{name} differs: {changed} lines changed ({generated_count} generated vs {committed_count} committed)"
            )

    return diffs


def untracked_recipe_outputs(repo_root: Path) -> list[str]:
    listing = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "docs/recipes"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in listing.stdout.splitlines() if "/output/" in path]


def check_pml_recipe(source: Path) -> list[str]:
    with tempfile.TemporaryDirectory() as scratch:
        generated = Path(scratch) / "output"
        write_recipe_outputs(source, source.parent.name, generated)
        return compare_output_dirs(source.parent / "output", generated)


def check_nest_recipe(source: Path) -> list[str]:
    result = nest_job(parse_nest_yaml(source.read_text(encoding="utf-8")))
    if result["total_sheets"] == 0:
        return ["Nesting produced 0 sheets"]
    if result["utilization"] < MIN_NEST_UTILIZATION:
        return [f"Utilization too low: {result['utilization'] * 100:.1f}%"]
    return []


def regenerate_pml_recipe(source: Path) -> list[str]:
    write_recipe_outputs(source, source.parent.name, source.parent / "output")
    return []


def run_on_recipes(sources: list[Path], action: Callable[[Path], list[str]]) -> list[str]:
    failures: list[str] = []
    for source in sources:
        try:
            problems = action(source)
        except Exception as e:
            problems = [f"{type(e).__name__}: {e}"]
        failures += [f"{source.parent.name}: {problem}" for problem in problems]
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that every recipe's committed output/ matches what current code generates",
        epilog="Without --regen, writes nothing. Also runs as the recipe-outputs pre-commit hook.",
    )
    parser.add_argument("--regen", action="store_true", help="Rewrite every recipe's output/ from current code")
    args = parser.parse_args()

    pml_sources = find_pml_sources()
    if not pml_sources:
        print(f"No recipe PML files found under {RECIPES_DIR}", file=sys.stderr)
        return 1

    if args.regen:
        failures = run_on_recipes(pml_sources, regenerate_pml_recipe)
        for failure in failures:
            print(f"  FAILED: {failure}", file=sys.stderr)
        print(f"Regenerated {len(pml_sources) - len(failures)} of {len(pml_sources)} recipe(s)")
        return 1 if failures else 0

    nest_sources = find_nest_sources()
    failures = [f"Untracked recipe output: {path}" for path in untracked_recipe_outputs(REPO_ROOT)]
    failures += run_on_recipes(pml_sources, check_pml_recipe)
    failures += run_on_recipes(nest_sources, check_nest_recipe)
    for failure in failures:
        print(f"  FAIL: {failure}", file=sys.stderr)
    print(f"Checked {len(pml_sources) + len(nest_sources)} recipe(s): {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
