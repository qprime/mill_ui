from __future__ import annotations
from typing import List, Dict, Any, Tuple
from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.cad.layout.place import item_size_mm

__all__ = ["render_svg_layout"]

def _svg_header(w: float, h: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">\n'
        f'  <g transform="scale(1,-1) translate(0,-{h})">\n'
        f'    <style> .panel {{ fill:none; stroke:#888; stroke-width:0.6; }} '
        f'.item {{ fill:none; stroke:#000; stroke-width:0.5; }} </style>\n'
    )

def _svg_footer() -> str:
    return "  </g>\n</svg>\n"

def _rect_svg(x: float, y: float, w: float, h: float, cls: str) -> str:
    return f'    <rect class="{cls}" x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" />\n'

def _circle_svg(cx: float, cy: float, r: float, cls: str) -> str:
    return f'    <circle class="{cls}" cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" />\n'

def render_svg_layout(panel: Panel, placements: List[Dict[str, Any]]) -> str:
    """Render a simple debug SVG for a panel + placed items.
    For unknown items, draws the item's bounding box sized by item_size_mm.
    """
    w, h = panel.width, panel.height
    out = _svg_header(w, h)
    # panel border
    out += _rect_svg(0.0, 0.0, w, h, "panel")
    # items
    for pl in placements:
        item = pl.get("item", {})
        cx, cy = pl.get("center_xy_mm", (0.0, 0.0))
        kind = item.get("kind")
        if kind == "shape":
            t = item.get("type")
            g = item.get("geometry", {})
            if t == "Rect":
                iw, ih = float(g.get("w_mm", 0.0)), float(g.get("h_mm", 0.0))
                out += _rect_svg(cx - iw/2, cy - ih/2, iw, ih, "item")
                continue
            if t == "Circle":
                d = float(g.get("diameter_mm", 0.0))
                out += _circle_svg(cx, cy, d/2.0, "item")
                continue
        # fallback to bounding box of item size
        iw, ih = item_size_mm(item)
        out += _rect_svg(cx - iw/2, cy - ih/2, iw, ih, "item")
    out += _svg_footer()
    return out
