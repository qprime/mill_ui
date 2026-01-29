#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from pml.yaml_parser import parse_pml_yaml, PMLParseError as ParseError
from pml import parse_pml
from pml.revision_header import update_file_header
from resolution.layout_resolver import resolve_layout
from cam.pipeline import run_pipeline, write_pipeline_outputs, DEFAULT_TOOL_DB
from adapters.ast_to_removal import ast_to_removal_intents


def discover_recipe_pml_files() -> list[Path]:
    recipes_dir = Path(__file__).parent.parent / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    pml_files = list(recipes_dir.glob("*/*.pml.yml"))
    return sorted(pml_files)


def generate_outputs_from_pml(pml_path: Path) -> tuple[Any, dict[str, str], dict[str, Any]]:
    parse_start = time.perf_counter()
    with open(pml_path, "r") as f:
        pml_source = f.read()

    try:
        comp_ast = parse_pml_yaml(pml_source)
        ast = resolve_layout(comp_ast)
    except ParseError:
        ast = parse_pml(pml_source)

    parse_time = time.perf_counter() - parse_start

    result = run_pipeline(
        ast,
        kerf_mm=3.175,
        min_channel_width_mm=6.0,
        tool_db=DEFAULT_TOOL_DB,
        generate_svg=True,
        svg_theme="dark",
    )

    metrics = result.metrics
    metrics["timing"]["parse_ms"] = round(parse_time * 1000, 2)
    metrics["timing"]["total_ms"] = round(
        parse_time * 1000 + metrics["timing"]["ir_ms"] + metrics["timing"]["hints_ms"] +
        metrics["timing"]["plan_ms"] + metrics["timing"]["gcode_ms"], 2
    )

    return ast, result.gcode, metrics


def write_outputs(
    output_dir: Path,
    recipe_name: str,
    ast: Any,
    gcode_dict: dict[str, str],
    metrics: dict[str, Any],
    pml_path: Path,
):
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for pass_name, gcode in gcode_dict.items():
        output_path = output_dir / f"{pass_name}.nc"
        with open(output_path, "w") as f:
            f.write(gcode)

    try:
        from export.blueprint_svg import render_blueprint_svg

        # Keep SVG aligned with the G-code toolpath by stamping in the kerf used
        # for this recipe run.
        ast_with_kerf = replace(ast, kerf_width_mm=3.175)
        removal_intents = ast_to_removal_intents(ast_with_kerf)
        svg_string = render_blueprint_svg(ast_with_kerf, removal_intents=removal_intents, theme="dark")
        recipe_dir_name = pml_path.parent.name
        svg_path = output_dir / f"{recipe_dir_name}.svg"
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_string)
    except Exception as e:
        print(f"  Warning: SVG generation failed: {e}")

    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)


def compare_outputs(
    output_dir: Path,
    gcode_dict: dict[str, str],
    metrics: dict[str, Any],
) -> tuple[bool, list[str]]:
    if not output_dir.exists():
        return False, [f"Output directory does not exist: {output_dir}"]

    diffs = []

    for pass_name, generated_gcode in gcode_dict.items():
        expected_path = output_dir / f"{pass_name}.nc"
        if not expected_path.exists():
            diffs.append(f"Missing expected file: {expected_path}")
            continue

        with open(expected_path, "r") as f:
            expected_gcode = f.read()

        if generated_gcode != expected_gcode:
            gen_lines = generated_gcode.split('\n')
            exp_lines = expected_gcode.split('\n')
            diff_count = sum(1 for g, e in zip(gen_lines, exp_lines) if g != e)
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
    ast, gcode_dict, metrics = generate_outputs_from_pml(pml_path)

    output_dir = pml_path.parent / "output"
    recipe_name = pml_path.stem

    if regenerate:
        write_outputs(output_dir, recipe_name, ast, gcode_dict, metrics, pml_path)
        print(f"\n  Regenerated recipe outputs for {pml_path.name}")
        print(f"  Output: {output_dir}")
        print(f"  Files: {len(gcode_dict)} G-code + SVG + metrics.json")
        print(f"  Total time: {metrics['timing']['total_ms']:.1f}ms")
    else:
        all_match, diffs = compare_outputs(output_dir, gcode_dict, metrics)

        if not all_match:
            diff_summary = "\n  ".join(diffs)
            raise AssertionError(
                f"Recipe output mismatch for {pml_path.name}:\n  {diff_summary}"
            )

        metrics_path = output_dir / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)


def test_recipe_outputs():
    print("Running test_recipe_outputs...")
    pml_files = discover_recipe_pml_files()

    if not pml_files:
        print("  SKIP: No recipe PML files found")
        return True

    all_passed = True
    for pml_path in pml_files:
        try:
            _test_recipe_output_impl(pml_path, regenerate=False)
            print(f"  {pml_path.name}: OK")
        except AssertionError as e:
            print(f"  {pml_path.name}: FAIL - {e}")
            all_passed = False
        except Exception as e:
            print(f"  {pml_path.name}: ERROR - {e}")
            all_passed = False

    if all_passed:
        print("  PASS")
        return True
    else:
        return False


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
                ast, gcode_dict, metrics = generate_outputs_from_pml(pml_path)
                output_dir = pml_path.parent / "output"
                recipe_name = pml_path.stem

                write_outputs(output_dir, recipe_name, ast, gcode_dict, metrics, pml_path)
                update_file_header(pml_path)

                print(f"  Generated {len(gcode_dict)} G-code pass(es) + SVG")
                print(f"  Total time: {metrics['timing']['total_ms']:.1f}ms")
                print(f"  Output: {output_dir}\n")
            except Exception as e:
                print(f"  FAILED: {e}\n")
                import traceback
                traceback.print_exc()

        print("Done!")
    else:
        tests = [
            test_recipe_outputs,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                if test():
                    passed += 1
            except Exception as e:
                print(f"  FAIL: {e}")
                failed += 1

        print(f"\n{passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)
