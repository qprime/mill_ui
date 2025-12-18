"""JSON emitter for LayoutAST.

Emits canonical JSON from LayoutAST with deterministic ordering.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skills.mill_ui.layout_ast.layout import LayoutAST, Sheet, Item, Placement, Geometry, Feature
from skills.mill_ui.layout_ast.canonicalize import canonicalize_layout


def emit_layout_json(ast: LayoutAST, path: str | None = None) -> str:
    """Emit LayoutAST to canonical JSON.

    Args:
        ast: LayoutAST instance to emit
        path: Optional path to write JSON file. If None, returns JSON string.

    Returns:
        Canonical JSON string

    Note:
        Output is deterministic with stable key ordering for semantic equivalence.
    """
    # Canonicalize the AST
    canonical_ast = canonicalize_layout(ast)

    # Convert to dict
    data = _ast_to_dict(canonical_ast)

    # Emit JSON with stable ordering
    json_str = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)

    if path:
        Path(path).write_text(json_str, encoding="utf-8")

    return json_str


def _ast_to_dict(ast: LayoutAST) -> dict[str, Any]:
    """Convert LayoutAST to dictionary."""
    data: dict[str, Any] = {}

    # Top-level v1 fields (if present)
    if ast.project is not None:
        data["project"] = ast.project
    if ast.kerf_width_mm is not None:
        data["kerf_width_mm"] = ast.kerf_width_mm
    if ast.cam is not None:
        data["cam"] = ast.cam
    if ast.layout is not None:
        data["layout"] = ast.layout

    # Sheet (required)
    data["sheet"] = _sheet_to_dict(ast.sheet)

    # Items
    data["items"] = [_item_to_dict(item) for item in ast.items]

    # Config (if non-empty)
    if ast.config:
        data["config"] = ast.config

    return data


def _sheet_to_dict(sheet: Sheet) -> dict[str, Any]:
    """Convert Sheet to dictionary."""
    return {
        "width_mm": sheet.width_mm,
        "height_mm": sheet.height_mm,
        "thickness_mm": sheet.thickness_mm,
    }


def _item_to_dict(item: Item) -> dict[str, Any]:
    """Convert Item to dictionary."""
    data: dict[str, Any] = {
        "kind": item.kind,
        "type": item.type,
    }

    if item.kind == "template":
        # Template items
        if item.params is not None:
            data["params"] = item.params
        if item.id is not None:
            data["id"] = item.id
    else:
        # Shape items
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
    """Convert Placement to dictionary."""
    return {
        "center_xy_mm": list(placement.center_xy_mm),
    }


def _feature_to_dict(feature: Feature) -> dict[str, Any]:
    """Convert Feature to dictionary."""
    data: dict[str, Any] = {
        "type": feature.type,
    }

    if feature.depth is not None:
        data["depth"] = feature.depth
    if feature.depth_mm is not None:
        data["depth_mm"] = feature.depth_mm
    if feature.side is not None:
        data["side"] = feature.side

    return data
