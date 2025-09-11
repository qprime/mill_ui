# path: skills/mill_ui/recipes/cookbook/examples.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple

from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.api.cam import build_cam_hints, write_gcode
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.planner.pipeline import hints_to_moves

# Optional helpers if present (components shipped earlier)
try:
    from skills.mill_ui.recipes.components import shelf_pin_grid, counterbore
    _HAS_COMPONENTS = True
except Exception:
    _HAS_COMPONENTS = False


def _mk_setup_objs(panel: Panel) -> Tuple[Material, Machine, Stock]:
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")
    stock = Stock(width=panel.width, height=panel.height, thickness=panel.thickness)
    return material, machine, stock


def example_progressive_hole_grid(
    panel: Panel,
    *,
    tool_db: List[Dict[str, Any]],
    origin_xy: Tuple[float, float] = (40.0, 40.0),
    rows: int = 3,
    cols: int = 4,
    pitch_x_mm: float = 30.0,
    pitch_y_mm: float = 30.0,
    start_d_mm: float = 4.0,
    step_d_mm: float = 2.0,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Generates a grid of holes that increase in diameter across the grid.
    Exercises hole policy: small drill, medium bore, large pocket-circle.
    """
    ox, oy = origin_xy
    items: List[Dict[str, Any]] = []

    if _HAS_COMPONENTS:
        # uniform grid then adjust diameters progressively
        items = shelf_pin_grid((ox, oy), rows=rows, cols=cols,
                               pitch_x_mm=pitch_x_mm, pitch_y_mm=pitch_y_mm,
                               hole_d_mm=start_d_mm, depth="through")
        for i, it in enumerate(items):
            r = i // cols
            c = i % cols
            it["geometry"]["diameter_mm"] = start_d_mm + (r * cols + c) * step_d_mm
    else:
        # fallback: synthesize explicitly with placements
        for r in range(rows):
            for c in range(cols):
                cx = ox + c * pitch_x_mm
                cy = oy + r * pitch_y_mm
                d = start_d_mm + (r * cols + c) * step_d_mm
                items.append({
                    "kind": "shape",
                    "type": "Circle",
                    "geometry": {"diameter_mm": d},
                    "placement": {"center_xy_mm": (cx, cy)},
                    "feature": {"type": "hole", "depth": "through"},
                })

    material, machine, stock = _mk_setup_objs(panel)
    hints = build_cam_hints(items_resolved=items, sheet_thickness=panel.thickness)
    moves = hints_to_moves(
        hints, tool_db=tool_db, material=material, machine=machine, stock=stock, safe_z=panel.safe_z
    )
    gcode = write_gcode(moves, safe_z=panel.safe_z)
    return moves, gcode


def example_organizer_tray_rect_islands(
    panel: Panel,
    *,
    tool_db: List[Dict[str, Any]],
    center_xy: Tuple[float, float] = (150.0, 100.0),
    outer_w_mm: float = 160.0,
    outer_h_mm: float = 100.0,
    depth_mm: float = 8.0,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Rectangular pocket with rectangular islands (compartments).
    Uses Region with Rect outer + Rect holes (supported by pocket_region_rect_raster).
    """
    cx, cy = center_xy
    # Create 4 compartments by leaving two rectangular islands
    hole_w = outer_w_mm * 0.3
    hole_h = outer_h_mm * 0.8
    items = [{
        "kind": "shape",
        "type": "Region",
        "geometry": {
            "outer": {"type": "Rect", "geometry": {"w_mm": outer_w_mm, "h_mm": outer_h_mm}, "center_xy_mm": (cx, cy)},
            "holes": [
                {"type": "Rect", "geometry": {"w_mm": hole_w, "h_mm": hole_h}, "center_xy_mm": (cx - outer_w_mm*0.25, cy)},
                {"type": "Rect", "geometry": {"w_mm": hole_w, "h_mm": hole_h}, "center_xy_mm": (cx + outer_w_mm*0.25, cy)},
            ],
        },
        "feature": {"type": "pocket", "depth_mm": depth_mm},
    }]

    material, machine, stock = _mk_setup_objs(panel)
    hints = build_cam_hints(items_resolved=items, sheet_thickness=panel.thickness)
    moves = hints_to_moves(
        hints, tool_db=tool_db, material=material, machine=machine, stock=stock, safe_z=panel.safe_z
    )
    gcode = write_gcode(moves, safe_z=panel.safe_z)
    return moves, gcode


def example_counterbored_holes(
    panel: Panel,
    *,
    tool_db: List[Dict[str, Any]],
    centers: List[Tuple[float, float]] = ((80.0, 60.0), (120.0, 60.0)),
    through_d_mm: float = 5.0,
    bore_d_mm: float = 20.0,
    bore_depth_mm: float = 3.0,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Classic counterbore: shallow circular pocket + through hole at the same center.
    """
    items: List[Dict[str, Any]] = []
    for c in centers:
        if _HAS_COMPONENTS:
            items.extend(counterbore(c, through_d_mm=through_d_mm, bore_d_mm=bore_d_mm, bore_depth_mm=bore_depth_mm))
        else:
            cx, cy = c
            items.append({
                "kind": "shape", "type": "Circle",
                "geometry": {"diameter_mm": bore_d_mm},
                "placement": {"center_xy_mm": (cx, cy)},
                "feature": {"type": "pocket", "depth_mm": bore_depth_mm},
            })
            items.append({
                "kind": "shape", "type": "Circle",
                "geometry": {"diameter_mm": through_d_mm},
                "placement": {"center_xy_mm": (cx, cy)},
                "feature": {"type": "hole", "depth": "through"},
            })

    material, machine, stock = _mk_setup_objs(panel)
    hints = build_cam_hints(items_resolved=items, sheet_thickness=panel.thickness)
    moves = hints_to_moves(
        hints, tool_db=tool_db, material=material, machine=machine, stock=stock, safe_z=panel.safe_z
    )
    gcode = write_gcode(moves, safe_z=panel.safe_z)
    return moves, gcode
