from __future__ import annotations

from collections import deque

import numpy as np


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


def dilate2d(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a.astype(np.float32, copy=False)
    a = a.astype(np.float32, copy=False)
    height, width = a.shape
    tmp = np.empty_like(a, dtype=np.float32)
    out = np.empty_like(a, dtype=np.float32)
    for y in range(height):
        tmp[y, :] = _max_filter1d_same(a[y, :], k)
    for x in range(width):
        out[:, x] = _max_filter1d_same(tmp[:, x], k)
    return out


def erode2d(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a.astype(np.float32, copy=False)
    a = a.astype(np.float32, copy=False)
    height, width = a.shape
    tmp = np.empty_like(a, dtype=np.float32)
    out = np.empty_like(a, dtype=np.float32)
    for y in range(height):
        tmp[y, :] = _min_filter1d_same(a[y, :], k)
    for x in range(width):
        out[:, x] = _min_filter1d_same(tmp[:, x], k)
    return out


def gray_close(a: np.ndarray, k: int) -> np.ndarray:
    return erode2d(dilate2d(a, k), k)


def compute_envelope(surface_mm: np.ndarray, diameter_mm: float, pixel_pitch_mm: float) -> np.ndarray:
    r_px = max(1, round(0.5 * float(diameter_mm) / max(1e-9, pixel_pitch_mm)))
    k = 2 * r_px + 1
    return dilate2d(surface_mm, k)


__all__ = ["compute_envelope", "dilate2d", "erode2d", "gray_close"]
