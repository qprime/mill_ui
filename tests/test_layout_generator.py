import sys

from nesting.layout_generator import (
    nesting_result_to_asts,
    sheet_layout_to_ast,
    sheet_layout_to_pml,
)
from nesting.types import NestedPart, NestingResult, PartSpec, SheetLayout, SheetSpec


def test_simple_sheet_to_ast():
    print("Running test_simple_sheet_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=400, height_mm=300)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    assert ast.sheet.width_mm == 1000
    assert ast.sheet.height_mm == 1000
    assert ast.sheet.thickness_mm == 19

    assert len(ast.items) >= 1
    item = ast.items[0]
    assert item.type == "Rect"
    assert item.placement is not None
    assert item.placement.center_xy_mm == (500, 500)

    print("  PASSED")


def test_multiple_placements_to_ast():
    print("Running test_multiple_placements_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    placements = (
        NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=0),
        NestedPart(part_spec=part, x_mm=600, y_mm=200, instance_id=1),
        NestedPart(part_spec=part, x_mm=200, y_mm=600, instance_id=2),
    )

    layout = SheetLayout(sheet_spec=sheet_spec, placements=placements)
    ast = sheet_layout_to_ast(layout)

    assert len(ast.items) == 3

    positions = {item.placement.center_xy_mm for item in ast.items if item.placement is not None}
    assert (200, 200) in positions
    assert (600, 200) in positions
    assert (200, 600) in positions

    print("  PASSED")


def test_shaker_placement_to_ast():
    print("Running test_shaker_placement_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="shaker",
        template_params={"stile_w": 50, "panel_recess": 6},
    )
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    assert len(ast.items) >= 2

    profiles = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    pockets = [i for i in ast.items if i.feature and i.feature.type == "pocket"]

    assert len(profiles) >= 1
    assert len(pockets) >= 1

    print("  PASSED")


def test_rotated_placement_to_ast():
    print("Running test_rotated_placement_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=400)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, rotated=True)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    item = ast.items[0]

    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 400
    assert item.geometry.data["h_mm"] == 200

    print("  PASSED")


def test_kerf_preserved_in_ast():
    print("Running test_kerf_preserved_in_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    assert ast.kerf_width_mm == 6

    print("  PASSED")


def test_nesting_result_to_asts():
    print("Running test_nesting_result_to_asts...")
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=400, height_mm=400)

    sheet1 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),),
        sheet_index=0,
    )
    sheet2 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=1),),
        sheet_index=1,
    )

    result = NestingResult(sheets=(sheet1, sheet2))
    asts = nesting_result_to_asts(result)

    assert len(asts) == 2
    assert all(ast.sheet.width_mm == 500 for ast in asts)

    print("  PASSED")


def test_sheet_to_pml_simple():
    print("Running test_sheet_to_pml_simple...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=400, height_mm=300)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, instance_id=0)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,), sheet_index=0)
    pml = sheet_layout_to_pml(layout)

    assert "width: 1000mm" in pml
    assert "height: 1000mm" in pml
    assert "thickness: 19mm" in pml
    assert "panel_0_rect" in pml
    assert "x: 500mm" in pml
    assert "y: 500mm" in pml
    assert "width: 400mm" in pml
    assert "height: 300mm" in pml
    assert "type: profile" in pml
    assert "depth: through" in pml

    print("  PASSED")


def test_sheet_to_pml_shaker():
    print("Running test_sheet_to_pml_shaker...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="shaker",
        template_params={"stile_w": 50, "panel_recess": 6},
    )
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, instance_id=0)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,), sheet_index=0)
    pml = sheet_layout_to_pml(layout)

    assert "door_0" in pml or "door" in pml
    assert "profile" in pml

    print("  PASSED")


def test_sheet_to_pml_rotated():
    print("Running test_sheet_to_pml_rotated...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=400)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, rotated=True)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    pml = sheet_layout_to_pml(layout)

    assert "width: 400mm" in pml
    assert "height: 200mm" in pml

    print("  PASSED")


def test_empty_sheet_to_ast():
    print("Running test_empty_sheet_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    layout = SheetLayout(sheet_spec=sheet_spec, placements=())

    ast = sheet_layout_to_ast(layout)

    assert ast.sheet.width_mm == 1000
    assert len(ast.items) == 0

    print("  PASSED")


def test_unique_shape_ids():
    print("Running test_unique_shape_ids...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    placements = tuple(NestedPart(part_spec=part, x_mm=100 + i * 200, y_mm=100, instance_id=i) for i in range(5))

    layout = SheetLayout(sheet_spec=sheet_spec, placements=placements)
    ast = sheet_layout_to_ast(layout)

    shape_ids = [item.shape_id for item in ast.items]

    assert len(shape_ids) == len(set(shape_ids))

    print("  PASSED")


def run_all_tests():
    print("=" * 60)
    print("Phase 5: LayoutAST Generation Tests")
    print("=" * 60)

    tests = [
        test_simple_sheet_to_ast,
        test_multiple_placements_to_ast,
        test_shaker_placement_to_ast,
        test_rotated_placement_to_ast,
        test_kerf_preserved_in_ast,
        test_nesting_result_to_asts,
        test_sheet_to_pml_simple,
        test_sheet_to_pml_shaker,
        test_sheet_to_pml_rotated,
        test_empty_sheet_to_ast,
        test_unique_shape_ids,
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

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
