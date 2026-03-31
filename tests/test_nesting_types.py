from nesting.types import (
    NestedPart,
    NestingResult,
    PartSpec,
    SheetLayout,
    SheetSpec,
)


def test_part_spec_basic():
    part = PartSpec(name="door", width_mm=457, height_mm=597, quantity=4)
    assert part.name == "door"
    assert part.width_mm == 457
    assert part.height_mm == 597
    assert part.quantity == 4
    assert part.template is None
    assert part.allow_rotation is True


def test_part_spec_with_template():
    params = {"stile_w": 57, "rail_h": 57, "panel_recess": 6}
    part = PartSpec(
        name="shaker_door",
        width_mm=457,
        height_mm=597,
        quantity=20,
        template="Shaker",
        template_params=params,
    )
    assert part.template == "Shaker"
    assert part.template_params == params


def test_part_spec_area():
    part = PartSpec(name="panel", width_mm=100, height_mm=200, quantity=5)
    assert part.area_mm2 == 20000
    assert part.total_area_mm2 == 100000


def test_part_spec_area_circle():
    import math

    part = PartSpec(name="disc", width_mm=200, height_mm=200, shape="Circle")
    expected = math.pi / 4 * 200 * 200
    assert abs(part.area_mm2 - expected) < 0.01
    assert abs(part.total_area_mm2 - expected) < 0.01


def test_part_spec_area_polygon():
    points = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    part = PartSpec(
        name="square_poly",
        width_mm=100,
        height_mm=100,
        shape="Polygon",
        geometry_points=points,
    )
    assert abs(part.area_mm2 - 10000) < 0.01


def test_part_spec_area_triangle():
    points = ((0.0, 0.0), (100.0, 0.0), (50.0, 100.0))
    part = PartSpec(
        name="tri",
        width_mm=100,
        height_mm=100,
        shape="Triangle",
        geometry_points=points,
    )
    assert abs(part.area_mm2 - 5000) < 0.01


def test_part_spec_area_rounded_rect():
    part = PartSpec(name="panel", width_mm=100, height_mm=200, shape="RoundedRect")
    assert part.area_mm2 == 20000


def test_sheet_layout_utilization_circle():
    import math

    sheet = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, kerf_mm=6)
    circle_part = PartSpec(name="disc", width_mm=200, height_mm=200, shape="Circle")
    placement = NestedPart(part_spec=circle_part, x_mm=100, y_mm=100)
    layout = SheetLayout(sheet_spec=sheet, placements=(placement,))
    expected_area = math.pi / 4 * 200 * 200
    assert abs(layout.parts_area_mm2 - expected_area) < 0.01


def test_part_spec_validation():

    try:
        PartSpec(name="bad", width_mm=-100, height_mm=100)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "width_mm must be positive" in str(e)

    try:
        PartSpec(name="bad", width_mm=100, height_mm=0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "height_mm must be positive" in str(e)

    try:
        PartSpec(name="bad", width_mm=100, height_mm=100, quantity=-1)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "quantity must be non-negative" in str(e)

    part = PartSpec(name="maybe", width_mm=100, height_mm=100, quantity=0)
    assert part.quantity == 0


def test_part_spec_immutable():
    part = PartSpec(name="door", width_mm=100, height_mm=100)
    try:
        part.width_mm = 200  # type: ignore[misc]
        raise AssertionError("Should have raised AttributeError")
    except AttributeError:
        pass


def test_part_spec_json_roundtrip():
    original = PartSpec(
        name="test",
        width_mm=457,
        height_mm=597,
        quantity=10,
        template="Shaker",
        template_params={"stile_w": 57},
        allow_rotation=False,
    )
    data = original.to_dict()
    restored = PartSpec.from_dict(data)
    assert restored == original


def test_sheet_spec_basic():
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sheet = SheetSpec(width_mm=1220, height_mm=2440, thickness_mm=19)

        assert len(w) == 1
        assert "kerf_mm not specified" in str(w[0].message)

    assert sheet.width_mm == 1220
    assert sheet.height_mm == 2440
    assert sheet.thickness_mm == 19
    assert sheet.margin_mm == 10.0
    assert sheet.kerf_mm == 6.35
    assert sheet.gap_margin_mm == 0.0
    assert sheet.gap_mm == 6.35


def test_sheet_spec_usable_area():
    sheet = SheetSpec(
        width_mm=1000,
        height_mm=2000,
        thickness_mm=19,
        margin_mm=10,
    )

    assert sheet.usable_width_mm == 980
    assert sheet.usable_height_mm == 1980
    assert sheet.usable_area_mm2 == 980 * 1980


def test_sheet_spec_validation():

    try:
        SheetSpec(width_mm=1000, height_mm=2000, thickness_mm=-1)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "thickness_mm must be positive" in str(e)

    try:
        SheetSpec(width_mm=1000, height_mm=2000, thickness_mm=19, margin_mm=-5)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "margin_mm must be non-negative" in str(e)

    try:
        SheetSpec(width_mm=100, height_mm=100, thickness_mm=19, margin_mm=60)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "no usable area" in str(e).lower()


def test_sheet_spec_json_roundtrip():
    original = SheetSpec(
        width_mm=1245,
        height_mm=1232,
        thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
    )
    data = original.to_dict()
    restored = SheetSpec.from_dict(data)
    assert restored == original


def test_nested_part_basic():
    part = PartSpec(name="door", width_mm=457, height_mm=597)
    placement = NestedPart(part_spec=part, x_mm=238.5, y_mm=308.5)
    assert placement.part_spec == part
    assert placement.x_mm == 238.5
    assert placement.y_mm == 308.5
    assert placement.rotated is False
    assert placement.instance_id == 0


def test_nested_part_bounds_no_rotation():
    part = PartSpec(name="door", width_mm=100, height_mm=200)
    placement = NestedPart(part_spec=part, x_mm=100, y_mm=150)

    assert placement.left_mm == 50
    assert placement.right_mm == 150
    assert placement.bottom_mm == 50
    assert placement.top_mm == 250
    assert placement.bounds == (50, 50, 150, 250)


def test_nested_part_bounds_with_rotation():
    part = PartSpec(name="door", width_mm=100, height_mm=200)
    placement = NestedPart(part_spec=part, x_mm=150, y_mm=100, rotated=True)

    assert placement.effective_width_mm == 200
    assert placement.effective_height_mm == 100
    assert placement.left_mm == 50
    assert placement.right_mm == 250
    assert placement.bottom_mm == 50
    assert placement.top_mm == 150


def test_nested_part_json_roundtrip():
    part = PartSpec(name="door", width_mm=457, height_mm=597, quantity=4)
    original = NestedPart(
        part_spec=part,
        x_mm=238.5,
        y_mm=308.5,
        rotated=True,
        instance_id=2,
    )
    data = original.to_dict()
    restored = NestedPart.from_dict(data)
    assert restored.part_spec == original.part_spec
    assert restored.x_mm == original.x_mm
    assert restored.y_mm == original.y_mm
    assert restored.rotated == original.rotated
    assert restored.instance_id == original.instance_id


def test_sheet_layout_empty():
    sheet = SheetSpec(width_mm=1000, height_mm=2000, thickness_mm=19)
    layout = SheetLayout(sheet_spec=sheet, placements=())
    assert layout.part_count == 0
    assert layout.parts_area_mm2 == 0
    assert layout.utilization == 0.0


def test_sheet_layout_single_part():
    sheet = SheetSpec(
        width_mm=1000,
        height_mm=1000,
        thickness_mm=19,
        margin_mm=0,
    )
    part = PartSpec(name="square", width_mm=500, height_mm=500)
    placement = NestedPart(part_spec=part, x_mm=250, y_mm=250)
    layout = SheetLayout(sheet_spec=sheet, placements=(placement,))

    assert layout.part_count == 1
    assert layout.parts_area_mm2 == 250_000
    assert layout.utilization == 0.25


def test_sheet_layout_multiple_parts():
    sheet = SheetSpec(
        width_mm=1000,
        height_mm=1000,
        thickness_mm=19,
        margin_mm=0,
    )
    part1 = PartSpec(name="a", width_mm=400, height_mm=400)
    part2 = PartSpec(name="b", width_mm=300, height_mm=300)
    layout = SheetLayout(
        sheet_spec=sheet,
        placements=(
            NestedPart(part_spec=part1, x_mm=200, y_mm=200),
            NestedPart(part_spec=part2, x_mm=650, y_mm=150),
        ),
    )

    assert layout.part_count == 2
    assert layout.parts_area_mm2 == 160_000 + 90_000
    assert layout.utilization == 0.25


def test_sheet_layout_json_roundtrip():
    sheet = SheetSpec(width_mm=1245, height_mm=1232, thickness_mm=19)
    part = PartSpec(name="door", width_mm=457, height_mm=597)
    layout = SheetLayout(
        sheet_spec=sheet,
        placements=(
            NestedPart(part_spec=part, x_mm=238.5, y_mm=308.5, instance_id=0),
            NestedPart(part_spec=part, x_mm=701.5, y_mm=308.5, instance_id=1),
        ),
        sheet_index=0,
    )
    data = layout.to_dict()
    restored = SheetLayout.from_dict(data)
    assert restored.sheet_spec == layout.sheet_spec
    assert len(restored.placements) == len(layout.placements)
    assert restored.sheet_index == layout.sheet_index


def test_nesting_result_empty():
    result = NestingResult(sheets=())
    assert result.total_sheets == 0
    assert result.total_parts == 0
    assert result.overall_utilization == 0.0


def test_nesting_result_single_sheet():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=0)
    part = PartSpec(name="panel", width_mm=500, height_mm=500)
    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250),),
        sheet_index=0,
    )
    result = NestingResult(sheets=(layout,))

    assert result.total_sheets == 1
    assert result.total_parts == 1
    assert result.overall_utilization == 0.25


def test_nesting_result_multiple_sheets():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=0)
    part = PartSpec(name="panel", width_mm=500, height_mm=500)

    sheet1 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),
            NestedPart(part_spec=part, x_mm=750, y_mm=250, instance_id=1),
        ),
        sheet_index=0,
    )
    sheet2 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=2),),
        sheet_index=1,
    )

    result = NestingResult(sheets=(sheet1, sheet2))

    assert result.total_sheets == 2
    assert result.total_parts == 3
    assert result.total_parts_area_mm2 == 750_000
    assert result.total_sheet_area_mm2 == 2_000_000
    assert result.overall_utilization == 0.375
    assert result.waste_area_mm2 == 1_250_000


def test_nesting_result_unplaced_parts():
    big_part = PartSpec(name="too_big", width_mm=5000, height_mm=5000)
    result = NestingResult(sheets=(), unplaced_parts=(big_part,))

    assert result.total_sheets == 0
    assert len(result.unplaced_parts) == 1
    assert result.unplaced_parts[0].name == "too_big"


def test_nesting_result_json_roundtrip():
    sheet_spec = SheetSpec(width_mm=1245, height_mm=1232, thickness_mm=19)
    part = PartSpec(name="door", width_mm=457, height_mm=597, quantity=4)
    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=238.5, y_mm=308.5, instance_id=0),
            NestedPart(part_spec=part, x_mm=701.5, y_mm=308.5, instance_id=1),
        ),
        sheet_index=0,
    )
    unplaced = PartSpec(name="huge", width_mm=9999, height_mm=9999)
    result = NestingResult(sheets=(layout,), unplaced_parts=(unplaced,))

    json_str = result.to_json()
    restored = NestingResult.from_json(json_str)

    assert restored.total_sheets == result.total_sheets
    assert restored.total_parts == result.total_parts
    assert len(restored.unplaced_parts) == 1
    assert restored.unplaced_parts[0].name == "huge"


def test_recipe16_like_layout():
    sheet_spec = SheetSpec(
        width_mm=1245,
        height_mm=1232,
        thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
    )

    door = PartSpec(name="cabinet_door", width_mm=457, height_mm=597, quantity=4)
    drawer = PartSpec(name="drawer_front", width_mm=254, height_mm=152, quantity=7)

    placements = []

    door_positions = [
        (238.5, 308.5),
        (701.5, 308.5),
        (238.5, 911.5),
        (701.5, 911.5),
    ]
    for i, (x, y) in enumerate(door_positions):
        placements.append(NestedPart(part_spec=door, x_mm=x, y_mm=y, instance_id=i))

    drawer_y_positions = [86, 244, 402, 560, 718, 876, 1034]
    for i, y in enumerate(drawer_y_positions):
        placements.append(NestedPart(part_spec=drawer, x_mm=1063, y_mm=y, instance_id=i))

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=tuple(placements),
        sheet_index=0,
    )

    assert layout.part_count == 11

    door_area = 4 * 457 * 597
    drawer_area = 7 * 254 * 152
    expected_area = door_area + drawer_area

    assert layout.parts_area_mm2 == expected_area

    assert layout.utilization > 0.90
    assert layout.utilization < 0.95

    result = NestingResult(sheets=(layout,))
    assert result.total_sheets == 1
    assert result.overall_utilization_percent > 90


def test_part_spec_shape_serialization():
    original = PartSpec(
        name="coaster",
        width_mm=100,
        height_mm=100,
        shape="RoundedRect",
        shape_params={"radius_mm": 10.0, "corners": ("bl", "tl")},
    )
    data = original.to_dict()
    restored = PartSpec.from_dict(data)
    assert restored.shape == "RoundedRect"
    assert restored.shape_params is not None
    assert restored.shape_params["radius_mm"] == 10.0
    assert restored.shape_params["corners"] == ("bl", "tl")


def test_part_spec_shape_params_json_safe():
    import json

    part = PartSpec(
        name="coaster",
        width_mm=100,
        height_mm=100,
        shape="RoundedRect",
        shape_params={"radius_mm": 10.0, "corners": ("bl", "tl")},
    )
    data = part.to_dict()
    json_str = json.dumps(data)
    assert "radius_mm" in json_str


def test_part_spec_corners_normalized_after_json_round_trip():
    import json

    original = PartSpec(
        name="strip",
        width_mm=200,
        height_mm=100,
        shape="RoundedRect",
        shape_params={"radius_mm": 12.7, "corners": ("bl", "tl")},
    )
    data = original.to_dict()
    json_str = json.dumps(data)
    restored_data = json.loads(json_str)
    restored = PartSpec.from_dict(restored_data)
    assert restored.shape_params is not None
    assert isinstance(restored.shape_params["corners"], tuple)
    assert restored.shape_params["corners"] == ("bl", "tl")


def test_polygon_geometry_points_populated():
    from nesting.api import _parts_from_dicts

    parts = _parts_from_dicts(
        [
            {
                "name": "gusset",
                "width_mm": 100,
                "height_mm": 100,
                "shape": "Polygon",
                "shape_params": {"points": [[-50, -50], [50, -50], [0, 50]]},
            }
        ]
    )
    assert parts[0].geometry_points is not None
    assert len(parts[0].geometry_points) == 3
    assert parts[0].geometry_points[0] == (-50, -50)
