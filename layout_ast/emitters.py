from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from layout_ast.layout import Feature, Item, LayoutAST, Placement, Sheet

if TYPE_CHECKING:
    from layout_ast.layout import DogboneSpec, FeedsOverride, RestSpec


def emit_layout_json(ast: LayoutAST, path: str | None = None) -> str:

    data = _ast_to_dict(ast)

    json_str = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)

    if path:
        Path(path).write_text(json_str, encoding="utf-8")

    return json_str


def _ast_to_dict(ast: LayoutAST) -> dict[str, Any]:
    data: dict[str, Any] = {}

    if ast.project is not None:
        data["project"] = ast.project
    if ast.kerf_width_mm is not None:
        data["kerf_width_mm"] = ast.kerf_width_mm
    if ast.cam is not None:
        data["cam"] = ast.cam
    if ast.layout is not None:
        data["layout"] = ast.layout

    data["sheet"] = _sheet_to_dict(ast.sheet)

    data["items"] = [_item_to_dict(item) for item in ast.items]

    if ast.config:
        data["config"] = ast.config

    return data


def _sheet_to_dict(sheet: Sheet) -> dict[str, Any]:
    data: dict[str, Any] = {
        "width_mm": sheet.width_mm,
        "height_mm": sheet.height_mm,
        "thickness_mm": sheet.thickness_mm,
    }
    if sheet.margin_mm != 0.0:
        data["margin_mm"] = sheet.margin_mm
    if not sheet.show_dimensions:
        data["show_dimensions"] = False
    return data


def _item_to_dict(item: Item) -> dict[str, Any]:
    data: dict[str, Any] = {
        "kind": item.kind,
        "type": item.type,
    }

    if item.kind == "template":
        if item.params is not None:
            data["params"] = item.params
        if item.id is not None:
            data["id"] = item.id
    else:
        if item.geometry is not None:
            data["geometry"] = item.geometry.data
        if item.placement is not None:
            data["placement"] = _placement_to_dict(item.placement)
        if item.feature is not None:
            data["feature"] = _feature_to_dict(item.feature)
        if item.shape_id is not None:
            data["shape_id"] = item.shape_id

    return data


def _placement_to_dict(placement: Placement) -> dict[str, Any]:
    return {
        "center_xy_mm": list(placement.center_xy_mm),
    }


def _dogbone_to_dict(dogbone: DogboneSpec) -> dict[str, Any]:
    result: dict[str, Any] = {"style": dogbone.style}
    if dogbone.diameter_mm is not None:
        result["diameter_mm"] = dogbone.diameter_mm
    if dogbone.overcut_mm != 0.0:
        result["overcut_mm"] = dogbone.overcut_mm
    return result


def _rest_to_dict(rest: RestSpec) -> dict[str, Any]:
    result: dict[str, Any] = {"tool_diameter_mm": rest.tool_diameter_mm}
    if rest.rough_allowance_mm != 0.5:
        result["rough_allowance_mm"] = rest.rough_allowance_mm
    if rest.finish_allowance_mm != 0.0:
        result["finish_allowance_mm"] = rest.finish_allowance_mm
    return result


def _feeds_override_to_dict(feeds: FeedsOverride) -> dict[str, Any] | None:
    result: dict[str, Any] = {}
    if feeds.rpm is not None:
        result["rpm"] = feeds.rpm
    if feeds.feed_xy is not None:
        result["feed_xy"] = feeds.feed_xy
    if feeds.feed_z is not None:
        result["feed_z"] = feeds.feed_z
    if feeds.depth_per_pass is not None:
        result["depth_per_pass"] = feeds.depth_per_pass
    if feeds.stepover_percent is not None:
        result["stepover_percent"] = feeds.stepover_percent
    return result or None


def _feature_optional_fields(feature: Feature, data: dict[str, Any]) -> None:
    _OPTIONAL_SCALAR_FIELDS = (
        "corner_cleanup_tool_diameter_mm",
        "tab_count",
        "tab_height_mm",
        "tab_width_mm",
        "onion_skin_mm",
        "bevel_width_mm",
        "bevel_angle_deg",
        "bevel_inner_depth_mm",
        "chamfer_width_mm",
        "chamfer_angle_deg",
        "roundover_radius_mm",
    )
    for field_name in _OPTIONAL_SCALAR_FIELDS:
        value = getattr(feature, field_name)
        if value is not None:
            data[field_name] = value


def _feature_to_dict(feature: Feature) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": feature.type,
    }

    if feature.is_through:
        data["depth"] = "through"
    else:
        data["depth"] = feature.depth_mm
    data["depth_mm"] = feature.depth_mm
    if feature.side is not None:
        data["side"] = feature.side
    if feature.dogbone is not None:
        data["dogbone"] = _dogbone_to_dict(feature.dogbone)
    if feature.rest is not None:
        data["rest"] = _rest_to_dict(feature.rest)
    _feature_optional_fields(feature, data)
    if feature.feeds_override is not None:
        feeds_dict = _feeds_override_to_dict(feature.feeds_override)
        if feeds_dict is not None:
            data["feeds_override"] = feeds_dict

    return data
