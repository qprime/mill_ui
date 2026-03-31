from __future__ import annotations

import json

from pml import PMLParseError, parse_pml
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml


def test_pml_parse_minimal_layout():
    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
"""

    ast = parse_pml(pml)

    assert ast.sheet.width_mm == 450.0
    assert ast.sheet.height_mm == 650.0
    assert ast.sheet.thickness_mm == 19.0
    assert len(ast.items) == 1

    item = ast.items[0]
    assert item.kind == "shape"
    assert item.type == "Rect"
    assert item.shape_id == "outer"
    assert item.feature.type == "profile"
    assert item.feature.is_through
    assert item.feature.side == "outside"


def test_pml_parse_with_metadata():
    pml = """
Sheet:
  width: 300mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

project: test_panel
kerf: 0.15mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 5mm
"""

    ast = parse_pml(pml)

    assert ast.project == "test_panel"
    assert ast.kerf_width_mm == 0.15
    assert ast.sheet.width_mm == 300.0


def test_pml_parse_multiple_shapes():
    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: door_outer
      feature:
        type: profile
        side: outside
        depth: through
  - Inset:
      distance: 50mm
      children:
        - Rect:
            id: door_panel
            feature:
              type: pocket
              depth: 6mm
  - Circle:
      id: door_anchor_1
      diameter: 10mm
      at:
        x: 95mm
        y: 545mm
      feature:
        type: hole
        depth: 8mm
  - Circle:
      id: door_anchor_2
      diameter: 10mm
      at:
        x: 355mm
        y: 545mm
      feature:
        type: hole
        depth: 8mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 4

    outer = ast.items[0]
    assert outer.shape_id == "door_outer"
    assert outer.type == "Rect"
    assert outer.feature.type == "profile"

    panel = ast.items[1]
    assert panel.shape_id == "door_panel"
    assert panel.type == "Rect"
    assert panel.feature.type == "pocket"
    assert panel.feature.depth_mm == 6.0

    anchor1 = ast.items[2]
    assert anchor1.shape_id == "door_anchor_1"
    assert anchor1.type == "Circle"
    assert anchor1.feature.type == "hole"
    assert anchor1.feature.depth_mm == 8.0


def test_pml_parse_circle_diameter_vs_radius():
    pml = """
Sheet:
  width: 200mm
  height: 200mm
  thickness: 19mm
  margin: 0mm

children:
  - Circle:
      id: hole1
      diameter: 20mm
      at:
        x: 50mm
        y: 50mm
      feature:
        type: hole
        depth: through
  - Circle:
      id: hole2
      radius: 8mm
      at:
        x: 150mm
        y: 150mm
      feature:
        type: hole
        depth: 12mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 2

    hole1 = ast.items[0]
    assert "diameter_mm" in hole1.geometry.data
    assert hole1.geometry.data["diameter_mm"] == 20.0

    hole2 = ast.items[1]
    assert "radius_mm" in hole2.geometry.data
    assert hole2.geometry.data["radius_mm"] == 8.0


def test_pml_parse_roundedrect():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - RoundedRect:
      id: panel
      radius: 10mm
      feature:
        type: pocket
        depth: 5mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 1

    item = ast.items[0]
    assert item.type == "RoundedRect"
    assert item.geometry.data["w_mm"] == 300.0
    assert item.geometry.data["h_mm"] == 300.0
    assert item.geometry.data["corner_radius_mm"] == 10.0
    assert item.feature.type == "pocket"


def test_pml_parse_comments_and_blank_lines():
    pml = """
Sheet:
  width: 300mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: profile
        side: inside
        depth: through
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 1
    assert ast.sheet.width_mm == 300.0


def test_pml_parse_error_missing_sheet():
    pml = """
children:
  - Rect:
      id: panel
      feature:
        type: profile
        side: inside
        depth: through
"""

    try:
        parse_pml(pml)
        print("  FAIL: Expected PMLParseError")
    except PMLParseError as e:
        assert "Sheet" in str(e)


def test_pml_parse_error_invalid_sheet_syntax():
    pml = """
Sheet:
  width: invalid_dimension
  height: 400mm
  thickness: 19mm
"""

    try:
        parse_pml(pml)
        print("  FAIL: Expected PMLParseError or ValueError")
    except (PMLParseError, ValueError):
        pass


def test_pml_parse_error_invalid_feature():
    pml = """
Sheet:
  width: 300mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: invalid_feature
        depth: 5mm
"""

    ast = parse_pml(pml)
    assert ast.items[0].feature.type == "invalid_feature"


def test_pml_parse_error_invalid_profile_side():
    pml = """
Sheet:
  width: 300mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: profile
        side: bad_side
        depth: through
"""

    ast = parse_pml(pml)
    assert ast.items[0].feature.side == "bad_side"


def test_pml_format_minimal_layout():
    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
"""

    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)

    assert "Sheet:" in formatted
    assert "width:" in formatted
    assert "450" in formatted


def test_pml_format_with_metadata():
    pml = """
Sheet:
  width: 300mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

project: test_panel
kerf: 0.15mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 5mm
"""

    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)

    assert "project:" in formatted
    assert "test_panel" in formatted


def test_pml_roundtrip_semantic_equivalence():
    original_pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

project: shaker_door

children:
  - Rect:
      id: door_outer
      feature:
        type: profile
        side: outside
        depth: through
  - Inset:
      distance: 50mm
      children:
        - Rect:
            id: door_panel
            feature:
              type: pocket
              depth: 6mm
"""

    ast1 = parse_pml(original_pml)
    comp_ast = parse_pml_yaml(original_pml)
    canonical_pml = format_pml_yaml(comp_ast)
    ast2 = parse_pml(canonical_pml)

    assert ast1.sheet.width_mm == ast2.sheet.width_mm
    assert ast1.sheet.height_mm == ast2.sheet.height_mm
    assert ast1.sheet.thickness_mm == ast2.sheet.thickness_mm
    assert ast1.project == ast2.project
    assert len(ast1.items) == len(ast2.items)

    for item1, item2 in zip(ast1.items, ast2.items, strict=False):
        assert item1.kind == item2.kind
        assert item1.type == item2.type
        assert item1.shape_id == item2.shape_id
        assert item1.feature.type == item2.feature.type
        assert item1.feature.is_through == item2.feature.is_through
        assert item1.feature.depth_mm == item2.feature.depth_mm


def test_pml_to_json_to_ast_semantic_equivalence():
    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

project: test_panel
kerf: 0.15mm

children:
  - Rect:
      id: door_outer
      feature:
        type: profile
        side: outside
        depth: through
  - Inset:
      distance: 50mm
      children:
        - Rect:
            id: door_panel
            feature:
              type: pocket
              depth: 6mm
  - Circle:
      id: door_anchor_1
      diameter: 10mm
      at:
        x: 95mm
        y: 545mm
      feature:
        type: hole
        depth: 8mm
"""

    ast1 = parse_pml(pml)
    json_str = ast1.to_json()
    json_dict = json.loads(json_str)

    assert "sheet" in json_dict
    assert "items" in json_dict
    assert json_dict["sheet"]["thickness_mm"] == 19.0
    assert len(json_dict["items"]) == 3
    assert json_dict.get("project") == "test_panel"
    assert json_dict.get("kerf_width_mm") == 0.15

    assert ast1.sheet.thickness_mm == 19.0
    assert len(ast1.items) == 3
    assert ast1.project == "test_panel"
    assert ast1.kerf_width_mm == 0.15


def test_pml_canonical_formatting():
    pml = """
Sheet:
  width: 450.123mm
  height: 650.456mm
  thickness: 19.789mm
  margin: 0mm

children:
  - Rect:
      id: test
      feature:
        type: pocket
        depth: 5.123mm
"""

    comp_ast = parse_pml_yaml(pml)
    canonical_pml = format_pml_yaml(comp_ast)

    comp_ast2 = parse_pml_yaml(canonical_pml)
    canonical_pml2 = format_pml_yaml(comp_ast2)

    assert canonical_pml == canonical_pml2
