"""Unit tests for RemovalIntent IR data structures.

Stage 4 acceptance tests.
"""

from __future__ import annotations

import pytest

from skills.mill_ui.v2.ir.removal_intent import (
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
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    assert bounds.x_min == 0.0
    assert bounds.x_max == 100.0
    assert bounds.y_min == 0.0
    assert bounds.y_max == 50.0


def test_bounds2d_invalid_x():
    """Test that invalid X bounds raise ValueError."""
    with pytest.raises(ValueError, match="x_max.*< x_min"):
        Bounds2D(x_min=100.0, x_max=0.0, y_min=0.0, y_max=50.0)


def test_bounds2d_invalid_y():
    """Test that invalid Y bounds raise ValueError."""
    with pytest.raises(ValueError, match="y_max.*< y_min"):
        Bounds2D(x_min=0.0, x_max=100.0, y_min=50.0, y_max=0.0)


def test_allowance_defaults():
    """Test Allowance default values."""
    allowance = Allowance()
    assert allowance.inside == 0.0
    assert allowance.outside == 0.0
    assert allowance.on == 0.0
    assert allowance.kerf_compensation == 0.0


def test_allowance_custom():
    """Test Allowance with custom values."""
    allowance = Allowance(inside=0.5, outside=-0.2, on=0.1, kerf_compensation=3.175)
    assert allowance.inside == 0.5
    assert allowance.outside == -0.2
    assert allowance.on == 0.1
    assert allowance.kerf_compensation == 3.175


def test_tab_constraint():
    """Test TabConstraint construction."""
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    assert tab.count == 4
    assert tab.height_mm == 3.0
    assert tab.width_mm == 10.0


def test_keepout_region():
    """Test KeepoutRegion construction."""
    bounds = Bounds2D(x_min=10.0, x_max=20.0, y_min=10.0, y_max=20.0)
    keepout = KeepoutRegion(bounds=bounds, reason="clamp zone")
    assert keepout.bounds == bounds
    assert keepout.reason == "clamp zone"


def test_island():
    """Test Island construction."""
    bounds = Bounds2D(x_min=30.0, x_max=40.0, y_min=30.0, y_max=40.0)
    island = Island(bounds=bounds, label="mounting_hole")
    assert island.bounds == bounds
    assert island.label == "mounting_hole"


def test_constraints_defaults():
    """Test Constraints default values."""
    constraints = Constraints()
    assert constraints.tabs is None
    assert constraints.keepouts == ()
    assert constraints.islands == ()
    assert constraints.tolerance_mm == 0.1
    assert constraints.safe_z_mm == 5.0


def test_constraints_with_tabs():
    """Test Constraints with tabs."""
    tab = TabConstraint(count=6, height_mm=3.0, width_mm=10.0)
    constraints = Constraints(tabs=tab, safe_z_mm=10.0)
    assert constraints.tabs is not None
    assert constraints.tabs.count == 6
    assert constraints.safe_z_mm == 10.0


def test_removal_intent_minimal():
    """Test minimal RemovalIntent construction."""
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


def test_removal_intent_with_allowance():
    """Test RemovalIntent with allowance."""
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


def test_removal_intent_with_constraints():
    """Test RemovalIntent with full constraints."""
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


def test_removal_intent_with_metadata():
    """Test RemovalIntent with metadata."""
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


def test_removal_intent_invalid_depth():
    """Test that z_bottom > z_top raises ValueError."""
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)

    with pytest.raises(ValueError, match="z_bottom.*> z_top"):
        RemovalIntent(
            region_id="invalid",
            bounds=bounds,
            z_top=-10.0,
            z_bottom=0.0,  # Invalid: bottom above top
        )


def test_removal_intent_to_dict():
    """Test RemovalIntent serialization to dict."""
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

    # Verify structure
    assert data["region_id"] == "profile_1"
    assert data["bounds"]["x_min"] == 0.0
    assert data["bounds"]["x_max"] == 100.0
    assert data["z_top"] == 0.0
    assert data["z_bottom"] == -12.0
    assert data["depth_mm"] == 12.0
    assert data["allowance"]["outside"] == -0.5
    assert data["constraints"]["tabs"]["count"] == 4
    assert data["metadata"]["shape_id"] == "rect_1"


def test_removal_intent_depth_calculation():
    """Test depth_mm() calculation for various cases."""
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)

    # Standard removal from surface
    intent1 = RemovalIntent(
        region_id="standard",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-10.0,
    )
    assert intent1.depth_mm() == 10.0

    # Removal from elevated surface
    intent2 = RemovalIntent(
        region_id="elevated",
        bounds=bounds,
        z_top=5.0,
        z_bottom=-5.0,
    )
    assert intent2.depth_mm() == 10.0

    # Shallow removal
    intent3 = RemovalIntent(
        region_id="shallow",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-0.5,
    )
    assert intent3.depth_mm() == 0.5


def test_removal_intent_immutability():
    """Test that RemovalIntent dataclasses are immutable."""
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    intent = RemovalIntent(
        region_id="immutable_test",
        bounds=bounds,
        z_top=0.0,
        z_bottom=-10.0,
    )

    # Attempt to modify should raise AttributeError
    with pytest.raises(AttributeError):
        intent.z_bottom = -5.0
