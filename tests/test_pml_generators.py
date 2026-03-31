from __future__ import annotations

import pytest

from layout_ast.compositional import (
    ChamferGen,
    PocketGen,
    ProfileGen,
    RaisedPanelGen,
    SplitGrid,
    SplitHorizontal,
    SplitVertical,
    WaveGen,
)
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout

PARSE_CASES = [
    pytest.param(
        "Profile:\n            side: outside\n            depth: through",
        ProfileGen,
        {"side": "outside", "depth": "through"},
        id="profile_outside_through",
    ),
    pytest.param(
        "Profile:\n            side: inside\n            depth: 10mm",
        ProfileGen,
        {"side": "inside", "depth": 10.0},
        id="profile_inside_depth",
    ),
    pytest.param(
        "Pocket:\n            depth: 6mm",
        PocketGen,
        {"depth_mm": 6.0},
        id="pocket",
    ),
    pytest.param(
        "RaisedPanel:\n            border_width: 25mm\n            border_depth: 6mm\n            field_depth: 2mm",
        RaisedPanelGen,
        {"border_width_mm": 25.0, "border_depth_mm": 6.0, "field_depth_mm": 2.0},
        id="raised_panel",
    ),
    pytest.param(
        "Chamfer:\n            width: 5mm\n            depth: 3mm",
        ChamferGen,
        {"width_mm": 5.0, "depth_mm": 3.0},
        id="chamfer",
    ),
    pytest.param(
        "Wave:\n            count: 5\n            amplitude: 10mm\n            wavelength: 60mm\n            groove: 3mm\n            depth: 2mm",
        WaveGen,
        {"wave_count": 5, "amplitude_mm": 10.0, "wavelength_mm": 60.0, "groove_width_mm": 3.0, "depth_mm": 2.0},
        id="wave",
    ),
]


@pytest.mark.parametrize("gen_yaml, expected_type, expected_fields", PARSE_CASES)
def test_parse_generator(gen_yaml, expected_type, expected_fields):
    pml = f"""
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - {gen_yaml}
"""
    ast = parse_pml_yaml(pml)
    gen = ast.root.children[0].children[0]
    assert isinstance(gen, expected_type)
    for attr, value in expected_fields.items():
        assert getattr(gen, attr) == value, f"{attr}: expected {value}, got {getattr(gen, attr)}"


def test_parse_split_horizontal():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - SplitHorizontal:
            count: 3
            gap: 20mm
            children:
              - Pocket:
                  depth: 6mm
"""
    ast = parse_pml_yaml(pml)
    split_h = ast.root.children[0].children[0]
    assert isinstance(split_h, SplitHorizontal)
    assert split_h.n == 3
    assert split_h.gap_mm == 20.0
    assert len(split_h.children) == 1
    assert isinstance(split_h.children[0], PocketGen)


def test_parse_split_vertical():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - SplitVertical:
            count: 2
            gap: 15mm
            children:
              - Pocket:
                  depth: 4mm
"""
    ast = parse_pml_yaml(pml)
    split_v = ast.root.children[0].children[0]
    assert isinstance(split_v, SplitVertical)
    assert split_v.n == 2
    assert split_v.gap_mm == 15.0
    assert len(split_v.children) == 1


def test_parse_split_grid():
    pml = """
Sheet:
  width: 500mm
  height: 700mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - SplitGrid:
            rows: 2
            cols: 2
            gap: 35mm
            children:
              - RaisedPanel:
                  border_width: 25mm
                  border_depth: 6mm
                  field_depth: 2mm
"""
    ast = parse_pml_yaml(pml)
    split_g = ast.root.children[0].children[0]
    assert isinstance(split_g, SplitGrid)
    assert split_g.rows == 2
    assert split_g.cols == 2
    assert split_g.gap_mm == 35.0
    assert len(split_g.children) == 1
    assert isinstance(split_g.children[0], RaisedPanelGen)


def test_resolve_profile_gen():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    assert len(ast.items) == 2

    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    assert len(profile_items) == 1

    profile_item = profile_items[0]
    assert profile_item.feature is not None
    assert profile_item.feature.side == "outside"
    assert profile_item.feature.is_through


def test_resolve_pocket_gen():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Pocket:
            depth: 6mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    pocket_items = [i for i in ast.items if i.shape_id and i.shape_id.startswith("generated_pocket")]
    assert len(pocket_items) == 1

    pocket_item = pocket_items[0]
    assert pocket_item.feature is not None
    assert pocket_item.feature.type == "pocket"
    assert pocket_item.feature.depth_mm == 6.0


def test_resolve_raised_panel_gen():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - RaisedPanel:
            border_width: 25mm
            border_depth: 6mm
            field_depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    border_items = [i for i in ast.items if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 1, f"Expected 1 border item, got {len(border_items)}"
    assert len(field_items) == 1, f"Expected 1 field item, got {len(field_items)}"

    assert border_items[0].feature is not None
    assert border_items[0].feature.type == "bevel", f"Expected bevel, got {border_items[0].feature.type}"
    assert border_items[0].feature.depth_mm == 6.0
    assert field_items[0].feature is not None
    assert field_items[0].feature.type == "pocket", f"Expected pocket, got {field_items[0].feature.type}"
    assert field_items[0].feature.depth_mm == 2.0


def test_resolve_split_grid_with_raised_panel():
    pml = """
Sheet:
  width: 500mm
  height: 700mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - SplitGrid:
            rows: 2
            cols: 2
            gap: 35mm
            children:
              - RaisedPanel:
                  border_width: 25mm
                  border_depth: 6mm
                  field_depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    border_items = [i for i in ast.items if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 4, f"Expected 4 border items, got {len(border_items)}"
    assert len(field_items) == 4, f"Expected 4 field items, got {len(field_items)}"


def test_resolve_wave_gen():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Wave:
            count: 5
            amplitude: 10mm
            wavelength: 60mm
            groove: 3mm
            depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    wave_items = [i for i in ast.items if i.shape_id and "wave" in i.shape_id]
    assert len(wave_items) >= 1, f"Expected wave items, got {len(wave_items)}"

    for item in wave_items:
        assert item.feature is not None
        assert item.feature.type == "engrave", f"Expected engrave, got {item.feature.type}"
        assert item.feature.depth_mm == 2.0


def test_example_shaker_door():
    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: 50mm
            children:
              - Pocket:
                  depth: 6mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    assert len(ast.items) >= 3

    feature_types = {i.feature.type for i in ast.items if i.feature}
    assert "profile" in feature_types
    assert "pocket" in feature_types


def test_example_four_panel_door():
    pml = """
Sheet:
  width: 500mm
  height: 700mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: 65mm
            children:
              - SplitGrid:
                  rows: 2
                  cols: 2
                  gap: 35mm
                  children:
                    - RaisedPanel:
                        border_width: 25mm
                        border_depth: 6mm
                        field_depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    raised_items = [i for i in ast.items if i.shape_id and ("_border" in i.shape_id or "_field" in i.shape_id)]

    assert len(profile_items) >= 1, "Should have at least one profile"
    assert len(raised_items) == 8, f"Should have 8 raised panel items (4 borders + 4 fields), got {len(raised_items)}"


def test_example_wave_texture_panel():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Wave:
            count: 5
            amplitude: 10mm
            wavelength: 60mm
            groove: 3mm
            depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    wave_items = [i for i in ast.items if i.shape_id and "wave" in i.shape_id]

    assert len(profile_items) >= 1, "Should have profile"
    assert len(wave_items) >= 1, "Should have wave engrave items"
