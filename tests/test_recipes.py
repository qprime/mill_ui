#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from cam.pipeline import SheetRun, run_sheets, write_run_outputs
from cli.mill import RECIPE_KERF_MM, RECIPE_THEME
from pml import parse_pml
from pml.yaml_parser import PMLParseError as ParseError
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout_multi

REPO_ROOT = Path(__file__).parent.parent


def discover_recipe_pml_files() -> list[Path]:
    recipes_dir = REPO_ROOT / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    pml_files = list(recipes_dir.glob("*/*.pml.yml"))
    return sorted(pml_files)


RECIPE_BUILD_PARAMS = {
    "kerf_mm": RECIPE_KERF_MM,
    "theme": RECIPE_THEME,
    "y_origin": "back",
}


def generate_outputs_from_pml(pml_path: Path) -> list[SheetRun]:
    with open(pml_path) as f:
        pml_source = f.read()

    try:
        comp_ast = parse_pml_yaml(pml_source)
        comp_ast = replace(comp_ast, source_dir=str(pml_path.parent.resolve()))
        asts = resolve_layout_multi(comp_ast)
    except ParseError:
        asts = [parse_pml(pml_source)]

    return run_sheets(
        asts,
        source=pml_path.name,
        job_stem=pml_path.parent.name,
        kerf_mm=RECIPE_KERF_MM,
        generate_svg=True,
        svg_theme=RECIPE_THEME,
    )


def combined_gcode(runs: Sequence[SheetRun]) -> dict[str, str]:
    return {name: gcode for run in runs for name, gcode in run.result.gcode.items()}


def write_recipe_outputs(pml_path: Path, runs: Sequence[SheetRun]) -> None:
    write_run_outputs(runs, pml_path.parent / "output", build_params=RECIPE_BUILD_PARAMS)


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


def _test_recipe_output_impl(pml_path: Path) -> None:
    runs = generate_outputs_from_pml(pml_path)
    with tempfile.TemporaryDirectory() as scratch:
        generated_dir = Path(scratch) / "output"
        write_run_outputs(runs, generated_dir, build_params=RECIPE_BUILD_PARAMS)
        diffs = compare_output_dirs(pml_path.parent / "output", generated_dir)

    if diffs:
        diff_summary = "\n  ".join(diffs)
        raise AssertionError(f"Recipe output mismatch for {pml_path.parent.name}:\n  {diff_summary}")


def untracked_output_failures() -> list[str]:
    return [f"Untracked recipe output: {path}" for path in untracked_recipe_outputs(REPO_ROOT)]


def validate_recipes(pml_files: list[Path]) -> list[str]:
    failures = []
    for pml_path in pml_files:
        try:
            _test_recipe_output_impl(pml_path)
        except Exception as e:
            failures.append(f"{pml_path.parent.name}: {e}")

    return failures


def _write_dir(directory: Path, files: Mapping[str, str]) -> Path:
    directory.mkdir(parents=True)
    for name, text in files.items():
        (directory / name).write_text(text)
    return directory


def test_compare_output_dirs_flags_changed_svg(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"profile-3.17mm.nc": "G1\n", "door.svg": "<svg>a</svg>"})
    generated = _write_dir(tmp_path / "generated", {"profile-3.17mm.nc": "G1\n", "door.svg": "<svg>b</svg>"})

    assert compare_output_dirs(committed, generated) == [
        "door.svg differs: 1 lines changed (1 generated vs 1 committed)"
    ]


def test_compare_output_dirs_flags_changed_metrics(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"metrics.json": '{"errors": []}'})
    generated = _write_dir(tmp_path / "generated", {"metrics.json": '{"errors": ["too deep"]}'})

    assert compare_output_dirs(committed, generated) == [
        "metrics.json differs: 1 lines changed (1 generated vs 1 committed)"
    ]


def test_compare_output_dirs_flags_file_no_longer_generated(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"pocket-3.17mm.nc": "G0\n", "profile-3.17mm.nc": "G1\n"})
    generated = _write_dir(tmp_path / "generated", {"profile-3.17mm.nc": "G1\n"})

    assert compare_output_dirs(committed, generated) == ["File no longer generated: pocket-3.17mm.nc"]


def test_compare_output_dirs_flags_missing_file(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"profile-3.17mm.nc": "G1\n"})
    generated = _write_dir(tmp_path / "generated", {"profile-3.17mm.nc": "G1\n", "machining_summary.json": "{}"})

    assert compare_output_dirs(committed, generated) == ["Missing generated file: machining_summary.json"]


def test_compare_output_dirs_accepts_identical_dirs(tmp_path: Path):
    files = {"profile-3.17mm.nc": "G1\n", "door.svg": "<svg/>", "metrics.json": "{}"}
    committed = _write_dir(tmp_path / "committed", files)
    generated = _write_dir(tmp_path / "generated", files)

    assert compare_output_dirs(committed, generated) == []


def test_untracked_recipe_outputs_lists_new_output_file(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    output_dir = _write_dir(tmp_path / "docs" / "recipes" / "x" / "output", {"a.nc": "G0\n", "b.svg": "<svg/>"})
    _write_dir(tmp_path / "docs" / "recipes" / "x" / "src", {"example.pml.yml": "Sheet: {}"})
    subprocess.run(["git", "add", str(output_dir / "a.nc")], cwd=tmp_path, check=True)

    assert untracked_recipe_outputs(tmp_path) == ["docs/recipes/x/output/b.svg"]


def test_recipe_outputs():
    pml_files = discover_recipe_pml_files()

    if not pml_files:
        pytest.skip("No recipe PML files found")

    failures = untracked_output_failures() + validate_recipes(pml_files)

    if failures:
        raise AssertionError("Recipe output mismatches:\n  " + "\n  ".join(failures))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test recipe outputs")
    parser.add_argument(
        "--regen_recipes",
        action="store_true",
        help="Regenerate recipe artifacts instead of comparing",
    )
    args = parser.parse_args()

    if args.regen_recipes:
        print("Discovering recipe PML files...")
        pml_files = discover_recipe_pml_files()
        print(f"Found {len(pml_files)} recipe(s):\n")

        for pml_path in pml_files:
            print(f"Processing: {pml_path.relative_to(Path.cwd())}")
            try:
                runs = generate_outputs_from_pml(pml_path)
                write_recipe_outputs(pml_path, runs)

                total_ms = sum(run.result.metrics["timing"]["total_ms"] for run in runs)
                print(f"  Generated {len(combined_gcode(runs))} G-code pass(es) + SVG")
                print(f"  Total time: {total_ms:.1f}ms")
                print(f"  Output: {pml_path.parent / 'output'}\n")
            except Exception as e:
                print(f"  FAILED: {e}\n")
                import traceback

                traceback.print_exc()

        print("Done!")
    else:
        pml_files = discover_recipe_pml_files()

        if not pml_files:
            print("No recipe PML files found under docs/recipes/")
            sys.exit(1)

        print(f"Validating {len(pml_files)} recipe(s)...")

        untracked = untracked_output_failures()
        failures = validate_recipes(pml_files)

        for failure in untracked + failures:
            print(f"  FAIL: {failure}")

        print(f"\n{len(pml_files) - len(failures)} passed, {len(failures)} failed")
        sys.exit(1 if untracked or failures else 0)
