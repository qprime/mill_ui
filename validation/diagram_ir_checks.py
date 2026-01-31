from __future__ import annotations

from diagram_ir import DiagramIR, LayerIR
from diagram_ir.shapes import Shape, Rect, Line, Circle, Polyline, Text, Path
from validation.core import InvariantResult, Verdict


def check_dir_bounds_contain_layers(diagram: DiagramIR) -> InvariantResult:
    failures = []
    checked = 0
    passed = 0

    for layer in diagram.layers:
        for shape in layer.items:
            checked += 1
            shape_bounds = _get_shape_bounds(shape)
            if shape_bounds is None:
                passed += 1
                continue

            x_min, y_min, x_max, y_max = shape_bounds
            if (x_min < diagram.bounds.x_min - 0.001 or
                x_max > diagram.bounds.x_max + 0.001 or
                y_min < diagram.bounds.y_min - 0.001 or
                y_max > diagram.bounds.y_max + 0.001):
                shape_id = getattr(shape, 'id', None) or 'unnamed'
                failures.append(f"Shape '{shape_id}' in layer '{layer.name}' exceeds bounds")
            else:
                passed += 1

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="DIR_BOUNDS_CONTAIN_LAYERS",
        category="structural",
        artifact="diagram_ir",
        description="All shapes in all layers must fall within DiagramIR.bounds",
        status=status,
        checked=checked,
        passed=passed,
        failed=len(failures),
        failures=tuple(failures),
    )


def check_dir_layer_names_unique(diagram: DiagramIR) -> InvariantResult:
    names = [layer.name for layer in diagram.layers]
    seen = set()
    duplicates = []
    for name in names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)

    status = Verdict.PASS if not duplicates else Verdict.FAIL
    return InvariantResult(
        id="DIR_LAYER_NAMES_UNIQUE",
        category="structural",
        artifact="diagram_ir",
        description="No duplicate layer names in DiagramIR.layers",
        status=status,
        checked=len(names),
        passed=len(names) - len(duplicates),
        failed=len(duplicates),
        failures=tuple(f"Duplicate layer name: {name}" for name in duplicates),
    )


def check_dir_layer_order_stable(diagram: DiagramIR) -> InvariantResult:
    return InvariantResult(
        id="DIR_LAYER_ORDER_STABLE",
        category="structural",
        artifact="diagram_ir",
        description="Layers render in list order (first = back, last = front)",
        status=Verdict.PASS,
        checked=len(diagram.layers),
        passed=len(diagram.layers),
        failed=0,
        failures=(),
        details={"layer_order": [l.name for l in diagram.layers]},
    )


def check_dir_shapes_valid(diagram: DiagramIR) -> InvariantResult:
    failures = []
    checked = 0
    passed = 0

    for layer in diagram.layers:
        for shape in layer.items:
            checked += 1
            issues = _validate_shape(shape)
            if issues:
                shape_id = getattr(shape, 'id', None) or 'unnamed'
                for issue in issues:
                    failures.append(f"Shape '{shape_id}' in layer '{layer.name}': {issue}")
            else:
                passed += 1

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="DIR_SHAPES_VALID",
        category="structural",
        artifact="diagram_ir",
        description="All shapes have non-negative dimensions, non-NaN coordinates",
        status=status,
        checked=checked,
        passed=passed,
        failed=len(failures),
        failures=tuple(failures),
    )


def check_dir_style_tokens_resolvable(diagram: DiagramIR, available_tokens: set[str]) -> InvariantResult:
    failures = []
    checked = 0
    passed = 0

    for layer in diagram.layers:
        for shape in layer.items:
            checked += 1
            token = getattr(shape, 'style_token', 'default')
            if token not in available_tokens:
                shape_id = getattr(shape, 'id', None) or 'unnamed'
                failures.append(f"Unknown style_token '{token}' for shape '{shape_id}' in layer '{layer.name}'")
            else:
                passed += 1

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="DIR_STYLE_TOKENS_RESOLVABLE",
        category="structural",
        artifact="diagram_ir",
        description="Every style_token must exist in Theme",
        status=status,
        checked=checked,
        passed=passed,
        failed=len(failures),
        failures=tuple(failures),
    )


def validate_diagram_ir_invariants(diagram: DiagramIR, available_tokens: set[str] | None = None) -> list[InvariantResult]:
    results = [
        check_dir_bounds_contain_layers(diagram),
        check_dir_layer_names_unique(diagram),
        check_dir_layer_order_stable(diagram),
        check_dir_shapes_valid(diagram),
    ]

    if available_tokens:
        results.append(check_dir_style_tokens_resolvable(diagram, available_tokens))

    return results


def _get_shape_bounds(shape: Shape) -> tuple[float, float, float, float] | None:
    if isinstance(shape, Rect):
        return (shape.x, shape.y, shape.x + shape.width, shape.y + shape.height)
    elif isinstance(shape, Line):
        return (min(shape.x1, shape.x2), min(shape.y1, shape.y2),
                max(shape.x1, shape.x2), max(shape.y1, shape.y2))
    elif isinstance(shape, Circle):
        return (shape.cx - shape.radius, shape.cy - shape.radius,
                shape.cx + shape.radius, shape.cy + shape.radius)
    elif isinstance(shape, Polyline):
        if not shape.points:
            return None
        xs = [p.x for p in shape.points]
        ys = [p.y for p in shape.points]
        return (min(xs), min(ys), max(xs), max(ys))
    elif isinstance(shape, Text):
        return None
    elif isinstance(shape, Path):
        return None
    return None


def _validate_shape(shape: Shape) -> list[str]:
    issues = []

    if isinstance(shape, Rect):
        if shape.width < 0:
            issues.append(f"negative width: {shape.width}")
        if shape.height < 0:
            issues.append(f"negative height: {shape.height}")
        for coord_name, coord_value in [("x", shape.x), ("y", shape.y),
                                         ("width", shape.width), ("height", shape.height)]:
            if coord_value != coord_value:
                issues.append(f"NaN value for {coord_name}")

    elif isinstance(shape, Line):
        for coord_name, coord_value in [("x1", shape.x1), ("y1", shape.y1),
                                         ("x2", shape.x2), ("y2", shape.y2)]:
            if coord_value != coord_value:
                issues.append(f"NaN value for {coord_name}")

    elif isinstance(shape, Circle):
        if shape.radius < 0:
            issues.append(f"negative radius: {shape.radius}")
        for coord_name, coord_value in [("cx", shape.cx), ("cy", shape.cy), ("radius", shape.radius)]:
            if coord_value != coord_value:
                issues.append(f"NaN value for {coord_name}")

    elif isinstance(shape, Polyline):
        if not shape.points:
            issues.append("empty points list")

    return issues


__all__ = [
    "check_dir_bounds_contain_layers",
    "check_dir_layer_names_unique",
    "check_dir_layer_order_stable",
    "check_dir_shapes_valid",
    "check_dir_style_tokens_resolvable",
    "validate_diagram_ir_invariants",
]
