
from __future__ import annotations

import sys

from pml.yaml_parser import parse_pml_yaml, PMLParseError
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import (
    ProfileGen,
    PocketGen,
    RaisedPanelGen,
    ChamferGen,
    WaveGen,
    SplitHorizontal,
    SplitVertical,
    SplitGrid,
)


def test_parse_profile_gen_outside_through():
    print("Running test_parse_profile_gen_outside_through...")
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
    ast = parse_pml_yaml(pml)

    root = ast.root
    rect = root.children[0]
    assert len(rect.children) == 1

    profile = rect.children[0]
    assert isinstance(profile, ProfileGen)
    assert profile.side == "outside"
    assert profile.depth == "through"
    print("  PASS")
    return True


def test_parse_profile_gen_inside_depth():
    print("Running test_parse_profile_gen_inside_depth...")
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
            side: inside
            depth: 10mm
"""
    ast = parse_pml_yaml(pml)

    root = ast.root
    rect = root.children[0]
    profile = rect.children[0]
    assert isinstance(profile, ProfileGen)
    assert profile.side == "inside"
    assert profile.depth == 10.0
    print("  PASS")
    return True


def test_parse_pocket_gen():
    print("Running test_parse_pocket_gen...")
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
    ast = parse_pml_yaml(pml)

    root = ast.root
    rect = root.children[0]
    pocket = rect.children[0]
    assert isinstance(pocket, PocketGen)
    assert pocket.depth_mm == 6.0
    print("  PASS")
    return True


def test_parse_raised_panel_gen():
    print("Running test_parse_raised_panel_gen...")
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
    ast = parse_pml_yaml(pml)

    root = ast.root
    rect = root.children[0]
    raised = rect.children[0]
    assert isinstance(raised, RaisedPanelGen)
    assert raised.border_width_mm == 25.0
    assert raised.border_depth_mm == 6.0
    assert raised.field_depth_mm == 2.0
    print("  PASS")
    return True


def test_parse_chamfer_gen():
    print("Running test_parse_chamfer_gen...")
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Chamfer:
            width: 5mm
            depth: 3mm
"""
    ast = parse_pml_yaml(pml)

    root = ast.root
    rect = root.children[0]
    chamfer = rect.children[0]
    assert isinstance(chamfer, ChamferGen)
    assert chamfer.width_mm == 5.0
    assert chamfer.depth_mm == 3.0
    print("  PASS")
    return True


def test_parse_wave_gen():
    print("Running test_parse_wave_gen...")
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
    ast = parse_pml_yaml(pml)

    root = ast.root
    rect = root.children[0]
    wave = rect.children[0]
    assert isinstance(wave, WaveGen)
    assert wave.wave_count == 5
    assert wave.amplitude_mm == 10.0
    assert wave.wavelength_mm == 60.0
    assert wave.groove_width_mm == 3.0
    assert wave.depth_mm == 2.0
    print("  PASS")
    return True


def test_parse_split_horizontal():
    print("Running test_parse_split_horizontal...")
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

    root = ast.root
    rect = root.children[0]
    split_h = rect.children[0]
    assert isinstance(split_h, SplitHorizontal)
    assert split_h.n == 3
    assert split_h.gap_mm == 20.0
    assert len(split_h.children) == 1
    assert isinstance(split_h.children[0], PocketGen)
    print("  PASS")
    return True


def test_parse_split_vertical():
    print("Running test_parse_split_vertical...")
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

    root = ast.root
    rect = root.children[0]
    split_v = rect.children[0]
    assert isinstance(split_v, SplitVertical)
    assert split_v.n == 2
    assert split_v.gap_mm == 15.0
    assert len(split_v.children) == 1
    print("  PASS")
    return True


def test_parse_split_grid():
    print("Running test_parse_split_grid...")
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

    root = ast.root
    rect = root.children[0]
    split_g = rect.children[0]
    assert isinstance(split_g, SplitGrid)
    assert split_g.rows == 2
    assert split_g.cols == 2
    assert split_g.gap_mm == 35.0
    assert len(split_g.children) == 1
    assert isinstance(split_g.children[0], RaisedPanelGen)
    print("  PASS")
    return True


def test_resolve_profile_gen():
    print("Running test_resolve_profile_gen...")
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
    assert profile_item.feature.side == "outside"
    assert profile_item.feature.depth == "through"
    print("  PASS")
    return True


def test_resolve_pocket_gen():
    print("Running test_resolve_pocket_gen...")
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

    pocket_items = [i for i in ast.items
                    if i.shape_id and i.shape_id.startswith("generated_pocket")]
    assert len(pocket_items) == 1

    pocket_item = pocket_items[0]
    assert pocket_item.feature.type == "pocket"
    assert pocket_item.feature.depth_mm == 6.0
    print("  PASS")
    return True


def test_resolve_raised_panel_gen():
    print("Running test_resolve_raised_panel_gen...")
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

    border_items = [i for i in ast.items
                    if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items
                   if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 1, f"Expected 1 border item, got {len(border_items)}"
    assert len(field_items) == 1, f"Expected 1 field item, got {len(field_items)}"

    assert border_items[0].feature.type == "bevel", f"Expected bevel, got {border_items[0].feature.type}"
    assert border_items[0].feature.depth_mm == 6.0
    assert field_items[0].feature.type == "pocket", f"Expected pocket, got {field_items[0].feature.type}"
    assert field_items[0].feature.depth_mm == 2.0
    print("  PASS")
    return True


def test_resolve_split_grid_with_raised_panel():
    print("Running test_resolve_split_grid_with_raised_panel...")
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

    border_items = [i for i in ast.items
                    if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items
                   if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 4, f"Expected 4 border items, got {len(border_items)}"
    assert len(field_items) == 4, f"Expected 4 field items, got {len(field_items)}"
    print("  PASS")
    return True


def test_resolve_wave_gen():
    print("Running test_resolve_wave_gen...")
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

    wave_items = [i for i in ast.items
                  if i.shape_id and "wave" in i.shape_id]
    assert len(wave_items) >= 1, f"Expected wave items, got {len(wave_items)}"

    for item in wave_items:
        assert item.feature.type == "engrave", f"Expected engrave, got {item.feature.type}"
        assert item.feature.depth_mm == 2.0
    print("  PASS")
    return True


def test_example_shaker_door():
    print("Running test_example_shaker_door...")
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
    print("  PASS")
    return True


def test_example_four_panel_door():
    print("Running test_example_four_panel_door...")
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
    raised_items = [i for i in ast.items
                    if i.shape_id and ("_border" in i.shape_id or "_field" in i.shape_id)]

    assert len(profile_items) >= 1, "Should have at least one profile"
    assert len(raised_items) == 8, f"Should have 8 raised panel items (4 borders + 4 fields), got {len(raised_items)}"
    print("  PASS")
    return True


def test_example_wave_texture_panel():
    print("Running test_example_wave_texture_panel...")
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
    print("  PASS")
    return True


def test_parse_error_invalid_profile_side():
    print("Running test_parse_error_invalid_profile_side...")
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
            side: invalid
            depth: through
"""
    try:
        parse_pml_yaml(pml)
        print("  FAIL: Expected PMLParseError")
        return False
    except PMLParseError as e:
        pass
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_parse_profile_gen_outside_through,
        test_parse_profile_gen_inside_depth,
        test_parse_pocket_gen,
        test_parse_raised_panel_gen,
        test_parse_chamfer_gen,
        test_parse_wave_gen,
        test_parse_split_horizontal,
        test_parse_split_vertical,
        test_parse_split_grid,
        test_resolve_profile_gen,
        test_resolve_pocket_gen,
        test_resolve_raised_panel_gen,
        test_resolve_split_grid_with_raised_panel,
        test_resolve_wave_gen,
        test_example_shaker_door,
        test_example_four_panel_door,
        test_example_wave_texture_panel,
        test_parse_error_invalid_profile_side,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
