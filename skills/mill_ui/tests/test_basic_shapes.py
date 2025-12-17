"""Tests for Stage 14 basic shape primitives (Circle, RoundedRect, Line).

Acceptance tests:
- New PML parses and formats canonically
- Circle 'fit' works inside rect region
- RoundedRect fills region with corner radius preserved
- Line horizontal/vertical spans region deterministically
- Existing Stage 12/13 exemplar still passes unchanged
"""

from __future__ import annotations

import sys
from pathlib import Path

from skills.mill_ui.pml.compositional_parser import parse_compositional_pml
from skills.mill_ui.pml.compositional_formatter import format_compositional_pml
from skills.mill_ui.resolution.layout_resolver import resolve_layout


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    """Check if two floats are approximately equal."""
    return abs(a - b) < tolerance


def test_circle_with_explicit_diameter():
    """Test circle with explicit diameter."""
    print("Running test_circle_with_explicit_diameter...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

circle medallion diameter 120.00mm pocket 3.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"
    assert item.shape_id == "medallion"
    assert item.geometry.data["diameter_mm"] == 120.0
    assert item.feature.type == "pocket"

    # Circle should be centered in region
    assert item.placement.center_xy_mm == (200.0, 300.0)

    print("  ✓ PASS")
    return True


def test_circle_fit_mode():
    """Test circle 'fit' mode - inscribed in current region."""
    print("Running test_circle_fit_mode...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

circle fit pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"

    # Fit mode: diameter = min(400, 600) = 400
    assert item.geometry.data["diameter_mm"] == 400.0
    assert item.placement.center_xy_mm == (200.0, 300.0)

    print("  ✓ PASS")
    return True


def test_circle_fit_in_rect_region():
    """Test circle fit inside a rect-defined region."""
    print("Running test_circle_fit_in_rect_region...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

inset 50.00mm
    circle badge fit profile through outside
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"

    # Inset region: 400-100=300, 600-100=500
    # Fit diameter: min(300, 500) = 300
    assert item.geometry.data["diameter_mm"] == 300.0
    # Center stays same (inset doesn't move center)
    assert item.placement.center_xy_mm == (200.0, 300.0)

    print("  ✓ PASS")
    return True


def test_rounded_rect_fills_region():
    """Test rounded rectangle fills current region."""
    print("Running test_rounded_rect_fills_region...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rounded_rect badge radius 8.00mm pocket 3.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "RoundedRect"
    assert item.shape_id == "badge"

    # Fills region
    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.geometry.data["radius_mm"] == 8.0
    assert item.feature.type == "pocket"

    print("  ✓ PASS")
    return True


def test_rounded_rect_with_inset():
    """Test rounded rectangle with inset preserves corner radius."""
    print("Running test_rounded_rect_with_inset...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

inset 25.00mm
    rounded_rect panel radius 12.00mm profile through outside
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "RoundedRect"

    # Inset region: 400-50=350, 600-50=550
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0
    # Radius preserved
    assert item.geometry.data["radius_mm"] == 12.0

    print("  ✓ PASS")
    return True


def test_line_horizontal():
    """Test horizontal line spans region."""
    print("Running test_line_horizontal...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

line decoration horizontal engrave
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"
    assert item.kind == "path"  # Open path, not closed shape

    # Horizontal line across center of region
    # start: (0, 300), end: (400, 300)
    assert item.geometry.data["start_xy_mm"] == (0.0, 300.0)
    assert item.geometry.data["end_xy_mm"] == (400.0, 300.0)
    assert item.feature.type == "engrave"

    print("  ✓ PASS")
    return True


def test_line_vertical():
    """Test vertical line spans region."""
    print("Running test_line_vertical...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

line divider vertical engrave
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"

    # Vertical line down center of region
    # start: (200, 0), end: (200, 600)
    assert item.geometry.data["start_xy_mm"] == (200.0, 0.0)
    assert item.geometry.data["end_xy_mm"] == (200.0, 600.0)

    print("  ✓ PASS")
    return True


def test_line_in_inset_region():
    """Test line adapts to inset region."""
    print("Running test_line_in_inset_region...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

inset 50.00mm
    line flourish horizontal engrave
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"

    # Inset region: x: 50-350, y: 50-550
    # Horizontal line: (50, 300) to (350, 300)
    assert item.geometry.data["start_xy_mm"] == (50.0, 300.0)
    assert item.geometry.data["end_xy_mm"] == (350.0, 300.0)

    print("  ✓ PASS")
    return True


def test_round_trip_circle():
    """Test PML → AST → PML round-trip for circle."""
    print("Running test_round_trip_circle...")

    original_pml = """sheet 400.00mm 600.00mm 19.00mm

project test_circle

circle badge diameter 100.00mm pocket 5.00mm
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted)

    # Verify semantic equivalence
    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].type == flat2.items[0].type
    assert flat1.items[0].geometry.data == flat2.items[0].geometry.data

    print("  ✓ PASS")
    return True


def test_round_trip_rounded_rect():
    """Test PML → AST → PML round-trip for rounded_rect."""
    print("Running test_round_trip_rounded_rect...")

    original_pml = """sheet 400.00mm 600.00mm 19.00mm

rounded_rect panel radius 10.00mm profile through outside
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry.data["radius_mm"] == flat2.items[0].geometry.data["radius_mm"]

    print("  ✓ PASS")
    return True


def test_round_trip_line():
    """Test PML → AST → PML round-trip for line."""
    print("Running test_round_trip_line...")

    original_pml = """sheet 400.00mm 600.00mm 19.00mm

line decoration vertical engrave
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry.data["start_xy_mm"] == flat2.items[0].geometry.data["start_xy_mm"]
    assert flat1.items[0].geometry.data["end_xy_mm"] == flat2.items[0].geometry.data["end_xy_mm"]

    print("  ✓ PASS")
    return True


def test_mixed_shapes_composition():
    """Test composition with mixed shape types."""
    print("Running test_mixed_shapes_composition...")

    pml = """sheet 800.00mm 600.00mm 19.00mm

project mixed_shapes

rect outer profile through outside
    frame 40.00mm
        grid 2 2 gap 20.00mm
            cell
                circle fit pocket 5.00mm

rounded_rect badge radius 8.00mm profile through outside

line divider horizontal engrave
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Count shape types
    circles = [item for item in flat.items if item.type == "Circle"]
    rects = [item for item in flat.items if item.type == "Rect"]
    rounded_rects = [item for item in flat.items if item.type == "RoundedRect"]
    lines = [item for item in flat.items if item.type == "Line"]

    # outer rect + frame profile + 4 grid circles + rounded_rect + line
    # = 1 + 1 + 4 + 1 + 1 = 8 items
    assert len(flat.items) == 8
    assert len(circles) == 4  # Grid produces 4 circles
    assert len(rects) == 2  # outer + frame profile
    assert len(rounded_rects) == 1
    assert len(lines) == 1

    print("  ✓ PASS")
    return True


def test_acceptance_canonical_formatting():
    """Acceptance: verify canonical formatting is stable."""
    print("Running test_acceptance_canonical_formatting...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

project shape_test

circle badge diameter 120.00mm pocket 3.00mm

rounded_rect panel radius 12.00mm profile through outside

line decoration horizontal engrave
"""

    ast = parse_compositional_pml(pml)
    formatted1 = format_compositional_pml(ast)
    ast2 = parse_compositional_pml(formatted1)
    formatted2 = format_compositional_pml(ast2)

    # Canonical output should be stable
    assert formatted1 == formatted2
    assert "circle badge diameter 120.00mm pocket 3.00mm" in formatted1
    assert "rounded_rect panel radius 12.00mm profile through outside" in formatted1
    assert "line decoration horizontal engrave" in formatted1

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_circle_with_explicit_diameter,
        test_circle_fit_mode,
        test_circle_fit_in_rect_region,
        test_rounded_rect_fills_region,
        test_rounded_rect_with_inset,
        test_line_horizontal,
        test_line_vertical,
        test_line_in_inset_region,
        test_round_trip_circle,
        test_round_trip_rounded_rect,
        test_round_trip_line,
        test_mixed_shapes_composition,
        test_acceptance_canonical_formatting,
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
    print(f"\n{passed}/{total} basic shape tests passed")

    if all(results):
        print("\n✅ Stage 14 basic shapes tests COMPLETE - All tests passed!")

    sys.exit(0 if all(results) else 1)
