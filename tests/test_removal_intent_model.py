
from __future__ import annotations

import sys

from ir.removal_intent import (
    RemovalIntent,
    Bounds2D,
    Allowance,
    Constraints,
    TabConstraint,
    KeepoutRegion,
    Island,
)


def test_bounds2d_valid():
    print("Running test_bounds2d_valid...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    assert bounds.x_min == 0.0
    assert bounds.x_max == 100.0
    assert bounds.y_min == 0.0
    assert bounds.y_max == 50.0
    print("  PASS")
    return True


def test_bounds2d_invalid_x():
    print("Running test_bounds2d_invalid_x...")
    try:
        Bounds2D(x_min=100.0, x_max=0.0, y_min=0.0, y_max=50.0)
        print("  FAIL: Expected ValueError")
        return False
    except ValueError as e:
        if "x_max" in str(e) and "< x_min" in str(e):
            pass
        else:
            print(f"  FAIL: Wrong error message: {e}")
            return False
    print("  PASS")
    return True


def test_bounds2d_invalid_y():
    print("Running test_bounds2d_invalid_y...")
    try:
        Bounds2D(x_min=0.0, x_max=100.0, y_min=50.0, y_max=0.0)
        print("  FAIL: Expected ValueError")
        return False
    except ValueError as e:
        if "y_max" in str(e) and "< y_min" in str(e):
            pass
        else:
            print(f"  FAIL: Wrong error message: {e}")
            return False
    print("  PASS")
    return True


def test_allowance_defaults():
    print("Running test_allowance_defaults...")
    allowance = Allowance()
    assert allowance.inside == 0.0
    assert allowance.outside == 0.0
    assert allowance.on == 0.0
    assert allowance.kerf_compensation == 0.0
    print("  PASS")
    return True


def test_allowance_custom():
    print("Running test_allowance_custom...")
    allowance = Allowance(inside=0.5, outside=-0.2, on=0.1, kerf_compensation=3.175)
    assert allowance.inside == 0.5
    assert allowance.outside == -0.2
    assert allowance.on == 0.1
    assert allowance.kerf_compensation == 3.175
    print("  PASS")
    return True


def test_tab_constraint():
    print("Running test_tab_constraint...")
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    assert tab.count == 4
    assert tab.height_mm == 3.0
    assert tab.width_mm == 10.0
    print("  PASS")
    return True


def test_keepout_region():
    print("Running test_keepout_region...")
    bounds = Bounds2D(x_min=10.0, x_max=20.0, y_min=10.0, y_max=20.0)
    keepout = KeepoutRegion(bounds=bounds, reason="clamp zone")
    assert keepout.bounds == bounds
    assert keepout.reason == "clamp zone"
    print("  PASS")
    return True


def test_island():
    print("Running test_island...")
    bounds = Bounds2D(x_min=30.0, x_max=40.0, y_min=30.0, y_max=40.0)
    island = Island(bounds=bounds, label="mounting_hole")
    assert island.bounds == bounds
    assert island.label == "mounting_hole"
    print("  PASS")
    return True


def test_constraints_defaults():
    print("Running test_constraints_defaults...")
    constraints = Constraints()
    assert constraints.tabs is None
    assert constraints.keepouts == ()
    assert constraints.islands == ()
    assert constraints.tolerance_mm == 0.1
    assert constraints.safe_z_mm == 5.0
    print("  PASS")
    return True


def test_constraints_with_tabs():
    print("Running test_constraints_with_tabs...")
    tab = TabConstraint(count=6, height_mm=3.0, width_mm=10.0)
    constraints = Constraints(tabs=tab, safe_z_mm=10.0)
    assert constraints.tabs is not None
    assert constraints.tabs.count == 6
    assert constraints.safe_z_mm == 10.0
    print("  PASS")
    return True


def test_removal_intent_minimal():
    print("Running test_removal_intent_minimal...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    intent = RemovalIntent(
        region_id="profile_1",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-10.0,
    )

    assert intent.region_id == "profile_1"
    assert intent.bounds == bounds
    assert intent.z_top == 0.0
    assert intent.z_bottom == -10.0
    assert intent.depth_mm() == 10.0
    print("  PASS")
    return True


def test_removal_intent_with_allowance():
    print("Running test_removal_intent_with_allowance...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    allowance = Allowance(outside=-0.5, kerf_compensation=3.175)
    intent = RemovalIntent(
        region_id="profile_outside",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-12.0,
        allowance=allowance,
    )

    assert intent.allowance.outside == -0.5
    assert intent.allowance.kerf_compensation == 3.175
    assert intent.depth_mm() == 12.0
    print("  PASS")
    return True


def test_removal_intent_with_constraints():
    print("Running test_removal_intent_with_constraints...")
    bounds = Bounds2D(x_min=0.0, x_max=200.0, y_min=0.0, y_max=100.0)
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    keepout_bounds = Bounds2D(x_min=10.0, x_max=20.0, y_min=10.0, y_max=20.0)
    keepout = KeepoutRegion(bounds=keepout_bounds, reason="clamp")

    constraints = Constraints(
        tabs=tab,
        keepouts=(keepout,),
        tolerance_mm=0.05,
        safe_z_mm=10.0,
    )

    intent = RemovalIntent(
        region_id="profile_with_tabs",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-19.1,
        constraints=constraints,
    )

    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 4
    assert len(intent.constraints.keepouts) == 1
    assert intent.constraints.tolerance_mm == 0.05
    assert intent.depth_mm() == 19.1
    print("  PASS")
    return True


def test_removal_intent_with_metadata():
    print("Running test_removal_intent_with_metadata...")
    bounds = Bounds2D(x_min=0.0, x_max=50.0, y_min=0.0, y_max=30.0)
    metadata = {
        "shape_id": "rect_1",
        "feature_type": "pocket",
        "tool_id": "6mm_endmill",
    }

    intent = RemovalIntent(
        region_id="pocket_1",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-5.0,
        metadata=metadata,
    )

    assert intent.metadata["shape_id"] == "rect_1"
    assert intent.metadata["feature_type"] == "pocket"
    assert intent.metadata["tool_id"] == "6mm_endmill"
    print("  PASS")
    return True


def test_removal_intent_invalid_depth():
    print("Running test_removal_intent_invalid_depth...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)

    try:
        RemovalIntent(
            region_id="invalid",
            bounds=bounds,
            z_top=-10.0,
            z_bottom=0.0,
        )
        print("  FAIL: Expected ValueError")
        return False
    except ValueError as e:
        if "z_bottom" in str(e) and "> z_top" in str(e):
            pass
        else:
            print(f"  FAIL: Wrong error message: {e}")
            return False
    print("  PASS")
    return True


def test_removal_intent_to_dict():
    print("Running test_removal_intent_to_dict...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    allowance = Allowance(outside=-0.5)
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    constraints = Constraints(tabs=tab)

    intent = RemovalIntent(
        region_id="profile_1",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-12.0,
        allowance=allowance,
        constraints=constraints,
        metadata={"shape_id": "rect_1"},
    )

    data = intent.to_dict()


    assert data["region_id"] == "profile_1"
    assert data["bounds"]["x_min"] == 0.0
    assert data["bounds"]["x_max"] == 100.0
    assert data["z_top"] == 0.0
    assert data["z_bottom"] == -12.0
    assert data["depth_mm"] == 12.0
    assert data["allowance"]["outside"] == -0.5
    assert data["constraints"]["tabs"]["count"] == 4
    assert data["metadata"]["shape_id"] == "rect_1"
    print("  PASS")
    return True


def test_removal_intent_depth_calculation():
    print("Running test_removal_intent_depth_calculation...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)


    intent1 = RemovalIntent(
        region_id="standard",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-10.0,
    )
    assert intent1.depth_mm() == 10.0


    intent2 = RemovalIntent(
        region_id="elevated",
        bounds=bounds,
        z_top=5.0,
        z_bottom=-5.0,
    )
    assert intent2.depth_mm() == 10.0


    intent3 = RemovalIntent(
        region_id="shallow",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-0.5,
    )
    assert intent3.depth_mm() == 0.5
    print("  PASS")
    return True


def test_removal_intent_immutability():
    print("Running test_removal_intent_immutability...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    intent = RemovalIntent(
        region_id="immutable_test",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-10.0,
    )


    try:
        intent.z_bottom = -5.0
        print("  FAIL: Expected AttributeError for immutable dataclass")
        return False
    except AttributeError:
        pass
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_bounds2d_valid,
        test_bounds2d_invalid_x,
        test_bounds2d_invalid_y,
        test_allowance_defaults,
        test_allowance_custom,
        test_tab_constraint,
        test_keepout_region,
        test_island,
        test_constraints_defaults,
        test_constraints_with_tabs,
        test_removal_intent_minimal,
        test_removal_intent_with_allowance,
        test_removal_intent_with_constraints,
        test_removal_intent_with_metadata,
        test_removal_intent_invalid_depth,
        test_removal_intent_to_dict,
        test_removal_intent_depth_calculation,
        test_removal_intent_immutability,
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
