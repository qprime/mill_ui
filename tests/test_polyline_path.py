
from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import Polyline
from layout_ast.layout import Feature


def test_polyline_inside_rect():
    pml = """sheet 400.00mm 300.00mm 19.00mm margin 0mm

rect canvas
    polyline path1 points (0.00,0.00) (1.00,1.00) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    items = flat.items
    assert len(items) == 2

    polyline_item = [item for item in items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert len(points) == 2
    assert abs(cx - 200.0) < 0.01
    assert abs(cy - 150.0) < 0.01
    assert abs(points[0][0] + 200.0) < 0.01
    assert abs(points[0][1] + 150.0) < 0.01
    assert abs(points[1][0] - 200.0) < 0.01
    assert abs(points[1][1] - 150.0) < 0.01


def test_polyline_inside_rounded_rect():
    pml = """sheet 500.00mm 500.00mm 19.00mm margin 0mm

rounded_rect panel radius 20.00mm
    polyline diagonal points (0.10,0.10) (0.90,0.90) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    items = flat.items
    polyline_item = [item for item in items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert abs(cx - 250.0) < 0.01
    assert abs(cy - 250.0) < 0.01
    assert abs(points[0][0] + 200.0) < 0.01
    assert abs(points[0][1] + 200.0) < 0.01
    assert abs(points[1][0] - 200.0) < 0.01
    assert abs(points[1][1] - 200.0) < 0.01


def test_polyline_inside_circle_fit():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

circle boundary fit
    polyline cross points (0.25,0.50) (0.75,0.50) (0.50,0.50) (0.50,0.25) (0.50,0.75) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = [item for item in flat.items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert len(points) == 5
    assert abs(cx - 200.0) < 0.01
    assert abs(cy - 200.0) < 0.01


def test_polyline_with_10_points():
    pml = """sheet 600.00mm 400.00mm 19.00mm margin 0mm

polyline zigzag points (0.0,0.0) (0.1,0.9) (0.2,0.1) (0.3,0.8) (0.4,0.2) (0.5,0.7) (0.6,0.3) (0.7,0.6) (0.8,0.4) (0.9,0.5) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert len(points) == 10

    assert abs(cx - 270.0) < 0.01
    assert abs(cy - 180.0) < 0.01


def test_polyline_error_out_of_range_x_negative():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (-0.1,0.5) (1.0,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)

        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_x_over_one():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (0.5,0.5) (1.1,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_y_negative():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (0.5,-0.1) (0.5,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_y_over_one():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (0.5,0.5) (0.5,1.1) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_single_point():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (0.5,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError or ParseError"
    except (ValueError, ParseError) as e:
        assert "2 points" in str(e).lower() or "at least 2" in str(e).lower()


def test_polyline_error_malformed_no_comma():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (0.5 0.5) (1.0,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        assert False, "Should have raised ParseError"
    except ParseError as e:
        assert "," in str(e) or "comma" in str(e).lower()


def test_polyline_error_malformed_no_closing_paren():
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

polyline bad points (0.5,0.5 (1.0,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        assert False, "Should have raised ParseError"
    except ParseError as e:
        assert ")" in str(e) or "paren" in str(e).lower()


def test_polyline_roundtrip_preserves_coordinates():
    original_pml = """sheet 500.00mm 400.00mm 19.00mm margin 0mm

polyline path1 points (0.10,0.20) (0.50,0.50) (0.90,0.80) engrave 1.00mm
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    points1 = flat1.items[0].geometry.data["points"]
    points2 = flat2.items[0].geometry.data["points"]
    cx1, cy1 = flat1.items[0].placement.center_xy_mm
    cx2, cy2 = flat2.items[0].placement.center_xy_mm

    assert len(points1) == len(points2) == 3

    for (x1, y1), (x2, y2) in zip(points1, points2):
        assert abs((x1 + cx1) - (x2 + cx2)) < 0.01
        assert abs((y1 + cy1) - (y2 + cy2)) < 0.01


def test_polyline_in_inset_region():
    pml = """sheet 600.00mm 400.00mm 19.00mm margin 0mm

inset 50.00mm
    polyline path1 points (0.00,0.00) (1.00,1.00) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert abs(cx - 300.0) < 0.01
    assert abs(cy - 200.0) < 0.01
    assert abs(points[0][0] + cx - 50.0) < 0.01
    assert abs(points[0][1] + cy - 50.0) < 0.01
    assert abs(points[1][0] + cx - 550.0) < 0.01
    assert abs(points[1][1] + cy - 350.0) < 0.01
