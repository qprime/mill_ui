"""Tests for MaxRects bin-packing algorithm.

Run from repository root: PYTHONPATH=. python3 -m tests.test_maxrects
"""

import sys
from nesting.maxrects import maxrects_pack, MaxRectsHeuristic
from nesting.api import nest_parts, nest_and_generate


def test_maxrects_basic():
    """Basic MaxRects packing."""
    print("Running test_maxrects_basic...")
    parts = [
        (100, 100, False, "p1"),
        (100, 100, False, "p2"),
        (100, 100, False, "p3"),
        (100, 100, False, "p4"),
    ]

    placements = maxrects_pack(
        parts=parts,
        bin_width=300,
        bin_height=300,
        gap=0,
    )

    assert len(placements) == 4
    # Verify all parts have unique positions
    positions = [(p.x, p.y) for p in placements]
    assert len(set(positions)) == 4
    print("  PASSED")


def test_maxrects_with_gap():
    """MaxRects with gap between parts."""
    print("Running test_maxrects_with_gap...")
    parts = [
        (100, 100, False, "p1"),
        (100, 100, False, "p2"),
    ]

    placements = maxrects_pack(
        parts=parts,
        bin_width=250,
        bin_height=150,
        gap=10,
    )

    assert len(placements) == 2
    # Parts + gap should not exceed bin dimensions
    for p in placements:
        assert p.x + 100 + 10 <= 250 or p.x == placements[-1].x
        assert p.y + 100 + 10 <= 150 or p.y == placements[-1].y
    print("  PASSED")


def test_maxrects_rotation():
    """MaxRects with rotation enabled."""
    print("Running test_maxrects_rotation...")
    # Part is 200x100, bin is 150x250
    # Won't fit normally, but will fit rotated
    parts = [
        (200, 100, True, "p1"),  # allow_rotation=True
    ]

    placements = maxrects_pack(
        parts=parts,
        bin_width=150,
        bin_height=250,
        gap=0,
    )

    assert len(placements) == 1
    assert placements[0].rotated == True
    print("  PASSED")


def test_maxrects_no_rotation():
    """MaxRects with rotation disabled."""
    print("Running test_maxrects_no_rotation...")
    # Part is 200x100, bin is 150x250
    # Won't fit without rotation, and rotation is disabled
    parts = [
        (200, 100, False, "p1"),  # allow_rotation=False
    ]

    placements = maxrects_pack(
        parts=parts,
        bin_width=150,
        bin_height=250,
        gap=0,
    )

    assert len(placements) == 0
    print("  PASSED")


def test_maxrects_heuristics():
    """Test different heuristics produce results."""
    print("Running test_maxrects_heuristics...")
    parts = [
        (100, 150, True, "p1"),
        (80, 120, True, "p2"),
        (60, 90, True, "p3"),
    ]

    for heuristic in MaxRectsHeuristic:
        placements = maxrects_pack(
            parts=parts,
            bin_width=300,
            bin_height=300,
            gap=5,
            heuristic=heuristic,
        )
        assert len(placements) == 3, f"Heuristic {heuristic.name} failed"

    print("  PASSED")


def test_maxrects_contact_point():
    """Contact Point heuristic places parts without overlap."""
    print("Running test_maxrects_contact_point...")
    parts = [
        (50, 50, False, "p1"),
        (50, 50, False, "p2"),
        (50, 50, False, "p3"),
        (50, 50, False, "p4"),
    ]

    placements = maxrects_pack(
        parts=parts,
        bin_width=200,
        bin_height=200,
        gap=0,
        heuristic=MaxRectsHeuristic.CONTACT_POINT,
    )

    assert len(placements) == 4
    # Verify no overlaps between placements
    for i, p1 in enumerate(placements):
        for j, p2 in enumerate(placements):
            if i >= j:
                continue
            # Check that rectangles don't overlap
            x1_max = p1.x + 50
            x2_max = p2.x + 50
            y1_max = p1.y + 50
            y2_max = p2.y + 50
            overlaps = not (p1.x >= x2_max or p2.x >= x1_max or p1.y >= y2_max or p2.y >= y1_max)
            assert not overlaps, f"Parts {i} and {j} overlap"
    print("  PASSED")


def test_maxrects_api_integration():
    """Test MaxRects through the nesting API."""
    print("Running test_maxrects_api_integration...")
    parts = [
        {"name": "panel", "width_mm": 400, "height_mm": 300, "quantity": 4},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=1000,
        sheet_thickness_mm=19,
        algorithm="maxrects",
    )

    assert result["total_parts"] == 4
    assert result["total_sheets"] >= 1
    print("  PASSED")


def test_maxrects_vs_guillotine():
    """Compare MaxRects vs Guillotine utilization."""
    print("Running test_maxrects_vs_guillotine...")
    parts = [
        {"name": "large_door", "width_mm": 457, "height_mm": 597, "quantity": 20},
        {"name": "small_door", "width_mm": 305, "height_mm": 203, "quantity": 15},
        {"name": "tall_door", "width_mm": 457, "height_mm": 914, "quantity": 2},
    ]

    guillotine_result = nest_parts(
        parts=parts,
        sheet_width_mm=1220,
        sheet_height_mm=2440,
        sheet_thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
        algorithm="guillotine",
    )

    maxrects_result = nest_parts(
        parts=parts,
        sheet_width_mm=1220,
        sheet_height_mm=2440,
        sheet_thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
        algorithm="maxrects",
    )

    print(f"  Guillotine: {guillotine_result['total_sheets']} sheets, {guillotine_result['utilization_percent']:.1f}%")
    print(f"  MaxRects:   {maxrects_result['total_sheets']} sheets, {maxrects_result['utilization_percent']:.1f}%")

    # MaxRects should achieve at least as good utilization
    assert maxrects_result["utilization_percent"] >= guillotine_result["utilization_percent"] - 5  # Allow small variance
    # MaxRects should use fewer or equal sheets
    assert maxrects_result["total_sheets"] <= guillotine_result["total_sheets"]
    print("  PASSED")


def test_maxrects_generate_ast():
    """Generate LayoutAST with MaxRects."""
    print("Running test_maxrects_generate_ast...")
    parts = [
        {"name": "panel", "width_mm": 300, "height_mm": 300, "quantity": 2},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=800,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        output_format="ast",
        algorithm="maxrects",
    )

    assert result["output_format"] == "ast"
    assert len(result["output"]) >= 1

    ast = result["output"][0]
    assert hasattr(ast, "sheet")
    assert hasattr(ast, "items")
    print("  PASSED")


def test_maxrects_invalid_algorithm():
    """Invalid algorithm raises ValueError."""
    print("Running test_maxrects_invalid_algorithm...")
    parts = [{"name": "panel", "width_mm": 100, "height_mm": 100}]

    try:
        nest_parts(
            parts=parts,
            sheet_width_mm=500,
            sheet_height_mm=500,
            sheet_thickness_mm=19,
            algorithm="invalid_algo",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid algorithm" in str(e)

    print("  PASSED")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("MaxRects Algorithm Tests")
    print("=" * 60)

    tests = [
        test_maxrects_basic,
        test_maxrects_with_gap,
        test_maxrects_rotation,
        test_maxrects_no_rotation,
        test_maxrects_heuristics,
        test_maxrects_contact_point,
        test_maxrects_api_integration,
        test_maxrects_vs_guillotine,
        test_maxrects_generate_ast,
        test_maxrects_invalid_algorithm,
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
