
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["build_cam_hints"]

def _id(it: Dict[str, Any]) -> str:
    return it.get("id") or ""

def _xy(placement: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    if not placement:
        return None
    v = placement.get("center_xy_mm")
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return float(v[0]), float(v[1])
    return None

def _rect_geom(g: Dict[str, Any]) -> Dict[str, float]:
    return {"w_mm": float(g.get("w_mm", 0.0)),
            "h_mm": float(g.get("h_mm", 0.0))}

def _circle_geom(g: Dict[str, Any]) -> Dict[str, float]:
    return {"diameter_mm": float(g.get("diameter_mm", 0.0))}

def _polyline_geom(g: Dict[str, Any]) -> Dict[str, Any]:
    pts_raw = g.get("points") or []
    pts = [(float(p[0]), float(p[1])) for p in pts_raw if isinstance(p, (tuple, list)) and len(p) == 2]
    closed = bool(g.get("closed", False))
    return {"points": pts, "closed": closed}

def _depth_mm(feature: Dict[str, Any], sheet_thickness: float) -> float:
    ftype = (feature or {}).get("type", feature.get("kind", "profile")).lower()
    if ftype in ("pocket", "engrave"):
        return float(feature.get("depth_mm", 0.0))
    if feature.get("depth") == "through":
        return float(sheet_thickness)
    if "depth_mm" in feature:
        return float(feature["depth_mm"])
    return float(feature.get("depth", sheet_thickness))

def _classify(item: Dict[str, Any], sheet_thickness: float) -> str:
    f = (item.get("feature") or {})
    ftype = (f.get("type") or f.get("kind") or "profile").lower()
    t = (item.get("type") or "").lower()
    if ftype == "pocket" or t == "region":
        return "pockets"
    if ftype == "engrave":
        return "engraves"
    if ftype == "hole" or (t == "circle" and ftype in ("drill", "hole")):
        return "holes"
    return "profiles"

def _expand_door(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    params = item.get("params") or {}
    center = _xy(item.get("placement"))
    outer_w = float(params.get("outer_w", 0.0))
    outer_h = float(params.get("outer_h", 0.0))
    stile_w = float(params.get("stile_w", 0.0))
    rail_h  = float(params.get("rail_h", 0.0))
    panel_recess = float(params.get("panel_recess", 0.0))

    out.append({
        "id": _id(item) or (item.get("id") or ""),
        "type": "Rect",
        "geometry": {"w_mm": outer_w, "h_mm": outer_h},
        "placement": {"center_xy_mm": center},
        "feature": {"type": "profile", "depth": "through", "side": "outside"},
    })

    if panel_recess > 0 and outer_w > 2 * stile_w and outer_h > 2 * rail_h:
        in_w = max(0.0, outer_w - 2 * stile_w)
        in_h = max(0.0, outer_h - 2 * rail_h)
        out.append({
            "id": (_id(item) + ":panel") if _id(item) else "",
            "type": "Rect",
            "geometry": {"w_mm": in_w, "h_mm": in_h},
            "placement": {"center_xy_mm": center},
            "feature": {"type": "pocket", "depth_mm": panel_recess}
        })
    return out

def build_cam_hints(*, items_resolved: List[Dict[str, Any]], sheet_thickness: float,
                    kerf_width_mm: float = 3.175, min_channel_width: float = 6.0) -> Dict[str, Any]:
    profiles: List[Dict[str, Any]] = []
    pockets:  List[Dict[str, Any]] = []
    holes:    List[Dict[str, Any]] = []
    engraves: List[Dict[str, Any]] = []


    expanded: List[Dict[str, Any]] = []
    for it in items_resolved:
        kind = (it.get("kind") or "").lower()
        if kind == "door":

            expanded.extend(_expand_door(it))
        else:
            expanded.append(it)


    for it in expanded:
        bucket = _classify(it, sheet_thickness)
        t = (it.get("type") or it.get("shape") or "").strip()
        g = it.get("geometry") or {}
        center = _xy(it.get("placement"))
        f = (it.get("feature") or {})
        depth = _depth_mm(f, sheet_thickness)

        start_depth = 0.0
        if bucket == "pockets":
            try:
                start_depth = max(0.0, float(f.get("start_depth_mm", f.get("start_depth", 0.0))))
            except (TypeError, ValueError):
                start_depth = 0.0

        rec: Dict[str, Any] = {
            "id": _id(it),
            "shape": t,
            "geometry": g,
            "depth_mm": float(depth),
        }
        if center is not None:
            rec["center_xy_mm"] = (float(center[0]), float(center[1]))


        side = (f.get("side") or it.get("side"))
        if side and bucket == "profiles":
            rec["side"] = str(side).lower()

        if bucket == "profiles" and "tabs" in f:
            rec["tabs"] = f.get("tabs")

        if start_depth > 0.0 and bucket == "pockets":
            rec["start_depth_mm"] = start_depth

        if bucket == "profiles":
            profiles.append(rec)
        elif bucket == "pockets":
            pockets.append(rec)
        elif bucket == "holes":
            holes.append(rec)
        elif bucket == "engraves":
            engraves.append(rec)


    return {
        "units": "mm",
        "kerf_width_mm": float(kerf_width_mm),
        "min_channel_width_mm": float(min_channel_width),
        "profiles": profiles,
        "pockets": pockets,
        "holes": holes,
        "engraves": engraves,
        "items_resolved": items_resolved,
    }
