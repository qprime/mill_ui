from __future__ import annotations

from ir.removal_intent import (
    Allowance,
    Bounds2D,
    Constraints,
    DepthProfile,
    Island,
    KeepoutRegion,
    RemovalIntent,
    TabConstraint,
)


def test_bounds2d_valid():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    assert bounds.x_min == 0.0
    assert bounds.x_max == 100.0
    assert bounds.y_min == 0.0
    assert bounds.y_max == 50.0


def test_bounds2d_invalid_x():
    try:
        Bounds2D(x_min=100.0, x_max=0.0, y_min=0.0, y_max=50.0)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "x_max" in str(e) and "< x_min" in str(e)


def test_bounds2d_invalid_y():
    try:
        Bounds2D(x_min=0.0, x_max=100.0, y_min=50.0, y_max=0.0)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "y_max" in str(e) and "< y_min" in str(e)


def test_allowance_defaults():
    allowance = Allowance()
    assert allowance.inside == 0.0
    assert allowance.outside == 0.0
    assert allowance.on == 0.0
    assert allowance.kerf_compensation == 0.0


def test_allowance_custom():
    allowance = Allowance(inside=0.5, outside=-0.2, on=0.1, kerf_compensation=3.175)
    assert allowance.inside == 0.5
    assert allowance.outside == -0.2
    assert allowance.on == 0.1
    assert allowance.kerf_compensation == 3.175


def test_tab_constraint():
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    assert tab.count == 4
    assert tab.height_mm == 3.0
    assert tab.width_mm == 10.0


def test_keepout_region():
    bounds = Bounds2D(x_min=10.0, x_max=20.0, y_min=10.0, y_max=20.0)
    keepout = KeepoutRegion(bounds=bounds, reason="clamp zone")
    assert keepout.bounds == bounds
    assert keepout.reason == "clamp zone"


def test_island():
    bounds = Bounds2D(x_min=30.0, x_max=40.0, y_min=30.0, y_max=40.0)
    island = Island(bounds=bounds, label="mounting_hole")
    assert island.bounds == bounds
    assert island.label == "mounting_hole"


def test_constraints_defaults():
    constraints = Constraints()
    assert constraints.tabs is None
    assert constraints.keepouts == ()
    assert constraints.islands == ()
    assert constraints.tolerance_mm == 0.1
    assert constraints.safe_z_mm == 5.0


def test_constraints_with_tabs():
    tab = TabConstraint(count=6, height_mm=3.0, width_mm=10.0)
    constraints = Constraints(tabs=tab, safe_z_mm=10.0)
    assert constraints.tabs is not None
    assert constraints.tabs.count == 6
    assert constraints.safe_z_mm == 10.0


def test_removal_intent_minimal():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    intent = RemovalIntent(
        region_id="profile_1",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-10.0),
    )

    assert intent.region_id == "profile_1"
    assert intent.bounds == bounds
    assert intent.depth_profile.z_top == 0.0
    assert intent.depth_profile.z_bottom == -10.0
    assert intent.depth_mm() == 10.0
    assert intent.depth_profile.mode == "constant"


def test_removal_intent_with_allowance():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    allowance = Allowance(outside=-0.5, kerf_compensation=3.175)
    intent = RemovalIntent(
        region_id="profile_outside",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-12.0),
        allowance=allowance,
    )

    assert intent.allowance.outside == -0.5
    assert intent.allowance.kerf_compensation == 3.175
    assert intent.depth_mm() == 12.0


def test_removal_intent_with_constraints():
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
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-19.1),
        constraints=constraints,
    )

    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 4
    assert len(intent.constraints.keepouts) == 1
    assert intent.constraints.tolerance_mm == 0.05
    assert intent.depth_mm() == 19.1


def test_removal_intent_with_typed_fields():
    bounds = Bounds2D(x_min=0.0, x_max=50.0, y_min=0.0, y_max=30.0)

    intent = RemovalIntent(
        region_id="pocket_1",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-5.0),
        shape_id="rect_1",
        feature_type="pocket",
        hint_type="pocket",
        shape="Rect",
    )

    assert intent.shape_id == "rect_1"
    assert intent.feature_type == "pocket"
    assert intent.hint_type == "pocket"
    assert intent.shape == "Rect"


def test_removal_intent_invalid_depth():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)

    try:
        RemovalIntent(
            region_id="invalid",
            bounds=bounds,
            depth_profile=DepthProfile.constant(z_top=-10.0, z_bottom=0.0),
        )
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "z_bottom" in str(e) and "> z_top" in str(e)


def test_removal_intent_to_dict():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    allowance = Allowance(outside=-0.5)
    tab = TabConstraint(count=4, height_mm=3.0, width_mm=10.0)
    constraints = Constraints(tabs=tab)

    intent = RemovalIntent(
        region_id="profile_1",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-12.0),
        allowance=allowance,
        constraints=constraints,
        shape_id="rect_1",
        hint_type="profile",
        shape="Rect",
    )

    data = intent.to_dict()

    assert data["region_id"] == "profile_1"
    assert data["bounds"]["x_min"] == 0.0
    assert data["bounds"]["x_max"] == 100.0
    assert data["depth_profile"]["mode"] == "constant"
    assert data["depth_profile"]["z_top"] == 0.0
    assert data["depth_profile"]["z_bottom"] == -12.0
    assert data["depth_profile"]["depth_mm"] == 12.0
    assert data["allowance"]["outside"] == -0.5
    assert data["constraints"]["tabs"]["count"] == 4
    assert data["shape_id"] == "rect_1"
    assert data["hint_type"] == "profile"
    assert data["shape"] == "Rect"


def test_removal_intent_depth_calculation():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)

    intent1 = RemovalIntent(
        region_id="standard",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-10.0),
    )
    assert intent1.depth_mm() == 10.0

    intent2 = RemovalIntent(
        region_id="elevated",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=5.0, z_bottom=-5.0),
    )
    assert intent2.depth_mm() == 10.0

    intent3 = RemovalIntent(
        region_id="shallow",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-0.5),
    )
    assert intent3.depth_mm() == 0.5


def test_removal_intent_immutability():
    bounds = Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0)
    intent = RemovalIntent(
        region_id="immutable_test",
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-10.0),
    )

    try:
        intent.depth_profile = DepthProfile.constant(z_top=0.0, z_bottom=-5.0)  # type: ignore[misc]
        raise AssertionError("Expected AttributeError for immutable dataclass")
    except AttributeError:
        pass


def test_depth_profile_constant():
    profile = DepthProfile.constant(z_top=0.0, z_bottom=-10.0)
    assert profile.mode == "constant"
    assert profile.z_top == 0.0
    assert profile.z_bottom == -10.0
    assert profile.depth_mm() == 10.0
    assert profile.gradient_direction_deg is None
    assert profile.v_angle_deg is None


def test_depth_profile_linear_gradient():
    profile = DepthProfile.linear_gradient(z_top=0.0, z_bottom=-6.0, direction_deg=45.0)
    assert profile.mode == "linear_gradient"
    assert profile.z_top == 0.0
    assert profile.z_bottom == -6.0
    assert profile.depth_mm() == 6.0
    assert profile.gradient_direction_deg == 45.0
    assert profile.v_angle_deg is None


def test_depth_profile_v_carve():
    profile = DepthProfile.v_carve(z_top=0.0, z_bottom=-5.0, v_angle_deg=90.0)
    assert profile.mode == "v_carve"
    assert profile.z_top == 0.0
    assert profile.z_bottom == -5.0
    assert profile.depth_mm() == 5.0
    assert profile.gradient_direction_deg is None
    assert profile.v_angle_deg == 90.0


def test_depth_profile_invalid_mode():
    try:
        DepthProfile(mode="invalid", z_top=0.0, z_bottom=-5.0)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "Invalid depth mode" in str(e)


def test_depth_profile_gradient_requires_direction():
    try:
        DepthProfile(mode="linear_gradient", z_top=0.0, z_bottom=-5.0)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "gradient_direction_deg required" in str(e)


def test_depth_profile_v_carve_requires_angle():
    try:
        DepthProfile(mode="v_carve", z_top=0.0, z_bottom=-5.0)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "v_angle_deg required" in str(e)


def test_depth_profile_v_carve_invalid_angle():
    try:
        DepthProfile(mode="v_carve", z_top=0.0, z_bottom=-5.0, v_angle_deg=0.0)
        raise AssertionError("Expected ValueError for angle 0")
    except ValueError as e:
        assert "v_angle_deg must be between 0 and 180" in str(e)

    try:
        DepthProfile(mode="v_carve", z_top=0.0, z_bottom=-5.0, v_angle_deg=180.0)
        raise AssertionError("Expected ValueError for angle 180")
    except ValueError as e:
        assert "v_angle_deg must be between 0 and 180" in str(e)


def test_depth_profile_to_dict():
    profile1 = DepthProfile.constant(z_top=0.0, z_bottom=-10.0)
    data1 = profile1.to_dict()
    assert data1["mode"] == "constant"
    assert data1["z_top"] == 0.0
    assert data1["z_bottom"] == -10.0
    assert data1["depth_mm"] == 10.0
    assert "gradient_direction_deg" not in data1
    assert "v_angle_deg" not in data1

    profile2 = DepthProfile.linear_gradient(z_top=0.0, z_bottom=-6.0, direction_deg=90.0)
    data2 = profile2.to_dict()
    assert data2["mode"] == "linear_gradient"
    assert data2["gradient_direction_deg"] == 90.0
    assert "v_angle_deg" not in data2

    profile3 = DepthProfile.v_carve(z_top=0.0, z_bottom=-5.0, v_angle_deg=60.0)
    data3 = profile3.to_dict()
    assert data3["mode"] == "v_carve"
    assert data3["v_angle_deg"] == 60.0
    assert "gradient_direction_deg" not in data3
