"""Compositional PML formatter: CompositionalAST → canonical PML.

This formatter produces canonical, human-readable compositional PML from
CompositionalAST instances. The output is deterministic and suitable for
round-trip testing.

Formatting rules:
- 4-space indentation
- Explicit units (mm) on all numeric values
- Stable ordering for components
- No blank lines between nodes at same level
- Feature attributes inline with node declaration
"""

from __future__ import annotations

from typing import Any

from skills.mill_ui.v2.ast.compositional import (
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
    CompositionalLayoutAST,
)


def format_compositional_pml(ast: CompositionalLayoutAST) -> str:
    """Format CompositionalAST as canonical PML.

    Args:
        ast: CompositionalLayoutAST instance

    Returns:
        Canonical PML string
    """
    lines = []

    # Sheet declaration
    lines.append(f"sheet {ast.sheet.width_mm:.2f}mm {ast.sheet.height_mm:.2f}mm {ast.sheet.thickness_mm:.2f}mm")
    lines.append("")

    # Project declaration
    if ast.project:
        lines.append(f"project {ast.project}")
        lines.append("")

    # Component definitions
    for name in sorted(ast.components.keys()):
        comp_def = ast.components[name]
        lines.append(f"component {name}")
        lines.extend(_format_node(comp_def.body, indent=1))
        lines.append("")

    # Root layout
    lines.extend(_format_node(ast.root, indent=0))

    return "\n".join(lines)


def _format_node(node: Any, indent: int = 0) -> list[str]:
    """Format a layout node with proper indentation.

    Args:
        node: Compositional AST node
        indent: Current indentation level (0-based)

    Returns:
        List of formatted lines
    """
    prefix = "    " * indent
    lines = []

    if isinstance(node, Panel):
        # Panel is implicit; just format children
        for child in node.children:
            lines.extend(_format_node(child, indent))

    elif isinstance(node, Rect):
        # rect [id] [feature]
        parts = ["rect"]
        if node.id:
            parts.append(node.id)
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))

        # Children (if any)
        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Circle):
        # circle [id] [diameter <value>mm | fit] [feature]
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

        # Children (if any)
        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, RoundedRect):
        # rounded_rect [id] radius <value>mm [feature]
        parts = ["rounded_rect"]
        if node.id:
            parts.append(node.id)
        parts.append(f"radius {node.radius_mm:.2f}mm")
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))

        # Children (if any)
        if node.children:
            for child in node.children:
                lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Line):
        # line [id] horizontal|vertical [feature]
        parts = ["line"]
        if node.id:
            parts.append(node.id)
        parts.append(node.orientation)
        if node.feature:
            parts.append(_format_feature(node.feature))
        lines.append(prefix + " ".join(parts))

    elif isinstance(node, Inset):
        # inset <amount>mm
        lines.append(f"{prefix}inset {node.amount_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Frame):
        # frame <width>mm
        lines.append(f"{prefix}frame {node.width_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Grid):
        # grid <rows> <cols> gap <gap>mm
        lines.append(f"{prefix}grid {node.rows} {node.cols} gap {node.gap_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Split):
        # split <rows> <cols> rail <rail>mm mullion <mullion>mm
        lines.append(f"{prefix}split {node.rows} {node.cols} rail {node.rail_mm:.2f}mm mullion {node.mullion_mm:.2f}mm")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Cell):
        # cell
        lines.append(f"{prefix}cell")
        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, Place):
        # place grid <rows> <cols> gap <gap>mm
        if isinstance(node.layout, Grid):
            grid = node.layout
            lines.append(f"{prefix}place grid {grid.rows} {grid.cols} gap {grid.gap_mm:.2f}mm")
        else:
            lines.append(f"{prefix}place")

        for child in node.children:
            lines.extend(_format_node(child, indent + 1))

    elif isinstance(node, UseComponent):
        # use <component_name>
        lines.append(f"{prefix}use {node.component_name}")

    else:
        # Unknown node type; skip
        pass

    return lines


def _format_feature(feature: Any) -> str:
    """Format a feature as inline PML.

    Args:
        feature: Feature instance

    Returns:
        Feature string (e.g., "pocket 5.00mm", "profile through outside")
    """
    if feature.type == 'pocket':
        return f"pocket {feature.depth_mm:.2f}mm"
    elif feature.type == 'profile':
        return f"profile {feature.depth} {feature.side}"
    elif feature.type in ('engrave', 'hole', 'edge'):
        return feature.type
    else:
        return feature.type
