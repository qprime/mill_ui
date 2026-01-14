"""Tests for template expansion (Phase 4).

Run from repository root: PYTHONPATH=. python3 -m tests.test_template_expander
"""

import sys
from nesting.types import PartSpec, NestedPart
from nesting.template_expander import (
    TEMPLATE_REGISTRY,
    get_part_bounds,
    expand_part_to_items,
    placement_to_items,
)


def test_shaker_template_registered():
    """Shaker template should be registered."""
    print("Running test_shaker_template_registered...")
    assert "Shaker" in TEMPLATE_REGISTRY
    print("  PASSED")


def test_get_part_bounds_simple():
    """Get bounds for simple part."""
    print("Running test_get_part_bounds_simple...")
    part = PartSpec(name="panel", width_mm=400, height_mm=600)
    w, h = get_part_bounds(part)
    assert w == 400
    assert h == 600
    print("  PASSED")


def test_expand_simple_rect():
    """Expand part without template to rect."""
    print("Running test_expand_simple_rect...")
    part = PartSpec(name="panel", width_mm=200, height_mm=300)
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 150),
        rotated=False,
        sheet_thickness_mm=19,
    )

    assert len(items) == 1
    item = items[0]
    assert item.type == "Rect"
    assert item.geometry.data["w_mm"] == 200
    assert item.geometry.data["h_mm"] == 300
    assert item.placement.center_xy_mm == (100, 150)
    assert item.feature.type == "profile"
    assert item.feature.side == "outside"
    print("  PASSED")


def test_expand_simple_rect_rotated():
    """Expand rotated part swaps dimensions."""
    print("Running test_expand_simple_rect_rotated...")
    part = PartSpec(name="panel", width_mm=200, height_mm=300)
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 150),
        rotated=True,
        sheet_thickness_mm=19,
    )

    assert len(items) == 1
    item = items[0]
    # Dimensions swapped due to rotation
    assert item.geometry.data["w_mm"] == 300
    assert item.geometry.data["h_mm"] == 200
    print("  PASSED")


def test_expand_shaker_template():
    """Expand Shaker template to multiple items."""
    print("Running test_expand_shaker_template...")
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="Shaker",
        template_params={
            "stile_w": 50,
            "rail_h": 50,
            "panel_recess": 6,
        },
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(500, 500),
        rotated=False,
        sheet_thickness_mm=19,
    )

    # Shaker produces at least 2 items: outer profile + panel pocket
    assert len(items) >= 2

    # Find outer profile
    outer = None
    panel = None
    for item in items:
        if "outer" in (item.shape_id or ""):
            outer = item
        elif "panel" in (item.shape_id or ""):
            panel = item

    assert outer is not None, "Missing outer profile"
    assert panel is not None, "Missing panel pocket"

    # Outer should be at center
    assert outer.placement.center_xy_mm == (500, 500)
    assert outer.geometry.data["w_mm"] == 400
    assert outer.geometry.data["h_mm"] == 600

    # Panel should be smaller (inner dimensions)
    assert panel.geometry.data["w_mm"] == 300  # 400 - 2*50
    assert panel.geometry.data["h_mm"] == 500  # 600 - 2*50
    assert panel.feature.type == "pocket"

    print("  PASSED")


def test_expand_shaker_rotated():
    """Expand rotated Shaker template."""
    print("Running test_expand_shaker_rotated...")
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="Shaker",
        template_params={
            "stile_w": 50,
            "rail_h": 50,
            "panel_recess": 6,
        },
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(500, 500),
        rotated=True,
        sheet_thickness_mm=19,
    )

    # Find outer profile
    outer = None
    for item in items:
        if "outer" in (item.shape_id or ""):
            outer = item
            break

    assert outer is not None

    # Dimensions should be swapped due to rotation
    assert outer.geometry.data["w_mm"] == 600  # Was height
    assert outer.geometry.data["h_mm"] == 400  # Was width

    print("  PASSED")


def test_placement_to_items():
    """Convert Placement to Items."""
    print("Running test_placement_to_items...")
    part = PartSpec(name="panel", width_mm=200, height_mm=300)
    placement = NestedPart(
        part_spec=part,
        x_mm=250,
        y_mm=350,
        rotated=False,
        instance_id=2,
    )

    items = placement_to_items(placement, sheet_thickness_mm=19)

    assert len(items) == 1
    item = items[0]
    assert item.placement.center_xy_mm == (250, 350)
    # Shape ID should include name and instance
    assert "panel" in item.shape_id
    assert "2" in item.shape_id

    print("  PASSED")


def test_shape_id_prefix():
    """Shape IDs use provided prefix."""
    print("Running test_shape_id_prefix...")
    part = PartSpec(name="door", width_mm=400, height_mm=600)
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(200, 300),
        rotated=False,
        sheet_thickness_mm=19,
        shape_id_prefix="sheet1_door3_",
    )

    assert len(items) >= 1
    assert items[0].shape_id.startswith("sheet1_door3_")

    print("  PASSED")


def test_shaker_with_anchor_recess():
    """Shaker with anchor holes produces more items."""
    print("Running test_shaker_with_anchor_recess...")
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="Shaker",
        template_params={
            "stile_w": 50,
            "rail_h": 50,
            "panel_recess": 6,
            "anchor_recess": {
                "enabled": True,
                "diameter_mm": 25,
                "extra_depth_mm": 2,
                "offsets_mm": {"left": 30, "right": 30, "top": 30, "bottom": 30},
            },
        },
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(500, 500),
        rotated=False,
        sheet_thickness_mm=19,
    )

    # Should have outer + panel + 4 anchor holes
    assert len(items) >= 6

    # Count anchor holes
    anchors = [item for item in items if "anchor" in (item.shape_id or "")]
    assert len(anchors) == 4

    # Anchors should be circles
    for anchor in anchors:
        assert anchor.type == "Circle"
        assert anchor.feature.type == "hole"

    print("  PASSED")


def test_unknown_template_fallback():
    """Unknown template falls back to simple rect."""
    print("Running test_unknown_template_fallback...")
    part = PartSpec(
        name="custom",
        width_mm=300,
        height_mm=400,
        template="UnknownTemplate",  # Not registered
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(200, 250),
        rotated=False,
        sheet_thickness_mm=19,
    )

    # Should fall back to simple rect
    assert len(items) == 1
    assert items[0].type == "Rect"
    assert items[0].geometry.data["w_mm"] == 300
    assert items[0].geometry.data["h_mm"] == 400

    print("  PASSED")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Phase 4: Template Expander Tests")
    print("=" * 60)

    tests = [
        test_shaker_template_registered,
        test_get_part_bounds_simple,
        test_expand_simple_rect,
        test_expand_simple_rect_rotated,
        test_expand_shaker_template,
        test_expand_shaker_rotated,
        test_placement_to_items,
        test_shape_id_prefix,
        test_shaker_with_anchor_recess,
        test_unknown_template_fallback,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
