import sys

import pytest

from nesting.template_expander import (
    expand_part_to_items,
    get_part_bounds,
    placement_to_items,
)
from nesting.types import NestedPart, PartSpec


def test_get_part_bounds_simple():
    print("Running test_get_part_bounds_simple...")
    part = PartSpec(name="panel", width_mm=400, height_mm=600)
    w, h = get_part_bounds(part)
    assert w == 400
    assert h == 600
    print("  PASSED")


def test_expand_simple_rect():
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
    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 200
    assert item.geometry.data["h_mm"] == 300
    assert item.placement is not None
    assert item.placement.center_xy_mm == (100, 150)
    assert item.feature is not None
    assert item.feature.type == "profile"
    assert item.feature.side == "outside"
    print("  PASSED")


def test_expand_simple_rect_rotated():
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

    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 300
    assert item.geometry.data["h_mm"] == 200
    print("  PASSED")


def test_expand_shaker_template():
    print("Running test_expand_shaker_template...")
    part = PartSpec(
        name="door",
        width_mm=400,
        height_mm=600,
        template="shaker",
        template_params={
            "stile_w": 50,
            "panel_recess": 6,
        },
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(500, 500),
        rotated=False,
        sheet_thickness_mm=19,
    )

    assert len(items) >= 2

    profile_items = [i for i in items if i.feature and i.feature.type == "profile"]
    pocket_items = [i for i in items if i.feature and i.feature.type == "pocket"]

    assert len(profile_items) >= 1, "Missing profile"
    assert len(pocket_items) >= 1, "Missing pocket"

    profile = profile_items[0]
    assert profile.placement is not None
    assert profile.placement.center_xy_mm == (500, 500)
    assert profile.geometry is not None
    assert profile.geometry.data["w_mm"] == 400
    assert profile.geometry.data["h_mm"] == 600

    pocket = pocket_items[0]
    assert pocket.geometry is not None
    assert pocket.geometry.data["w_mm"] == 300
    assert pocket.geometry.data["h_mm"] == 500
    assert pocket.feature is not None
    assert pocket.feature.type == "pocket"

    print("  PASSED")


def test_placement_to_items():
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
    assert item.placement is not None
    assert item.placement.center_xy_mm == (250, 350)

    assert item.shape_id is not None
    assert "panel" in item.shape_id
    assert "2" in item.shape_id

    print("  PASSED")


def test_shape_id_prefix():
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
    assert items[0].shape_id is not None
    assert items[0].shape_id.startswith("sheet1_door3_")

    print("  PASSED")


def test_unknown_template_raises():
    print("Running test_unknown_template_raises...")
    part = PartSpec(
        name="custom",
        width_mm=300,
        height_mm=400,
        template="UnknownTemplate",
    )

    with pytest.raises(ValueError) as exc_info:
        expand_part_to_items(
            part_spec=part,
            center_xy=(200, 250),
            rotated=False,
            sheet_thickness_mm=19,
        )
    assert "Template not found" in str(exc_info.value)

    print("  PASSED")


def run_all_tests():
    print("=" * 60)
    print("Template Expander Tests")
    print("=" * 60)

    tests = [
        test_get_part_bounds_simple,
        test_expand_simple_rect,
        test_expand_simple_rect_rotated,
        test_expand_shaker_template,
        test_placement_to_items,
        test_shape_id_prefix,
        test_unknown_template_raises,
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
