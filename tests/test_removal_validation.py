from __future__ import annotations

from dataclasses import replace

import pytest

from adapters.hints_to_removal import (
    engrave_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    profile_hint_to_removal_intent,
)
from ir.removal_intent import Allowance, Bounds2D, Constraints, DepthProfile, Island, KeepoutRegion, RemovalIntent
from validation import (
    ValidationResult,
    check_back_face_support,
    check_cross_face_web,
    check_depth_feasibility,
    check_overlap,
    check_toolability,
    check_toolpath_clearance,
    check_working_area_bounds,
)


def _make_intent(
    region_id: str,
    bounds: Bounds2D,
    z_top: float = 0.0,
    z_bottom: float = -5.0,
    allowance: Allowance | None = None,
    constraints: Constraints | None = None,
    hint_type: str = "",
    side: str | None = None,
) -> RemovalIntent:
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=z_top, z_bottom=z_bottom),
        hint_type=hint_type,
        side=side,
        allowance=allowance or Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=constraints or Constraints(tabs=None, keepouts=(), islands=(), tolerance_mm=0.1, safe_z_mm=5.0),
    )


def _floor_pocket() -> RemovalIntent:
    return pocket_hint_to_removal_intent(
        {
            "id": "floor",
            "shape": "Rect",
            "center_xy_mm": [150, 150],
            "geometry": {"w_mm": 100, "h_mm": 80},
            "depth_mm": 3,
        }
    )


def _notch_and_back_groove(start: float = 20) -> list[RemovalIntent]:
    from assembly.notches import build_notched_polygon
    from assembly.panel import Edge, NotchSpec
    from ir.removal_intent import DogboneSpec

    points = build_notched_polygon(100, 100, (0, 0), [NotchSpec(Edge.TOP, start, 20, 18)])
    outline = profile_hint_to_removal_intent(
        {
            "id": "outline",
            "shape": "Polygon",
            "center_xy_mm": [50, 50],
            "geometry": {"points": points},
            "side": "outside",
            "depth_mm": 18,
        },
        18,
    )
    groove = pocket_hint_to_removal_intent(
        {
            "id": "back_slot",
            "shape": "Rect",
            "center_xy_mm": [50, 90.9],
            "geometry": {"w_mm": 100, "h_mm": 18.2},
            "depth_mm": 9,
        }
    )
    relief = pocket_hint_to_removal_intent(
        {
            "id": "corner_relief",
            "shape": "Rect",
            "center_xy_mm": [start + 10, 91],
            "geometry": {"w_mm": 20, "h_mm": 18},
            "depth_mm": 18,
        }
    )
    return [
        outline,
        replace(groove, dogbone=DogboneSpec()),
        replace(
            relief,
            dogbone=DogboneSpec(),
            dogbone_corners=((start, 82), (start + 20, 82)),
            dogbone_reference_point=(50, 50),
        ),
    ]


@pytest.mark.parametrize("start", [0, 20])
@pytest.mark.parametrize("order", [(0, 1, 2), (2, 1, 0), (1, 2, 0)])
@pytest.mark.parametrize("reference_inside_notch", [False, True])
def test_back_groove_may_cross_relief_of_a_proven_profile_notch(start, order, reference_inside_notch):
    intents = _notch_and_back_groove(start)
    if reference_inside_notch:
        intents[2] = replace(intents[2], dogbone_reference_point=intents[2].bounds.center)
    assert check_overlap([intents[index] for index in order]).is_valid()


def test_notch_relief_cannot_claim_a_profile_that_is_missing():
    assert len(check_overlap(_notch_and_back_groove()[1:]).errors) == 1


@pytest.mark.parametrize(
    "index, changes",
    [
        (0, {"shape": "Rect"}),
        (0, {"side": "inside"}),
        (0, {"face": "back"}),
        (0, {"depth_profile": DepthProfile.constant(0, -20)}),
        (1, {"bounds": Bounds2D(0, 101, 81.8, 100)}),
        (1, {"shape": "Circle"}),
        (1, {"depth_profile": DepthProfile.constant(0, -18)}),
        (1, {"depth_profile": DepthProfile.constant(-1, -9)}),
        (2, {"dogbone_corners": None}),
        (2, {"dogbone_reference_point": None}),
        (2, {"dogbone_reference_point": (130, 90)}),
        (2, {"dogbone_corners": ((20, 83), (40, 83))}),
        (2, {"depth_profile": DepthProfile.constant(0, -19)}),
        (2, {"depth_profile": DepthProfile.constant(-1, -18)}),
    ],
)
def test_unproven_notch_relief_overlap_keeps_its_report(index, changes):
    intents = _notch_and_back_groove()
    intents[index] = replace(intents[index], **changes)
    assert check_overlap(intents).errors


def test_notch_relief_rectangle_must_be_in_the_profile_cutout():
    intents = _notch_and_back_groove()
    intents[2] = replace(intents[2], bounds=Bounds2D(20, 40, 80, 100), dogbone_corners=((20, 80), (40, 80)))
    assert check_overlap(intents).errors


def test_relief_cannot_claim_an_uncut_or_invalid_polygon_boundary():
    from ir.removal_intent import ShapeGeometry

    for points in (
        ((-50, -50), (50, -50), (50, 50), (-50, 50)),
        ((-50, -50), (50, 50), (50, -50), (-50, 50)),
    ):
        intents = _notch_and_back_groove()
        intents[0] = replace(intents[0], shape_geometry=ShapeGeometry(points=points))
        intents[2] = replace(intents[2], dogbone_corners=((20, 100), (40, 100)))
        assert check_overlap(intents).errors


def _floor_hole(center: tuple[float, float] = (150, 150), depth: float = 19) -> RemovalIntent:
    return hole_hint_to_removal_intent(
        {"id": "mount", "shape": "Circle", "center_xy_mm": center, "geometry": {"diameter_mm": 6}, "depth_mm": depth}
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_contained_hole_through_pocket_floor_is_a_compatible_cut(reverse):
    pair = [_floor_pocket(), _floor_hole()]
    assert check_overlap(list(reversed(pair)) if reverse else pair).is_valid()


@pytest.mark.parametrize("depth, valid", [(2, False), (3, False), (10, True), (19, True)])
def test_pocket_floor_hole_must_extend_below_the_floor(depth, valid):
    assert check_overlap([_floor_pocket(), _floor_hole(depth=depth)]).is_valid() == valid


@pytest.mark.parametrize("x, valid", [(198, False), (197, False), (196.9999999, False), (196.9, True)])
def test_pocket_floor_hole_requires_clearance_from_pocket_walls(x, valid):
    assert check_overlap([_floor_pocket(), _floor_hole(center=(x, 150))]).is_valid() == valid


def test_floor_hole_must_avoid_a_preserved_island():
    from dataclasses import replace

    pocket = replace(_floor_pocket(), constraints=Constraints(islands=(Island(Bounds2D(140, 160, 140, 160)),)))
    assert len(check_overlap([pocket, _floor_hole(center=(140, 150))]).errors) == 1


@pytest.mark.parametrize("center, valid", [((140, 150), False), ((180, 150), True)])
def test_floor_hole_must_avoid_polygon_holes(center, valid):
    pocket = pocket_hint_to_removal_intent(
        {
            "id": "ring",
            "shape": "Polygon",
            "center_xy_mm": [150, 150],
            "geometry": {
                "points": [[-50, -40], [50, -40], [50, 40], [-50, 40]],
                "holes": [[[-10, -10], [-10, 10], [10, 10], [10, -10]]],
            },
            "depth_mm": 3,
        }
    )
    assert check_overlap([pocket, _floor_hole(center=center)]).is_valid() == valid


@pytest.mark.parametrize("center, valid", [((80, 85), False), ((65, 120), True)])
def test_floor_hole_containment_uses_a_concave_pockets_actual_region(center, valid):
    pocket = pocket_hint_to_removal_intent(
        {
            "id": "concave",
            "shape": "Polygon",
            "center_xy_mm": [50, 50],
            "geometry": {"points": [[0, 0], [100, 0], [100, 30], [30, 30], [30, 100], [0, 100]]},
            "depth_mm": 3,
        }
    )
    assert check_overlap([pocket, _floor_hole(center=center)]).is_valid() == valid


def test_round_pocket_bounds_are_not_proof_of_floor_containment():
    pocket = pocket_hint_to_removal_intent(
        {"id": "round", "shape": "Circle", "center_xy_mm": [150, 150], "geometry": {"diameter_mm": 100}, "depth_mm": 3}
    )
    assert len(check_overlap([pocket, _floor_hole(center=(185, 185))]).errors) == 1


@pytest.mark.parametrize("index", [0, 1])
def test_pocket_floor_hole_with_nonzero_start_keeps_conservative_overlap_check(index):
    from dataclasses import replace

    pair = [_floor_pocket(), _floor_hole()]
    pair[index] = replace(pair[index], depth_profile=DepthProfile.constant(-1, pair[index].depth_profile.z_bottom))
    assert len(check_overlap(pair).errors) == 1


@pytest.mark.parametrize("index", [0, 1])
def test_pocket_floor_hole_with_varying_depth_keeps_conservative_overlap_check(index):
    from dataclasses import replace

    pair = [_floor_pocket(), _floor_hole()]
    pair[index] = replace(
        pair[index], depth_profile=DepthProfile.linear_gradient(0, pair[index].depth_profile.z_bottom, 0)
    )
    assert len(check_overlap(pair).errors) == 1


@pytest.mark.parametrize("index", [0, 1])
def test_modified_pocket_floor_hole_keeps_conservative_overlap_check(index):
    from dataclasses import replace

    from ir.removal_intent import EdgeTreatment

    pair = [_floor_pocket(), _floor_hole()]
    pair[index] = replace(
        pair[index], constraints=Constraints(edge_treatment=EdgeTreatment(type="allowance", finish_allowance_mm=2))
    )
    assert len(check_overlap(pair).errors) == 1


@pytest.mark.parametrize("shape", ["Polygon", "unknown"])
def test_pocket_floor_containment_requires_supported_geometry(shape):
    from dataclasses import replace

    pocket = replace(_floor_pocket(), shape=shape)
    assert len(check_overlap([pocket, _floor_hole()]).errors) == 1


@pytest.mark.parametrize("thickness", [19, 25])
def test_through_hole_in_a_pocket_uses_the_sheet_thickness(thickness):
    from adapters.ast_to_removal import ast_to_removal_intents
    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    ast = resolve_layout(
        parse_pml_yaml(f"""Sheet:
  working_width: 200mm
  working_height: 160mm
  thickness: {thickness}mm
children:
  - Pocket:
      depth: 3mm
  - Circle:
      id: mount
      diameter: 6mm
      at:
        x: 100mm
        y: 80mm
      feature:
        type: hole
        depth: through
""")
    )
    intents = ast_to_removal_intents(ast)
    assert len(intents) == 2
    hole = next(i for i in intents if i.hint_type == "hole")
    assert hole.depth_profile.z_bottom == -thickness
    assert check_overlap(intents).is_valid()


def test_validation_result_basic():
    result = ValidationResult()

    assert result.is_valid()
    assert not result.has_issues()
    assert result.summary() == "Validation passed with no issues"

    result.add_error("Test error", region_id="test_1")
    assert not result.is_valid()
    assert result.has_issues()
    assert len(result.errors) == 1
    assert result.errors[0].message == "Test error"
    assert result.errors[0].region_id == "test_1"


def test_validation_result_multiple_issue_types():
    result = ValidationResult()

    result.add_error("Error 1")
    result.add_error("Error 2")
    result.add_warning("Warning 1")
    result.add_suggestion("Suggestion 1")

    assert not result.is_valid()
    assert result.has_issues()
    assert len(result.errors) == 2
    assert len(result.warnings) == 1
    assert len(result.suggestions) == 1
    assert "2 error(s)" in result.summary()
    assert "1 warning(s)" in result.summary()
    assert "1 suggestion(s)" in result.summary()


def test_check_overlap_no_overlap():
    intent_a = _make_intent(
        region_id="pocket_a",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )

    intent_b = _make_intent(
        region_id="pocket_b",
        bounds=Bounds2D(x_min=20.0, x_max=30.0, y_min=0.0, y_max=10.0),
    )

    result = check_overlap([intent_a, intent_b])
    assert result.is_valid()
    assert len(result.errors) == 0


def test_check_overlap_xy_overlap():
    intent_a = _make_intent(
        region_id="pocket_a",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )

    intent_b = _make_intent(
        region_id="pocket_b",
        bounds=Bounds2D(x_min=5.0, x_max=15.0, y_min=5.0, y_max=15.0),
    )

    result = check_overlap([intent_a, intent_b])
    assert not result.is_valid()
    assert len(result.errors) == 1
    assert "pocket_a" in result.errors[0].message
    assert "pocket_b" in result.errors[0].message


def _clipped_groove(angle):
    from shapely.affinity import rotate
    from shapely.geometry import box

    return rotate(box(-150, -3.175, 150, 3.175), angle, origin=(0, 0)).intersection(box(-60, -80, 60, 80))


def _polygon_pocket(polygon, name):
    return pocket_hint_to_removal_intent(
        {
            "id": name,
            "shape": "Polygon",
            "center_xy_mm": [200, 200],
            "geometry": {"points": list(polygon.exterior.coords)[:-1]},
            "depth_mm": 3,
        }
    )


@pytest.mark.parametrize("rotation", [0, 17, 45, 72, 90, 135])
def test_perpendicular_clipped_pockets_are_independent_of_sheet_rotation(rotation):
    from shapely.affinity import rotate

    a = rotate(_clipped_groove(45), rotation, origin=(0, 0))
    b = rotate(_clipped_groove(135), rotation, origin=(0, 0))
    assert check_overlap([_polygon_pocket(a, "a"), _polygon_pocket(b, "b")]).is_valid()


@pytest.mark.parametrize("other_angle", [45, 120, 134.999])
def test_parallel_and_oblique_pocket_intersections_still_reported(other_angle):
    a = _polygon_pocket(_clipped_groove(45), "a")
    b = _polygon_pocket(_clipped_groove(other_angle), "b")
    assert len(check_overlap([a, b]).errors) == 1


def test_square_pockets_have_no_dominant_groove_axis():
    from shapely.affinity import rotate
    from shapely.geometry import box

    square = rotate(box(-20, -20, 20, 20), 45, origin=(0, 0))
    assert len(check_overlap([_polygon_pocket(square, "a"), _polygon_pocket(square, "b")]).errors) == 1


def test_nonconvex_pocket_shapes_are_not_classified_as_rotated_grooves():
    from shapely.affinity import rotate
    from shapely.geometry import box

    notched = box(-70, -4, 70, 4).difference(box(40, 0, 50, 5))
    a = _polygon_pocket(rotate(notched, 45, origin=(0, 0)), "a")
    b = _polygon_pocket(rotate(notched, 135, origin=(0, 0)), "b")
    assert len(check_overlap([a, b]).errors) == 1


@pytest.mark.parametrize("modifier", ["allowance", "dogbone"])
def test_rotated_grooves_with_boundary_modifiers_remain_conservative(modifier):
    from dataclasses import replace

    from ir.removal_intent import EdgeTreatment
    from layout_ast.layout import DogboneSpec

    a = _polygon_pocket(_clipped_groove(45), "a")
    b = _polygon_pocket(_clipped_groove(135), "b")
    if modifier == "allowance":
        a = replace(a, constraints=Constraints(edge_treatment=EdgeTreatment(type="allowance", finish_allowance_mm=-1)))
    else:
        a = replace(a, dogbone=DogboneSpec())
    assert len(check_overlap([a, b]).errors) == 1


def test_empty_pocket_region_has_no_groove_axis():
    from dataclasses import replace

    a = replace(
        _make_intent(
            "empty",
            Bounds2D(150, 250, 150, 250),
            hint_type="pocket",
            constraints=Constraints(islands=(Island(Bounds2D(150, 250, 150, 250)),)),
        ),
        shape="Rect",
    )
    b = _polygon_pocket(_clipped_groove(135), "b")
    assert len(check_overlap([a, b]).errors) == 1


def test_diamond_lattice_pockets_validate_without_dropping_features():
    from adapters.ast_to_removal import ast_to_removal_intents
    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    ast = resolve_layout(
        parse_pml_yaml("""Sheet:
  working_width: 240mm
  working_height: 340mm
  thickness: 19mm
children:
  - Lines: {angle: 45, spacing: 40mm, width: 6.35mm, depth: 3mm}
  - Lines: {angle: 135, spacing: 40mm, width: 6.35mm, depth: 3mm}
""")
    )
    intents = ast_to_removal_intents(ast)
    assert len(intents) == 22
    assert check_overlap(intents).is_valid()


def _profile_intent(name, shape, geometry, center, side):
    return profile_hint_to_removal_intent(
        {"id": name, "shape": shape, "geometry": geometry, "center_xy_mm": center, "side": side, "depth_mm": 19},
        sheet_thickness_mm=19,
    )


def _edge_intent(reference, spec, depth):
    from dataclasses import replace

    return replace(
        reference,
        region_id="edge_" + reference.region_id,
        hint_type=spec.to_dict()["type"],
        edge_feature=spec,
        depth_profile=DepthProfile.constant(0, -depth),
    )


@pytest.mark.parametrize("side", ["outside", "inside"])
def test_profile_and_its_chamfer_are_compatible_edge_operations(side):
    from ir.removal_intent import ChamferSpec

    profile = _profile_intent("part", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], side)
    edge = _edge_intent(profile, ChamferSpec(5, 45), 5)
    assert check_overlap([profile, edge]).is_valid()
    assert check_overlap([edge, profile]).is_valid()


def test_profile_and_its_roundover_are_compatible_independently_of_tool_availability():
    from ir.removal_intent import RoundoverSpec

    profile = _profile_intent("part", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    assert check_overlap([profile, _edge_intent(profile, RoundoverSpec(6), 6)]).is_valid()


def test_chamfer_envelope_inside_outer_profile_does_not_conflict():
    from ir.removal_intent import ChamferSpec

    outer = _profile_intent("outer", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    inner = _profile_intent("inner", "Rect", {"w_mm": 60, "h_mm": 40}, [150, 150], "inside")
    edge = _edge_intent(inner, ChamferSpec(5, 45), 5)
    assert check_overlap([outer, inner, edge]).is_valid()


@pytest.mark.parametrize("width", [5, 6])
def test_chamfer_envelope_touching_or_crossing_outer_boundary_still_reports(width):
    from ir.removal_intent import ChamferSpec

    outer = _profile_intent("outer", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    reference = _profile_intent("edge", "Rect", {"w_mm": 40, "h_mm": 40}, [205, 150], "inside")
    assert len(check_overlap([outer, _edge_intent(reference, ChamferSpec(width, 45), width)]).errors) == 1


def test_bevel_overlap_remains_unresolved_by_chamfer_compatibility():
    from ir.removal_intent import BevelSpec

    profile = _profile_intent("part", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    assert len(check_overlap([profile, _edge_intent(profile, BevelSpec(5, 45, 2), 5)]).errors) == 1


def test_full_depth_chamfer_is_not_exempt_from_profile_overlap():
    from ir.removal_intent import ChamferSpec

    profile = _profile_intent("part", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    assert len(check_overlap([profile, _edge_intent(profile, ChamferSpec(19, 45), 19)]).errors) == 1


def test_chamfer_validation_uses_the_complementary_included_tool_angle():
    from ir.removal_intent import ChamferSpec
    from validation.removal_checks import check_edge_feature

    reference = _profile_intent("edge", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    edge = _edge_intent(reference, ChamferSpec(2, 30), 2 / 3**0.5)
    result = check_edge_feature(edge, 19, available_v_angles=[120])
    assert not result.has_issues()


def test_roundover_with_opposite_retained_side_remains_an_overlap():
    from dataclasses import replace

    from ir.removal_intent import RoundoverSpec

    profile = _profile_intent("part", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "inside")
    edge = replace(_edge_intent(profile, RoundoverSpec(6), 6), side="outside")
    assert len(check_overlap([profile, edge]).errors) == 1


def test_chamfer_containment_uses_the_actual_concave_part():
    from ir.removal_intent import ChamferSpec

    profile = _profile_intent(
        "part", "Polygon", {"points": [[0, 0], [100, 0], [100, 30], [30, 30], [30, 100], [0, 100]]}, [50, 50], "outside"
    )
    reference = _profile_intent("edge", "Rect", {"w_mm": 20, "h_mm": 80}, [85, 100], "inside")
    assert len(check_overlap([profile, _edge_intent(reference, ChamferSpec(5, 45), 5)]).errors) == 1


def test_edge_starting_below_the_surface_keeps_conservative_overlap_check():
    from dataclasses import replace

    from ir.removal_intent import ChamferSpec

    profile = _profile_intent("part", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    edge = replace(_edge_intent(profile, ChamferSpec(5, 45), 5), depth_profile=DepthProfile.constant(-2, -7))
    assert len(check_overlap([profile, edge]).errors) == 1


@pytest.mark.parametrize("shape, geometry", [("Rect", {"w_mm": 40, "h_mm": 30}), ("Circle", {"diameter_mm": 40})])
@pytest.mark.parametrize("reverse", [False, True])
def test_inside_profile_cutouts_do_not_conflict_with_the_containing_outside_profile(shape, geometry, reverse):
    outer = _profile_intent("outer", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    inner = _profile_intent("inner", shape, geometry, [150, 150], "inside")
    pair = [inner, outer] if reverse else [outer, inner]
    assert check_overlap(pair).is_valid()


def test_nested_polygon_profiles_use_actual_outlines():
    outer = _profile_intent(
        "outer", "Polygon", {"points": [[-80, -60], [80, -60], [60, 60], [-60, 60]]}, [150, 150], "outside"
    )
    inner = _profile_intent(
        "inner", "Polygon", {"points": [[-30, -20], [30, -20], [20, 20], [-20, 20]]}, [150, 150], "inside"
    )
    assert check_overlap([outer, inner]).is_valid()


@pytest.mark.parametrize("side", ["outside", "on"])
def test_nested_profile_with_wrong_cut_side_is_not_exempt(side):
    outer = _profile_intent("outer", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    inner = _profile_intent("inner", "Rect", {"w_mm": 40, "h_mm": 30}, [150, 150], side)
    assert len(check_overlap([outer, inner]).errors) == 1


@pytest.mark.parametrize("gap, valid", [(-1, False), (0, False), (1e-7, False), (0.01, True)])
def test_inside_profile_requires_a_positive_retained_wall(gap, valid):
    outer = _profile_intent("outer", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    inner = _profile_intent("inner", "Rect", {"w_mm": 40, "h_mm": 30}, [210 - gap, 150], "inside")
    assert check_overlap([outer, inner]).is_valid() == valid


def test_nested_profiles_are_not_inferred_from_bounding_boxes_of_concave_parts():
    outer = _profile_intent(
        "outer",
        "Polygon",
        {"points": [[0, 0], [100, 0], [100, 30], [30, 30], [30, 100], [0, 100]]},
        [50, 50],
        "outside",
    )
    inner = _profile_intent("inner", "Rect", {"w_mm": 20, "h_mm": 80}, [85, 100], "inside")
    assert len(check_overlap([outer, inner]).errors) == 1


@pytest.mark.parametrize("modified", ["outer", "inner"])
def test_nested_profiles_with_allowances_keep_conservative_check(modified):
    from dataclasses import replace

    from ir.removal_intent import EdgeTreatment

    outer = _profile_intent("outer", "Rect", {"w_mm": 160, "h_mm": 120}, [150, 150], "outside")
    inner = _profile_intent("inner", "Rect", {"w_mm": 40, "h_mm": 30}, [150, 150], "inside")
    constraints = Constraints(edge_treatment=EdgeTreatment(type="allowance", finish_allowance_mm=-80))
    if modified == "outer":
        outer = replace(outer, constraints=constraints)
    else:
        inner = replace(inner, constraints=constraints)
    assert len(check_overlap([outer, inner]).errors) == 1


def test_inside_profile_near_circle_corner_is_not_exempt_using_outer_bounds():
    outer = _profile_intent("outer", "Circle", {"diameter_mm": 100}, [150, 150], "outside")
    inner = _profile_intent("inner", "Rect", {"w_mm": 40, "h_mm": 40}, [175, 175], "inside")
    assert len(check_overlap([outer, inner]).errors) == 1


def test_nested_profile_missing_outer_polygon_geometry_is_not_exempt():
    outer = _profile_intent("outer", "Polygon", {}, [150, 150], "outside")
    inner = _profile_intent("inner", "Rect", {"w_mm": 0.2, "h_mm": 0.2}, [150, 150], "inside")
    assert len(check_overlap([outer, inner]).errors) == 1


def _engraving_trace(region_id, points):
    return engrave_hint_to_removal_intent(
        {
            "id": region_id,
            "shape": "Polyline",
            "geometry": {"points": points},
            "center_xy_mm": [120, 80],
            "depth_mm": 0.8,
        }
    )


def test_overlap_disjoint_engraving_borders_with_nested_bounds():
    outer = _engraving_trace("outer", [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)])
    inner = _engraving_trace("inner", [(10, 10), (90, 10), (90, 70), (10, 70), (10, 10)])
    assert not check_overlap([outer, inner]).is_valid()
    assert check_overlap([outer, inner], engrave_tool_diameter_mm=3).is_valid()


@pytest.mark.parametrize("diameter, valid", [(1, True), (3, False), (4, False)])
def test_overlap_parallel_engraving_paths_accounts_for_full_cutter(diameter, valid):
    a = _engraving_trace("a", [(0, 0), (100, 0), (100, 80)])
    b = _engraving_trace("b", [(10, 3), (97, 3), (97, 70)])
    result = check_overlap([a, b], engrave_tool_diameter_mm=diameter)
    assert result.is_valid() == valid


def test_overlap_crossing_engraving_paths_still_reported():
    a = _engraving_trace("a", [(0, 0), (50, 50)])
    b = _engraving_trace("b", [(0, 50), (50, 0)])
    assert len(check_overlap([a, b], engrave_tool_diameter_mm=1).errors) == 1


@pytest.mark.parametrize(
    "shape, geometry, center",
    [
        ("Line", {"start": [10, 20], "end": [90, 60]}, [120, 80]),
        ("Rect", {"w_mm": 60, "h_mm": 40}, [170, 120]),
    ],
)
def test_overlap_engraving_shapes_share_positioned_planner_paths(shape, geometry, center):
    outer = _engraving_trace("outer", [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)])
    inner = engrave_hint_to_removal_intent(
        {"id": "inner", "shape": shape, "geometry": geometry, "center_xy_mm": center, "depth_mm": 0.8}
    )
    assert not check_overlap([outer, inner]).is_valid()
    assert check_overlap([outer, inner], engrave_tool_diameter_mm=3).is_valid()


def test_overlap_ramped_engraving_follows_the_declared_path():
    from dataclasses import replace

    outer = _engraving_trace("outer", [(0, 0), (0, 50), (50, 50)])
    inner = _engraving_trace("inner", [(25, 10), (25, 40)])
    assert check_overlap([outer, inner], engrave_tool_diameter_mm=1).is_valid()
    ramped = replace(outer, ramp_mm=5)
    assert check_overlap([ramped, inner], engrave_tool_diameter_mm=1).is_valid()


def test_overlap_unknown_engraving_geometry_keeps_bounds_check():
    a = _make_intent("a", Bounds2D(0, 100, 0, 100), hint_type="engrave")
    b = _make_intent("b", Bounds2D(10, 90, 10, 90), hint_type="engrave")
    assert not check_overlap([a, b], engrave_tool_diameter_mm=1).is_valid()


@pytest.mark.parametrize("diameter", [0, -1, float("inf"), float("nan")])
def test_overlap_rejects_invalid_engraving_tool_diameter(diameter):
    with pytest.raises(ValueError, match="engrave_tool_diameter_mm"):
        check_overlap([], engrave_tool_diameter_mm=diameter)


def test_check_overlap_different_z_levels():
    intent_a = _make_intent(
        region_id="pocket_shallow",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-3.0,
    )

    intent_b = _make_intent(
        region_id="pocket_deep",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=-4.0,
        z_bottom=-8.0,
    )

    result = check_overlap([intent_a, intent_b])
    assert result.is_valid()


def _ring_pocket():
    return pocket_hint_to_removal_intent(
        {
            "id": "ring",
            "shape": "Polygon",
            "center_xy_mm": [120, 80],
            "geometry": {
                "points": [[-10, -10], [110, -10], [110, 110], [-10, 110]],
                "holes": [[[0, 0], [0, 100], [100, 100], [100, 0]]],
            },
            "depth_mm": 3,
        }
    )


@pytest.mark.parametrize("gap, valid", [(10, True), (0, False), (-2, False), (1e-7, False)])
def test_overlap_pocket_within_ring_hole_uses_material_regions(gap, valid):
    center = pocket_hint_to_removal_intent(
        {
            "id": "center",
            "shape": "Rect",
            "center_xy_mm": [170, 130],
            "geometry": {"w_mm": 100 - 2 * gap, "h_mm": 100 - 2 * gap},
            "depth_mm": 6,
        }
    )
    assert check_overlap([_ring_pocket(), center]).is_valid() == valid


def test_overlap_pockets_respect_preserved_island_material():
    from dataclasses import replace

    outer = _make_intent(
        "outer",
        Bounds2D(0, 100, 0, 100),
        hint_type="pocket",
        constraints=Constraints(islands=(Island(Bounds2D(20, 80, 20, 80)),)),
    )
    outer = replace(outer, shape="Rect")
    inner = _make_intent("inner", Bounds2D(30, 70, 30, 70), hint_type="pocket")
    assert check_overlap([outer, inner]).is_valid()


def test_overlap_pocket_with_missing_geometry_remains_conservative():
    unknown = _make_intent("unknown", Bounds2D(100, 240, 60, 200), hint_type="pocket")
    assert not check_overlap([_ring_pocket(), unknown]).is_valid()


@pytest.mark.parametrize("extra", ["allowance", "dogbone"])
def test_overlap_pocket_boundary_modifiers_keep_conservative_check(extra):
    from dataclasses import replace

    from ir.removal_intent import EdgeTreatment
    from layout_ast.layout import DogboneSpec

    ring = _ring_pocket()
    inner = _make_intent("inner", Bounds2D(130, 210, 90, 170), hint_type="pocket")
    assert check_overlap([ring, inner]).is_valid()
    if extra == "allowance":
        ring = replace(
            ring, constraints=Constraints(edge_treatment=EdgeTreatment(type="allowance", finish_allowance_mm=-20))
        )
    else:
        ring = replace(ring, dogbone=DogboneSpec())
    assert not check_overlap([ring, inner]).is_valid()


def test_check_depth_feasibility_valid():
    intent = _make_intent(
        region_id="pocket_valid",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-6.0,
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()
    assert len(result.errors) == 0


def test_check_depth_feasibility_inverted_z():
    try:
        _make_intent(
            region_id="pocket_inverted",
            bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
            z_top=-6.0,
            z_bottom=0.0,
        )
        raise AssertionError("Expected ValueError for inverted Z values")
    except ValueError as e:
        assert "z_bottom" in str(e) and "z_top" in str(e)


def test_check_depth_feasibility_too_deep():
    intent = _make_intent(
        region_id="pocket_deep",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-15.0,
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()
    assert len(result.warnings) == 1
    assert "deeper than material thickness" in result.warnings[0].message


def test_check_depth_feasibility_very_shallow():
    intent = _make_intent(
        region_id="engrave_shallow",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-0.2,
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()
    assert len(result.suggestions) == 1
    assert "Very shallow cut" in result.suggestions[0].message


def test_check_toolability_no_tools():
    intent = _make_intent(
        region_id="pocket_normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )

    result = check_toolability(intent, available_tools=None)
    assert result.is_valid()
    assert len(result.warnings) == 0


def test_check_toolability_very_small_feature():
    intent = _make_intent(
        region_id="hole_tiny",
        bounds=Bounds2D(x_min=0.0, x_max=0.5, y_min=0.0, y_max=0.5),
    )

    result = check_toolability(intent, available_tools=None)
    assert result.is_valid()
    assert len(result.warnings) == 1
    assert "Very small feature" in result.warnings[0].message


def test_check_toolability_with_suitable_tools():
    intent = _make_intent(
        region_id="pocket_normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )

    tools = [
        {"diameter_mm": 3.175, "flutes": 2},
        {"diameter_mm": 6.35, "flutes": 2},
    ]

    result = check_toolability(intent, available_tools=tools)
    assert result.is_valid()
    assert len(result.errors) == 0


def test_check_toolability_no_suitable_tools():
    intent = _make_intent(
        region_id="pocket_tiny",
        bounds=Bounds2D(x_min=0.0, x_max=1.5, y_min=0.0, y_max=1.5),
    )

    tools = [
        {"diameter_mm": 3.175, "flutes": 2},
        {"diameter_mm": 6.35, "flutes": 2},
    ]

    result = check_toolability(intent, available_tools=tools)
    assert not result.is_valid()
    assert len(result.errors) == 1
    assert "No available tool" in result.errors[0].message


def test_check_toolability_limited_tools():
    intent = _make_intent(
        region_id="pocket_small",
        bounds=Bounds2D(x_min=0.0, x_max=4.0, y_min=0.0, y_max=4.0),
    )

    tools = [
        {"diameter_mm": 1.5, "flutes": 2},
        {"diameter_mm": 3.175, "flutes": 2},
        {"diameter_mm": 6.35, "flutes": 2},
        {"diameter_mm": 12.7, "flutes": 4},
    ]

    result = check_toolability(intent, available_tools=tools)
    assert result.is_valid()
    assert len(result.suggestions) == 1
    assert "Limited tool options" in result.suggestions[0].message


def test_check_overlap_three_pairwise():
    intent_a = _make_intent(
        region_id="a",
        bounds=Bounds2D(x_min=0.0, x_max=20.0, y_min=0.0, y_max=20.0),
    )
    intent_b = _make_intent(
        region_id="b",
        bounds=Bounds2D(x_min=10.0, x_max=30.0, y_min=10.0, y_max=30.0),
    )
    intent_c = _make_intent(
        region_id="c",
        bounds=Bounds2D(x_min=15.0, x_max=35.0, y_min=0.0, y_max=20.0),
    )
    result = check_overlap([intent_a, intent_b, intent_c])
    assert not result.is_valid()
    assert len(result.errors) >= 2


def test_check_overlap_touching_edges_no_overlap():
    intent_a = _make_intent(
        region_id="left",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )
    intent_b = _make_intent(
        region_id="right",
        bounds=Bounds2D(x_min=10.0, x_max=20.0, y_min=0.0, y_max=10.0),
    )
    result = check_overlap([intent_a, intent_b])
    assert result.is_valid()


def test_check_overlap_zero_width_inside_detects_overlap():
    intent_a = _make_intent(
        region_id="normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )
    intent_b = _make_intent(
        region_id="zero_w",
        bounds=Bounds2D(x_min=5.0, x_max=5.0, y_min=0.0, y_max=10.0),
    )
    result = check_overlap([intent_a, intent_b])
    assert not result.is_valid()


def _through_profile() -> RemovalIntent:
    return _make_intent(
        region_id="profile_panel",
        bounds=Bounds2D(x_min=0.0, x_max=200.0, y_min=0.0, y_max=200.0),
        z_bottom=-12.0,
        hint_type="profile",
        side="outside",
    )


def test_check_overlap_engrave_inside_profile_exempt():
    engrave = _make_intent(
        region_id="engrave_mark",
        bounds=Bounds2D(x_min=50.0, x_max=60.0, y_min=50.0, y_max=60.0),
        z_bottom=-0.5,
        hint_type="engrave",
    )
    assert check_overlap([_through_profile(), engrave]).is_valid()


def test_check_overlap_engrave_past_profile_reported():
    engrave = _make_intent(
        region_id="engrave_mark",
        bounds=Bounds2D(x_min=190.0, x_max=210.0, y_min=50.0, y_max=60.0),
        z_bottom=-0.5,
        hint_type="engrave",
    )
    result = check_overlap([_through_profile(), engrave])
    assert len(result.errors) == 1


def test_check_overlap_zero_width_outside_no_overlap():
    intent_a = _make_intent(
        region_id="normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )
    intent_b = _make_intent(
        region_id="zero_w_outside",
        bounds=Bounds2D(x_min=15.0, x_max=15.0, y_min=0.0, y_max=10.0),
    )
    result = check_overlap([intent_a, intent_b])
    assert result.is_valid()


def test_check_depth_feasibility_zero_depth():
    intent = _make_intent(
        region_id="zero_depth",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=0.0,
    )
    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()


def test_check_toolability_all_tools_too_large():
    intent = _make_intent(
        region_id="tiny_slot",
        bounds=Bounds2D(x_min=0.0, x_max=2.0, y_min=0.0, y_max=0.5),
    )
    tools = [
        {"diameter_mm": 3.175, "flutes": 2},
        {"diameter_mm": 6.35, "flutes": 2},
        {"diameter_mm": 12.7, "flutes": 4},
    ]
    result = check_toolability(intent, available_tools=tools)
    assert not result.is_valid()
    assert len(result.errors) == 1


def test_check_toolpath_clearance_insufficient_gap():
    intent_a = _make_intent(
        region_id="profile_a",
        bounds=Bounds2D(x_min=0.0, x_max=50.0, y_min=0.0, y_max=50.0),
        hint_type="profile",
        side="outside",
    )
    intent_b = _make_intent(
        region_id="profile_b",
        bounds=Bounds2D(x_min=52.0, x_max=100.0, y_min=0.0, y_max=50.0),
        hint_type="profile",
        side="outside",
    )
    result = check_toolpath_clearance([intent_a, intent_b], tool_diameter_mm=6.35)
    assert not result.is_valid()
    assert "clearance" in result.errors[0].message.lower()


def test_check_toolpath_clearance_sufficient_gap():
    intent_a = _make_intent(
        region_id="profile_a",
        bounds=Bounds2D(x_min=0.0, x_max=50.0, y_min=0.0, y_max=50.0),
        hint_type="profile",
        side="outside",
    )
    intent_b = _make_intent(
        region_id="profile_b",
        bounds=Bounds2D(x_min=60.0, x_max=100.0, y_min=0.0, y_max=50.0),
        hint_type="profile",
        side="outside",
    )
    result = check_toolpath_clearance([intent_a, intent_b], tool_diameter_mm=6.35)
    assert result.is_valid()


@pytest.mark.parametrize(
    ("x_gap", "y_gap", "expected_gap", "valid"),
    [(70, 1, 70.00714249, True), (5, 5, 7.07106781, True), (3, 4, 5.0, False), (0, 4, 4.0, False)],
)
def test_check_toolpath_clearance_diagonal_distance(x_gap, y_gap, expected_gap, valid):
    a = _make_intent("a", Bounds2D(0, 50, 0, 50), hint_type="profile", side="outside")
    b = _make_intent(
        "b", Bounds2D(50 + x_gap, 100 + x_gap, 50 + y_gap, 100 + y_gap), hint_type="profile", side="outside"
    )

    for pair in ([a, b], [b, a]):
        result = check_toolpath_clearance(pair, tool_diameter_mm=6.35)
        assert result.is_valid() == valid
        if not valid:
            assert result.errors[0].metadata["gap_mm"] == pytest.approx(expected_gap)


def test_check_working_area_bounds_inside():
    intent = _make_intent(
        region_id="inside",
        bounds=Bounds2D(x_min=10.0, x_max=90.0, y_min=10.0, y_max=90.0),
    )
    result = check_working_area_bounds([intent], working_width_mm=100.0, working_height_mm=100.0)
    assert result.is_valid()


def test_check_working_area_bounds_exceeds_right():
    intent = _make_intent(
        region_id="too_wide",
        bounds=Bounds2D(x_min=10.0, x_max=110.0, y_min=10.0, y_max=90.0),
    )
    result = check_working_area_bounds([intent], working_width_mm=100.0, working_height_mm=100.0)
    assert not result.is_valid()
    assert any("right" in e.metadata.get("boundary_exceeded", "") for e in result.errors)


def test_check_working_area_bounds_exceeds_left():
    intent = _make_intent(
        region_id="neg_x",
        bounds=Bounds2D(x_min=-5.0, x_max=50.0, y_min=10.0, y_max=90.0),
    )
    result = check_working_area_bounds([intent], working_width_mm=100.0, working_height_mm=100.0)
    assert not result.is_valid()
    assert any("left" in e.metadata.get("boundary_exceeded", "") for e in result.errors)


def test_check_working_area_bounds_outside_profile_offset():
    intent = _make_intent(
        region_id="outside_prof",
        bounds=Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=100.0),
        side="outside",
    )
    result = check_working_area_bounds(
        [intent],
        working_width_mm=100.0,
        working_height_mm=100.0,
        tool_radius_mm=3.175,
    )
    assert not result.is_valid()


def test_check_working_area_bounds_multiple_violations():
    intent = _make_intent(
        region_id="out_of_bounds",
        bounds=Bounds2D(x_min=-5.0, x_max=110.0, y_min=-5.0, y_max=110.0),
    )
    result = check_working_area_bounds([intent], working_width_mm=100.0, working_height_mm=100.0)
    assert not result.is_valid()
    assert len(result.errors) == 4


def test_check_overlap_with_keepouts():
    keepout_bounds = Bounds2D(x_min=20.0, x_max=40.0, y_min=20.0, y_max=40.0)
    keepout = KeepoutRegion(bounds=keepout_bounds, reason="clamp")
    constraints = Constraints(
        tabs=None,
        keepouts=(keepout,),
        islands=(),
        tolerance_mm=0.1,
        safe_z_mm=5.0,
    )
    intent = _make_intent(
        region_id="pocket_with_keepout",
        bounds=Bounds2D(x_min=0.0, x_max=60.0, y_min=0.0, y_max=60.0),
        constraints=constraints,
    )
    result = check_overlap([intent])
    assert result.is_valid()


def test_check_overlap_with_islands():
    island_bounds = Bounds2D(x_min=30.0, x_max=50.0, y_min=30.0, y_max=50.0)
    island = Island(bounds=island_bounds, label="raised_area")
    constraints = Constraints(
        tabs=None,
        keepouts=(),
        islands=(island,),
        tolerance_mm=0.1,
        safe_z_mm=5.0,
    )
    intent = _make_intent(
        region_id="pocket_with_island",
        bounds=Bounds2D(x_min=0.0, x_max=80.0, y_min=0.0, y_max=80.0),
        constraints=constraints,
    )
    result = check_overlap([intent])
    assert result.is_valid()


def _face_intent(
    region_id: str,
    bounds: Bounds2D,
    depth_mm: float,
    face: str,
    hint_type: str = "pocket",
    mode: str = "constant",
) -> RemovalIntent:
    if mode == "linear_gradient":
        profile = DepthProfile.linear_gradient(z_top=0.0, z_bottom=-depth_mm, direction_deg=0.0)
    else:
        profile = DepthProfile.constant(z_top=0.0, z_bottom=-depth_mm)
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=profile,
        hint_type=hint_type,
        face=face,
    )


class TestCrossFaceValidation:
    def test_overlap_check_skips_cross_face_pairs(self) -> None:
        front = _face_intent("front_pocket", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "front")
        back = _face_intent("back_pocket", Bounds2D(10.0, 30.0, 10.0, 30.0), 5.0, "back")

        assert not check_overlap([front, back]).has_issues()

    def test_same_face_overlap_still_errors(self) -> None:
        a = _face_intent("back_a", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "back")
        b = _face_intent("back_b", Bounds2D(10.0, 30.0, 10.0, 30.0), 5.0, "back")

        assert check_overlap([a, b]).has_issues()

    def test_cross_face_web_error_on_breach(self) -> None:
        front = _face_intent("front_pocket", Bounds2D(0.0, 40.0, 0.0, 40.0), 5.0, "front")
        back = _face_intent("back_cup", Bounds2D(10.0, 30.0, 10.0, 30.0), 12.5, "back")

        result = check_cross_face_web([front, back], sheet_thickness_mm=19.0, min_web_mm=3.0)

        assert result.has_issues()
        assert "web breach" in result.errors[0].message

    def test_cross_face_web_passes_at_exact_boundary(self) -> None:
        front = _face_intent("front_pocket", Bounds2D(0.0, 40.0, 0.0, 40.0), 3.5, "front")
        back = _face_intent("back_cup", Bounds2D(10.0, 30.0, 10.0, 30.0), 12.5, "back")

        assert not check_cross_face_web([front, back], sheet_thickness_mm=19.0, min_web_mm=3.0).has_issues()

    def test_cross_face_web_ignores_non_overlapping_pairs(self) -> None:
        front = _face_intent("front_pocket", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "front")
        back = _face_intent("back_cup", Bounds2D(100.0, 140.0, 0.0, 40.0), 12.5, "back")

        assert not check_cross_face_web([front, back], sheet_thickness_mm=19.0, min_web_mm=3.0).has_issues()

    def test_cross_face_web_ignores_profiles(self) -> None:
        profile = _face_intent("door_profile", Bounds2D(0.0, 400.0, 0.0, 600.0), 19.0, "front", hint_type="profile")
        back = _face_intent("back_cup", Bounds2D(10.0, 45.0, 90.0, 125.0), 12.5, "back")

        assert not check_cross_face_web([profile, back], sheet_thickness_mm=19.0, min_web_mm=3.0).has_issues()

    def test_cross_face_web_disabled_at_zero(self) -> None:
        front = _face_intent("front_pocket", Bounds2D(0.0, 40.0, 0.0, 40.0), 10.0, "front")
        back = _face_intent("back_cup", Bounds2D(10.0, 30.0, 10.0, 30.0), 12.5, "back")

        assert not check_cross_face_web([front, back], sheet_thickness_mm=19.0, min_web_mm=0.0).has_issues()

    def test_back_face_gradient_depth_rejected(self) -> None:
        intent = _face_intent("back_gradient", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "back", mode="linear_gradient")

        result = check_back_face_support(intent)

        assert result.has_issues()
        assert "linear_gradient" in result.errors[0].message

    def test_back_face_constant_depth_accepted(self) -> None:
        intent = _face_intent("back_pocket", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "back")

        assert not check_back_face_support(intent).has_issues()

    def test_back_face_profile_type_rejected(self) -> None:
        intent = _face_intent("back_profile", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "back", hint_type="profile")

        result = check_back_face_support(intent)

        assert result.has_issues()
        assert "profile" in result.errors[0].message

    def test_front_intent_skips_back_face_check(self) -> None:
        intent = _face_intent("front_gradient", Bounds2D(0.0, 40.0, 0.0, 40.0), 6.0, "front", mode="linear_gradient")

        assert not check_back_face_support(intent).has_issues()


def test_check_overlap_pocket_inside_profile_exempt():
    profile = _make_intent(
        region_id="profile_panel",
        bounds=Bounds2D(x_min=0.0, x_max=400.0, y_min=0.0, y_max=600.0),
        hint_type="profile",
    )
    pocket = _make_intent(
        region_id="pocket_field",
        bounds=Bounds2D(x_min=50.0, x_max=350.0, y_min=50.0, y_max=550.0),
        hint_type="pocket",
    )

    assert check_overlap([profile, pocket]).is_valid()


def test_check_overlap_pocket_outside_profile_still_errors():
    profile = _make_intent(
        region_id="profile_panel",
        bounds=Bounds2D(x_min=0.0, x_max=400.0, y_min=0.0, y_max=600.0),
        hint_type="profile",
    )
    pocket = _make_intent(
        region_id="pocket_stray",
        bounds=Bounds2D(x_min=350.0, x_max=450.0, y_min=200.0, y_max=300.0),
        hint_type="pocket",
    )

    result = check_overlap([profile, pocket])
    assert not result.is_valid()
    assert "pocket_stray" in result.errors[0].message
