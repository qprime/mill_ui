# path: skills/mill_ui/cam/planner/passes.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from types import SimpleNamespace
import math

from skills.mill_ui.core.types import Vec2
from skills.mill_ui.cad.primitives import rectangle, circle as circle_shape
from skills.mill_ui.cad.transforms import Transform2D, place

from skills.mill_ui.cam.model.tool import Tool
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.setup import Setup

from skills.mill_ui.cam.ops.profile import profile_outline
from skills.mill_ui.cam.ops.pocket import pocket_raster
from skills.mill_ui.cam.ops.pocket_region import pocket_region_rect_raster
from skills.mill_ui.cam.ops.drill import drill_peck
from skills.mill_ui.cam.ops.engrave import engrave_lines
from skills.mill_ui.cam.ops.bore import bore_helical, pocket_circle_concentric

# ---------------- Shapes / Specs ----------------

def _as_tool(spec: SimpleNamespace) -> Tool:
    return Tool(
        name=spec.name,
        diameter=spec.diameter,
        kind=spec.kind,  # type: ignore[arg-type]
        rpm=spec.rpm,
        feed_xy=spec.feed_xy,
        feed_z=spec.feed_z,
    )

def _spec_from_dict(d: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        name=d.get("name","tool"),
        diameter=float(d.get("diameter", 0.0)),
        kind=str(d.get("kind","flat")),
        rpm=float(d.get("rpm", 18000.0)),
        feed_xy=float(d.get("feed_xy", 2000.0)),
        feed_z=float(d.get("feed_z", 300.0)),
        rotation=d.get("rotation"),
        depth_per_pass=float(d.get("depth_per_pass", 0.0)) if d.get("depth_per_pass") is not None else None,
        stepover_percent=float(d.get("stepover_percent", 0.0)) if d.get("stepover_percent") is not None else None,
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

def _tool_identity(spec: SimpleNamespace) -> Dict[str, Any]:
    return {
        "name": spec.name,
        "diameter": float(spec.diameter),
        "kind": getattr(spec, "kind", "flat"),
        "rotation": getattr(spec, "rotation", None),
        "rpm": float(spec.rpm),
        "feed_xy": float(spec.feed_xy),
        "feed_z": float(spec.feed_z),
    }

def _pass_key(op: str, tool_id: Dict[str, Any]) -> Tuple[str, float, str, Optional[str]]:
    return (op, tool_id["diameter"], tool_id.get("kind", "flat"), tool_id.get("rotation"))

def _mm_str(v: float) -> str:
    return f"{v:.2f}mm".replace(".00mm", "mm")

# ---------------- Tool selection ----------------

def _flat_tools(db: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [t for t in db if str(t.get("kind","flat")).lower() != "ball"]

def _ball_or_v_tools(db: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [t for t in db if str(t.get("kind","")).lower() in ("ball","v")]

def _pick_for_pocket(db: List[Dict[str, Any]]) -> SimpleNamespace:
    cands = _flat_tools(db)
    cands.sort(key=lambda t: (0 if str(t.get("rotation","")).lower() in ("upcut","compression") else 1,
                              -float(t.get("diameter", 0.0))))
    return _spec_from_dict(cands[0])

def _pick_for_profile(db: List[Dict[str, Any]], kerf_mm: float) -> SimpleNamespace:
    cands = _flat_tools(db)
    if kerf_mm > 0 and cands:
        cands.sort(key=lambda t: abs(float(t.get("diameter",0.0)) - kerf_mm))
        return _spec_from_dict(cands[0])
    cands.sort(key=lambda t: float(t.get("diameter", 0.0)))
    return _spec_from_dict(cands[0] if cands else _spec_from_dict(db[0]))

def _pick_for_engrave(db: List[Dict[str, Any]]) -> SimpleNamespace:
    cands = _ball_or_v_tools(db)
    if cands:
        cands.sort(key=lambda t: float(t.get("diameter", 999.0)))
        return _spec_from_dict(cands[0])
    db_sorted = sorted(db, key=lambda t: float(t.get("diameter", 999.0)))
    return _spec_from_dict(db_sorted[0])

# ---------------- Per-tool pass params ----------------

def _stepdown_for_tool(spec: SimpleNamespace) -> float:
    if getattr(spec, "depth_per_pass", None):
        return float(spec.depth_per_pass)
    return min(3.0, 0.5 * float(spec.diameter))

def _stepover_for_tool(spec: SimpleNamespace) -> float:
    if getattr(spec, "stepover_percent", None):
        return float(spec.diameter) * (float(spec.stepover_percent) / 100.0)
    return float(spec.diameter) * 0.40

# ---------------- Planner ----------------

def plan_passes(
    hints: Dict[str, Any],
    *,
    tool_db: List[dict],
    material: Material,
    machine: Machine,
    stock: Stock,
    safe_z: float = 6.0,
    prime_spindle: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    kerf_mm = float(hints.get("kerf_width_mm", 0.0))

    passes: Dict[Tuple[str, float, str, Optional[str]], Dict[str, Any]] = {}
    summary_passes: List[Dict[str, Any]] = []

    def _get_or_make_pass(op_name: str, spec: SimpleNamespace) -> Dict[str, Any]:
        tool_id = _tool_identity(spec)
        key = _pass_key(op_name, tool_id)
        if key in passes:
            return passes[key]
        setup = Setup(stock=stock, tool=_as_tool(spec), material=material, machine=machine, safe_z=safe_z)
        rot = tool_id.get("rotation")
        name_bits = [op_name, _mm_str(tool_id["diameter"])]
        if rot: name_bits.append(str(rot))
        filename = "-".join(name_bits).replace(" ", "_") + ".nc"
        p = {"op": op_name, "tool": tool_id, "setup": setup,
             "moves": [] if not prime_spindle else [{"kind": "set_rpm", "rpm": 0}],
             "filename": filename, "count": 0}
        passes[key] = p
        return p

    # ---------- Pockets ----------
    for rec in hints.get("pockets", []):
        geom = rec.get("geometry") or {}
        shape_name = rec.get("shape")
        t = _pick_for_pocket(tool_db)
        p = _get_or_make_pass("pocket", t)
        setup: Setup = p["setup"]
        depth = float(rec.get("depth_mm", 0.0))
        step_over = _stepover_for_tool(t)
        step_down = _stepdown_for_tool(t)

        if shape_name == "Rect":
            w, h = float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0))
            shp = _rect_shape(w, h, _ensure_center(rec))
            p["moves"] += pocket_raster(shp, setup, depth=depth, stepover=step_over, stepdown=step_down)
        elif shape_name == "Circle":
            d = float(geom.get("diameter_mm", 0.0))
            cx, cy = _ensure_center(rec)
            p["moves"] += pocket_circle_concentric((cx, cy), d, setup,
                                                   depth=depth, stepover_mm=step_over,
                                                   stepdown_mm=step_down, finish=True)
        elif shape_name == "Region":
            p["moves"] += pocket_region_rect_raster(rec, setup,
                                                    default_center_xy=_ensure_center(rec),
                                                    depth_mm=depth,
                                                    stepover_mm=step_over,
                                                    stepdown_mm=step_down)
        else:
            continue
        p["count"] += 1

    # ---------- Holes ----------
    for rec in hints.get("holes", []):
        if rec.get("shape") != "Circle":
            continue
        geom = rec.get("geometry") or {}
        D = float(geom.get("diameter_mm", 0.0))
        x, y = _ensure_center(rec)
        depth = float(rec.get("depth_mm", 0.0))
        t = _pick_for_pocket(tool_db)
        tool_d = float(t.diameter)
        eps = 0.05
        if D <= tool_d + eps:
            p = _get_or_make_pass("drill", t)
            peck = min(_stepdown_for_tool(t), 2.5)
            p["moves"] += drill_peck([(x, y)], p["setup"], depth=depth, peck=peck)
        elif D <= 3.0 * tool_d + eps:
            p = _get_or_make_pass("bore", t)
            sd = _stepdown_for_tool(t)
            p["moves"] += bore_helical((x, y), D, p["setup"], depth=depth, stepdown_mm=sd)
        else:
            p = _get_or_make_pass("pocket", t)
            so = _stepover_for_tool(t); sd = _stepdown_for_tool(t)
            p["moves"] += pocket_circle_concentric((x, y), D, p["setup"], depth=depth,
                                                   stepover_mm=so, stepdown_mm=sd, finish=True)
        passes[_pass_key(p["op"], p["tool"])]["count"] += 1

    # ---------- Profiles ----------
    for rec in hints.get("profiles", []):
        geom = rec.get("geometry") or {}
        side = (rec.get("side") or "on").lower()
        t = _pick_for_profile(tool_db, kerf_mm=kerf_mm)
        p = _get_or_make_pass("profile", t)
        setup: Setup = p["setup"]
        step_down = _stepdown_for_tool(t)
        depth = float(rec.get("depth_mm", 0.0))

        if rec.get("shape") == "Rect":
            w, h = float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0))
            if side == "outside":
                w2, h2 = w + t.diameter, h + t.diameter
            elif side == "inside":
                w2, h2 = max(0.0, w - t.diameter), max(0.0, h - t.diameter)
            else:
                w2, h2 = w, h
            if w2 <= 0.0 or h2 <= 0.0: continue
            shp = _rect_shape(w2, h2, _ensure_center(rec))
        elif rec.get("shape") == "Circle":
            d = float(geom.get("diameter_mm", 0.0))
            if side == "outside":
                d2 = d + t.diameter
            elif side == "inside":
                d2 = max(0.0, d - t.diameter)
            else:
                d2 = d
            if d2 <= 0.0: continue
            shp = _circle_shape(d2, _ensure_center(rec))
        else:
            continue

        p["moves"] += profile_outline(shp, setup, depth=depth, step_down=step_down)
        p["count"] += 1

    # ---------- Engraves ----------
    for rec in hints.get("engraves", []):
        geom = rec.get("geometry") or {}
        lines = []
        if rec.get("shape") == "Polyline":
            pts = geom.get("points") or []
            cx, cy = _ensure_center(rec)
            line = [(float(p[0]) + cx, float(p[1]) + cy) for p in pts if isinstance(p, (tuple, list)) and len(p) == 2]
            if line: lines.append(line)
        if not lines: continue
        t = _pick_for_engrave(tool_db)
        p = _get_or_make_pass("engrave", t)
        p["moves"] += engrave_lines(lines, p["setup"], z=-abs(float(rec.get("depth_mm", 0.3))))
        p["count"] += 1

    # ---------- Summaries ----------
    pass_list = list(passes.values())

    def _summarize_moves(moves: List[Dict[str, Any]]) -> Dict[str, Any]:
        x = y = z = None; cut_len_xy = 0.0; cut_len_3d = 0.0; plunge_z = 0.0; min_z = 0.0
        for m in moves:
            k = m.get("kind")
            if k in ("rapid","cut"):
                nx = m.get("x", x); ny = m.get("y", y); nz = m.get("z", z)
                if k == "cut" and (x is not None or y is not None or z is not None):
                    dx = 0.0 if nx is None or x is None else (nx - x)
                    dy = 0.0 if ny is None or y is None else (ny - y)
                    dz = 0.0 if nz is None or z is None else (nz - z)
                    seg_xy = math.hypot(dx, dy); seg_3d = math.sqrt(dx*dx + dy*dy + dz*dz)
                    cut_len_xy += max(0.0, seg_xy); cut_len_3d += max(0.0, seg_3d)
                    if abs(dx) < 1e-9 and abs(dy) < 1e-9 and nz is not None and z is not None:
                        plunge_z += abs(nz - z)
                    if nz is not None: min_z = min(min_z, nz)
                x, y, z = nx, ny, nz
        return {"cut_length_xy_mm": cut_len_xy, "cut_length_3d_mm": cut_len_3d,
                "plunge_travel_mm": plunge_z, "max_depth_mm": abs(min_z)}

    summary_passes: List[Dict[str, Any]] = []
    for p in pass_list:
        s = _summarize_moves(p["moves"])
        info = {
            "filename": p["filename"],
            "operation": p["op"],
            "tool": p["tool"],
            "item_count": p["count"],
            "metrics": s,
            "description": f"{p['op']} with {p['tool']['diameter']:.2f}mm {p['tool'].get('kind','flat')}"
                           + (f" ({p['tool']['rotation']})" if p['tool'].get('rotation') else ""),
        }
        summary_passes.append(info)

    job_summary = {"passes": summary_passes,
                   "notes": "Grouped by operation and tool; DB depth_per_pass/stepover honored."}
    return pass_list, job_summary
