"""Tests for Polyline path primitive (Stage 16).

Acceptance tests:
- Polyline inside rect region
- Polyline inside rounded_rect region
- Polyline inside circle fit region (bounding box mapping)
- Polyline with 10 points renders correctly
- Error: out-of-range points (x<0, x>1, y<0, y>1)
- Error: malformed points syntax
- Error: single point (minimum 2 required)
- Round-trip preserves point coordinates
"""

from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import Polyline
from layout_ast.layout import Feature


def test_polyline_inside_rect():
    """Test polyline inside rect region maps normalized coordinates correctly."""
    pml = """sheet 400.00mm 300.00mm 19.00mm

rect canvas
    polyline path1 points (0.00,0.00) (1.00,1.00) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Should have rect + polyline
    items = flat.items
    assert len(items) == 2

    polyline_item = [item for item in items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points_mm"]

    # Region is 400×300mm
    # (0,0) → (0, 0), (1,1) → (400, 300)
    assert len(points) == 2
    assert abs(points[0][0] - 0.0) < 0.01
    assert abs(points[0][1] - 0.0) < 0.01
    assert abs(points[1][0] - 400.0) < 0.01
    assert abs(points[1][1] - 300.0) < 0.01


def test_polyline_inside_rounded_rect():
    """Test polyline inside rounded_rect region."""
    pml = """sheet 500.00mm 500.00mm 19.00mm

rounded_rect panel radius 20.00mm
    polyline diagonal points (0.10,0.10) (0.90,0.90) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    items = flat.items
    polyline_item = [item for item in items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points_mm"]

    # Region is 500×500mm
    # (0.1,0.1) → (50, 50), (0.9,0.9) → (450, 450)
    assert abs(points[0][0] - 50.0) < 0.01
    assert abs(points[0][1] - 50.0) < 0.01
    assert abs(points[1][0] - 450.0) < 0.01
    assert abs(points[1][1] - 450.0) < 0.01


def test_polyline_inside_circle_fit():
    """Test polyline inside circle fit region (bounding box mapping)."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

circle boundary fit
    polyline cross points (0.25,0.50) (0.75,0.50) (0.50,0.50) (0.50,0.25) (0.50,0.75) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = [item for item in flat.items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points_mm"]

    # Circle fit mode inscribes in 400×400mm sheet
    # Bounding box is 400×400mm centered at (200,200)
    # (0.25,0.50) → (100, 200), (0.75,0.50) → (300, 200), etc.
    assert len(points) == 5
    assert abs(points[0][0] - 100.0) < 0.01
    assert abs(points[0][1] - 200.0) < 0.01


def test_polyline_with_10_points():
    """Test polyline with 10 points renders correctly."""
    pml = """sheet 600.00mm 400.00mm 19.00mm

polyline zigzag points (0.0,0.0) (0.1,0.9) (0.2,0.1) (0.3,0.8) (0.4,0.2) (0.5,0.7) (0.6,0.3) (0.7,0.6) (0.8,0.4) (0.9,0.5) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    points = polyline_item.geometry.data["points_mm"]

    assert len(points) == 10
    # Verify first and last points
    assert abs(points[0][0] - 0.0) < 0.01
    assert abs(points[0][1] - 0.0) < 0.01
    assert abs(points[9][0] - 540.0) < 0.01  # 0.9 * 600
    assert abs(points[9][1] - 200.0) < 0.01  # 0.5 * 400


def test_polyline_error_out_of_range_x_negative():
    """Test error: x coordinate < 0."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (-0.1,0.5) (1.0,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        # Validation happens in Polyline.__post_init__
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_x_over_one():
    """Test error: x coordinate > 1."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5,0.5) (1.1,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_y_negative():
    """Test error: y coordinate < 0."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5,-0.1) (0.5,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_y_over_one():
    """Test error: y coordinate > 1."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5,0.5) (0.5,1.1) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_single_point():
    """Test error: minimum 2 points required."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError or ParseError"
    except (ValueError, ParseError) as e:
        assert "2 points" in str(e).lower() or "at least 2" in str(e).lower()


def test_polyline_error_malformed_no_comma():
    """Test error: malformed point syntax (missing comma)."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5 0.5) (1.0,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        assert False, "Should have raised ParseError"
    except ParseError as e:
        assert "," in str(e) or "comma" in str(e).lower()


def test_polyline_error_malformed_no_closing_paren():
    """Test error: malformed point syntax (missing closing paren)."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5,0.5 (1.0,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        assert False, "Should have raised ParseError"
    except ParseError as e:
        assert ")" in str(e) or "paren" in str(e).lower()


def test_polyline_roundtrip_preserves_coordinates():
    """Test round-trip: PML → AST → PML preserves point coordinates."""
    original_pml = """sheet 500.00mm 400.00mm 19.00mm

polyline path1 points (0.10,0.20) (0.50,0.50) (0.90,0.80) engrave 1.00mm
"""

    # Parse → Format → Parse
    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    # Resolve both and compare
    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    points1 = flat1.items[0].geometry.data["points_mm"]
    points2 = flat2.items[0].geometry.data["points_mm"]

    assert len(points1) == len(points2) == 3

    for (x1, y1), (x2, y2) in zip(points1, points2):
        assert abs(x1 - x2) < 0.01
        assert abs(y1 - y2) < 0.01


def test_polyline_in_inset_region():
    """Test polyline inside inset region calculates correctly."""
    pml = """sheet 600.00mm 400.00mm 19.00mm

inset 50.00mm
    polyline path1 points (0.00,0.00) (1.00,1.00) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    points = polyline_item.geometry.data["points_mm"]

    # Inset region: 600 - 100 = 500mm × 400 - 100 = 300mm
    # Positioned at (50, 50) to (550, 350)
    # (0,0) → (50, 50), (1,1) → (550, 350)
    assert abs(points[0][0] - 50.0) < 0.01
    assert abs(points[0][1] - 50.0) < 0.01
    assert abs(points[1][0] - 550.0) < 0.01
    assert abs(points[1][1] - 350.0) < 0.01
