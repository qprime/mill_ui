"""Tests for x_panel generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from generators.base import XPanelParams
from generators.area.x_panel import x_panel_generator
from domains import Domain


def test_x_panel_parse():
    pml = """sheet 300mm 300mm 19mm

rect panel
    x_panel bar_width 40mm depth 5mm
"""
    ast = parse_compositional_pml(pml)
    assert ast is not None
    print("  ✓ test_x_panel_parse PASS")


def test_x_panel_resolve():
    pml = """sheet 300mm 300mm 19mm

rect panel
    x_panel bar_width 40mm depth 5mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polygon_items = [item for item in flat.items if item.type == "Polygon"]
    assert len(polygon_items) == 4

    for item in polygon_items:
        assert item.feature is not None
        assert item.feature.type == "pocket"
        assert item.feature.depth_mm == 5.0

    print("  ✓ test_x_panel_resolve PASS")


def test_x_panel_generator_directly():
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    params = XPanelParams(bar_width_mm=30.0, depth_mm=4.0)

    items = x_panel_generator(domain, params)

    assert len(items) == 4
    names = {item.shape_id.split("_")[-1] for item in items}
    assert names == {"top", "bottom", "left", "right"}

    for item in items:
        assert item.type == "Polygon"
        assert "points" in item.geometry.data
        assert len(item.geometry.data["points"]) == 3

    print("  ✓ test_x_panel_generator_directly PASS")


def test_x_panel_uniform_bar_width():
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    params = XPanelParams(bar_width_mm=40.0, depth_mm=4.0)

    items = x_panel_generator(domain, params)

    top_item = next(i for i in items if "top" in i.shape_id)
    bottom_item = next(i for i in items if "bottom" in i.shape_id)
    left_item = next(i for i in items if "left" in i.shape_id)
    right_item = next(i for i in items if "right" in i.shape_id)

    top_points = top_item.geometry.data["points"]
    bottom_points = bottom_item.geometry.data["points"]

    top_apex_y = min(p[1] for p in top_points)
    bottom_apex_y = max(p[1] for p in bottom_points)

    expected_gap = params.bar_width_mm
    actual_gap = top_apex_y - bottom_apex_y
    assert abs(actual_gap - expected_gap) < 0.01, f"Expected gap {expected_gap}, got {actual_gap}"

    print("  ✓ test_x_panel_uniform_bar_width PASS")


def test_x_panel_with_frame():
    pml = """sheet 400mm 600mm 19mm

rect door
    profile outside through
    frame 50mm
        x_panel bar_width 50mm depth 6mm
"""
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    polygon_items = [item for item in flat.items if item.type == "Polygon"]
    assert len(polygon_items) == 4

    for item in polygon_items:
        points = item.geometry.data["points"]
        for x, y in points:
            assert 50 <= x <= 350, f"x={x} outside frame bounds"
            assert 50 <= y <= 550, f"y={y} outside frame bounds"

    print("  ✓ test_x_panel_with_frame PASS")


def test_x_panel_too_small_domain():
    domain = Domain.from_rectangle(50, 50, center=(25, 25))
    params = XPanelParams(bar_width_mm=30.0, depth_mm=4.0)

    items = x_panel_generator(domain, params, allow_empty=True)
    assert items == []

    print("  ✓ test_x_panel_too_small_domain PASS")


def test_x_panel_params_validation():
    try:
        params = XPanelParams(bar_width_mm=-10, depth_mm=4.0)
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "bar_width_mm must be positive" in str(e)

    try:
        params = XPanelParams(bar_width_mm=10, depth_mm=0)
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "depth_mm must be positive" in str(e)

    print("  ✓ test_x_panel_params_validation PASS")


if __name__ == "__main__":
    test_x_panel_parse()
    test_x_panel_resolve()
    test_x_panel_generator_directly()
    test_x_panel_uniform_bar_width()
    test_x_panel_with_frame()
    test_x_panel_too_small_domain()
    test_x_panel_params_validation()
    print("\nAll tests passed!")
