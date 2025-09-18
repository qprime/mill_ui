from __future__ import annotations
from typing import Dict, List, Optional, Iterable, Tuple
import math
import numpy as np

from skills.cam_engine.kernels import compute_center_z_ball, scallop_to_stepover_mm
from skills.cam_engine.masks import rest_mask_ball


__all__ = ["plan_finish"]

# Replace the constants section at the top of strategy_raster_finish.py

VERTICAL_SERPENTINE = False  # set True for vertical
Z_SMOOTH_WINDOW_PX = 7        # much smaller window - was 31, now 7
Z_SMOOTH_PASSES = 1           # single pass - was 3, now 1  
X_TOL_MM = 0.06              # skip points closer than this in X if Z change is tiny
Z_TOL_MM = 0.20              # skip points if |ΔZ| < this (tuned for wood)

_Move = Dict[str, float]


# Much simpler smoothing - just light cleanup, not aggressive smoothing
def _light_smooth1d(v: np.ndarray, win: int) -> np.ndarray:
    """Very light smoothing to remove only the worst noise."""
    if win <= 1:
        return v.astype(np.float32, copy=False)
    win = int(win) | 1
    k = np.ones(win, dtype=np.float32) / float(win)
    pad = win // 2
    y = v.astype(np.float32, copy=True)
    y = np.convolve(np.pad(y, pad, mode="edge"), k, mode="valid")
    return y

# Replace the _emit_row_moves function with minimal smoothing

def _emit_row_moves(
    y: int,
    xs: int, xe: int, forward: bool,
    surface: np.ndarray, top: np.ndarray, bot: np.ndarray,
    pitch: float, safe_z: float, feed: float, plunge: float,
    x_tol: float, z_tol: float
) -> List[Dict[str, float]]:
    moves: List[Dict[str, float]] = []
    rng = range(xs, xe + 1) if forward else range(xe, xs - 1, -1)

    # Clamp surface to band and apply MINIMAL smoothing
    z_line = np.clip(surface[y, xs:xe + 1], bot[y, xs:xe + 1], top[y, xs:xe + 1]).astype(np.float32, copy=False)
    z_line = _light_smooth1d(z_line, Z_SMOOTH_WINDOW_PX)  # Just a tiny bit of smoothing

    # Map smoothed values back by x index
    xs_arr = np.arange(xs, xe + 1, dtype=int)
    z_at = dict(zip(xs_arr.tolist(), z_line.tolist()))

    # Start move
    start_x = xs if forward else xe
    y_mm = y * pitch
    x0_mm = start_x * pitch
    z0 = float(z_at[start_x])

    moves.append({"mode": 0, "x": x0_mm, "y": y_mm, "z": safe_z, "f": 0})
    moves.append({"mode": 1, "x": x0_mm, "y": y_mm, "z": z0, "f": plunge})

    last_x = x0_mm
    last_z = z0
    for x in rng:
        x_mm = x * pitch
        z = float(z_at[x])
        if abs(x_mm - last_x) < x_tol and abs(z - last_z) < z_tol:
            continue
        moves.append({"mode": 1, "x": x_mm, "y": y_mm, "z": z, "f": feed})
        last_x, last_z = x_mm, z

    # Retract
    end_x = xe if forward else xs
    moves.append({"mode": 0, "x": end_x * pitch, "y": y_mm, "z": safe_z, "f": 0})
    return moves


def raster_finish_moves_with_rest(heightmap_mm: np.ndarray,
                                  pixel_pitch_mm: float,
                                  bounds_mm: Tuple[float, float, float, float],
                                  tool_radius_mm: float,
                                  stepover_mm: float,
                                  angle_deg: float,
                                  feed_mm_min: float,
                                  rest_prev_tool_radius_mm: float | None = None,
                                  rest_tol_mm: float = 0.01) -> List[_Move]:
    """
    Raster finish using per-tool center-Z; if rest_prev_tool_radius_mm is given,
    only cut where the smaller tool can actually go deeper than the previous tool.
    """
    # 1) Per-tool center Z (guaranteed no-gouge)
    z_center = compute_center_z_ball(heightmap_mm, pixel_pitch_mm, tool_radius_mm)

    # 2) Optional rest mask (tool-aware)
    rest_mask: np.ndarray | None = None
    if rest_prev_tool_radius_mm is not None:
        rest_mask = rest_mask_ball(heightmap_mm, pixel_pitch_mm,
                                   prev_tool_radius_mm=rest_prev_tool_radius_mm,
                                   this_tool_radius_mm=tool_radius_mm,
                                   tol_mm=rest_tol_mm)

    # 3) Build scanlines
    xmin, xmax, ymin, ymax = bounds_mm
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)

    def to_scan(x, y):  return (c*x + s*y, -s*x + c*y)
    def to_world(u, v): return ( c*u - s*v,  s*u + c*v)

    corners = [to_scan(x, y) for x, y in [(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)]]
    u_vals, v_vals = zip(*corners)
    umin, umax = min(u_vals), max(u_vals)
    vmin, vmax = min(v_vals), max(v_vals)

    if stepover_mm <= 0:
        return []

    # 4) Emit moves; gate by rest_mask if present
    h, w = z_center.shape
    def px(x: float, y: float) -> tuple[int,int]:
        ix = int(round((x - xmin) / pixel_pitch_mm))
        iy = int(round((y - ymin) / pixel_pitch_mm))
        ix = min(max(ix, 0), w - 1)
        iy = min(max(iy, 0), h - 1)
        return ix, iy

    moves: List[_Move] = []
    v = vmin
    toggle = False
    while v <= vmax + 1e-6:
        (x0, y0) = to_world(umin, v)
        (x1, y1) = to_world(umax, v)
        if toggle:
            x0, y0, x1, y1 = x1, y1, x0, y0

        ix0, iy0 = px(x0, y0)
        ix1, iy1 = px(x1, y1)

        # If rest mask is enabled and neither endpoint is in-mask, skip this swath fast.
        if rest_mask is not None and not (rest_mask[iy0, ix0] or rest_mask[iy1, ix1]):
            v += stepover_mm
            toggle = not toggle
            continue

        z0 = float(z_center[iy0, ix0]); z1 = float(z_center[iy1, ix1])

        if rest_mask is not None:
            # Walk across and punch small gaps (cheap & robust)
            steps = max(2, int(round(abs((umax - umin)) / pixel_pitch_mm)))
            for i in range(steps + 1):
                t = i / steps
                x = x0 + (x1 - x0) * t
                y = y0 + (y1 - y0) * t
                ix, iy = px(x, y)
                if rest_mask[iy, ix]:
                    z = float(z_center[iy, ix])
                    moves.append({"mode": 1, "x": x, "y": y, "z": z, "f": feed_mm_min})
        else:
            moves.append({"mode": 1, "x": x0, "y": y0, "z": z0, "f": feed_mm_min})
            moves.append({"mode": 1, "x": x1, "y": y1, "z": z1, "f": feed_mm_min})

        v += stepover_mm
        toggle = not toggle

    return moves

def _scan_indices(n: int, step: int) -> List[int]:
    out = list(range(0, n, max(1, step)))
    if out[-1] != n - 1:
        out.append(n - 1)
    return out



def _smooth1d(v: np.ndarray, win: int, passes: int) -> np.ndarray:
    """Improved 1D smoothing with edge preservation."""
    if win <= 1 or passes <= 0:
        return v
    win = int(win) | 1
    y = v.astype(np.float32, copy=True)
    
    # First apply standard smoothing
    k = np.ones(win, dtype=np.float32) / float(win)
    pad = win // 2
    for _ in range(passes):
        y = np.convolve(np.pad(y, pad, mode="edge"), k, mode="valid")
    
    return y

def plan_finish(
    pass_name: str,
    surface_mm: np.ndarray,      # final S(x,y)
    band_top: np.ndarray,        # stock plane
    band_bot: np.ndarray,        # S(x,y)
    pixel_pitch_mm: float,
    stepover_mm: float,
    safe_z_mm: float,
    feed_mm_per_min: float,
    plunge_mm_per_min: float,
) -> List[Dict[str, float]]:
    """
    Independent serpentine finish with along-path smoothing + decimation.
    """
    assert band_top.shape == band_bot.shape == surface_mm.shape, "shape mismatch"
    H, W = surface_mm.shape
    step_px = max(1, int(round(stepover_mm / max(1e-9, pixel_pitch_mm))))
    moves: List[Dict[str, float]] = []

    if VERTICAL_SERPENTINE:
        cols = _scan_indices(W, step_px)
        for ci, x in enumerate(cols):
            mask = (band_top[:, x] - band_bot[:, x]) > 1e-6
            if not np.any(mask): 
                continue
            ys = int(np.argmax(mask))
            ye = H - 1 - int(np.argmax(mask[::-1]))
            forward = (ci % 2 == 0)
            rng = range(ys, ye + 1) if forward else range(ye, ys - 1, -1)

            # extract and smooth column
            z_col = np.clip(surface_mm[ys:ye + 1, x], band_bot[ys:ye + 1, x], band_top[ys:ye + 1, x]).astype(np.float32, copy=False)
            z_col = _smooth1d(z_col, Z_SMOOTH_WINDOW_PX, Z_SMOOTH_PASSES)
            ys_arr = np.arange(ys, ye + 1, dtype=int)
            z_at = dict(zip(ys_arr.tolist(), z_col.tolist()))

            start_y = ys if forward else ye
            x_mm = x * pixel_pitch_mm
            y0_mm = start_y * pixel_pitch_mm
            z0 = float(z_at[start_y])

            moves.append({"mode": 0, "x": x_mm, "y": y0_mm, "z": safe_z_mm, "f": 0})
            moves.append({"mode": 1, "x": x_mm, "y": y0_mm, "z": z0, "f": plunge_mm_per_min})

            last_y = y0_mm
            last_z = z0
            for y in rng:
                y_mm = y * pixel_pitch_mm
                z = float(z_at[y])
                if abs(y_mm - last_y) < X_TOL_MM and abs(z - last_z) < Z_TOL_MM:
                    continue
                moves.append({"mode": 1, "x": x_mm, "y": y_mm, "z": z, "f": feed_mm_per_min})
                last_y, last_z = y_mm, z

            end_y = ye if forward else ys
            moves.append({"mode": 0, "x": x_mm, "y": end_y * pixel_pitch_mm, "z": safe_z_mm, "f": 0})
    else:
        rows = _scan_indices(H, step_px)
        for ri, y in enumerate(rows):
            mask = (band_top[y] - band_bot[y]) > 1e-6
            if not np.any(mask): 
                continue
            xs = int(np.argmax(mask))
            xe = W - 1 - int(np.argmax(mask[::-1]))
            forward = (ri % 2 == 0)
            moves.extend(_emit_row_moves(
                y, xs, xe, forward,
                surface_mm, band_top, band_bot,
                pixel_pitch_mm, safe_z_mm, feed_mm_per_min, plunge_mm_per_min,
                X_TOL_MM, Z_TOL_MM
            ))
    return moves



def _raster_scanlines(bounds_mm: Tuple[float, float, float, float],
                      pitch_mm: float,
                      stepover_mm: float,
                      angle_deg: float) -> List[List[Tuple[float, float]]]:
    """Generate XY scanlines (list of polylines) inside [xmin,xmax]x[ymin,ymax] at given angle and stepover."""
    xmin, xmax, ymin, ymax = bounds_mm
    # rotate the bounding box into scan space
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)
    def to_scan(x, y):  return (c*x + s*y, -s*x + c*y)
    def to_world(u, v): return ( c*u - s*v,  s*u + c*v)

    # Find extents in scan space
    corners = [to_scan(x, y) for x, y in [(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)]]
    u_vals, v_vals = zip(*corners)
    umin, umax = min(u_vals), max(u_vals)
    vmin, vmax = min(v_vals), max(v_vals)

    if stepover_mm <= 0:
        return []

    lines: List[List[Tuple[float,float]]] = []
    v = vmin
    toggle = False
    while v <= vmax + 1e-6:
        # two points define the line across u-span; clip to world bbox afterward
        p0 = to_world(umin, v)
        p1 = to_world(umax, v)
        if toggle:
            p0, p1 = p1, p0
        lines.append([p0, p1])
        v += stepover_mm
        toggle = not toggle
    return lines

def raster_finish_moves(heightmap_mm: np.ndarray,
                        pixel_pitch_mm: float,
                        bounds_mm: Tuple[float, float, float, float],
                        tool_radius_mm: float,
                        scallop_mm: float,
                        angle_deg: float,
                        feed_mm_min: float) -> List[_Move]:
    """Generate G1 moves for a raster finish using a tool-center Z map (no-gouge by construction)."""
    # 1) tool-center surface from heightmap
    z_center = compute_center_z_ball(heightmap_mm, pixel_pitch_mm, tool_radius_mm)

    # 2) stepover from scallop
    stepover_mm = scallop_to_stepover_mm(tool_radius_mm, scallop_mm)
    if stepover_mm <= 0:
        stepover_mm = max(pixel_pitch_mm, tool_radius_mm * 0.25)  # conservative fallback

    # 3) scanline XYs
    scanlines = _raster_scanlines(bounds_mm, pixel_pitch_mm, stepover_mm, angle_deg)
    if not scanlines:
        return []

    # 4) sample z_center at each XY and emit moves
    xmin, xmax, ymin, ymax = bounds_mm
    h, w = z_center.shape
    moves: List[_Move] = []
    # simple mm->px mapping
    def world_to_px(x: float, y: float) -> Tuple[int, int]:
        ix = int(round((x - xmin) / pixel_pitch_mm))
        iy = int(round((y - ymin) / pixel_pitch_mm))
        # clamp
        if ix < 0: ix = 0
        if iy < 0: iy = 0
        if ix >= w: ix = w - 1
        if iy >= h: iy = h - 1
        return ix, iy

    for line in scanlines:
        x0, y0 = line[0]
        ix, iy = world_to_px(x0, y0)
        z0 = float(z_center[iy, ix])
        moves.append({"mode": 1, "x": x0, "y": y0, "z": z0, "f": feed_mm_min})
        x1, y1 = line[1]
        ix, iy = world_to_px(x1, y1)
        z1 = float(z_center[iy, ix])
        moves.append({"mode": 1, "x": x1, "y": y1, "z": z1, "f": feed_mm_min})

    return moves

# --- paste into strategy_raster_finish.py (or linking.py) ---

def compute_link_z_mm(heightmap_mm: np.ndarray,
                      pixel_pitch_mm: float,
                      bounds_mm: Tuple[float, float, float, float],
                      x0: float, y0: float, x1: float, y1: float,
                      margin_mm: float) -> float:
    """Sample the heightfield along the XY link and return a safe local link-Z."""
    xmin, xmax, ymin, ymax = bounds_mm
    h, w = heightmap_mm.shape
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        ix = int(round((x0 - xmin) / pixel_pitch_mm))
        iy = int(round((y0 - ymin) / pixel_pitch_mm))
        ix = min(max(ix, 0), w - 1)
        iy = min(max(iy, 0), h - 1)
        return float(heightmap_mm[iy, ix]) + margin_mm

    # sample every ~1 pixel along the link
    steps = max(2, int(math.ceil(length / pixel_pitch_mm)))
    zmax = -1e9
    for i in range(steps + 1):
        t = i / steps
        x = x0 + t * dx
        y = y0 + t * dy
        ix = int(round((x - xmin) / pixel_pitch_mm))
        iy = int(round((y - ymin) / pixel_pitch_mm))
        if ix < 0 or iy < 0 or ix >= w or iy >= h:
            continue
        z = float(heightmap_mm[iy, ix])
        if z > zmax:
            zmax = z
    return (zmax if zmax > -1e8 else 0.0) + margin_mm
