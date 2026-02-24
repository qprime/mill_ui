from __future__ import annotations

from core.constants import DepthMode
from layout_ast.layout import Feature, Item, LayoutAST


def format_pml(ast: LayoutAST) -> str:
    lines: list[str] = []

    lines.append(
        f"sheet {ast.sheet.width_mm:.2f}mm {ast.sheet.height_mm:.2f}mm {ast.sheet.thickness_mm:.2f}mm margin {ast.sheet.margin_mm:.2f}mm"
    )
    lines.append("")

    if ast.project:
        lines.append(f"project {ast.project}")
    if ast.kerf_width_mm is not None:
        lines.append(f"kerf {ast.kerf_width_mm:.2f}mm")
    if ast.project or ast.kerf_width_mm:
        lines.append("")

    for item in ast.items:
        if item.kind == "shape":
            if not item.feature:
                continue
            lines.append(_format_shape(item))
        else:
            continue

    return "\n".join(lines) + "\n"


def _format_shape(item: Item) -> str:
    if not item.geometry or not item.placement or not item.feature:
        raise ValueError(f"Shape item missing required fields: {item}")

    shape_id = item.shape_id or "unnamed"
    cx, cy = item.placement.center_xy_mm
    feature_str = _format_feature(item.feature)

    if item.type == "Rect":
        w = item.geometry.data.get("w_mm", 0.0)
        h = item.geometry.data.get("h_mm", 0.0)
        return f"rect {shape_id} at {cx:.2f}mm,{cy:.2f}mm size {w:.2f}mm,{h:.2f}mm {feature_str}"

    elif item.type == "Circle":
        if "diameter_mm" in item.geometry.data:
            diameter = item.geometry.data["diameter_mm"]
            return f"circle {shape_id} at {cx:.2f}mm,{cy:.2f}mm diameter {diameter:.2f}mm {feature_str}"
        elif "radius_mm" in item.geometry.data:
            radius = item.geometry.data["radius_mm"]
            return f"circle {shape_id} at {cx:.2f}mm,{cy:.2f}mm radius {radius:.2f}mm {feature_str}"
        else:
            raise ValueError(f"Circle geometry missing diameter_mm or radius_mm: {item.geometry.data}")

    elif item.type == "RoundedRect":
        w = item.geometry.data.get("w_mm", 0.0)
        h = item.geometry.data.get("h_mm", 0.0)
        radius = item.geometry.data.get("corner_radius_mm", 0.0)
        return f"roundedrect {shape_id} at {cx:.2f}mm,{cy:.2f}mm size {w:.2f}mm,{h:.2f}mm radius {radius:.2f}mm {feature_str}"

    else:
        return f"# Unknown shape type: {item.type}"


def _format_feature(feature: Feature) -> str:
    feature_type = feature.type

    depth_str = DepthMode.THROUGH if feature.is_through else f"{feature.depth_mm:.2f}mm"

    result = f"{feature_type} {depth_str}"

    if feature_type == "profile" and feature.side:
        result = f"{result} {feature.side}"

    if feature_type == "profile" and feature.tab_count is not None and feature.tab_height_mm is not None:
        result = f"{result} tabs {feature.tab_count} height {feature.tab_height_mm:.2f}mm"
        if feature.tab_width_mm is not None:
            result = f"{result} width {feature.tab_width_mm:.2f}mm"

    if feature_type == "pocket" and feature.corner_cleanup_tool_diameter_mm is not None:
        result = f"{result} corner_cleanup {feature.corner_cleanup_tool_diameter_mm:.2f}mm"

    return result
