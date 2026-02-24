from __future__ import annotations

import sys

from adapters.hints_to_removal import (
    hole_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    profile_hint_to_removal_intent,
)
from adapters.removal_to_planner import (
    removal_intent_to_hint,
    removal_intents_to_hints,
)


def approx_eq(a, b, rel=1e-6):
    """Check if two values are approximately equal."""
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_roundtrip_profile_through_cut():
    print("Running test_roundtrip_profile_through_cut...")
    original_hint = {
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
    print("  PASS")
    return True


def test_roundtrip_profile_with_tabs():
    print("Running test_roundtrip_profile_with_tabs...")
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
    print("  PASS")
    return True


def test_roundtrip_profile_inside_cut():
    print("Running test_roundtrip_profile_inside_cut...")
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
    print("  PASS")
    return True


def test_roundtrip_pocket_basic():
    print("Running test_roundtrip_pocket_basic...")
    original_hint = {
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
    print("  PASS")
    return True


def test_roundtrip_pocket_with_start_depth():
    print("Running test_roundtrip_pocket_with_start_depth...")
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
    print("  PASS")
    return True


def test_roundtrip_hole_circle():
    print("Running test_roundtrip_hole_circle...")
    original_hint = {
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
    print("  PASS")
    return True


def test_batch_conversion_to_hints_structure():
    print("Running test_batch_conversion_to_hints_structure...")
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
    print("  PASS")
    return True


def test_geometry_preservation_rect():
    print("Running test_geometry_preservation_rect...")
    hint = {
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
    print("  PASS")
    return True


def test_geometry_preservation_circle():
    print("Running test_geometry_preservation_circle...")
    hint = {
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
    print("  PASS")
    return True


def test_depth_preservation():
    print("Running test_depth_preservation...")
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
    print("  PASS")
    return True


def test_metadata_fields_preserved():
    print("Running test_metadata_fields_preserved...")
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
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_roundtrip_profile_through_cut,
        test_roundtrip_profile_with_tabs,
        test_roundtrip_profile_inside_cut,
        test_roundtrip_pocket_basic,
        test_roundtrip_pocket_with_start_depth,
        test_roundtrip_hole_circle,
        test_batch_conversion_to_hints_structure,
        test_geometry_preservation_rect,
        test_geometry_preservation_circle,
        test_depth_preservation,
        test_metadata_fields_preserved,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
