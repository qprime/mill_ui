"""Comprehensive tests for Stage 6: SVG as Generator Input.

This test module covers:
- SVG path tokenization
- SVG path command parsing (M, L, H, V, C, S, Q, T, A, Z)
- Curve flattening (cubic Bezier, quadratic Bezier, arcs)
- SVGPathParams validation
- svg_stamp_generator integration
- Edge cases and error handling
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domains import Domain
from generators.svg.curves import (
    flatten_arc,
    flatten_cubic_bezier,
    flatten_quadratic_bezier,
)
from generators.svg.params import SVGPathParams
from generators.svg.parser import (
    SVGParseError,
    center_polylines,
    normalize_polylines,
    parse_svg_path,
    polylines_bounds,
    scale_polylines,
    translate_polylines,
)
from generators.svg.stamp import svg_stamp_generator

# =============================================================================
# Test Helpers
# =============================================================================


def approx_equal(a: float, b: float, tolerance: float = 0.1) -> bool:
    """Check if two floats are approximately equal within tolerance."""
    return abs(a - b) <= tolerance


def point_near(p1: tuple, p2: tuple, tolerance: float = 0.1) -> bool:
    """Check if two points are approximately equal."""
    return approx_equal(p1[0], p2[0], tolerance) and approx_equal(p1[1], p2[1], tolerance)


# =============================================================================
# Curve Flattening Tests
# =============================================================================


def test_flatten_cubic_bezier_straight_line():
    """A cubic Bezier that is already a line should produce minimal points."""
    # Control points on a straight line
    p0 = (0.0, 0.0)
    p1 = (33.0, 0.0)
    p2 = (66.0, 0.0)
    p3 = (100.0, 0.0)

    result = flatten_cubic_bezier(p0, p1, p2, p3, tolerance=0.1)

    # Should produce just the endpoint (p0 is not included in result)
    assert len(result) >= 1
    assert point_near(result[-1], p3)


def test_flatten_cubic_bezier_curved():
    """A curved cubic Bezier should produce multiple points."""
    p0 = (0.0, 0.0)
    p1 = (0.0, 100.0)  # Control point way off the line
    p2 = (100.0, 100.0)
    p3 = (100.0, 0.0)

    result = flatten_cubic_bezier(p0, p1, p2, p3, tolerance=0.1)

    # Should produce multiple points for the curve
    assert len(result) > 1
    # Endpoint should be last
    assert point_near(result[-1], p3)
    # Should have intermediate points above the baseline
    max_y = max(p[1] for p in result)
    assert max_y > 50  # Curve goes above


def test_flatten_cubic_bezier_tolerance():
    """Smaller tolerance should produce more points."""
    p0 = (0.0, 0.0)
    p1 = (50.0, 100.0)
    p2 = (50.0, 100.0)
    p3 = (100.0, 0.0)

    result_coarse = flatten_cubic_bezier(p0, p1, p2, p3, tolerance=10.0)
    result_fine = flatten_cubic_bezier(p0, p1, p2, p3, tolerance=0.1)

    assert len(result_fine) >= len(result_coarse)


def test_flatten_quadratic_bezier():
    """Test quadratic Bezier flattening."""
    p0 = (0.0, 0.0)
    p1 = (50.0, 100.0)  # Control point
    p2 = (100.0, 0.0)

    result = flatten_quadratic_bezier(p0, p1, p2, tolerance=0.1)

    assert len(result) >= 1
    assert point_near(result[-1], p2)

    # Curve should have points above baseline
    max_y = max(p[1] for p in result)
    assert max_y > 30


def test_flatten_arc_semicircle():
    """Test arc flattening with a semicircle."""
    p0 = (0.0, 0.0)
    p1 = (100.0, 0.0)
    rx = 50.0
    ry = 50.0
    x_rotation = 0.0
    large_arc = True
    sweep = True

    result = flatten_arc(p0, rx, ry, x_rotation, large_arc, sweep, p1, tolerance=0.1)

    assert len(result) >= 1
    assert point_near(result[-1], p1)

    # Arc should curve above (or below depending on sweep direction)
    y_values = [p[1] for p in result]
    assert max(abs(y) for y in y_values) > 20  # Significant curve


def test_flatten_arc_zero_radius():
    """Arc with zero radius should produce straight line."""
    p0 = (0.0, 0.0)
    p1 = (100.0, 50.0)

    result = flatten_arc(p0, 0.0, 0.0, 0.0, False, True, p1, tolerance=0.1)

    # Should just return the endpoint
    assert len(result) == 1
    assert point_near(result[0], p1)


def test_flatten_tolerance_validation():
    """Tolerance must be positive."""
    try:
        flatten_cubic_bezier((0, 0), (1, 1), (2, 2), (3, 3), tolerance=0)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass

    try:
        flatten_quadratic_bezier((0, 0), (1, 1), (2, 2), tolerance=-1)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass

    try:
        flatten_arc((0, 0), 10, 10, 0, False, True, (10, 0), tolerance=0)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass


# =============================================================================
# SVG Path Parser Tests - Basic Commands
# =============================================================================


def test_parse_simple_line():
    """Parse a simple line: M L commands."""
    path = "M0,0 L100,0 L100,100 L0,100"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    assert len(polylines[0]) == 4
    assert point_near(polylines[0][0], (0, 0))
    assert point_near(polylines[0][1], (100, 0))
    assert point_near(polylines[0][2], (100, 100))
    assert point_near(polylines[0][3], (0, 100))


def test_parse_closed_path():
    """Parse a closed path with Z command."""
    path = "M0,0 L100,0 L100,100 Z"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    # Closed path should have start point at end
    assert point_near(polylines[0][-1], (0, 0))


def test_parse_relative_commands():
    """Parse path with relative commands (lowercase)."""
    path = "M10,10 l20,0 l0,20 l-20,0 z"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    poly = polylines[0]

    assert point_near(poly[0], (10, 10))
    assert point_near(poly[1], (30, 10))  # +20 in x
    assert point_near(poly[2], (30, 30))  # +20 in y
    assert point_near(poly[3], (10, 30))  # -20 in x
    assert point_near(poly[4], (10, 10))  # closed


def test_parse_horizontal_vertical():
    """Parse H and V commands."""
    path = "M0,0 H100 V50 H0 V0"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    poly = polylines[0]

    assert point_near(poly[0], (0, 0))
    assert point_near(poly[1], (100, 0))
    assert point_near(poly[2], (100, 50))
    assert point_near(poly[3], (0, 50))
    assert point_near(poly[4], (0, 0))


def test_parse_relative_hv():
    """Parse relative h and v commands."""
    path = "M10,10 h50 v30 h-50 v-30"
    polylines = parse_svg_path(path)

    poly = polylines[0]
    assert point_near(poly[0], (10, 10))
    assert point_near(poly[1], (60, 10))
    assert point_near(poly[2], (60, 40))
    assert point_near(poly[3], (10, 40))
    assert point_near(poly[4], (10, 10))


def test_parse_multiple_subpaths():
    """Parse path with multiple M commands (subpaths)."""
    path = "M0,0 L50,50 M100,0 L150,50"
    polylines = parse_svg_path(path)

    assert len(polylines) == 2
    assert len(polylines[0]) == 2
    assert len(polylines[1]) == 2


def test_parse_implicit_lineto():
    """After M, numbers are implicit L commands."""
    path = "M0,0 100,0 100,100"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    assert len(polylines[0]) == 3


# =============================================================================
# SVG Path Parser Tests - Curves
# =============================================================================


def test_parse_cubic_bezier():
    """Parse C (cubic Bezier) command."""
    path = "M0,0 C25,50 75,50 100,0"
    polylines = parse_svg_path(path, tolerance=0.5)

    assert len(polylines) == 1
    poly = polylines[0]

    # Should have multiple points from curve flattening
    assert len(poly) > 2
    # Endpoints should be correct
    assert point_near(poly[0], (0, 0))
    assert point_near(poly[-1], (100, 0))
    # Curve should have points with positive Y
    assert any(p[1] > 10 for p in poly)


def test_parse_smooth_cubic():
    """Parse S (smooth cubic) command."""
    path = "M0,0 C25,50 75,50 100,0 S175,-50 200,0"
    polylines = parse_svg_path(path, tolerance=0.5)

    assert len(polylines) == 1
    poly = polylines[0]

    assert point_near(poly[-1], (200, 0))


def test_parse_quadratic_bezier():
    """Parse Q (quadratic Bezier) command."""
    path = "M0,0 Q50,100 100,0"
    polylines = parse_svg_path(path, tolerance=0.5)

    assert len(polylines) == 1
    poly = polylines[0]

    assert len(poly) > 2
    assert point_near(poly[0], (0, 0))
    assert point_near(poly[-1], (100, 0))


def test_parse_smooth_quadratic():
    """Parse T (smooth quadratic) command."""
    path = "M0,0 Q50,50 100,0 T200,0"
    polylines = parse_svg_path(path, tolerance=0.5)

    assert len(polylines) == 1
    assert point_near(polylines[0][-1], (200, 0))


def test_parse_arc():
    """Parse A (arc) command."""
    # Simple arc: radius 50, not rotated, small arc, sweep positive direction
    path = "M0,0 A50,50 0 0,1 100,0"
    polylines = parse_svg_path(path, tolerance=0.5)

    assert len(polylines) == 1
    poly = polylines[0]

    assert point_near(poly[0], (0, 0))
    assert point_near(poly[-1], (100, 0))
    # Arc should curve downward (positive sweep with positive Y down)
    assert any(p[1] != 0 for p in poly[1:-1])


# =============================================================================
# SVG Path Parser Tests - Edge Cases
# =============================================================================


def test_parse_empty_path():
    """Empty path should return empty list."""
    assert parse_svg_path("") == []
    assert parse_svg_path("   ") == []


def test_parse_whitespace_variations():
    """Parser should handle various whitespace formats."""
    paths = [
        "M0,0L100,100",
        "M 0 0 L 100 100",
        "M0 0L100 100",
        "M 0,0 L 100,100",
        "M0,0\nL100,100",
        "M0,0\tL100,100",
    ]

    for path in paths:
        polylines = parse_svg_path(path)
        assert len(polylines) == 1
        assert point_near(polylines[0][0], (0, 0))
        assert point_near(polylines[0][1], (100, 100))


def test_parse_negative_numbers():
    """Parser should handle negative numbers."""
    path = "M-50,-50 L50,50 L-50,50"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    assert point_near(polylines[0][0], (-50, -50))
    assert point_near(polylines[0][1], (50, 50))


def test_parse_scientific_notation():
    """Parser should handle scientific notation."""
    path = "M1e2,2e1 L1.5e2,5e0"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    assert point_near(polylines[0][0], (100, 20))
    assert point_near(polylines[0][1], (150, 5))


def test_parse_decimal_numbers():
    """Parser should handle decimal numbers."""
    path = "M0.5,0.25 L10.75,20.125"
    polylines = parse_svg_path(path)

    assert len(polylines) == 1
    assert approx_equal(polylines[0][0][0], 0.5, 0.001)
    assert approx_equal(polylines[0][0][1], 0.25, 0.001)


def test_parse_invalid_command():
    """Parser should raise on invalid commands."""
    try:
        parse_svg_path("M0,0 X100,100")  # X is not a valid command
        raise AssertionError("Should have raised SVGParseError")
    except SVGParseError:
        pass


def test_parse_missing_arguments():
    """Parser should raise on missing arguments."""
    try:
        parse_svg_path("M0,0 L50")  # L needs 2 arguments
        raise AssertionError("Should have raised SVGParseError")
    except (SVGParseError, ValueError):
        pass


# =============================================================================
# Polyline Utility Tests
# =============================================================================


def test_polylines_bounds():
    """Test bounding box calculation."""
    polylines = [
        [(0, 0), (100, 0), (100, 50)],
        [(25, 75), (75, 75)],
    ]

    x_min, y_min, x_max, y_max = polylines_bounds(polylines)  # type: ignore[arg-type]

    assert x_min == 0
    assert y_min == 0
    assert x_max == 100
    assert y_max == 75


def test_scale_polylines():
    """Test polyline scaling."""
    polylines = [[(0, 0), (10, 10)]]

    scaled = scale_polylines(polylines, 2.0)  # type: ignore[arg-type]

    assert point_near(scaled[0][0], (0, 0))
    assert point_near(scaled[0][1], (20, 20))


def test_translate_polylines():
    """Test polyline translation."""
    polylines = [[(0, 0), (10, 10)]]

    translated = translate_polylines(polylines, 5, -5)  # type: ignore[arg-type]

    assert point_near(translated[0][0], (5, -5))
    assert point_near(translated[0][1], (15, 5))


def test_center_polylines():
    """Test polyline centering."""
    polylines = [[(10, 20), (30, 40)]]

    centered = center_polylines(polylines)  # type: ignore[arg-type]

    # Center was at (20, 30), should be translated to origin
    assert point_near(centered[0][0], (-10, -10))
    assert point_near(centered[0][1], (10, 10))


def test_normalize_polylines():
    """Test polyline normalization."""
    polylines = [[(0, 0), (200, 100)]]

    # Normalize to 100x100, preserving aspect
    normalized = normalize_polylines(polylines, target_width=100, target_height=100)  # type: ignore[arg-type]

    x_min, y_min, x_max, y_max = polylines_bounds(normalized)

    # Should fit within 100x100
    assert (x_max - x_min) <= 100.1
    assert (y_max - y_min) <= 100.1


# =============================================================================
# SVGPathParams Tests
# =============================================================================


def test_svg_path_params_valid():
    """Test valid SVGPathParams construction."""
    params = SVGPathParams(
        svg_path="M0,0 L100,100",
        depth_mm=2.0,
    )
    params.validate()  # Should not raise


def test_svg_path_params_full():
    """Test SVGPathParams with all options."""
    params = SVGPathParams(
        svg_path="M0,0 C50,50 100,0 100,100",
        depth_mm=3.0,
        tolerance=0.05,
        feature_type="pocket",
        scale_mode="fill",
        center=False,
        invert_y=False,
    )
    params.validate()


def test_svg_path_params_empty_path():
    """SVGPathParams should reject empty path."""
    params = SVGPathParams(svg_path="", depth_mm=2.0)
    try:
        params.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "empty" in str(e).lower()


def test_svg_path_params_invalid_depth():
    """SVGPathParams should reject non-positive depth."""
    params = SVGPathParams(svg_path="M0,0 L10,10", depth_mm=0)
    try:
        params.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "depth" in str(e).lower()


def test_svg_path_params_invalid_tolerance():
    """SVGPathParams should reject non-positive tolerance."""
    params = SVGPathParams(svg_path="M0,0 L10,10", depth_mm=2.0, tolerance=-0.1)
    try:
        params.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "tolerance" in str(e).lower()


def test_svg_path_params_invalid_feature():
    """SVGPathParams should reject invalid feature type."""
    params = SVGPathParams(svg_path="M0,0 L10,10", depth_mm=2.0, feature_type="invalid")  # type: ignore[arg-type]
    try:
        params.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "feature" in str(e).lower()


def test_svg_path_params_invalid_scale():
    """SVGPathParams should reject invalid scale mode."""
    params = SVGPathParams(svg_path="M0,0 L10,10", depth_mm=2.0, scale_mode="stretch")  # type: ignore[arg-type]
    try:
        params.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "scale" in str(e).lower()


def test_svg_path_params_invalid_svg_unit_mm():
    """SVGPathParams should reject non-positive svg_unit_mm."""
    params = SVGPathParams(svg_path="M0,0 L10,10", depth_mm=2.0, svg_unit_mm=0)
    try:
        params.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "svg_unit_mm" in str(e).lower()

    params2 = SVGPathParams(svg_path="M0,0 L10,10", depth_mm=2.0, svg_unit_mm=-1.0)
    try:
        params2.validate()
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "svg_unit_mm" in str(e).lower()


# =============================================================================
# SVG Stamp Generator Tests
# =============================================================================


def test_svg_stamp_generator_simple():
    """Test svg_stamp_generator with a simple rectangle."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0 L100,0 L100,100 L0,100 Z",
        depth_mm=2.0,
    )

    items = svg_stamp_generator(domain, params)

    assert len(items) >= 1
    assert items[0].kind == "shape"
    assert items[0].feature is not None
    assert items[0].feature.type == "engrave"
    assert items[0].feature.depth_mm == 2.0


def test_svg_stamp_generator_curved():
    """Test svg_stamp_generator with curves."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = SVGPathParams(
        svg_path="M0,0 C50,100 150,100 200,0",
        depth_mm=3.0,
        tolerance=1.0,
    )

    items = svg_stamp_generator(domain, params)

    assert len(items) >= 1


def test_svg_stamp_generator_pocket():
    """Test svg_stamp_generator with pocket feature."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0 L50,0 L50,50 L0,50 Z",
        depth_mm=5.0,
        feature_type="pocket",
    )

    items = svg_stamp_generator(domain, params)

    assert len(items) >= 1
    assert items[0].feature is not None
    assert items[0].feature.type == "pocket"
    assert items[0].type == "Polygon"


def test_svg_stamp_generator_profile():
    """Test svg_stamp_generator with profile feature."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0 L100,0 L100,100 L0,100 Z",
        depth_mm=19.0,
        feature_type="profile",
    )

    items = svg_stamp_generator(domain, params)

    assert len(items) >= 1
    assert items[0].feature is not None
    assert items[0].feature.type == "profile"


def test_svg_stamp_generator_scale_fit():
    """Test that scale_mode='fit' scales SVG to fit domain."""
    # Small domain, large SVG
    domain = Domain.from_rectangle(50, 50, center=(25, 25))
    params = SVGPathParams(
        svg_path="M0,0 L1000,0 L1000,1000 L0,1000 Z",
        depth_mm=2.0,
        scale_mode="fit",
    )

    items = svg_stamp_generator(domain, params)

    # Check that geometry fits within domain bounds (roughly)
    assert len(items) >= 1
    assert items[0].geometry is not None
    geometry = items[0].geometry.data
    points = geometry.get("points", [])
    if points:
        x_coords = [p[0] for p in points]
        [p[1] for p in points]
        # Should be roughly within domain bounds (with some margin for centering)
        assert max(x_coords) - min(x_coords) <= 60  # Domain is 50, allow some margin


def test_svg_stamp_generator_no_scale():
    """Test scale_mode='none' uses SVG coordinates directly."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0 L20,0 L20,20 L0,20 Z",
        depth_mm=2.0,
        scale_mode="none",
        center=True,
    )

    items = svg_stamp_generator(domain, params)

    assert len(items) >= 1
    assert items[0].geometry is not None
    points = items[0].geometry.data.get("points", [])
    if points:
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        width = max(x_coords) - min(x_coords)
        height = max(y_coords) - min(y_coords)
        assert approx_equal(width, 20, 1)
        assert approx_equal(height, 20, 1)


def test_svg_stamp_generator_allow_empty():
    """Test allow_empty=True with empty SVG."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0",  # Just a move, no actual lines
        depth_mm=2.0,
    )

    items = svg_stamp_generator(domain, params, allow_empty=True)

    assert items == []


def test_svg_stamp_generator_error_empty_svg():
    """Test that empty SVG raises without allow_empty."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0",  # Just a move
        depth_mm=2.0,
    )

    try:
        svg_stamp_generator(domain, params, allow_empty=False)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass


def test_svg_stamp_generator_determinism():
    """Same inputs should produce identical outputs."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0 C50,50 50,50 100,0 L100,100 L0,100 Z",
        depth_mm=2.5,
        tolerance=0.5,
    )

    items1 = svg_stamp_generator(domain, params)
    items2 = svg_stamp_generator(domain, params)

    assert len(items1) == len(items2)
    for i1, i2 in zip(items1, items2, strict=False):
        assert i1.type == i2.type
        assert i1.feature is not None
        assert i2.feature is not None
        assert i1.feature.type == i2.feature.type
        assert i1.feature.is_through == i2.feature.is_through
        assert i1.feature.depth_mm == i2.feature.depth_mm
        assert i1.geometry is not None
        assert i2.geometry is not None
        g1 = i1.geometry.data
        g2 = i2.geometry.data
        if "points" in g1 and "points" in g2:
            assert len(g1["points"]) == len(g2["points"])


def test_svg_stamp_generator_multiple_paths():
    """Test SVG with multiple subpaths."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = SVGPathParams(
        svg_path="M0,0 L50,50 M100,0 L150,50 M0,100 L50,150",
        depth_mm=1.5,
    )

    items = svg_stamp_generator(domain, params)

    # Should produce multiple items for multiple subpaths
    assert len(items) >= 3


# =============================================================================
# Transform and Coordinate Tests
# =============================================================================


def test_svg_stamp_generator_y_inversion_default():
    """Test that invert_y=True (default) flips Y coordinates.

    SVG convention: Y increases downward (0 at top)
    CAM convention: Y increases upward (0 at bottom)

    With invert_y=True, a point at SVG (50, 10) should appear "higher" than
    a point at SVG (50, 90) in the output (i.e., larger Y value in output).
    """
    domain = Domain.from_rectangle(100, 100, center=(50, 50))

    # Create a rectangle that we can track - left edge is at SVG Y=10, right at Y=90
    # Using a 2D shape avoids degenerate dimensions
    params = SVGPathParams(
        svg_path="M0,10 L100,10 L100,90 L0,90 Z",  # Rectangle spanning Y 10-90
        depth_mm=2.0,
        scale_mode="fit",
        center=True,
        invert_y=True,  # Default
    )

    items = svg_stamp_generator(domain, params)
    assert len(items) == 1
    assert items[0].geometry is not None
    points = items[0].geometry.data.get("points", [])
    assert len(points) >= 4

    # Get Y values of top and bottom edges
    y_values = [p[1] for p in points]
    min(y_values)
    max_y_out = max(y_values)

    # The first point (SVG Y=10, which is "top" in SVG) should map to
    # higher Y values in output due to inversion
    # Find the output Y for points that were at SVG Y=10 (top edge)
    # After inversion, SVG Y=10 becomes output max_y, SVG Y=90 becomes output min_y
    first_point_y = points[0][1]

    # With inversion, the original SVG top (Y=10) should become the CAM top (higher Y)
    assert first_point_y == max_y_out, "With invert_y=True, SVG top (Y=10) should map to CAM top (max Y)"


def test_svg_stamp_generator_y_inversion_disabled():
    """Test that invert_y=False keeps Y coordinates as-is."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))

    params = SVGPathParams(
        svg_path="M0,10 L100,10 L100,90 L0,90 Z",  # Rectangle spanning Y 10-90
        depth_mm=2.0,
        scale_mode="fit",
        center=True,
        invert_y=False,  # No inversion
    )

    items = svg_stamp_generator(domain, params)
    assert len(items) == 1
    assert items[0].geometry is not None
    points = items[0].geometry.data.get("points", [])
    assert len(points) >= 4

    y_values = [p[1] for p in points]
    min_y_out = min(y_values)
    max(y_values)
    first_point_y = points[0][1]

    # Without inversion, SVG Y=10 (low Y) should stay at low Y in output
    assert first_point_y == min_y_out, "With invert_y=False, SVG Y=10 should map to CAM min Y"


def test_svg_stamp_generator_svg_unit_mm():
    """Test svg_unit_mm with scale_mode='none' for exact sizing."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))

    # SVG path in "pixels" at 96 DPI
    # A 96x96 pixel square should become 25.4x25.4 mm (1 inch)
    params = SVGPathParams(
        svg_path="M0,0 L96,0 L96,96 L0,96 Z",
        depth_mm=2.0,
        scale_mode="none",  # Use svg_unit_mm directly
        svg_unit_mm=25.4 / 96,  # Convert 96 DPI pixels to mm
        center=True,
        invert_y=True,
    )

    items = svg_stamp_generator(domain, params)
    assert len(items) >= 1
    assert items[0].geometry is not None
    points = items[0].geometry.data.get("points", [])
    if points:
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        width = max(x_coords) - min(x_coords)
        height = max(y_coords) - min(y_coords)

        # Should be approximately 25.4mm (1 inch)
        assert approx_equal(width, 25.4, 0.5), f"Width {width} should be ~25.4mm"
        assert approx_equal(height, 25.4, 0.5), f"Height {height} should be ~25.4mm"


def test_svg_stamp_generator_svg_unit_mm_default():
    """Test that svg_unit_mm=1.0 treats SVG units as mm directly."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))

    # SVG path of 50x30 units, should become 50x30 mm with svg_unit_mm=1.0
    params = SVGPathParams(
        svg_path="M0,0 L50,0 L50,30 L0,30 Z",
        depth_mm=2.0,
        scale_mode="none",
        svg_unit_mm=1.0,  # Default: 1 SVG unit = 1 mm
        center=True,
        invert_y=True,
    )

    items = svg_stamp_generator(domain, params)
    assert len(items) >= 1
    assert items[0].geometry is not None
    points = items[0].geometry.data.get("points", [])
    if points:
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        width = max(x_coords) - min(x_coords)
        height = max(y_coords) - min(y_coords)

        assert approx_equal(width, 50, 0.5), f"Width {width} should be 50mm"
        assert approx_equal(height, 30, 0.5), f"Height {height} should be 30mm"


# =============================================================================
# Integration Tests
# =============================================================================


def test_svg_to_ast_integration():
    """Test that SVG generator output integrates with LayoutAST pipeline."""
    from layout_ast.layout import LayoutAST, Sheet

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M10,10 L90,10 L90,90 L10,90 Z",
        depth_mm=3.0,
    )

    items = svg_stamp_generator(domain, params)

    # Build LayoutAST
    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=200, thickness_mm=19, margin_mm=0.0),
        items=tuple(items),
    )

    assert ast.sheet.width_mm == 200
    assert len(ast.items) >= 1


def test_svg_complex_path():
    """Test with a more complex real-world SVG path."""
    # A simple star shape
    path = """
    M 50,0
    L 61,35
    L 98,35
    L 68,57
    L 79,91
    L 50,70
    L 21,91
    L 32,57
    L 2,35
    L 39,35
    Z
    """

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path=path,
        depth_mm=2.0,
        feature_type="engrave",
    )

    items = svg_stamp_generator(domain, params)

    assert len(items) == 1
    assert items[0].geometry is not None
    points = items[0].geometry.data.get("points", [])
    assert len(points) >= 10  # Star has 10 points + closure


# =============================================================================
# Test Runner
# =============================================================================


def run_tests():
    """Run all tests and report results."""
    test_functions = [
        # Curve flattening
        test_flatten_cubic_bezier_straight_line,
        test_flatten_cubic_bezier_curved,
        test_flatten_cubic_bezier_tolerance,
        test_flatten_quadratic_bezier,
        test_flatten_arc_semicircle,
        test_flatten_arc_zero_radius,
        test_flatten_tolerance_validation,
        # Basic path parsing
        test_parse_simple_line,
        test_parse_closed_path,
        test_parse_relative_commands,
        test_parse_horizontal_vertical,
        test_parse_relative_hv,
        test_parse_multiple_subpaths,
        test_parse_implicit_lineto,
        # Curve parsing
        test_parse_cubic_bezier,
        test_parse_smooth_cubic,
        test_parse_quadratic_bezier,
        test_parse_smooth_quadratic,
        test_parse_arc,
        # Edge cases
        test_parse_empty_path,
        test_parse_whitespace_variations,
        test_parse_negative_numbers,
        test_parse_scientific_notation,
        test_parse_decimal_numbers,
        test_parse_invalid_command,
        test_parse_missing_arguments,
        # Polyline utilities
        test_polylines_bounds,
        test_scale_polylines,
        test_translate_polylines,
        test_center_polylines,
        test_normalize_polylines,
        # SVGPathParams
        test_svg_path_params_valid,
        test_svg_path_params_full,
        test_svg_path_params_empty_path,
        test_svg_path_params_invalid_depth,
        test_svg_path_params_invalid_tolerance,
        test_svg_path_params_invalid_feature,
        test_svg_path_params_invalid_scale,
        test_svg_path_params_invalid_svg_unit_mm,
        # SVG stamp generator
        test_svg_stamp_generator_simple,
        test_svg_stamp_generator_curved,
        test_svg_stamp_generator_pocket,
        test_svg_stamp_generator_profile,
        test_svg_stamp_generator_scale_fit,
        test_svg_stamp_generator_no_scale,
        test_svg_stamp_generator_allow_empty,
        test_svg_stamp_generator_error_empty_svg,
        test_svg_stamp_generator_determinism,
        test_svg_stamp_generator_multiple_paths,
        # Transform and coordinates
        test_svg_stamp_generator_y_inversion_default,
        test_svg_stamp_generator_y_inversion_disabled,
        test_svg_stamp_generator_svg_unit_mm,
        test_svg_stamp_generator_svg_unit_mm_default,
        # Integration
        test_svg_to_ast_integration,
        test_svg_complex_path,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_func in test_functions:
        try:
            test_func()
            passed += 1
            print(f"  ✓ {test_func.__name__}")
        except AssertionError as e:
            failed += 1
            errors.append((test_func.__name__, f"AssertionError: {e}"))
            print(f"  ✗ {test_func.__name__}: {e}")
        except Exception as e:
            failed += 1
            errors.append((test_func.__name__, f"{type(e).__name__}: {e}"))
            print(f"  ✗ {test_func.__name__}: {type(e).__name__}: {e}")

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if errors:
        print("\nFailed tests:")
        for name, error in errors:
            print(f"  - {name}: {error}")

    return failed == 0


if __name__ == "__main__":
    print("Running Stage 6 SVG Parser Tests")
    print("=" * 50)
    success = run_tests()
    sys.exit(0 if success else 1)
