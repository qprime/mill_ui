"""Tests for PML Generator Syntax (Stage 12).

Tests the parsing and resolution of generator keywords in compositional PML.
"""

from __future__ import annotations

import sys

from pml.compositional_parser import parse_compositional_pml, ParseError
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


# =============================================================================
# Parser Tests - verify AST nodes are created correctly
# =============================================================================


def test_parse_profile_gen_outside_through():
    """Test parsing: profile outside through"""
    print("Running test_parse_profile_gen_outside_through...")
    pml = """
sheet 400mm 600mm 19mm

rect door
    profile outside through
"""
    ast = parse_compositional_pml(pml)

    # The root should contain a rect with a profile child
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
    """Test parsing: profile inside 10mm"""
    print("Running test_parse_profile_gen_inside_depth...")
    pml = """
sheet 400mm 600mm 19mm

rect door
    profile inside 10mm
"""
    ast = parse_compositional_pml(pml)

    root = ast.root
    rect = root.children[0]
    profile = rect.children[0]
    assert isinstance(profile, ProfileGen)
    assert profile.side == "inside"
    assert profile.depth == 10.0
    print("  PASS")
    return True


def test_parse_pocket_gen():
    """Test parsing: pocket 6mm"""
    print("Running test_parse_pocket_gen...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    pocket 6mm
"""
    ast = parse_compositional_pml(pml)

    root = ast.root
    rect = root.children[0]
    pocket = rect.children[0]
    assert isinstance(pocket, PocketGen)
    assert pocket.depth_mm == 6.0
    print("  PASS")
    return True


def test_parse_raised_panel_gen():
    """Test parsing: raised_panel border 25mm border_depth 6mm field_depth 2mm"""
    print("Running test_parse_raised_panel_gen...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    raised_panel border 25mm border_depth 6mm field_depth 2mm
"""
    ast = parse_compositional_pml(pml)

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
    """Test parsing: chamfer 5mm 3mm"""
    print("Running test_parse_chamfer_gen...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    chamfer 5mm 3mm
"""
    ast = parse_compositional_pml(pml)

    root = ast.root
    rect = root.children[0]
    chamfer = rect.children[0]
    assert isinstance(chamfer, ChamferGen)
    assert chamfer.width_mm == 5.0
    assert chamfer.depth_mm == 3.0
    print("  PASS")
    return True


def test_parse_wave_gen():
    """Test parsing: wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm"""
    print("Running test_parse_wave_gen...")
    pml = """
sheet 300mm 300mm 19mm

rect panel
    wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
"""
    ast = parse_compositional_pml(pml)

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
    """Test parsing: split_horizontal 3 gap 20mm"""
    print("Running test_parse_split_horizontal...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    split_horizontal 3 gap 20mm
        pocket 6mm
"""
    ast = parse_compositional_pml(pml)

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
    """Test parsing: split_vertical 2 gap 15mm"""
    print("Running test_parse_split_vertical...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    split_vertical 2 gap 15mm
        pocket 4mm
"""
    ast = parse_compositional_pml(pml)

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
    """Test parsing: split_grid 2 2 gap 35mm"""
    print("Running test_parse_split_grid...")
    pml = """
sheet 500mm 700mm 19mm

rect door
    split_grid 2 2 gap 35mm
        raised_panel border 25mm border_depth 6mm field_depth 2mm
"""
    ast = parse_compositional_pml(pml)

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


# =============================================================================
# Resolution Tests - verify Items are generated correctly
# =============================================================================


def test_resolve_profile_gen():
    """Test resolution of profile generator to LayoutAST Item."""
    print("Running test_resolve_profile_gen...")
    pml = """
sheet 400mm 600mm 19mm

rect door
    profile outside through
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Should have 2 items: the rect and the profile
    assert len(ast.items) == 2

    # Find the profile item
    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    assert len(profile_items) == 1

    profile_item = profile_items[0]
    assert profile_item.feature.side == "outside"
    assert profile_item.feature.depth == "through"
    print("  PASS")
    return True


def test_resolve_pocket_gen():
    """Test resolution of pocket generator to LayoutAST Item."""
    print("Running test_resolve_pocket_gen...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    pocket 6mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Find the generated pocket item
    pocket_items = [i for i in ast.items
                    if i.shape_id and i.shape_id.startswith("generated_pocket")]
    assert len(pocket_items) == 1

    pocket_item = pocket_items[0]
    assert pocket_item.feature.type == "pocket"
    assert pocket_item.feature.depth_mm == 6.0
    print("  PASS")
    return True


def test_resolve_raised_panel_gen():
    """Test resolution of raised_panel generator to LayoutAST Items."""
    print("Running test_resolve_raised_panel_gen...")
    pml = """
sheet 400mm 600mm 19mm

rect panel
    raised_panel border 25mm border_depth 6mm field_depth 2mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Should have: rect + border (bevel) + field (pocket) = 3+ items
    # The raised_panel_generator creates items with shape_id pattern:
    # "generated_<prefix>_border" and "generated_<prefix>_field"
    border_items = [i for i in ast.items
                    if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items
                   if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 1, f"Expected 1 border item, got {len(border_items)}"
    assert len(field_items) == 1, f"Expected 1 field item, got {len(field_items)}"

    # Border should be a bevel feature (not pocket)
    assert border_items[0].feature.type == "bevel", f"Expected bevel, got {border_items[0].feature.type}"
    assert border_items[0].feature.depth_mm == 6.0
    # Field should be a pocket
    assert field_items[0].feature.type == "pocket", f"Expected pocket, got {field_items[0].feature.type}"
    assert field_items[0].feature.depth_mm == 2.0
    print("  PASS")
    return True


def test_resolve_split_grid_with_raised_panel():
    """Test resolution of split_grid with raised_panel children."""
    print("Running test_resolve_split_grid_with_raised_panel...")
    pml = """
sheet 500mm 700mm 19mm

rect door
    split_grid 2 2 gap 35mm
        raised_panel border 25mm border_depth 6mm field_depth 2mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Should have 4 cells × (border + field) = 8 raised panel items
    # Using updated shape_id pattern from raised_panel_generator
    border_items = [i for i in ast.items
                    if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items
                   if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 4, f"Expected 4 border items, got {len(border_items)}"
    assert len(field_items) == 4, f"Expected 4 field items, got {len(field_items)}"
    print("  PASS")
    return True


def test_resolve_wave_gen():
    """Test resolution of wave generator to LayoutAST Items.

    Wave generator produces engrave polylines (not a single "wave" item),
    which correctly map to the engraves bucket in v1 hint export.
    """
    print("Running test_resolve_wave_gen...")
    pml = """
sheet 300mm 300mm 19mm

rect panel
    wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Wave generator produces engrave polylines with "wave" in shape_id
    wave_items = [i for i in ast.items
                  if i.shape_id and "wave" in i.shape_id]
    assert len(wave_items) >= 1, f"Expected wave items, got {len(wave_items)}"

    # Check that items are engraves (not "wave" feature type)
    for item in wave_items:
        assert item.feature.type == "engrave", f"Expected engrave, got {item.feature.type}"
        assert item.feature.depth_mm == 2.0
    print("  PASS")
    return True


# =============================================================================
# Integration Tests - full PML examples from enhancement spec
# =============================================================================


def test_example_shaker_door():
    """Test the example from the spec: simple shaker door in PML."""
    print("Running test_example_shaker_door...")
    pml = """
sheet 450mm 650mm 19mm

rect door
    profile outside through
    frame 50mm
        pocket 6mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Should have: outer rect (profile) + outer profile + inner rect + inner pocket
    assert len(ast.items) >= 3

    # Check we have profile and pocket features
    feature_types = {i.feature.type for i in ast.items if i.feature}
    assert "profile" in feature_types
    assert "pocket" in feature_types
    print("  PASS")
    return True


def test_example_four_panel_door():
    """Test the example from the spec: four-panel raised door."""
    print("Running test_example_four_panel_door...")
    pml = """
sheet 500mm 700mm 19mm

rect door
    profile outside through
    frame 65mm
        split_grid 2 2 gap 35mm
            raised_panel border 25mm border_depth 6mm field_depth 2mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Check we have the expected structure
    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    # Using updated shape_id pattern: "_border" and "_field" instead of "raised_border" / "raised_field"
    raised_items = [i for i in ast.items
                    if i.shape_id and ("_border" in i.shape_id or "_field" in i.shape_id)]

    assert len(profile_items) >= 1, "Should have at least one profile"
    assert len(raised_items) == 8, f"Should have 8 raised panel items (4 borders + 4 fields), got {len(raised_items)}"
    print("  PASS")
    return True


def test_example_wave_texture_panel():
    """Test the example from the spec: wave texture panel.

    Wave generator produces engrave polylines, so we check for engrave feature type.
    """
    print("Running test_example_wave_texture_panel...")
    pml = """
sheet 300mm 300mm 19mm

rect panel
    profile outside through
    wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
"""
    comp_ast = parse_compositional_pml(pml)
    ast = resolve_layout(comp_ast)

    # Check for both profile and wave-generated engraves
    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    wave_items = [i for i in ast.items if i.shape_id and "wave" in i.shape_id]

    assert len(profile_items) >= 1, "Should have profile"
    assert len(wave_items) >= 1, "Should have wave engrave items"
    print("  PASS")
    return True


# =============================================================================
# Error Tests
# =============================================================================


def test_parse_error_invalid_profile_side():
    """Test that invalid profile side raises ParseError."""
    print("Running test_parse_error_invalid_profile_side...")
    pml = """
sheet 400mm 600mm 19mm

rect door
    profile invalid through
"""
    try:
        parse_compositional_pml(pml)
        print("  FAIL: Expected ParseError")
        return False
    except ParseError as e:
        if "Expected profile side" in str(e):
            pass
        else:
            print(f"  FAIL: Wrong error message: {e}")
            return False
    print("  PASS")
    return True


def test_parse_error_missing_depth():
    """Test that missing depth raises ParseError."""
    print("Running test_parse_error_missing_depth...")
    pml = """
sheet 400mm 600mm 19mm

rect door
    profile outside
"""
    try:
        parse_compositional_pml(pml)
        print("  FAIL: Expected ParseError")
        return False
    except ParseError as e:
        # Should fail because 'outside' is followed by newline, not depth
        pass
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        # Parser tests
        test_parse_profile_gen_outside_through,
        test_parse_profile_gen_inside_depth,
        test_parse_pocket_gen,
        test_parse_raised_panel_gen,
        test_parse_chamfer_gen,
        test_parse_wave_gen,
        test_parse_split_horizontal,
        test_parse_split_vertical,
        test_parse_split_grid,
        # Resolution tests
        test_resolve_profile_gen,
        test_resolve_pocket_gen,
        test_resolve_raised_panel_gen,
        test_resolve_split_grid_with_raised_panel,
        test_resolve_wave_gen,
        # Integration tests
        test_example_shaker_door,
        test_example_four_panel_door,
        test_example_wave_texture_panel,
        # Error tests
        test_parse_error_invalid_profile_side,
        test_parse_error_missing_depth,
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
