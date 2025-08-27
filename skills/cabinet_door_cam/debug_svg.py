# path: skills/cabinet_door_cam/debug_svg.py
# desc: Tiny SVG renderer for cabinet door CAM geometry (stock, panel, anchors, hinges).
# api: render_debug_svg(cfg: MergedConfig, geo: Geometry, out_path: str | None) -> str
# tags: svg, debug, visualization

from __future__ import annotations
from typing import List
from pathlib import Path
from .types import MergedConfig, Geometry, Rect, Circle

def _rect_svg(r: Rect, cls: str) -> str:
    return f'<rect class="{cls}" x="{r.x}" y="{r.y}" width="{r.w}" height="{r.h}" />'

def _circle_svg(x: float, y: float, radius: float, cls: str) -> str:
    return f'<circle class="{cls}" cx="{x}" cy="{y}" r="{radius}" />'

def _crosshair_svg(x: float, y: float, cls: str, size: float = 6.0) -> str:
    s = size / 2.0
    return (
        f'<line class="{cls}" x1="{x-s}" y1="{y}" x2="{x+s}" y2="{y}"/>'
        f'<line class="{cls}" x1="{x}" y1="{y-s}" x2="{x}" y2="{y+s}"/>'
    )

def render_debug_svg(cfg: MergedConfig, geo: Geometry, out_path: str | None = None) -> str:
    """
    Returns SVG text. If out_path is provided, writes the SVG and returns the absolute path.
    Coordinates are in mm, origin at lower-left-front (front-view semantics).
    """
    W, H = geo.stock_rect.w, geo.stock_rect.h

    # Basic stylesheet for clarity in dark/light themes
    style = """
    <style>
      svg { background: #fff; }
      .stock { fill:none; stroke:#333; stroke-width:0.6; }
      .panel { fill:none; stroke:#1f77b4; stroke-width:0.8; }
      .border{ fill:none; stroke:#2ca02c; stroke-dasharray:4 3; stroke-width:0.6; }
      .anchor{ fill:none; stroke:#d62728; stroke-width:0.8; }
      .hinge { stroke:#9467bd; stroke-width:0.8; }
      .label { font: 8px monospace; fill:#111; }
      .axis  { stroke:#aaa; stroke-width:0.3; }
    </style>
    """

    # Build SVG elements
    elements: List[str] = []

    # Axes for reference (origin lower-left)
    elements.append(f'<line class="axis" x1="0" y1="0" x2="{W}" y2="0"/>')
    elements.append(f'<line class="axis" x1="0" y1="0" x2="0" y2="{H}"/>')

    # Stock / border / panel
    elements.append(_rect_svg(geo.stock_rect, "stock"))
    elements.append(_rect_svg(geo.border_rect, "border"))
    elements.append(_rect_svg(geo.panel_rect, "panel"))

    # Anchors (as circles)
    for c in geo.anchors:
        elements.append(_circle_svg(c.x, c.y, c.r, "anchor"))

    # Hinge centers (crosshairs) + diameter outline
    for (hx, hy) in geo.hinge_centers:
        elements.append(_crosshair_svg(hx, hy, "hinge"))
        elements.append(_circle_svg(hx, hy, geo.hinge_diameter_mm/2.0, "hinge"))

    # Labels
    labels = [
        (4, 10, f"style: {cfg.style.style_id}.v{cfg.style.version}"),
        (4, 20, f"size: {cfg.order.width_mm} x {cfg.order.height_mm} x {cfg.order.thickness_mm} mm"),
        (4, 30, f"panel depth: {geo.panel_depth_mm} mm  | hinge side: {cfg.order.hinge_side}"),
        (4, 40, f"anchors: {'yes' if cfg.order.anchors_enabled else 'no'} face={cfg.order.anchors_face} mode={cfg.order.anchors_mode}"),
        (4, 50, f"origin: lower_left_top  (0,0 at lower-left)"),
    ]
    for (x, y, t) in labels:
        elements.append(f'<text class="label" x="{x}" y="{y}">{t}</text>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">'
        f"{style}"
        + "\n".join(elements) +
        "</svg>"
    )

    if out_path:
        p = Path(out_path).with_suffix(".svg")
        p.write_text(svg, encoding="utf-8")
        return str(p.resolve())
    return svg
