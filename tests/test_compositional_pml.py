
from __future__ import annotations

import pytest

from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import (
    Panel,
    Rect,
    Frame,
    Grid,
    Cell,
    UseComponent,
)
from layout_ast.layout import Feature


def test_simple_rect():
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
"""
    ast = parse_compositional_pml(pml)
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 600.0
    assert ast.sheet.thickness_mm == 19.0


    assert isinstance(ast.root, Panel)
    assert len(ast.root.children) == 1
    rect = ast.root.children[0]
    assert isinstance(rect, Rect)
    assert rect.id == "outer"
    assert rect.feature.type == "profile"


def test_rect_with_inset():
    pml = """sheet 400.00mm 600.00mm 19.00mm

inset 25.00mm
    rect panel pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0


def test_frame_with_pocket():
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    assert len(flat.items) == 3

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry.data["w_mm"] == 400.0

    frame_profile = flat.items[1]
    assert frame_profile.feature.type == "profile"

    inner = flat.items[2]
    assert inner.shape_id == "inner"
    assert inner.feature.type == "pocket"

    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0


def test_grid_with_pockets():
    pml = """sheet 400.00mm 400.00mm 19.00mm

grid 2 2 gap 10.00mm
    cell
        rect pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    assert len(flat.items) == 4

    for item in flat.items:
        assert item.feature.type == "pocket"

        assert item.geometry.data["w_mm"] == pytest.approx(195.0)
        assert item.geometry.data["h_mm"] == pytest.approx(195.0)


def test_component_definition_and_use():
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


    assert len(flat.items) == 4


    first = flat.items[0]

    assert first.geometry.data["w_mm"] == pytest.approx(475.0)


def test_acceptance_stage12_gold_exemplar():
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


    ast = parse_compositional_pml(pml)


    assert ast.sheet.width_mm == 1200
    assert ast.sheet.height_mm == 1200
    assert ast.sheet.thickness_mm == 19
    assert ast.project == "acceptance_test_grid_panels"
    assert "GridPanel" in ast.components


    flat = resolve_layout(ast)


    assert len(flat.items) == 24


    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]


    assert len(profile_items) == 8


    assert len(pocket_items) == 16


    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"


    first_outer = flat.items[0]
    assert first_outer.shape_id == "panel_outer"
    assert first_outer.geometry.data["w_mm"] == pytest.approx(550.0)
    assert first_outer.geometry.data["h_mm"] == pytest.approx(550.0)


    first_pocket = pocket_items[0]
    assert first_pocket.geometry.data["w_mm"] == pytest.approx(230.0)
    assert first_pocket.geometry.data["h_mm"] == pytest.approx(230.0)


def test_roundtrip_preserves_semantics():
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


    ast1 = parse_compositional_pml(original_pml)


    canonical_pml = format_compositional_pml(ast1)


    ast2 = parse_compositional_pml(canonical_pml)


    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)


    types1 = [item.feature.type if item.feature else None for item in flat1.items]
    types2 = [item.feature.type if item.feature else None for item in flat2.items]
    assert types1 == types2


def test_error_handling_invalid_indentation():
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
  frame 50.00mm
    rect inner pocket 6.00mm
"""

    with pytest.raises(ParseError) as exc_info:
        parse_compositional_pml(pml)

    assert "indentation" in str(exc_info.value).lower()
    assert exc_info.value.line > 0


def test_error_handling_unknown_keyword():
    pml = """sheet 400.00mm 600.00mm 19.00mm

unknown_node 123
"""
    with pytest.raises(ParseError) as exc_info:
        parse_compositional_pml(pml)

    assert exc_info.value.line == 3


def test_error_handling_missing_unit():
    pml = """sheet 400 600 19

rect outer profile through outside
"""
    with pytest.raises(ParseError) as exc_info:
        parse_compositional_pml(pml)

    assert "expected" in str(exc_info.value).lower()


def test_formatter_produces_canonical_output():
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


    assert "sheet 1200.00mm 1200.00mm 19.00mm" in formatted
    assert "project test_canonical" in formatted
    assert "component Panel" in formatted
    assert "place grid 2 2 gap 100.00mm" in formatted


    ast2 = parse_compositional_pml(formatted)
    formatted2 = format_compositional_pml(ast2)
    assert formatted == formatted2


def test_grid_without_explicit_cell():
    pml = """sheet 400.00mm 400.00mm 19.00mm

grid 2 2 gap 0.00mm
    rect pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    assert len(flat.items) == 4


def test_project_optional():
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
"""
    ast = parse_compositional_pml(pml)
    assert ast.project is None

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
