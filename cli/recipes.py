#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from cli.mill import write_recipe_outputs
from cli.nest import nest_job
from config.machine_loader import MachineConfig, load_machine_by_name
from ir.removal_intent import Bounds2D
from pml.yaml_parser import parse_nest_yaml
from validation.core import InvariantResult
from validation.machine_checks import check_job_fits_machine, check_sheet_fits_machine
from validation.recipe_docs import (
    document_problems,
    load_catalog,
    readme_problems,
    render_documents,
    uncatalogued_categories,
    unknown_recipe_names,
    write_documents,
)
from validation.recipes import OUTPUT_DIR_NAME, RECIPES_ROOT, Recipe, find_recipes, misplaced_inputs

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_MACHINE = "altmill_4x4"
MIN_NEST_UTILIZATION = 0.3
REGEN_HINT = "run `python -m cli.recipes --regen`"


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


def untracked_recipe_files(repo_root: Path, root: Path, documents: Iterable[Path]) -> list[str]:
    generated = {path.relative_to(repo_root).as_posix() for path in documents}
    listing = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", root.relative_to(repo_root).as_posix(), *generated],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in listing.stdout.splitlines() if f"/{OUTPUT_DIR_NAME}/" in path or path in generated]


def _fit_problems(result: InvariantResult, label: str) -> list[str]:
    return [f"{label} does not fit {RECIPE_MACHINE}: {failure}" for failure in result.failures]


def check_pml_recipe(recipe: Recipe, machine: MachineConfig) -> list[str]:
    with tempfile.TemporaryDirectory() as scratch:
        generated = Path(scratch) / OUTPUT_DIR_NAME
        runs, _ = write_recipe_outputs(recipe, generated)
        problems = compare_output_dirs(recipe.path / OUTPUT_DIR_NAME, generated)
    for run in runs:
        problems += _fit_problems(
            check_sheet_fits_machine(run.result.ast, machine), f"{run.source} sheet {run.sheet_index}"
        )
    return problems


def check_nest_recipe(recipe: Recipe, machine: MachineConfig) -> list[str]:
    problems: list[str] = []
    for source in recipe.nest_sources:
        job = parse_nest_yaml(source.read_text(encoding="utf-8"))
        bounds = Bounds2D(
            x_min=job.margin_mm,
            x_max=job.sheet_width_mm - job.margin_mm,
            y_min=job.margin_mm,
            y_max=job.sheet_height_mm - job.margin_mm,
        )
        problems += _fit_problems(check_job_fits_machine(bounds, machine), source.name)
        result = nest_job(job)
        if result["total_sheets"] == 0:
            problems.append(f"{source.name}: nesting produced 0 sheets")
        elif result["utilization"] < MIN_NEST_UTILIZATION:
            problems.append(f"{source.name}: utilization too low: {result['utilization'] * 100:.1f}%")
    return problems


def check_recipe(recipe: Recipe, machine: MachineConfig) -> list[str]:
    problems = readme_problems(recipe)
    if recipe.pml_sources:
        problems += check_pml_recipe(recipe, machine)
    if recipe.nest_sources:
        problems += check_nest_recipe(recipe, machine)
    return problems


def regenerate_recipe(recipe: Recipe) -> list[str]:
    write_recipe_outputs(recipe, recipe.path / OUTPUT_DIR_NAME)
    return []


def run_on_recipes(recipes: Sequence[Recipe], action: Callable[[Recipe], list[str]]) -> list[str]:
    failures: list[str] = []
    for recipe in recipes:
        try:
            problems = action(recipe)
        except Exception as e:
            problems = [f"{type(e).__name__}: {e}"]
        failures += [f"{recipe.name}: {problem}" for problem in problems]
    return failures


def check_tree(root: Path, machine: MachineConfig, repo_root: Path | None = None) -> list[str]:
    recipes = find_recipes(root)
    catalog = load_catalog(root)
    documents = render_documents(catalog, recipes, root)
    failures = [f"Misplaced input file: {path}" for path in misplaced_inputs(root)]
    failures += uncatalogued_categories(catalog, recipes)
    failures += unknown_recipe_names(catalog, recipes)
    failures += [f"{problem}; {REGEN_HINT}" for problem in document_problems(documents, root)]
    if repo_root is not None:
        failures += [f"Untracked recipe file: {path}" for path in untracked_recipe_files(repo_root, root, documents)]
    failures += run_on_recipes(recipes, lambda recipe: check_recipe(recipe, machine))
    return failures


def regenerate_tree(root: Path) -> list[str]:
    recipes = find_recipes(root)
    catalog = load_catalog(root)
    failures = run_on_recipes([recipe for recipe in recipes if recipe.pml_sources], regenerate_recipe)
    write_documents(render_documents(catalog, recipes, root), root)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that every recipe's committed output/ and the generated recipe documents match current code",
        epilog="Without --regen, writes nothing. Also runs as the recipe-outputs pre-commit hook.",
    )
    parser.add_argument(
        "--regen",
        action="store_true",
        help="Rewrite every recipe's output/, the recipe index, category READMEs and the feature guide",
    )
    args = parser.parse_args()

    recipe_count = len(find_recipes(RECIPES_ROOT))
    if args.regen:
        failures = regenerate_tree(RECIPES_ROOT)
        for failure in failures:
            print(f"  FAILED: {failure}", file=sys.stderr)
        print(f"Regenerated {recipe_count} recipe(s) and the recipe documents: {len(failures)} failure(s)")
        return 1 if failures else 0

    failures = check_tree(RECIPES_ROOT, load_machine_by_name(RECIPE_MACHINE), REPO_ROOT)
    for failure in failures:
        print(f"  FAIL: {failure}", file=sys.stderr)
    print(f"Checked {recipe_count} recipe(s): {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
