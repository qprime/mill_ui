from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import ezdxf  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ezdxf = None  # type: ignore


def _scale_val(v: float, units: str) -> float:
    if units == "inch":
        return v * 25.4
    return v


def _area_of_poly(points: List[Tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    # Shoelace area (closed path; ignore duplicate last point)
    s = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def _bbox(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _sample_arc_bulge(p0: Tuple[float, float], p1: Tuple[float, float], bulge: float,
                      *, chord_segments_min: int = 8) -> List[Tuple[float, float]]:
    # bulge = tan(theta/4), theta signed (CCW positive)
    import math
    x0, y0 = p0; x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    c = math.hypot(dx, dy)
    if c == 0.0 or abs(bulge) < 1e-12:
        return [p0, p1]
    theta = 4.0 * math.atan(bulge)
    # radius and center offset
    r = c / (2.0 * math.sin(theta / 2.0)) if abs(math.sin(theta/2.0)) > 1e-12 else 1e9
    mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    ux, uy = dx / c, dy / c
    nx, ny = -uy, ux
    h = r * (1.0 - math.cos(theta / 2.0))
    cx, cy = (mx + (nx * h if bulge > 0 else -nx * h),
              my + (ny * h if bulge > 0 else -ny * h))
    # start and end angles
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = a0 + theta
    # choose segments: ~10 deg per segment, min
    n = max(chord_segments_min, int(abs(theta) / (math.pi / 18.0)))
    pts: List[Tuple[float, float]] = []
    for i in range(n + 1):
        t = a0 + (theta * i / n)
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def _polyline_points_from_lwpolyline(e) -> Optional[List[Tuple[float, float]]]:
    # Expect ezdxf entity LWPOLYLINE; handle bulge arcs
    try:
        data = list(e.get_points("xyb"))  # (x, y, bulge)
    except Exception:
        return None
    if len(data) < 2:
        return None
    closed = bool(getattr(e, "closed", False))
    pts: List[Tuple[float, float]] = []
    for i in range(len(data) - (0 if closed else 1)):
        x0, y0, b0 = data[i][0], data[i][1], (data[i][2] if len(data[i]) > 2 else 0.0)
        x1, y1, _ = data[(i + 1) % len(data)][0], data[(i + 1) % len(data)][1], 0.0
        if abs(b0) > 1e-12:
            seg = _sample_arc_bulge((x0, y0), (x1, y1), b0)
            if pts and seg:
                seg = seg[1:]  # avoid duplicate join
            pts.extend(seg)
        else:
            if not pts:
                pts.append((x0, y0))
            pts.append((x1, y1))
    # Close if necessary
    if pts and (abs(pts[0][0] - pts[-1][0]) > 1e-9 or abs(pts[0][1] - pts[-1][1]) > 1e-9):
        pts.append(pts[0])
    return pts


def infer_layout_from_dxf(
    dxf_path: Path,
    *,
    units: str = "mm",
    margin_mm: float = 5.0,
    sheet_overrides: Optional[Dict[str, float]] = None,
    default_thickness_mm: float = 18.0,
) -> Dict[str, Any]:
    if ezdxf is None:  # pragma: no cover
        raise ImportError("ezdxf is required for DXF import")

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    polylines: List[List[Tuple[float, float]]] = []

    # Prefer LWPOLYLINE with bulge arcs; ignore open ones
    for e in msp.query("LWPOLYLINE"):
        try:
            if not e.closed:
                continue
        except Exception:
            continue
        pts = _polyline_points_from_lwpolyline(e)
        if pts and len(pts) >= 4:
            polylines.append(pts)

    # Fallback: try SPLINE approximations
    if not polylines:
        for e in msp.query("SPLINE"):
            try:
                pts = list(e.approximate(200))  # returns tuples of (x,y[,z])
                pts2 = [(float(p[0]), float(p[1])) for p in pts]
                if len(pts2) >= 4:
                    if (abs(pts2[0][0] - pts2[-1][0]) > 1e-9 or abs(pts2[0][1] - pts2[-1][1]) > 1e-9):
                        pts2.append(pts2[0])
                    polylines.append(pts2)
            except Exception:
                continue

    if not polylines:
        raise RuntimeError("No closed polylines found in DXF")

    # Choose the largest area closed loop as the outer profile
    pl = max(polylines, key=lambda p: abs(_area_of_poly(p[:-1] if p[0] == p[-1] else p)))

    # Compute extents for sheet
    minx, miny, maxx, maxy = _bbox(pl)
    w_mm = _scale_val(maxx - minx, units) + 2.0 * margin_mm
    h_mm = _scale_val(maxy - miny, units) + 2.0 * margin_mm
    t_mm = default_thickness_mm

    if sheet_overrides:
        w_mm = float(sheet_overrides.get("width_mm", w_mm))
        h_mm = float(sheet_overrides.get("height_mm", h_mm))
        t_mm = float(sheet_overrides.get("thickness_mm", t_mm))

    # Center of bbox as placement
    cx = (minx + maxx) * 0.5
    cy = (miny + maxy) * 0.5
    pts_rel = [(_scale_val(x - cx, units), _scale_val(y - cy, units)) for (x, y) in pl]

    items = [{
        "id": "dxf:outline",
        "kind": "shape",
        "type": "Polyline",
        "geometry": {"points": pts_rel, "closed": True},
        "feature": {"type": "profile", "depth": "through"},
        "placement": {"center_xy_mm": (_scale_val(cx, units), _scale_val(cy, units))},
    }]

    layout: Dict[str, Any] = {
        "sheet": {"width_mm": w_mm, "height_mm": h_mm, "thickness_mm": t_mm},
        "items": items,
    }
    return layout

