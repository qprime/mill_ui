# validation - IR-level and CAM artifact validation
#
# This module provides two levels of validation:
# 1. IR-level validation (removal_checks.py) - Fast semantic validation before CAM execution
# 2. CAM artifact validation (runner.py, metrics/, invariants/) - Post-generation validation
#
# For CAM validation usage, see docs/cam_validation_plan.md

# IR-level validation (existing, for RemovalIntent checks)
from .results import ValidationResult
from .removal_checks import (
    check_overlap,
    check_depth_feasibility,
    check_toolability,
    check_depth_profile,
    check_toolpath_clearance,
    check_working_area_bounds,
)

# CAM validation types (new infrastructure)
from .core import (
    Verdict,
    InvariantResult,
    AssertionResult,
    RegressionResult,
    CAMValidationResult,
)

# CAM validation runner
from .runner import (
    validate,
    validate_recipe,
    ValidationInput,
    ValidationOptions,
)

__all__ = [
    # IR-level validation
    "ValidationResult",
    "check_overlap",
    "check_depth_feasibility",
    "check_toolability",
    "check_depth_profile",
    "check_toolpath_clearance",
    "check_working_area_bounds",
    # CAM validation types
    "Verdict",
    "InvariantResult",
    "AssertionResult",
    "RegressionResult",
    "CAMValidationResult",
    # CAM validation runner
    "validate",
    "validate_recipe",
    "ValidationInput",
    "ValidationOptions",
]
