
import sys
from pathlib import Path

from ir.removal_intent import RemovalIntent, Bounds2D, Allowance, Constraints, DepthProfile
from validation import (
    ValidationResult,
    check_overlap,
    check_depth_feasibility,
    check_toolability,
)


def _make_intent(
    region_id: str,
    bounds: Bounds2D,
    z_top: float = 0.0,
    z_bottom: float = -5.0,
    allowance: Allowance = None,
    constraints: Constraints = None,
    metadata: dict = None,
) -> RemovalIntent:
    """Helper to create RemovalIntent with DepthProfile."""
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=z_top, z_bottom=z_bottom),
        allowance=allowance or Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=constraints or Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata=metadata or {},
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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
        assert False, "Expected ValueError for inverted Z values"
    except ValueError as e:
        assert "z_bottom" in str(e) and "z_top" in str(e)

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
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

    print("  ✓ PASS")
    return True


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

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} validation tests passed")

    sys.exit(0 if all(results) else 1)
