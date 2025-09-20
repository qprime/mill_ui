from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple
import json


def skeleton_layout() -> Dict[str, Any]:
    return {
        "sheet": {
            "width_mm": 0.0,
            "height_mm": 0.0,
            "thickness_mm": 0.0,
        },
        "kerf_width_mm": 0.0,
        "layout": {
            "cols": 1,
            "rows": 1,
            "border_mm": 0.0,
            "fit": "tight",
            "gap_mode": "explicit",
            "gap_x_mm": 0.0,
            "gap_y_mm": 0.0,
        },
        "cam": {
            "profile": {
                "cut_through_mm": 0.0,
                "tabs": {"count": 0, "height_mm": 3.0},
            }
        },
        "items": [],
    }


def validate_layout_json(data: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Top-level JSON must be an object"
    sheet = data.get("sheet")
    if not isinstance(sheet, dict):
        return False, "Missing or invalid 'sheet' object"
    for k in ("width_mm", "height_mm", "thickness_mm"):
        if k not in sheet:
            return False, f"sheet.{k} is required"
        try:
            float(sheet[k])
        except Exception:
            return False, f"sheet.{k} must be a number"
    items = data.get("items")
    if not isinstance(items, list):
        return False, "Missing or invalid 'items' (must be an array)"
    # Light validation of items; allow empty for new projects
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            return False, f"items[{i}] must be an object"
        if not (it.get("kind") or it.get("type")):
            return False, f"items[{i}] must include 'kind' or 'type'"
    if "kerf_width_mm" in data:
        try:
            float(data["kerf_width_mm"])
        except Exception:
            return False, "kerf_width_mm must be numeric if present"
    # Accept 'cam' and 'layout' as-is when present
    return True, "ok"


def ensure_project_structure(base: Path) -> None:
    (base / "input").mkdir(parents=True, exist_ok=True)
    (base / "CAM").mkdir(parents=True, exist_ok=True)


def write_layout(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_layout(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

