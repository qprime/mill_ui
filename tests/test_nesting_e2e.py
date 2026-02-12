
from __future__ import annotations

import sys

from nesting import nest_and_generate
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode


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
    print("Running test_simple_rect_through_cam...")


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


    assert ast.sheet.width_mm == 500
    assert ast.sheet.height_mm == 500
    assert ast.sheet.thickness_mm == 19
    assert len(ast.items) >= 1


    intents = ast_to_removal_intents(ast)
    assert len(intents) >= 1


    planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)
    assert len(planner_input.profiles) + len(planner_input.pockets) + len(planner_input.holes) >= 1


    stock = Stock(width=500, height=500, thickness=19)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    passes, _ = plan_passes(
        planner_input,
        config=Config(),
        tool_db=TEST_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    assert len(passes) >= 1


    for p in passes:
        gcode = write_gcode(
            p.moves,
            safe_z=p.setup.safe_z,
        )


        assert len(gcode) > 0
        assert "G" in gcode
        lines = gcode.strip().split("\n")
        assert len(lines) >= 5

    print("  PASSED")


def test_multiple_parts_through_cam():
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

        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

        stock = Stock(
            width=ast.sheet.width_mm,
            height=ast.sheet.height_mm,
            thickness=ast.sheet.thickness_mm,
        )
        material = Material(name="MDF")
        machine = Machine(name="default_grbl")

        passes, _ = plan_passes(
            planner_input,
            config=Config(),
            tool_db=TEST_TOOL_DB,
            material=material,
            machine=machine,
            stock=stock,
            safe_z=6.0,
        )

        for p in passes:
            gcode = write_gcode(
                p.moves,
                safe_z=p.setup.safe_z,
            )
            total_gcode_lines += gcode.count("\n")


    assert total_gcode_lines > 20

    print("  PASSED")


def test_template_parts_through_cam():
    print("Running test_template_parts_through_cam...")

    parts = [
        {
            "name": "cabinet_door",
            "width_mm": 400,
            "height_mm": 600,
            "template": "shaker",
            "template_params": {
                "stile_w": 50,
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

    assert len(ast.items) >= 2

    feature_types = {item.feature.type for item in ast.items if item.feature}
    assert "profile" in feature_types
    assert "pocket" in feature_types


    intents = ast_to_removal_intents(ast)
    planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    passes, _ = plan_passes(
        planner_input,
        config=Config(),
        tool_db=TEST_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )


    assert len(passes) >= 1


    for p in passes:
        gcode = write_gcode(
            p.moves,
            safe_z=p.setup.safe_z,
        )
        assert len(gcode) > 0
        assert "G" in gcode

    print("  PASSED")


def test_multi_sheet_through_cam():
    print("Running test_multi_sheet_through_cam...")


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


    assert result["total_sheets"] >= 2
    asts = result["output"]
    assert len(asts) >= 2


    sheet_gcodes = []
    for i, ast in enumerate(asts):
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

        stock = Stock(
            width=ast.sheet.width_mm,
            height=ast.sheet.height_mm,
            thickness=ast.sheet.thickness_mm,
        )
        material = Material(name="MDF")
        machine = Machine(name="default_grbl")

        passes, _ = plan_passes(
            planner_input,
            config=Config(),
            tool_db=TEST_TOOL_DB,
            material=material,
            machine=machine,
            stock=stock,
            safe_z=6.0,
        )

        sheet_gcode = ""
        for p in passes:
            gcode = write_gcode(
                p.moves,
                safe_z=p.setup.safe_z,
            )
            sheet_gcode += gcode

        sheet_gcodes.append(sheet_gcode)
        assert len(sheet_gcode) > 0


    assert len(sheet_gcodes) >= 2

    print("  PASSED")


def test_gcode_basic_invariants():
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
    planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=6.35, min_channel_width_mm=12.0)

    stock = Stock(width=300, height=300, thickness=19)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    passes, _ = plan_passes(
        planner_input,
        config=Config(),
        tool_db=TEST_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    for p in passes:
        gcode = write_gcode(
            p.moves,
            safe_z=p.setup.safe_z,
        )

        lines = [line.strip() for line in gcode.split("\n") if line.strip()]


        has_g0_or_g1 = any("G0" in line or "G1" in line for line in lines)
        assert has_g0_or_g1, "G-code should contain G0 or G1 moves"


        has_coordinates = any("X" in line or "Y" in line or "Z" in line for line in lines)
        assert has_coordinates, "G-code should contain X, Y, or Z coordinates"

    print("  PASSED")


def run_all_tests():
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
