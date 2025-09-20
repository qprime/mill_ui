from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cadquery as cq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cq = None  # type: ignore


@dataclass(frozen=True)
class _WireInfo:
    kind: str  # "rect" | "circle" | "other"
    center: Tuple[float, float]
    dims: Tuple[float, float]  # (w,h) for rect; (d,0) for circle


def _scale_val(v: float, units: str) -> float:
    if units == "inch":
        return v * 25.4
    return v


def _bounding_box(shape) -> Any:
    try:
        return shape.BoundingBox()
    except Exception:
        try:
            return shape.val().BoundingBox()
        except Exception:
            try:
                return cq.Workplane("XY").add(shape).val().BoundingBox()  # type: ignore[attr-defined]
            except Exception:
                class _BB:  # pragma: no cover - extreme fallback
                    xmin = ymin = xmax = ymax = xlen = ylen = 0.0
                return _BB()


def _edges_of(obj) -> List[Any]:
    try:
        return list(cq.Workplane("XY").add(obj).edges().vals())  # type: ignore[attr-defined]
    except Exception:
        try:
            sel = obj.edges()
            try:
                return list(sel.vals())
            except Exception:
                return list(sel)
        except Exception:
            return []


def _vertices_of(obj) -> List[Any]:
    try:
        return list(cq.Workplane("XY").add(obj).vertices().vals())  # type: ignore[attr-defined]
    except Exception:
        try:
            sel = obj.Vertices()
            try:
                return list(sel.vals())
            except Exception:
                return list(sel)
        except Exception:
            return []


def _wire_kind_info(wire) -> _WireInfo:
    bb = _bounding_box(wire)
    cx = 0.5 * (bb.xmin + bb.xmax)
    cy = 0.5 * (bb.ymin + bb.ymax)
    edges = _edges_of(wire)
    if len(edges) == 1:
        try:
            gt = str(edges[0].geomType()).lower()
        except Exception:
            gt = ""
        if gt == "circle":
            d = bb.xlen if bb.xlen >= bb.ylen else bb.ylen
            return _WireInfo("circle", (cx, cy), (float(d), 0.0))
    if len(edges) == 4:
        # axis-aligned rectangle if there are only lines and two Xs/two Ys
        try:
            gts = {str(e.geomType()).lower() for e in edges}
        except Exception:
            gts = set()
        if gts == {"line"}:
            # check axis alignment by unique x/y of vertices
            pts = []
            for e in edges:
                for p in _vertices_of(e):
                    try:
                        pts.append((float(p.X), float(p.Y)))
                    except Exception:
                        pass
            xs = sorted({round(p[0], 4) for p in pts})
            ys = sorted({round(p[1], 4) for p in pts})
            if len(xs) == 2 and len(ys) == 2:
                return _WireInfo("rect", (cx, cy), (float(bb.xlen), float(bb.ylen)))
    return _WireInfo("other", (cx, cy), (0.0, 0.0))


def _edge_sample_points(edge, *, segments: int = 16, deflection_mm: float = 0.2) -> List[Tuple[float, float]]:
    """Return a list of (x,y) points along an edge. Fallback to endpoints.

    Tries OCP (CadQuery backend) BRepAdaptor to evaluate points uniformly in
    parameter space; if unavailable, uses the edge's vertices.
    """
    pts: List[Tuple[float, float]] = []
    # Try OCP (CadQuery modern backend) — prefer adaptive deflection sampling
    adp = None
    try:  # OCP backend
        from OCP.BRepAdaptor import BRepAdaptor_Curve  # type: ignore
        from OCP.GCPnts import GCPnts_QuasiUniformDeflection  # type: ignore
        adp = BRepAdaptor_Curve(edge)
        u0 = float(adp.FirstParameter()); u1 = float(adp.LastParameter())
        approx = GCPnts_QuasiUniformDeflection(adp, float(deflection_mm), u0, u1)
        nb = int(getattr(approx, "NbPoints", lambda: 0)())
        if nb >= 2:
            for i in range(1, nb + 1):
                u = float(approx.Parameter(i))
                p = adp.Value(u)
                pts.append((float(p.X()), float(p.Y())))
            return pts
        # Fallback to uniform parameter sampling if adaptive failed
        n = max(32, int(segments))
        for k in range(n + 1):
            u = u0 + (u1 - u0) * (k / n)
            p = adp.Value(u)
            pts.append((float(p.X()), float(p.Y())))
        return pts
    except Exception:
        pass

    try:  # OCC legacy backend
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve  # type: ignore
        from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection  # type: ignore
        adp = BRepAdaptor_Curve(edge)
        u0 = float(adp.FirstParameter()); u1 = float(adp.LastParameter())
        approx = GCPnts_QuasiUniformDeflection(adp, float(deflection_mm), u0, u1)
        nb = int(getattr(approx, "NbPoints", lambda: 0)())
        if nb >= 2:
            for i in range(1, nb + 1):
                u = float(approx.Parameter(i))
                p = adp.Value(u)
                pts.append((float(p.X()), float(p.Y())))
            return pts
        # Fallback to uniform parameter sampling
        n = max(32, int(segments))
        for k in range(n + 1):
            u = u0 + (u1 - u0) * (k / n)
            p = adp.Value(u)
            pts.append((float(p.X()), float(p.Y())))
        return pts
    except Exception:
        pass

    # Fallback: endpoints from vertices
    verts = _vertices_of(edge)
    if verts:
        try:
            pts = [(float(verts[0].X), float(verts[0].Y))]
            if len(verts) > 1:
                pts.append((float(verts[-1].X), float(verts[-1].Y)))
            return pts
        except Exception:
            pass
    return []


def _wire_polyline_points(wire, *, segments_per_curve: int = 24, deflection_mm: float = 0.2) -> List[Tuple[float, float]]:
    """Flatten a wire into an ordered, closed polyline approximating its XY boundary.

    - Samples each edge (adaptive deflection where available).
    - Orders edge polylines by endpoint connectivity so the path doesn't jump.
    - Deduplicates adjacent points and closes the loop if needed.
    """
    tol = 1e-6
    edges = _edges_of(wire)
    if not edges:
        return []

    # 1) Sample each edge to a small polyline
    parts: List[Dict[str, Any]] = []
    for e in edges:
        segs = 2
        try:
            gt = str(getattr(e, "geomType")()).lower()
        except Exception:
            gt = ""
        if gt not in ("", "line"):
            segs = max(32, int(segments_per_curve))
        pts = _edge_sample_points(e, segments=segs, deflection_mm=deflection_mm)
        # ensure at least endpoints
        if len(pts) < 2:
            vs = _vertices_of(e)
            if len(vs) >= 2:
                try:
                    pts = [(float(vs[0].X), float(vs[0].Y)), (float(vs[-1].X), float(vs[-1].Y))]
                except Exception:
                    continue
        # prune adjacent duplicates
        cleaned: List[Tuple[float, float]] = []
        for p in pts:
            if not cleaned or (abs(cleaned[-1][0] - p[0]) > tol or abs(cleaned[-1][1] - p[1]) > tol):
                cleaned.append(p)
        if len(cleaned) >= 2:
            parts.append({
                "start": cleaned[0],
                "end": cleaned[-1],
                "pts": cleaned,
            })

    if not parts:
        return []

    # 2) Order parts by chaining endpoints (reverse parts as needed)
    def _dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        dx = a[0] - b[0]; dy = a[1] - b[1]
        return dx*dx + dy*dy

    used = [False] * len(parts)
    # start from the piece with the smallest (x,y) to be stable
    start_idx = min(range(len(parts)), key=lambda i: (parts[i]["start"][0], parts[i]["start"][1]))
    path: List[Tuple[float, float]] = list(parts[start_idx]["pts"])  # copy
    used[start_idx] = True
    last = path[-1]

    for _ in range(len(parts) - 1):
        best = None
        best_idx = -1
        best_rev = False
        best_d = float("inf")
        for j, pr in enumerate(parts):
            if used[j]:
                continue
            d_start = _dist2(last, pr["start"])  # try in forward order
            if d_start < best_d:
                best = pr; best_idx = j; best_rev = False; best_d = d_start
            d_end = _dist2(last, pr["end"])  # or reversed
            if d_end < best_d:
                best = pr; best_idx = j; best_rev = True; best_d = d_end
        if best is None:
            break
        seg = best["pts"]
        if best_rev:
            seg = list(reversed(seg))
        # append without duplicating the join point
        for p in seg:
            if abs(path[-1][0] - p[0]) > tol or abs(path[-1][1] - p[1]) > tol:
                path.append(p)
        used[best_idx] = True
        last = path[-1]

    # 3) Close the path if needed
    if path and (abs(path[0][0] - path[-1][0]) > tol or abs(path[0][1] - path[-1][1]) > tol):
        path.append(path[0])

    return path


def _collect_solids(shape_or_wp) -> List[Any]:
    if cq is None:  # pragma: no cover
        return []
    try:
        if isinstance(shape_or_wp, cq.Workplane):
            return list(shape_or_wp.solids().vals())
    except Exception:
        pass
    try:
        return list(cq.Workplane("XY").add(shape_or_wp).solids().vals())
    except Exception:
        return []


def _faces_xy_oriented(solid) -> List[Any]:
    """Return faces of a solid that lie approximately in the XY plane (small Z extent).

    Heuristic: face bounding box z-length close to 0 compared to the solid's z-span.
    """
    try:
        bb_s = solid.BoundingBox()
        z_span = float(getattr(bb_s, "zlen", 0.0) or 0.0)
    except Exception:
        z_span = 0.0
    tol_z = max(1e-4, 1e-3 * max(1.0, z_span))  # ~0.001 * thickness or >= 1e-4 mm
    faces: List[Any] = []
    try:
        all_faces = list(cq.Workplane("XY").add(solid).faces().vals())  # type: ignore[attr-defined]
    except Exception:
        all_faces = []
    for f in all_faces:
        try:
            bbf = f.BoundingBox()
            if float(getattr(bbf, "zlen", 0.0) or 0.0) <= tol_z:
                faces.append(f)
        except Exception:
            continue
    return faces


def infer_layout_from_step(
    step_path: Path,
    *,
    units: str = "mm",
    margin_mm: float = 5.0,
    sheet_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    if cq is None:  # pragma: no cover
        raise ImportError("cadquery is required for STEP import")

    try:
        shape_or_wp = cq.importers.importStep(str(step_path))  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to read STEP: {exc}")

    solids = _collect_solids(shape_or_wp)
    if not solids:
        raise RuntimeError("No solids found in STEP")

    # Global XY bounds
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")
    thicknesses: List[float] = []

    items: List[Dict[str, Any]] = []

    for idx, s in enumerate(solids):
        bb = s.BoundingBox()
        xmin = min(xmin, float(bb.xmin))
        ymin = min(ymin, float(bb.ymin))
        xmax = max(xmax, float(bb.xmax))
        ymax = max(ymax, float(bb.ymax))
        thicknesses.append(float(bb.zlen))

        # Prefer faces that are XY oriented based on Z thickness of their bounding box
        xy_faces = _faces_xy_oriented(s)
        if not xy_faces:
            # Fallback to faces with positive Z normal if detection failed
            try:
                xy_faces = list(cq.Workplane("XY").add(s).faces(">Z").vals())  # type: ignore[attr-defined]
            except Exception:
                xy_faces = []
        if not xy_faces:
            continue
        # Largest face by area among XY candidates
        def _f_area(ff):
            try:
                return ff.Area()
            except Exception:
                return getattr(ff, 'Area', lambda: 0.0)()
        face = max(xy_faces, key=_f_area)
        try:
            wires = face.wires().vals()
        except Exception:
            try:
                wires = list(cq.Workplane("XY").add(face).wires().vals())  # type: ignore[attr-defined]
            except Exception:
                wires = []
        if not wires:
            continue
        # Outer most wire by projected XY area (use bbox area as proxy)
        def _area(w):
            b = w.BoundingBox()
            return float(b.xlen) * float(b.ylen)

        outer = max(wires, key=_area)
        winfo = _wire_kind_info(outer)
        if winfo.kind == "rect":
            w, h = winfo.dims
            cx, cy = winfo.center
            items.append({
                "id": f"solid{idx+1}:outer",
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": _scale_val(w, units), "h_mm": _scale_val(h, units)},
                "feature": {"type": "profile", "depth": "through"},
                "placement": {"center_xy_mm": (_scale_val(cx, units), _scale_val(cy, units))},
            })
        elif winfo.kind == "circle":
            d, _ = winfo.dims
            cx, cy = winfo.center
            items.append({
                "id": f"solid{idx+1}:outer",
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": _scale_val(d, units)},
                "feature": {"type": "profile", "depth": "through"},
                "placement": {"center_xy_mm": (_scale_val(cx, units), _scale_val(cy, units))},
                "side": "outside",
            })
        else:
            # Generic outline: polyline profile sampled from wire (adaptive deflection)
            pts_abs = _wire_polyline_points(outer, segments_per_curve=64, deflection_mm=0.15)
            if pts_abs:
                # Center at wire bbox center and store points relative to that
                bb = _bounding_box(outer)
                cx, cy = 0.5 * (bb.xmin + bb.xmax), 0.5 * (bb.ymin + bb.ymax)
                pts_rel = [(_scale_val(px - cx, units), _scale_val(py - cy, units)) for (px, py) in pts_abs]
                items.append({
                    "id": f"solid{idx+1}:outer",
                    "kind": "shape",
                    "type": "Polyline",
                    "geometry": {"points": pts_rel, "closed": True},
                    "feature": {"type": "profile", "depth": "through"},
                    "placement": {"center_xy_mm": (_scale_val(cx, units), _scale_val(cy, units))},
                    "side": "on",
                })

        # Detect circular holes from inner wires on the top face
        for w in wires:
            if w == outer:
                continue
            info = _wire_kind_info(w)
            if info.kind != "circle":
                continue
            d, _ = info.dims
            cx, cy = info.center
            items.append({
                "id": f"solid{idx+1}:hole@{len(items)}",
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": _scale_val(d, units)},
                "feature": {"type": "hole", "depth_mm": _scale_val(float(bb.zlen), units)},
                "placement": {"center_xy_mm": (_scale_val(cx, units), _scale_val(cy, units))},
            })

    if xmin == float("inf"):
        raise RuntimeError("Failed to determine XY bounds from STEP")

    # Compute stock from bounds + margin unless overridden
    w_mm = _scale_val(xmax - xmin, units)
    h_mm = _scale_val(ymax - ymin, units)
    t_mm = _scale_val(sorted(thicknesses)[len(thicknesses)//2], units) if thicknesses else 0.0

    if sheet_overrides:
        w_mm = float(sheet_overrides.get("width_mm", w_mm))
        h_mm = float(sheet_overrides.get("height_mm", h_mm))
        t_mm = float(sheet_overrides.get("thickness_mm", t_mm))

    w_mm += 2.0 * float(margin_mm)
    h_mm += 2.0 * float(margin_mm)

    # Center shift so all placements are relative to stock center
    cx0 = _scale_val(0.5 * (xmax + xmin), units)
    cy0 = _scale_val(0.5 * (ymax + ymin), units)
    for it in items:
        plc = it.setdefault("placement", {})
        v = plc.get("center_xy_mm")
        if isinstance(v, (tuple, list)) and len(v) == 2:
            plc["center_xy_mm"] = (float(v[0]) - cx0, float(v[1]) - cy0)

    layout: Dict[str, Any] = {
        "sheet": {"width_mm": w_mm, "height_mm": h_mm, "thickness_mm": t_mm},
        "items": items,
    }
    return layout
