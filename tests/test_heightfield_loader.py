from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from generators.area.heightfield_loader import (
    SQUARE_PIXEL_TOLERANCE,
    load_heightfield,
    validate_square_pixels,
)


def _write_png_16bit(path: Path, w: int = 16, h: int = 16) -> None:
    arr = (np.linspace(0.0, 1.0, w * h).reshape(h, w) * 65535).astype(np.uint16)
    img = Image.fromarray(arr, mode="I;16")
    img.save(path, format="PNG")


def _write_png_8bit(path: Path, w: int = 16, h: int = 16) -> None:
    arr = np.full((h, w), 128, dtype=np.uint8)
    img = Image.fromarray(arr, mode="L")
    img.save(path, format="PNG")


def _write_png_rgb(path: Path, w: int = 16, h: int = 16) -> None:
    arr = np.full((h, w, 3), 128, dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    img.save(path, format="PNG")


def _write_png_rgba(path: Path, w: int = 16, h: int = 16) -> None:
    arr = np.full((h, w, 4), 128, dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGBA")
    img.save(path, format="PNG")


def test_heightfield_load_16bit_grayscale_ok(tmp_path: Path):
    p = tmp_path / "ok.png"
    _write_png_16bit(p, w=16, h=16)
    arr = load_heightfield(str(p))
    assert arr.dtype == np.float32
    assert arr.shape == (16, 16)
    assert 0.0 <= arr.min() <= arr.max() <= 1.0


def test_heightfield_rejects_8bit(tmp_path: Path):
    p = tmp_path / "eight.png"
    _write_png_8bit(p)
    with pytest.raises(ValueError, match="16-bit"):
        load_heightfield(str(p))


def test_heightfield_rejects_rgb(tmp_path: Path):
    p = tmp_path / "rgb.png"
    _write_png_rgb(p)
    with pytest.raises(ValueError, match=r"16-bit|single-channel grayscale"):
        load_heightfield(str(p))


def test_heightfield_rejects_alpha(tmp_path: Path):
    p = tmp_path / "rgba.png"
    _write_png_rgba(p)
    with pytest.raises(ValueError, match=r"16-bit|single-channel grayscale"):
        load_heightfield(str(p))


def test_heightfield_rejects_non_png(tmp_path: Path):
    p = tmp_path / "notpng.jpg"
    p.write_bytes(b"nope")
    with pytest.raises(ValueError, match="must be PNG"):
        load_heightfield(str(p))


def test_heightfield_rejects_missing_file(tmp_path: Path):
    p = tmp_path / "missing.png"
    with pytest.raises(ValueError, match="not found"):
        load_heightfield(str(p))


def test_heightfield_detects_16bit_despite_pil_mode_I(tmp_path: Path):
    p = tmp_path / "pil_mode_I.png"
    _write_png_16bit(p, w=8, h=8)
    with Image.open(p) as img:
        assert img.mode in ("I", "I;16")

    arr = load_heightfield(str(p))
    assert arr.shape == (8, 8)


def test_heightfield_cache_invalidates_on_mtime(tmp_path: Path):
    p = tmp_path / "cached.png"
    _write_png_16bit(p, w=4, h=4)
    arr1 = load_heightfield(str(p))

    arr2 = load_heightfield(str(p))
    assert arr2 is arr1

    new_mtime = p.stat().st_mtime + 1.0
    os.utime(p, (new_mtime, new_mtime))
    _write_png_16bit(p, w=4, h=4)
    os.utime(p, (new_mtime, new_mtime))

    arr_new = load_heightfield(str(p))
    assert arr_new is not arr1


def test_validate_square_pixels_ok(tmp_path: Path):
    p = tmp_path / "sq.png"
    _write_png_16bit(p, w=32, h=16)
    w_px, h_px = validate_square_pixels(str(p), width_mm=64.0, height_mm=32.0)
    assert (w_px, h_px) == (32, 16)


def test_validate_square_pixels_rejects_non_square(tmp_path: Path):
    p = tmp_path / "nonsq.png"
    _write_png_16bit(p, w=32, h=16)
    with pytest.raises(ValueError, match="pixel aspect inconsistent"):
        validate_square_pixels(str(p), width_mm=64.0, height_mm=16.0)


def test_square_pixel_tolerance_is_1e_minus_4():
    assert SQUARE_PIXEL_TOLERANCE == 1e-4
