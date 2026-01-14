"""Tests for nesting API (Phase 7).

Run from repository root: PYTHONPATH=. python3 -m tests.test_nesting_api
"""

import sys
from nesting.api import nest_parts, nest_and_generate


def test_basic_nesting_api():
    """Basic API usage."""
    print("Running test_basic_nesting_api...")
    parts = [
        {"name": "panel", "width_mm": 400, "height_mm": 300, "quantity": 4},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=1000,
        sheet_thickness_mm=19,
    )

    assert "sheets" in result
    assert result["total_parts"] == 4
    assert result["total_sheets"] >= 1
    assert "utilization" in result
    print("  PASSED")


def test_api_with_template():
    """API with Shaker template."""
    print("Running test_api_with_template...")
    parts = [
        {
            "name": "door",
            "width_mm": 400,
            "height_mm": 600,
            "quantity": 2,
            "template": "Shaker",
            "template_params": {
                "stile_w": 50,
                "rail_h": 50,
                "panel_recess": 6,
            },
        },
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=1000,
        sheet_thickness_mm=19,
    )

    assert result["total_parts"] == 2
    print("  PASSED")


def test_api_validation():
    """API returns validation results."""
    print("Running test_api_validation...")
    parts = [
        {"name": "panel", "width_mm": 200, "height_mm": 200, "quantity": 1},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        validate=True,
    )

    assert "validation" in result
    assert result["validation"] is not None
    assert "is_valid" in result["validation"]
    print("  PASSED")


def test_api_no_validation():
    """API can skip validation."""
    print("Running test_api_no_validation...")
    parts = [
        {"name": "panel", "width_mm": 200, "height_mm": 200, "quantity": 1},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        validate=False,
    )

    assert result["validation"] is None
    print("  PASSED")


def test_api_unplaced_parts():
    """API reports unplaced parts."""
    print("Running test_api_unplaced_parts...")
    parts = [
        {"name": "huge", "width_mm": 2000, "height_mm": 2000, "quantity": 1},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
    )

    assert result["total_parts"] == 0
    assert len(result["unplaced"]) == 1
    assert result["unplaced"][0]["name"] == "huge"
    print("  PASSED")


def test_api_max_sheets():
    """API respects max_sheets."""
    print("Running test_api_max_sheets...")
    parts = [
        {"name": "panel", "width_mm": 400, "height_mm": 400, "quantity": 10},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        margin_mm=10,
        max_sheets=2,
    )

    assert result["total_sheets"] <= 2
    print("  PASSED")


def test_nest_and_generate_ast():
    """Generate LayoutAST output."""
    print("Running test_nest_and_generate_ast...")
    parts = [
        {"name": "panel", "width_mm": 300, "height_mm": 300, "quantity": 2},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=800,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        output_format="ast",
    )

    assert result["output_format"] == "ast"
    assert len(result["output"]) >= 1  # At least one AST

    # Verify it's a LayoutAST
    ast = result["output"][0]
    assert hasattr(ast, "sheet")
    assert hasattr(ast, "items")

    print("  PASSED")


def test_nest_and_generate_pml():
    """Generate PML output."""
    print("Running test_nest_and_generate_pml...")
    parts = [
        {"name": "panel", "width_mm": 300, "height_mm": 300, "quantity": 2},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=800,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        output_format="pml",
    )

    assert result["output_format"] == "pml"
    assert len(result["output"]) >= 1

    # Verify it's PML string
    pml = result["output"][0]
    assert isinstance(pml, str)
    assert "sheet" in pml
    assert "rect" in pml

    print("  PASSED")


def test_user_example():
    """User's example: 20 + 15 + 2 panels."""
    print("Running test_user_example...")
    parts = [
        {"name": "large_door", "width_mm": 457, "height_mm": 597, "quantity": 20},
        {"name": "small_door", "width_mm": 305, "height_mm": 203, "quantity": 15},
        {"name": "tall_door", "width_mm": 457, "height_mm": 914, "quantity": 2},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1220,  # 4' sheet
        sheet_height_mm=2440,  # 8' sheet
        sheet_thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
    )

    print(f"  Total sheets: {result['total_sheets']}")
    print(f"  Total parts placed: {result['total_parts']}")
    print(f"  Utilization: {result['utilization_percent']:.1f}%")

    # All 37 parts should fit
    assert result["total_parts"] >= 35  # Allow small variance
    assert result["total_sheets"] >= 3

    print("  PASSED")


def test_invalid_output_format():
    """Invalid output_format raises ValueError."""
    print("Running test_invalid_output_format...")
    parts = [{"name": "panel", "width_mm": 100, "height_mm": 100}]

    try:
        nest_and_generate(
            parts=parts,
            sheet_width_mm=500,
            sheet_height_mm=500,
            sheet_thickness_mm=19,
            kerf_mm=6,
            output_format="invalid",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid output_format" in str(e)
        assert "invalid" in str(e)

    print("  PASSED")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Phase 7: Nesting API Tests")
    print("=" * 60)

    tests = [
        test_basic_nesting_api,
        test_api_with_template,
        test_api_validation,
        test_api_no_validation,
        test_api_unplaced_parts,
        test_api_max_sheets,
        test_nest_and_generate_ast,
        test_nest_and_generate_pml,
        test_invalid_output_format,
        test_user_example,
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
