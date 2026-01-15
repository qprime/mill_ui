
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Placement,
    Geometry,
    Feature,
)


def parse_layout_json(path: str) -> LayoutAST:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Layout file not found: {path}")

    with path_obj.open("r", encoding="utf-8") as f:
        data = json.load(f)


    if "sheet" not in data:
        raise ValueError("Layout JSON missing required 'sheet' field")
    sheet_data = data["sheet"]
    sheet = Sheet(
        width_mm=float(sheet_data["width_mm"]),
        height_mm=float(sheet_data["height_mm"]),
        thickness_mm=float(sheet_data["thickness_mm"]),
    )


    items_data = data.get("items", [])
    items = tuple(_parse_item(item_data) for item_data in items_data)


    project = data.get("project")
    kerf_width_mm = data.get("kerf_width_mm")
    cam = data.get("cam")
    layout = data.get("layout")
    config = data.get("config", {})

    return LayoutAST(
        sheet=sheet,
        items=items,
        project=project,
        kerf_width_mm=kerf_width_mm,
        cam=cam,
        layout=layout,
        config=config,
    )


def _parse_item(item_data: dict[str, Any]) -> Item:
    kind = item_data.get("kind", "shape")
    item_type = item_data["type"]

    if kind == "template":

        params = item_data.get("params")
        template_id = item_data.get("id")
        return Item(
            kind=kind,
            type=item_type,
            params=params,
            id=template_id,
        )
    else:


        geometry_data = item_data.get("geometry", {})
        geometry = Geometry(data=geometry_data)


        placement_data = item_data["placement"]
        center_xy = placement_data["center_xy_mm"]
        placement = Placement(center_xy_mm=(float(center_xy[0]), float(center_xy[1])))


        feature_data = item_data["feature"]
        feature = _parse_feature(feature_data)


        shape_id = item_data.get("shape_id")

        return Item(
            kind=kind,
            type=item_type,
            geometry=geometry,
            placement=placement,
            feature=feature,
            shape_id=shape_id,
        )


def _parse_feature(feature_data: dict[str, Any]) -> Feature:
    feature_type = feature_data["type"]
    depth = feature_data.get("depth")
    depth_mm = feature_data.get("depth_mm")
    side = feature_data.get("side")

    return Feature(
        type=feature_type,
        depth=depth,
        side=side,
        depth_mm=depth_mm,
    )
