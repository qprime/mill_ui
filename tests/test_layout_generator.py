"""Tests for LayoutAST generation (Phase 5).

Run from repository root: PYTHONPATH=. python3 -m tests.test_layout_generator
"""

import sys
from nesting.types import PartSpec, SheetSpec, NestedPart, SheetLayout, NestingResult
from nesting.layout_generator import (
    sheet_layout_to_ast,
    nesting_result_to_asts,
    sheet_layout_to_pml,
)


def test_simple_sheet_to_ast():
    """Convert simple sheet layout to AST."""
    print("Running test_simple_sheet_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=400, height_mm=300)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    # Verify sheet
    assert ast.sheet.width_mm == 1000
    assert ast.sheet.height_mm == 1000
    assert ast.sheet.thickness_mm == 19

    # Verify items
    assert len(ast.items) >= 1
    item = ast.items[0]
    assert item.type == "Rect"
    assert item.placement.center_xy_mm == (500, 500)

    print("  PASSED")


def test_multiple_placements_to_ast():
    """Multiple placements generate multiple items."""
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

    # Should have 3 items (one per placement)
    assert len(ast.items) == 3

    # Verify positions
    positions = {item.placement.center_xy_mm for item in ast.items}
    assert (200, 200) in positions
    assert (600, 200) in positions
    assert (200, 600) in positions

    print("  PASSED")


def test_shaker_placement_to_ast():
    """Shaker template generates multiple items per placement."""
    print("Running test_shaker_placement_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="Shaker",
        template_params={"stile_w": 50, "rail_h": 50, "panel_recess": 6},
    )
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    # Shaker produces at least outer + panel
    assert len(ast.items) >= 2

    # Find profile and pocket
    profiles = [i for i in ast.items if i.feature.type == "profile"]
    pockets = [i for i in ast.items if i.feature.type == "pocket"]

    assert len(profiles) >= 1
    assert len(pockets) >= 1

    print("  PASSED")


def test_rotated_placement_to_ast():
    """Rotated placement has swapped dimensions."""
    print("Running test_rotated_placement_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=400)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, rotated=True)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    item = ast.items[0]
    # Dimensions should be swapped
    assert item.geometry.data["w_mm"] == 400  # Was height
    assert item.geometry.data["h_mm"] == 200  # Was width

    print("  PASSED")


def test_kerf_preserved_in_ast():
    """Kerf width is preserved in AST."""
    print("Running test_kerf_preserved_in_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    ast = sheet_layout_to_ast(layout)

    assert ast.kerf_width_mm == 6

    print("  PASSED")


def test_nesting_result_to_asts():
    """Convert multi-sheet result to multiple ASTs."""
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
    """Generate PML from simple sheet layout."""
    print("Running test_sheet_to_pml_simple...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=400, height_mm=300)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, instance_id=0)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,), sheet_index=0)
    pml = sheet_layout_to_pml(layout)

    # Check PML structure
    assert "sheet 1000mm 1000mm 19mm" in pml
    assert "rect panel_0" in pml
    assert "500mm,500mm" in pml
    assert "400mm,300mm" in pml
    assert "profile through outside" in pml

    print("  PASSED")


def test_sheet_to_pml_shaker():
    """PML output is bounding box only, even for template parts.

    Template expansion happens in sheet_layout_to_ast(), not in PML output.
    The PML output is for debug visualization only.
    """
    print("Running test_sheet_to_pml_shaker...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="Shaker",
        template_params={"stile_w": 50, "rail_h": 50, "panel_recess": 6},
    )
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, instance_id=0)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,), sheet_index=0)
    pml = sheet_layout_to_pml(layout)

    # PML shows bounding box rect, not template internals
    assert "door_0" in pml
    assert "400mm,600mm" in pml or "size 400" in pml
    assert "profile through outside" in pml

    # Template details are NOT in PML (use sheet_layout_to_ast for that)
    assert "pocket" not in pml

    print("  PASSED")


def test_sheet_to_pml_rotated():
    """Rotated placement shows in PML comments."""
    print("Running test_sheet_to_pml_rotated...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=400)
    placement = NestedPart(part_spec=part, x_mm=500, y_mm=500, rotated=True)

    layout = SheetLayout(sheet_spec=sheet_spec, placements=(placement,))
    pml = sheet_layout_to_pml(layout)

    # Should note rotation
    assert "rotated" in pml.lower()

    # Dimensions should be swapped in rect statement
    assert "400mm,200mm" in pml  # width x height after rotation

    print("  PASSED")


def test_empty_sheet_to_ast():
    """Empty sheet produces valid but empty AST."""
    print("Running test_empty_sheet_to_ast...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    layout = SheetLayout(sheet_spec=sheet_spec, placements=())

    ast = sheet_layout_to_ast(layout)

    assert ast.sheet.width_mm == 1000
    assert len(ast.items) == 0

    print("  PASSED")


def test_unique_shape_ids():
    """All items have unique shape IDs."""
    print("Running test_unique_shape_ids...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    placements = tuple(
        NestedPart(part_spec=part, x_mm=100 + i*200, y_mm=100, instance_id=i)
        for i in range(5)
    )

    layout = SheetLayout(sheet_spec=sheet_spec, placements=placements)
    ast = sheet_layout_to_ast(layout)

    shape_ids = [item.shape_id for item in ast.items]
    # All should be unique
    assert len(shape_ids) == len(set(shape_ids))

    print("  PASSED")


def run_all_tests():
    """Run all tests."""
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
