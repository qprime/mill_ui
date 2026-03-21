import math

import pytest

from domains.domain import Domain
from pml.yaml_parser import PMLParseError, parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def _resolve(pml: str):
    ast = parse_pml_yaml(pml)
    layout = resolve_layout(ast, validate=False)
    return layout.items


def _items_by_prefix(items, prefix):
    return [i for i in items if i.shape_id and i.shape_id.startswith(prefix)]


class TestShellDomainFactories:
    def test_from_circle_basic(self):
        d = Domain.from_circle(100.0)
        expected_area = math.pi * 50**2
        assert abs(d.area_mm2 - expected_area) / expected_area < 0.01

    def test_from_circle_custom_segments(self):
        d = Domain.from_circle(100.0, segments=16)
        assert len(d.outer_boundary) == 16

    def test_from_circle_with_center(self):
        d = Domain.from_circle(100.0, center=(200.0, 300.0))
        cx, cy = d.centroid
        assert abs(cx - 200.0) < 1.0
        assert abs(cy - 300.0) < 1.0

    def test_from_rounded_rect_basic(self):
        d = Domain.from_rounded_rect(200.0, 100.0, 10.0)
        assert d.area_mm2 < 200.0 * 100.0
        assert d.area_mm2 > 190.0 * 90.0

    def test_from_rounded_rect_selective_corners(self):
        d = Domain.from_rounded_rect(200.0, 100.0, 10.0, corners=("tl", "tr"))
        assert d.area_mm2 > 0

    def test_from_rounded_rect_zero_radius(self):
        d = Domain.from_rounded_rect(200.0, 100.0, 0.0)
        assert abs(d.area_mm2 - 200.0 * 100.0) < 1.0


class TestShellPMLParsing:
    def test_parse_shell_profile(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 15mm
        interior: profile
"""
        ast = parse_pml_yaml(pml)
        from layout_ast.compositional import ShellGen

        rect = ast.root.children[0]
        shell = rect.children[0]
        assert isinstance(shell, ShellGen)
        assert shell.wall_mm == 15.0
        assert shell.interior == "profile"
        assert shell.depth == "through"

    def test_parse_shell_pocket(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 20mm
        interior: pocket
        depth: 8mm
"""
        ast = parse_pml_yaml(pml)
        from layout_ast.compositional import ShellGen

        shell = ast.root.children[0].children[0]
        assert isinstance(shell, ShellGen)
        assert shell.interior == "pocket"
        assert shell.depth == 8.0

    def test_parse_shell_with_children(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 20mm
        interior: pocket
        depth: 6mm
        children:
        - Chamfer:
            width: 3mm
            depth: 2mm
"""
        ast = parse_pml_yaml(pml)
        from layout_ast.compositional import ChamferGen, ShellGen

        shell = ast.root.children[0].children[0]
        assert isinstance(shell, ShellGen)
        assert len(shell.children) == 1
        assert isinstance(shell.children[0], ChamferGen)

    def test_parse_shell_missing_wall(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        interior: profile
"""
        with pytest.raises(PMLParseError, match="wall"):
            parse_pml_yaml(pml)

    def test_parse_shell_missing_interior(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 15mm
"""
        with pytest.raises(PMLParseError, match="interior"):
            parse_pml_yaml(pml)


class TestShellResolver:
    def test_shell_profile_on_rect(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 15mm
        interior: profile
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].feature.type == "profile"
        assert interior[0].feature.side == "inside"
        assert interior[0].feature.is_through is True

    def test_shell_pocket_on_rect(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 30mm
        interior: pocket
        depth: 6mm
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].feature.type == "pocket"
        assert interior[0].feature.depth_mm == 6.0

    def test_shell_profile_on_polygon(self):
        items = _resolve("""
Sheet:
  width: 500mm
  height: 500mm
  thickness: 19mm
children:
- Polygon:
    points: [[50,50], [250,50], [250,200], [150,300], [50,200]]
    children:
    - Shell:
        wall: 15mm
        interior: profile
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].feature.type == "profile"
        assert interior[0].type == "Polygon"

    def test_shell_pocket_on_circle(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Circle:
    diameter: 200mm
    children:
    - Shell:
        wall: 20mm
        interior: pocket
        depth: 8mm
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].feature.type == "pocket"
        assert interior[0].feature.depth_mm == 8.0

    def test_shell_on_rounded_rect(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- RoundedRect:
    radius: 10mm
    children:
    - Shell:
        wall: 20mm
        interior: profile
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].type == "Polygon"

    def test_shell_on_triangle(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Triangle:
    base: 200mm
    height: 200mm
    children:
    - Shell:
        wall: 15mm
        interior: profile
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].type == "Polygon"

    def test_shell_on_arch(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Arch:
    width: 200mm
    height: 250mm
    radius: 80mm
    children:
    - Shell:
        wall: 20mm
        interior: profile
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].type == "Polygon"
        assert interior[0].feature.type == "profile"

    def test_shell_with_wall_chamfer(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 30mm
        interior: pocket
        depth: 6mm
        children:
        - Chamfer:
            width: 3mm
            depth: 2mm
""")
        chamfers = _items_by_prefix(items, "generated_chamfer")
        assert len(chamfers) == 1
        assert chamfers[0].feature.type == "chamfer"

    def test_shell_with_wall_roundover(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 30mm
        interior: pocket
        depth: 6mm
        children:
        - Roundover:
            radius: 3mm
""")
        roundovers = _items_by_prefix(items, "generated_roundover")
        assert len(roundovers) == 1
        assert roundovers[0].feature.type == "roundover"

    def test_shell_with_wall_pocket(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 40mm
        interior: pocket
        depth: 6mm
        children:
        - Pocket:
            depth: 3mm
""")
        pockets = [i for i in items if i.feature and i.feature.type == "pocket"]
        assert len(pockets) == 2
        depths = sorted(p.feature.depth_mm for p in pockets)
        assert depths == [3.0, 6.0]

    def test_shell_wall_too_thick(self):
        with pytest.raises(ValueError, match="exceeds shape capacity"):
            _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 300mm
        interior: profile
""")

    def test_shell_concave_split(self):
        with pytest.raises(ValueError, match="disjoint regions"):
            _resolve("""
Sheet:
  width: 700mm
  height: 600mm
  thickness: 19mm
children:
- Polygon:
    points: [[0,0], [200,0], [200,180], [400,180], [400,0], [600,0], [600,500], [400,500], [400,320], [200,320], [200,500], [0,500]]
    children:
    - Shell:
        wall: 70mm
        interior: profile
""")

    def test_shell_invalid_interior(self):
        with pytest.raises(ValueError, match="interior must be"):
            _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 15mm
        interior: invalid
""")

    def test_shell_pocket_through_invalid(self):
        with pytest.raises(ValueError, match="interior=pocket requires numeric depth"):
            _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 15mm
        interior: pocket
""")

    def test_shell_interior_profile_side(self):
        items = _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Polygon:
    points: [[50,50], [250,50], [250,250], [50,250]]
    children:
    - Shell:
        wall: 20mm
        interior: profile
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        assert interior[0].feature.side == "inside"

    def test_shell_nested_rejected(self):
        with pytest.raises(ValueError, match="nested Shell is not supported"):
            _resolve("""
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 30mm
        interior: pocket
        depth: 6mm
        children:
        - Shell:
            wall: 10mm
            interior: profile
""")

    def test_shell_interior_geometry_dimensions(self):
        items = _resolve("""
Sheet:
  width: 500mm
  height: 500mm
  thickness: 19mm
children:
- Rect:
    children:
    - Shell:
        wall: 30mm
        interior: pocket
        depth: 6mm
""")
        interior = _items_by_prefix(items, "shell_interior")
        assert len(interior) == 1
        points = interior[0].geometry.data["points"]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        inner_w = max(xs) - min(xs)
        inner_h = max(ys) - min(ys)
        assert abs(inner_w - 440.0) < 1.0
        assert abs(inner_h - 440.0) < 1.0
