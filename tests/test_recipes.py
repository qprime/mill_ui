#!/usr/bin/env python3

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from cam.pipeline import SheetRun, run_sheets, write_run_outputs
from pml import parse_pml
from pml.yaml_parser import PMLParseError as ParseError
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout_multi


def discover_recipe_pml_files() -> list[Path]:
    recipes_dir = Path(__file__).parent.parent / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    pml_files = list(recipes_dir.glob("*/*.pml.yml"))
    return sorted(pml_files)


RECIPE_BUILD_PARAMS = {
    "kerf_mm": 3.175,
    "theme": "dark",
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
        kerf_mm=RECIPE_BUILD_PARAMS["kerf_mm"],
        min_channel_width_mm=6.0,
        generate_svg=True,
        svg_theme=RECIPE_BUILD_PARAMS["theme"],
    )


def combined_gcode(runs: Sequence[SheetRun]) -> dict[str, str]:
    return {name: gcode for run in runs for name, gcode in run.result.gcode.items()}


def write_recipe_outputs(pml_path: Path, runs: Sequence[SheetRun]) -> None:
    write_run_outputs(runs, pml_path.parent / "output", build_params=RECIPE_BUILD_PARAMS)


def compare_outputs(
    output_dir: Path,
    gcode: Mapping[str, str],
) -> tuple[bool, list[str]]:
    if not output_dir.exists():
        return False, [f"Output directory does not exist: {output_dir}"]

    diffs = []

    for pass_name, generated_gcode in gcode.items():
        expected_path = output_dir / f"{pass_name}.nc"
        if not expected_path.exists():
            diffs.append(f"Missing expected file: {expected_path}")
            continue

        with open(expected_path) as f:
            expected_gcode = f.read()

        if generated_gcode != expected_gcode:
            gen_lines = generated_gcode.split("\n")
            exp_lines = expected_gcode.split("\n")
            diff_count = sum(1 for g, e in zip(gen_lines, exp_lines, strict=False) if g != e)
            diff_count += abs(len(gen_lines) - len(exp_lines))
            diffs.append(
                f"{pass_name}.nc differs: {diff_count} lines changed "
                f"({len(gen_lines)} generated vs {len(exp_lines)} expected)"
            )

    generated_files = {f"{pass_name}.nc" for pass_name in gcode}
    ungenerated = sorted(f.name for f in output_dir.glob("*.nc") if f.name not in generated_files)
    if ungenerated:
        diffs.append(f"Expected G-code no longer generated: {ungenerated}")

    expected_extensions = {".nc", ".svg", ".json"}
    actual_files = {f.name for f in output_dir.iterdir() if f.is_file()}
    extra_files = {f for f in actual_files if not any(f.endswith(ext) for ext in expected_extensions)}
    if extra_files:
        diffs.append(f"Extra files in output directory: {extra_files}")

    return len(diffs) == 0, diffs


def _test_recipe_output_impl(pml_path: Path) -> None:
    runs = generate_outputs_from_pml(pml_path)
    all_match, diffs = compare_outputs(pml_path.parent / "output", combined_gcode(runs))

    if not all_match:
        diff_summary = "\n  ".join(diffs)
        raise AssertionError(f"Recipe output mismatch for {pml_path.name}:\n  {diff_summary}")


def validate_recipes(pml_files: list[Path]) -> list[str]:
    failures = []
    for pml_path in pml_files:
        try:
            _test_recipe_output_impl(pml_path)
        except Exception as e:
            failures.append(f"{pml_path.name}: {e}")

    return failures


def test_compare_outputs_flags_expected_gcode_no_longer_generated(tmp_path: Path):
    (tmp_path / "pocket-3.17mm.nc").write_text("G0\n")
    (tmp_path / "profile-3.17mm.nc").write_text("G1\n")
    matches, diffs = compare_outputs(tmp_path, {"profile-3.17mm": "G1\n"})

    assert not matches
    assert diffs == ["Expected G-code no longer generated: ['pocket-3.17mm.nc']"]


def test_recipe_outputs():
    pml_files = discover_recipe_pml_files()

    if not pml_files:
        pytest.skip("No recipe PML files found")

    failures = validate_recipes(pml_files)

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

        failures = validate_recipes(pml_files)

        for failure in failures:
            print(f"  FAIL: {failure}")

        print(f"\n{len(pml_files) - len(failures)} passed, {len(failures)} failed")
        sys.exit(1 if failures else 0)
