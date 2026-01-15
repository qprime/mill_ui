
from __future__ import annotations
from typing import Iterable, Dict, Any, List, Tuple

from cam.types import Vec2
from cam.primitives import rectangle, circle as circle_shape
from cam.transforms import Transform2D, place
from cam.model.tool import Tool
from cam.model.material import Material
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.model.setup import Setup

from cam.ops.profile import profile_outline
from cam.ops.pocket import pocket_raster
from cam.ops.drill import drill_peck
from cam.ops.engrave import engrave_lines
from cam.ops.bore import bore_helical, pocket_circle_concentric
from cam.ops.pocket_region import pocket_region_rect_raster

from cam.planner.select import (
    pick_for_profile, pick_for_pocket, pick_for_hole, pick_for_engrave, ToolSpec
)
from cam.planner.params import stepdown_for, stepover_for

def _as_tool(spec: ToolSpec) -> Tool:
    return Tool(
        name=spec.name,
        diameter=spec.diameter,
        kind=spec.kind,
        rpm=spec.rpm,
        feed_xy=spec.feed_xy,
        feed_z=spec.feed_z,
    )

def _rect_shape(w: float, h: float, center: Tuple[float, float]) -> Any:
    shp = rectangle(w, h)
    cx, cy = center
    return place(shp, Transform2D(tx=cx - w / 2.0, ty=cy - h / 2.0))

def _circle_shape(d: float, center: Tuple[float, float]) -> Any:
    cx, cy = center
    return circle_shape(Vec2(cx, cy), d / 2.0)

def _ensure_center(rec: Dict[str, Any]) -> Tuple[float, float]:
    c = rec.get("center_xy_mm")
    if isinstance(c, (list, tuple)) and len(c) == 2:
        return float(c[0]), float(c[1])
    return 0.0, 0.0

def _pick_setup(spec: ToolSpec, *, stock: Stock, material: Material, machine: Machine, safe_z: float) -> Setup:
    return Setup(
        stock=stock,
        tool=_as_tool(spec),
        material=material,
        machine=machine,
        safe_z=safe_z,
    )


def _offset_rect_shape(w: float, h: float, center: Tuple[float, float], offset: float):
    w2 = w + 2.0 * offset
    h2 = h + 2.0 * offset
    if w2 <= 0 or h2 <= 0:
        return None
    return _rect_shape(w2, h2, center)

def _offset_circle_shape(d: float, center: Tuple[float, float], offset: float):
    d2 = d + 2.0 * offset
    if d2 <= 0:
        return None
    return _circle_shape(d2, center)

def hints_to_moves(
    hints: Dict[str, Any],
    *,
    tool_db: Iterable[dict],
    material: Material,
    machine: Machine,
    stock: Stock,
    safe_z: float = 5.0,
) -> List[Dict[str, Any]]:
    moves: List[Dict[str, Any]] = []

    min_channel = float(hints.get("min_channel_width_mm", 6.0))


    for rec in hints.get("pockets", []):
        geom = rec.get("geometry") or {}
        shape_name = rec.get("shape")
        t = pick_for_pocket(tool_db, min_channel_width_mm=min_channel)
        setup = _pick_setup(t, stock=stock, material=material, machine=machine, safe_z=safe_z)
        depth = float(rec.get("depth_mm", 0.0))
        step_over = stepover_for(tool_diameter=t.diameter)
        step_down = stepdown_for(tool_diameter=t.diameter, cap_mm=3.0)

        if shape_name == "Rect":
            w, h = float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0))
            shape = _rect_shape(w, h, _ensure_center(rec))
            moves += pocket_raster(shape, setup, depth=depth, stepover=step_over)
        elif shape_name == "Circle":

            d = float(geom.get("diameter_mm", 0.0))
            cx, cy = _ensure_center(rec)
            out = pocket_circle_concentric(
                (cx, cy), d, setup,
                depth=depth, stepover_mm=step_over, stepdown_mm=step_down, finish=True
            )
            if out:
                moves += out
            else:

                shape = _circle_shape(d, (cx, cy))
                moves += pocket_raster(shape, setup, depth=depth, stepover=step_over)
        elif shape_name == "Region":

            moves += pocket_region_rect_raster(
                rec, setup,
                default_center_xy=_ensure_center(rec),
                depth_mm=depth,
                stepover_mm=step_over,
            )
        else:
            continue


    for rec in hints.get("holes", []):
        geom = rec.get("geometry") or {}
        if rec.get("shape") != "Circle":
            continue
        D = float(geom.get("diameter_mm", 0.0))
        t = pick_for_hole(tool_db, hole_diameter_mm=D)
        setup = _pick_setup(t, stock=stock, material=material, machine=machine, safe_z=safe_z)
        tool_d = float(t.diameter)
        x, y = _ensure_center(rec)
        depth = float(rec.get("depth_mm", 0.0))

        if D <= tool_d + 1e-9:
            peck = stepdown_for(tool_diameter=t.diameter, cap_mm=2.5)
            moves += drill_peck([(x, y)], setup, depth=depth, peck=peck)
        elif D <= 3.0 * tool_d + 1e-9:
            sd = stepdown_for(tool_diameter=t.diameter, cap_mm=2.5)
            moves += bore_helical((x, y), D, setup, depth=depth, stepdown_mm=sd)
        else:
            so = stepover_for(tool_diameter=t.diameter)
            sd = stepdown_for(tool_diameter=t.diameter, cap_mm=3.0)
            moves += pocket_circle_concentric((x, y), D, setup, depth=depth, stepover_mm=so, stepdown_mm=sd, finish=True)


    for rec in hints.get("profiles", []):
        geom = rec.get("geometry") or {}
        side = str(rec.get("side", "on")).lower()
        t = pick_for_profile(tool_db)
        setup = _pick_setup(t, stock=stock, material=material, machine=machine, safe_z=safe_z)
        tool_r = 0.5 * float(t.diameter)
        off = 0.0
        if side == "outside":
            off = +tool_r
        elif side == "inside":
            off = -tool_r

        if rec.get("shape") == "Rect":
            w, h = float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0))
            shape = _offset_rect_shape(w, h, _ensure_center(rec), off) if off != 0.0 else _rect_shape(w, h, _ensure_center(rec))
            if shape is None:
                continue
        elif rec.get("shape") == "Circle":
            d = float(geom.get("diameter_mm", 0.0))
            shape = _offset_circle_shape(d, _ensure_center(rec), off) if off != 0.0 else _circle_shape(d, _ensure_center(rec))
            if shape is None:
                continue
        else:
            continue

        step_down = stepdown_for(tool_diameter=t.diameter, cap_mm=3.0)
        depth = float(rec.get("depth_mm", 0.0))
        moves += profile_outline(shape, setup, depth=depth, step_down=step_down)


    for rec in hints.get("engraves", []):
        geom = rec.get("geometry") or {}
        lines = []
        if rec.get("shape") == "Polyline":
            pts = geom.get("points") or []
            cx, cy = _ensure_center(rec)
            line = [(float(p[0]) + cx, float(p[1]) + cy) for p in pts if isinstance(p, (tuple, list)) and len(p) == 2]
            if line:
                lines.append(line)
        if not lines:
            continue
        t = pick_for_engrave(tool_db)
        setup = _pick_setup(t, stock=stock, material=material, machine=machine, safe_z=safe_z)
        moves += engrave_lines(lines, setup, z=-abs(float(rec.get("depth_mm", 0.3))))

    return moves
