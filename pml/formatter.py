"""PML (Panel Machining Language) formatter: LayoutAST → PML.

Emits canonical PML from LayoutAST.
"""

from __future__ import annotations

from layout_ast.layout import LayoutAST, Item, Feature


def format_pml(ast: LayoutAST) -> str:
    """Format LayoutAST as canonical PML text.

    Args:
        ast: LayoutAST to format

    Returns:
        Canonical PML string

    Note:
        Produces canonical formatting:
        - 2 decimal places for dimensions
        - Consistent spacing
        - Sheet declaration first, then metadata, then items
        - Comments are not preserved (semantic equivalence only)
    """
    lines: list[str] = []

    # 1. Sheet declaration (required)
    lines.append(
        f"sheet {ast.sheet.width_mm:.2f}mm {ast.sheet.height_mm:.2f}mm {ast.sheet.thickness_mm:.2f}mm"
    )
    lines.append("")

    # 2. Optional metadata
    if ast.project:
        lines.append(f"project {ast.project}")
    if ast.kerf_width_mm is not None:
        lines.append(f"kerf {ast.kerf_width_mm:.2f}mm")
    if ast.project or ast.kerf_width_mm:
        lines.append("")

    # 3. Items (shapes and templates)
    for item in ast.items:
        if item.kind == "shape":
            lines.append(_format_shape(item))
        elif item.kind == "template":
            lines.append(_format_template(item))
        else:
            # Unknown kind, skip
            continue

    return "\n".join(lines) + "\n"


def _format_shape(item: Item) -> str:
    """Format shape Item as PML line."""
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
        # Prefer diameter if available, otherwise compute from radius
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
        # Unknown shape type, use generic representation
        return f"# Unknown shape type: {item.type}"


def _format_template(item: Item) -> str:
    """Format template Item as PML line.

    NOTE: Template formatting is simplified for Phase 2.
    Multi-line param dict formatting not yet implemented.
    """
    template_id = item.id or "unnamed"
    return f"# template {item.type} {template_id} (template formatting not yet implemented)"


def _format_feature(feature: Feature) -> str:
    """Format Feature as PML feature string."""
    feature_type = feature.type

    # Format depth
    if feature.depth == "through":
        depth_str = "through"
    elif feature.depth_mm is not None:
        depth_str = f"{feature.depth_mm:.2f}mm"
    else:
        # Fallback: use depth as string
        depth_str = str(feature.depth)
        if not depth_str.endswith("mm") and depth_str != "through":
            depth_str = f"{depth_str}mm"

    # Add optional side for profiles
    if feature_type == "profile" and feature.side:
        return f"{feature_type} {depth_str} {feature.side}"
    else:
        return f"{feature_type} {depth_str}"
