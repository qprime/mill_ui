from __future__ import annotations

import base64
import os
import struct

import numpy as np
from PIL import Image

SQUARE_PIXEL_TOLERANCE = 1e-4

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


_array_cache: dict[str, tuple[float, np.ndarray]] = {}
_data_url_cache: dict[str, tuple[float, str]] = {}


def _read_png_ihdr(path: str) -> tuple[int, int, int, int]:
    with open(path, "rb") as fh:
        sig = fh.read(8)
        if sig != _PNG_SIGNATURE:
            raise ValueError(f"Heightfield image is not a valid PNG (bad signature): {path}")
        length_bytes = fh.read(4)
        chunk_type = fh.read(4)
        if chunk_type != b"IHDR":
            raise ValueError(f"Heightfield PNG missing IHDR chunk: {path}")
        length = struct.unpack(">I", length_bytes)[0]
        if length < 13:
            raise ValueError(f"Heightfield PNG IHDR chunk truncated: {path}")
        data = fh.read(13)
        width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
    return width, height, bit_depth, color_type


def load_heightfield(image_path: str) -> np.ndarray:
    if not os.path.exists(image_path):
        raise ValueError(f"Heightfield image not found: {image_path}")

    mtime = os.path.getmtime(image_path)
    cached = _array_cache.get(image_path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    ext = os.path.splitext(image_path)[1].lower()
    if ext != ".png":
        raise ValueError(f"Heightfield image must be PNG, got {ext or '(none)'}")

    _, _, bit_depth, color_type = _read_png_ihdr(image_path)

    if bit_depth != 16:
        raise ValueError(
            f"Heightfield image must be 16-bit grayscale (got {bit_depth}-bit). See docs/heightfield.md for conversion."
        )
    if color_type != 0:
        raise ValueError(
            f"Heightfield image must be single-channel grayscale (PNG color-type 0), got color-type {color_type}"
        )

    with Image.open(image_path) as img:
        img.load()
        raw = np.array(img, dtype=np.uint16)

    if raw.ndim != 2:
        raise ValueError(f"Heightfield image decoded to {raw.ndim}-D array; expected 2-D grayscale")

    arr = (raw.astype(np.float32) / 65535.0).copy()
    _array_cache[image_path] = (mtime, arr)
    return arr


def load_heightfield_data_url(image_path: str) -> str:
    if not os.path.exists(image_path):
        raise ValueError(f"Heightfield image not found: {image_path}")

    mtime = os.path.getmtime(image_path)
    cached = _data_url_cache.get(image_path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    with open(image_path, "rb") as fh:
        data_bytes = fh.read()
    encoded = base64.b64encode(data_bytes).decode("ascii")
    url = f"data:image/png;base64,{encoded}"
    _data_url_cache[image_path] = (mtime, url)
    return url


def validate_square_pixels(
    image_path: str,
    width_mm: float,
    height_mm: float,
) -> tuple[int, int]:
    if not os.path.exists(image_path):
        raise ValueError(f"Heightfield image not found: {image_path}")
    w_px, h_px, _, _ = _read_png_ihdr(image_path)
    a = width_mm / w_px
    b = height_mm / h_px
    denom = max(a, b)
    if denom > 0 and abs(a - b) / denom >= SQUARE_PIXEL_TOLERANCE:
        raise ValueError(
            f"Heightfield pixel aspect inconsistent: width_mm/W={a:.6f}mm, "
            f"height_mm/H={b:.6f}mm (tolerance={SQUARE_PIXEL_TOLERANCE})"
        )
    return w_px, h_px


__all__ = [
    "SQUARE_PIXEL_TOLERANCE",
    "load_heightfield",
    "load_heightfield_data_url",
    "validate_square_pixels",
]
