
from __future__ import annotations

from typing import Any

from layout_ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    Split,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    Circle,
    RoundedRect,
    Line,
    Polyline,
    SplinePath,
    Keepout,
    Edge,
    CompositionalLayoutAST,
    # Stage 12 generator nodes
    ProfileGen,
    PocketGen,
    RaisedPanelGen,
    ChamferGen,
    WaveGen,
    SplitHorizontal,
    SplitVertical,
    SplitGrid,
)


def format_compositional_pml(ast: CompositionalLayoutAST) -> str:
    lines = []


    lines.append(f"sheet {ast.sheet.width_mm:.2f}mm {ast.sheet.height_mm:.2f}mm {ast.sheet.thickness_mm:.2f}mm margin {ast.sheet.margin_mm:.2f}mm")
    lines.append("")


    if ast.project:
        lines.append(f"project {ast.project}")
        lines.append("")


    for name in sorted(ast.components.keys()):
        comp_def = ast.components[name]
        lines.append(f"component {name}")
        lines.extend(_format_node(comp_def.body, indent=1))
        lines.append("")


    lines.extend(_format_node(ast.root, indent=0))

    return "\n".join(lines)


def _format_node(node: Any, indent: int = 0) -> list[str]:
    prefix = "    " * indent
    lines = []

    if isinstance(node, Panel):

        for child in node.children:
            lines.extend(_format_node(child, indent))

    elif isinstance(node, Rect):

        parts = ["rect"]
        if node.id:
            parts.append(node.id)
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))


        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Circle):

        parts = ["circle"]
        if node.id:
            parts.append(node.id)
        if node.diameter_mm is not None:
            parts.append(f"diameter {node.diameter_mm:.2f}mm")
        else:
            parts.append("fit")
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))


        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, RoundedRect):

        parts = ["rounded_rect"]
        if node.id:
            parts.append(node.id)
        parts.append(f"radius {node.radius_mm:.2f}mm")
        if node.corners is not None:
            corner_order = ['tl', 'tr', 'bl', 'br']
            sorted_corners = [c for c in corner_order if c in node.corners]
            parts.append("corners")
            parts.extend(sorted_corners)
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))


        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Line):

        parts = ["line"]
        if node.id:
            parts.append(node.id)
        parts.append(node.orientation)
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))

    elif isinstance(node, Polyline):

        parts = ["polyline"]
        if node.id:
            parts.append(node.id)
        parts.append("points")


        point_strs = []
        for x, y in node.points:
            point_strs.append(f"({x:.2f},{y:.2f})")
        parts.extend(point_strs)

        if node.feature:
            parts.append(_format_feature(node.feature))

        lines.append(prefix + " ".join(parts))

    elif isinstance(node, SplinePath):

        parts = ["spline"]
        if node.id:
            parts.append(node.id)


        if node.feature:
            parts.append(_format_feature(node.feature))

        parts.append("points")


        point_strs = []
        for x, y in node.points:
            point_strs.append(f"({x:.2f},{y:.2f})")
        parts.extend(point_strs)


        if node.tolerance_mm != 0.1:
            parts.append(f"tolerance {node.tolerance_mm:.2f}mm")

        lines.append(prefix + " ".join(parts))

    elif isinstance(node, Keepout):


        parts = ["keepout"]
        if node.id:
            parts.append(node.id)
        lines.append(prefix + " ".join(parts))


        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Edge):


        parts = ["edge", node.treatment_type]

        if node.treatment_type == "allowance":
            parts.append(f"{node.rough_allowance_mm:.2f}mm")
            parts.append(f"{node.finish_allowance_mm:.2f}mm")
        elif node.treatment_type == "fillet":
            parts.append(f"{node.radius_mm:.2f}mm")
        elif node.treatment_type == "chamfer":
            parts.append(f"{node.distance_mm:.2f}mm")

        if node.id:
            parts.append(node.id)

        lines.append(prefix + " ".join(parts))

    elif isinstance(node, Inset):

        lines.append(f"{prefix}inset {node.amount_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Frame):

        lines.append(f"{prefix}frame {node.width_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Grid):

        lines.append(f"{prefix}grid {node.rows} {node.cols} gap {node.gap_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Split):

        lines.append(f"{prefix}split {node.rows} {node.cols} rail {node.rail_mm:.2f}mm mullion {node.mullion_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Cell):

        lines.append(f"{prefix}cell")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Place):

        if isinstance(node.layout, Grid):
            grid = node.layout
            lines.append(f"{prefix}place grid {grid.rows} {grid.cols} gap {grid.gap_mm:.2f}mm")
        else:
            lines.append(f"{prefix}place")

        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, UseComponent):

        lines.append(f"{prefix}use {node.component_name}")

    # =========================================================================
    # Stage 12 Generator Nodes
    # =========================================================================

    elif isinstance(node, ProfileGen):
        depth_str = "through" if node.depth == "through" else f"{node.depth:.2f}mm"
        lines.append(f"{prefix}profile {node.side} {depth_str}")

    elif isinstance(node, PocketGen):
        lines.append(f"{prefix}pocket {node.depth_mm:.2f}mm")

    elif isinstance(node, RaisedPanelGen):
        lines.append(
            f"{prefix}raised_panel border {node.border_width_mm:.2f}mm "
            f"border_depth {node.border_depth_mm:.2f}mm "
            f"field_depth {node.field_depth_mm:.2f}mm"
        )

    elif isinstance(node, ChamferGen):
        lines.append(f"{prefix}chamfer {node.width_mm:.2f}mm {node.depth_mm:.2f}mm")

    elif isinstance(node, WaveGen):
        lines.append(
            f"{prefix}wave count {node.wave_count} "
            f"amplitude {node.amplitude_mm:.2f}mm "
            f"wavelength {node.wavelength_mm:.2f}mm "
            f"groove {node.groove_width_mm:.2f}mm "
            f"depth {node.depth_mm:.2f}mm"
        )

    elif isinstance(node, SplitHorizontal):
        lines.append(f"{prefix}split_horizontal {node.n} gap {node.gap_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, SplitVertical):
        lines.append(f"{prefix}split_vertical {node.n} gap {node.gap_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, SplitGrid):
        lines.append(f"{prefix}split_grid {node.rows} {node.cols} gap {node.gap_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    else:

        pass

    return lines


def _format_feature(feature: Any) -> str:
    if feature.type == 'pocket':
        return f"pocket {feature.depth_mm:.2f}mm"
    elif feature.type == 'profile':
        return f"profile {feature.depth} {feature.side}"
    elif feature.type == 'engrave':
        return f"engrave {feature.depth_mm:.2f}mm"
    elif feature.type == 'hole':
        return f"hole {feature.depth_mm:.2f}mm"
    elif feature.type == 'edge':
        return feature.type
    else:
        return feature.type
