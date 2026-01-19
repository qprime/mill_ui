
from __future__ import annotations

from typing import Any

from layout_ast.layout import Item


def items_to_shape_dicts(items: tuple[Item, ...]) -> list[dict[str, Any]]:
    shapes: list[dict[str, Any]] = []

    for item in items:

        if item.kind != "shape":
            continue


        if item.geometry is None or item.placement is None or item.feature is None:
            continue


        shape: dict[str, Any] = {
            "type": item.type,
            "geometry": dict(item.geometry.data),
            "placement": {"center_xy_mm": item.placement.center_xy_mm},
            "feature": {
                "type": item.feature.type,
                "depth": item.feature.depth,
            },
        }


        if item.feature.side is not None:
            shape["feature"]["side"] = item.feature.side

        if item.feature.depth_mm is not None:
            shape["feature"]["depth_mm"] = item.feature.depth_mm


        if item.shape_id is not None:
            shape["id"] = item.shape_id

        shapes.append(shape)

    return shapes


__all__ = ["items_to_shape_dicts"]
