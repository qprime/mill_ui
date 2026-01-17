"""Tests for core/geometry.py bounds calculation utilities.

These tests verify the unified compute_shape_bounds() function handles
all supported shape types correctly.
"""

import sys
import traceback


def test_rect_bounds():
    """Test bounds calculation for Rect shape."""
    print("Running test_rect_bounds...")

    from core.geometry import compute_shape_bounds
    from ir.removal_intent import Bounds2D

    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={"w_mm": 100.0, "h_mm": 50.0},
        center_xy=(200.0, 150.0),
    )

    assert isinstance(bounds, Bounds2D)
    assert bounds.x_min == 150.0  # 200 - 50
    assert bounds.x_max == 250.0  # 200 + 50
    assert bounds.y_min == 125.0  # 150 - 25
    assert bounds.y_max == 175.0  # 150 + 25

    print("  ✓ PASS")
    return True


def test_rectangle_alias_bounds():
    """Test bounds calculation for Rectangle (alias for Rect)."""
    print("Running test_rectangle_alias_bounds...")

    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Rectangle",
        geometry_data={"w_mm": 60.0, "h_mm": 40.0},
        center_xy=(100.0, 100.0),
    )

    assert bounds.x_min == 70.0   # 100 - 30
    assert bounds.x_max == 130.0  # 100 + 30
    assert bounds.y_min == 80.0   # 100 - 20
    assert bounds.y_max == 120.0  # 100 + 20

    print("  ✓ PASS")
    return True


def test_rect_case_insensitive():
    """Test that rect shape comparison is case-insensitive."""
    print("Running test_rect_case_insensitive...")

    from core.geometry import compute_shape_bounds

    # All these should produce the same bounds
    for shape in ["rect", "RECT", "Rect", "rectangle", "RECTANGLE", "Rectangle"]:
        bounds = compute_shape_bounds(
            shape_type=shape,
            geometry_data={"w_mm": 20.0, "h_mm": 10.0},
            center_xy=(0.0, 0.0),
        )
        assert bounds.x_min == -10.0
        assert bounds.x_max == 10.0
        assert bounds.y_min == -5.0
        assert bounds.y_max == 5.0

    print("  ✓ PASS")
    return True


def test_circle_bounds():
    """Test bounds calculation for Circle shape."""
    print("Running test_circle_bounds...")

    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Circle",
        geometry_data={"diameter_mm": 50.0},
        center_xy=(100.0, 100.0),
    )

    assert bounds.x_min == 75.0   # 100 - 25
    assert bounds.x_max == 125.0  # 100 + 25
    assert bounds.y_min == 75.0   # 100 - 25
    assert bounds.y_max == 125.0  # 100 + 25

    print("  ✓ PASS")
    return True


def test_circle_case_insensitive():
    """Test that circle shape comparison is case-insensitive."""
    print("Running test_circle_case_insensitive...")

    from core.geometry import compute_shape_bounds

    for shape in ["circle", "CIRCLE", "Circle"]:
        bounds = compute_shape_bounds(
            shape_type=shape,
            geometry_data={"diameter_mm": 20.0},
            center_xy=(50.0, 50.0),
        )
        assert bounds.x_min == 40.0
        assert bounds.x_max == 60.0
        assert bounds.y_min == 40.0
        assert bounds.y_max == 60.0

    print("  ✓ PASS")
    return True


def test_rounded_rect_bounds():
    """Test bounds calculation for RoundedRect shape."""
    print("Running test_rounded_rect_bounds...")

    from core.geometry import compute_shape_bounds

    # RoundedRect uses same w_mm/h_mm as Rect (corner radius doesn't affect bounds)
    bounds = compute_shape_bounds(
        shape_type="RoundedRect",
        geometry_data={"w_mm": 80.0, "h_mm": 60.0, "radius_mm": 5.0},
        center_xy=(200.0, 300.0),
    )

    assert bounds.x_min == 160.0  # 200 - 40
    assert bounds.x_max == 240.0  # 200 + 40
    assert bounds.y_min == 270.0  # 300 - 30
    assert bounds.y_max == 330.0  # 300 + 30

    print("  ✓ PASS")
    return True


def test_unknown_shape_fallback():
    """Test that unknown shapes return a 1x1mm fallback box."""
    print("Running test_unknown_shape_fallback...")

    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Polygon",  # Unknown shape type
        geometry_data={},
        center_xy=(100.0, 200.0),
    )

    # Fallback is 1x1mm centered at the point
    assert bounds.x_min == 99.5
    assert bounds.x_max == 100.5
    assert bounds.y_min == 199.5
    assert bounds.y_max == 200.5

    print("  ✓ PASS")
    return True


def test_none_center_defaults_to_origin():
    """Test that None center defaults to (0, 0)."""
    print("Running test_none_center_defaults_to_origin...")

    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={"w_mm": 10.0, "h_mm": 10.0},
        center_xy=None,
    )

    assert bounds.x_min == -5.0
    assert bounds.x_max == 5.0
    assert bounds.y_min == -5.0
    assert bounds.y_max == 5.0

    print("  ✓ PASS")
    return True


def test_list_center_accepted():
    """Test that center_xy as list works (JSON parsing produces lists)."""
    print("Running test_list_center_accepted...")

    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Circle",
        geometry_data={"diameter_mm": 30.0},
        center_xy=[50, 60],  # List instead of tuple
    )

    assert bounds.x_min == 35.0
    assert bounds.x_max == 65.0
    assert bounds.y_min == 45.0
    assert bounds.y_max == 75.0

    print("  ✓ PASS")
    return True


def test_compute_shape_bounds_dict():
    """Test the dict-returning variant for JSON contexts."""
    print("Running test_compute_shape_bounds_dict...")

    from core.geometry import compute_shape_bounds_dict

    bounds_dict = compute_shape_bounds_dict(
        shape_type="Rect",
        geometry_data={"w_mm": 40.0, "h_mm": 20.0},
        center_xy=(100.0, 100.0),
    )

    assert isinstance(bounds_dict, dict)
    assert bounds_dict["x_min"] == 80.0
    assert bounds_dict["x_max"] == 120.0
    assert bounds_dict["y_min"] == 90.0
    assert bounds_dict["y_max"] == 110.0

    print("  ✓ PASS")
    return True


def test_missing_geometry_keys():
    """Test behavior with missing geometry keys (should default to 0)."""
    print("Running test_missing_geometry_keys...")

    from core.geometry import compute_shape_bounds

    # Empty geometry data - dimensions default to 0
    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={},
        center_xy=(50.0, 50.0),
    )

    # With 0 width and height, bounds collapse to a point
    assert bounds.x_min == 50.0
    assert bounds.x_max == 50.0
    assert bounds.y_min == 50.0
    assert bounds.y_max == 50.0

    print("  ✓ PASS")
    return True


def run_tests():
    """Run all bounds utility tests."""
    tests = [
        test_rect_bounds,
        test_rectangle_alias_bounds,
        test_rect_case_insensitive,
        test_circle_bounds,
        test_circle_case_insensitive,
        test_rounded_rect_bounds,
        test_unknown_shape_fallback,
        test_none_center_defaults_to_origin,
        test_list_center_accepted,
        test_compute_shape_bounds_dict,
        test_missing_geometry_keys,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed}/{passed + failed} passed")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
