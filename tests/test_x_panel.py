import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from domains import Domain
from generators import XPanelParams
from generators.area.x_panel import x_panel_generator
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def test_x_panel_parse():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - XPanel:
            bar_width: 40mm
            depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    assert ast is not None
    print("  ✓ test_x_panel_parse PASS")


def test_x_panel_resolve():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - XPanel:
            bar_width: 40mm
            depth: 5mm
"""
    ast = parse_pml_yaml(pml)
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
    names = {item.shape_id.split("_")[-1] for item in items if item.shape_id is not None}
    assert names == {"top", "bottom", "left", "right"}

    for item in items:
        assert item.type == "Polygon"
        assert item.geometry is not None
        assert "points" in item.geometry.data
        assert len(item.geometry.data["points"]) == 3

    print("  ✓ test_x_panel_generator_directly PASS")


def test_x_panel_uniform_bar_width():
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    params = XPanelParams(bar_width_mm=40.0, depth_mm=4.0)

    items = x_panel_generator(domain, params)

    top_item = next(i for i in items if i.shape_id is not None and "top" in i.shape_id)
    bottom_item = next(i for i in items if i.shape_id is not None and "bottom" in i.shape_id)

    assert top_item.geometry is not None
    assert bottom_item.geometry is not None
    top_points = top_item.geometry.data["points"]
    bottom_points = bottom_item.geometry.data["points"]
    assert top_item.placement is not None
    assert bottom_item.placement is not None
    _top_cx, top_cy = top_item.placement.center_xy_mm
    _bottom_cx, bottom_cy = bottom_item.placement.center_xy_mm

    top_apex_y = min(p[1] + top_cy for p in top_points)
    bottom_apex_y = max(p[1] + bottom_cy for p in bottom_points)

    expected_gap = params.bar_width_mm
    actual_gap = top_apex_y - bottom_apex_y
    assert abs(actual_gap - expected_gap) < 0.01, f"Expected gap {expected_gap}, got {actual_gap}"

    print("  ✓ test_x_panel_uniform_bar_width PASS")


def test_x_panel_with_frame():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: 50mm
            children:
              - XPanel:
                  bar_width: 50mm
                  depth: 6mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    x_panel_items = [
        item for item in flat.items if item.type == "Polygon" and item.feature and item.feature.type == "pocket"
    ]
    assert len(x_panel_items) == 4

    for item in x_panel_items:
        assert item.geometry is not None
        assert item.placement is not None
        points = item.geometry.data["points"]
        cx, cy = item.placement.center_xy_mm
        for rel_x, rel_y in points:
            x = rel_x + cx
            y = rel_y + cy
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
        XPanelParams(bar_width_mm=-10, depth_mm=4.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "bar_width_mm must be positive" in str(e)

    try:
        XPanelParams(bar_width_mm=10, depth_mm=0)
        raise AssertionError("Should have raised ValueError")
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
