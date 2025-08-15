# path: skills/cam_generator_v4/heightfield_solid.py
# desc: Triangulate a heightfield to a watertight solid with optional base/skirt
# api: triangulate_heightfield

from __future__ import annotations

from typing import Generator, Iterable, Tuple

import numpy as np

__all__ = ["triangulate_heightfield"]

_F3 = Tuple[float, float, float]
_Tri = Tuple[_F3, _F3, _F3]


def _p(x: float, y: float, z: float) -> _F3:
    return (float(x), float(y), float(z))


def _top_tris(z: np.ndarray, pitch: float) -> Generator[_Tri, None, None]:
    h, w = z.shape
    for j in range(h - 1):
        y = j * pitch
        y1 = (j + 1) * pitch
        z0 = z[j]
        z1 = z[j + 1]
        for i in range(w - 1):
            x = i * pitch
            x1 = (i + 1) * pitch
            a = _p(x, y, z0[i])
            b = _p(x1, y, z0[i + 1])
            c = _p(x1, y1, z1[i + 1])
            d = _p(x, y1, z1[i])
            # consistent winding (counter-clockwise outward normal)
            yield (a, b, c)
            yield (a, c, d)


def _base_tris(h: int, w: int, pitch: float, zb: float) -> Generator[_Tri, None, None]:
    # bottom face, reversed winding to point normal downward
    for j in range(h - 1):
        y = j * pitch
        y1 = (j + 1) * pitch
        for i in range(w - 1):
            x = i * pitch
            x1 = (i + 1) * pitch
            a = _p(x, y, zb)
            b = _p(x1, y, zb)
            c = _p(x1, y1, zb)
            d = _p(x, y1, zb)
            yield (c, b, a)
            yield (d, c, a)


def _wall_side(col: np.ndarray, xs: float, ys0: float, axis: str,
               pitch: float, zb: float, flip: bool) -> Generator[_Tri, None, None]:
    n = col.size
    for k in range(n - 1):
        if axis in ("west", "east"):
            a = _p(xs, ys0 + k * pitch, col[k])
            d = _p(xs, ys0 + (k + 1) * pitch, col[k + 1])
            b = _p(xs, ys0 + k * pitch, zb)
            c = _p(xs, ys0 + (k + 1) * pitch, zb)
        else:
            a = _p(ys0 + k * pitch, xs, col[k])
            d = _p(ys0 + (k + 1) * pitch, xs, col[k + 1])
            b = _p(ys0 + k * pitch, xs, zb)
            c = _p(ys0 + (k + 1) * pitch, xs, zb)
        if flip:
            yield (b, a, d)
            yield (b, d, c)
        else:
            yield (a, b, c)
            yield (a, c, d)


def _walls(z: np.ndarray, pitch: float, zb: float) -> Generator[_Tri, None, None]:
    h, w = z.shape
    west = z[:, 0]
    east = z[:, -1]
    south = z[0, :]
    north = z[-1, :]

    yield from _wall_side(west, 0.0, 0.0, "west", pitch, zb, flip=False)
    yield from _wall_side(east, (w - 1) * pitch, 0.0, "east", pitch, zb, flip=True)
    yield from _wall_side(south, 0.0, 0.0, "south", pitch, zb, flip=True)
    yield from _wall_side(north, 0.0, (h - 1) * pitch, "north", pitch, zb, flip=False)


def _z_exaggerate(z: np.ndarray, top_z: float, k: float) -> np.ndarray:
    if k == 1.0:
        return z
    # scale deltas around top_z to exaggerate relief for print proofs
    return (top_z - (top_z - z) * float(k)).astype(np.float32, copy=False)


def triangulate_heightfield(z_mm: np.ndarray,
                            pixel_pitch_mm: float,
                            base_plane_z_mm: float,
                            add_base_and_walls: bool,
                            top_z_mm: float,
                            z_exaggeration: float = 1.0) -> Iterable[_Tri]:
    """
    Triangulate heightfield to triangles. If add_base_and_walls is True, returns a
    watertight solid (top + walls + base).
    """
    z = np.asarray(z_mm, dtype=np.float32)
    z = _z_exaggerate(z, float(top_z_mm), float(z_exaggeration))

    h, w = z.shape
    if h < 2 or w < 2:
        return  # nothing to emit

    yield from _top_tris(z, float(pixel_pitch_mm))

    if add_base_and_walls:
        yield from _base_tris(h, w, float(pixel_pitch_mm), float(base_plane_z_mm))
        yield from _walls(z, float(pixel_pitch_mm), float(base_plane_z_mm))
