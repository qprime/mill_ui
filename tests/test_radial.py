import pytest

from domains import Domain
from generators.area.radial_label import radial_label_generator
from generators.area.radial_pocket import radial_pocket_generator
from generators.area.radial_tick import radial_tick_generator
from generators.params.area import (
    RadialLabelParams,
    RadialPocketParams,
    RadialTickParams,
)
from generators.radial_utils import generate_angular_positions, radial_point
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


class TestAngularPositions:
    def test_full_circle_four_rays(self):
        positions = generate_angular_positions(4)
        assert len(positions) == 4
        angles = [a for a, _ in positions]
        assert angles == pytest.approx([0.0, 90.0, 180.0, 270.0])
        assert all(m for _, m in positions)

    def test_full_circle_with_minor(self):
        positions = generate_angular_positions(4, minor_subdivisions=4)
        assert len(positions) == 20
        majors = [a for a, m in positions if m]
        minors = [a for a, m in positions if not m]
        assert len(majors) == 4
        assert len(minors) == 16
        assert majors == pytest.approx([0.0, 90.0, 180.0, 270.0])

    def test_partial_arc(self):
        positions = generate_angular_positions(3, start_deg=0.0, end_deg=180.0)
        assert len(positions) == 3
        angles = [a for a, _ in positions]
        assert angles == pytest.approx([0.0, 90.0, 180.0])

    def test_single_ray(self):
        positions = generate_angular_positions(1)
        assert len(positions) == 1
        assert positions[0] == pytest.approx((0.0, True))

    def test_single_ray_partial_arc(self):
        positions = generate_angular_positions(1, start_deg=45.0, end_deg=135.0)
        assert len(positions) == 1
        assert positions[0][0] == pytest.approx(45.0)

    def test_twelve_rays_sixty_positions(self):
        positions = generate_angular_positions(12, minor_subdivisions=4)
        assert len(positions) == 60
        majors = [a for a, m in positions if m]
        assert len(majors) == 12
        assert majors[0] == pytest.approx(0.0)
        assert majors[1] == pytest.approx(30.0)

    def test_protractor_reaches_endpoint(self):
        positions = generate_angular_positions(18, minor_subdivisions=10, start_deg=0.0, end_deg=180.0)
        assert positions[-1][0] == pytest.approx(180.0)


class TestRadialPoint:
    def test_zero_angle(self):
        x, y = radial_point((0.0, 0.0), 100.0, 0.0)
        assert x == pytest.approx(100.0)
        assert y == pytest.approx(0.0)

    def test_ninety_degrees(self):
        x, y = radial_point((0.0, 0.0), 100.0, 90.0)
        assert x == pytest.approx(0.0, abs=1e-10)
        assert y == pytest.approx(100.0)

    def test_with_offset_center(self):
        x, y = radial_point((50.0, 50.0), 100.0, 0.0)
        assert x == pytest.approx(150.0)
        assert y == pytest.approx(50.0)


class TestRadialPocketGenerator:
    def _domain(self, size=300.0):
        return Domain.from_rectangle(size, size, center=(size / 2, size / 2))

    def test_four_ray_triangle(self):
        params = RadialPocketParams(rays=4, depth_mm=6.0, bar_width_mm=20.0)
        items = radial_pocket_generator(self._domain(), params)
        assert len(items) == 4
        for item in items:
            assert item.type == "Polygon"
            assert item.feature is not None
            assert item.feature.type == "pocket"
            assert item.feature.depth_mm == 6.0

    def test_six_ray_arc(self):
        params = RadialPocketParams(rays=6, depth_mm=4.0, shape="arc")
        items = radial_pocket_generator(self._domain(), params)
        assert len(items) == 6

    def test_center_island_subtracts(self):
        params_no_center = RadialPocketParams(rays=4, depth_mm=6.0)
        params_with_center = RadialPocketParams(rays=4, depth_mm=6.0, center_shape="circle", center_size_mm=50.0)
        items_no = radial_pocket_generator(self._domain(), params_no_center)
        items_with = radial_pocket_generator(self._domain(), params_with_center)
        assert len(items_no) == 4
        assert len(items_with) >= 4

    def test_large_bar_collapses_wedge(self):
        params = RadialPocketParams(rays=4, depth_mm=6.0, bar_width_mm=500.0)
        items = radial_pocket_generator(self._domain(), params, allow_empty=True)
        assert items == []

    def test_partial_arc(self):
        params = RadialPocketParams(rays=4, depth_mm=6.0, start_angle_deg=0.0, end_angle_deg=180.0)
        items = radial_pocket_generator(self._domain(), params)
        assert len(items) == 3


class TestRadialPocketParams:
    def test_invalid_rays(self):
        with pytest.raises(ValueError, match="rays must be >= 2"):
            RadialPocketParams(rays=1, depth_mm=6.0)

    def test_invalid_depth(self):
        with pytest.raises(ValueError, match="depth_mm must be positive"):
            RadialPocketParams(rays=4, depth_mm=0)

    def test_invalid_center_shape(self):
        with pytest.raises(ValueError, match="center_shape must be one of"):
            RadialPocketParams(rays=4, depth_mm=6.0, center_shape="pentagon", center_size_mm=50.0)

    def test_center_shape_requires_size(self):
        with pytest.raises(ValueError, match="center_size_mm required"):
            RadialPocketParams(rays=4, depth_mm=6.0, center_shape="circle")

    def test_invalid_shape(self):
        with pytest.raises(ValueError, match="shape must be one of"):
            RadialPocketParams(rays=4, depth_mm=6.0, shape="star")  # type: ignore[arg-type]


class TestRadialTickGenerator:
    def _domain(self, size=300.0):
        return Domain.from_rectangle(size, size, center=(size / 2, size / 2))

    def test_twelve_rays_no_minor(self):
        params = RadialTickParams(rays=12, depth_mm=0.3)
        items = radial_tick_generator(self._domain(), params)
        assert len(items) == 12
        for item in items:
            assert item.type == "Line"
            assert item.feature is not None
            assert item.feature.type == "engrave"
            assert item.feature.depth_mm == 0.3

    def test_major_and_minor_counts(self):
        params = RadialTickParams(rays=4, depth_mm=0.3, minor_subdivisions=4)
        items = radial_tick_generator(self._domain(), params)
        assert len(items) == 20

    def test_labels_add_items(self):
        params_no_labels = RadialTickParams(rays=4, depth_mm=0.3)
        params_with_labels = RadialTickParams(rays=4, depth_mm=0.3, labels=True)
        items_no = radial_tick_generator(self._domain(), params_no_labels)
        items_with = radial_tick_generator(self._domain(), params_with_labels)
        assert len(items_with) > len(items_no)

    def test_label_list(self):
        params = RadialTickParams(rays=4, depth_mm=0.3, label_list=("N", "E", "S", "W"))
        items = radial_tick_generator(self._domain(), params)
        assert len(items) > 4


class TestRadialTickParams:
    def test_invalid_rays(self):
        with pytest.raises(ValueError, match="rays must be >= 1"):
            RadialTickParams(rays=0, depth_mm=0.3)

    def test_negative_minor(self):
        with pytest.raises(ValueError, match="minor_subdivisions must be non-negative"):
            RadialTickParams(rays=4, depth_mm=0.3, minor_subdivisions=-1)


class TestRadialLabelGenerator:
    def _domain(self, size=300.0):
        return Domain.from_rectangle(size, size, center=(size / 2, size / 2))

    def test_four_labels(self):
        params = RadialLabelParams(rays=4, depth_mm=0.3, values=("N", "E", "S", "W"))
        items = radial_label_generator(self._domain(), params)
        assert len(items) > 0
        for item in items:
            assert item.feature is not None
            assert item.feature.type == "engrave"

    def test_auto_values(self):
        params = RadialLabelParams(rays=3, depth_mm=0.3)
        items = radial_label_generator(self._domain(), params)
        assert len(items) > 0


class TestRadialLabelParams:
    def test_values_length_mismatch(self):
        with pytest.raises(ValueError, match="values length"):
            RadialLabelParams(rays=4, depth_mm=0.3, values=("A", "B"))


class TestRadialPMLParse:
    def test_pocket_parse_and_resolve(self):
        pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: panel
      children:
        - Radial:
            rays: 4
            depth: 6mm
            element:
              type: pocket
              bar_width: 40mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        pocket_items = [i for i in flat.items if i.feature and i.feature.type == "pocket"]
        assert len(pocket_items) == 4

    def test_tick_parse_and_resolve(self):
        pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: panel
      children:
        - Radial:
            rays: 4
            minor_subdivisions: 4
            depth: 0.3mm
            element:
              type: tick
              label_list: [N, E, S, W]
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        engrave_items = [i for i in flat.items if i.feature and i.feature.type == "engrave"]
        assert len(engrave_items) >= 20

    def test_label_parse_and_resolve(self):
        pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: panel
      children:
        - Radial:
            rays: 4
            depth: 0.3mm
            element:
              type: label
              values: [1, 2, 3, 4]
              height: 4mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        engrave_items = [i for i in flat.items if i.feature and i.feature.type == "engrave"]
        assert len(engrave_items) > 0

    def test_svg_parse_and_resolve(self):
        pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: panel
      children:
        - Radial:
            rays: 4
            depth: 0.3mm
            element:
              type: svg
              path: "M 0 0 L 20 10 L 0 20 Z"
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        engrave_items = [i for i in flat.items if i.feature and i.feature.type == "engrave"]
        assert len(engrave_items) == 4

    def test_unknown_element_type_raises(self):
        pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: panel
      children:
        - Radial:
            rays: 4
            depth: 1mm
            element:
              type: bogus
"""
        with pytest.raises(Exception, match="Unknown Radial element type"):
            parse_pml_yaml(pml)
