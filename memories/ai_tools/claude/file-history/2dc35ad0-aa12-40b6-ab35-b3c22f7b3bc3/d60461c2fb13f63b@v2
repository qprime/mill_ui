"""Unit tests for RemovalIntent validation layer.

Stage 8 acceptance tests.
"""

from __future__ import annotations

import pytest

from skills.mill_ui.v2.ir.removal_intent import RemovalIntent, Bounds2D, Allowance, Constraints
from skills.mill_ui.v2.validation import (
    ValidationResult,
    check_overlap,
    check_depth_feasibility,
    check_toolability,
)


def test_validation_result_basic():
    """Test ValidationResult basic operations."""
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


def test_validation_result_multiple_issue_types():
    """Test ValidationResult with errors, warnings, and suggestions."""
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


def test_check_overlap_no_overlap():
    """Test check_overlap with non-overlapping regions."""
    intent_a = RemovalIntent(
        region_id="pocket_a",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    intent_b = RemovalIntent(
        region_id="pocket_b",
        bounds=Bounds2D(x_min=20.0, x_max=30.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_overlap([intent_a, intent_b])
    assert result.is_valid()
    assert len(result.errors) == 0


def test_check_overlap_xy_overlap():
    """Test check_overlap with XY overlapping regions at same Z."""
    intent_a = RemovalIntent(
        region_id="pocket_a",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    intent_b = RemovalIntent(
        region_id="pocket_b",
        bounds=Bounds2D(x_min=5.0, x_max=15.0, y_min=5.0, y_max=15.0),  # Overlaps with pocket_a
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_overlap([intent_a, intent_b])
    assert not result.is_valid()
    assert len(result.errors) == 1
    assert "pocket_a" in result.errors[0].message
    assert "pocket_b" in result.errors[0].message


def test_check_overlap_different_z_levels():
    """Test check_overlap with overlapping XY but different Z levels."""
    intent_a = RemovalIntent(
        region_id="pocket_shallow",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-3.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    intent_b = RemovalIntent(
        region_id="pocket_deep",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),  # Same XY
        z_top=-4.0,  # Below pocket_shallow
        z_bottom=-8.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_overlap([intent_a, intent_b])
    assert result.is_valid()  # Different Z levels, so no overlap


def test_check_depth_feasibility_valid():
    """Test check_depth_feasibility with valid depth constraints."""
    intent = RemovalIntent(
        region_id="pocket_valid",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-6.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()
    assert len(result.errors) == 0


def test_check_depth_feasibility_inverted_z():
    """Test that RemovalIntent itself rejects inverted Z values."""
    # RemovalIntent.__post_init__ should reject inverted Z values
    with pytest.raises(ValueError, match="z_bottom.*z_top"):
        intent = RemovalIntent(
            region_id="pocket_inverted",
            bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
            z_top=-6.0,  # Below z_bottom (invalid)
            z_bottom=0.0,
            allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
            constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
            metadata={},
        )


def test_check_depth_feasibility_too_deep():
    """Test check_depth_feasibility cutting deeper than material (warning)."""
    intent = RemovalIntent(
        region_id="pocket_deep",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-15.0,  # Deeper than 12mm material
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()  # Warning, not error
    assert len(result.warnings) == 1
    assert "deeper than material thickness" in result.warnings[0].message


def test_check_depth_feasibility_very_shallow():
    """Test check_depth_feasibility with very shallow cut (suggestion)."""
    intent = RemovalIntent(
        region_id="engrave_shallow",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-0.2,  # Very shallow
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_depth_feasibility(intent, sheet_thickness_mm=12.0)
    assert result.is_valid()
    assert len(result.suggestions) == 1
    assert "Very shallow cut" in result.suggestions[0].message


def test_check_toolability_no_tools():
    """Test check_toolability with no tools specified (basic checks only)."""
    intent = RemovalIntent(
        region_id="pocket_normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_toolability(intent, available_tools=None)
    assert result.is_valid()
    assert len(result.warnings) == 0


def test_check_toolability_very_small_feature():
    """Test check_toolability with very small feature (warning)."""
    intent = RemovalIntent(
        region_id="hole_tiny",
        bounds=Bounds2D(x_min=0.0, x_max=0.5, y_min=0.0, y_max=0.5),  # 0.5mm x 0.5mm
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    result = check_toolability(intent, available_tools=None)
    assert result.is_valid()  # Warning, not error
    assert len(result.warnings) == 1
    assert "Very small feature" in result.warnings[0].message


def test_check_toolability_with_suitable_tools():
    """Test check_toolability with suitable tools available."""
    intent = RemovalIntent(
        region_id="pocket_normal",
        bounds=Bounds2D(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0),
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    tools = [
        {"diameter_mm": 3.175, "flutes": 2},  # 1/8" endmill
        {"diameter_mm": 6.35, "flutes": 2},   # 1/4" endmill
    ]

    result = check_toolability(intent, available_tools=tools)
    assert result.is_valid()
    assert len(result.errors) == 0


def test_check_toolability_no_suitable_tools():
    """Test check_toolability with no suitable tools (error)."""
    intent = RemovalIntent(
        region_id="pocket_tiny",
        bounds=Bounds2D(x_min=0.0, x_max=1.5, y_min=0.0, y_max=1.5),  # 1.5mm x 1.5mm
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    tools = [
        {"diameter_mm": 3.175, "flutes": 2},  # Too large for 1.5mm feature
        {"diameter_mm": 6.35, "flutes": 2},   # Too large
    ]

    result = check_toolability(intent, available_tools=tools)
    assert not result.is_valid()
    assert len(result.errors) == 1
    assert "No available tool" in result.errors[0].message


def test_check_toolability_limited_tools():
    """Test check_toolability with limited tool options (suggestion)."""
    intent = RemovalIntent(
        region_id="pocket_small",
        bounds=Bounds2D(x_min=0.0, x_max=4.0, y_min=0.0, y_max=4.0),
        z_top=0.0,
        z_bottom=-5.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    tools = [
        {"diameter_mm": 1.5, "flutes": 2},    # Suitable
        {"diameter_mm": 3.175, "flutes": 2},  # Suitable
        {"diameter_mm": 6.35, "flutes": 2},   # Too large
        {"diameter_mm": 12.7, "flutes": 4},   # Too large
    ]

    result = check_toolability(intent, available_tools=tools)
    assert result.is_valid()
    assert len(result.suggestions) == 1
    assert "Limited tool options" in result.suggestions[0].message
