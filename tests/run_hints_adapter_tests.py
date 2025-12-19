"""Standalone test runner for Stage 5 hints adapter tests (without pytest).

Run from repository root: PYTHONPATH=. python3 -m tests.run_hints_adapter_tests
"""

import sys

from adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)


def test_profile_through_cut():
    """Test profile hint with through-cut."""
    print("Running test_profile_through_cut...")
    hint = {
        "id": "rect_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 50.0},
        "center_xy_mm": (150.0, 75.0),
        "depth_mm": 19.1,
        "side": "outside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=19.1)

    assert intent.region_id == "profile_rect_outline"
    assert intent.z_top == 0.0
    assert intent.z_bottom == -19.1
    assert intent.depth_mm() == 19.1
    print("  ✓ PASS")
    return True


def test_profile_with_tabs():
    """Test profile hint with tabs."""
    print("Running test_profile_with_tabs...")
    hint = {
        "id": "panel_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 200.0, "h_mm": 150.0},
        "center_xy_mm": (100.0, 75.0),
        "depth_mm": 18.0,
        "side": "outside",
        "tabs": {"count": 6, "height": 3.0, "width_mm": 10.0},
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=18.0)

    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 6
    assert intent.constraints.tabs.height_mm == 3.0
    print("  ✓ PASS")
    return True


def test_pocket_basic():
    """Test pocket hint."""
    print("Running test_pocket_basic...")
    hint = {
        "id": "pocket_1",
        "shape": "Rect",
        "geometry": {"w_mm": 80.0, "h_mm": 40.0},
        "center_xy_mm": (100.0, 50.0),
        "depth_mm": 5.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.region_id == "pocket_pocket_1"
    assert intent.z_top == 0.0
    assert intent.z_bottom == -5.0
    assert intent.depth_mm() == 5.0
    print("  ✓ PASS")
    return True


def test_pocket_with_start_depth():
    """Test pocket with start depth."""
    print("Running test_pocket_with_start_depth...")
    hint = {
        "id": "stepped_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 60.0, "h_mm": 60.0},
        "center_xy_mm": (75.0, 75.0),
        "depth_mm": 8.0,
        "start_depth_mm": 2.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.z_top == -2.0
    assert intent.z_bottom == -10.0
    assert intent.depth_mm() == 8.0
    print("  ✓ PASS")
    return True


def test_hole_circle():
    """Test hole hint (circle)."""
    print("Running test_hole_circle...")
    hint = {
        "id": "mounting_hole",
        "shape": "Circle",
        "geometry": {"diameter_mm": 10.0},
        "center_xy_mm": (50.0, 50.0),
        "depth_mm": 12.0,
    }

    intent = hole_hint_to_removal_intent(hint)

    assert intent.region_id == "hole_mounting_hole"
    assert intent.depth_mm() == 12.0
    assert intent.bounds.x_min == 45.0
    assert intent.bounds.x_max == 55.0
    print("  ✓ PASS")
    return True


def test_bounds_calculation():
    """Test bounds calculation."""
    print("Running test_bounds_calculation...")
    hint = {
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 60.0},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": 10.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.bounds.x_min == 150.0
    assert intent.bounds.x_max == 250.0
    assert intent.bounds.y_min == 120.0
    assert intent.bounds.y_max == 180.0
    print("  ✓ PASS")
    return True


def test_metadata_preservation():
    """Test metadata preservation."""
    print("Running test_metadata_preservation...")
    hint = {
        "id": "custom_shape",
        "shape": "Rect",
        "geometry": {"w_mm": 30.0, "h_mm": 30.0},
        "center_xy_mm": (15.0, 15.0),
        "depth_mm": 6.0,
        "side": "inside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)

    assert intent.metadata["hint_type"] == "profile"
    assert intent.metadata["shape"] == "Rect"
    assert intent.metadata["side"] == "inside"
    assert intent.metadata["original_id"] == "custom_shape"
    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_profile_through_cut,
        test_profile_with_tabs,
        test_pocket_basic,
        test_pocket_with_start_depth,
        test_hole_circle,
        test_bounds_calculation,
        test_metadata_preservation,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")

    sys.exit(0 if all(results) else 1)
