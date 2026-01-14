"""Tests for nesting validation (Phase 6).

Run from repository root: PYTHONPATH=. python3 -m tests.test_nesting_validation
"""

import sys
from nesting.types import PartSpec, SheetSpec, NestedPart, SheetLayout, NestingResult
from nesting.validation import (
    validate_sheet_layout,
    validate_nesting_result,
)


def test_valid_layout_passes():
    """Valid layout with no issues."""
    print("Running test_valid_layout_passes...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    # Non-overlapping placements within bounds
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
    """Placement extending outside sheet bounds."""
    print("Running test_out_of_bounds_error...")
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    # Part at edge will exceed margin
    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=50, y_mm=250, instance_id=0),  # Left edge at -50
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("outside sheet bounds" in e["message"] for e in result.errors)
    print("  PASSED")


def test_overlapping_error():
    """Overlapping placements detected."""
    print("Running test_overlapping_error...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=0)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    # Two parts at same location
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
    """Parts too close (violating kerf gap)."""
    print("Running test_kerf_violation_error...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=10)
    part = PartSpec(name="panel", width_mm=100, height_mm=100)

    # Parts touching (0 gap, but 10mm required)
    # Part1: center at (100, 100), bounds (50, 50, 150, 150)
    # Part2: center at (200, 100), bounds (150, 50, 250, 150)
    # They touch at x=150, but need 10mm gap
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
    """Low utilization generates warning."""
    print("Running test_low_utilization_warning...")
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="tiny", width_mm=50, height_mm=50)

    # Very small part on large sheet
    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=100, y_mm=100, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)
    # Should be valid but with warning
    assert result.is_valid  # Low util is warning, not error
    assert any("utilization" in w["message"].lower() for w in result.warnings)
    print("  PASSED")


def test_unplaced_parts_warning():
    """Unplaced parts generate warnings."""
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

    # Should warn about unplaced
    assert any("could not place" in w["message"].lower() for w in result.warnings)
    print("  PASSED")


def test_multiple_sheets_validated():
    """All sheets in result are validated."""
    print("Running test_multiple_sheets_validated...")
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    # Sheet 1: Valid
    sheet1 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),),
        sheet_index=0,
    )

    # Sheet 2: Part out of bounds
    sheet2 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=50, y_mm=50, instance_id=1),),  # Out of bounds
        sheet_index=1,
    )

    nesting = NestingResult(sheets=(sheet1, sheet2))
    result = validate_nesting_result(nesting)

    # Should find error in sheet2
    assert not result.is_valid
    print("  PASSED")


def test_valid_nesting_result():
    """Valid nesting result passes validation."""
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
    """Run all tests."""
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
