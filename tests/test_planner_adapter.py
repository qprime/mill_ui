from __future__ import annotations

from typing import Any

import pytest

from adapters.ast_to_removal import item_to_removal_intent
from adapters.hints_to_removal import (
    engrave_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    profile_hint_to_removal_intent,
)
from adapters.removal_to_planner import (
    removal_intent_to_hint,
    removal_intents_to_hints,
    removal_intents_to_planner_input,
)
from cam.planner.planner_input import PlannerInput
from layout_ast.layout import Feature, Geometry, Item, Placement

_RING_POINTS = [[-50.0, -50.0], [50.0, -50.0], [50.0, 50.0], [-50.0, 50.0]]
_RING_HOLE = [[-40.0, -40.0], [40.0, -40.0], [40.0, 40.0], [-40.0, 40.0]]


def approx_eq(a, b, rel=1e-6):
    """Check if two values are approximately equal."""
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_roundtrip_profile_through_cut():
    original_hint: dict[str, Any] = {
        "id": "rect_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 50.0},
        "center_xy_mm": (150.0, 75.0),
        "depth_mm": 19.1,
        "side": "outside",
    }

    intent = profile_hint_to_removal_intent(original_hint, sheet_thickness_mm=19.1)

    reconstructed_hint = removal_intent_to_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == original_hint["shape"]
    assert approx_eq(reconstructed_hint["geometry"]["w_mm"], original_hint["geometry"]["w_mm"])
    assert approx_eq(reconstructed_hint["geometry"]["h_mm"], original_hint["geometry"]["h_mm"])
    assert approx_eq(reconstructed_hint["center_xy_mm"][0], original_hint["center_xy_mm"][0])
    assert approx_eq(reconstructed_hint["center_xy_mm"][1], original_hint["center_xy_mm"][1])
    assert approx_eq(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert reconstructed_hint["side"] == original_hint["side"]


def test_roundtrip_profile_with_tabs():
    original_hint = {
        "id": "panel_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 200.0, "h_mm": 150.0},
        "center_xy_mm": (100.0, 75.0),
        "depth_mm": 18.0,
        "side": "outside",
        "tabs": {"count": 6, "height": 3.0, "width_mm": 10.0},
    }

    intent = profile_hint_to_removal_intent(original_hint, sheet_thickness_mm=18.0)
    reconstructed_hint = removal_intent_to_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert approx_eq(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert "tabs" in reconstructed_hint
    assert reconstructed_hint["tabs"]["count"] == 6
    assert approx_eq(reconstructed_hint["tabs"]["height_mm"], 3.0)
    assert approx_eq(reconstructed_hint["tabs"]["width_mm"], 10.0)


def test_roundtrip_profile_inside_cut():
    original_hint = {
        "id": "aperture",
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 30.0},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 12.0,
        "side": "inside",
    }

    intent = profile_hint_to_removal_intent(original_hint, sheet_thickness_mm=12.0)
    reconstructed_hint = removal_intent_to_hint(intent)

    assert reconstructed_hint["side"] == "inside"
    assert approx_eq(reconstructed_hint["depth_mm"], 12.0)


def test_roundtrip_pocket_basic():
    original_hint: dict[str, Any] = {
        "id": "pocket_1",
        "shape": "Rect",
        "geometry": {"w_mm": 80.0, "h_mm": 40.0},
        "center_xy_mm": (100.0, 50.0),
        "depth_mm": 5.0,
    }

    intent = pocket_hint_to_removal_intent(original_hint)
    reconstructed_hint = removal_intent_to_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == original_hint["shape"]
    assert approx_eq(reconstructed_hint["geometry"]["w_mm"], original_hint["geometry"]["w_mm"])
    assert approx_eq(reconstructed_hint["geometry"]["h_mm"], original_hint["geometry"]["h_mm"])
    assert approx_eq(reconstructed_hint["depth_mm"], original_hint["depth_mm"])

    assert "start_depth_mm" not in reconstructed_hint


def test_roundtrip_pocket_with_start_depth():
    original_hint = {
        "id": "stepped_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 60.0, "h_mm": 60.0},
        "center_xy_mm": (75.0, 75.0),
        "depth_mm": 8.0,
        "start_depth_mm": 2.0,
    }

    intent = pocket_hint_to_removal_intent(original_hint)
    reconstructed_hint = removal_intent_to_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert approx_eq(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert approx_eq(reconstructed_hint["start_depth_mm"], original_hint["start_depth_mm"])


def test_roundtrip_hole_circle():
    original_hint: dict[str, Any] = {
        "id": "mounting_hole",
        "shape": "Circle",
        "geometry": {"diameter_mm": 10.0},
        "center_xy_mm": (50.0, 50.0),
        "depth_mm": 12.0,
    }

    intent = hole_hint_to_removal_intent(original_hint)
    reconstructed_hint = removal_intent_to_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == "Circle"
    assert approx_eq(reconstructed_hint["geometry"]["diameter_mm"], original_hint["geometry"]["diameter_mm"])
    assert approx_eq(reconstructed_hint["center_xy_mm"][0], original_hint["center_xy_mm"][0])
    assert approx_eq(reconstructed_hint["center_xy_mm"][1], original_hint["center_xy_mm"][1])
    assert approx_eq(reconstructed_hint["depth_mm"], original_hint["depth_mm"])


def test_batch_conversion_to_hints_structure():
    profile_hint = {
        "id": "outer",
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 50.0},
        "center_xy_mm": (50.0, 25.0),
        "depth_mm": 12.0,
        "side": "outside",
    }

    pocket_hint = {
        "id": "inner_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 30.0, "h_mm": 20.0},
        "center_xy_mm": (50.0, 25.0),
        "depth_mm": 5.0,
    }

    hole_hint = {
        "id": "mount",
        "shape": "Circle",
        "geometry": {"diameter_mm": 6.0},
        "center_xy_mm": (20.0, 20.0),
        "depth_mm": 12.0,
    }

    profile_intent = profile_hint_to_removal_intent(profile_hint, sheet_thickness_mm=12.0)
    pocket_intent = pocket_hint_to_removal_intent(pocket_hint)
    hole_intent = hole_hint_to_removal_intent(hole_hint)

    intents = [profile_intent, pocket_intent, hole_intent]
    hints = removal_intents_to_hints(intents, kerf_width_mm=3.175)

    assert hints["units"] == "mm"
    assert approx_eq(hints["kerf_width_mm"], 3.175)
    assert len(hints["profiles"]) == 1
    assert len(hints["pockets"]) == 1
    assert len(hints["holes"]) == 1
    assert len(hints["engraves"]) == 0

    assert hints["profiles"][0]["id"] == "outer"
    assert hints["profiles"][0]["side"] == "outside"

    assert hints["pockets"][0]["id"] == "inner_pocket"
    assert approx_eq(hints["pockets"][0]["depth_mm"], 5.0)

    assert hints["holes"][0]["id"] == "mount"
    assert approx_eq(hints["holes"][0]["geometry"]["diameter_mm"], 6.0)


def test_geometry_preservation_rect():
    hint: dict[str, Any] = {
        "id": "test_rect",
        "shape": "Rect",
        "geometry": {"w_mm": 123.45, "h_mm": 67.89},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": 10.0,
    }

    intent = pocket_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_hint(intent)

    assert approx_eq(reconstructed["geometry"]["w_mm"], hint["geometry"]["w_mm"], rel=1e-9)
    assert approx_eq(reconstructed["geometry"]["h_mm"], hint["geometry"]["h_mm"], rel=1e-9)
    assert approx_eq(reconstructed["center_xy_mm"][0], hint["center_xy_mm"][0], rel=1e-9)
    assert approx_eq(reconstructed["center_xy_mm"][1], hint["center_xy_mm"][1], rel=1e-9)


def test_geometry_preservation_circle():
    hint: dict[str, Any] = {
        "id": "test_circle",
        "shape": "Circle",
        "geometry": {"diameter_mm": 25.4},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 8.0,
    }

    intent = hole_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_hint(intent)

    assert approx_eq(reconstructed["geometry"]["diameter_mm"], hint["geometry"]["diameter_mm"], rel=1e-9)
    assert approx_eq(reconstructed["center_xy_mm"][0], hint["center_xy_mm"][0], rel=1e-9)
    assert approx_eq(reconstructed["center_xy_mm"][1], hint["center_xy_mm"][1], rel=1e-9)


def test_depth_preservation():
    hint = {
        "id": "deep_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 50.0},
        "center_xy_mm": (25.0, 25.0),
        "depth_mm": 15.75,
        "start_depth_mm": 3.25,
    }

    intent = pocket_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_hint(intent)

    assert approx_eq(reconstructed["depth_mm"], hint["depth_mm"], rel=1e-9)
    assert approx_eq(reconstructed["start_depth_mm"], hint["start_depth_mm"], rel=1e-9)


def test_metadata_fields_preserved():
    hint = {
        "id": "custom_id_123",
        "shape": "Rect",
        "geometry": {"w_mm": 40.0, "h_mm": 30.0},
        "center_xy_mm": (20.0, 15.0),
        "depth_mm": 6.0,
        "side": "on",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)
    reconstructed = removal_intent_to_hint(intent)

    assert reconstructed["id"] == hint["id"]
    assert reconstructed["shape"] == hint["shape"]
    assert reconstructed["side"] == hint["side"]


def test_roundtrip_pocket_polygon_holes():
    hint: dict[str, Any] = {
        "id": "ring",
        "shape": "Polygon",
        "geometry": {"points": _RING_POINTS, "holes": [_RING_HOLE]},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 2.0,
    }
    expected_hole = tuple((x, y) for x, y in _RING_HOLE)

    intent = pocket_hint_to_removal_intent(hint)
    assert intent.shape_geometry.holes == (expected_hole,)

    reconstructed = removal_intent_to_hint(intent)
    assert reconstructed["geometry"]["holes"] == [_RING_HOLE]

    restored = PlannerInput.from_hints_dict(removal_intents_to_planner_input([intent]).to_hints_dict())
    assert restored.pockets[0].geometry.geometry.holes == (expected_hole,)


def test_polygon_without_holes_keeps_holes_none():
    hint: dict[str, Any] = {
        "id": "square",
        "shape": "Polygon",
        "geometry": {"points": _RING_POINTS, "holes": []},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 2.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.shape_geometry.holes is None
    assert "holes" not in intent.to_dict()["shape_geometry"]
    assert "holes" not in removal_intent_to_hint(intent)["geometry"]


_TRIANGLE = [[-20.0, -10.0], [40.0, -10.0], [-20.0, 20.0]]
_TRIANGLE_HOLE = [[-12.0, -4.0], [8.0, -4.0], [-12.0, 6.0]]
_CENTROID = (100.0, 50.0)


def _absolute(center: tuple[float, float], points) -> list[float]:
    return [value for x, y in points for value in (center[0] + x, center[1] + y)]


@pytest.mark.parametrize(
    "to_intent",
    [
        pocket_hint_to_removal_intent,
        engrave_hint_to_removal_intent,
        lambda hint: profile_hint_to_removal_intent(hint, sheet_thickness_mm=19.0),
    ],
    ids=["pocket", "engrave", "profile"],
)
def test_polygon_points_rebased_to_bounds_center(to_intent):
    hint: dict[str, Any] = {
        "id": "tri",
        "shape": "Polygon",
        "geometry": {"points": _TRIANGLE, "holes": [_TRIANGLE_HOLE]},
        "center_xy_mm": _CENTROID,
        "depth_mm": 2.0,
    }

    intent = to_intent(hint)

    center = intent.bounds.center
    assert center != _CENTROID
    assert _absolute(center, intent.shape_geometry.points) == pytest.approx(_absolute(_CENTROID, _TRIANGLE))
    (hole,) = intent.shape_geometry.holes
    assert _absolute(center, hole) == pytest.approx(_absolute(_CENTROID, _TRIANGLE_HOLE))


def test_polyline_and_line_rebased_to_bounds_center():
    polyline = engrave_hint_to_removal_intent(
        {
            "id": "wave",
            "shape": "Polyline",
            "geometry": {"points": _TRIANGLE},
            "center_xy_mm": _CENTROID,
            "depth_mm": 0.5,
        }
    )
    line = engrave_hint_to_removal_intent(
        {
            "id": "stroke",
            "shape": "Line",
            "geometry": {"start": [-5.0, 0.0], "end": [25.0, 10.0]},
            "center_xy_mm": _CENTROID,
            "depth_mm": 0.5,
        }
    )

    assert _absolute(polyline.bounds.center, polyline.shape_geometry.points) == pytest.approx(
        _absolute(_CENTROID, _TRIANGLE)
    )
    line_center = line.bounds.center
    assert _absolute(line_center, [line.shape_geometry.start, line.shape_geometry.end]) == pytest.approx(
        _absolute(_CENTROID, [[-5.0, 0.0], [25.0, 10.0]])
    )


def test_edge_feature_polygon_rebased_to_bounds_center():
    item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data={"points": _TRIANGLE}),
        placement=Placement(center_xy_mm=_CENTROID),
        feature=Feature(type="chamfer", depth_mm=3.0, chamfer_width_mm=3.0, chamfer_angle_deg=45.0),
        shape_id="tri_chamfer",
    )

    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)

    assert _absolute(intent.bounds.center, intent.shape_geometry.points) == pytest.approx(
        _absolute(_CENTROID, _TRIANGLE)
    )


def test_centered_polygon_keeps_points_exactly():
    diamond = [[0.0, -50.0], [50.0, 0.0], [0.0, 50.0], [-50.0, 0.0]]
    intent = pocket_hint_to_removal_intent(
        {
            "id": "diamond",
            "shape": "Polygon",
            "geometry": {"points": diamond},
            "center_xy_mm": (0.013, 0.113),
            "depth_mm": 2.0,
        }
    )

    assert intent.shape_geometry.points == tuple((x, y) for x, y in diamond)


def test_pocket_islands_reach_planner_input():
    hint: dict[str, Any] = {
        "id": "panel",
        "shape": "Rect",
        "geometry": {
            "w_mm": 400.0,
            "h_mm": 400.0,
            "islands": [{"x_min": 60.0, "x_max": 340.0, "y_min": 60.0, "y_max": 340.0}],
        },
        "center_xy_mm": (200.0, 200.0),
        "depth_mm": 6.0,
    }

    intent = pocket_hint_to_removal_intent(hint)
    (feature,) = PlannerInput.from_hints_dict(removal_intents_to_planner_input([intent]).to_hints_dict()).pockets

    (island,) = feature.islands
    assert (island.x_min, island.x_max, island.y_min, island.y_max) == (60.0, 340.0, 60.0, 340.0)
