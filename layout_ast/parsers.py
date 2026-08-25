from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.constants import DepthMode
from layout_ast.layout import (
    DEFAULT_MIN_WEB_MM,
    DogboneSpec,
    Feature,
    FeedsOverride,
    Geometry,
    Item,
    LayoutAST,
    Placement,
    RestSpec,
    Sheet,
)


def _parse_dogbone(raw: Any) -> DogboneSpec | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return DogboneSpec(
            style=raw.get("style", "dogbone"),
            diameter_mm=raw.get("diameter_mm"),
            overcut_mm=raw.get("overcut_mm", 0.0),
        )
    return None


def _parse_rest(raw: Any) -> RestSpec | None:
    if not isinstance(raw, dict):
        return None
    return RestSpec(
        tool_diameter_mm=raw["tool_diameter_mm"],
        rough_allowance_mm=raw.get("rough_allowance_mm", 0.5),
        finish_allowance_mm=raw.get("finish_allowance_mm", 0.0),
    )


def _parse_feeds_override(raw: Any) -> FeedsOverride | None:
    if not isinstance(raw, dict):
        return None
    return FeedsOverride(
        rpm=raw.get("rpm"),
        feed_xy=raw.get("feed_xy"),
        feed_z=raw.get("feed_z"),
        depth_per_pass=raw.get("depth_per_pass"),
        stepover_percent=raw.get("stepover_percent"),
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
        margin_mm=float(sheet_data.get("margin_mm", 0.0)),
        show_dimensions=sheet_data.get("show_dimensions", True),
        min_web_mm=float(sheet_data.get("min_web_mm", DEFAULT_MIN_WEB_MM)),
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
        raise ValueError(
            f"Layout item '{item_data.get('id', item_type)}' uses kind 'template', which is no longer supported. "
            f"Define reusable parts as PML templates instead."
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

    is_through = DepthMode.is_through(depth)
    if depth_mm is None:
        if is_through:
            depth_mm = 0.0
        elif depth is not None:
            depth_mm = float(depth)
        else:
            depth_mm = 0.0

    return Feature(
        type=feature_type,
        depth_mm=depth_mm,
        side=side,
        face=feature_data.get("face", "front"),
        is_through=is_through,
        corner_cleanup_tool_diameter_mm=feature_data.get("corner_cleanup_tool_diameter_mm"),
        dogbone=_parse_dogbone(feature_data.get("dogbone")),
        rest=_parse_rest(feature_data.get("rest")),
        tab_count=feature_data.get("tab_count"),
        tab_height_mm=feature_data.get("tab_height_mm"),
        tab_width_mm=feature_data.get("tab_width_mm"),
        onion_skin_mm=feature_data.get("onion_skin_mm"),
        bevel_width_mm=feature_data.get("bevel_width_mm"),
        bevel_angle_deg=feature_data.get("bevel_angle_deg"),
        bevel_inner_depth_mm=feature_data.get("bevel_inner_depth_mm"),
        chamfer_width_mm=feature_data.get("chamfer_width_mm"),
        chamfer_angle_deg=feature_data.get("chamfer_angle_deg"),
        roundover_radius_mm=feature_data.get("roundover_radius_mm"),
        feeds_override=_parse_feeds_override(feature_data.get("feeds_override")),
        ramp_mm=feature_data.get("ramp_mm"),
    )
