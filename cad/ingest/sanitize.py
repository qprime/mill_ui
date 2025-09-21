"""Canonicalisation helpers for layout ingestion."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping


_CANONICAL_TYPES = {
    "rect": {"rect", "rectangle", "box"},
    "circle": {"circle", "disk", "round"},
    "polyline": {"polyline", "poly_line", "line"},
    "path": {"path", "curve"},
    "text": {"text", "label"},
}


def _canonical_type(value: str) -> str:
    value_lower = value.strip().lower()
    for canonical, aliases in _CANONICAL_TYPES.items():
        if value_lower == canonical or value_lower in aliases:
            return canonical
    return value_lower


def _require_geometry(item: Mapping[str, Any]) -> Mapping[str, Any]:
    geometry = item.get("geometry")
    if not isinstance(geometry, Mapping):
        raise ValueError("Shape item requires a geometry mapping")
    return geometry


def _validate_rect(item: Mapping[str, Any]) -> None:
    geometry = _require_geometry(item)
    for key in ("w_mm", "h_mm"):
        if key not in geometry:
            raise ValueError("Rect geometry must include w_mm and h_mm")
        float(geometry[key])


def _validate_circle(item: Mapping[str, Any]) -> None:
    geometry = _require_geometry(item)
    if "diameter_mm" in geometry:
        float(geometry["diameter_mm"])
        return
    if "radius_mm" in geometry:
        float(geometry["radius_mm"])
        return
    raise ValueError("Circle geometry must include diameter_mm or radius_mm")


def _validate_polyline(item: Mapping[str, Any]) -> None:
    geometry = _require_geometry(item)
    points = geometry.get("points")
    if not isinstance(points, Iterable):
        raise ValueError("Polyline geometry must include a points iterable")
    for point in points:
        if not (isinstance(point, (list, tuple)) and len(point) == 2):
            raise ValueError("Polyline points must be 2D coordinates")
        float(point[0])
        float(point[1])


def _validate_text(item: Mapping[str, Any]) -> None:
    if "text" not in item:
        raise ValueError("Text item requires the text field")


_VALIDATORS = {
    "rect": _validate_rect,
    "circle": _validate_circle,
    "polyline": _validate_polyline,
    "path": _validate_polyline,
    "text": _validate_text,
}


def canonicalize_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a deep-copied, canonicalised version of *item*."""

    canonical = deepcopy(item)
    kind_raw = canonical.get("kind", canonical.get("Kind"))
    if isinstance(kind_raw, str):
        canonical["kind"] = kind_raw.strip().lower()
    item_type = canonical.get("type", canonical.get("Type"))
    if isinstance(item_type, str):
        canonical["type"] = _canonical_type(item_type)

    kind = str(canonical.get("kind", "")).lower()
    type_name = str(canonical.get("type", "")).lower()

    if kind == "shape" and type_name:
        validator = _VALIDATORS.get(type_name)
        if validator:
            validator(canonical)
    return canonical


def canonicalize_items(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Canonicalise a sequence of layout items."""

    canonical_items: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("Items must be mapping objects")
        canonical_items.append(canonicalize_item(item))
    return canonical_items


__all__ = ["canonicalize_item", "canonicalize_items"]
