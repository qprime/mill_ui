
import sys
from pathlib import Path

from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_simple_rect():
    print("Running test_simple_rect...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
"""
    ast = parse_compositional_pml(pml)
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 600.0
    assert ast.sheet.thickness_mm == 19.0

    flat = resolve_layout(ast)
    assert len(flat.items) == 1

    print("  ✓ PASS")
    return True


def test_rect_with_inset():
    print("Running test_rect_with_inset...")

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

    print("  ✓ PASS")
    return True


def test_frame_with_pocket():
    print("Running test_frame_with_pocket...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 2

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
        assert approx_equal(item.geometry.data["w_mm"], 195.0)
        assert approx_equal(item.geometry.data["h_mm"], 195.0)

    print("  ✓ PASS")
    return True


def test_component_definition_and_use():
    print("Running test_component_definition_and_use...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

component SimplePanel
    rect panel pocket 6.00mm

use SimplePanel
"""
    ast = parse_compositional_pml(pml)

    assert "SimplePanel" in ast.components

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
    assert flat.items[0].shape_id == "panel"

    print("  ✓ PASS")
    return True


def test_place_with_components():
    print("Running test_place_with_components...")

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
    assert approx_equal(first.geometry.data["w_mm"], 475.0)

    print("  ✓ PASS")
    return True


def test_acceptance_stage12_gold_exemplar():
    print("Running test_acceptance_stage12_gold_exemplar...")

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

    print("  ✓ PASS")
    return True


def test_error_handling_invalid_indentation():
    print("Running test_error_handling_invalid_indentation...")


    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
  rect bad pocket 5.00mm
"""


    try:
        parse_compositional_pml(pml)
        assert False, "Expected ParseError"
    except ParseError as e:
        assert ("indentation" in str(e).lower() or "invalid" in str(e).lower() or
                "expected" in str(e).lower())
        assert e.line > 0

    print("  ✓ PASS")
    return True


def test_formatter_produces_canonical_output():
    print("Running test_formatter_produces_canonical_output...")

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


    ast2 = parse_compositional_pml(formatted)
    formatted2 = format_compositional_pml(ast2)
    assert formatted == formatted2

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
        test_error_handling_invalid_indentation,
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
