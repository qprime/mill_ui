#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from io import StringIO
from pathlib import Path
from typing import Any

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    pytest = None

from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.parser import parse_pml
from resolution.layout_resolver import resolve_layout
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode


try:
    from adapters.ast_to_cad import items_to_shape_dicts
    from cad.export.stl import export_stl
    STL_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    STL_AVAILABLE = False

try:
    from export.blueprint_svg import render_blueprint_svg
    SVG_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    SVG_AVAILABLE = False


RECIPE_TOOL_DB = [
    {
        "name": "1_8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    },
    {
        "name": "1_4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 800,
        "feed_z": 280,
    },
    {
        "name": "3_8_endmill",
        "diameter": 9.525,
        "kind": "flat",
        "rpm": 10000,
        "feed_xy": 700,
        "feed_z": 250,
    },
]


def pytest_addoption(parser):
    if not PYTEST_AVAILABLE:
        return
    parser.addoption(
        "--regen_recipes",
        action="store_true",
        default=False,
        help="Regenerate recipe artifacts instead of comparing",
    )


def discover_recipe_pml_files() -> list[Path]:
    recipes_dir = Path(__file__).parent.parent / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    pml_files = list(recipes_dir.glob("*/*.pml"))
    return sorted(pml_files)


def generate_outputs_from_pml(pml_path: Path) -> tuple[Any, dict[str, str], dict[str, Any]]:

    parse_start = time.perf_counter()
    with open(pml_path, "r") as f:
        pml_source = f.read()

    try:

        comp_ast = parse_compositional_pml(pml_source)
        ast = resolve_layout(comp_ast)
    except ParseError:

        ast = parse_pml(pml_source)

    parse_time = time.perf_counter() - parse_start


    ir_start = time.perf_counter()
    intents = ast_to_removal_intents(ast)
    ir_time = time.perf_counter() - ir_start


    hints_start = time.perf_counter()
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
    hints_time = time.perf_counter() - hints_start


    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    plan_start = time.perf_counter()
    passes, _ = plan_passes(
        hints,
        config=Config(),
        tool_db=RECIPE_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )
    plan_time = time.perf_counter() - plan_start


    gcode_start = time.perf_counter()
    gcode_dict = {}
    total_moves = 0
    total_rapid_moves = 0
    total_cut_moves = 0

    for pass_dict in passes:

        setup = pass_dict["setup"]
        gcode = write_gcode(
            pass_dict["moves"],
            safe_z=setup.safe_z,
        )


        tool_diameter = setup.tool.diameter
        pass_name = f"{pass_dict['op']}-{tool_diameter:.2f}mm"
        gcode_dict[pass_name] = gcode


        moves = pass_dict["moves"]
        total_moves += len(moves)
        for move in moves:
            if isinstance(move, dict) and move.get('is_rapid'):
                total_rapid_moves += 1
            else:
                total_cut_moves += 1

    gcode_time = time.perf_counter() - gcode_start


    total_time = parse_time + ir_time + hints_time + plan_time + gcode_time
    total_gcode_size = sum(len(gc) for gc in gcode_dict.values())
    total_gcode_lines = sum(gc.count('\n') for gc in gcode_dict.values())

    metrics = {
        "timing": {
            "parse_ms": round(parse_time * 1000, 2),
            "ir_ms": round(ir_time * 1000, 2),
            "hints_ms": round(hints_time * 1000, 2),
            "plan_ms": round(plan_time * 1000, 2),
            "gcode_ms": round(gcode_time * 1000, 2),
            "total_ms": round(total_time * 1000, 2),
        },
        "complexity": {
            "total_moves": total_moves,
            "rapid_moves": total_rapid_moves,
            "cut_moves": total_cut_moves,
            "rapid_ratio": round(total_rapid_moves / total_moves, 3) if total_moves > 0 else 0,
        },
        "fidelity": {
            "tool_changes": len(passes),
            "passes": [
                {
                    "name": p["op"],
                    "tool_diameter_mm": p["setup"].tool.diameter,
                    "move_count": len(p["moves"]),
                }
                for p in passes
            ],
        },
        "output_size": {
            "total_bytes": total_gcode_size,
            "total_lines": total_gcode_lines,
            "files": {
                name: {
                    "bytes": len(gcode),
                    "lines": gcode.count('\n'),
                }
                for name, gcode in gcode_dict.items()
            },
        },
    }

    return ast, gcode_dict, metrics


def write_outputs(
    output_dir: Path,
    recipe_name: str,
    ast: Any,
    gcode_dict: dict[str, str],
    metrics: dict[str, Any]
):
    output_dir.mkdir(parents=True, exist_ok=True)


    for pass_name, gcode in gcode_dict.items():
        output_path = output_dir / f"{pass_name}.nc"
        with open(output_path, "w") as f:
            f.write(gcode)


    if STL_AVAILABLE:
        try:
            shapes = items_to_shape_dicts(ast.items)
            stl_path = output_dir / f"{recipe_name}.stl"
            export_stl(
                shapes=shapes,
                sheet_thickness_mm=ast.sheet.thickness_mm,
                output_path=stl_path,
            )
        except Exception as e:
            print(f"  Warning: STL generation failed: {e}")
    else:
        print(f"  Warning: STL generation skipped (trimesh not available)")


    if SVG_AVAILABLE:
        try:
            svg_string = render_blueprint_svg(ast, theme="dark")

            recipe_dir_name = pml_path.parent.name
            svg_path = output_dir / f"{recipe_dir_name}.svg"
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_string)
        except Exception as e:
            print(f"  Warning: SVG generation failed: {e}")
    else:
        print(f"  Warning: SVG generation skipped (module not available)")


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


    expected_files = {f"{name}.nc" for name in gcode_dict.keys()}
    expected_files.add("metrics.json")
    actual_files = {f.name for f in output_dir.glob("*.nc")}
    actual_files.add("metrics.json")

    extra_files = actual_files - expected_files
    if extra_files:
        diffs.append(f"Extra files in output directory: {extra_files}")

    return len(diffs) == 0, diffs


if PYTEST_AVAILABLE:
    @pytest.mark.parametrize("pml_path", discover_recipe_pml_files())
    def test_recipe_output(pml_path: Path, request):
        _test_recipe_output_impl(pml_path, request.config.getoption("--regen_recipes"))


def _test_recipe_output_impl(pml_path: Path, regenerate: bool = False):

    ast, gcode_dict, metrics = generate_outputs_from_pml(pml_path)


    output_dir = pml_path.parent / "output"
    recipe_name = pml_path.stem

    if regenerate:

        write_outputs(output_dir, recipe_name, ast, gcode_dict, metrics)
        print(f"\n✓ Regenerated recipe outputs for {pml_path.name}")
        print(f"  Output: {output_dir}")
        print(f"  Files: {len(gcode_dict)} G-code + STL + SVG + metrics.json")
        print(f"  Total time: {metrics['timing']['total_ms']:.1f}ms")
    else:

        all_match, diffs = compare_outputs(output_dir, gcode_dict, metrics)

        if not all_match:
            diff_summary = "\n  ".join(diffs)
            if PYTEST_AVAILABLE:
                pytest.fail(
                    f"Recipe output mismatch for {pml_path.name}:\n  {diff_summary}\n\n"
                    f"To update recipe outputs, run:\n"
                    f"  pytest tests/test_recipe_outputs.py --regen_recipes"
                )
            else:
                raise AssertionError(
                    f"Recipe output mismatch for {pml_path.name}:\n  {diff_summary}"
                )


        metrics_path = output_dir / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)


if __name__ == "__main__":
    """Standalone runner for quick testing."""
    print("Discovering recipe PML files...")
    pml_files = discover_recipe_pml_files()
    print(f"Found {len(pml_files)} recipe(s):\n")

    for pml_path in pml_files:
        print(f"Processing: {pml_path.relative_to(Path.cwd())}")
        try:
            ast, gcode_dict, metrics = generate_outputs_from_pml(pml_path)
            output_dir = pml_path.parent / "output"
            recipe_name = pml_path.stem

            write_outputs(output_dir, recipe_name, ast, gcode_dict, metrics)

            print(f"  ✓ Generated {len(gcode_dict)} G-code pass(es) + STL + SVG")
            print(f"  ✓ Total time: {metrics['timing']['total_ms']:.1f}ms")
            print(f"  ✓ Output: {output_dir}\n")
        except Exception as e:
            print(f"  ✗ FAILED: {e}\n")
            import traceback
            traceback.print_exc()

    print("Done!")
