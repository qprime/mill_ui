# path: skills/mill_ui/cad/layout/place.py
from __future__ import annotations
from typing import List, Dict, Tuple, Any
from skills.mill_ui.cad.layout.panel import Panel

__all__ = [
    "grid_place", "row_place", "col_place",
    "item_size_mm", "apply_grid_layout"
]

def grid_place(shape, rows: int, cols: int, pitch_x: float, pitch_y: float):
    from skills.mill_ui.core.types import Vec2
    from skills.mill_ui.cad.shape import Shape2D
    out: List[Shape2D] = []
    for r in range(rows):
        for c in range(cols):
            out.append(Shape2D([Vec2(p.x + c * pitch_x, p.y + r * pitch_y) for p in shape.points]))
    return out

def row_place(shape, count: int, pitch_x: float):
    from skills.mill_ui.core.types import Vec2
    from skills.mill_ui.cad.shape import Shape2D
    return [Shape2D([Vec2(p.x + i * pitch_x, p.y) for p in shape.points]) for i in range(count)]

def col_place(shape, count: int, pitch_y: float):
    from skills.mill_ui.core.types import Vec2
    from skills.mill_ui.cad.shape import Shape2D
    return [Shape2D([Vec2(p.x, p.y + i * pitch_y) for p in shape.points]) for i in range(count)]

# ------------------------------------------------------------------
# Grid layout (pure math)
# ------------------------------------------------------------------

def item_size_mm(it: Dict[str, Any]) -> Tuple[float, float]:
    """Return (w_mm, h_mm) for supported item dictionaries.

    Supported items:
      - {'kind':'door', 'params': {'outer_w': mm, 'outer_h': mm}}
      - {'kind':'shape','type':'Rect','geometry':{'w_mm': mm, 'h_mm': mm}}
      - {'kind':'shape','type':'Circle','geometry':{'diameter_mm': mm}}
      - {'kind':'shape','type':'Polyline','geometry':{'points': [[x,y],...]}}
    Unknown items return (0.0, 0.0).
    """
    if not isinstance(it, dict):
        return 0.0, 0.0
    k = it.get("kind")
    if k == "door":
        p = it.get("params", {})
        return float(p.get("outer_w", 0.0)), float(p.get("outer_h", 0.0))
    if k == "shape":
        t = it.get("type")
        g = it.get("geometry", {}) or {}
        if t == "Rect":
            return float(g.get("w_mm", 0.0)), float(g.get("h_mm", 0.0))
        if t == "Circle":
            d = float(g.get("diameter_mm", 0.0))
            return d, d
        if t == "Polyline":
            pts = g.get("points") or []
            xs = [float(p[0]) for p in pts if isinstance(p, (list, tuple)) and len(p) == 2]
            ys = [float(p[1]) for p in pts if isinstance(p, (list, tuple)) and len(p) == 2]
            if not xs or not ys:
                return 0.0, 0.0
            return (max(xs) - min(xs), max(ys) - min(ys))
    return 0.0, 0.0

def apply_grid_layout(
    panel: Panel,
    items: List[Dict[str, Any]],
    *,
    rows: int,
    cols: int,
    gap_x: float = 0.0,
    gap_y: float = 0.0,
    border: float = 0.0,
    fit: str = "tight",   # 'tight' or 'even'
) -> List[Dict[str, Any]]:
    """Lay out items in a grid on a sheet (panel), returning placements.

    Returns a list of placements: {'item': item, 'center_xy_mm': (cx, cy), 'cell_size_mm': (cw, ch)}

    - If fit == 'tight': cell size is the max of item sizes; validated to fit interior area.
    - If fit == 'even' : interior is divided evenly by rows/cols (legacy behavior).
    """
    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive")
    avail_w = panel.width  - 2 * border - (cols - 1) * gap_x
    avail_h = panel.height - 2 * border - (rows - 1) * gap_y
    if avail_w <= 0 or avail_h <= 0:
        raise ValueError("Grid + borders/gaps leave no interior area")

    # Determine cell size
    if fit == "tight":
        sizes = [item_size_mm(it) for it in items]
        max_w = max((w for (w, _) in sizes), default=0.0)
        max_h = max((h for (_, h) in sizes), default=0.0)
        cell_w, cell_h = max_w, max_h
        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y
        if block_w > avail_w + 1e-6 or block_h > avail_h + 1e-6:
            raise ValueError(
                f"Tight pack does not fit: block {block_w:.2f}×{block_h:.2f} > "
                f"avail {avail_w:.2f}×{avail_h:.2f}"
            )
    else:
        # 'even' fill: divide interior equally
        cell_w = avail_w / cols
        cell_h = avail_h / rows

    placements: List[Dict[str, Any]] = []
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(items):
                return placements
            cx = border + c * (cell_w + gap_x) + cell_w * 0.5
            cy = border + r * (cell_h + gap_y) + cell_h * 0.5
            placements.append({
                "item": items[idx],
                "center_xy_mm": (cx, cy),
                "cell_size_mm": (cell_w, cell_h),
                "row": r, "col": c
            })
            idx += 1
    return placements

