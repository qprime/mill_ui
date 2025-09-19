# path: skills/mill_ui/cam/planner/passes.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from types import SimpleNamespace
import math

from skills.mill_ui.core.types import Vec2
from skills.mill_ui.cad.primitives import rectangle, circle as circle_shape
from skills.mill_ui.cad.transforms import Transform2D, place
from skills.mill_ui.cad.shape import Shape2D

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

from skills.mill_ui.cam.path.strategies import (
    pocket_then_finish_profile,
    onion_skin_then_finish,
    profile_outline_with_tabs,
)

# --- Shared-edge merge toggle (default ON) -------------------------------
MERGE_SHARED_EDGES = True
MERGE_TOL_MM = 0.10
MIN_OVERLAP_MM = 1.00  # must overlap at least this much to treat as a seam
CLEANUP_OFFSET_MM = 0.25  # for pocket finish strategy

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

def _rect_shape(w: float, h: float, center: Tuple[float, float]) -> Shape2D:
    shp = rectangle(w, h)
    cx, cy = center
    return place(shp, Transform2D(tx=cx - w / 2.0, ty=cy - h / 2.0))

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

# ---------------- Tool selection (2.5D sane) ----------------

def _flat_tools(db: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [t for t in db if str(t.get("kind","flat")).lower() != "ball"]

def _ball_or_v_tools(db: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [t for t in db if str(t.get("kind","")).lower() in ("ball","v")]

def _pick_for_pocket(db: List[Dict[str, Any]], required_width_mm: float | None = None) -> SimpleNamespace:
    cands = _flat_tools(db)
    if not cands:
        raise ValueError("No flat tools available for pocketing")
    cands.sort(key=lambda t: (0 if str(t.get("rotation","")).lower() in ("upcut","compression") else 1,
                              -float(t.get("diameter", 0.0))))
    if required_width_mm and required_width_mm > 0.0:
        clearance = max(required_width_mm - 2 * CLEANUP_OFFSET_MM, 0.0)
        valid = [t for t in cands if float(t.get("diameter", 0.0)) <= clearance]
        if valid:
            cands = valid
        else:
            valid = [t for t in cands if float(t.get("diameter", 0.0)) < required_width_mm]
            if valid:
                cands = valid
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

# ---------------- Edge helpers ----------------

class _Edge:
    # axis-aligned edge
    __slots__ = ("orient","coord","a","b","rect_id","minx","miny","maxx","maxy")
    def __init__(self, orient: str, coord: float, a: float, b: float,
                 rect_id: str, minx: float, miny: float, maxx: float, maxy: float):
        self.orient = orient  # 'v' or 'h'
        self.coord = coord    # x for vertical, y for horizontal
        self.a = min(a, b)
        self.b = max(a, b)
        self.rect_id = rect_id
        self.minx, self.miny, self.maxx, self.maxy = minx, miny, maxx, maxy

def _rect_edges(cx: float, cy: float, w: float, h: float, rect_id: str) -> List[_Edge]:
    minx, miny = cx - w/2, cy - h/2
    maxx, maxy = cx + w/2, cy + h/2
    return [
        _Edge("v", minx, miny, maxy, rect_id, minx, miny, maxx, maxy),  # left
        _Edge("v", maxx, miny, maxy, rect_id, minx, miny, maxx, maxy),  # right
        _Edge("h", miny, minx, maxx, rect_id, minx, miny, maxx, maxy),  # bottom
        _Edge("h", maxy, minx, maxx, rect_id, minx, miny, maxx, maxy),  # top
    ]

def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    lo = max(min(a1, a2), min(b1, b2))
    hi = min(max(a1, a2), max(b1, b2))
    return max(0.0, hi - lo)

# ---------------- Planner ----------------

def _profile_moves_with_options(shape: Shape2D,
                                setup: Setup,
                                depth_mm: float,
                                tool_spec: SimpleNamespace,
                                onion_skin_mm: float,
                                tabs_opts: Dict[str, Any]) -> List[Dict[str, Any]]:
    step_down = _stepdown_for_tool(tool_spec)
    tabs_count = 0
    tabs_height = 0.0
    tab_width = None
    if tabs_opts and isinstance(tabs_opts, dict):
        try:
            tabs_count = int(tabs_opts.get("count", 0) or 0)
        except Exception:
            tabs_count = 0
        try:
            tabs_height = float(tabs_opts.get("height_mm", 3.0))
        except Exception:
            tabs_height = 3.0
        if "width_mm" in tabs_opts:
            try:
                tab_width = float(tabs_opts.get("width_mm"))
            except Exception:
                tab_width = None

    if onion_skin_mm > 0.0 and tabs_count > 0:
        raise ValueError("Onion skin and tabs cannot yet be combined in the same profile pass")

    if onion_skin_mm > 0.0:
        return onion_skin_then_finish(
            shape,
            setup,
            total_depth_mm=depth_mm,
            skin_mm=onion_skin_mm,
            step_down_mm=step_down,
        )

    if tabs_count > 0:
        return profile_outline_with_tabs(
            shape,
            setup,
            depth_mm=depth_mm,
            step_down_mm=step_down,
            tab_count=max(1, tabs_count),
            tab_height_mm=max(0.1, tabs_height),
            tab_width_mm=tab_width,
        )

    return profile_outline(shape, setup, depth_mm, step_down=step_down)


def plan_passes(
    hints: Dict[str, Any],
    *,
    tool_db: List[dict],
    material: Material,
    machine: Machine,
    stock: Stock,
    safe_z: float = 6.0,
    prime_spindle: bool = False,
    profile_opts: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    kerf_mm = float(hints.get("kerf_width_mm", 0.0))  # may be 0.0 if not provided

    passes: Dict[Tuple[str, float, str, Optional[str]], Dict[str, Any]] = {}
    summary_passes: List[Dict[str, Any]] = []
    merged_seams_count = 0

    profile_opts = profile_opts or {}
    try:
        onion_skin_mm = max(0.0, float(profile_opts.get("onion_skin_mm", 0.0)))
    except Exception:
        onion_skin_mm = 0.0
    tabs_opts = profile_opts.get("tabs") if isinstance(profile_opts.get("tabs"), dict) else {}
    tabs_enabled = False
    if isinstance(tabs_opts, dict):
        try:
            tabs_enabled = int(tabs_opts.get("count", 0) or 0) > 0
        except Exception:
            tabs_enabled = False
    try:
        cut_through_mm = max(0.0, float(profile_opts.get("cut_through_mm", 0.0)))
    except Exception:
        cut_through_mm = 0.0

    use_profile_options = onion_skin_mm > 0.0 or tabs_enabled
    merge_shared_edges = MERGE_SHARED_EDGES and not use_profile_options

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
        shape_lower = str(shape_name or "").lower()
        target_width = None
        if shape_lower == "rect":
            target_width = min(float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0)))
        elif shape_lower == "circle":
            target_width = float(geom.get("diameter_mm", 0.0))

        t = _pick_for_pocket(tool_db, required_width_mm=target_width)
        p = _get_or_make_pass("pocket", t)
        setup: Setup = p["setup"]
        depth = float(rec.get("depth_mm", 0.0))
        step_over = _stepover_for_tool(t)
        step_down = _stepdown_for_tool(t)

        if shape_name == "Rect":
            w, h = float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0))
            shp = _rect_shape(w, h, _ensure_center(rec))
            # Rough then finish the wall
            p["moves"] += pocket_then_finish_profile(
                shp, setup,
                total_depth_mm=depth,
                stepover_mm=step_over,
                step_down_mm=step_down,
                cleanup_offset_mm=CLEANUP_OFFSET_MM,
            )
        elif shape_name == "Circle":
            d = float(geom.get("diameter_mm", 0.0))
            cx, cy = _ensure_center(rec)
            p["moves"] += pocket_circle_concentric((cx, cy), d, setup,
                                                   depth=depth,
                                                   stepover_mm=step_over,
                                                   stepdown_mm=step_down,
                                                   finish=True)
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

    # ---------- Engraves ----------
    for rec in hints.get("engraves", []):
        geom = rec.get("geometry") or {}
        shape_name = str(rec.get("shape") or rec.get("type") or "").lower()
        lines: List[List[Tuple[float, float]]] = []

        if shape_name == "polyline":
            pts = geom.get("points") or []
            cx, cy = _ensure_center(rec)
            line: List[Tuple[float, float]] = []
            for pt in pts:
                if isinstance(pt, (list, tuple)) and len(pt) == 2:
                    line.append((float(pt[0]) + cx, float(pt[1]) + cy))
            if line:
                lines.append(line)
        elif shape_name == "rect":
            w = float(geom.get("w_mm", 0.0))
            h = float(geom.get("h_mm", 0.0))
            if w > 0.0 and h > 0.0:
                cx, cy = _ensure_center(rec)
                half_w, half_h = 0.5 * w, 0.5 * h
                lines.append([
                    (cx - half_w, cy - half_h),
                    (cx + half_w, cy - half_h),
                    (cx + half_w, cy + half_h),
                    (cx - half_w, cy + half_h),
                    (cx - half_w, cy - half_h),
                ])
        else:
            continue

        if not lines:
            continue

        t = _pick_for_engrave(tool_db)
        p = _get_or_make_pass("engrave", t)
        setup: Setup = p["setup"]
        depth = float(rec.get("depth_mm", 0.0))
        if depth == 0.0:
            depth = 0.3
        p["moves"] += engrave_lines(lines, setup, z=-abs(depth))
        p["count"] += len(lines)

    # ---------- Profiles (merge shared seams for Rects) ----------
    rect_profiles = [rec for rec in hints.get("profiles", []) if str(rec.get("shape","")).lower() == "rect"]
    if not merge_shared_edges or len(rect_profiles) == 0:
        # Fallback: cut each rect perimeter with kerf-aware offset (outside)
        for rec in rect_profiles:
            t = _pick_for_profile(tool_db, kerf_mm=float(hints.get("kerf_width_mm", 0.0)))
            p = _get_or_make_pass("profile", t)
            setup: Setup = p["setup"]
            depth = max(0.0, float(rec.get("depth_mm", 0.0))) + cut_through_mm
            w = float((rec.get("geometry") or {}).get("w_mm", 0.0))
            h = float((rec.get("geometry") or {}).get("h_mm", 0.0))
            shp = _rect_shape(w + t.diameter, h + t.diameter, _ensure_center(rec))  # outside offset
            p["moves"] += _profile_moves_with_options(
                shp,
                setup,
                depth,
                t,
                onion_skin_mm,
                tabs_opts,
            )
            p["count"] += 1
    else:
        # Build edges and classify seams vs exterior
        edges: List[_Edge] = []
        rect_infos: List[Tuple[str, float, float, float, float]] = []
        for rec in rect_profiles:
            rid = rec.get("id") or f"rect@{len(rect_infos)}"
            cx, cy = _ensure_center(rec)
            w = float((rec.get("geometry") or {}).get("w_mm", 0.0))
            h = float((rec.get("geometry") or {}).get("h_mm", 0.0))
            rect_infos.append((rid, cx, cy, w, h))
            edges.extend(_rect_edges(cx, cy, w, h, rid))

        # Index by (orient, coord rounded)
        def _key(orient: str, coord: float) -> Tuple[str, int]:
            return orient, int(round(coord / MERGE_TOL_MM))

        buckets: Dict[Tuple[str,int], List[_Edge]] = {}
        for e in edges:
            buckets.setdefault(_key(e.orient, e.coord), []).append(e)

        t = _pick_for_profile(tool_db, kerf_mm=float(hints.get("kerf_width_mm", 0.0)))
        p = _get_or_make_pass("profile", t)
        setup: Setup = p["setup"]

        used_pairs: set[Tuple[str,str,float]] = set()
        # 1) seams = pairs in same bucket with sufficient overlap and different rects
        for k, lst in buckets.items():
            if len(lst) < 2: continue
            n = len(lst)
            for i in range(n):
                for j in range(i+1, n):
                    a, b = lst[i], lst[j]
                    if a.rect_id == b.rect_id: continue
                    if a.orient != b.orient: continue
                    if abs(a.coord - b.coord) > MERGE_TOL_MM: continue
                    overlap = _overlap_len(a.a, a.b, b.a, b.b)
                    if overlap < max(MIN_OVERLAP_MM, float(t.diameter)):
                        continue
                    # Emit on-center seam once
                    if a.orient == "v":
                        x = 0.5 * (a.coord + b.coord)
                        y0, y1 = max(min(a.a, a.b), min(b.a, b.b)), min(max(a.a, a.b), max(b.a, b.b))
                        shp = Shape2D([Vec2(x, y0), Vec2(x, y1)])
                    else:  # 'h'
                        y = 0.5 * (a.coord + b.coord)
                        x0, x1 = max(min(a.a, a.b), min(b.a, b.b)), min(max(a.a, a.b), max(b.a, b.b))
                        shp = Shape2D([Vec2(x0, y), Vec2(x1, y)])

                    depth = max(
                        float(next(rec for rec in rect_profiles if (rec.get("id") or "") == a.rect_id).get("depth_mm", 0.0)),
                        float(next(rec for rec in rect_profiles if (rec.get("id") or "") == b.rect_id).get("depth_mm", 0.0)),
                    )
                    depth += cut_through_mm
                    p["moves"] += profile_outline(shp, setup, depth=depth, step_down=_stepdown_for_tool(t))
                    p["count"] += 1
                    merged_seams_count += 1
                    used_pairs.add((a.rect_id, b.rect_id, a.coord))

        # 2) exterior edges = edges with no partner in tolerance
        tool_r = 0.5 * float(t.diameter)
        for e in edges:
            bucket = buckets.get(_key(e.orient, e.coord), [])
            if len([x for x in bucket if x.rect_id != e.rect_id and _overlap_len(x.a,x.b,e.a,e.b) >= MIN_OVERLAP_MM]) > 0:
                continue  # seam handled already
            # Exterior edge: offset outward by tool radius before cutting
            if e.orient == "v":
                x = e.coord
                x_off = x - tool_r if math.isclose(x, e.minx, abs_tol=MERGE_TOL_MM) else x + tool_r
                y0, y1 = e.a, e.b
                shp = Shape2D([Vec2(x_off, y0), Vec2(x_off, y1)])
            else:
                y = e.coord
                y_off = y - tool_r if math.isclose(y, e.miny, abs_tol=MERGE_TOL_MM) else y + tool_r
                x0, x1 = e.a, e.b
                shp = Shape2D([Vec2(x0, y_off), Vec2(x1, y_off)])

            depth = float(next(rec for rec in rect_profiles if (rec.get("id") or "") == e.rect_id).get("depth_mm", 0.0)) + cut_through_mm
            p["moves"] += profile_outline(shp, setup, depth=depth, step_down=_stepdown_for_tool(t))
            p["count"] += 1

    # ---------- Circle Profiles (NEW): single perimeter, not a pocket ----------
    circle_profiles = [rec for rec in hints.get("profiles", []) if str(rec.get("shape","")).lower() == "circle"]
    for rec in circle_profiles:
        geom = rec.get("geometry") or {}
        d = float(geom.get("diameter_mm", 0.0))
        cx, cy = _ensure_center(rec)
        side = str(rec.get("side", "on")).lower()  # 'inside' | 'outside' | 'on'
        t = _pick_for_profile(tool_db, kerf_mm=kerf_mm)
        p = _get_or_make_pass("profile", t)
        setup: Setup = p["setup"]
        tool_r = 0.5 * float(t.diameter)

        r = 0.5 * d
        if side == "outside":
            r += tool_r
        elif side == "inside":
            r -= tool_r
        if r <= 0.0:
            continue

        shp = circle_shape(Vec2(cx, cy), r)
        depth = max(0.0, float(rec.get("depth_mm", 0.0))) + cut_through_mm
        p["moves"] += _profile_moves_with_options(
            shp,
            setup,
            depth,
            t,
            onion_skin_mm,
            tabs_opts,
        )
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

    note = "Shared-edge merge is ON" if merge_shared_edges else "Shared-edge merge is OFF"
    job_summary = {
        "passes": summary_passes,
        "notes": note,
        "merged_seams": merged_seams_count,
    }
    if use_profile_options or cut_through_mm > 0.0:
        opts_summary: Dict[str, Any] = {}
        if onion_skin_mm > 0.0:
            opts_summary["onion_skin_mm"] = onion_skin_mm
        if tabs_enabled:
            opts_summary["tabs"] = {
                "count": int(tabs_opts.get("count", 0)),
                "height_mm": float(tabs_opts.get("height_mm", 3.0)),
            }
        if cut_through_mm > 0.0:
            opts_summary["cut_through_mm"] = cut_through_mm
        job_summary["profile_options"] = opts_summary
    return pass_list, job_summary
