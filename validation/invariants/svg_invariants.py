from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from validation.core import InvariantResult, Verdict
from validation.metrics.svg_metrics import SVG_NS, SVGMetrics

SVG_INVARIANT_IDS = [
    "SVG_VALID_XML",
    "SVG_HAS_VIEWBOX",
    "SVG_POSITIVE_DIMENSIONS",
    "SVG_PATHS_VALID",
    "SVG_CLOSED_PROFILES",
    "SVG_CLOSED_POCKETS",
    "SVG_NO_EMPTY_LAYERS",
    "SVG_DIMENSIONS_PRESENT",
    "SVG_BOUNDS_WITHIN_VIEWBOX",
]


CONTENT_LAYERS = ["SHEET_OUTLINE", "PROFILE_CUTS", "POCKET_REGIONS"]


def _is_polyline_closed(points: str, tolerance: float = 0.01) -> bool:
    if not points:
        return False

    coords = re.split(r"[\s,]+", points.strip())
    if len(coords) < 4:
        return False

    try:
        first_x, first_y = float(coords[0]), float(coords[1])
        last_x, last_y = float(coords[-2]), float(coords[-1])

        dist = ((last_x - first_x) ** 2 + (last_y - first_y) ** 2) ** 0.5
        return dist < tolerance
    except (ValueError, IndexError):
        return False


def check_svg_invariants(
    svg_content: str | bytes,
    metrics: SVGMetrics | None = None,
    expected_layers: list[str] | None = None,
) -> list[InvariantResult]:
    results: list[InvariantResult] = []

    if isinstance(svg_content, bytes):
        svg_content = svg_content.decode("utf-8")

    xml_result, root = _check_valid_xml(svg_content)
    results.append(xml_result)

    if root is None:
        return results

    if metrics is None:
        from validation.metrics.svg_metrics import extract_svg_metrics

        try:
            metrics = extract_svg_metrics(svg_content)
        except Exception as e:
            results.append(
                InvariantResult(
                    id="SVG_METRICS_ERROR",
                    category="structural",
                    artifact="svg",
                    description="Metrics extraction failed",
                    status=Verdict.FAIL,
                    details={"error": str(e)},
                )
            )
            return results

    results.append(_check_has_viewbox(root, metrics))

    results.append(_check_positive_dimensions(metrics))

    results.append(_check_paths_valid(root))

    results.append(_check_closed_profiles(root, metrics))

    results.append(_check_closed_pockets(root, metrics))

    results.append(_check_no_empty_layers(metrics, expected_layers))

    results.append(_check_dimensions_present(metrics))

    results.append(_check_bounds_within_viewbox(metrics))

    return results


def _check_valid_xml(svg_content: str) -> tuple[InvariantResult, ET.Element | None]:
    try:
        root = ET.fromstring(svg_content)
        return (
            InvariantResult(
                id="SVG_VALID_XML",
                category="structural",
                artifact="svg",
                description="SVG parses as valid XML",
                status=Verdict.PASS,
                checked=1,
                passed=1,
            ),
            root,
        )
    except ET.ParseError as e:
        return (
            InvariantResult(
                id="SVG_VALID_XML",
                category="structural",
                artifact="svg",
                description="SVG parses as valid XML",
                status=Verdict.FAIL,
                checked=1,
                failed=1,
                failures=(f"XML parse error: {e}",),
            ),
            None,
        )


def _check_has_viewbox(root: ET.Element, metrics: SVGMetrics) -> InvariantResult:
    viewbox = root.get("viewBox")
    vb = metrics.document.viewbox

    if viewbox and vb[2] > 0 and vb[3] > 0:
        return InvariantResult(
            id="SVG_HAS_VIEWBOX",
            category="structural",
            artifact="svg",
            description="Document has viewBox attribute",
            status=Verdict.PASS,
            checked=1,
            passed=1,
            details={"viewbox": list(vb)},
        )
    else:
        return InvariantResult(
            id="SVG_HAS_VIEWBOX",
            category="structural",
            artifact="svg",
            description="Document has viewBox attribute",
            status=Verdict.FAIL,
            checked=1,
            failed=1,
            failures=("Missing or invalid viewBox attribute",),
        )


def _check_positive_dimensions(metrics: SVGMetrics) -> InvariantResult:
    width = metrics.document.width_mm
    height = metrics.document.height_mm

    if width > 0 and height > 0:
        return InvariantResult(
            id="SVG_POSITIVE_DIMENSIONS",
            category="structural",
            artifact="svg",
            description="Width and height > 0",
            status=Verdict.PASS,
            checked=2,
            passed=2,
            details={"width_mm": width, "height_mm": height},
        )
    else:
        failures = []
        if width <= 0:
            failures.append(f"Width is not positive: {width}")
        if height <= 0:
            failures.append(f"Height is not positive: {height}")
        return InvariantResult(
            id="SVG_POSITIVE_DIMENSIONS",
            category="structural",
            artifact="svg",
            description="Width and height > 0",
            status=Verdict.FAIL,
            checked=2,
            passed=2 - len(failures),
            failed=len(failures),
            failures=tuple(failures),
        )


def _check_paths_valid(root: ET.Element) -> InvariantResult:
    checked = 0
    passed = 0
    failures: list[str] = []

    for path in root.iter(f"{SVG_NS}path"):
        checked += 1
        d = path.get("d", "")

        if not d or not d.strip():
            failures.append("Path has empty d attribute")
            continue

        d_clean = d.strip()
        if d_clean[0].upper() != "M":
            failures.append(f"Path d attribute doesn't start with M: {d_clean[:20]}...")
            continue

        if re.search(r"[^MmLlHhVvCcSsQqTtAaZz0-9.,\s\-+eE]", d_clean):
            failures.append("Path has invalid characters in d attribute")
            continue

        passed += 1

    if checked == 0:
        return InvariantResult(
            id="SVG_PATHS_VALID",
            category="structural",
            artifact="svg",
            description="All path elements have valid d attribute",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No path elements found"},
        )

    status = Verdict.PASS if len(failures) == 0 else Verdict.FAIL
    return InvariantResult(
        id="SVG_PATHS_VALID",
        category="structural",
        artifact="svg",
        description="All path elements have valid d attribute",
        status=status,
        checked=checked,
        passed=passed,
        failed=len(failures),
        failures=tuple(failures),
    )


def _check_closed_profiles(root: ET.Element, metrics: SVGMetrics) -> InvariantResult:
    return _check_closed_layer(
        root,
        layer_id="PROFILE_CUTS",
        invariant_id="SVG_CLOSED_PROFILES",
        description="Profile cut geometry is closed",
        element_prefix="Profile",
    )


def _check_closed_pockets(root: ET.Element, metrics: SVGMetrics) -> InvariantResult:
    return _check_closed_layer(
        root,
        layer_id="POCKET_REGIONS",
        invariant_id="SVG_CLOSED_POCKETS",
        description="Pocket region geometry is closed",
        element_prefix="Pocket",
    )


def _check_closed_layer(
    root: ET.Element,
    *,
    layer_id: str,
    invariant_id: str,
    description: str,
    element_prefix: str,
) -> InvariantResult:
    checked = 0
    passed = 0
    failures: list[str] = []

    layer = None
    for group in root.iter(f"{SVG_NS}g"):
        if group.get("id") == layer_id:
            layer = group
            break

    if layer is None:
        return InvariantResult(
            id=invariant_id,
            category="structural",
            artifact="svg",
            description=description,
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": f"No {layer_id} layer found"},
        )

    for path in layer.iter(f"{SVG_NS}path"):
        checked += 1
        d = path.get("d", "").strip()
        if d.upper().endswith("Z"):
            passed += 1
        else:
            failures.append(f"{element_prefix} path is not closed (missing Z): {d[:30]}...")

    for tag in ("rect", "circle", "polygon", "ellipse"):
        for _ in layer.iter(f"{SVG_NS}{tag}"):
            checked += 1
            passed += 1

    for polyline in layer.iter(f"{SVG_NS}polyline"):
        checked += 1
        points = polyline.get("points", "").strip()
        if _is_polyline_closed(points):
            passed += 1
        else:
            failures.append(f"{element_prefix} polyline is not closed: {points[:30]}...")

    if checked == 0:
        return InvariantResult(
            id=invariant_id,
            category="structural",
            artifact="svg",
            description=description,
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": f"{layer_id} layer is empty"},
        )

    status = Verdict.PASS if len(failures) == 0 else Verdict.FAIL
    return InvariantResult(
        id=invariant_id,
        category="structural",
        artifact="svg",
        description=description,
        status=status,
        checked=checked,
        passed=passed,
        failed=len(failures),
        failures=tuple(failures),
    )


def _check_no_empty_layers(
    metrics: SVGMetrics,
    expected_layers: list[str] | None = None,
) -> InvariantResult:
    if expected_layers is None:
        expected_layers = ["SHEET_OUTLINE"]

    checked = 0
    passed = 0
    failures: list[str] = []

    for layer_name in expected_layers:
        checked += 1

        if layer_name not in metrics.layers:
            failures.append(f"Expected layer '{layer_name}' is missing from document")
            continue

        layer = metrics.layers[layer_name]

        if layer.element_count > 0:
            passed += 1
        else:
            failures.append(f"Layer '{layer_name}' exists but is empty")

    if checked == 0:
        return InvariantResult(
            id="SVG_NO_EMPTY_LAYERS",
            category="structural",
            artifact="svg",
            description="Expected content layers exist and contain elements",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No expected layers specified"},
        )

    status = Verdict.PASS if len(failures) == 0 else Verdict.WARN
    return InvariantResult(
        id="SVG_NO_EMPTY_LAYERS",
        category="structural",
        artifact="svg",
        description="Expected content layers exist and contain elements",
        status=status,
        checked=checked,
        passed=passed,
        failed=len(failures),
        failures=tuple(failures),
    )


def _check_dimensions_present(metrics: SVGMetrics) -> InvariantResult:
    dim_count = len(metrics.text.dimension_labels)

    dim_layer_count = metrics.layers.get("DIMENSIONS", None)
    dim_layer_elements = dim_layer_count.element_count if dim_layer_count else 0

    if dim_count > 0 or dim_layer_elements > 0:
        return InvariantResult(
            id="SVG_DIMENSIONS_PRESENT",
            category="structural",
            artifact="svg",
            description="At least one dimension annotation exists",
            status=Verdict.PASS,
            checked=1,
            passed=1,
            details={
                "dimension_labels": dim_count,
                "dimension_layer_elements": dim_layer_elements,
            },
        )
    else:
        return InvariantResult(
            id="SVG_DIMENSIONS_PRESENT",
            category="structural",
            artifact="svg",
            description="At least one dimension annotation exists",
            status=Verdict.WARN,
            checked=1,
            failed=1,
            failures=("No dimension annotations found",),
            details={"note": "SVG has no dimension labels or DIMENSIONS layer content"},
        )


def _check_bounds_within_viewbox(metrics: SVGMetrics) -> InvariantResult:
    vb = metrics.document.viewbox
    bounds = metrics.bounds

    vb_x_min = vb[0]
    vb_y_min = vb[1]
    vb_x_max = vb[0] + vb[2]
    vb_y_max = vb[1] + vb[3]

    failures: list[str] = []

    if bounds.x_min == 0 and bounds.x_max == 0 and bounds.y_min == 0 and bounds.y_max == 0:
        return InvariantResult(
            id="SVG_BOUNDS_WITHIN_VIEWBOX",
            category="structural",
            artifact="svg",
            description="Content bounds within viewBox",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No content bounds detected"},
        )

    tolerance = 0.1

    if bounds.x_min < vb_x_min - tolerance:
        failures.append(f"Content x_min ({bounds.x_min}) < viewBox x_min ({vb_x_min})")
    if bounds.x_max > vb_x_max + tolerance:
        failures.append(f"Content x_max ({bounds.x_max}) > viewBox x_max ({vb_x_max})")
    if bounds.y_min < vb_y_min - tolerance:
        failures.append(f"Content y_min ({bounds.y_min}) < viewBox y_min ({vb_y_min})")
    if bounds.y_max > vb_y_max + tolerance:
        failures.append(f"Content y_max ({bounds.y_max}) > viewBox y_max ({vb_y_max})")

    if len(failures) == 0:
        return InvariantResult(
            id="SVG_BOUNDS_WITHIN_VIEWBOX",
            category="structural",
            artifact="svg",
            description="Content bounds within viewBox",
            status=Verdict.PASS,
            checked=4,
            passed=4,
            details={
                "viewbox": list(vb),
                "bounds": {
                    "x_min": bounds.x_min,
                    "x_max": bounds.x_max,
                    "y_min": bounds.y_min,
                    "y_max": bounds.y_max,
                },
            },
        )
    else:
        return InvariantResult(
            id="SVG_BOUNDS_WITHIN_VIEWBOX",
            category="structural",
            artifact="svg",
            description="Content bounds within viewBox",
            status=Verdict.FAIL,
            checked=4,
            passed=4 - len(failures),
            failed=len(failures),
            failures=tuple(failures),
        )
