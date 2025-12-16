"""Standalone test runner for Stage 6 planner adapter tests (without pytest).

Run from repository root: python3 -m skills.mill_ui.v2.tests.run_planner_adapter_tests
"""

import sys

from skills.mill_ui.v2.adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)
from skills.mill_ui.v2.adapters.removal_to_planner import (
    removal_intent_to_v1_hint,
    removal_intents_to_v1_hints,
)


def approx_equal(a: float, b: float, rel: float = 1e-9) -> bool:
    """Check if two floats are approximately equal."""
    return abs(a - b) <= rel * max(abs(a), abs(b), 1.0)


def test_roundtrip_profile_through_cut():
    """Test round-trip conversion for profile through-cut."""
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
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert reconstructed_hint["shape"] == original_hint["shape"]
    assert approx_equal(reconstructed_hint["geometry"]["w_mm"], original_hint["geometry"]["w_mm"])
    assert approx_equal(reconstructed_hint["geometry"]["h_mm"], original_hint["geometry"]["h_mm"])
    assert approx_equal(reconstructed_hint["center_xy_mm"][0], original_hint["center_xy_mm"][0])
    assert approx_equal(reconstructed_hint["center_xy_mm"][1], original_hint["center_xy_mm"][1])
    assert approx_equal(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert reconstructed_hint["side"] == original_hint["side"]

    print("  ✓ PASS")
    return True


def test_roundtrip_profile_with_tabs():
    """Test round-trip conversion for profile with tabs."""
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
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert approx_equal(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert "tabs" in reconstructed_hint
    assert reconstructed_hint["tabs"]["count"] == 6
    assert approx_equal(reconstructed_hint["tabs"]["height"], 3.0)
    assert approx_equal(reconstructed_hint["tabs"]["width_mm"], 10.0)

    print("  ✓ PASS")
    return True


def test_roundtrip_pocket_basic():
    """Test round-trip conversion for basic pocket."""
    print("Running test_roundtrip_pocket_basic...")
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
    assert approx_equal(reconstructed_hint["geometry"]["w_mm"], original_hint["geometry"]["w_mm"])
    assert approx_equal(reconstructed_hint["geometry"]["h_mm"], original_hint["geometry"]["h_mm"])
    assert approx_equal(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert "start_depth_mm" not in reconstructed_hint

    print("  ✓ PASS")
    return True


def test_roundtrip_pocket_with_start_depth():
    """Test round-trip conversion for pocket with start depth."""
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
    reconstructed_hint = removal_intent_to_v1_hint(intent)

    assert reconstructed_hint["id"] == original_hint["id"]
    assert approx_equal(reconstructed_hint["depth_mm"], original_hint["depth_mm"])
    assert approx_equal(reconstructed_hint["start_depth_mm"], original_hint["start_depth_mm"])

    print("  ✓ PASS")
    return True


def test_roundtrip_hole_circle():
    """Test round-trip conversion for hole (circle)."""
    print("Running test_roundtrip_hole_circle...")
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
    assert approx_equal(reconstructed_hint["geometry"]["diameter_mm"], original_hint["geometry"]["diameter_mm"])
    assert approx_equal(reconstructed_hint["center_xy_mm"][0], original_hint["center_xy_mm"][0])
    assert approx_equal(reconstructed_hint["center_xy_mm"][1], original_hint["center_xy_mm"][1])
    assert approx_equal(reconstructed_hint["depth_mm"], original_hint["depth_mm"])

    print("  ✓ PASS")
    return True


def test_batch_conversion():
    """Test converting multiple RemovalIntents to v1 hints structure."""
    print("Running test_batch_conversion...")
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
    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175)

    assert hints["units"] == "mm"
    assert approx_equal(hints["kerf_width_mm"], 3.175)
    assert len(hints["profiles"]) == 1
    assert len(hints["pockets"]) == 1
    assert len(hints["holes"]) == 1
    assert len(hints["engraves"]) == 0

    assert hints["profiles"][0]["id"] == "outer"
    assert hints["profiles"][0]["side"] == "outside"
    assert hints["pockets"][0]["id"] == "inner_pocket"
    assert approx_equal(hints["pockets"][0]["depth_mm"], 5.0)
    assert hints["holes"][0]["id"] == "mount"
    assert approx_equal(hints["holes"][0]["geometry"]["diameter_mm"], 6.0)

    print("  ✓ PASS")
    return True


def test_geometry_preservation():
    """Test that geometry is preserved through round-trip."""
    print("Running test_geometry_preservation...")
    hint = {
        "id": "test_rect",
        "shape": "Rect",
        "geometry": {"w_mm": 123.45, "h_mm": 67.89},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": 10.0,
    }

    intent = pocket_hint_to_removal_intent(hint)
    reconstructed = removal_intent_to_v1_hint(intent)

    assert approx_equal(reconstructed["geometry"]["w_mm"], hint["geometry"]["w_mm"])
    assert approx_equal(reconstructed["geometry"]["h_mm"], hint["geometry"]["h_mm"])
    assert approx_equal(reconstructed["center_xy_mm"][0], hint["center_xy_mm"][0])
    assert approx_equal(reconstructed["center_xy_mm"][1], hint["center_xy_mm"][1])

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_roundtrip_profile_through_cut,
        test_roundtrip_profile_with_tabs,
        test_roundtrip_pocket_basic,
        test_roundtrip_pocket_with_start_depth,
        test_roundtrip_hole_circle,
        test_batch_conversion,
        test_geometry_preservation,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")

    sys.exit(0 if all(results) else 1)
