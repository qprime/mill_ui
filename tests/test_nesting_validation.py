
import sys
from nesting.types import PartSpec, SheetSpec, NestedPart, SheetLayout, NestingResult
from nesting.validation import (
    validate_sheet_layout,
    validate_nesting_result,
)


def test_valid_layout_passes():
    print("Running test_valid_layout_passes...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)


    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=part, x_mm=500, y_mm=200, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert result.is_valid, result.summary()
    print("  PASSED")


def test_out_of_bounds_error():
    print("Running test_out_of_bounds_error...")
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)


    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=50, y_mm=250, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("outside sheet bounds" in e["message"] for e in result.errors)
    print("  PASSED")


def test_overlapping_error():
    print("Running test_overlapping_error...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=0)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)


    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("overlap" in e["message"].lower() for e in result.errors)
    print("  PASSED")


def test_kerf_violation_error():
    print("Running test_kerf_violation_error...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=10)
    part = PartSpec(name="panel", width_mm=100, height_mm=100)


    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=100, y_mm=100, instance_id=0),
            NestedPart(part_spec=part, x_mm=200, y_mm=100, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("kerf" in e["message"].lower() or "overlap" in e["message"].lower() for e in result.errors)
    print("  PASSED")


def test_low_utilization_warning():
    print("Running test_low_utilization_warning...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="tiny", width_mm=50, height_mm=50)


    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=100, y_mm=100, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)

    assert result.is_valid
    assert any("utilization" in w["message"].lower() for w in result.warnings)
    print("  PASSED")


def test_unplaced_parts_warning():
    print("Running test_unplaced_parts_warning...")
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19)
    placed_part = PartSpec(name="placed", width_mm=200, height_mm=200)
    unplaced_part = PartSpec(name="too_big", width_mm=1000, height_mm=1000, quantity=2)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=placed_part, x_mm=250, y_mm=250, instance_id=0),
        ),
    )

    nesting = NestingResult(sheets=(layout,), unplaced_parts=(unplaced_part,))
    result = validate_nesting_result(nesting)


    assert any("could not place" in w["message"].lower() for w in result.warnings)
    print("  PASSED")


def test_multiple_sheets_validated():
    print("Running test_multiple_sheets_validated...")
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)


    sheet1 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),),
        sheet_index=0,
    )


    sheet2 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=50, y_mm=50, instance_id=1),),
        sheet_index=1,
    )

    nesting = NestingResult(sheets=(sheet1, sheet2))
    result = validate_nesting_result(nesting)


    assert not result.is_valid
    print("  PASSED")


def test_valid_nesting_result():
    print("Running test_valid_nesting_result...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=300, height_mm=300)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),
            NestedPart(part_spec=part, x_mm=650, y_mm=250, instance_id=1),
            NestedPart(part_spec=part, x_mm=250, y_mm=650, instance_id=2),
            NestedPart(part_spec=part, x_mm=650, y_mm=650, instance_id=3),
        ),
    )

    nesting = NestingResult(sheets=(layout,))
    result = validate_nesting_result(nesting)

    assert result.is_valid, result.summary()
    print("  PASSED")


def run_all_tests():
    print("=" * 60)
    print("Phase 6: Nesting Validation Tests")
    print("=" * 60)

    tests = [
        test_valid_layout_passes,
        test_out_of_bounds_error,
        test_overlapping_error,
        test_kerf_violation_error,
        test_low_utilization_warning,
        test_unplaced_parts_warning,
        test_multiple_sheets_validated,
        test_valid_nesting_result,
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
