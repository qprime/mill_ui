
from __future__ import annotations

import sys
from pathlib import Path

from pml.compositional_parser import parse_compositional_pml
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_circle_with_explicit_diameter():
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


    assert item.placement.center_xy_mm == (200.0, 300.0)

    print("  ✓ PASS")
    return True


def test_circle_fit_mode():
    print("Running test_circle_fit_mode...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

circle fit pocket 5.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Circle"


    assert item.geometry.data["diameter_mm"] == 400.0
    assert item.placement.center_xy_mm == (200.0, 300.0)

    print("  ✓ PASS")
    return True


def test_circle_fit_in_rect_region():
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


    assert item.geometry.data["diameter_mm"] == 300.0

    assert item.placement.center_xy_mm == (200.0, 300.0)

    print("  ✓ PASS")
    return True


def test_rounded_rect_fills_region():
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


    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.geometry.data["radius_mm"] == 8.0
    assert item.feature.type == "pocket"

    print("  ✓ PASS")
    return True


def test_rounded_rect_with_inset():
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


    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0

    assert item.geometry.data["radius_mm"] == 12.0

    print("  ✓ PASS")
    return True


def test_line_horizontal():
    print("Running test_line_horizontal...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

line decoration horizontal engrave 1.50mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"
    assert item.kind == "path"


    assert item.geometry.data["start_xy_mm"] == (0.0, 300.0)
    assert item.geometry.data["end_xy_mm"] == (400.0, 300.0)
    assert item.feature.type == "engrave"
    assert item.feature.depth_mm == 1.5

    print("  ✓ PASS")
    return True


def test_line_vertical():
    print("Running test_line_vertical...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

line divider vertical engrave 1.50mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"


    assert item.geometry.data["start_xy_mm"] == (200.0, 0.0)
    assert item.geometry.data["end_xy_mm"] == (200.0, 600.0)
    assert item.feature.depth_mm == 1.5

    print("  ✓ PASS")
    return True


def test_line_in_inset_region():
    print("Running test_line_in_inset_region...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

inset 50.00mm
    line flourish horizontal engrave 1.50mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Line"


    assert item.geometry.data["start_xy_mm"] == (50.0, 300.0)
    assert item.geometry.data["end_xy_mm"] == (350.0, 300.0)
    assert item.feature.depth_mm == 1.5

    print("  ✓ PASS")
    return True


def test_round_trip_circle():
    print("Running test_round_trip_circle...")

    original_pml = """sheet 400.00mm 600.00mm 19.00mm

project test_circle

circle badge diameter 100.00mm pocket 5.00mm
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted)


    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].type == flat2.items[0].type
    assert flat1.items[0].geometry.data == flat2.items[0].geometry.data

    print("  ✓ PASS")
    return True


def test_round_trip_rounded_rect():
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
    print("Running test_round_trip_line...")

    original_pml = """sheet 400.00mm 600.00mm 19.00mm

line decoration vertical engrave 1.50mm
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry.data["start_xy_mm"] == flat2.items[0].geometry.data["start_xy_mm"]
    assert flat1.items[0].geometry.data["end_xy_mm"] == flat2.items[0].geometry.data["end_xy_mm"]
    assert flat1.items[0].feature.depth_mm == flat2.items[0].feature.depth_mm

    print("  ✓ PASS")
    return True


def test_mixed_shapes_composition():
    print("Running test_mixed_shapes_composition...")

    pml = """sheet 800.00mm 600.00mm 19.00mm

project mixed_shapes

rect outer profile through outside
    frame 40.00mm
        grid 2 2 gap 20.00mm
            cell
                circle fit pocket 5.00mm

rounded_rect badge radius 8.00mm profile through outside

line divider horizontal engrave 1.50mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    circles = [item for item in flat.items if item.type == "Circle"]
    rects = [item for item in flat.items if item.type == "Rect"]
    rounded_rects = [item for item in flat.items if item.type == "RoundedRect"]
    lines = [item for item in flat.items if item.type == "Line"]


    assert len(flat.items) == 7
    assert len(circles) == 4
    assert len(rects) == 1
    assert len(rounded_rects) == 1
    assert len(lines) == 1
    assert lines[0].feature.depth_mm == 1.5

    print("  ✓ PASS")
    return True


def test_rounded_rect_selective_corners():
    print("Running test_rounded_rect_selective_corners...")

    pml = """sheet 686.00mm 864.00mm 19.00mm

rounded_rect table_half radius 12.70mm corners tl bl profile through outside
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "RoundedRect"
    assert item.shape_id == "table_half"

    assert item.geometry.data["radius_tl_mm"] == 12.7
    assert item.geometry.data["radius_tr_mm"] == 0.0
    assert item.geometry.data["radius_bl_mm"] == 12.7
    assert item.geometry.data["radius_br_mm"] == 0.0

    print("  ✓ PASS")
    return True


def test_rounded_rect_all_corners_explicit():
    print("Running test_rounded_rect_all_corners_explicit...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rounded_rect panel radius 10.00mm corners tl tr bl br pocket 3.00mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.geometry.data["radius_tl_mm"] == 10.0
    assert item.geometry.data["radius_tr_mm"] == 10.0
    assert item.geometry.data["radius_bl_mm"] == 10.0
    assert item.geometry.data["radius_br_mm"] == 10.0
    assert item.geometry.data["radius_mm"] == 10.0

    print("  ✓ PASS")
    return True


def test_rounded_rect_single_corner():
    print("Running test_rounded_rect_single_corner...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rounded_rect corner_piece radius 25.00mm corners tr profile through outside
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.geometry.data["radius_tl_mm"] == 0.0
    assert item.geometry.data["radius_tr_mm"] == 25.0
    assert item.geometry.data["radius_bl_mm"] == 0.0
    assert item.geometry.data["radius_br_mm"] == 0.0

    print("  ✓ PASS")
    return True


def test_rounded_rect_corners_round_trip():
    print("Running test_rounded_rect_corners_round_trip...")

    original_pml = """sheet 686.00mm 864.00mm 19.00mm

rounded_rect table_half radius 12.70mm corners tl bl profile through outside
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)
    assert flat1.items[0].geometry.data["radius_tl_mm"] == flat2.items[0].geometry.data["radius_tl_mm"]
    assert flat1.items[0].geometry.data["radius_tr_mm"] == flat2.items[0].geometry.data["radius_tr_mm"]
    assert flat1.items[0].geometry.data["radius_bl_mm"] == flat2.items[0].geometry.data["radius_bl_mm"]
    assert flat1.items[0].geometry.data["radius_br_mm"] == flat2.items[0].geometry.data["radius_br_mm"]

    assert "corners tl bl" in formatted

    print("  ✓ PASS")
    return True


def test_acceptance_canonical_formatting():
    print("Running test_acceptance_canonical_formatting...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

project shape_test

circle badge diameter 120.00mm pocket 3.00mm

rounded_rect panel radius 12.00mm profile through outside

line decoration horizontal engrave 1.50mm
"""

    ast = parse_compositional_pml(pml)
    formatted1 = format_compositional_pml(ast)
    ast2 = parse_compositional_pml(formatted1)
    formatted2 = format_compositional_pml(ast2)


    assert formatted1 == formatted2
    assert "circle badge diameter 120.00mm pocket 3.00mm" in formatted1
    assert "rounded_rect panel radius 12.00mm profile through outside" in formatted1
    assert "line decoration horizontal engrave 1.50mm" in formatted1

    print("  ✓ PASS")
    return True


def test_rounded_rect_with_profile_child_inherits_geometry():
    """Test that profile generator inside rounded_rect produces RoundedRect profile."""
    print("Running test_rounded_rect_with_profile_child_inherits_geometry...")

    pml = """sheet 584.00mm 584.00mm 19.00mm

rounded_rect panel radius 25.40mm corners bl br
    profile outside through
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.type == "RoundedRect"
    assert shape_item.shape_id == "panel"
    assert shape_item.geometry.data["radius_bl_mm"] == 25.4
    assert shape_item.geometry.data["radius_br_mm"] == 25.4
    assert shape_item.geometry.data["radius_tl_mm"] == 0.0
    assert shape_item.geometry.data["radius_tr_mm"] == 0.0

    profile_item = flat.items[1]
    assert profile_item.type == "RoundedRect"
    assert profile_item.feature.type == "profile"
    assert profile_item.feature.side == "outside"
    assert profile_item.geometry.data["radius_bl_mm"] == 25.4
    assert profile_item.geometry.data["radius_br_mm"] == 25.4
    assert profile_item.geometry.data["radius_tl_mm"] == 0.0
    assert profile_item.geometry.data["radius_tr_mm"] == 0.0

    print("  ✓ PASS")
    return True


def test_rect_with_profile_child_stays_rect():
    """Test backward compatibility: profile inside rect stays rect."""
    print("Running test_rect_with_profile_child_stays_rect...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rect panel
    profile outside through
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.type == "Rect"

    profile_item = flat.items[1]
    assert profile_item.type == "Rect"
    assert profile_item.feature.type == "profile"
    assert "radius_mm" not in profile_item.geometry.data
    assert "radius_bl_mm" not in profile_item.geometry.data

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_circle_with_explicit_diameter,
        test_circle_fit_mode,
        test_circle_fit_in_rect_region,
        test_rounded_rect_fills_region,
        test_rounded_rect_with_inset,
        test_rounded_rect_selective_corners,
        test_rounded_rect_all_corners_explicit,
        test_rounded_rect_single_corner,
        test_rounded_rect_corners_round_trip,
        test_line_horizontal,
        test_line_vertical,
        test_line_in_inset_region,
        test_round_trip_circle,
        test_round_trip_rounded_rect,
        test_round_trip_line,
        test_mixed_shapes_composition,
        test_acceptance_canonical_formatting,
        test_rounded_rect_with_profile_child_inherits_geometry,
        test_rect_with_profile_child_stays_rect,
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
