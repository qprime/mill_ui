# path: skills/mill_ui/recipes/components.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple

def counterbore(center_xy: Tuple[float, float], *, through_d_mm: float, bore_d_mm: float, bore_depth_mm: float) -> List[Dict[str, Any]]:
    cx, cy = float(center_xy[0]), float(center_xy[1])
    return [
        {  # shallow pocket for the counterbore
            "kind": "shape",
            "type": "Circle",
            "geometry": {"diameter_mm": float(bore_d_mm)},
            "placement": {"center_xy_mm": (cx, cy)},
            "feature": {"type": "pocket", "depth_mm": float(bore_depth_mm)},
        },
        {  # through hole
            "kind": "shape",
            "type": "Circle",
            "geometry": {"diameter_mm": float(through_d_mm)},
            "placement": {"center_xy_mm": (cx, cy)},
            "feature": {"type": "hole", "depth": "through"},
        },
    ]

def shelf_pin_grid(origin_xy: Tuple[float, float], *, rows: int, cols: int, pitch_x_mm: float, pitch_y_mm: float, hole_d_mm: float, depth: str | float = "through") -> List[Dict[str, Any]]:
    ox, oy = float(origin_xy[0]), float(origin_xy[1])
    items: List[Dict[str, Any]] = []
    for r in range(rows):
        for c in range(cols):
            cx = ox + c * float(pitch_x_mm)
            cy = oy + r * float(pitch_y_mm)
            feature = {"type": "hole", "depth": "through"} if depth == "through" else {"type": "hole", "depth_mm": float(depth)}
            items.append({
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": float(hole_d_mm)},
                "placement": {"center_xy_mm": (cx, cy)},
                "feature": feature,
            })
    return items

def slot_pocket(center_xy: Tuple[float, float], *, length_mm: float, width_mm: float, depth: str | float = "through") -> List[Dict[str, Any]]:
    cx, cy = float(center_xy[0]), float(center_xy[1])
    feat = {"type": "pocket", "depth": "through"} if depth == "through" else {"type": "pocket", "depth_mm": float(depth)}
    # Full-depth pocket is acceptable for slots with your current ops
    return [{
        "kind": "shape",
        "type": "Rect",
        "geometry": {"w_mm": float(length_mm), "h_mm": float(width_mm)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feat,
    }]

def dogbone_rect(center_xy: Tuple[float, float], *, w_mm: float, h_mm: float, tool_d_mm: float) -> List[Dict[str, Any]]:
    cx, cy = float(center_xy[0]), float(center_xy[1])
    w, h, td = float(w_mm), float(h_mm), float(tool_d_mm)
    rx = w * 0.5
    ry = h * 0.5
    holes = []
    for dx in (-rx, rx):
        for dy in (-ry, ry):
            holes.append({
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": td},
                "placement": {"center_xy_mm": (cx + dx, cy + dy)},
                "feature": {"type": "hole", "depth": "through"},
            })
    rect_profile = {
        "kind": "shape",
        "type": "Rect",
        "geometry": {"w_mm": w, "h_mm": h},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": {"type": "profile", "depth": "through", "side": "outside"},
    }
    return [rect_profile] + holes
