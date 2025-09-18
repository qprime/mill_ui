from __future__ import annotations
from typing import Dict, Any, Tuple
import numpy as np
from collections import deque
from .envelopes import compute_envelope

__all__ = ["make_bands"]

EPS = 1e-6

def _max_filter1d_same(v: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return v.astype(np.float32, copy=False)
    k = int(k) | 1
    pad = k // 2
    vv = np.pad(v.astype(np.float32, copy=False), (pad, pad), mode="edge")
    out = np.empty(v.shape[0], dtype=np.float32)
    q: deque[int] = deque()
    for i in range(vv.shape[0]):
        while q and vv[q[-1]] <= vv[i]:
            q.pop()
        q.append(i)
        left = i - k + 1
        if q[0] < left:
            q.popleft()
        if i >= k - 1:
            out[i - (k - 1)] = vv[q[0]]
    return out

def _min_filter1d_same(v: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return v.astype(np.float32, copy=False)
    k = int(k) | 1
    pad = k // 2
    vv = np.pad(v.astype(np.float32, copy=False), (pad, pad), mode="edge")
    out = np.empty(v.shape[0], dtype=np.float32)
    q: deque[int] = deque()
    for i in range(vv.shape[0]):
        while q and vv[q[-1]] >= vv[i]:
            q.pop()
        q.append(i)
        left = i - k + 1
        if q[0] < left:
            q.popleft()
        if i >= k - 1:
            out[i - (k - 1)] = vv[q[0]]
    return out

def _dilate2d(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a.astype(np.float32, copy=False)
    a = a.astype(np.float32, copy=False)
    H, W = a.shape
    tmp = np.empty_like(a, dtype=np.float32)
    out = np.empty_like(a, dtype=np.float32)
    for y in range(H):
        tmp[y, :] = _max_filter1d_same(a[y, :], k)
    for x in range(W):
        out[:, x] = _max_filter1d_same(tmp[:, x], k)
    return out

def _erode2d(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a.astype(np.float32, copy=False)
    a = a.astype(np.float32, copy=False)
    H, W = a.shape
    tmp = np.empty_like(a, dtype=np.float32)
    out = np.empty_like(a, dtype=np.float32)
    for y in range(H):
        tmp[y, :] = _min_filter1d_same(a[y, :], k)
    for x in range(W):
        out[:, x] = _min_filter1d_same(tmp[:, x], k)
    return out

def _gray_close(a: np.ndarray, k: int) -> np.ndarray:
    # closing = dilation then erosion (square SE of size k), same-sized output
    return _erode2d(_dilate2d(a, k), k)

def _tool_key(t: Dict[str, Any]) -> Tuple[str, float, float]:
    return (str(t.get("type") or "").lower(),
            float(t.get("diameter_mm") or 0.0),
            float(t.get("angle_deg") or 0.0))

def _order_tools_fine_to_coarse(passes: list) -> list:
    seen = {}
    for p in passes:
        tk = _tool_key(p["tool"])
        if tk not in seen:
            seen[tk] = dict(p["tool"])
    tools = list(seen.values())
    tools.sort(key=lambda t: (float(t.get("diameter_mm") or 0.0), str(t.get("type"))))
    return tools  # ascending diameter: fine -> coarse

def make_bands(surface_mm: np.ndarray,
               stock_top_z_mm: float,
               pixel_pitch_mm: float,
               cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heavy-cloth barriers (fine→coarse) + per-pass bands:
      N1 = S + delta
      Ni = max( close(N_{i-1}, k_i), envelope_i(S), S + delta, N_{i-1} )
    Rough pass i uses bot=Ni; finish uses bot=S (independent).
    """
    S = surface_mm.astype(np.float32, copy=False)
    Zs = float(stock_top_z_mm)
    passes = list(cfg["passes"])
    tools_f2c = _order_tools_fine_to_coarse(passes)
    delta = float(cfg.get("finish", {}).get("skin_mm", 0.3))

    barriers: Dict[Tuple[str, float, float], np.ndarray] = {}
    N_prev = S + delta

    for t in tools_f2c:
        tk = _tool_key(t)
        r_px = max(1, int(round(0.8 * 0.5 * float(t.get("diameter_mm") or 0.0) / max(1e-9, pixel_pitch_mm))))
        k = (2 * r_px + 1)
        C = _gray_close(N_prev, k)
        E = compute_envelope(S, t, pixel_pitch_mm)
        N = np.maximum.reduce([N_prev, C, E, S + delta]).astype(np.float32, copy=False)
        barriers[tk] = N
        N_prev = N  # blankets are non-decreasing

    pass_bands: Dict[str, Dict[str, np.ndarray]] = {}
    current_top = np.full_like(S, Zs, dtype=np.float32)

    def barrier_for(tool: Dict[str, Any]) -> np.ndarray:
        return barriers[_tool_key(tool)]

    for p in passes:
        name = str(p["name"])
        role = str(p.get("role"))
        tool = p["tool"]

        if role == "rough":
            bot = barrier_for(tool)
            top = current_top
            dz = np.clip(top - bot, 0.0, None).astype(np.float32, copy=False)
            pass_bands[name] = {"top": top, "bot": bot, "dz": dz}
            current_top = bot  # next rough starts here

        elif role == "finish":
            bot = S
            top = np.full_like(S, Zs, dtype=np.float32)
            dz = np.clip(top - bot, 0.0, None).astype(np.float32, copy=False)
            pass_bands[name] = {"top": top, "bot": bot, "dz": dz}

        else:
            pass_bands[name] = {"top": current_top, "bot": current_top, "dz": np.zeros_like(S, dtype=np.float32)}

    return {"barriers": barriers, "pass_bands": pass_bands}
