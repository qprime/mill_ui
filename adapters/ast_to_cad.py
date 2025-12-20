"""Adapter: LayoutAST → shape dicts for native CAD backend (STL/STEP export).

Converts v2 LayoutAST Items to the dict format expected by cad.native.core.
All dimensions in millimeters.
"""

from __future__ import annotations

from typing import Any

from layout_ast.layout import Item


def items_to_shape_dicts(items: tuple[Item, ...]) -> list[dict[str, Any]]:
    """Convert LayoutAST Items to shape dicts for native CAD backend.

    Args:
        items: Tuple of LayoutAST Items (shapes and templates)

    Returns:
        List of shape dicts compatible with native_core.export_stl/export_step

    Notes:
        - Only processes items with kind="shape"
        - Templates should already be expanded to shapes before calling this
        - Output format matches the dict structure expected by cad.native.core:
          {
              "type": "Rect" | "Circle" | "Polyline",
              "geometry": {"w_mm": ..., "h_mm": ...} or {"diameter_mm": ...},
              "placement": {"center_xy_mm": (x, y)},
              "feature": {
                  "type": "profile" | "pocket" | "hole" | "engrave",
                  "depth": "through" or numeric depth_mm,
                  "side": "inside" | "outside" | "on"  # for profiles only
              }
          }
    """
    shapes: list[dict[str, Any]] = []

    for item in items:
        # Skip non-shape items (templates should already be expanded)
        if item.kind != "shape":
            continue

        # Validate required fields for shapes
        if item.geometry is None or item.placement is None or item.feature is None:
            raise ValueError(
                f"Shape item missing required fields (geometry/placement/feature): {item}"
            )

        # Build shape dict
        shape: dict[str, Any] = {
            "type": item.type,
            "geometry": dict(item.geometry.data),  # Copy geometry data
            "placement": {"center_xy_mm": item.placement.center_xy_mm},
            "feature": {
                "type": item.feature.type,
                "depth": item.feature.depth,
            },
        }

        # Add optional feature fields
        if item.feature.side is not None:
            shape["feature"]["side"] = item.feature.side

        if item.feature.depth_mm is not None:
            shape["feature"]["depth_mm"] = item.feature.depth_mm

        # Add optional shape_id
        if item.shape_id is not None:
            shape["id"] = item.shape_id

        shapes.append(shape)

    return shapes


__all__ = ["items_to_shape_dicts"]
