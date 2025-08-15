from __future__ import annotations
from typing import Dict, List, Tuple
import numpy as np

__all__ = ["plan_rough"]

EPS = 1e-6

# ---- knobs ----
BRIDGE_GAP_MM = 2.0   # keep-down bridge gaps <= this (feed at band_top)
X_TOL_MM      = 1.0   # decimator: min X advance to keep a point
Z_TOL_MM      = 0.05  # decimator: keep if |ΔZ| >= this

def _scan_indices(n: int, step: int) -> List[int]:
    out = list(range(0, n, max(1, step)))
    if out[-1] != n - 1:
        out.append(n - 1)
    return out

def _spans(mask: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Return [(xs, xe, gs, ge), ...] per row.
    xs..xe inclusive is a 'material' span (mask True).
    gs..ge is the following gap (mask False), or (-1,-1) at end.
    """
    n = mask.size
    spans = []
    i = 0
    while i < n:
        while i < n and not mask[i]:
            i += 1
        if i >= n:
            break
        xs = i
        while i < n and mask[i]:
            i += 1
        xe = i - 1
        gs = i
        while i < n and not mask[i]:
            i += 1
        ge = i - 1 if gs < n else -1
        spans.append((xs, xe, gs if gs < n else -1, ge))
    return spans

def plan_rough(
    pass_name: str,
    band_top: np.ndarray,
    band_bot: np.ndarray,
    pixel_pitch_mm: float,
    stepover_mm: float,
    stepdown_mm: float,          # kept for API; not used for per-pixel slope limiting
    safe_z_mm: float,
    feed_mm_per_min: float,
    plunge_mm_per_min: float,
) -> List[Dict[str, float]]:
    """
    Roughing with:
      • Serpentine rows.
      • Single-sweep per span following band_bot (no per-pixel stepdown serrations).
      • Short gaps bridged keep-down at band_top (feed), not retract.
      • X/Z decimator to collapse redundant points.
    """
    assert band_top.shape == band_bot.shape, "band top/bot mismatch"
    H, W = band_top.shape
    step_px = max(1, int(round(stepover_mm / max(1e-9, pixel_pitch_mm))))
    bridge_gap_px = int(round(BRIDGE_GAP_MM / max(1e-9, pixel_pitch_mm)))

    rows = _scan_indices(H, step_px)
    moves: List[Dict[str, float]] = []

    for ri, y in enumerate(rows):
        row_mask = (band_top[y] - band_bot[y]) > EPS
        if not np.any(row_mask):
            continue

        spans = _spans(row_mask)
        forward = (ri % 2 == 0)
        yi_mm = y * pixel_pitch_mm

        # serpentine span order
        span_idxs = range(len(spans)) if forward else range(len(spans) - 1, -1, -1)
        for si in span_idxs:
            xs, xe, gs, ge = spans[si]
            if not forward:
                xs, xe = xe, xs  # traverse reversed

            # ---- enter span (retract then plunge) ----
            start_x = xs
            x0_mm = start_x * pixel_pitch_mm
            z0 = float(np.clip(band_bot[y, start_x], band_bot[y, start_x], band_top[y, start_x]))
            moves.append({"mode": 0, "x": x0_mm, "y": yi_mm, "z": safe_z_mm, "f": 0})
            moves.append({"mode": 1, "x": x0_mm, "y": yi_mm, "z": z0, "f": plunge_mm_per_min})

            # ---- cut span with decimation ----
            rng = range(xs, xe + (1 if xs <= xe else -1), 1 if xs <= xe else -1)
            last_x_mm = x0_mm
            last_z = z0
            for x in rng:
                x_mm = x * pixel_pitch_mm
                z_des = float(np.clip(band_bot[y, x], band_bot[y, x], band_top[y, x]))
                if (abs(x_mm - last_x_mm) < X_TOL_MM) and (abs(z_des - last_z) < Z_TOL_MM):
                    continue
                moves.append({"mode": 1, "x": x_mm, "y": yi_mm, "z": z_des, "f": feed_mm_per_min})
                last_x_mm, last_z = x_mm, z_des

            # ensure span end is emitted
            end_x = xe
            end_x_mm = end_x * pixel_pitch_mm
            end_z = float(np.clip(band_bot[y, end_x], band_bot[y, end_x], band_top[y, end_x]))
            if (abs(end_x_mm - last_x_mm) >= 1e-9) or (abs(end_z - last_z) >= 1e-9):
                moves.append({"mode": 1, "x": end_x_mm, "y": yi_mm, "z": end_z, "f": feed_mm_per_min})

            # ---- link to next span ----
            if gs != -1 and ge != -1:
                gap_len = ge - gs + 1
                if gap_len <= bridge_gap_px:
                    # single-segment keep-down bridge at band_top (feed)
                    br_start = end_x
                    br_end = ge if forward else gs
                    z_top_start = float(np.clip(band_top[y, br_start], band_bot[y, br_start], band_top[y, br_start]))
                    z_top_end   = float(np.clip(band_top[y, br_end],   band_bot[y, br_end],   band_top[y, br_end]))
                    # raise to local top if needed
                    if abs(z_top_start - last_z) > 1e-9:
                        moves.append({"mode": 1, "x": end_x_mm, "y": yi_mm, "z": z_top_start, "f": feed_mm_per_min})
                    moves.append({"mode": 1, "x": br_end * pixel_pitch_mm, "y": yi_mm, "z": z_top_end, "f": feed_mm_per_min})
                else:
                    # long gap: retract & rapid to the start of next span
                    next_x = gs if forward else ge
                    moves.append({"mode": 0, "x": next_x * pixel_pitch_mm, "y": yi_mm, "z": safe_z_mm, "f": 0})

        # end of row: retract
        last_end = spans[-1][1] if forward else spans[0][0]
        moves.append({"mode": 0, "x": last_end * pixel_pitch_mm, "y": yi_mm, "z": safe_z_mm, "f": 0})

    return moves
