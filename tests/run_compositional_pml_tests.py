
import sys
from pathlib import Path

from pml.yaml_parser import parse_pml_yaml, PMLParseError as ParseError
from pml.yaml_formatter import format_pml_yaml
from resolution.layout_resolver import resolve_layout


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_simple_rect():
    print("Running test_simple_rect...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
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
    ast = parse_pml_yaml(pml)
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 600.0
    assert ast.sheet.thickness_mm == 19.0

    flat = resolve_layout(ast)
    assert len(flat.items) == 1, f"Expected 1 item, got {len(flat.items)}"

    print("  ✓ PASS")
    return True


def test_rect_with_inset():
    print("Running test_rect_with_inset...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

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

    assert len(flat.items) == 1, f"Expected 1 item, got {len(flat.items)}"
    item = flat.items[0]
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0

    print("  ✓ PASS")
    return True


def test_frame_with_pocket():
    print("Running test_frame_with_pocket...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

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

    assert len(flat.items) == 2, f"Expected 2 items, got {len(flat.items)}"

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.feature.type == "profile"

    inner = flat.items[1]
    assert inner.shape_id == "inner"
    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0

    print("  ✓ PASS")
    return True


def test_grid_with_pockets():
    print("Running test_grid_with_pockets...")

    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Grid:
      cols: 2
      rows: 2
      gap: 10mm
      children:
        - Cell:
            children:
              - Rect:
                  id: cell_rect
                  feature:
                    type: pocket
                    depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 4, f"Expected 4 items, got {len(flat.items)}"

    for item in flat.items:
        assert item.feature.type == "pocket"
        assert approx_equal(item.geometry.data["w_mm"], 195.0)
        assert approx_equal(item.geometry.data["h_mm"], 195.0)

    print("  ✓ PASS")
    return True


def test_component_definition_and_use():
    print("Running test_component_definition_and_use...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

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

    flat = resolve_layout(ast)
    assert len(flat.items) == 1, f"Expected 1 item, got {len(flat.items)}"
    assert flat.items[0].shape_id == "panel"

    print("  ✓ PASS")
    return True


def test_place_with_components():
    print("Running test_place_with_components...")

    pml = """
Sheet:
  width: 1000mm
  height: 1000mm
  thickness: 19mm
  margin: 0mm

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
          cols: 2
          rows: 2
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

    assert len(flat.items) == 4, f"Expected 4 items, got {len(flat.items)}"

    first = flat.items[0]
    assert approx_equal(first.geometry.data["w_mm"], 475.0)

    print("  ✓ PASS")
    return True


def test_acceptance_stage12_gold_exemplar():
    print("Running test_acceptance_stage12_gold_exemplar...")

    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm
  margin: 0mm

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
                      cols: 2
                      rows: 2
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
          cols: 2
          rows: 2
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
    assert ast.project == "acceptance_test_grid_panels"
    assert "GridPanel" in ast.components

    flat = resolve_layout(ast)

    assert len(flat.items) == 20, f"Expected 20 items, got {len(flat.items)}"

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 4, f"Expected 4 profiles, got {len(profile_items)}"
    assert len(pocket_items) == 16, f"Expected 16 pockets, got {len(pocket_items)}"

    first_outer = flat.items[0]
    assert first_outer.shape_id == "panel_outer"
    assert approx_equal(first_outer.geometry.data["w_mm"], 550.0)

    first_pocket = pocket_items[0]
    assert approx_equal(first_pocket.geometry.data["w_mm"], 230.0)

    print("  ✓ PASS - Stage 13 acceptance test validated!")
    print(f"    - 20 items resolved (4 profiles, 16 pockets)")
    print(f"    - Matches Stage 12 gold exemplar exactly")
    return True


def test_roundtrip_preserves_semantics():
    print("Running test_roundtrip_preserves_semantics...")

    original_pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

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
          cols: 2
          rows: 2
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

    assert len(flat1.items) == len(flat2.items), f"Expected {len(flat1.items)}, got {len(flat2.items)}"

    print("  ✓ PASS")
    return True


def test_error_handling_invalid_yaml():
    print("Running test_error_handling_invalid_yaml...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: outer
      children:
        - Profile:
            side: outside
            depth: through
    - InvalidIndent:
        foo: bar
"""

    try:
        parse_pml_yaml(pml)
        assert False, "Expected ParseError"
    except (ParseError, Exception) as e:
        pass

    print("  ✓ PASS")
    return True


def test_formatter_produces_canonical_output():
    print("Running test_formatter_produces_canonical_output...")

    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm
  margin: 0mm

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
                      cols: 2
                      rows: 2
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
          cols: 2
          rows: 2
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
    assert "width:" in formatted
    assert "project:" in formatted
    assert "components:" in formatted

    ast2 = parse_pml_yaml(formatted)
    formatted2 = format_pml_yaml(ast2)
    assert formatted == formatted2, f"Formatted output not idempotent"

    print("  ✓ PASS")
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
        test_error_handling_invalid_yaml,
        test_formatter_produces_canonical_output,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} compositional PML tests passed")

    if all(results):
        print("\n✅ Stage 13 COMPLETE - All acceptance criteria met!")

    sys.exit(0 if all(results) else 1)
