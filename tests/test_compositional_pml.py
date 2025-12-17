"""Tests for compositional PML parser and formatter.

Stage 13 acceptance tests:
- Parse Stage 12 gold exemplar PML
- Resolve to 24 items (8 profiles, 16 pockets)
- Round-trip: PML → AST → PML produces canonical formatting
- Error handling with line/column information
"""

from __future__ import annotations

import pytest

from skills.mill_ui.pml.compositional_parser import parse_compositional_pml, ParseError
from skills.mill_ui.pml.compositional_formatter import format_compositional_pml
from skills.mill_ui.resolution.layout_resolver import resolve_layout
from skills.mill_ui.layout_ast.compositional import (
    Panel,
    Rect,
    Frame,
    Grid,
    Cell,
    UseComponent,
)
from skills.mill_ui.layout_ast.layout import Feature


def test_simple_rect():
    """Test parsing simple rect."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
"""
    ast = parse_compositional_pml(pml)
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 600.0
    assert ast.sheet.thickness_mm == 19.0

    # Root should be Panel with one Rect child
    assert isinstance(ast.root, Panel)
    assert len(ast.root.children) == 1
    rect = ast.root.children[0]
    assert isinstance(rect, Rect)
    assert rect.id == "outer"
    assert rect.feature.type == "profile"


def test_rect_with_inset():
    """Test parsing rect with inset."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

inset 25.00mm
    rect panel pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    # Inset 25mm on all sides: 400-50=350, 600-50=550
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0


def test_frame_with_pocket():
    """Test parsing frame with inner pocket."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Should have: outer rect + frame profile + inner pocket
    assert len(flat.items) == 3

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry.data["w_mm"] == 400.0

    frame_profile = flat.items[1]
    assert frame_profile.feature.type == "profile"

    inner = flat.items[2]
    assert inner.shape_id == "inner"
    assert inner.feature.type == "pocket"
    # Frame insets by 50mm on each side: 400-100=300, 600-100=500
    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0


def test_grid_with_pockets():
    """Test parsing grid with pockets."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

grid 2 2 gap 10.00mm
    cell
        rect pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # 2×2 grid = 4 cells, each with 1 pocket rect
    assert len(flat.items) == 4

    for item in flat.items:
        assert item.feature.type == "pocket"
        # Cell size: (400 - 10) / 2 = 195mm
        assert item.geometry.data["w_mm"] == pytest.approx(195.0)
        assert item.geometry.data["h_mm"] == pytest.approx(195.0)


def test_component_definition_and_use():
    """Test component definition with use."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

component SimplePanel
    rect panel pocket 6.00mm

use SimplePanel
"""
    ast = parse_compositional_pml(pml)

    assert "SimplePanel" in ast.components
    comp_def = ast.components["SimplePanel"]
    assert comp_def.name == "SimplePanel"
    assert isinstance(comp_def.body, Rect)

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
    assert flat.items[0].shape_id == "panel"


def test_place_with_components():
    """Test place with grid layout."""
    pml = """sheet 1000.00mm 1000.00mm 19.00mm

component Panel
    rect outer profile through outside

place grid 2 2 gap 50.00mm
    use Panel
    use Panel
    use Panel
    use Panel
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # 4 instances × 1 rect each = 4 items
    assert len(flat.items) == 4

    # First instance should be in top-left cell
    first = flat.items[0]
    # Cell size: (1000 - 50) / 2 = 475mm
    assert first.geometry.data["w_mm"] == pytest.approx(475.0)


def test_acceptance_stage12_gold_exemplar():
    """Stage 13 acceptance test: Parse Stage 12 gold exemplar.

    This test validates that the compositional PML parser produces the exact
    same resolved output as the Stage 12 Python AST construction.

    Expected output:
    - 24 total items
    - 8 profiles (2 per instance: outer rect + frame profile)
    - 16 pockets (4 per instance: 2×2 grid)
    """
    pml = """sheet 1200.00mm 1200.00mm 19.00mm

project acceptance_test_grid_panels

component GridPanel
    rect panel_outer profile through outside
        frame 40.00mm
            grid 2 2 gap 10.00mm
                cell
                    rect pocket 5.00mm

place grid 2 2 gap 100.00mm
    use GridPanel
    use GridPanel
    use GridPanel
    use GridPanel
"""

    # Parse PML → CompositionalAST
    ast = parse_compositional_pml(pml)

    # Validate AST structure
    assert ast.sheet.width_mm == 1200
    assert ast.sheet.height_mm == 1200
    assert ast.sheet.thickness_mm == 19
    assert ast.project == "acceptance_test_grid_panels"
    assert "GridPanel" in ast.components

    # Resolve to flat LayoutAST
    flat = resolve_layout(ast)

    # Acceptance criteria: 24 items total
    assert len(flat.items) == 24

    # Count feature types
    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    # 4 instances × 2 profiles = 8 profiles
    assert len(profile_items) == 8

    # 4 instances × 4 pockets = 16 pockets
    assert len(pocket_items) == 16

    # Validate sheet metadata
    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"

    # Validate first instance geometry (top-left cell)
    # Cell size: (1200 - 100) / 2 = 550mm
    first_outer = flat.items[0]
    assert first_outer.shape_id == "panel_outer"
    assert first_outer.geometry.data["w_mm"] == pytest.approx(550.0)
    assert first_outer.geometry.data["h_mm"] == pytest.approx(550.0)

    # Validate first pocket (top-left cell, inner grid top-left)
    # Inner region: 550 - 80 (frame) = 470mm
    # Pocket size: (470 - 10) / 2 = 230mm
    first_pocket = pocket_items[0]
    assert first_pocket.geometry.data["w_mm"] == pytest.approx(230.0)
    assert first_pocket.geometry.data["h_mm"] == pytest.approx(230.0)


def test_roundtrip_preserves_semantics():
    """Test that PML → AST → PML → AST preserves semantics."""
    original_pml = """sheet 400.00mm 600.00mm 19.00mm

project test_roundtrip

component TestPanel
    rect outer profile through outside
        frame 50.00mm
            rect inner pocket 6.00mm

place grid 2 2 gap 20.00mm
    use TestPanel
    use TestPanel
    use TestPanel
    use TestPanel
"""

    # First parse
    ast1 = parse_compositional_pml(original_pml)

    # Format to canonical PML
    canonical_pml = format_compositional_pml(ast1)

    # Second parse
    ast2 = parse_compositional_pml(canonical_pml)

    # Resolve both and compare item counts
    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)

    # Verify item types match
    types1 = [item.feature.type if item.feature else None for item in flat1.items]
    types2 = [item.feature.type if item.feature else None for item in flat2.items]
    assert types1 == types2


def test_error_handling_invalid_indentation():
    """Test error handling for invalid indentation."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
  frame 50.00mm
    rect inner pocket 6.00mm
"""
    # 2-space indent is invalid (expecting 4-space)
    with pytest.raises(ParseError) as exc_info:
        parse_compositional_pml(pml)

    assert "indentation" in str(exc_info.value).lower()
    assert exc_info.value.line > 0


def test_error_handling_unknown_keyword():
    """Test error handling for unknown keyword."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

unknown_node 123
"""
    with pytest.raises(ParseError) as exc_info:
        parse_compositional_pml(pml)

    assert exc_info.value.line == 3


def test_error_handling_missing_unit():
    """Test error handling for missing unit."""
    pml = """sheet 400 600 19

rect outer profile through outside
"""
    with pytest.raises(ParseError) as exc_info:
        parse_compositional_pml(pml)

    assert "expected" in str(exc_info.value).lower()


def test_formatter_produces_canonical_output():
    """Test that formatter produces deterministic canonical output."""
    pml = """sheet 1200.00mm 1200.00mm 19.00mm

project test_canonical

component Panel
    rect outer profile through outside
        frame 40.00mm
            grid 2 2 gap 10.00mm
                cell
                    rect pocket 5.00mm

place grid 2 2 gap 100.00mm
    use Panel
    use Panel
    use Panel
    use Panel
"""

    ast = parse_compositional_pml(pml)
    formatted = format_compositional_pml(ast)

    # Verify canonical properties
    assert "sheet 1200.00mm 1200.00mm 19.00mm" in formatted
    assert "project test_canonical" in formatted
    assert "component Panel" in formatted
    assert "place grid 2 2 gap 100.00mm" in formatted

    # Verify formatting is stable (re-format produces same output)
    ast2 = parse_compositional_pml(formatted)
    formatted2 = format_compositional_pml(ast2)
    assert formatted == formatted2


def test_grid_without_explicit_cell():
    """Test grid without explicit Cell node (children as cell content)."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

grid 2 2 gap 0.00mm
    rect pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # 2×2 grid = 4 cells, each with rect
    assert len(flat.items) == 4


def test_project_optional():
    """Test that project declaration is optional."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
"""
    ast = parse_compositional_pml(pml)
    assert ast.project is None

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
