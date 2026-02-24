from __future__ import annotations

import sys

from layout_ast.compositional import (
    Panel,
    Rect,
)
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import PMLParseError, parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def approx_eq(a, b, rel=1e-6):
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_simple_rect():
    print("Running test_simple_rect...")
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      children:
        - Profile:
            side: outside
            depth: through
"""
    ast = parse_pml_yaml(pml)
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 600.0
    assert ast.sheet.thickness_mm == 19.0

    assert isinstance(ast.root, Panel)
    assert len(ast.root.children) == 1
    rect = ast.root.children[0]
    assert isinstance(rect, Rect)
    assert rect.id == "outer"
    print("  PASS")
    return True


def test_rect_with_inset():
    print("Running test_rect_with_inset...")
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Inset:
      distance: 25mm
      children:
        - Rect:
            id: panel
            feature:
              type: pocket
              depth: 6mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0
    print("  PASS")
    return True


def test_frame_with_pocket():
    print("Running test_frame_with_pocket...")
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 50mm
            children:
              - Rect:
                  id: inner
                  feature:
                    type: pocket
                    depth: 6mm
"""
    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Grid:
      rows: 2
      cols: 2
      gap: 10mm
      children:
        - Cell:
            children:
              - Rect:
                  feature:
                    type: pocket
                    depth: 5mm
"""
    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

components:
  SimplePanel:
    body:
      - Rect:
          id: panel
          feature:
            type: pocket
            depth: 6mm

children:
  - UseComponent:
      name: SimplePanel
"""
    ast = parse_pml_yaml(pml)

    assert "SimplePanel" in ast.components
    comp_def = ast.components["SimplePanel"]
    assert comp_def.name == "SimplePanel"

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
    assert flat.items[0].shape_id == "panel"
    print("  PASS")
    return True


def test_place_with_components():
    print("Running test_place_with_components...")
    pml = """
Sheet:
  width: 1000mm
  height: 1000mm
  thickness: 19mm

components:
  Panel:
    body:
      - Rect:
          id: outer
          feature:
            type: profile
            side: outside
            depth: through

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 50mm
      children:
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 4

    first = flat.items[0]

    assert approx_eq(first.geometry.data["w_mm"], 475.0)
    print("  PASS")
    return True


def test_acceptance_stage12_gold_exemplar():
    print("Running test_acceptance_stage12_gold_exemplar...")
    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm

project: acceptance_test_grid_panels

components:
  GridPanel:
    body:
      - Rect:
          id: panel_outer
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
                      gap: 10mm
                      children:
                        - Cell:
                            children:
                              - Rect:
                                  id: cell_rect
                                  feature:
                                    type: pocket
                                    depth: 5mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 100mm
      children:
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
"""

    ast = parse_pml_yaml(pml)

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
    original_pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

project: test_roundtrip

components:
  TestPanel:
    body:
      - Rect:
          id: outer
          feature:
            type: profile
            side: outside
            depth: through
          children:
            - Frame:
                width: 50mm
                children:
                  - Rect:
                      id: inner
                      feature:
                        type: pocket
                        depth: 6mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 20mm
      children:
        - UseComponent:
            name: TestPanel
        - UseComponent:
            name: TestPanel
        - UseComponent:
            name: TestPanel
        - UseComponent:
            name: TestPanel
"""

    ast1 = parse_pml_yaml(original_pml)

    canonical_pml = format_pml_yaml(ast1)

    ast2 = parse_pml_yaml(canonical_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)

    types1 = [item.feature.type if item.feature else None for item in flat1.items]
    types2 = [item.feature.type if item.feature else None for item in flat2.items]
    assert types1 == types2
    print("  PASS")
    return True


def test_error_handling_unknown_keyword():
    print("Running test_error_handling_unknown_keyword...")
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - UnknownNode:
      value: 123
"""
    try:
        parse_pml_yaml(pml)
        print("  FAIL: Expected PMLParseError")
        return False
    except PMLParseError:
        pass
    print("  PASS")
    return True


def test_formatter_produces_canonical_output():
    print("Running test_formatter_produces_canonical_output...")
    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm

project: test_canonical

components:
  Panel:
    body:
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
                      gap: 10mm
                      children:
                        - Cell:
                            children:
                              - Rect:
                                  id: cell_rect
                                  feature:
                                    type: pocket
                                    depth: 5mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 100mm
      children:
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
"""

    ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(ast)

    assert "Sheet:" in formatted
    assert "project:" in formatted
    assert "components:" in formatted

    ast2 = parse_pml_yaml(formatted)
    formatted2 = format_pml_yaml(ast2)
    assert formatted == formatted2
    print("  PASS")
    return True


def test_grid_without_explicit_cell():
    print("Running test_grid_without_explicit_cell...")
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Grid:
      rows: 2
      cols: 2
      gap: 0mm
      children:
        - Cell:
            children:
              - Rect:
                  feature:
                    type: pocket
                    depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 4
    print("  PASS")
    return True


def test_project_optional():
    print("Running test_project_optional...")
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
"""
    ast = parse_pml_yaml(pml)
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
        test_error_handling_unknown_keyword,
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
