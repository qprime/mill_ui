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
    assert "points" in profile.geometry.data
    profile_points = profile.geometry.data["points"]
    profile_xs = [p[0] for p in profile_points]
    profile_ys = [p[1] for p in profile_points]
    assert abs((max(profile_xs) - min(profile_xs)) - 400) < 0.01
    assert abs((max(profile_ys) - min(profile_ys)) - 600) < 0.01

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


def test_expand_rounded_rect():
    part = PartSpec(
        name="coaster",
        width_mm=100,
        height_mm=100,
        shape="RoundedRect",
        shape_params={"radius_mm": 10.0},
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(50, 50),
        rotated=False,
        sheet_thickness_mm=19,
    )
    assert len(items) == 1
    item = items[0]
    assert item.type == "RoundedRect"
    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 100
    assert item.geometry.data["h_mm"] == 100
    assert item.geometry.data["radius_tl_mm"] == 10.0
    assert item.geometry.data["radius_tr_mm"] == 10.0
    assert item.geometry.data["radius_bl_mm"] == 10.0
    assert item.geometry.data["radius_br_mm"] == 10.0
    assert item.geometry.data["radius_mm"] == 10.0
    assert item.geometry.data["corner_radius_mm"] == 10.0


def test_expand_rounded_rect_selective_corners():
    part = PartSpec(
        name="strip",
        width_mm=200,
        height_mm=800,
        shape="RoundedRect",
        shape_params={"radius_mm": 12.7, "corners": ("bl", "tl")},
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 400),
        rotated=False,
        sheet_thickness_mm=19,
    )
    item = items[0]
    assert item.type == "RoundedRect"
    assert item.geometry is not None
    assert item.geometry.data["radius_tl_mm"] == 12.7
    assert item.geometry.data["radius_bl_mm"] == 12.7
    assert item.geometry.data["radius_tr_mm"] == 0.0
    assert item.geometry.data["radius_br_mm"] == 0.0
    assert "radius_mm" not in item.geometry.data


def test_expand_rounded_rect_rotated():
    part = PartSpec(
        name="strip",
        width_mm=200,
        height_mm=800,
        shape="RoundedRect",
        shape_params={"radius_mm": 12.7, "corners": ("bl", "tl")},
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(400, 100),
        rotated=True,
        sheet_thickness_mm=19,
    )
    item = items[0]
    assert item.type == "RoundedRect"
    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 800
    assert item.geometry.data["h_mm"] == 200
    assert item.geometry.data["radius_bl_mm"] == 12.7
    assert item.geometry.data["radius_br_mm"] == 12.7
    assert item.geometry.data["radius_tl_mm"] == 0.0
    assert item.geometry.data["radius_tr_mm"] == 0.0


def test_expand_circle():
    part = PartSpec(
        name="disc",
        width_mm=200,
        height_mm=200,
        shape="Circle",
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 100),
        rotated=False,
        sheet_thickness_mm=19,
    )
    assert len(items) == 1
    item = items[0]
    assert item.type == "Circle"
    assert item.geometry is not None
    assert item.geometry.data["diameter_mm"] == 200.0


def test_expand_no_shape():
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


def test_expand_polygon():
    points = [[-50, -50], [50, -50], [50, 50]]
    part = PartSpec(
        name="gusset",
        width_mm=100,
        height_mm=100,
        shape="Polygon",
        shape_params={"points": points},
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(200, 200),
        rotated=False,
        sheet_thickness_mm=19,
    )
    item = items[0]
    assert item.type == "Polygon"
    assert item.geometry is not None
    assert item.geometry.data["points"] == points
    assert item.geometry.data["holes"] == []


def test_expand_triangle():
    part = PartSpec(
        name="bracket",
        width_mm=100,
        height_mm=80,
        shape="Triangle",
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(200, 200),
        rotated=False,
        sheet_thickness_mm=19,
    )
    item = items[0]
    assert item.type == "Polygon"
    assert item.geometry is not None
    assert len(item.geometry.data["points"]) == 3
    pts = item.geometry.data["points"]
    assert pts[0] == [-50.0, -40.0]
    assert pts[1] == [50.0, -40.0]
    assert pts[2] == [0.0, 40.0]


def test_expand_polygon_rotated():
    points = [[-50, -25], [50, -25], [0, 25]]
    part = PartSpec(
        name="gusset",
        width_mm=100,
        height_mm=50,
        shape="Polygon",
        shape_params={"points": points},
    )
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(200, 200),
        rotated=True,
        sheet_thickness_mm=19,
    )
    item = items[0]
    assert item.type == "Polygon"
    assert item.geometry is not None
    assert item.geometry.data["points"] == points
    assert item.geometry.data["holes"] == []


def test_triangle_normalizes_to_polygon():
    from nesting.template_expander import _build_geometry_data

    item_type, data = _build_geometry_data("Triangle", None, 100, 80)
    assert item_type == "Polygon"
    assert len(data["points"]) == 3


def test_expand_shape_id_suffix():
    for shape, expected_suffix in [
        ("RoundedRect", "roundedrect"),
        ("Circle", "circle"),
        ("Triangle", "polygon"),
        (None, "rect"),
    ]:
        params = {"radius_mm": 5.0} if shape == "RoundedRect" else None
        part = PartSpec(
            name="x",
            width_mm=100,
            height_mm=100,
            shape=shape,
            shape_params=params,
        )
        items = expand_part_to_items(
            part_spec=part,
            center_xy=(50, 50),
            rotated=False,
            sheet_thickness_mm=19,
            shape_id_prefix="test_",
        )
        assert items[0].shape_id == f"test_{expected_suffix}", (
            f"shape={shape}: expected test_{expected_suffix}, got {items[0].shape_id}"
        )


def test_holding_onion_skin_on_feature():
    from pml.nest_parser import HoldingSpec

    holding = HoldingSpec(onion_skin_mm=0.3)
    part = PartSpec(name="panel", width_mm=200, height_mm=300, holding=holding)
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 150),
        rotated=False,
        sheet_thickness_mm=19,
    )
    assert len(items) == 1
    feature = items[0].feature
    assert feature is not None
    assert feature.onion_skin_mm == 0.3
    assert feature.tab_count is None
    assert feature.is_through is True


def test_holding_tabs_on_feature():
    from pml.nest_parser import HoldingSpec

    holding = HoldingSpec(tab_count=4, tab_height_mm=3.0, tab_width_mm=10.0)
    part = PartSpec(name="panel", width_mm=200, height_mm=300, holding=holding)
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 150),
        rotated=False,
        sheet_thickness_mm=19,
    )
    assert len(items) == 1
    feature = items[0].feature
    assert feature is not None
    assert feature.tab_count == 4
    assert feature.tab_height_mm == 3.0
    assert feature.tab_width_mm == 10.0
    assert feature.onion_skin_mm is None
    assert feature.is_through is True


def test_holding_none_produces_bare_through():
    part = PartSpec(name="panel", width_mm=200, height_mm=300)
    items = expand_part_to_items(
        part_spec=part,
        center_xy=(100, 150),
        rotated=False,
        sheet_thickness_mm=19,
    )
    feature = items[0].feature
    assert feature is not None
    assert feature.is_through is True
    assert feature.onion_skin_mm is None
    assert feature.tab_count is None


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
        test_expand_rounded_rect,
        test_expand_rounded_rect_selective_corners,
        test_expand_rounded_rect_rotated,
        test_expand_circle,
        test_expand_no_shape,
        test_expand_polygon,
        test_expand_polygon_rotated,
        test_expand_triangle,
        test_triangle_normalizes_to_polygon,
        test_expand_shape_id_suffix,
        test_holding_onion_skin_on_feature,
        test_holding_tabs_on_feature,
        test_holding_none_produces_bare_through,
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
