#!/usr/bin/env python3

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cam.pipeline import PipelineResult, run_pipeline, write_pipeline_outputs
from pml import parse_pml
from pml.revision_header import update_file_header
from pml.yaml_parser import PMLParseError as ParseError
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout_multi


def discover_recipe_pml_files() -> list[Path]:
    recipes_dir = Path(__file__).parent.parent / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    pml_files = list(recipes_dir.glob("*/*.pml.yml"))
    return sorted(pml_files)


def generate_outputs_from_pml(pml_path: Path) -> PipelineResult:
    with open(pml_path) as f:
        pml_source = f.read()

    try:
        comp_ast = parse_pml_yaml(pml_source)
        comp_ast = replace(comp_ast, source_dir=str(pml_path.parent.resolve()))
        asts = resolve_layout_multi(comp_ast)
    except ParseError:
        asts = [parse_pml(pml_source)]

    combined_gcode: dict[str, str] = {}
    multi_sheet = len(asts) > 1
    sheet_metrics: list[dict[str, Any]] = []
    last_result: PipelineResult | None = None

    for sheet_idx, ast in enumerate(asts):
        result = run_pipeline(
            ast,
            kerf_mm=3.175,
            min_channel_width_mm=6.0,
            generate_svg=True,
            svg_theme="dark",
        )

        if multi_sheet:
            prefix = f"sheet_{sheet_idx + 1}."
            for pass_name, gcode in result.gcode.items():
                combined_gcode[f"{prefix}{pass_name}"] = gcode
        else:
            combined_gcode = dict(result.gcode)

        sheet_metrics.append(result.metrics)
        last_result = result

    assert last_result is not None

    if multi_sheet:
        metrics: dict[str, Any] = {
            "total_sheets": len(asts),
            "sheets": sheet_metrics,
            "timing": {"total_ms": sum(m["timing"]["total_ms"] for m in sheet_metrics)},
        }
    else:
        metrics = sheet_metrics[0]

    return replace(last_result, gcode=combined_gcode, metrics=metrics)


def compare_outputs(
    output_dir: Path,
    result: PipelineResult,
) -> tuple[bool, list[str]]:
    if not output_dir.exists():
        return False, [f"Output directory does not exist: {output_dir}"]

    diffs = []

    for pass_name, generated_gcode in result.gcode.items():
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

    expected_extensions = {".nc", ".svg", ".json"}
    actual_files = {f.name for f in output_dir.iterdir() if f.is_file()}
    extra_files = {f for f in actual_files if not any(f.endswith(ext) for ext in expected_extensions)}
    if extra_files:
        diffs.append(f"Extra files in output directory: {extra_files}")

    return len(diffs) == 0, diffs


def _test_recipe_output_impl(pml_path: Path, regenerate: bool = False):
    result = generate_outputs_from_pml(pml_path)

    output_dir = pml_path.parent / "output"

    if regenerate:
        write_pipeline_outputs(result, output_dir, pml_path.parent.name)
        print(f"\n  Regenerated recipe outputs for {pml_path.name}")
        print(f"  Output: {output_dir}")
        print(f"  Files: {len(result.gcode)} G-code + SVG + metrics.json")
        print(f"  Total time: {result.metrics['timing']['total_ms']:.1f}ms")
    else:
        all_match, diffs = compare_outputs(output_dir, result)

        if not all_match:
            diff_summary = "\n  ".join(diffs)
            raise AssertionError(f"Recipe output mismatch for {pml_path.name}:\n  {diff_summary}")


def validate_recipes(pml_files: list[Path]) -> list[str]:
    failures = []
    for pml_path in pml_files:
        try:
            _test_recipe_output_impl(pml_path, regenerate=False)
        except Exception as e:
            failures.append(f"{pml_path.name}: {e}")

    return failures


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
                result = generate_outputs_from_pml(pml_path)
                output_dir = pml_path.parent / "output"

                write_pipeline_outputs(result, output_dir, pml_path.parent.name)
                update_file_header(pml_path)

                print(f"  Generated {len(result.gcode)} G-code pass(es) + SVG")
                print(f"  Total time: {result.metrics['timing']['total_ms']:.1f}ms")
                print(f"  Output: {output_dir}\n")
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
