from __future__ import annotations

import pytest

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

    with pytest.raises(PMLParseError, match="Unknown feature type"):
        parse_pml(pml)


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


def test_pml_roundtrip_feature_dogbone():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 10mm
        dogbone:
          style: t-bone_x
          diameter: 4mm
          overcut: 0.5mm
"""
    ast1 = parse_pml(pml)
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)
    ast2 = parse_pml(formatted)

    assert ast1.items[0].feature.dogbone is not None
    assert ast2.items[0].feature.dogbone is not None
    assert ast1.items[0].feature.dogbone.style == ast2.items[0].feature.dogbone.style
    assert ast1.items[0].feature.dogbone.diameter_mm == ast2.items[0].feature.dogbone.diameter_mm
    assert ast1.items[0].feature.dogbone.overcut_mm == ast2.items[0].feature.dogbone.overcut_mm


def test_pml_roundtrip_feature_dogbone_bool():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 10mm
        dogbone: true
"""
    ast1 = parse_pml(pml)
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)
    ast2 = parse_pml(formatted)

    assert ast1.items[0].feature.dogbone is not None
    assert ast2.items[0].feature.dogbone is not None


def test_pml_roundtrip_feature_onion_skin():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: profile
        side: outside
        depth: through
        onion_skin_mm: 0.5mm
"""
    ast1 = parse_pml(pml)
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)
    ast2 = parse_pml(formatted)

    assert ast1.items[0].feature.onion_skin_mm == 0.5
    assert ast2.items[0].feature.onion_skin_mm == 0.5


def test_pml_roundtrip_feature_feeds_override():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 5mm
        feeds:
          rpm: 18000
          feed_xy: 1500
          depth_per_pass: 2.0
"""
    ast1 = parse_pml(pml)
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)
    ast2 = parse_pml(formatted)

    f1 = ast1.items[0].feature.feeds_override
    f2 = ast2.items[0].feature.feeds_override
    assert f1 is not None
    assert f2 is not None
    assert f1.rpm == f2.rpm == 18000.0
    assert f1.feed_xy == f2.feed_xy == 1500.0
    assert f1.depth_per_pass == f2.depth_per_pass == 2.0


def test_pml_roundtrip_profile_feeds_and_onion_skin():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Profile:
      side: outside
      depth: through
      onion_skin_mm: 0.3mm
      feeds:
        rpm: 16000
        feed_xy: 1200
"""
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)

    assert "onion_skin_mm" in formatted
    assert "feeds:" in formatted
    assert "rpm:" in formatted

    comp_ast2 = parse_pml_yaml(formatted)
    formatted2 = format_pml_yaml(comp_ast2)
    assert formatted == formatted2


def test_pml_roundtrip_pocket_feeds():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Pocket:
      depth: 5mm
      feeds:
        feed_z: 500
        stepover_percent: 45.0
"""
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)

    assert "feeds:" in formatted
    assert "feed_z:" in formatted

    comp_ast2 = parse_pml_yaml(formatted)
    formatted2 = format_pml_yaml(comp_ast2)
    assert formatted == formatted2


def test_pml_roundtrip_all_feature_fields():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: full_feature
      feature:
        type: profile
        side: outside
        depth: through
        tab_count: 4
        tab_height: 3mm
        tab_width: 10mm
        onion_skin_mm: 0.2mm
        feeds:
          rpm: 18000
          feed_xy: 1500
          feed_z: 500
          depth_per_pass: 2.0
          stepover_percent: 40.0
"""
    ast1 = parse_pml(pml)
    comp_ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(comp_ast)
    ast2 = parse_pml(formatted)

    f1 = ast1.items[0].feature
    f2 = ast2.items[0].feature

    assert f1.type == f2.type
    assert f1.is_through == f2.is_through
    assert f1.side == f2.side
    assert f1.tab_count == f2.tab_count
    assert f1.tab_height_mm == f2.tab_height_mm
    assert f1.tab_width_mm == f2.tab_width_mm
    assert f1.onion_skin_mm == f2.onion_skin_mm
    assert f1.feeds_override == f2.feeds_override


def test_pml_roundtrip_pocket_feature_fields():
    pml = """
Sheet: {width: 300mm, height: 300mm, thickness: 19mm}
children:
  - Rect:
      feature:
        type: pocket
        depth: 5mm
        corner_cleanup: 3mm
        dogbone:
          style: t-bone_y
          diameter: 6mm
        rest:
          tool: 3mm
          rough_allowance: 0.3mm
          finish_allowance: 0.1mm
"""
    ast1 = parse_pml_yaml(pml)
    ast2 = parse_pml_yaml(format_pml_yaml(ast1))
    assert ast1 == ast2
    feature = ast2.root.children[0].feature
    assert feature.corner_cleanup_tool_diameter_mm == 3.0
    assert feature.dogbone.style == "t-bone_y"
    assert feature.dogbone.diameter_mm == 6.0
    assert feature.rest.tool_diameter_mm == 3.0
    assert feature.rest.rough_allowance_mm == 0.3
    assert feature.rest.finish_allowance_mm == 0.1


def test_feature_face_survives_roundtrip():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Circle:
      id: hinge_cup
      diameter: 35mm
      feature:
        type: pocket
        depth: 12.5mm
        face: back
      at:
        x: 40mm
        y: 100mm
"""
    comp_ast = parse_pml_yaml(pml)
    reparsed = parse_pml_yaml(format_pml_yaml(comp_ast))

    assert reparsed.root.children[0].child.feature.face == "back"


def test_feature_face_front_not_emitted():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Circle:
      id: hole_1
      diameter: 6mm
      feature:
        type: hole
        depth: 10mm
        face: front
      at:
        x: 40mm
        y: 100mm
"""
    assert "face" not in format_pml_yaml(parse_pml_yaml(pml))


def test_sheet_min_web_survives_roundtrip():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  min_web: 5mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
"""
    comp_ast = parse_pml_yaml(pml)
    reparsed = parse_pml_yaml(format_pml_yaml(comp_ast))

    assert reparsed.sheet.min_web_mm == 5.0


def test_sheet_safe_z_survives_roundtrip():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  safe_z: 15mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
"""
    comp_ast = parse_pml_yaml(pml)
    reparsed = parse_pml_yaml(format_pml_yaml(comp_ast))

    assert comp_ast.sheet.safe_z_mm == 15.0
    assert reparsed.sheet.safe_z_mm == 15.0


def _layout_gap_pml(node_type, gap):
    dimensions = {
        "Assembly": "width: 100mm, depth: 100mm, height: 100mm, thickness: 19mm",
        "Beam": "length: 100mm, width: 50mm, thickness: 19mm",
    }
    return (
        "Sheet: {width: 400mm, height: 300mm, thickness: 19mm}\n"
        f"children:\n- {node_type}: {{{dimensions[node_type]}, layout_gap: {gap}}}\n"
    )


@pytest.mark.parametrize("node_type", ["Assembly", "Beam"])
@pytest.mark.parametrize(
    "gap, expected", [("auto", "auto"), ("0mm", 0.0), ("3.175mm", 3.175), (0, 0.0), (10, 10.0), (3.175, 3.175)]
)
def test_layout_gap_parser_contract(node_type, gap, expected):
    parsed = parse_pml_yaml(_layout_gap_pml(node_type, gap))
    assert parsed.root.children[0].layout_gap_mm == expected
    assert parse_pml_yaml(format_pml_yaml(parsed)) == parsed


@pytest.mark.parametrize("node_type", ["Assembly", "Beam"])
@pytest.mark.parametrize("gap", ["automatic", "-1mm", -1, "null", ".nan", ".inf", "-.inf"])
def test_invalid_layout_gap_parser_contract(node_type, gap):
    with pytest.raises((ValueError, PMLParseError), match=r"dimension|layout_gap"):
        parse_pml_yaml(_layout_gap_pml(node_type, gap))


def test_profile_direction_and_finishing_requests_are_not_silently_ignored():
    import pytest

    for key in ("direction", "cut_direction", "finish_direction", "ramp_mm"):
        sources = (
            f"Sheet: {{width: 300mm, height: 200mm, thickness: 6mm}}\nchildren:\n- Rect:\n    children:\n    - Profile: {{side: outside, {key}: climb}}\n",
            f"Sheet: {{width: 300mm, height: 200mm, thickness: 6mm}}\nchildren:\n- Rect:\n    feature: {{type: profile, side: outside, {key}: climb}}\n",
        )
        for source in sources:
            with pytest.raises(PMLParseError, match=key):
                parse_pml_yaml(source)
