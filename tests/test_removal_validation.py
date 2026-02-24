from __future__ import annotations

import sys

from ir.removal_intent import Allowance, Bounds2D, Constraints, DepthProfile, Island, KeepoutRegion, RemovalIntent
from validation import (
    ValidationResult,
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


def test_validation_result_basic():
    print("Running test_validation_result_basic...")
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
    print("  PASS")
    return True


def test_validation_result_multiple_issue_types():
    print("Running test_validation_result_multiple_issue_types...")
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
    print("  PASS")
    return True


def test_check_overlap_no_overlap():
    print("Running test_check_overlap_no_overlap...")
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
    print("  PASS")
    return True


def test_check_overlap_xy_overlap():
    print("Running test_check_overlap_xy_overlap...")
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
    print("  PASS")
    return True


def test_check_overlap_different_z_levels():
    print("Running test_check_overlap_different_z_levels...")
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
    print("  PASS")
    return True


def test_check_depth_feasibility_valid():
    print("Running test_check_depth_feasibility_valid...")
    intent = _make_intent(
        region_id="pocket_valid",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-6.0,
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()
    assert len(result.errors) == 0
    print("  PASS")
    return True


def test_check_depth_feasibility_inverted_z():
    print("Running test_check_depth_feasibility_inverted_z...")

    # DepthProfile now validates z_bottom > z_top
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

    print("  PASS")
    return True


def test_check_depth_feasibility_too_deep():
    print("Running test_check_depth_feasibility_too_deep...")
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
    print("  PASS")
    return True


def test_check_depth_feasibility_very_shallow():
    print("Running test_check_depth_feasibility_very_shallow...")
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
    print("  PASS")
    return True


def test_check_toolability_no_tools():
    print("Running test_check_toolability_no_tools...")
    intent = _make_intent(
        region_id="pocket_normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
    )

    result = check_toolability(intent, available_tools=None)
    assert result.is_valid()
    assert len(result.warnings) == 0
    print("  PASS")
    return True


def test_check_toolability_very_small_feature():
    print("Running test_check_toolability_very_small_feature...")
    intent = _make_intent(
        region_id="hole_tiny",
        bounds=Bounds2D(x_min=0.0, x_max=0.5, y_min=0.0, y_max=0.5),
    )

    result = check_toolability(intent, available_tools=None)
    assert result.is_valid()
    assert len(result.warnings) == 1
    assert "Very small feature" in result.warnings[0].message
    print("  PASS")
    return True


def test_check_toolability_with_suitable_tools():
    print("Running test_check_toolability_with_suitable_tools...")
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
    print("  PASS")
    return True


def test_check_toolability_no_suitable_tools():
    print("Running test_check_toolability_no_suitable_tools...")
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
    print("  PASS")
    return True


def test_check_toolability_limited_tools():
    print("Running test_check_toolability_limited_tools...")
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
    print("  PASS")
    return True


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


if __name__ == "__main__":
    tests = [
        test_validation_result_basic,
        test_validation_result_multiple_issue_types,
        test_check_overlap_no_overlap,
        test_check_overlap_xy_overlap,
        test_check_overlap_different_z_levels,
        test_check_depth_feasibility_valid,
        test_check_depth_feasibility_inverted_z,
        test_check_depth_feasibility_too_deep,
        test_check_depth_feasibility_very_shallow,
        test_check_toolability_no_tools,
        test_check_toolability_very_small_feature,
        test_check_toolability_with_suitable_tools,
        test_check_toolability_no_suitable_tools,
        test_check_toolability_limited_tools,
        test_check_overlap_three_pairwise,
        test_check_overlap_touching_edges_no_overlap,
        test_check_overlap_zero_width_inside_detects_overlap,
        test_check_overlap_zero_width_outside_no_overlap,
        test_check_depth_feasibility_zero_depth,
        test_check_toolability_all_tools_too_large,
        test_check_toolpath_clearance_insufficient_gap,
        test_check_toolpath_clearance_sufficient_gap,
        test_check_working_area_bounds_inside,
        test_check_working_area_bounds_exceeds_right,
        test_check_working_area_bounds_exceeds_left,
        test_check_working_area_bounds_outside_profile_offset,
        test_check_working_area_bounds_multiple_violations,
        test_check_overlap_with_keepouts,
        test_check_overlap_with_islands,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
