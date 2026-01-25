
from __future__ import annotations

import sys

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


def approx_eq(a, b, rel=1e-6):
    """Check if two values are approximately equal."""
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_simple_rect():
    print("Running test_simple_rect...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

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
    print("  PASS")
    return True


def test_rect_with_inset():
    print("Running test_rect_with_inset...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

inset 25.00mm
    rect panel pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0
    print("  PASS")
    return True


def test_frame_with_pocket():
    print("Running test_frame_with_pocket...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry.data["w_mm"] == 400.0
    assert outer.feature.type == "profile"

    inner = flat.items[1]
    assert inner.shape_id == "inner"
    assert inner.feature.type == "pocket"

    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0
    print("  PASS")
    return True


def test_grid_with_pockets():
    print("Running test_grid_with_pockets...")
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

grid 2 2 gap 10.00mm
    cell
        rect pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    assert len(flat.items) == 4

    for item in flat.items:
        assert item.feature.type == "pocket"

        assert approx_eq(item.geometry.data["w_mm"], 195.0)
        assert approx_eq(item.geometry.data["h_mm"], 195.0)
    print("  PASS")
    return True


def test_component_definition_and_use():
    print("Running test_component_definition_and_use...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

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
    print("  PASS")
    return True


def test_place_with_components():
    print("Running test_place_with_components...")
    pml = """sheet 1000.00mm 1000.00mm 19.00mm margin 0mm

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

    assert approx_eq(first.geometry.data["w_mm"], 475.0)
    print("  PASS")
    return True


def test_acceptance_stage12_gold_exemplar():
    print("Running test_acceptance_stage12_gold_exemplar...")
    pml = """sheet 1200.00mm 1200.00mm 19.00mm margin 0mm

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

    assert len(flat.items) == 20

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 4

    assert len(pocket_items) == 16


    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"


    first_outer = flat.items[0]
    assert first_outer.shape_id == "panel_outer"
    assert approx_eq(first_outer.geometry.data["w_mm"], 550.0)
    assert approx_eq(first_outer.geometry.data["h_mm"], 550.0)


    first_pocket = pocket_items[0]
    assert approx_eq(first_pocket.geometry.data["w_mm"], 230.0)
    assert approx_eq(first_pocket.geometry.data["h_mm"], 230.0)
    print("  PASS")
    return True


def test_roundtrip_preserves_semantics():
    print("Running test_roundtrip_preserves_semantics...")
    original_pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

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
    print("  PASS")
    return True


def test_error_handling_invalid_indentation():
    print("Running test_error_handling_invalid_indentation...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

rect outer profile through outside
  frame 50.00mm
    rect inner pocket 6.00mm
"""

    try:
        parse_compositional_pml(pml)
        print("  FAIL: Expected ParseError")
        return False
    except ParseError as exc_info:
        if "indentation" in str(exc_info).lower():
            if exc_info.line > 0:
                pass
            else:
                print(f"  FAIL: Line number should be > 0")
                return False
        else:
            print(f"  FAIL: Error should mention 'indentation': {exc_info}")
            return False
    print("  PASS")
    return True


def test_error_handling_unknown_keyword():
    print("Running test_error_handling_unknown_keyword...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

unknown_node 123
"""
    try:
        parse_compositional_pml(pml)
        print("  FAIL: Expected ParseError")
        return False
    except ParseError as exc_info:
        if exc_info.line == 3:
            pass
        else:
            print(f"  FAIL: Expected line 3, got {exc_info.line}")
            return False
    print("  PASS")
    return True


def test_error_handling_missing_unit():
    print("Running test_error_handling_missing_unit...")
    pml = """sheet 400 600 19

rect outer profile through outside
"""
    try:
        parse_compositional_pml(pml)
        print("  FAIL: Expected ParseError")
        return False
    except ParseError as exc_info:
        if "expected" in str(exc_info).lower():
            pass
        else:
            print(f"  FAIL: Error should mention 'expected': {exc_info}")
            return False
    print("  PASS")
    return True


def test_formatter_produces_canonical_output():
    print("Running test_formatter_produces_canonical_output...")
    pml = """sheet 1200.00mm 1200.00mm 19.00mm margin 0mm

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
    print("  PASS")
    return True


def test_grid_without_explicit_cell():
    print("Running test_grid_without_explicit_cell...")
    pml = """sheet 400.00mm 400.00mm 19.00mm margin 0mm

grid 2 2 gap 0.00mm
    rect pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    assert len(flat.items) == 4
    print("  PASS")
    return True


def test_project_optional():
    print("Running test_project_optional...")
    pml = """sheet 400.00mm 600.00mm 19.00mm margin 0mm

rect outer profile through outside
"""
    ast = parse_compositional_pml(pml)
    assert ast.project is None

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_simple_rect,
        test_rect_with_inset,
        test_frame_with_pocket,
        test_grid_with_pockets,
        test_component_definition_and_use,
        test_place_with_components,
        test_acceptance_stage12_gold_exemplar,
        test_roundtrip_preserves_semantics,
        test_error_handling_invalid_indentation,
        test_error_handling_unknown_keyword,
        test_error_handling_missing_unit,
        test_formatter_produces_canonical_output,
        test_grid_without_explicit_cell,
        test_project_optional,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
