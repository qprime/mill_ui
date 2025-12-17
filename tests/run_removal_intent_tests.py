"""Standalone test runner for Stage 4 RemovalIntent tests (without pytest).

Run from repository root: python3 -m skills.mill_ui.tests.run_removal_intent_tests
"""

import sys

from skills.mill_ui.ir.removal_intent import (
    RemovalIntent,
    Bounds2D,
    Allowance,
    Constraints,
    TabConstraint,
    KeepoutRegion,
    Island,
)


def test_bounds2d_valid():
    """Test valid Bounds2D construction."""
    print("Running test_bounds2d_valid...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    assert bounds.x_min == 0.0
    assert bounds.x_max == 100.0
    print("  ✓ PASS")
    return True


def test_bounds2d_invalid():
    """Test invalid bounds raise ValueError."""
    print("Running test_bounds2d_invalid...")
    try:
        Bounds2D(x_min=100.0, x_max=0.0, y_min=0.0, y_max=50.0)
        print("  ✗ FAIL: Expected ValueError")
        return False
    except ValueError:
        print("  ✓ PASS")
        return True


def test_removal_intent_minimal():
    """Test minimal RemovalIntent."""
    print("Running test_removal_intent_minimal...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    intent = RemovalIntent(
        region_id="profile_1",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-10.0,
    )
    assert intent.region_id == "profile_1"
    assert intent.depth_mm() == 10.0
    print("  ✓ PASS")
    return True


def test_removal_intent_with_tabs():
    """Test RemovalIntent with tabs."""
    print("Running test_removal_intent_with_tabs...")
    bounds = Bounds2D(x_min=0.0, x_max=200.0, y_min=0.0, y_max=100.0)
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    constraints = Constraints(tabs=tab, safe_z_mm=10.0)

    intent = RemovalIntent(
        region_id="profile_with_tabs",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-19.1,
        constraints=constraints,
    )

    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 4
    assert intent.depth_mm() == 19.1
    print("  ✓ PASS")
    return True


def test_removal_intent_to_dict():
    """Test serialization to dict."""
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
    assert data["depth_mm"] == 12.0
    assert data["allowance"]["outside"] == -0.5
    assert data["constraints"]["tabs"]["count"] == 4
    assert data["metadata"]["shape_id"] == "rect_1"
    print("  ✓ PASS")
    return True


def test_removal_intent_invalid_depth():
    """Test invalid depth raises ValueError."""
    print("Running test_removal_intent_invalid_depth...")
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)

    try:
        RemovalIntent(
            region_id="invalid",
            bounds=bounds,
            z_top=-10.0,
            z_bottom=0.0,  # Invalid: bottom above top
        )
        print("  ✗ FAIL: Expected ValueError")
        return False
    except ValueError:
        print("  ✓ PASS")
        return True


def test_allowance_and_constraints():
    """Test Allowance and Constraints construction."""
    print("Running test_allowance_and_constraints...")
    allowance = Allowance(inside=0.5, outside=-0.2, kerf_compensation=3.175)
    assert allowance.inside == 0.5
    assert allowance.kerf_compensation == 3.175

    keepout_bounds = Bounds2D(x_min=10.0, x_max=20.0, y_min=10.0, y_max=20.0)
    keepout = KeepoutRegion(bounds=keepout_bounds, reason="clamp")

    island_bounds = Bounds2D(x_min=30.0, x_max=40.0, y_min=30.0, y_max=40.0)
    island = Island(bounds=island_bounds, label="mount")

    constraints = Constraints(
        keepouts=(keepout,),
        islands=(island,),
        tolerance_mm=0.05,
    )

    assert len(constraints.keepouts) == 1
    assert len(constraints.islands) == 1
    assert constraints.tolerance_mm == 0.05
    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_bounds2d_valid,
        test_bounds2d_invalid,
        test_removal_intent_minimal,
        test_removal_intent_with_tabs,
        test_removal_intent_to_dict,
        test_removal_intent_invalid_depth,
        test_allowance_and_constraints,
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
