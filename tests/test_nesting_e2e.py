"""End-to-end tests for nesting → CAM pipeline.

These tests verify that nesting output integrates correctly with the
full CAM pipeline: LayoutAST → RemovalIntent → Planner hints → G-code.

Run from repository root: PYTHONPATH=. python3 -m tests.test_nesting_e2e
"""

from __future__ import annotations

import sys

from nesting import nest_and_generate
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode


# Standard tool database for tests
TEST_TOOL_DB = [
    {
        "name": "1_4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 800,
        "feed_z": 280,
    },
]


def test_simple_rect_through_cam():
    """Simple rect part through full CAM pipeline."""
    print("Running test_simple_rect_through_cam...")

    # Nest a single simple part
    parts = [{"name": "panel", "width_mm": 200, "height_mm": 150}]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        kerf_mm=6.35,
        output_format="ast",
    )

    assert result["total_sheets"] == 1
    asts = result["output"]
    assert len(asts) == 1

    ast = asts[0]

    # Verify AST structure
    assert ast.sheet.width_mm == 500
    assert ast.sheet.height_mm == 500
    assert ast.sheet.thickness_mm == 19
    assert len(ast.items) >= 1

    # Convert to RemovalIntent IR
    intents = ast_to_removal_intents(ast)
    assert len(intents) >= 1

    # Convert to planner hints
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)
    assert len(hints) >= 1

    # Plan passes
    stock = Stock(width=500, height=500, thickness=19)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    passes, _ = plan_passes(
        hints,
        config=Config(),
        tool_db=TEST_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    assert len(passes) >= 1

    # Generate G-code
    for pass_dict in passes:
        gcode = write_gcode(
            pass_dict["moves"],
            safe_z=pass_dict["setup"].safe_z,
        )

        # Basic G-code validation
        assert len(gcode) > 0
        assert "G" in gcode  # Contains G-codes
        lines = gcode.strip().split("\n")
        assert len(lines) >= 5  # Has reasonable content

    print("  PASSED")


def test_multiple_parts_through_cam():
    """Multiple parts nested and processed through CAM."""
    print("Running test_multiple_parts_through_cam...")

    parts = [
        {"name": "door", "width_mm": 300, "height_mm": 400, "quantity": 2},
        {"name": "drawer", "width_mm": 150, "height_mm": 100, "quantity": 3},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        kerf_mm=6.35,
        output_format="ast",
    )

    assert result["total_sheets"] >= 1
    asts = result["output"]

    total_gcode_lines = 0

    for ast in asts:
        # Convert through pipeline
        intents = ast_to_removal_intents(ast)
        hints = removal_intents_to_v1_hints(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

        stock = Stock(
            width=ast.sheet.width_mm,
            height=ast.sheet.height_mm,
            thickness=ast.sheet.thickness_mm,
        )
        material = Material(name="MDF")
        machine = Machine(name="default_grbl")

        passes, _ = plan_passes(
            hints,
            config=Config(),
            tool_db=TEST_TOOL_DB,
            material=material,
            machine=machine,
            stock=stock,
            safe_z=6.0,
        )

        for pass_dict in passes:
            gcode = write_gcode(
                pass_dict["moves"],
                safe_z=pass_dict["setup"].safe_z,
            )
            total_gcode_lines += gcode.count("\n")

    # Should have generated meaningful G-code
    assert total_gcode_lines > 20

    print("  PASSED")


def test_template_parts_through_cam():
    """Parts with Shaker template through full CAM pipeline."""
    print("Running test_template_parts_through_cam...")

    parts = [
        {
            "name": "cabinet_door",
            "width_mm": 400,
            "height_mm": 600,
            "template": "Shaker",
            "template_params": {
                "stile_w": 50,
                "rail_h": 50,
                "panel_recess": 6,
            },
        },
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=600,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        kerf_mm=6.35,
        output_format="ast",
    )

    assert result["total_sheets"] == 1
    asts = result["output"]
    ast = asts[0]

    # Shaker template should produce outer profile + panel pocket
    assert len(ast.items) >= 2

    # Verify we have both profile and pocket operations
    feature_types = {item.feature.type for item in ast.items}
    assert "profile" in feature_types
    assert "pocket" in feature_types

    # Convert through pipeline
    intents = ast_to_removal_intents(ast)
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    passes, _ = plan_passes(
        hints,
        config=Config(),
        tool_db=TEST_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    # Should have multiple passes for profile and pocket
    assert len(passes) >= 1

    # Generate and validate G-code
    for pass_dict in passes:
        gcode = write_gcode(
            pass_dict["moves"],
            safe_z=pass_dict["setup"].safe_z,
        )
        assert len(gcode) > 0
        assert "G" in gcode

    print("  PASSED")


def test_multi_sheet_through_cam():
    """Parts spanning multiple sheets through CAM pipeline."""
    print("Running test_multi_sheet_through_cam...")

    # Create parts that require multiple sheets
    parts = [
        {"name": "large_panel", "width_mm": 400, "height_mm": 400, "quantity": 5},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        kerf_mm=6.35,
        output_format="ast",
    )

    # Should require multiple sheets (only 1 fits per sheet with margins)
    assert result["total_sheets"] >= 2
    asts = result["output"]
    assert len(asts) >= 2

    # Process each sheet through CAM
    sheet_gcodes = []
    for i, ast in enumerate(asts):
        intents = ast_to_removal_intents(ast)
        hints = removal_intents_to_v1_hints(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

        stock = Stock(
            width=ast.sheet.width_mm,
            height=ast.sheet.height_mm,
            thickness=ast.sheet.thickness_mm,
        )
        material = Material(name="MDF")
        machine = Machine(name="default_grbl")

        passes, _ = plan_passes(
            hints,
            config=Config(),
            tool_db=TEST_TOOL_DB,
            material=material,
            machine=machine,
            stock=stock,
            safe_z=6.0,
        )

        sheet_gcode = ""
        for pass_dict in passes:
            gcode = write_gcode(
                pass_dict["moves"],
                safe_z=pass_dict["setup"].safe_z,
            )
            sheet_gcode += gcode

        sheet_gcodes.append(sheet_gcode)
        assert len(sheet_gcode) > 0

    # Each sheet should have similar G-code (same part type)
    assert len(sheet_gcodes) >= 2

    print("  PASSED")


def test_gcode_basic_invariants():
    """Verify G-code follows basic invariants."""
    print("Running test_gcode_basic_invariants...")

    parts = [{"name": "test_part", "width_mm": 100, "height_mm": 80}]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=300,
        sheet_height_mm=300,
        sheet_thickness_mm=19,
        kerf_mm=6.35,
        output_format="ast",
    )

    ast = result["output"][0]
    intents = ast_to_removal_intents(ast)
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

    stock = Stock(width=300, height=300, thickness=19)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    passes, _ = plan_passes(
        hints,
        config=Config(),
        tool_db=TEST_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    for pass_dict in passes:
        gcode = write_gcode(
            pass_dict["moves"],
            safe_z=pass_dict["setup"].safe_z,
        )

        lines = [line.strip() for line in gcode.split("\n") if line.strip()]

        # Check basic G-code invariants
        has_g0_or_g1 = any("G0" in line or "G1" in line for line in lines)
        assert has_g0_or_g1, "G-code should contain G0 or G1 moves"

        # Check for valid coordinate format
        has_coordinates = any("X" in line or "Y" in line or "Z" in line for line in lines)
        assert has_coordinates, "G-code should contain X, Y, or Z coordinates"

    print("  PASSED")


def run_all_tests():
    """Run all end-to-end tests."""
    print("=" * 60)
    print("Nesting End-to-End Tests (Phase 8)")
    print("=" * 60)

    tests = [
        test_simple_rect_through_cam,
        test_multiple_parts_through_cam,
        test_template_parts_through_cam,
        test_multi_sheet_through_cam,
        test_gcode_basic_invariants,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
