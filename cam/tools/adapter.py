# path: skills/mill_ui/cam/tools/adapter.py
from __future__ import annotations
from typing import List, Dict, Any
import json

def _kind_from_type(t: str) -> str:
    t = (t or "").lower()
    if "ball" in t:
        return "ball"
    if "taper" in t or "v_bit" in t or "v-" in t:
        return "v"
    return "flat"

def _first_value(d: Dict[str, Any]) -> Dict[str, Any]:
    return next(iter(d.values()), {}) if isinstance(d, dict) else {}

def load_tool_db(json_path: str, material: str = "MDF") -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        db = json.load(f)

    tools_out: List[Dict[str, Any]] = []
    for t in db.get("tools", []):
        feeds = t.get("feeds_speeds", {}) or {}
        fs = feeds.get(material) or _first_value(feeds)
        tools_out.append({
            "name": t.get("tool_id") or t.get("name") or "tool",
            "diameter": float(t.get("diameter_mm", 0.0)),
            "kind": _kind_from_type(t.get("type", "")),
            "rpm": float(fs.get("rpm", 18000)),
            "feed_xy": float(fs.get("feed_rate_mm_min", 2000)),
            "feed_z": float(fs.get("plunge_rate_mm_min", 300)),
            "depth_per_pass": float(fs.get("depth_per_pass_mm", 3.0)),
            "stepover_percent": float(fs.get("step_over_percent", 40)),
            "flutes": int(t.get("flutes", 2)),
            # carry flute direction/spiral if present: 'upcut', 'downcut', 'compression'
            "rotation": t.get("rotation"),
        })
    return tools_out

def select_tools_for_job(
    json_path: str,
    *,
    material: str = "MDF",
    needs_roughing: bool = True,
    needs_finishing: bool = False,
    needs_detail: bool = False,
    max_depth_mm: float = 19.0
) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        db = json.load(f)

    rule_ids = set()
    rules = db.get("tool_selection_rules", {})
    if needs_roughing:
        if max_depth_mm > 10 and "deep_cuts" in rules:
            rule_ids.update(rules["deep_cuts"])
        rule_ids.update(rules.get("roughing_priority", []))
    if needs_finishing:
        rule_ids.update(rules.get("finishing_priority", []))
    if needs_detail:
        rule_ids.update(rules.get("fine_details", []))

    chosen: List[Dict[str, Any]] = []
    for t in db.get("tools", []):
        if (t.get("tool_id") or "") in rule_ids:
            feeds = t.get("feeds_speeds", {}) or {}
            fs = feeds.get(material) or _first_value(feeds)
            chosen.append({
                "name": t.get("tool_id") or t.get("name") or "tool",
                "diameter": float(t.get("diameter_mm", 0.0)),
                "kind": _kind_from_type(t.get("type", "")),
                "rpm": float(fs.get("rpm", 18000)),
                "feed_xy": float(fs.get("feed_rate_mm_min", 2000)),
                "feed_z": float(fs.get("plunge_rate_mm_min", 300)),
                "depth_per_pass": float(fs.get("depth_per_pass_mm", 3.0)),
                "stepover_percent": float(fs.get("step_over_percent", 40)),
                "flutes": int(t.get("flutes", 2)),
                "rotation": t.get("rotation"),
            })
    return sorted(chosen, key=lambda x: x["diameter"], reverse=True)
