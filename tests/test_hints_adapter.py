
from __future__ import annotations

import pytest

from adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    engrave_hint_to_removal_intent,
)


def test_profile_hint_through_cut():
    hint = {
        "id": "rect_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 50.0},
        "center_xy_mm": (150.0, 75.0),
        "depth_mm": 19.1,
        "side": "outside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=19.1)

    assert intent.region_id == "profile_rect_outline"
    assert intent.z_top == 0.0
    assert intent.z_bottom == -19.1
    assert intent.depth_mm() == 19.1
    assert intent.bounds.x_min == 100.0
    assert intent.bounds.x_max == 200.0
    assert intent.bounds.y_min == 50.0
    assert intent.bounds.y_max == 100.0
    assert intent.metadata["hint_type"] == "profile"
    assert intent.metadata["side"] == "outside"


def test_profile_hint_with_tabs():
    hint = {
        "id": "panel_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 200.0, "h_mm": 150.0},
        "center_xy_mm": (100.0, 75.0),
        "depth_mm": 18.0,
        "side": "outside",
        "tabs": {"count": 6, "height": 3.0, "width_mm": 10.0},
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=18.0)

    assert intent.region_id == "profile_panel_outline"
    assert intent.depth_mm() == 18.0
    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 6
    assert intent.constraints.tabs.height_mm == 3.0
    assert intent.constraints.tabs.width_mm == 10.0


def test_profile_hint_inside_cut():
    hint = {
        "id": "aperture",
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 30.0},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 12.0,
        "side": "inside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)

    assert intent.metadata["side"] == "inside"
    assert intent.allowance.inside == 0.0


def test_pocket_hint_basic():
    hint = {
        "id": "pocket_1",
        "shape": "Rect",
        "geometry": {"w_mm": 80.0, "h_mm": 40.0},
        "center_xy_mm": (100.0, 50.0),
        "depth_mm": 5.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.region_id == "pocket_pocket_1"
    assert intent.z_top == 0.0
    assert intent.z_bottom == -5.0
    assert intent.depth_mm() == 5.0
    assert intent.bounds.x_min == 60.0
    assert intent.bounds.x_max == 140.0
    assert intent.metadata["hint_type"] == "pocket"


def test_pocket_hint_with_start_depth():
    hint = {
        "id": "stepped_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 60.0, "h_mm": 60.0},
        "center_xy_mm": (75.0, 75.0),
        "depth_mm": 8.0,
        "start_depth_mm": 2.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.region_id == "pocket_stepped_pocket"
    assert intent.z_top == -2.0
    assert intent.z_bottom == -10.0
    assert intent.depth_mm() == 8.0


def test_hole_hint_circle():
    hint = {
        "id": "mounting_hole",
        "shape": "Circle",
        "geometry": {"diameter_mm": 10.0},
        "center_xy_mm": (50.0, 50.0),
        "depth_mm": 12.0,
    }

    intent = hole_hint_to_removal_intent(hint)

    assert intent.region_id == "hole_mounting_hole"
    assert intent.z_top == 0.0
    assert intent.z_bottom == -12.0
    assert intent.depth_mm() == 12.0

    assert intent.bounds.x_min == 45.0
    assert intent.bounds.x_max == 55.0
    assert intent.bounds.y_min == 45.0
    assert intent.bounds.y_max == 55.0
    assert intent.metadata["hint_type"] == "hole"


def test_engrave_hint():
    hint = {
        "id": "text_engrave",
        "shape": "Polyline",
        "geometry": {"points": [(0, 0), (10, 0), (10, 10)]},
        "center_xy_mm": (25.0, 25.0),
        "depth_mm": 0.5,
    }

    intent = engrave_hint_to_removal_intent(hint)

    assert intent.region_id == "engrave_text_engrave"
    assert intent.z_top == 0.0
    assert intent.z_bottom == -0.5
    assert intent.depth_mm() == 0.5
    assert intent.metadata["hint_type"] == "engrave"


def test_profile_no_id():
    hint = {
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 50.0},
        "center_xy_mm": (25.0, 25.0),
        "depth_mm": 12.0,
        "side": "outside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)

    assert intent.region_id == "profile"


def test_pocket_no_center():
    hint = {
        "id": "centered_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 20.0, "h_mm": 20.0},
        "depth_mm": 3.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.bounds.x_min == -10.0
    assert intent.bounds.x_max == 10.0
    assert intent.bounds.y_min == -10.0
    assert intent.bounds.y_max == 10.0


def test_bounds_calculation_rect():
    hint = {
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 60.0},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": 10.0,
    }

    intent = pocket_hint_to_removal_intent(hint)

    assert intent.bounds.x_min == 150.0
    assert intent.bounds.x_max == 250.0
    assert intent.bounds.y_min == 120.0
    assert intent.bounds.y_max == 180.0


def test_bounds_calculation_circle():
    hint = {
        "shape": "Circle",
        "geometry": {"diameter_mm": 40.0},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 8.0,
    }

    intent = hole_hint_to_removal_intent(hint)

    assert intent.bounds.x_min == 80.0
    assert intent.bounds.x_max == 120.0
    assert intent.bounds.y_min == 80.0
    assert intent.bounds.y_max == 120.0


def test_side_to_allowance_outside():
    hint = {
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 50.0},
        "center_xy_mm": (25.0, 25.0),
        "depth_mm": 12.0,
        "side": "outside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)
    assert intent.allowance.outside == 0.0


def test_side_to_allowance_on():
    hint = {
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 50.0},
        "center_xy_mm": (25.0, 25.0),
        "depth_mm": 12.0,
        "side": "on",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)
    assert intent.allowance.on == 0.0


def test_metadata_preservation():
    hint = {
        "id": "custom_shape",
        "shape": "Rect",
        "geometry": {"w_mm": 30.0, "h_mm": 30.0},
        "center_xy_mm": (15.0, 15.0),
        "depth_mm": 6.0,
        "side": "inside",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)

    assert intent.metadata["hint_type"] == "profile"
    assert intent.metadata["shape"] == "Rect"
    assert intent.metadata["side"] == "inside"
    assert intent.metadata["original_id"] == "custom_shape"
