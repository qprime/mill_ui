from __future__ import annotations

import math

import pytest

from core.geometry import ellipse_points
from layout_ast.compositional import Ellipse
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


class TestEllipseAST:
    def test_ellipse_with_explicit_axes(self):
        e = Ellipse(rx_mm=50.0, ry_mm=30.0)
        assert e.rx_mm == 50.0
        assert e.ry_mm == 30.0

    def test_ellipse_defaults_none(self):
        e = Ellipse()
        assert e.rx_mm is None
        assert e.ry_mm is None

    def test_ellipse_partial_axes_raises(self):
        with pytest.raises(ValueError, match="both rx and ry"):
            Ellipse(rx_mm=50.0)

    def test_ellipse_partial_axes_raises_ry_only(self):
        with pytest.raises(ValueError, match="both rx and ry"):
            Ellipse(ry_mm=30.0)

    def test_ellipse_zero_rx_raises(self):
        with pytest.raises(ValueError, match="rx_mm must be positive"):
            Ellipse(rx_mm=0.0, ry_mm=30.0)

    def test_ellipse_negative_ry_raises(self):
        with pytest.raises(ValueError, match="ry_mm must be positive"):
            Ellipse(rx_mm=50.0, ry_mm=-1.0)


class TestEllipsePoints:
    def test_point_count(self):
        pts = ellipse_points(0.0, 0.0, 50.0, 30.0)
        assert len(pts) == 64

    def test_on_boundary(self):
        rx, ry = 50.0, 30.0
        pts = ellipse_points(0.0, 0.0, rx, ry)
        for x, y in pts:
            val = (x / rx) ** 2 + (y / ry) ** 2
            assert approx_equal(val, 1.0, tolerance=0.001)

    def test_degenerates_to_circle(self):
        r = 40.0
        pts = ellipse_points(0.0, 0.0, r, r)
        for x, y in pts:
            dist = math.sqrt(x**2 + y**2)
            assert approx_equal(dist, r, tolerance=0.001)

    def test_center_offset(self):
        cx, cy = 100.0, 200.0
        rx, ry = 50.0, 30.0
        pts = ellipse_points(cx, cy, rx, ry)
        for x, y in pts:
            val = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            assert approx_equal(val, 1.0, tolerance=0.001)


class TestEllipseParsing:
    def test_parse_ellipse_explicit(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 50mm
      ry: 30mm
"""
        ast = parse_pml_yaml(pml)
        assert ast.root is not None
        node = ast.root.children[0]
        assert isinstance(node, Ellipse)
        assert node.rx_mm == 50.0
        assert node.ry_mm == 30.0

    def test_parse_ellipse_with_feature(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 50mm
      ry: 30mm
      feature:
        type: pocket
        depth: 6mm
"""
        ast = parse_pml_yaml(pml)
        node = ast.root.children[0]
        assert isinstance(node, Ellipse)
        assert node.feature is not None
        assert node.feature.type == "pocket"
        assert node.feature.depth_mm == 6.0

    def test_parse_ellipse_at_position(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 50mm
      ry: 30mm
      feature:
        type: profile
        side: outside
        depth: through
      at:
        x: 100mm
        y: 100mm
"""
        ast = parse_pml_yaml(pml)
        from layout_ast.compositional import AtPosition

        node = ast.root.children[0]
        assert isinstance(node, AtPosition)
        assert isinstance(node.child, Ellipse)
        assert node.x_mm == 100.0
        assert node.y_mm == 100.0

    def test_parse_ellipse_region_fill(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      feature:
        type: pocket
        depth: 5mm
"""
        ast = parse_pml_yaml(pml)
        node = ast.root.children[0]
        assert isinstance(node, Ellipse)
        assert node.rx_mm is None
        assert node.ry_mm is None


class TestEllipseRoundTrip:
    def test_pml_round_trip_explicit(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 50mm
      ry: 30mm
      feature:
        type: pocket
        depth: 6mm
"""
        ast = parse_pml_yaml(pml)
        formatted = format_pml_yaml(ast)
        ast2 = parse_pml_yaml(formatted)
        node = ast2.root.children[0]
        assert isinstance(node, Ellipse)
        assert node.rx_mm == 50.0
        assert node.ry_mm == 30.0
        assert node.feature.type == "pocket"

    def test_pml_round_trip_region_derived(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      feature:
        type: pocket
        depth: 5mm
"""
        ast = parse_pml_yaml(pml)
        formatted = format_pml_yaml(ast)
        ast2 = parse_pml_yaml(formatted)
        node = ast2.root.children[0]
        assert isinstance(node, Ellipse)
        assert node.rx_mm is None
        assert node.ry_mm is None

    def test_format_ellipse_at_position(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 50mm
      ry: 30mm
      feature:
        type: profile
        side: outside
        depth: through
      at:
        x: 100mm
        y: 100mm
"""
        ast = parse_pml_yaml(pml)
        formatted = format_pml_yaml(ast)
        ast2 = parse_pml_yaml(formatted)
        from layout_ast.compositional import AtPosition

        node = ast2.root.children[0]
        assert isinstance(node, AtPosition)
        assert isinstance(node.child, Ellipse)
        assert node.child.rx_mm == 50.0


class TestEllipseResolver:
    def test_resolves_to_polygon_item(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 50mm
      ry: 30mm
      feature:
        type: pocket
        depth: 6mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        assert len(flat.items) == 1
        item = flat.items[0]
        assert item.type == "Polygon"
        assert item.kind == "shape"
        assert item.geometry is not None
        assert len(item.geometry.data["points"]) == 64
        assert item.feature is not None
        assert item.feature.type == "pocket"

    def test_region_fill(self):
        pml = """
Sheet:
  width: 200mm
  height: 100mm
  thickness: 10mm
children:
  - Ellipse:
      feature:
        type: pocket
        depth: 5mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        assert len(flat.items) == 1
        item = flat.items[0]
        assert item.geometry is not None
        points = item.geometry.data["points"]
        assert len(points) == 64
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        assert approx_equal(max(xs), 100.0, tolerance=0.1)
        assert approx_equal(max(ys), 50.0, tolerance=0.1)

    def test_domain_propagation(self):
        pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 80mm
      ry: 50mm
      children:
        - Pocket:
            depth: 3mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        assert len(flat.items) == 1
        item = flat.items[0]
        assert item.type == "Polygon"
        assert item.feature is not None
        assert item.feature.type == "pocket"

    def test_at_position_resolve(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 10mm
children:
  - Ellipse:
      rx: 60mm
      ry: 40mm
      id: oval
      feature:
        type: profile
        side: outside
        depth: through
      at:
        x: 200mm
        y: 150mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        assert len(flat.items) == 1
        item = flat.items[0]
        assert item.type == "Polygon"
        assert item.placement is not None
        cx, cy = item.placement.center_xy_mm
        assert approx_equal(cx, 200.0)
        assert approx_equal(cy, 150.0)


class TestEllipseNesting:
    def test_nesting_area(self):
        from nesting.types import PartSpec

        spec = PartSpec(name="oval", width_mm=100.0, height_mm=60.0, shape="Ellipse")
        expected = math.pi * 50.0 * 30.0
        assert approx_equal(spec.area_mm2, expected, tolerance=0.1)

    def test_nesting_expander_discretizes(self):
        from nesting.template_expander import expand_part_to_items
        from nesting.types import PartSpec

        spec = PartSpec(name="oval", width_mm=100.0, height_mm=60.0, shape="Ellipse")
        items = expand_part_to_items(spec, center_xy=(50.0, 30.0), rotated=False, sheet_thickness_mm=19.0)
        assert len(items) == 1
        item = items[0]
        assert item.type == "Polygon"
        assert item.geometry is not None
        assert len(item.geometry.data["points"]) == 64
