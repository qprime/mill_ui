# path: skills/cam_engine/stl_writer.py
# desc: Write binary STL from triangle stream
# api: write_binary_stl

from __future__ import annotations

import io
import math
from pathlib import Path
from struct import pack
from typing import Iterable, Tuple

__all__ = ["write_binary_stl"]

_F3 = Tuple[float, float, float]
_Tri = Tuple[_F3, _F3, _F3]


def _normal(a: _F3, b: _F3, c: _F3) -> _F3:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / l, ny / l, nz / l)


def _write_header(f: io.BufferedWriter) -> None:
    tag = b"heightmap-stl"
    f.write(tag + b"\0" * (80 - len(tag)))


def _write_count_placeholder(f: io.BufferedWriter) -> int:
    f.write(pack("<I", 0))
    return f.tell() - 4


def _write_tri(f: io.BufferedWriter, a: _F3, b: _F3, c: _F3) -> None:
    nx, ny, nz = _normal(a, b, c)
    f.write(pack("<12fH", nx, ny, nz,
                 a[0], a[1], a[2],
                 b[0], b[1], b[2],
                 c[0], c[1], c[2], 0))


def write_binary_stl(path: Path, triangles: Iterable[_Tri]) -> None:
    """
    Write triangles to a binary STL at `path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "wb") as f:
        _write_header(f)
        pos = _write_count_placeholder(f)
        for a, b, c in triangles:
            _write_tri(f, a, b, c)
            count += 1
        f.seek(pos)
        f.write(pack("<I", count))
