from __future__ import annotations
from typing import Dict
import numpy as np
from collections import deque

__all__ = ["compute_envelope"]

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

def compute_envelope(surface_mm: np.ndarray, tool: Dict[str, object], pixel_pitch_mm: float) -> np.ndarray:
    """
    Conservative 'can't-go-below' surface for rough-safety.
    Flat-style dilation with radius ~= tool radius (safe over-approx for any tool).
    """
    diam = float((tool or {}).get("diameter_mm") or 0.0)
    r_px = max(1, int(round(0.5 * diam / max(1e-9, pixel_pitch_mm))))
    k = 2 * r_px + 1
    return _dilate2d(surface_mm, k)
