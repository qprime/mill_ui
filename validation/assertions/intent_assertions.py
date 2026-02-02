

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.constants import DepthMode
from layout_ast.layout import LayoutAST, Item, Feature
from validation.core import AssertionResult, Verdict


ASSERTION_IDS = [
    "SHEET_DIMENSIONS",
    "PROFILE_EXISTS",
    "PROFILE_SIDE",
    "HOLE_POSITION",
    "HOLE_DIAMETER",
    "THROUGH_CUT",
    "TAB_COUNT",
    "ITEM_COUNT",
]


DEFAULT_POSITION_TOLERANCE_MM = 0.01
DEFAULT_DEPTH_TOLERANCE_MM = 0.01
DEFAULT_DIMENSION_TOLERANCE_MM = 0.01
DEFAULT_PERCENT_TOLERANCE = 0.001


@dataclass
class IntentAssertion:

    id: str
    source: str
    intent: str
    expected: dict[str, Any]
    tolerance: float = 0.1
    artifact: str = "any"


def derive_assertions(ast: LayoutAST) -> list[IntentAssertion]:
    assertions: list[IntentAssertion] = []


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
        artifact="svg",
    ))


    assertions.append(IntentAssertion(
        id="ITEM_COUNT",
        source="ast:items",
        intent=f"Layout has {len(ast.items)} items",
        expected={"count": len(ast.items)},
        tolerance=0,
        artifact="any",
    ))


    for item in ast.items:
        assertions.extend(_derive_item_assertions(item, ast.sheet.thickness_mm))


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
    assertions: list[IntentAssertion] = []

    if item.feature is None:
        return assertions

    feature = item.feature
    item_id = item.shape_id or item.id or "unnamed"
    source = f"ast:item:{item_id}"


    center_xy = None
    if item.placement:
        center_xy = item.placement.center_xy_mm


    width_mm = None
    height_mm = None
    diameter_mm = None
    if item.geometry and item.geometry.data:
        width_mm = item.geometry.data.get("w_mm")
        height_mm = item.geometry.data.get("h_mm")
        diameter_mm = item.geometry.data.get("diameter_mm")


    if feature.type == "profile":

        expected_profile = {
            "shape_id": item_id,
            "feature_type": "profile",
        }

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
            artifact="svg",
        ))


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


        if feature.is_through:
            assertions.append(IntentAssertion(
                id="THROUGH_CUT",
                source=source,
                intent=f"Through cut for '{item_id}' reaches full depth",
                expected={
                    "shape_id": item_id,
                    "target_depth_mm": -sheet_thickness_mm,
                },
                tolerance=DEFAULT_DEPTH_TOLERANCE_MM,
                artifact="gcode",
            ))


    elif feature.type == "hole":

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
                artifact="svg",
            ))


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


        if feature.is_through:
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


def _resolve_depth(feature: Feature, sheet_thickness_mm: float) -> float:
    if feature.is_through:
        return sheet_thickness_mm
    return feature.depth_mm


def _unwrap_metrics(metrics: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    if metrics is None:
        return None

    if key in metrics and isinstance(metrics[key], dict):
        return metrics[key]

    return metrics


def check_assertions(
    assertions: list[IntentAssertion],
    svg_metrics: dict[str, Any] | None = None,
    gcode_metrics: dict[str, Any] | None = None,
) -> list[AssertionResult]:

    svg_unwrapped = _unwrap_metrics(svg_metrics, "svg")
    gcode_unwrapped = _unwrap_metrics(gcode_metrics, "gcode")

    results: list[AssertionResult] = []

    for assertion in assertions:
        result = _check_single_assertion(
            assertion,
            svg_metrics=svg_unwrapped,
            gcode_metrics=gcode_unwrapped,
        )
        results.append(result)

    return results


def _check_single_assertion(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:


    checkers = {
        "SHEET_DIMENSIONS": _check_sheet_dimensions,
        "ITEM_COUNT": _check_item_count,
        "PROFILE_EXISTS": _check_profile_exists,
        "PROFILE_SIDE": _check_profile_side,
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
        gcode_metrics=gcode_metrics,
    )


def _check_sheet_dimensions(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    expected_width = assertion.expected["width_mm"]
    expected_height = assertion.expected["height_mm"]
    tol = assertion.tolerance

    actual: dict[str, Any] = {}
    actual_width = None
    actual_height = None
    source = None


    if svg_metrics is not None:
        layers = svg_metrics.get("layers", {})
        by_layer = layers.get("by_layer", {})
        sheet_outline = by_layer.get("SHEET_OUTLINE", {})
        elements = sheet_outline.get("elements", [])

        if elements:
            elem = elements[0]
            actual_width = elem.get("width")
            actual_height = elem.get("height")
            source = "svg_sheet_outline"
            actual["source"] = source
            actual["sheet_outline_element"] = elem

    if actual_width is None:
        return AssertionResult(
            id=assertion.id,
            source=assertion.source,
            intent=assertion.intent,
            expected=assertion.expected,
            actual={"error": "No dimension data available"},
            status=Verdict.WARN,
            tolerance=assertion.tolerance,
            message="Cannot verify sheet dimensions: no SVG metrics provided",
        )

    actual["width_mm"] = actual_width
    actual["height_mm"] = actual_height

    width_ok = abs(actual_width - expected_width) <= tol
    height_ok = abs(actual_height - expected_height) <= tol

    all_ok = width_ok and height_ok

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
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
    return AssertionResult(
        id=assertion.id,
        source=assertion.source,
        intent=assertion.intent,
        expected=assertion.expected,
        actual=assertion.expected,
        status=Verdict.PASS,
        tolerance=assertion.tolerance,
        message=f"Layout contains {assertion.expected['count']} items",
    )


def _check_profile_exists(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
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


    layers = svg_metrics.get("layers", {})
    by_layer = layers.get("by_layer", {})
    profile_layer = by_layer.get("PROFILE_CUTS", {})

    element_count = profile_layer.get("element_count", 0)
    elements = profile_layer.get("elements", [])


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


    if expected_width and expected_height or expected_diameter:
        tol = assertion.tolerance
        match_found = False
        best_match = None
        dim_matches = []

        for elem in elements:
            elem_width = elem.get("width")
            elem_height = elem.get("height")
            elem_radius = elem.get("radius")


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
            actual["available_elements"] = elements[:5]
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
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
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


    side = assertion.expected.get("side", "outside")
    center_xy = assertion.expected.get("center_xy", (0, 0))
    nominal_width = assertion.expected.get("nominal_width_mm", 0)
    nominal_height = assertion.expected.get("nominal_height_mm", 0)


    half_w = nominal_width / 2
    half_h = nominal_height / 2
    shape_x_min = center_xy[0] - half_w
    shape_x_max = center_xy[0] + half_w
    shape_y_min = center_xy[1] - half_h
    shape_y_max = center_xy[1] + half_h


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


    gcode_tolerance = max(assertion.tolerance, 10.0)

    if side == "outside":


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


def _check_hole_position(
    assertion: IntentAssertion,
    svg_metrics: dict[str, Any] | None,
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
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
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
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


    layers = svg_metrics.get("layers", {})
    by_layer = layers.get("by_layer", {})
    holes_layer = by_layer.get("HOLES", {})
    elements = holes_layer.get("elements", [])


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
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
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


    z_profile = gcode_metrics.get("z_profile", {})
    max_plunge_z = z_profile.get("max_plunge_z_mm", 0)

    actual = {
        "target_depth_mm": target_depth,
        "max_plunge_z_mm": max_plunge_z,
        "note": "Uses global max plunge depth (may include other items)",
    }


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
    gcode_metrics: dict[str, Any] | None,
) -> AssertionResult:
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
