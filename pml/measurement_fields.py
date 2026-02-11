from __future__ import annotations

from typing import Any


MEASUREMENT_DEFAULTS = {
    "minor_length": "3mm",
    "major_length": "6mm",
    "minor_ticks": True,
    "labels": False,
    "label_height": "3mm",
    "label_interval": 1,
    "label_start": 0,
}

MEASUREMENT_FORMAT_DEFAULTS = {
    "minor_length_mm": 3.0,
    "major_length_mm": 6.0,
    "minor_ticks": True,
    "labels": False,
    "label_height_mm": 3.0,
    "label_interval": 1,
    "label_start": 0,
}


def parse_measurement_fields(node_data: dict, parse_dimension) -> dict[str, Any]:
    return {
        "unit": node_data.get("unit", "metric"),
        "minor_spacing_mm": parse_dimension(node_data["minor_spacing"]) if "minor_spacing" in node_data else None,
        "major_spacing_mm": parse_dimension(node_data["major_spacing"]) if "major_spacing" in node_data else None,
        "minor_length_mm": parse_dimension(node_data.get("minor_length", MEASUREMENT_DEFAULTS["minor_length"])),
        "major_length_mm": parse_dimension(node_data.get("major_length", MEASUREMENT_DEFAULTS["major_length"])),
        "minor_ticks": node_data.get("minor_ticks", MEASUREMENT_DEFAULTS["minor_ticks"]),
        "labels": node_data.get("labels", MEASUREMENT_DEFAULTS["labels"]),
        "label_height_mm": parse_dimension(node_data.get("label_height", MEASUREMENT_DEFAULTS["label_height"])),
        "label_offset_mm": parse_dimension(node_data["label_offset"]) if "label_offset" in node_data else None,
        "label_interval": node_data.get("label_interval", MEASUREMENT_DEFAULTS["label_interval"]),
        "label_start": node_data.get("label_start", MEASUREMENT_DEFAULTS["label_start"]),
    }


def format_measurement_fields(node, dim, default_depth: float) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if node.unit != "metric":
        result["unit"] = node.unit
    if node.minor_spacing_mm is not None:
        result["minor_spacing"] = dim(node.minor_spacing_mm)
    if node.major_spacing_mm is not None:
        result["major_spacing"] = dim(node.major_spacing_mm)
    if node.minor_length_mm != MEASUREMENT_FORMAT_DEFAULTS["minor_length_mm"]:
        result["minor_length"] = dim(node.minor_length_mm)
    if node.major_length_mm != MEASUREMENT_FORMAT_DEFAULTS["major_length_mm"]:
        result["major_length"] = dim(node.major_length_mm)
    if node.depth_mm != default_depth:
        result["depth"] = dim(node.depth_mm)
    if not node.minor_ticks:
        result["minor_ticks"] = False
    if node.labels:
        result["labels"] = True
    if node.label_height_mm != MEASUREMENT_FORMAT_DEFAULTS["label_height_mm"]:
        result["label_height"] = dim(node.label_height_mm)
    if node.label_offset_mm is not None:
        result["label_offset"] = dim(node.label_offset_mm)
    if node.label_interval != MEASUREMENT_FORMAT_DEFAULTS["label_interval"]:
        result["label_interval"] = node.label_interval
    if node.label_start != MEASUREMENT_FORMAT_DEFAULTS["label_start"]:
        result["label_start"] = node.label_start
    return result


__all__ = [
    "parse_measurement_fields",
    "format_measurement_fields",
]
