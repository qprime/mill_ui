# validation/assertions/intent_assertions.py - Intent-derived assertions
#
# Derives assertions from LayoutAST (source intent) and validates them
# against extracted metrics from CAM artifacts (SVG, STL, G-code).
#
# See docs/cam_validation_plan.md for architecture and schema.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.constants import DepthMode
from layout_ast.layout import LayoutAST, Item, Feature
from validation.core import AssertionResult, Verdict


# Assertion IDs for each type of intent check
ASSERTION_IDS = [
    "SHEET_DIMENSIONS",    # Sheet size matches SVG/STL bounds
    "PROFILE_EXISTS",      # Profile cut path exists for profile features
    "PROFILE_SIDE",        # Profile side (inside/outside) affects bounds correctly
    "POCKET_DEPTH",        # Pocket depth matches STL Z-level
    "HOLE_POSITION",       # Hole center at expected XY
    "HOLE_DIAMETER",       # Hole diameter matches specification
    "THROUGH_CUT",         # Through cut reaches Z=0 (or -thickness)
    "TAB_COUNT",           # G-code Z lifts match expected tab count
    "ITEM_COUNT",          # Expected number of items exist
]


# Default tolerances for assertions (per docs/cam_validation_plan.md section 5.3)
DEFAULT_POSITION_TOLERANCE_MM = 0.01   # XY position tolerance
DEFAULT_DEPTH_TOLERANCE_MM = 0.01      # Z depth tolerance
DEFAULT_DIMENSION_TOLERANCE_MM = 0.01  # Width/height tolerance (length)
DEFAULT_PERCENT_TOLERANCE = 0.001      # 0.1% for area/volume


@dataclass
class IntentAssertion:
    """Internal representation of a derived assertion before checking."""

    id: str
    source: str  # e.g., "ast:item:door_outer" or "ast:sheet"
    intent: str  # Human-readable intent
    expected: dict[str, Any]
    tolerance: float = 0.1
    artifact: str = "any"  # Which artifact to check: "svg", "stl", "gcode", "any"


def derive_assertions(ast: LayoutAST) -> list[IntentAssertion]:
    """
    Derive assertions from a LayoutAST.

    Examines the sheet and items to generate assertions that can be
    checked against extracted metrics from CAM artifacts.

    Args:
        ast: The LayoutAST representing the design intent

    Returns:
        List of IntentAssertion objects to be validated
    """
    assertions: list[IntentAssertion] = []

    # Sheet dimension assertions
    assertions.append(IntentAssertion(
        id="SHEET_DIMENSIONS",
        source="ast:sheet",
        intent=f"Sheet {ast.sheet.width_mm}x{ast.sheet.height_mm}x{ast.sheet.thickness_mm}mm",
        expected={
            "width_mm": ast.sheet.width_mm,
            "height_mm": ast.sheet.height_mm,
            "thickness_mm": ast.sheet.thickness_mm,
        },
        tolerance=DEFAULT_DIMENSION_TOLERANCE_MM,
        artifact="stl",  # STL has 3D bounds including thickness
    ))

    # Item count assertion
    assertions.append(IntentAssertion(
        id="ITEM_COUNT",
        source="ast:items",
        intent=f"Layout has {len(ast.items)} items",
        expected={"count": len(ast.items)},
        tolerance=0,  # Exact match
        artifact="any",
    ))

    # Item-specific assertions
    for item in ast.items:
        assertions.extend(_derive_item_assertions(item, ast.sheet.thickness_mm))

    # Aggregate tab count assertion (sum tabs across all profiles)
    total_tab_count = 0
    tab_height_mm = None
    tab_profiles = []
    for item in ast.items:
        if item.feature and item.feature.type == "profile":
            if item.feature.tab_count and item.feature.tab_count > 0:
                total_tab_count += item.feature.tab_count
                if tab_height_mm is None:
                    tab_height_mm = item.feature.tab_height_mm
                item_id = item.shape_id or item.id or "unnamed"
                tab_profiles.append(f"{item_id}({item.feature.tab_count})")

    if total_tab_count > 0:
        assertions.append(IntentAssertion(
            id="TAB_COUNT",
            source="ast:aggregate",
            intent=f"Total {total_tab_count} tabs across {len(tab_profiles)} profiles",
            expected={
                "tab_count": total_tab_count,
                "tab_height_mm": tab_height_mm,
                "profiles": tab_profiles,
            },
            tolerance=0,
            artifact="gcode",
        ))

    return assertions


def _derive_item_assertions(item: Item, sheet_thickness_mm: float) -> list[IntentAssertion]:
    """Derive assertions from a single Item."""
    assertions: list[IntentAssertion] = []

    if item.feature is None:
        return assertions

    feature = item.feature
    item_id = item.shape_id or item.id or "unnamed"
    source = f"ast:item:{item_id}"

    # Get center position if available
    center_xy = None
    if item.placement:
        center_xy = item.placement.center_xy_mm

    # Get geometry dimensions
    width_mm = None
    height_mm = None
    diameter_mm = None
    if item.geometry and item.geometry.data:
        width_mm = item.geometry.data.get("w_mm")
        height_mm = item.geometry.data.get("h_mm")
        diameter_mm = item.geometry.data.get("diameter_mm")

    # Feature type assertions
    if feature.type == "profile":
        # Profile existence assertion - include expected geometry for matching
        expected_profile = {
            "shape_id": item_id,
            "feature_type": "profile",
        }
        # Include position and dimensions for matching
        if center_xy:
            expected_profile["center_xy"] = center_xy
        if width_mm and height_mm:
            expected_profile["width_mm"] = width_mm
            expected_profile["height_mm"] = height_mm
        elif diameter_mm:
            expected_profile["diameter_mm"] = diameter_mm

        assertions.append(IntentAssertion(
            id="PROFILE_EXISTS",
            source=source,
            intent=f"Profile cut exists for '{item_id}'",
            expected=expected_profile,
            tolerance=DEFAULT_POSITION_TOLERANCE_MM,
            artifact="svg",  # Check in SVG PROFILE_CUTS layer
        ))

        # Profile side assertion (outside profiles should be larger)
        if feature.side and center_xy and width_mm and height_mm:
            assertions.append(IntentAssertion(
                id="PROFILE_SIDE",
                source=source,
                intent=f"Profile side is '{feature.side}' for '{item_id}'",
                expected={
                    "shape_id": item_id,
                    "side": feature.side,
                    "center_xy": center_xy,
                    "nominal_width_mm": width_mm,
                    "nominal_height_mm": height_mm,
                },
                tolerance=DEFAULT_POSITION_TOLERANCE_MM,
                artifact="gcode",
            ))

        # Through cut assertion
        if DepthMode.is_through(feature.depth):
            assertions.append(IntentAssertion(
                id="THROUGH_CUT",
                source=source,
                intent=f"Through cut for '{item_id}' reaches full depth",
                expected={
                    "shape_id": item_id,
                    "target_depth_mm": -sheet_thickness_mm,  # Negative Z in G-code
                },
                tolerance=DEFAULT_DEPTH_TOLERANCE_MM,
                artifact="gcode",
            ))

        # Note: Tab count assertions are aggregated at the AST level
        # to compare total expected tabs vs total detected tabs in G-code

    elif feature.type == "pocket":
        # Pocket depth assertion
        depth_mm = _resolve_depth(feature, sheet_thickness_mm)
        if depth_mm is not None:
            assertions.append(IntentAssertion(
                id="POCKET_DEPTH",
                source=source,
                intent=f"Pocket depth {depth_mm}mm for '{item_id}'",
                expected={
                    "shape_id": item_id,
                    "depth_mm": depth_mm,
                },
                tolerance=DEFAULT_DEPTH_TOLERANCE_MM,
                artifact="stl",  # Check in STL z_statistics
            ))

    elif feature.type == "hole":
        # Hole position assertion
        if center_xy:
            assertions.append(IntentAssertion(
                id="HOLE_POSITION",
                source=source,
                intent=f"Hole at ({center_xy[0]}, {center_xy[1]})mm for '{item_id}'",
                expected={
                    "shape_id": item_id,
                    "center_x_mm": center_xy[0],
                    "center_y_mm": center_xy[1],
                },
                tolerance=DEFAULT_POSITION_TOLERANCE_MM,
                artifact="svg",  # Check in SVG HOLES layer
            ))

        # Hole diameter assertion
        if diameter_mm:
            assertions.append(IntentAssertion(
                id="HOLE_DIAMETER",
                source=source,
                intent=f"Hole diameter {diameter_mm}mm for '{item_id}'",
                expected={
                    "shape_id": item_id,
                    "diameter_mm": diameter_mm,
                },
                tolerance=DEFAULT_DIMENSION_TOLERANCE_MM,
                artifact="svg",
            ))

        # Through cut assertion for through holes
        if DepthMode.is_through(feature.depth):
            assertions.append(IntentAssertion(
                id="THROUGH_CUT",
                source=source,
                intent=f"Through hole for '{item_id}' reaches full depth",
                expected={
                    "shape_id": item_id,
                    "target_depth_mm": -sheet_thickness_mm,
                },
                tolerance=DEFAULT_DEPTH_TOLERANCE_MM,
                artifact="gcode",
            ))

    return assertions


def _resolve_depth(feature: Feature, sheet_thickness_mm: float) -> float | None:
    """Resolve a feature depth to a numeric value in mm."""
    if feature.depth_mm is not None:
        return feature.depth_mm

    if DepthMode.is_through(feature.depth):
        return sheet_thickness_mm

    if isinstance(feature.depth, (int, float)):
        return float(feature.depth)

    if isinstance(feature.depth, str):
        # Try to parse as number (e.g., "6" or "6mm")
        try:
            depth_str = feature.depth.replace("mm", "").strip()
            return float(depth_str)
        except (ValueError, AttributeError):
            pass

    return None


def _unwrap_metrics(metrics: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    """Unwrap metrics from their container key if present.

    Metrics from to_dict() are wrapped like {"svg": {...}} or {"stl": {...}}.
    This function extracts the inner dict if the wrapper key is present.
    """
    if metrics is None:
        return None
    # If already unwrapped (no wrapper key), return as-is
    if key in metrics and isinstance(metrics[key], dict):
        return metrics[key]
    # If it has typical metric keys, it's already unwrapped
    return metrics


def check_assertions(
    assertions: list[IntentAssertion],
    svg_metrics: dict[str, Any] | None = None,
    stl_metrics: dict[str, Any] | None = None,
    gcode_metrics: dict[str, Any] | None = None,
) -> list[AssertionResult]:
    """
    Check derived assertions against extracted metrics.

    Args:
        assertions: List of IntentAssertion objects from derive_assertions()
        svg_metrics: Extracted SVG metrics (from SVGMetrics.to_dict())
        stl_metrics: Extracted STL metrics (from STLMetrics.to_dict())
        gcode_metrics: Extracted G-code metrics (from GCodeMetrics.to_dict())

    Returns:
        List of AssertionResult objects with pass/fail status
    """
    # Unwrap metrics if they have wrapper keys
    svg_unwrapped = _unwrap_metrics(svg_metrics, "svg")
    stl_unwrapped = _unwrap_metrics(stl_metrics, "stl")
    gcode_unwrapped = _unwrap_metrics(gcode_metrics, "gcode")

    results: list[AssertionResult] = []

    for assertion in assertions:
        result = _check_single_assertion(
            assertion,
            svg_metrics=svg_unwrapped,
            stl_metrics=stl_unwrapped,
            gcode_metrics=gcode_unwrapped,
        )
        results.append(result)

    return results


def _check_single_assertion(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """Check a single assertion against the appropriate metrics."""

    # Route to the appropriate checker based on assertion ID
    checkers = {
        "SHEET_DIMENSIONS": _check_sheet_dimensions,
        "ITEM_COUNT": _check_item_count,
        "PROFILE_EXISTS": _check_profile_exists,
        "PROFILE_SIDE": _check_profile_side,
        "POCKET_DEPTH": _check_pocket_depth,
        "HOLE_POSITION": _check_hole_position,
        "HOLE_DIAMETER": _check_hole_diameter,
        "THROUGH_CUT": _check_through_cut,
        "TAB_COUNT": _check_tab_count,
    }

    checker = checkers.get(assertion.id)
    if checker is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "Unknown assertion type"},
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"No checker for assertion type '{assertion.id}'",
        )

    return checker(
        assertion,
        svg_metrics=svg_metrics,
        stl_metrics=stl_metrics,
        gcode_metrics=gcode_metrics,
    )


def _check_sheet_dimensions(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """
    Check that sheet dimensions are correct.

    Checks SVG SHEET_OUTLINE layer for sheet dimensions (preferred) since the STL
    typically represents the cut part geometry, not the full sheet. Falls back to
    STL if SVG not available.
    """
    expected_width = assertion.expected["width_mm"]
    expected_height = assertion.expected["height_mm"]
    expected_thickness = assertion.expected["thickness_mm"]
    tol = assertion.tolerance

    actual: dict[str, Any] = {}
    actual_width = None
    actual_height = None
    actual_thickness = None
    source = None

    # Try SVG SHEET_OUTLINE first (more reliable for sheet dimensions)
    if svg_metrics is not None:
        layers = svg_metrics.get("layers", {})
        by_layer = layers.get("by_layer", {})
        sheet_outline = by_layer.get("SHEET_OUTLINE", {})
        elements = sheet_outline.get("elements", [])

        if elements:
            # Get sheet dimensions from first SHEET_OUTLINE element
            elem = elements[0]
            actual_width = elem.get("width")
            actual_height = elem.get("height")
            source = "svg_sheet_outline"
            actual["source"] = source
            actual["sheet_outline_element"] = elem

    # Fall back to STL dimensions if SVG didn't work
    if actual_width is None and stl_metrics is not None:
        dimensions = stl_metrics.get("dimensions", {})
        actual_width = dimensions.get("width_mm", 0)
        actual_height = dimensions.get("height_mm", 0)
        actual_thickness = dimensions.get("thickness_mm", 0)
        source = "stl_dimensions"
        actual["source"] = source
        actual["note"] = "STL represents cut part geometry, may not match sheet dimensions"

    # Check if we have any dimensions to compare
    if actual_width is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No dimension data available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify sheet dimensions: no SVG or STL metrics provided",
        )

    actual["width_mm"] = actual_width
    actual["height_mm"] = actual_height

    # Check width and height within tolerance
    width_ok = abs(actual_width - expected_width) <= tol
    height_ok = abs(actual_height - expected_height) <= tol

    # For thickness, check STL if available (SVG doesn't have thickness)
    thickness_ok = True
    if actual_thickness is not None:
        actual["thickness_mm"] = actual_thickness
        thickness_ok = abs(actual_thickness - expected_thickness) <= tol
    elif stl_metrics is not None:
        dimensions = stl_metrics.get("dimensions", {})
        actual_thickness = dimensions.get("thickness_mm", 0)
        actual["thickness_mm"] = actual_thickness
        thickness_ok = abs(actual_thickness - expected_thickness) <= tol

    all_ok = width_ok and height_ok and thickness_ok

    if all_ok:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Sheet dimensions match within tolerance (source: {source})",
        )
    else:
        failures = []
        if not width_ok:
            failures.append(f"width: expected {expected_width}, got {actual_width}")
        if not height_ok:
            failures.append(f"height: expected {expected_height}, got {actual_height}")
        if not thickness_ok:
            failures.append(f"thickness: expected {expected_thickness}, got {actual_thickness}")

        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"Dimension mismatch: {'; '.join(failures)}",
        )


def _check_item_count(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """
    Check item count.

    This is an informational assertion - the item count is derived from AST
    and serves as metadata. We always pass it since we're not comparing against
    artifact counts (which may differ due to multi-pass operations, etc.).
    """
    return AssertionResult(
        id=assertion.id,
        source=assertion.source,
        intent=assertion.intent,
        expected=assertion.expected,
        actual=assertion.expected,  # Echo back the expected value
        status=Verdict.PASS,
        tolerance=assertion.tolerance,
        message=f"Layout contains {assertion.expected['count']} items",
    )


def _check_profile_exists(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """Check that a profile cut exists in SVG matching the expected geometry."""
    if svg_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No SVG metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify profile exists: SVG metrics not provided",
        )

    # Check PROFILE_CUTS layer has content
    layers = svg_metrics.get("layers", {})
    by_layer = layers.get("by_layer", {})
    profile_layer = by_layer.get("PROFILE_CUTS", {})

    element_count = profile_layer.get("element_count", 0)
    elements = profile_layer.get("elements", [])

    # If no expected geometry info, fall back to existence check
    expected_center = assertion.expected.get("center_xy")
    expected_width = assertion.expected.get("width_mm")
    expected_height = assertion.expected.get("height_mm")
    expected_diameter = assertion.expected.get("diameter_mm")

    actual: dict[str, Any] = {
        "profile_layer_elements": element_count,
        "profile_layer_element_count": len(elements),
    }

    if element_count == 0:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message="Profile layer is empty - expected profile cut geometry",
        )

    # If we have expected geometry, look for a matching element
    # NOTE: SVG uses visualization coordinates with margins, so we match primarily
    # on dimensions rather than absolute position. Position matching is optional.
    if expected_width and expected_height or expected_diameter:
        tol = assertion.tolerance
        match_found = False
        best_match = None
        dim_matches = []

        for elem in elements:
            elem_width = elem.get("width")
            elem_height = elem.get("height")
            elem_radius = elem.get("radius")

            # Check dimensions match (primary matching criterion)
            if expected_width and expected_height and elem_width and elem_height:
                dim_match = (
                    abs(elem_width - expected_width) <= tol and
                    abs(elem_height - expected_height) <= tol
                )
            elif expected_diameter and elem_radius:
                dim_match = abs(elem_radius * 2 - expected_diameter) <= tol
            else:
                dim_match = False

            if dim_match:
                dim_matches.append(elem)
                match_found = True
                best_match = elem
                # Don't break - collect all dimension matches

        actual["matched_element"] = best_match
        actual["dimension_matches_count"] = len(dim_matches)

        if match_found:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.PASS,
                tolerance=assertion.tolerance,
                message=f"Profile geometry found with matching dimensions for '{assertion.expected.get('shape_id')}'",
            )
        else:
            actual["available_elements"] = elements[:5]  # Show first 5 for debugging
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.FAIL,
                tolerance=assertion.tolerance,
                message=f"No profile geometry matches expected dimensions for '{assertion.expected.get('shape_id')}'",
            )
    else:
        # Fallback: just verify element exists
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Profile layer has {element_count} element(s) (geometry matching not possible - missing expected dimensions)",
        )


def _check_profile_side(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """
    Check profile side (inside/outside) is correct.

    For outside profiles, the toolpath should be offset outward from the shape.
    For inside profiles, the toolpath should be offset inward.

    This is checked by examining G-code XY bounds against nominal shape bounds.

    LIMITATION: Uses global G-code bounds, so for multi-item jobs, a large toolpath
    from any item can satisfy the assertion. For reliable per-item validation,
    use single-item G-code files or SVG-based verification.
    """
    if gcode_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No G-code metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify profile side: G-code metrics not provided",
        )

    # Get expected values
    side = assertion.expected.get("side", "outside")
    center_xy = assertion.expected.get("center_xy", (0, 0))
    nominal_width = assertion.expected.get("nominal_width_mm", 0)
    nominal_height = assertion.expected.get("nominal_height_mm", 0)

    # Calculate expected shape bounds
    half_w = nominal_width / 2
    half_h = nominal_height / 2
    shape_x_min = center_xy[0] - half_w
    shape_x_max = center_xy[0] + half_w
    shape_y_min = center_xy[1] - half_h
    shape_y_max = center_xy[1] + half_h

    # Get actual G-code bounds
    xy_bounds = gcode_metrics.get("xy_bounds", {})
    gcode_x_min = xy_bounds.get("x_min", 0)
    gcode_x_max = xy_bounds.get("x_max", 0)
    gcode_y_min = xy_bounds.get("y_min", 0)
    gcode_y_max = xy_bounds.get("y_max", 0)

    actual = {
        "gcode_x_min": gcode_x_min,
        "gcode_x_max": gcode_x_max,
        "gcode_y_min": gcode_y_min,
        "gcode_y_max": gcode_y_max,
        "shape_bounds": {
            "x_min": shape_x_min,
            "x_max": shape_x_max,
            "y_min": shape_y_min,
            "y_max": shape_y_max,
        },
        "note": "Uses global G-code bounds (may include other items)",
    }

    # For outside profile: toolpath bounds should be >= shape bounds
    # For inside profile: toolpath bounds should be <= shape bounds
    # (accounting for tool radius offset)

    # Use a relaxed tolerance for G-code bounds comparison since toolpath
    # offset depends on tool diameter which we don't know here
    gcode_tolerance = max(assertion.tolerance, 10.0)  # Allow up to 10mm for tool offset

    if side == "outside":
        # Outside profile should cut at or outside the shape boundary
        # G-code bounds should be at least as large as shape bounds
        x_ok = gcode_x_min <= shape_x_min + gcode_tolerance and \
               gcode_x_max >= shape_x_max - gcode_tolerance
        y_ok = gcode_y_min <= shape_y_min + gcode_tolerance and \
               gcode_y_max >= shape_y_max - gcode_tolerance

        if x_ok and y_ok:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.PASS,
                tolerance=assertion.tolerance,
                message="Outside profile: G-code bounds encompass shape bounds",
            )
        else:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.FAIL,
                tolerance=assertion.tolerance,
                message="Outside profile: G-code bounds do not encompass shape bounds",
            )
    else:
        # Inside profile should cut at or inside the shape boundary
        x_ok = gcode_x_min >= shape_x_min - gcode_tolerance and \
               gcode_x_max <= shape_x_max + gcode_tolerance
        y_ok = gcode_y_min >= shape_y_min - gcode_tolerance and \
               gcode_y_max <= shape_y_max + gcode_tolerance

        if x_ok and y_ok:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.PASS,
                tolerance=assertion.tolerance,
                message="Inside profile: G-code bounds within shape bounds",
            )
        else:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.FAIL,
                tolerance=assertion.tolerance,
                message="Inside profile: G-code bounds exceed shape bounds",
            )


def _check_pocket_depth(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """Check that pocket depth is present in STL Z levels."""
    if stl_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No STL metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify pocket depth: STL metrics not provided",
        )

    expected_depth = assertion.expected.get("depth_mm", 0)

    # Get Z levels from STL
    z_stats = stl_metrics.get("z_statistics", {})
    unique_z_levels = z_stats.get("unique_z_levels", [])

    # Get sheet thickness from dimensions
    dimensions = stl_metrics.get("dimensions", {})
    thickness_mm = dimensions.get("thickness_mm", 0)

    # Calculate expected Z level for pocket (top of sheet minus pocket depth)
    # Assuming Z=0 at bottom, Z=thickness at top
    expected_z = thickness_mm - expected_depth

    actual = {
        "expected_z_level": expected_z,
        "unique_z_levels": unique_z_levels,
        "thickness_mm": thickness_mm,
    }

    # Check if expected Z level is present in unique Z levels
    found = any(abs(z - expected_z) <= assertion.tolerance for z in unique_z_levels)

    if found:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Pocket depth {expected_depth}mm found at Z={expected_z:.2f}mm",
        )
    else:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"Expected Z level {expected_z:.2f}mm not found in STL (pocket depth {expected_depth}mm)",
        )


def _check_hole_position(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """Check that a hole exists at the expected position in SVG HOLES layer.

    Note: SVG blueprint uses visualization coordinates with a 140mm margin
    and Y-axis flip. This function converts SVG coordinates back to design
    coordinates before comparing with expected values.
    """
    if svg_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No SVG metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify hole position: SVG metrics not provided",
        )

    layers = svg_metrics.get("layers", {})
    by_layer = layers.get("by_layer", {})
    holes_layer = by_layer.get("HOLES", {})

    circle_count = holes_layer.get("circle_count", 0)
    elements = holes_layer.get("elements", [])

    expected_x = assertion.expected.get("center_x_mm")
    expected_y = assertion.expected.get("center_y_mm")
    tol = assertion.tolerance

    document = svg_metrics.get("document", {})
    viewbox = document.get("viewbox", [0, 0, 0, 0])
    viewbox_height = viewbox[3] if len(viewbox) > 3 else 0

    svg_margin = 140.0

    actual: dict[str, Any] = {
        "holes_layer_circles": circle_count,
        "expected_center": (expected_x, expected_y),
        "viewbox_height": viewbox_height,
        "svg_margin": svg_margin,
    }

    if circle_count == 0:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message="No circles found in HOLES layer",
        )

    circles = [e for e in elements if e.get("element_type") == "circle"]

    if not circles:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"HOLES layer has {circle_count} circle(s) but no geometry data available",
        )

    match_found = False
    best_match = None
    min_distance = float("inf")
    best_design_coords = None

    for circle in circles:
        center = circle.get("center", [0, 0])
        svg_x, svg_y = center[0], center[1]

        design_x = svg_x - svg_margin
        design_y = viewbox_height - svg_y - svg_margin

        distance = ((design_x - expected_x) ** 2 + (design_y - expected_y) ** 2) ** 0.5

        if distance < min_distance:
            min_distance = distance
            best_match = circle
            best_design_coords = (design_x, design_y)

        if abs(design_x - expected_x) <= tol and abs(design_y - expected_y) <= tol:
            match_found = True
            best_match = circle
            best_design_coords = (design_x, design_y)
            break

    actual["closest_circle"] = best_match
    actual["closest_distance_mm"] = round(min_distance, 3)
    if best_design_coords:
        actual["closest_design_coords"] = [round(c, 2) for c in best_design_coords]

    if match_found:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Hole found at ({expected_x}, {expected_y})mm within tolerance",
        )
    else:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"No hole found at ({expected_x}, {expected_y})mm; closest is {min_distance:.2f}mm away",
        )


def _check_hole_diameter(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """Check that a hole with expected diameter exists in the HOLES layer of SVG."""
    if svg_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No SVG metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify hole diameter: SVG metrics not provided",
        )

    expected_diameter = assertion.expected.get("diameter_mm", 0)
    expected_radius = expected_diameter / 2
    tol = assertion.tolerance

    # Get circles from HOLES layer specifically (not all SVG circles)
    layers = svg_metrics.get("layers", {})
    by_layer = layers.get("by_layer", {})
    holes_layer = by_layer.get("HOLES", {})
    elements = holes_layer.get("elements", [])

    # Extract radii from circle elements in HOLES layer
    hole_radii = []
    for elem in elements:
        if elem.get("element_type") == "circle":
            r = elem.get("radius")
            if r is not None:
                hole_radii.append(r)

    actual: dict[str, Any] = {
        "expected_diameter_mm": expected_diameter,
        "holes_layer_radii_mm": sorted(set(round(r, 3) for r in hole_radii)),
        "holes_layer_circle_count": len(hole_radii),
    }

    if not hole_radii:
        # Fallback: if no per-element data, check global circles
        # but warn that we can't verify HOLES layer specifically
        circles = svg_metrics.get("circles", {})
        all_radii = circles.get("radii_mm", [])
        actual["all_svg_radii_mm"] = all_radii

        if not all_radii:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.FAIL,
                tolerance=assertion.tolerance,
                message="No circles found in SVG",
            )

        found = any(abs(r - expected_radius) <= tol for r in all_radii)
        if found:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.WARN,
                tolerance=assertion.tolerance,
                message=f"Hole diameter {expected_diameter}mm found, but could not verify HOLES layer",
            )
        else:
            return AssertionResult(
                id=assertion.id,
                source=assertion.source,
                intent=assertion.intent,
                expected=assertion.expected,
                actual=actual,
                status=Verdict.FAIL,
                tolerance=assertion.tolerance,
                message=f"No hole with diameter {expected_diameter}mm found",
            )

    # Check if expected radius is present in HOLES layer
    found = any(abs(r - expected_radius) <= tol for r in hole_radii)

    if found:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Hole with diameter {expected_diameter}mm found in HOLES layer",
        )
    else:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"No hole with diameter {expected_diameter}mm found in HOLES layer",
        )


def _check_through_cut(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """
    Check that through cuts reach full depth in G-code.

    LIMITATION: Uses global max plunge depth from G-code, so for multi-item jobs
    where items have different depths, a deep cut on any item will satisfy all
    through-cut assertions. For reliable per-item depth validation, use separate
    G-code files per item or STL-based depth verification.
    """
    if gcode_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No G-code metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify through cut: G-code metrics not provided",
        )

    target_depth = assertion.expected.get("target_depth_mm", 0)

    # Get max plunge depth from G-code
    z_profile = gcode_metrics.get("z_profile", {})
    max_plunge_z = z_profile.get("max_plunge_z_mm", 0)

    actual = {
        "target_depth_mm": target_depth,
        "max_plunge_z_mm": max_plunge_z,
        "note": "Uses global max plunge depth (may include other items)",
    }

    # Check if max plunge reaches or exceeds target depth
    # Note: depths are negative (below Z=0)
    reaches_target = max_plunge_z <= target_depth + assertion.tolerance

    if reaches_target:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Through cut reaches {max_plunge_z:.2f}mm (target: {target_depth:.2f}mm)",
        )
    else:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.FAIL,
            tolerance=assertion.tolerance,
            message=f"Through cut only reaches {max_plunge_z:.2f}mm, target is {target_depth:.2f}mm",
        )


def _check_tab_count(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    stl_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    """
    Check that tab count matches expected value.

    Tab validation detects lift-cross-plunge sequences in G-code that occur
    at max cutting depth. Each tab causes a Z-lift during feed moves on final
    passes.

    Validates:
    - Detected tab count matches expected tab_count from AST
    - Detected tab heights match expected tab_height_mm (within tolerance)
    """
    expected_tab_count = assertion.expected.get("tab_count", 0)
    expected_tab_height = assertion.expected.get("tab_height_mm")
    tab_width = assertion.expected.get("tab_width_mm")

    if gcode_metrics is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No G-code metrics available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify tab count: G-code metrics not provided",
        )

    tabs_data = gcode_metrics.get("tabs", {})
    detected_count = tabs_data.get("detected_count", 0)
    detected_heights = tabs_data.get("tab_heights_mm", [])
    max_depth = tabs_data.get("max_cutting_depth_mm", 0)
    tabs_at_max = tabs_data.get("tabs_at_max_depth", True)

    actual: dict[str, Any] = {
        "expected_tab_count": expected_tab_count,
        "detected_tab_count": detected_count,
        "expected_tab_height_mm": expected_tab_height,
        "detected_tab_heights_mm": detected_heights,
        "max_cutting_depth_mm": max_depth,
        "tabs_at_max_depth": tabs_at_max,
        "tab_width_mm": tab_width,
    }

    count_matches = detected_count == expected_tab_count

    height_matches = True
    height_message = ""
    if expected_tab_height is not None and detected_heights:
        avg_detected_height = sum(detected_heights) / len(detected_heights)
        height_tolerance = max(assertion.tolerance, 0.5)
        height_matches = abs(avg_detected_height - expected_tab_height) <= height_tolerance
        if not height_matches:
            height_message = f"; height mismatch: expected {expected_tab_height}mm, detected avg {avg_detected_height:.2f}mm"

    if count_matches and height_matches and tabs_at_max:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual=actual,
            status=Verdict.PASS,
            tolerance=assertion.tolerance,
            message=f"Tab count verified: {detected_count} tabs detected at max depth",
        )

    failures = []
    if not count_matches:
        failures.append(f"count: expected {expected_tab_count}, detected {detected_count}")
    if not height_matches:
        failures.append(f"height mismatch{height_message}")
    if not tabs_at_max:
        failures.append("tabs not at max cutting depth")

    return AssertionResult(
        id=assertion.id,
        source=assertion.source,
        intent=assertion.intent,
        expected=assertion.expected,
        actual=actual,
        status=Verdict.FAIL,
        tolerance=assertion.tolerance,
        message=f"Tab verification failed: {'; '.join(failures)}",
    )
