
from __future__ import annotations

from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import Polygon, Triangle


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_polygon_parse_3_points():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

polygon tri points (0mm,0mm) (100mm,0mm) (50mm,80mm) pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    assert ast.root is not None
    assert isinstance(ast.root.children[0], Polygon)
    polygon = ast.root.children[0]
    assert len(polygon.points) == 3
    assert polygon.points == ((0.0, 0.0), (100.0, 0.0), (50.0, 80.0))
    assert polygon.feature.type == "pocket"


def test_polygon_parse_4_points():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

polygon quad points (0mm,0mm) (100mm,0mm) (100mm,100mm) (0mm,100mm) profile through outside
"""
    ast = parse_compositional_pml(pml)
    polygon = ast.root.children[0]
    assert len(polygon.points) == 4
    assert polygon.feature.type == "profile"


def test_polygon_resolve():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

polygon wedge points (10mm,10mm) (110mm,10mm) (60mm,90mm) pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Polygon"
    assert item.kind == "shape"
    assert item.placement.center_xy_mm == (60.0, 50.0)
    assert item.geometry.data["points"] == [[-50.0, -40.0], [50.0, -40.0], [0.0, 40.0]]
    assert item.geometry.data["holes"] == []
    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0


def test_polygon_with_profile_child():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

polygon shape points (0mm,0mm) (100mm,0mm) (50mm,80mm)
    profile outside through
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Polygon"
    assert item.feature.type == "profile"
    assert item.feature.side == "outside"
    assert item.feature.depth == "through"


def test_polygon_with_id():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

polygon corner_piece points (0mm,0mm) (50mm,0mm) (0mm,50mm) pocket 3.00mm
"""
    ast = parse_compositional_pml(pml)
    polygon = ast.root.children[0]
    assert polygon.id == "corner_piece"


def test_triangle_parse():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

triangle wedge base 100.00mm height 80.00mm pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    assert ast.root is not None
    assert isinstance(ast.root.children[0], Triangle)
    triangle = ast.root.children[0]
    assert triangle.base_mm == 100.0
    assert triangle.height_mm == 80.0
    assert triangle.id == "wedge"
    assert triangle.feature.type == "pocket"


def test_triangle_resolve():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

triangle shape base 100.00mm height 80.00mm pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Polygon"
    assert item.kind == "shape"
    assert len(item.geometry.data["points"]) == 3
    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0

    points = item.geometry.data["points"]
    half_base = 50.0
    half_height = 40.0
    expected_relative_points = [
        (-half_base, -half_height),
        (half_base, -half_height),
        (0, half_height),
    ]
    for actual, expected in zip(points, expected_relative_points):
        assert approx_equal(actual[0], expected[0])
        assert approx_equal(actual[1], expected[1])

    cx, cy = item.placement.center_xy_mm
    assert approx_equal(cx, 100.0)
    assert approx_equal(cy, 100.0)


def test_triangle_with_profile_child():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

triangle corner base 80.00mm height 60.00mm
    profile inside through
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Polygon"
    assert item.feature.type == "profile"
    assert item.feature.side == "inside"


def test_triangle_centered_in_region():
    pml = """sheet 400.00mm 400.00mm 10.00mm margin 0mm

inset 100.00mm
    triangle centered base 100.00mm height 100.00mm pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    points = item.geometry.data["points"]
    half_base = 50.0
    half_height = 50.0
    expected_relative_points = [
        (-half_base, -half_height),
        (half_base, -half_height),
        (0, half_height),
    ]
    for actual, expected in zip(points, expected_relative_points):
        assert approx_equal(actual[0], expected[0])
        assert approx_equal(actual[1], expected[1])

    cx, cy = item.placement.center_xy_mm
    assert approx_equal(cx, 200.0)
    assert approx_equal(cy, 200.0)


def test_polygon_bounds_calculation():
    pml = """sheet 200.00mm 200.00mm 10.00mm margin 0mm

polygon irregular points (10mm,20mm) (90mm,10mm) (80mm,70mm) (20mm,80mm) pocket 4.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    item = flat.items[0]
    cx, cy = item.placement.center_xy_mm
    assert approx_equal(cx, 50.0)
    assert approx_equal(cy, 45.0)


if __name__ == "__main__":
    test_polygon_parse_3_points()
    print("  ✓ test_polygon_parse_3_points PASS")
    test_polygon_parse_4_points()
    print("  ✓ test_polygon_parse_4_points PASS")
    test_polygon_resolve()
    print("  ✓ test_polygon_resolve PASS")
    test_polygon_with_profile_child()
    print("  ✓ test_polygon_with_profile_child PASS")
    test_polygon_with_id()
    print("  ✓ test_polygon_with_id PASS")
    test_triangle_parse()
    print("  ✓ test_triangle_parse PASS")
    test_triangle_resolve()
    print("  ✓ test_triangle_resolve PASS")
    test_triangle_with_profile_child()
    print("  ✓ test_triangle_with_profile_child PASS")
    test_triangle_centered_in_region()
    print("  ✓ test_triangle_centered_in_region PASS")
    test_polygon_bounds_calculation()
    print("  ✓ test_polygon_bounds_calculation PASS")
    print("\nAll tests passed!")
