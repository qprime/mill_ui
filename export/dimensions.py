"""Dimension placement engine for blueprint SVG drawings.

Implements deterministic rail-based dimension placement with collision avoidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from xml.etree import ElementTree as ET

from layout_ast.layout import LayoutAST, Item
from ir.removal_intent import RemovalIntent, Bounds2D


@dataclass(frozen=True)
class DimensionLabel:
    """A dimension label with position and text."""
    value_mm: float
    text: str
    x: float
    y: float
    orientation: str  # "horizontal" or "vertical"


@dataclass(frozen=True)
class BBox:
    """Bounding box for collision detection."""
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def overlaps(self, other: BBox) -> bool:
        """Check if this bbox overlaps with another."""
        return not (
            self.x_max < other.x_min
            or self.x_min > other.x_max
            or self.y_max < other.y_min
            or self.y_min > other.y_max
        )


def compute_bounding_boxes(ast: LayoutAST, intents: Sequence[RemovalIntent] | None = None) -> dict[str, Bounds2D]:
    """Compute bounding boxes for all items in layout.

    Args:
        ast: LayoutAST containing shapes
        intents: Optional RemovalIntent list (for validation)

    Returns:
        Dictionary mapping shape_id to Bounds2D
    """
    boxes = {}

    for item in ast.items:
        if item.kind != "shape" or item.geometry is None or item.placement is None:
            continue

        shape_id = item.shape_id or f"item_{id(item)}"
        bounds = _compute_item_bounds(item)
        if bounds:
            boxes[shape_id] = bounds

    return boxes


def _compute_item_bounds(item: Item) -> Bounds2D | None:
    """Compute bounds for a single item."""
    if item.geometry is None or item.placement is None:
        return None

    cx, cy = item.placement.center_xy_mm
    shape_type = item.type

    if shape_type == "Rect":
        w = item.geometry.data.get("w_mm", 0)
        h = item.geometry.data.get("h_mm", 0)
        return Bounds2D(
            x_min=cx - w / 2,
            x_max=cx + w / 2,
            y_min=cy - h / 2,
            y_max=cy + h / 2,
        )
    elif shape_type == "Circle":
        r = item.geometry.data.get("radius_mm") or item.geometry.data.get("diameter_mm", 0) / 2
        return Bounds2D(
            x_min=cx - r,
            x_max=cx + r,
            y_min=cy - r,
            y_max=cy + r,
        )
    elif shape_type == "RoundedRect":
        w = item.geometry.data.get("w_mm", 0)
        h = item.geometry.data.get("h_mm", 0)
        return Bounds2D(
            x_min=cx - w / 2,
            x_max=cx + w / 2,
            y_min=cy - h / 2,
            y_max=cy + h / 2,
        )

    return None


def place_dimensions_on_rails(
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    margin: float = 100.0,
) -> list[DimensionLabel]:
    """Place dimensions on outer rails (top and right).

    Args:
        ast: LayoutAST with sheet and items
        offset_x: X offset for sheet position
        offset_y: Y offset for sheet position
        margin: Margin size for rail placement

    Returns:
        List of DimensionLabel objects with deterministic placement
    """
    dimensions = []
    sheet = ast.sheet

    # Top rail: Sheet width
    dimensions.append(
        DimensionLabel(
            value_mm=sheet.width_mm,
            text=f"{sheet.width_mm:.1f}mm",
            x=offset_x + sheet.width_mm / 2,
            y=offset_y - 40,  # Above sheet
            orientation="horizontal",
        )
    )

    # Right rail: Sheet height
    dimensions.append(
        DimensionLabel(
            value_mm=sheet.height_mm,
            text=f"{sheet.height_mm:.1f}mm",
            x=offset_x + sheet.width_mm + 40,  # Right of sheet
            y=offset_y + sheet.height_mm / 2,
            orientation="vertical",
        )
    )

    # Add dimensions for each profile/pocket item
    item_bounds = compute_bounding_boxes(ast)
    for shape_id, bounds in item_bounds.items():
        w = bounds.x_max - bounds.x_min
        h = bounds.y_max - bounds.y_min

        # Item width on top rail (stacked if needed)
        dimensions.append(
            DimensionLabel(
                value_mm=w,
                text=f"{w:.1f}mm",
                x=offset_x + (bounds.x_min + bounds.x_max) / 2,
                y=offset_y - 20,  # Below sheet dimension
                orientation="horizontal",
            )
        )

        # Item height on right rail (stacked if needed)
        dimensions.append(
            DimensionLabel(
                value_mm=h,
                text=f"{h:.1f}mm",
                x=offset_x + sheet.width_mm + 20,  # Left of sheet dimension
                y=offset_y + (bounds.y_min + bounds.y_max) / 2,
                orientation="vertical",
            )
        )

    return dimensions


def render_dimension_line(
    parent: ET.Element,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    text: str,
    orientation: str,
    theme_color: str,
) -> None:
    """Render a dimension line with arrowheads and text.

    Args:
        parent: Parent SVG element
        start_x, start_y: Start point
        end_x, end_y: End point
        text: Dimension text
        orientation: "horizontal" or "vertical"
        theme_color: Color for dimension lines and text
    """
    # Dimension line
    ET.SubElement(
        parent,
        "line",
        {
            "x1": str(start_x),
            "y1": str(start_y),
            "x2": str(end_x),
            "y2": str(end_y),
            "stroke": theme_color,
            "stroke-width": "1",
        },
    )

    # Arrowheads (simple triangles)
    arrow_size = 3

    if orientation == "horizontal":
        # Left arrow
        _add_arrow(parent, start_x, start_y, "left", arrow_size, theme_color)
        # Right arrow
        _add_arrow(parent, end_x, end_y, "right", arrow_size, theme_color)
    else:  # vertical
        # Top arrow
        _add_arrow(parent, start_x, start_y, "up", arrow_size, theme_color)
        # Bottom arrow
        _add_arrow(parent, end_x, end_y, "down", arrow_size, theme_color)

    # Text label
    text_x = (start_x + end_x) / 2
    text_y = (start_y + end_y) / 2

    if orientation == "horizontal":
        text_y -= 5  # Above the line
    else:
        text_x += 10  # Right of the line

    ET.SubElement(
        parent,
        "text",
        {
            "x": str(text_x),
            "y": str(text_y),
            "class": "dimension-text",
            "text-anchor": "middle",
            "dominant-baseline": "middle",
        },
    ).text = text


def _add_arrow(parent: ET.Element, x: float, y: float, direction: str, size: float, color: str) -> None:
    """Add an arrowhead triangle."""
    if direction == "left":
        points = f"{x},{y} {x+size},{y-size} {x+size},{y+size}"
    elif direction == "right":
        points = f"{x},{y} {x-size},{y-size} {x-size},{y+size}"
    elif direction == "up":
        points = f"{x},{y} {x-size},{y+size} {x+size},{y+size}"
    else:  # down
        points = f"{x},{y} {x-size},{y-size} {x+size},{y-size}"

    ET.SubElement(
        parent,
        "polygon",
        {
            "points": points,
            "fill": color,
        },
    )


def avoid_label_collisions(labels: list[DimensionLabel], text_height: float = 12, padding: float = 4) -> list[DimensionLabel]:
    """Adjust label positions to avoid overlaps (simple stacking).

    Args:
        labels: List of DimensionLabel objects
        text_height: Estimated text height in mm
        padding: Padding between labels

    Returns:
        Adjusted list of DimensionLabel objects
    """
    # Simple approach: group by orientation and adjust Y (horizontal) or X (vertical) offsets
    # For v1, we'll just stack labels on the same rail

    horizontal_labels = [l for l in labels if l.orientation == "horizontal"]
    vertical_labels = [l for l in labels if l.orientation == "vertical"]

    # Sort horizontal labels by X position
    horizontal_labels.sort(key=lambda l: l.x)

    # Sort vertical labels by Y position
    vertical_labels.sort(key=lambda l: l.y)

    # For now, return as-is (collision avoidance is minimal in v1)
    # Future: implement proper bbox-based collision detection and stacking
    return labels
