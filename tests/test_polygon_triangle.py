
from __future__ import annotations

from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import Polygon, Triangle


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_polygon_parse_3_points():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Polygon:
      id: tri
      points:
        - [0mm, 0mm]
        - [100mm, 0mm]
        - [50mm, 80mm]
      children:
        - Pocket:
            depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    assert ast.root is not None
    assert isinstance(ast.root.children[0], Polygon)
    polygon = ast.root.children[0]
    assert len(polygon.points) == 3
    assert polygon.points == ((0.0, 0.0), (100.0, 0.0), (50.0, 80.0))


def test_polygon_parse_4_points():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Polygon:
      id: quad
      points:
        - [0mm, 0mm]
        - [100mm, 0mm]
        - [100mm, 100mm]
        - [0mm, 100mm]
      children:
        - Profile:
            side: outside
            depth: through
"""
    ast = parse_pml_yaml(pml)
    polygon = ast.root.children[0]
    assert len(polygon.points) == 4


def test_polygon_resolve():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Polygon:
      id: wedge
      points:
        - [10mm, 10mm]
        - [110mm, 10mm]
        - [60mm, 90mm]
      children:
        - Pocket:
            depth: 6mm
"""
    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Polygon:
      id: shape
      points:
        - [0mm, 0mm]
        - [100mm, 0mm]
        - [50mm, 80mm]
      children:
        - Profile:
            side: outside
            depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Polygon"
    assert item.feature.type == "profile"
    assert item.feature.side == "outside"
    assert item.feature.depth == "through"


def test_polygon_with_id():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Polygon:
      id: corner_piece
      points:
        - [0mm, 0mm]
        - [50mm, 0mm]
        - [0mm, 50mm]
      children:
        - Pocket:
            depth: 3mm
"""
    ast = parse_pml_yaml(pml)
    polygon = ast.root.children[0]
    assert polygon.id == "corner_piece"


def test_triangle_parse():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Triangle:
      id: wedge
      base: 100mm
      height: 80mm
      children:
        - Pocket:
            depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    assert ast.root is not None
    assert isinstance(ast.root.children[0], Triangle)
    triangle = ast.root.children[0]
    assert triangle.base_mm == 100.0
    assert triangle.height_mm == 80.0
    assert triangle.id == "wedge"


def test_triangle_resolve():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Triangle:
      id: shape
      base: 100mm
      height: 80mm
      children:
        - Pocket:
            depth: 6mm
"""
    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Triangle:
      id: corner
      base: 80mm
      height: 60mm
      children:
        - Profile:
            side: inside
            depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Polygon"
    assert item.feature.type == "profile"
    assert item.feature.side == "inside"


def test_triangle_centered_in_region():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 10mm

children:
  - Inset:
      distance: 100mm
      children:
        - Triangle:
            id: centered
            base: 100mm
            height: 100mm
            children:
              - Pocket:
                  depth: 5mm
"""
    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 10mm

children:
  - Polygon:
      id: irregular
      points:
        - [10mm, 20mm]
        - [90mm, 10mm]
        - [80mm, 70mm]
        - [20mm, 80mm]
      children:
        - Pocket:
            depth: 4mm
"""
    ast = parse_pml_yaml(pml)
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
