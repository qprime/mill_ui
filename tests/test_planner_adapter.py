"""Integration tests for RemovalIntent → v1 planner adapter.

Tests round-trip conversion:
  v1 hint → RemovalIntent → v1 hint (should be semantically equivalent)

Stage 6 acceptance tests.
"""

from __future__ import annotations

import pytest

from adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)
from adapters.removal_to_planner import (
    removal_intent_to_v1_hint,
    removal_intents_to_v1_hints,
)


def test_roundtrip_profile_through_cut():
    """Test round-trip conversion for profile through-cut."""
    original_hint = {
        "id": "rect_outline",
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 50.0},
        "center_xy_mm": (150.0, 75.0),
        "depth_mm": 19.1,
        "side": "outside",
    }

    # v1 → RemovalIntent
    intent = profile_hint_to_removal_intent(original_hint, sheet_thickness_mm=19.1)

    # RemovalIntent → v1
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    # Verify semantic equivalence
    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == original_hint["shape"]
    assert reconstructed_hint["geometry"]["w_mm"] == pytest.approx(original_hint["geometry"]["w_mm"])
    assert reconstructed_hint["geometry"]["h_mm"] == pytest.approx(original_hint["geometry"]["h_mm"])
    assert reconstructed_hint["center_xy_mm"][0] == pytest.approx(original_hint["center_xy_mm"][0])
    assert reconstructed_hint["center_xy_mm"][1] == pytest.approx(original_hint["center_xy_mm"][1])
    assert reconstructed_hint["depth_mm"] == pytest.approx(original_hint["depth_mm"])
    assert reconstructed_hint["side"] == original_hint["side"]


def test_roundtrip_profile_with_tabs():
    """Test round-trip conversion for profile with tabs."""
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
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["depth_mm"] == pytest.approx(original_hint["depth_mm"])
    assert "tabs" in reconstructed_hint
    assert reconstructed_hint["tabs"]["count"] == 6
    assert reconstructed_hint["tabs"]["height"] == pytest.approx(3.0)
    assert reconstructed_hint["tabs"]["width_mm"] == pytest.approx(10.0)


def test_roundtrip_profile_inside_cut():
    """Test round-trip conversion for profile inside cut."""
    original_hint = {
        "id": "aperture",
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 30.0},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 12.0,
        "side": "inside",
    }

    intent = profile_hint_to_removal_intent(original_hint, sheet_thickness_mm=12.0)
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["side"] == "inside"
    assert reconstructed_hint["depth_mm"] == pytest.approx(12.0)


def test_roundtrip_pocket_basic():
    """Test round-trip conversion for basic pocket."""
    original_hint = {
        "id": "pocket_1",
        "shape": "Rect",
        "geometry": {"w_mm": 80.0, "h_mm": 40.0},
        "center_xy_mm": (100.0, 50.0),
        "depth_mm": 5.0,
    }

    intent = pocket_hint_to_removal_intent(original_hint)
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == original_hint["shape"]
    assert reconstructed_hint["geometry"]["w_mm"] == pytest.approx(original_hint["geometry"]["w_mm"])
    assert reconstructed_hint["geometry"]["h_mm"] == pytest.approx(original_hint["geometry"]["h_mm"])
    assert reconstructed_hint["depth_mm"] == pytest.approx(original_hint["depth_mm"])
    # Basic pocket should not have start_depth_mm
    assert "start_depth_mm" not in reconstructed_hint


def test_roundtrip_pocket_with_start_depth():
    """Test round-trip conversion for pocket with start depth."""
    original_hint = {
        "id": "stepped_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 60.0, "h_mm": 60.0},
        "center_xy_mm": (75.0, 75.0),
        "depth_mm": 8.0,
        "start_depth_mm": 2.0,
    }

    intent = pocket_hint_to_removal_intent(original_hint)
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["depth_mm"] == pytest.approx(original_hint["depth_mm"])
    assert reconstructed_hint["start_depth_mm"] == pytest.approx(original_hint["start_depth_mm"])


def test_roundtrip_hole_circle():
    """Test round-trip conversion for hole (circle)."""
    original_hint = {
        "id": "mounting_hole",
        "shape": "Circle",
        "geometry": {"diameter_mm": 10.0},
        "center_xy_mm": (50.0, 50.0),
        "depth_mm": 12.0,
    }

    intent = hole_hint_to_removal_intent(original_hint)
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == "Circle"
    assert reconstructed_hint["geometry"]["diameter_mm"] == pytest.approx(original_hint["geometry"]["diameter_mm"])
    assert reconstructed_hint["center_xy_mm"][0] == pytest.approx(original_hint["center_xy_mm"][0])
    assert reconstructed_hint["center_xy_mm"][1] == pytest.approx(original_hint["center_xy_mm"][1])
    assert reconstructed_hint["depth_mm"] == pytest.approx(original_hint["depth_mm"])


def test_batch_conversion_to_hints_structure():
    """Test converting multiple RemovalIntents to v1 hints structure."""
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

    # Convert to RemovalIntent
    profile_intent = profile_hint_to_removal_intent(profile_hint, sheet_thickness_mm=12.0)
    pocket_intent = pocket_hint_to_removal_intent(pocket_hint)
    hole_intent = hole_hint_to_removal_intent(hole_hint)

    # Batch convert back to v1 hints structure
    intents = [profile_intent, pocket_intent, hole_intent]
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175)

    # Verify structure
    assert hints["units"] == "mm"
    assert hints["kerf_width_mm"] == pytest.approx(3.175)
    assert len(hints["profiles"]) == 1
    assert len(hints["pockets"]) == 1
    assert len(hints["holes"]) == 1
    assert len(hints["engraves"]) == 0

    # Verify profile
    assert hints["profiles"][0]["id"] == "outer"
    assert hints["profiles"][0]["side"] == "outside"

    # Verify pocket
    assert hints["pockets"][0]["id"] == "inner_pocket"
    assert hints["pockets"][0]["depth_mm"] == pytest.approx(5.0)

    # Verify hole
    assert hints["holes"][0]["id"] == "mount"
    assert hints["holes"][0]["geometry"]["diameter_mm"] == pytest.approx(6.0)


def test_geometry_preservation_rect():
    """Test that rectangular geometry is preserved through round-trip."""
    hint = {
        "id": "test_rect",
        "shape": "Rect",
        "geometry": {"w_mm": 123.45, "h_mm": 67.89},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": 10.0,
    }

    intent = pocket_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_v1_hint(intent)

    # Geometry should be preserved to floating point precision
    assert reconstructed["geometry"]["w_mm"] == pytest.approx(hint["geometry"]["w_mm"], rel=1e-9)
    assert reconstructed["geometry"]["h_mm"] == pytest.approx(hint["geometry"]["h_mm"], rel=1e-9)
    assert reconstructed["center_xy_mm"][0] == pytest.approx(hint["center_xy_mm"][0], rel=1e-9)
    assert reconstructed["center_xy_mm"][1] == pytest.approx(hint["center_xy_mm"][1], rel=1e-9)


def test_geometry_preservation_circle():
    """Test that circular geometry is preserved through round-trip."""
    hint = {
        "id": "test_circle",
        "shape": "Circle",
        "geometry": {"diameter_mm": 25.4},
        "center_xy_mm": (100.0, 100.0),
        "depth_mm": 8.0,
    }

    intent = hole_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_v1_hint(intent)

    assert reconstructed["geometry"]["diameter_mm"] == pytest.approx(hint["geometry"]["diameter_mm"], rel=1e-9)
    assert reconstructed["center_xy_mm"][0] == pytest.approx(hint["center_xy_mm"][0], rel=1e-9)
    assert reconstructed["center_xy_mm"][1] == pytest.approx(hint["center_xy_mm"][1], rel=1e-9)


def test_depth_preservation():
    """Test that depth values are preserved through round-trip."""
    hint = {
        "id": "deep_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 50.0, "h_mm": 50.0},
        "center_xy_mm": (25.0, 25.0),
        "depth_mm": 15.75,
        "start_depth_mm": 3.25,
    }

    intent = pocket_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_v1_hint(intent)

    # Depth should be exact (within floating point error)
    assert reconstructed["depth_mm"] == pytest.approx(hint["depth_mm"], rel=1e-9)
    assert reconstructed["start_depth_mm"] == pytest.approx(hint["start_depth_mm"], rel=1e-9)


def test_metadata_fields_preserved():
    """Test that important metadata is preserved."""
    hint = {
        "id": "custom_id_123",
        "shape": "Rect",
        "geometry": {"w_mm": 40.0, "h_mm": 30.0},
        "center_xy_mm": (20.0, 15.0),
        "depth_mm": 6.0,
        "side": "on",
    }

    intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=12.0)
    reconstructed = removal_intent_to_v1_hint(intent)

    assert reconstructed["id"] == hint["id"]
    assert reconstructed["shape"] == hint["shape"]
    assert reconstructed["side"] == hint["side"]
