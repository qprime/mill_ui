# path: skills/mill_ui/compositions/math_art/mandelbrot_outline.py
"""Mandelbrot outline + fill (native-accelerated).

Emits:
- Engrave polylines for the set's boundary
- Pocket rectangles using merged horizontal spans for the interior

Parameters (subset):
- width_mm, height_mm
- resolution_x, resolution_y (sampling grid)
- iterations, escape_radius, real_min/max, imag_min/max
- outline_depth_mm (engrave depth)
- pocket_depth_mm (pocket depth for interior)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from skills.mill_ui.compositions.base import TemplateBase, register_template
from skills.mill_ui.cam.native.core import is_native_available, mandelbrot_outline_fill as _native_mandel


@dataclass(frozen=True)
class OutlineParams:
    width_mm: float
    height_mm: float
    res_x: int
    res_y: int
    iterations: int
    escape_radius: float
    real_min: float
    real_max: float
    imag_min: float
    imag_max: float
    outline_depth_mm: float
    pocket_depth_mm: float

    @classmethod
    def from_dict(cls, p: Dict[str, Any]) -> "OutlineParams":
        return cls(
            width_mm=float(p.get("width_mm", 200.0)),
            height_mm=float(p.get("height_mm", 150.0)),
            res_x=max(8, int(p.get("resolution_x", p.get("resolution", 400)))),
            res_y=max(8, int(p.get("resolution_y", p.get("resolution", 300)))),
            iterations=max(50, int(p.get("iterations", 120))),
            escape_radius=float(p.get("escape_radius", 2.0)),
            real_min=float(p.get("real_min", -2.0)),
            real_max=float(p.get("real_max", 1.0)),
            imag_min=float(p.get("imag_min", -1.25)),
            imag_max=float(p.get("imag_max", 1.25)),
            outline_depth_mm=max(0.1, float(p.get("outline_depth_mm", 0.8))),
            pocket_depth_mm=max(0.1, float(p.get("pocket_depth_mm", p.get("depth_mm", 2.0)))),
        )


@register_template("MandelbrotOutlineFill")
class MandelbrotOutlineFill(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        cfg = OutlineParams.from_dict(params)
        if not is_native_available():
            # Surface a single note item when native isn't built
            return [
                {
                    "kind": "note",
                    "id": "mandelbrot_outline:native_required",
                    "message": "Native CAM core not available; build the C++ extension to enable MandelbrotOutlineFill",
                }
            ]

        payload = _native_mandel(
            width_mm=cfg.width_mm,
            height_mm=cfg.height_mm,
            resolution_x=cfg.res_x,
            resolution_y=cfg.res_y,
            iterations=cfg.iterations,
            escape_radius=cfg.escape_radius,
            real_min=cfg.real_min,
            real_max=cfg.real_max,
            imag_min=cfg.imag_min,
            imag_max=cfg.imag_max,
        )

        items: List[Dict[str, Any]] = []

        # Outline polylines (engrave)
        for k, pts in enumerate(payload.get("polylines", []), start=1):
            if not pts:
                continue
            items.append(
                {
                    "kind": "shape",
                    "type": "Polyline",
                    "id": f"outline:{k}",
                    "geometry": {"points": list(pts), "closed": False},
                    "placement": {"center_xy_mm": (0.0, 0.0)},
                    "feature": {"type": "engrave", "depth_mm": min(cfg.outline_depth_mm, thickness_mm)},
                }
            )

        # Interior spans (rect pockets) — coalesce adjacent rows into tall rectangles to reduce count
        spans = payload.get("spans", []) or []
        # Sort by y then x0 to ensure stable sweep
        spans.sort(key=lambda s: (float(s.get("y", 0.0)), float(s.get("x0", 0.0))))
        merged: List[Dict[str, float]] = []
        tol = 0.05  # mm tolerance to merge columns
        for s in spans:
            x0 = float(s.get("x0", 0.0))
            x1 = float(s.get("x1", 0.0))
            yb = float(s.get("y", 0.0))
            h = float(s.get("h", 0.0))
            if x1 - x0 <= 0.0 or h <= 0.0:
                continue
            if merged:
                m = merged[-1]
                same_col = abs(m["x0"] - x0) <= tol and abs(m["x1"] - x1) <= tol
                touching = abs((m["y"] + m["h"]) - yb) <= tol
                if same_col and touching:
                    m["h"] += h
                    continue
            merged.append({"x0": x0, "x1": x1, "y": yb, "h": h})

        for k, m in enumerate(merged, start=1):
            w = max(0.0, float(m["x1"]) - float(m["x0"]))
            h = float(m["h"]) if w > 0.0 else 0.0
            if w <= 0.0 or h <= 0.0:
                continue
            cx = float(m["x0"]) + 0.5 * w
            cy = float(m["y"]) + 0.5 * h
            items.append(
                {
                    "kind": "shape",
                    "type": "Rect",
                    "id": f"span:{k}",
                    "geometry": {"w_mm": w, "h_mm": h},
                    "placement": {"center_xy_mm": (cx, cy)},
                    "feature": {"type": "pocket", "depth_mm": min(cfg.pocket_depth_mm, thickness_mm)},
                }
            )

        return items
