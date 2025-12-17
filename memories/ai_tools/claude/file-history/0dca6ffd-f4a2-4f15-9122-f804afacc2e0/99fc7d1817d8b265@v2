"""Standalone test runner for Polyline path tests (without pytest)."""

import sys
import traceback


def test_polyline_inside_rect():
    """Test polyline inside rect region maps normalized coordinates correctly."""
    print("Running test_polyline_inside_rect...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 300.00mm 19.00mm

rect canvas
    polyline path1 points (0.00,0.00) (1.00,1.00) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    items = flat.items
    assert len(items) == 2

    polyline_item = [item for item in items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points_mm"]

    assert len(points) == 2
    assert abs(points[0][0] - 0.0) < 0.01
    assert abs(points[0][1] - 0.0) < 0.01
    assert abs(points[1][0] - 400.0) < 0.01
    assert abs(points[1][1] - 300.0) < 0.01

    print("  ✓ PASS")
    return True


def test_polyline_inside_rounded_rect():
    """Test polyline inside rounded_rect region."""
    print("Running test_polyline_inside_rounded_rect...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 500.00mm 500.00mm 19.00mm

rounded_rect panel radius 20.00mm
    polyline diagonal points (0.10,0.10) (0.90,0.90) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = [item for item in flat.items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points_mm"]

    assert abs(points[0][0] - 50.0) < 0.01
    assert abs(points[0][1] - 50.0) < 0.01
    assert abs(points[1][0] - 450.0) < 0.01
    assert abs(points[1][1] - 450.0) < 0.01

    print("  ✓ PASS")
    return True


def test_polyline_inside_circle_fit():
    """Test polyline inside circle fit region."""
    print("Running test_polyline_inside_circle_fit...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

circle boundary fit
    polyline cross points (0.25,0.50) (0.75,0.50) (0.50,0.50) (0.50,0.25) (0.50,0.75) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = [item for item in flat.items if item.type == "Polyline"][0]
    points = polyline_item.geometry.data["points_mm"]

    assert len(points) == 5
    assert abs(points[0][0] - 100.0) < 0.01
    assert abs(points[0][1] - 200.0) < 0.01

    print("  ✓ PASS")
    return True


def test_polyline_with_10_points():
    """Test polyline with 10 points renders correctly."""
    print("Running test_polyline_with_10_points...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 600.00mm 400.00mm 19.00mm

polyline zigzag points (0.0,0.0) (0.1,0.9) (0.2,0.1) (0.3,0.8) (0.4,0.2) (0.5,0.7) (0.6,0.3) (0.7,0.6) (0.8,0.4) (0.9,0.5) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    points = polyline_item.geometry.data["points_mm"]

    assert len(points) == 10
    assert abs(points[0][0] - 0.0) < 0.01
    assert abs(points[0][1] - 0.0) < 0.01
    assert abs(points[9][0] - 540.0) < 0.01
    assert abs(points[9][1] - 200.0) < 0.01

    print("  ✓ PASS")
    return True


def test_polyline_error_out_of_range():
    """Test error: coordinates out of range."""
    print("Running test_polyline_error_out_of_range...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (-0.1,0.5) (1.0,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "out of range" in str(e).lower()

    print("  ✓ PASS")
    return True


def test_polyline_error_single_point():
    """Test error: minimum 2 points required."""
    print("Running test_polyline_error_single_point...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml, ParseError
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5,0.5) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        flat = resolve_layout(ast)
        assert False, "Should have raised ValueError or ParseError"
    except (ValueError, ParseError) as e:
        assert "2 points" in str(e).lower() or "at least 2" in str(e).lower()

    print("  ✓ PASS")
    return True


def test_polyline_error_malformed():
    """Test error: malformed point syntax."""
    print("Running test_polyline_error_malformed...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml, ParseError

    pml = """sheet 400.00mm 400.00mm 19.00mm

polyline bad points (0.5 0.5) (1.0,1.0) engrave 1.00mm
"""

    try:
        ast = parse_compositional_pml(pml)
        assert False, "Should have raised ParseError"
    except ParseError as e:
        assert "," in str(e) or "comma" in str(e).lower()

    print("  ✓ PASS")
    return True


def test_polyline_roundtrip():
    """Test round-trip preserves coordinates."""
    print("Running test_polyline_roundtrip...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.pml.compositional_formatter import format_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    original_pml = """sheet 500.00mm 400.00mm 19.00mm

polyline path1 points (0.10,0.20) (0.50,0.50) (0.90,0.80) engrave 1.00mm
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    points1 = flat1.items[0].geometry.data["points_mm"]
    points2 = flat2.items[0].geometry.data["points_mm"]

    assert len(points1) == len(points2) == 3

    for (x1, y1), (x2, y2) in zip(points1, points2):
        assert abs(x1 - x2) < 0.01
        assert abs(y1 - y2) < 0.01

    print("  ✓ PASS")
    return True


def test_polyline_in_inset_region():
    """Test polyline inside inset region."""
    print("Running test_polyline_in_inset_region...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 600.00mm 400.00mm 19.00mm

inset 50.00mm
    polyline path1 points (0.00,0.00) (1.00,1.00) engrave 1.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    points = polyline_item.geometry.data["points_mm"]

    assert abs(points[0][0] - 50.0) < 0.01
    assert abs(points[0][1] - 50.0) < 0.01
    assert abs(points[1][0] - 550.0) < 0.01
    assert abs(points[1][1] - 350.0) < 0.01

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_polyline_inside_rect,
        test_polyline_inside_rounded_rect,
        test_polyline_inside_circle_fit,
        test_polyline_with_10_points,
        test_polyline_error_out_of_range,
        test_polyline_error_single_point,
        test_polyline_error_malformed,
        test_polyline_roundtrip,
        test_polyline_in_inset_region,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} Polyline path tests passed")

    sys.exit(0 if all(results) else 1)
