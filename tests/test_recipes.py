#!/usr/bin/env python3
"""Recipe output tests.

Auto-discovers PML files in docs/recipes/*/, generates G-code output,
and compares against committed artifacts. Tracks metrics for performance
and quality regression detection.

Usage:
    pytest tests/test_recipes.py                    # Verify outputs match
    pytest tests/test_recipes.py --regen_recipes    # Regenerate artifacts
"""

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


# Standard tool database for recipes
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
    """Add --regen_recipes flag to pytest."""
    if not PYTEST_AVAILABLE:
        return
    parser.addoption(
        "--regen_recipes",
        action="store_true",
        default=False,
        help="Regenerate recipe artifacts instead of comparing",
    )


def discover_recipe_pml_files() -> list[Path]:
    """Auto-discover all PML files in docs/recipes/*/."""
    recipes_dir = Path(__file__).parent.parent / "docs" / "recipes"
    if not recipes_dir.exists():
        return []

    pml_files = list(recipes_dir.glob("*/*.pml"))
    return sorted(pml_files)


def generate_gcode_from_pml(pml_path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    """Generate G-code from PML file.

    Returns:
        (gcode_dict, metrics_dict) where gcode_dict maps pass_name -> gcode_string
    """
    # Parse PML - try compositional first, fall back to flat
    parse_start = time.perf_counter()
    with open(pml_path, "r") as f:
        pml_source = f.read()

    try:
        # Try compositional parser first
        comp_ast = parse_compositional_pml(pml_source)
        ast = resolve_layout(comp_ast)
    except ParseError:
        # Fall back to flat parser
        ast = parse_pml(pml_source)

    parse_time = time.perf_counter() - parse_start

    # Convert to RemovalIntent IR
    ir_start = time.perf_counter()
    intents = ast_to_removal_intents(ast)
    ir_time = time.perf_counter() - ir_start

    # Convert to planner hints
    hints_start = time.perf_counter()
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
    hints_time = time.perf_counter() - hints_start

    # Plan passes
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

    # Generate G-code for each pass
    gcode_start = time.perf_counter()
    gcode_dict = {}
    total_moves = 0
    total_rapid_moves = 0
    total_cut_moves = 0

    for pass_dict in passes:
        # Generate G-code using basic write_gcode API
        setup = pass_dict["setup"]
        gcode = write_gcode(
            pass_dict["moves"],
            safe_z=setup.safe_z,
        )

        # Generate pass name from tool and operation
        tool_diameter = setup.tool.diameter
        pass_name = f"{pass_dict['op']}-{tool_diameter:.2f}mm"
        gcode_dict[pass_name] = gcode

        # Count move types
        moves = pass_dict["moves"]
        total_moves += len(moves)
        for move in moves:
            if isinstance(move, dict) and move.get('is_rapid'):
                total_rapid_moves += 1
            else:
                total_cut_moves += 1

    gcode_time = time.perf_counter() - gcode_start

    # Compute metrics
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

    return gcode_dict, metrics


def write_outputs(output_dir: Path, gcode_dict: dict[str, str], metrics: dict[str, Any]):
    """Write G-code files and metrics to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write G-code files
    for pass_name, gcode in gcode_dict.items():
        output_path = output_dir / f"{pass_name}.nc"
        with open(output_path, "w") as f:
            f.write(gcode)

    # Write metrics
    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)


def compare_outputs(
    output_dir: Path,
    gcode_dict: dict[str, str],
    metrics: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Compare generated outputs against committed artifacts.

    Returns:
        (all_match, diff_messages)
    """
    if not output_dir.exists():
        return False, [f"Output directory does not exist: {output_dir}"]

    diffs = []

    # Compare G-code files
    for pass_name, generated_gcode in gcode_dict.items():
        expected_path = output_dir / f"{pass_name}.nc"
        if not expected_path.exists():
            diffs.append(f"Missing expected file: {expected_path}")
            continue

        with open(expected_path, "r") as f:
            expected_gcode = f.read()

        if generated_gcode != expected_gcode:
            # Count differing lines for summary
            gen_lines = generated_gcode.split('\n')
            exp_lines = expected_gcode.split('\n')
            diff_count = sum(1 for g, e in zip(gen_lines, exp_lines) if g != e)
            diff_count += abs(len(gen_lines) - len(exp_lines))
            diffs.append(
                f"{pass_name}.nc differs: {diff_count} lines changed "
                f"({len(gen_lines)} generated vs {len(exp_lines)} expected)"
            )

    # Check for extra files in output directory
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
        """Test that recipe generates expected G-code output."""
        _test_recipe_output_impl(pml_path, request.config.getoption("--regen_recipes"))


def _test_recipe_output_impl(pml_path: Path, regenerate: bool = False):
    """Test that recipe generates expected G-code output."""
    # Generate outputs
    gcode_dict, metrics = generate_gcode_from_pml(pml_path)

    # Determine output directory (same directory as PML file)
    output_dir = pml_path.parent / "output"

    if regenerate:
        # Regenerate mode: write outputs and pass
        write_outputs(output_dir, gcode_dict, metrics)
        print(f"\n✓ Regenerated recipe outputs for {pml_path.name}")
        print(f"  Output: {output_dir}")
        print(f"  Files: {len(gcode_dict)} G-code files + metrics.json")
        print(f"  Total time: {metrics['timing']['total_ms']:.1f}ms")
    else:
        # Verify mode: compare against committed artifacts
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

        # Also write metrics even in verify mode (for tracking changes)
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
            gcode_dict, metrics = generate_gcode_from_pml(pml_path)
            output_dir = pml_path.parent / "output"
            write_outputs(output_dir, gcode_dict, metrics)

            print(f"  ✓ Generated {len(gcode_dict)} pass(es)")
            print(f"  ✓ Total time: {metrics['timing']['total_ms']:.1f}ms")
            print(f"  ✓ Output: {output_dir}\n")
        except Exception as e:
            print(f"  ✗ FAILED: {e}\n")
            import traceback
            traceback.print_exc()

    print("Done!")
