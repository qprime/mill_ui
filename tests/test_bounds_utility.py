"""Tests for core/geometry.py bounds calculation utilities.

These tests verify the unified compute_shape_bounds() function handles
all supported shape types correctly.
"""


def test_rect_bounds():
    """Test bounds calculation for Rect shape."""
    from core.geometry import compute_shape_bounds
    from ir.removal_intent import Bounds2D

    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={"w_mm": 100.0, "h_mm": 50.0},
        center_xy=(200.0, 150.0),
    )

    assert isinstance(bounds, Bounds2D)
    assert bounds.x_min == 150.0
    assert bounds.x_max == 250.0
    assert bounds.y_min == 125.0
    assert bounds.y_max == 175.0


def test_rectangle_alias_bounds():
    """Test bounds calculation for Rectangle (alias for Rect)."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Rectangle",
        geometry_data={"w_mm": 60.0, "h_mm": 40.0},
        center_xy=(100.0, 100.0),
    )

    assert bounds.x_min == 70.0
    assert bounds.x_max == 130.0
    assert bounds.y_min == 80.0
    assert bounds.y_max == 120.0


def test_rect_case_insensitive():
    """Test that rect shape comparison is case-insensitive."""
    from core.geometry import compute_shape_bounds

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


def test_circle_bounds():
    """Test bounds calculation for Circle shape."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Circle",
        geometry_data={"diameter_mm": 50.0},
        center_xy=(100.0, 100.0),
    )

    assert bounds.x_min == 75.0
    assert bounds.x_max == 125.0
    assert bounds.y_min == 75.0
    assert bounds.y_max == 125.0


def test_circle_case_insensitive():
    """Test that circle shape comparison is case-insensitive."""
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


def test_rounded_rect_bounds():
    """Test bounds calculation for RoundedRect shape."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="RoundedRect",
        geometry_data={"w_mm": 80.0, "h_mm": 60.0, "radius_mm": 5.0},
        center_xy=(200.0, 300.0),
    )

    assert bounds.x_min == 160.0
    assert bounds.x_max == 240.0
    assert bounds.y_min == 270.0
    assert bounds.y_max == 330.0


def test_polygon_bounds():
    """Test bounds calculation for Polygon shape."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Polygon",
        geometry_data={"points": [[10, 20], [100, 20], [100, 80], [10, 80]]},
        center_xy=(0.0, 0.0),
    )

    assert bounds.x_min == 10.0
    assert bounds.x_max == 100.0
    assert bounds.y_min == 20.0
    assert bounds.y_max == 80.0


def test_polygon_empty_points_fallback():
    """Test that Polygon with no points returns 1x1mm fallback box."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Polygon",
        geometry_data={},
        center_xy=(100.0, 200.0),
    )

    assert bounds.x_min == 99.5
    assert bounds.x_max == 100.5
    assert bounds.y_min == 199.5
    assert bounds.y_max == 200.5


def test_polyline_bounds():
    """Test bounds calculation for Polyline shape."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Polyline",
        geometry_data={"points": [[0, 0], [50, 100], [100, 50], [150, 75]]},
        center_xy=(0.0, 0.0),
    )

    assert bounds.x_min == 0.0
    assert bounds.x_max == 150.0
    assert bounds.y_min == 0.0
    assert bounds.y_max == 100.0


def test_polyline_case_insensitive():
    """Test that polyline shape comparison is case-insensitive."""
    from core.geometry import compute_shape_bounds

    for shape in ["polyline", "POLYLINE", "Polyline"]:
        bounds = compute_shape_bounds(
            shape_type=shape,
            geometry_data={"points": [[10, 20], [30, 40]]},
            center_xy=(0.0, 0.0),
        )
        assert bounds.x_min == 10.0
        assert bounds.x_max == 30.0
        assert bounds.y_min == 20.0
        assert bounds.y_max == 40.0


def test_line_bounds():
    """Test bounds calculation for Line shape."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Line",
        geometry_data={
            "start": [10, 20],
            "end": [100, 80],
        },
        center_xy=(0.0, 0.0),
    )

    assert bounds.x_min == 10.0
    assert bounds.x_max == 100.0
    assert bounds.y_min == 20.0
    assert bounds.y_max == 80.0


def test_line_case_insensitive():
    """Test that line shape comparison is case-insensitive."""
    from core.geometry import compute_shape_bounds

    for shape in ["line", "LINE", "Line"]:
        bounds = compute_shape_bounds(
            shape_type=shape,
            geometry_data={"start": [0, 0], "end": [50, 100]},
            center_xy=(0.0, 0.0),
        )
        assert bounds.x_min == 0.0
        assert bounds.x_max == 50.0
        assert bounds.y_min == 0.0
        assert bounds.y_max == 100.0


def test_line_reversed_coords():
    """Test Line bounds when start > end (reversed coordinates)."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Line",
        geometry_data={
            "start": [100, 80],
            "end": [10, 20],
        },
        center_xy=(0.0, 0.0),
    )

    assert bounds.x_min == 10.0
    assert bounds.x_max == 100.0
    assert bounds.y_min == 20.0
    assert bounds.y_max == 80.0


def test_line_empty_fallback():
    """Test that Line with no points returns 1x1mm fallback box."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Line",
        geometry_data={},
        center_xy=(50.0, 75.0),
    )

    assert bounds.x_min == 49.5
    assert bounds.x_max == 50.5
    assert bounds.y_min == 74.5
    assert bounds.y_max == 75.5


def test_unknown_shape_fallback():
    """Test that unknown shapes return a 1x1mm fallback box."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="UnknownFutureShape",
        geometry_data={},
        center_xy=(100.0, 200.0),
    )

    assert bounds.x_min == 99.5
    assert bounds.x_max == 100.5
    assert bounds.y_min == 199.5
    assert bounds.y_max == 200.5


def test_none_center_defaults_to_origin():
    """Test that None center defaults to (0, 0)."""
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


def test_list_center_accepted():
    """Test that center_xy as list works (JSON parsing produces lists)."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Circle",
        geometry_data={"diameter_mm": 30.0},
        center_xy=[50, 60],
    )

    assert bounds.x_min == 35.0
    assert bounds.x_max == 65.0
    assert bounds.y_min == 45.0
    assert bounds.y_max == 75.0


def test_compute_shape_bounds_dict():
    """Test the dict-returning variant for JSON contexts."""
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


def test_missing_geometry_keys():
    """Test behavior with missing geometry keys (should default to 0)."""
    from core.geometry import compute_shape_bounds

    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={},
        center_xy=(50.0, 50.0),
    )

    assert bounds.x_min == 50.0
    assert bounds.x_max == 50.0
    assert bounds.y_min == 50.0
    assert bounds.y_max == 50.0
