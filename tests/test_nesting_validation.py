from nesting.types import NestedPart, NestingResult, PartSpec, SheetLayout, SheetSpec
from nesting.validation import (
    validate_nesting_result,
    validate_sheet_layout,
)


def test_valid_layout_passes():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=part, x_mm=500, y_mm=200, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert result.is_valid, result.summary()


def test_out_of_bounds_error():
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=50, y_mm=250, instance_id=0),),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("outside sheet bounds" in e["message"] for e in result.errors)


def test_overlapping_error():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=0)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=part, x_mm=200, y_mm=200, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("overlap" in e["message"].lower() for e in result.errors)


def test_touching_parts_allowed():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=10)
    part = PartSpec(name="panel", width_mm=100, height_mm=100)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=100, y_mm=100, instance_id=0),
            NestedPart(part_spec=part, x_mm=200, y_mm=100, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert result.is_valid, f"Touching parts should be allowed (kerf overlap): {result.summary()}"


def test_geometry_overlap_error():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=10)
    part = PartSpec(name="panel", width_mm=100, height_mm=100)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=100, y_mm=100, instance_id=0),
            NestedPart(part_spec=part, x_mm=150, y_mm=100, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("overlap" in e["message"].lower() for e in result.errors)


def test_low_utilization_warning():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="tiny", width_mm=50, height_mm=50)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=100, y_mm=100, instance_id=0),),
    )

    result = validate_sheet_layout(layout)

    assert result.is_valid
    assert any("utilization" in w["message"].lower() for w in result.warnings)


def test_unplaced_parts_warning():
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19)
    placed_part = PartSpec(name="placed", width_mm=200, height_mm=200)
    unplaced_part = PartSpec(name="too_big", width_mm=1000, height_mm=1000, quantity=2)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=placed_part, x_mm=250, y_mm=250, instance_id=0),),
    )

    nesting = NestingResult(sheets=(layout,), unplaced_parts=(unplaced_part,))
    result = validate_nesting_result(nesting)

    assert any("could not place" in w["message"].lower() for w in result.warnings)


def test_multiple_sheets_validated():
    sheet_spec = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)
    part = PartSpec(name="panel", width_mm=200, height_mm=200)

    sheet1 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),),
        sheet_index=0,
    )

    sheet2 = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(NestedPart(part_spec=part, x_mm=50, y_mm=50, instance_id=1),),
        sheet_index=1,
    )

    nesting = NestingResult(sheets=(sheet1, sheet2))
    result = validate_nesting_result(nesting)

    assert not result.is_valid


def test_valid_nesting_result():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    part = PartSpec(name="panel", width_mm=300, height_mm=300)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=part, x_mm=250, y_mm=250, instance_id=0),
            NestedPart(part_spec=part, x_mm=650, y_mm=250, instance_id=1),
            NestedPart(part_spec=part, x_mm=250, y_mm=650, instance_id=2),
            NestedPart(part_spec=part, x_mm=650, y_mm=650, instance_id=3),
        ),
    )

    nesting = NestingResult(sheets=(layout,))
    result = validate_nesting_result(nesting)

    assert result.is_valid, result.summary()


def test_triangle_rectangle_no_overlap():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    rect = PartSpec(name="rect", width_mm=100, height_mm=100)
    triangle = PartSpec(
        name="triangle",
        width_mm=100,
        height_mm=100,
        geometry_points=((-50, -50), (50, -50), (0, 50)),
    )

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=rect, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=triangle, x_mm=400, y_mm=200, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)
    assert result.is_valid, result.summary()


def test_triangle_rectangle_overlap():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    rect = PartSpec(name="rect", width_mm=100, height_mm=100)
    triangle = PartSpec(
        name="triangle",
        width_mm=100,
        height_mm=100,
        geometry_points=((-50, -50), (50, -50), (0, 50)),
    )

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=rect, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=triangle, x_mm=220, y_mm=200, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("overlap" in e["message"].lower() for e in result.errors)


def test_triangles_bounding_box_overlap_but_no_geometry_overlap():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    triangle_up = PartSpec(
        name="tri_up",
        width_mm=100,
        height_mm=100,
        geometry_points=((-50, -50), (50, -50), (0, 50)),
    )
    triangle_down = PartSpec(
        name="tri_down",
        width_mm=100,
        height_mm=100,
        geometry_points=((-50, 50), (50, 50), (0, -50)),
    )

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=triangle_up, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=triangle_down, x_mm=250, y_mm=200, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)
    assert result.is_valid, f"Triangles should not overlap (interleaved): {result.summary()}"


def test_polygon_overlap_with_location():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    rect = PartSpec(name="rect", width_mm=100, height_mm=100)

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=rect, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=rect, x_mm=250, y_mm=200, instance_id=1),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert result.errors[0].get("overlap_location") is not None
    loc = result.errors[0]["overlap_location"]
    assert 200 <= loc[0] <= 250
    assert 150 <= loc[1] <= 250


def test_rotated_polygon_overlap():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    triangle = PartSpec(
        name="triangle",
        width_mm=100,
        height_mm=100,
        geometry_points=((-50, -50), (50, -50), (0, 50)),
    )

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=triangle, x_mm=200, y_mm=200, instance_id=0, rotated=False),
            NestedPart(part_spec=triangle, x_mm=200, y_mm=200, instance_id=1, rotated=True),
        ),
    )

    result = validate_sheet_layout(layout)
    assert not result.is_valid
    assert any("overlap" in e["message"].lower() for e in result.errors)


def test_polygon_from_shape_uses_geometry_points():
    sheet_spec = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)
    tri_up = PartSpec(
        name="tri_up",
        width_mm=100,
        height_mm=100,
        shape="Polygon",
        shape_params={"points": [[-50, -50], [50, -50], [0, 50]]},
        geometry_points=((-50, -50), (50, -50), (0, 50)),
    )
    tri_down = PartSpec(
        name="tri_down",
        width_mm=100,
        height_mm=100,
        shape="Polygon",
        shape_params={"points": [[-50, 50], [50, 50], [0, -50]]},
        geometry_points=((-50, 50), (50, 50), (0, -50)),
    )

    layout = SheetLayout(
        sheet_spec=sheet_spec,
        placements=(
            NestedPart(part_spec=tri_up, x_mm=200, y_mm=200, instance_id=0),
            NestedPart(part_spec=tri_down, x_mm=250, y_mm=200, instance_id=0),
        ),
    )

    result = validate_sheet_layout(layout)
    assert result.is_valid, f"Polygon parts with shape field should use geometry_points: {result.summary()}"
