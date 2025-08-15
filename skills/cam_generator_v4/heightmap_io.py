# path: cam_generator/heightmap_io.py
# desc: Load 8/16-bit PNG heightmap and map to surface Z in mm with floor removal and gamma scaling
# api: load_heightmap
# tags: image,io,mm

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

import numpy as np
from PIL import Image

def _read_png(path: Path) -> np.ndarray:
    im = Image.open(path)
    # 16-bit grayscale
    if im.mode == "I;16":
        arr = np.array(im, dtype=np.uint16)
        mn = float(arr.min()); mx = float(arr.max()); rng = mx - mn
        if rng <= 0: return np.zeros_like(arr, dtype=np.float32)
        return ((arr.astype(np.float32) - mn) / rng).astype(np.float32)
    # 8-bit grayscale (or convert)
    if im.mode != "L":
        im = im.convert("L")
    arr = np.array(im, dtype=np.uint8)
    return (arr.astype(np.float32) / 255.0).astype(np.float32)

def _apply_floor_and_gamma(norm01: np.ndarray, 
                          floor_gray: float, 
                          gamma: float,
                          bit_depth: int) -> np.ndarray:
    """Apply floor removal and gamma scaling to normalized image data."""
    # Convert back to original bit depth for floor calculation
    if bit_depth == 16:
        gray_values = norm01 * 65535.0
        max_gray = 65535.0
    else:
        gray_values = norm01 * 255.0
        max_gray = 255.0
    
    # Apply floor removal: values below floor_gray become 0
    floor_mask = gray_values <= floor_gray
    adjusted_values = np.maximum(gray_values - floor_gray, 0.0)
    
    # Renormalize to 0-1 based on remaining range
    remaining_range = max_gray - floor_gray
    if remaining_range > 0:
        norm_adjusted = adjusted_values / remaining_range
    else:
        norm_adjusted = np.zeros_like(adjusted_values)
    
    # Apply gamma scaling
    if gamma != 1.0:
        norm_adjusted = np.power(norm_adjusted, gamma)
    
    return norm_adjusted.astype(np.float32)

def _to_surface(norm01: np.ndarray,
                max_depth_mm: float,
                top_z_mm: float,
                white_is_high: bool,
                floor_gray: float = 0.0,
                gamma: float = 1.0,
                bit_depth: int = 8) -> np.ndarray:
    """Convert normalized image to surface heights with optional floor removal and gamma scaling."""
    
    # Apply floor removal and gamma scaling if specified
    if floor_gray > 0.0 or gamma != 1.0:
        norm01 = _apply_floor_and_gamma(norm01, floor_gray, gamma, bit_depth)
    
    v = norm01 if white_is_high else (1.0 - norm01)
    depth = (1.0 - v) * float(max_depth_mm)
    return (float(top_z_mm) - depth).astype(np.float32)

def _derive_pixel_pitch_mm_from_target(size_px: Tuple[int,int],
                                       target_size_mm: Optional[Dict[str, float]]) -> float:
    if not target_size_mm:
        raise ValueError("pixel_pitch_mm <= 0 but heightmap.target_size_mm not provided")
    H, W = int(size_px[0]), int(size_px[1])
    wmm = float(target_size_mm.get("width_mm", 0.0) or 0.0)
    hmm = float(target_size_mm.get("height_mm", 0.0) or 0.0)
    if wmm <= 0.0 and hmm <= 0.0:
        raise ValueError("target_size_mm must include width_mm or height_mm (>0)")
    if wmm > 0.0 and hmm > 0.0:
        # keep inside requested box
        pitch_w = wmm / float(W)
        pitch_h = hmm / float(H)
        return min(pitch_w, pitch_h)
    if wmm > 0.0:
        return wmm / float(W)
    return hmm / float(H)

def load_heightmap(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single entry used by planner.plan(cfg).
    Supports:
      - explicit heightmap.pixel_pitch_mm > 0
      - auto-pitch when heightmap.pixel_pitch_mm <= 0 using heightmap.target_size_mm.{width_mm|height_mm}
      - floor_gray: removes noise floor (gray values below this become background)
      - gamma: non-linear scaling for more dramatic relief (< 1.0 emphasizes highlights)
    Returns:
      {"z_mm": float32[H,W], "pixel_pitch_mm": float, "size_px": (H,W), "size_mm": (W*pitch, H*pitch)}
    Also writes back to cfg["heightmap"]:
      pixel_pitch_mm, bounds_mm, size_px, size_mm
    """
    hm_cfg = cfg.get("heightmap", {})
    img_path = hm_cfg.get("image_path")
    if not img_path:
        # fallback to paths.image if you keep that in cfg
        img_path = cfg.get("paths", {}).get("image")
    if not img_path:
        raise ValueError("heightmap.image_path is required (or paths.image)")

    # Required numeric params
    max_depth_mm = float(hm_cfg["max_depth_mm"])
    top_z_mm = float(cfg.get("stock", {}).get("top_z_mm", 0.0))
    white_is_high = bool(hm_cfg.get("white_is_high", True))
    
    # NEW: Floor removal and gamma scaling parameters
    floor_gray = float(hm_cfg.get("floor_gray", 0.0))
    gamma = float(hm_cfg.get("gamma", 1.0))

    # Load image and detect bit depth
    im = Image.open(Path(img_path))
    bit_depth = 16 if im.mode == "I;16" else 8
    
    # Load image → normalized → surface
    z_norm = _read_png(Path(img_path))
    z_mm = _to_surface(z_norm, max_depth_mm, top_z_mm, white_is_high, floor_gray, gamma, bit_depth)
    H, W = z_mm.shape

    # Resolve pixel pitch
    pitch_cfg = float(hm_cfg.get("pixel_pitch_mm", 0.0) or 0.0)
    if pitch_cfg > 0.0:
        pitch = pitch_cfg
    else:
        pitch = _derive_pixel_pitch_mm_from_target((H, W), hm_cfg.get("target_size_mm"))

    width_mm, height_mm = W * pitch, H * pitch

    # Persist resolved values for all downstream modules
    hm_cfg["pixel_pitch_mm"] = float(pitch)
    hm_cfg["bounds_mm"] = (0.0, width_mm, 0.0, height_mm)
    hm_cfg["size_px"] = (H, W)
    hm_cfg["size_mm"] = (width_mm, height_mm)
    cfg["heightmap"] = hm_cfg

    return {
        "z_mm": z_mm,
        "pixel_pitch_mm": float(pitch),
        "size_px": (H, W),
        "size_mm": (width_mm, height_mm),
    }