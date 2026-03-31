from __future__ import annotations

from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_circle_with_explicit_diameter():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Circle:
      id: medallion
      diameter: 120mm
      feature:
        type: pocket
        depth: 3mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"
    assert item.shape_id == "medallion"
    assert item.geometry is not None
    assert item.geometry.data["diameter_mm"] == 120.0
    assert item.feature is not None
    assert item.feature.type == "pocket"

    assert item.placement is not None
    assert item.placement.center_xy_mm == (200.0, 300.0)


def test_circle_fit_mode():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Circle:
      fit: true
      feature:
        type: pocket
        depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"

    assert item.geometry is not None
    assert item.geometry.data["diameter_mm"] == 400.0
    assert item.placement is not None
    assert item.placement.center_xy_mm == (200.0, 300.0)


def test_circle_fit_in_rect_region():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Inset:
      distance: 50mm
      children:
        - Circle:
            id: badge
            fit: true
            feature:
              type: profile
              side: outside
              depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"

    assert item.geometry is not None
    assert item.geometry.data["diameter_mm"] == 300.0

    assert item.placement is not None
    assert item.placement.center_xy_mm == (200.0, 300.0)


def test_rounded_rect_fills_region():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - RoundedRect:
      id: badge
      radius: 8mm
      feature:
        type: pocket
        depth: 3mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "RoundedRect"
    assert item.shape_id == "badge"

    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.geometry.data["radius_mm"] == 8.0
    assert item.feature is not None
    assert item.feature.type == "pocket"


def test_rounded_rect_with_inset():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Inset:
      distance: 25mm
      children:
        - RoundedRect:
            id: panel
            radius: 12mm
            feature:
              type: profile
              side: outside
              depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "RoundedRect"

    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0

    assert item.geometry.data["radius_mm"] == 12.0


def test_line_horizontal():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Line:
      id: decoration
      orientation: horizontal
      feature:
        type: engrave
        depth: 1.5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"
    assert item.kind == "shape"

    assert item.placement is not None
    cx, cy = item.placement.center_xy_mm
    assert item.geometry is not None
    start = item.geometry.data["start"]
    end = item.geometry.data["end"]
    assert approx_equal(cx, 200.0)
    assert approx_equal(cy, 300.0)
    assert approx_equal(start[0] + cx, 0.0)
    assert approx_equal(start[1] + cy, 300.0)
    assert approx_equal(end[0] + cx, 400.0)
    assert approx_equal(end[1] + cy, 300.0)
    assert item.feature is not None
    assert item.feature.type == "engrave"
    assert item.feature.depth_mm == 1.5


def test_line_vertical():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Line:
      id: divider
      orientation: vertical
      feature:
        type: engrave
        depth: 1.5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"

    assert item.placement is not None
    cx, cy = item.placement.center_xy_mm
    assert item.geometry is not None
    start = item.geometry.data["start"]
    end = item.geometry.data["end"]
    assert approx_equal(start[0] + cx, 200.0)
    assert approx_equal(start[1] + cy, 0.0)
    assert approx_equal(end[0] + cx, 200.0)
    assert approx_equal(end[1] + cy, 600.0)
    assert item.feature is not None
    assert item.feature.depth_mm == 1.5


def test_line_in_inset_region():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Inset:
      distance: 50mm
      children:
        - Line:
            id: flourish
            orientation: horizontal
            feature:
              type: engrave
              depth: 1.5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"

    assert item.placement is not None
    cx, cy = item.placement.center_xy_mm
    assert item.geometry is not None
    start = item.geometry.data["start"]
    end = item.geometry.data["end"]
    assert approx_equal(start[0] + cx, 50.0)
    assert approx_equal(start[1] + cy, 300.0)
    assert approx_equal(end[0] + cx, 350.0)
    assert approx_equal(end[1] + cy, 300.0)
    assert item.feature is not None
    assert item.feature.depth_mm == 1.5


def test_round_trip_circle():
    original_pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

project: test_circle

children:
  - Circle:
      id: badge
      diameter: 100mm
      feature:
        type: pocket
        depth: 5mm
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].type == flat2.items[0].type
    assert flat1.items[0].geometry is not None
    assert flat2.items[0].geometry is not None
    assert flat1.items[0].geometry.data == flat2.items[0].geometry.data


def test_round_trip_rounded_rect():
    original_pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - RoundedRect:
      id: panel
      radius: 10mm
      feature:
        type: profile
        side: outside
        depth: through
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry is not None
    assert flat2.items[0].geometry is not None
    assert flat1.items[0].geometry.data["radius_mm"] == flat2.items[0].geometry.data["radius_mm"]


def test_round_trip_line():
    original_pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Line:
      id: decoration
      orientation: vertical
      feature:
        type: engrave
        depth: 1.5mm
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry is not None
    assert flat2.items[0].geometry is not None
    assert flat1.items[0].geometry.data["start"] == flat2.items[0].geometry.data["start"]
    assert flat1.items[0].geometry.data["end"] == flat2.items[0].geometry.data["end"]
    assert flat1.items[0].feature is not None
    assert flat2.items[0].feature is not None
    assert flat1.items[0].feature.depth_mm == flat2.items[0].feature.depth_mm


def test_mixed_shapes_composition():
    pml = """
Sheet:
  width: 800mm
  height: 600mm
  thickness: 19mm

project: mixed_shapes

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 40mm
            children:
              - Grid:
                  rows: 2
                  cols: 2
                  gap: 20mm
                  children:
                    - Cell:
                        children:
                          - Circle:
                              fit: true
                              feature:
                                type: pocket
                                depth: 5mm

  - RoundedRect:
      id: badge
      radius: 8mm
      feature:
        type: profile
        side: outside
        depth: through

  - Line:
      id: divider
      orientation: horizontal
      feature:
        type: engrave
        depth: 1.5mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    circles = [item for item in flat.items if item.type == "Circle"]
    rects = [item for item in flat.items if item.type == "Rect"]
    rounded_rects = [item for item in flat.items if item.type == "RoundedRect"]
    lines = [item for item in flat.items if item.type == "Line"]

    assert len(flat.items) == 7
    assert len(circles) == 4
    assert len(rects) == 1
    assert len(rounded_rects) == 1
    assert len(lines) == 1
    assert lines[0].feature is not None
    assert lines[0].feature.depth_mm == 1.5


def test_rounded_rect_selective_corners():
    pml = """
Sheet:
  width: 686mm
  height: 864mm
  thickness: 19mm

children:
  - RoundedRect:
      id: table_half
      radius: 12.7mm
      corners: [tl, bl]
      feature:
        type: profile
        side: outside
        depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "RoundedRect"
    assert item.shape_id == "table_half"

    assert item.geometry is not None
    assert item.geometry.data["radius_tl_mm"] == 12.7
    assert item.geometry.data["radius_tr_mm"] == 0.0
    assert item.geometry.data["radius_bl_mm"] == 12.7
    assert item.geometry.data["radius_br_mm"] == 0.0


def test_rounded_rect_all_corners_explicit():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - RoundedRect:
      id: panel
      radius: 10mm
      corners: [tl, tr, bl, br]
      feature:
        type: pocket
        depth: 3mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.geometry is not None
    assert item.geometry.data["radius_tl_mm"] == 10.0
    assert item.geometry.data["radius_tr_mm"] == 10.0
    assert item.geometry.data["radius_bl_mm"] == 10.0
    assert item.geometry.data["radius_br_mm"] == 10.0
    assert item.geometry.data["radius_mm"] == 10.0


def test_rounded_rect_single_corner():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - RoundedRect:
      id: corner_piece
      radius: 25mm
      corners: [tr]
      feature:
        type: profile
        side: outside
        depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.geometry is not None
    assert item.geometry.data["radius_tl_mm"] == 0.0
    assert item.geometry.data["radius_tr_mm"] == 25.0
    assert item.geometry.data["radius_bl_mm"] == 0.0
    assert item.geometry.data["radius_br_mm"] == 0.0


def test_rounded_rect_corners_round_trip():
    original_pml = """
Sheet:
  width: 686mm
  height: 864mm
  thickness: 19mm

children:
  - RoundedRect:
      id: table_half
      radius: 12.7mm
      corners: [tl, bl]
      feature:
        type: profile
        side: outside
        depth: through
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry is not None
    assert flat2.items[0].geometry is not None
    assert flat1.items[0].geometry.data["radius_tl_mm"] == flat2.items[0].geometry.data["radius_tl_mm"]
    assert flat1.items[0].geometry.data["radius_tr_mm"] == flat2.items[0].geometry.data["radius_tr_mm"]
    assert flat1.items[0].geometry.data["radius_bl_mm"] == flat2.items[0].geometry.data["radius_bl_mm"]
    assert flat1.items[0].geometry.data["radius_br_mm"] == flat2.items[0].geometry.data["radius_br_mm"]

    assert "corners:" in formatted or "corners" in formatted


def test_acceptance_canonical_formatting():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

project: shape_test

children:
  - Circle:
      id: badge
      diameter: 120mm
      feature:
        type: pocket
        depth: 3mm

  - RoundedRect:
      id: panel
      radius: 12mm
      feature:
        type: profile
        side: outside
        depth: through

  - Line:
      id: decoration
      orientation: horizontal
      feature:
        type: engrave
        depth: 1.5mm
"""

    ast = parse_pml_yaml(pml)
    formatted1 = format_pml_yaml(ast)
    ast2 = parse_pml_yaml(formatted1)
    formatted2 = format_pml_yaml(ast2)

    assert formatted1 == formatted2
    assert "Circle:" in formatted1
    assert "RoundedRect:" in formatted1
    assert "Line:" in formatted1


def test_rounded_rect_with_profile_child_inherits_geometry():
    pml = """
Sheet:
  width: 584mm
  height: 584mm
  thickness: 19mm

children:
  - RoundedRect:
      id: panel
      radius: 25.4mm
      corners: [bl, br]
      feature:
        type: profile
        side: outside
        depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1

    item = flat.items[0]
    assert item.type == "RoundedRect"
    assert item.shape_id == "panel"
    assert item.geometry is not None
    assert item.geometry.data["radius_bl_mm"] == 25.4
    assert item.geometry.data["radius_br_mm"] == 25.4
    assert item.geometry.data["radius_tl_mm"] == 0.0
    assert item.geometry.data["radius_tr_mm"] == 0.0
    assert item.feature is not None
    assert item.feature.type == "profile"
    assert item.feature.side == "outside"


def test_rect_with_profile_child_stays_rect():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: profile
        side: outside
        depth: through
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1

    item = flat.items[0]
    assert item.type == "Rect"
    assert item.feature is not None
    assert item.feature.type == "profile"
    assert item.geometry is not None
    assert "radius_mm" not in item.geometry.data
    assert "radius_bl_mm" not in item.geometry.data
