# path: skills/cam_generator_v4/stl_export.py
# desc: Export STL meshes for CAM (surfaces) and PROOF (printable) in one run
# api: export_stl

from __future__ import annotations

from math import ceil, sqrt
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np

from skills.cam_generator_v4.heightmap_io import load_heightmap
from skills.cam_generator_v4.heightfield_solid import triangulate_heightfield
from skills.cam_generator_v4.stl_writer import write_binary_stl

__all__ = ["export_stl"]


# ---------- small config helpers ----------

def _b(d: Mapping[str, Any], k: str, dv: bool) -> bool:
    return bool(d.get(k, dv))


def _f(d: Mapping[str, Any], k: str, dv: float) -> float:
    try:
        return float(d.get(k, dv))
    except Exception:
        return float(dv)


def _i(d: Mapping[str, Any], k: str, dv: int) -> int:
    try:
        return int(d.get(k, dv))
    except Exception:
        return int(dv)


# ---------- plan/bands helpers ----------

def _bands(plan: Mapping[str, Any]) -> Optional[Dict[str, Dict[str, np.ndarray]]]:
    b = plan.get("bands")
    if not isinstance(b, dict):
        return None
    pb = b.get("pass_bands")
    if not isinstance(pb, dict):
        return None
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for name, v in pb.items():
        if isinstance(v, dict) and all(x in v for x in ("top", "bot", "dz")):
            out[name] = {"top": v["top"], "bot": v["bot"], "dz": v["dz"]}
    return out or None


def _ordered_band_names(plan: Mapping[str, Any], bands: Mapping[str, Any]) -> list[str]:
    ordered = [p.get("name") for p in plan.get("passes", []) if isinstance(p, dict)]
    return [n for n in ordered if n in bands] or list(bands.keys())


# ---------- geometry emit ----------

def _emit(path: Path,
          z: np.ndarray,
          pitch: float,
          base_z: float,
          add_walls: bool,
          top_z: float,
          z_exag: float) -> None:
    tris = triangulate_heightfield(z, pitch, base_z, add_walls, top_z, z_exag)
    write_binary_stl(path, tris)


# ---------- triangle estimation / downsample ----------

def _estimate_top_triangles(h: int, w: int) -> int:
    if h < 2 or w < 2:
        return 0
    return 2 * (h - 1) * (w - 1)


def _downsample_to_triangle_budget(z: np.ndarray,
                                   pitch_mm: float,
                                   max_top_tris: int) -> Tuple[np.ndarray, float]:
    """
    Downsample by striding to keep top-surface triangles under max_top_tris.
    Returns (z_ds, pitch_ds).
    """
    h, w = z.shape
    tris = _estimate_top_triangles(h, w)
    if max_top_tris <= 0 or tris <= max_top_tris:
        return z, pitch_mm
    # choose stride s so 2*((h/s-1)*(w/s-1)) <= max_top_tris
    s = max(1, int(ceil(sqrt(tris / float(max_top_tris)))))
    z2 = z[::s, ::s]
    return z2, pitch_mm * s


# ---------- proof downsample/scale ----------

def _downsample_if_needed(z: np.ndarray, pitch_mm: float, max_top_tris: int) -> Tuple[np.ndarray, float]:
    return _downsample_to_triangle_budget(z, pitch_mm, max_top_tris)


def _retarget_pitch(z: np.ndarray, pitch_mm: float, target_w_mm: float | None, target_h_mm: float | None) -> float:
    """
    Change pitch to meet target width/height in mm without resampling (keeps resolution).
    """
    if target_w_mm is None and target_h_mm is None:
        return pitch_mm
    h, w = z.shape
    pitch = pitch_mm
    if target_w_mm:
        pitch = float(target_w_mm) / max(1, (w - 1))
    if target_h_mm:
        pitch = min(pitch, float(target_h_mm) / max(1, (h - 1)))
    return pitch


# ---------- crop-to-changed for bands ----------

def _crop_to_bbox(z: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    y0, y1, x0, x1 = bbox
    return z[y0:y1, x0:x1]


def _bbox_from_mask(mask: np.ndarray, margin_px: int) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0 = max(0, y0 - margin_px)
    x0 = max(0, x0 - margin_px)
    y1 = min(mask.shape[0], y1 + margin_px)
    x1 = min(mask.shape[1], x1 + margin_px)
    return (y0, y1, x0, x1)


def _crop_band_surface(top_before: np.ndarray,
                       bot_after: np.ndarray,
                       eps_mm: float,
                       margin_px: int,
                       pitch_mm: float) -> Tuple[np.ndarray, float]:
    """
    Crop band surface to the minimal rectangle covering areas that changed
    (bot_after < top_before - eps). Returns (z_cropped, pitch_mm) — pitch unchanged.
    If nothing changed, returns a minimal 2x2 crop at one pixel (smallest valid mesh).
    """
    assert top_before.shape == bot_after.shape
    changed = bot_after < (top_before - float(eps_mm))
    bbox = _bbox_from_mask(changed, margin_px)
    if bbox is None:
        # No change: return a tiny 2x2 area from the corner to keep a valid mesh.
        h, w = bot_after.shape
        h2 = min(h, 2)
        w2 = min(w, 2)
        return bot_after[:h2, :w2], pitch_mm
    return _crop_to_bbox(bot_after, bbox), pitch_mm


# ---------- main export ----------

def export_stl(plan_result: Mapping[str, Any],
               cfg: Mapping[str, Any],
               out_dir: Path) -> Dict[str, Any]:
    """
    Emits both CAM and PROOF meshes in one run.

    CAM (for FreeCAD toolpathing):
      - CAM_output/meshes/relief_final.stl
      - CAM_output/meshes/stock_after_{NN}_{pass}.stl (if per_band true)
      - Options to crop band meshes to changed areas and cap triangles

    PROOF (for printing / client samples):
      - CAM_output/meshes/proof/proof_final.stl
      - Optional per-band proof STLs
      - Retarget XY size (target_size_mm), auto-downsample to max_triangles
      - Skirt/base + z_exaggeration for visual clarity
    """
    stl_cfg = cfg.get("stl", {}) if isinstance(cfg.get("stl"), dict) else {}
    if not _b(stl_cfg, "enable", True):
        return {"ok": True, "enabled": False}

    hm = load_heightmap(dict(cfg))
    z0 = hm["z_mm"]                    # full-resolution relief surface (final)
    pitch0 = float(hm["pixel_pitch_mm"])

    top_z = float(cfg["stock"]["top_z_mm"])
    max_depth = float(cfg["heightmap"]["max_depth_mm"])
    stock_bottom = top_z - max_depth

    # --- CAM options ---
    cam_add_walls = _b(stl_cfg, "add_skirt", True)
    cam_per_band = _b(stl_cfg, "per_band", True)
    cam_z_exag = _f(stl_cfg, "z_exaggeration", 1.0)
    base_mm_last = _f(stl_cfg, "base_mm_last", 0.0)
    cam_max_tris = _i(stl_cfg, "max_triangles", 0)          # 0 = unlimited (full res)
    cam_crop = _b(stl_cfg, "crop_changed", True)            # crop band meshes to changed bbox
    cam_crop_eps = _f(stl_cfg, "crop_eps_mm", 0.01)
    cam_crop_margin_px = _i(stl_cfg, "crop_margin_px", 4)

    mesh_dir = Path(out_dir) / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    # ---- CAM final surface ----
    z_final, pitch_final = _downsample_to_triangle_budget(z0, pitch0, cam_max_tris)
    final_cam = mesh_dir / "relief_final.stl"
    _emit(final_cam, z_final, pitch_final, stock_bottom, cam_add_walls, top_z, cam_z_exag)

    cam_files: list[str] = [str(final_cam)]

    # ---- CAM per-band stock-after ----
    bands = _bands(plan_result) if cam_per_band else None
    if isinstance(bands, dict):
        names = _ordered_band_names(plan_result, bands)
        for idx, name in enumerate(names, 1):
            top_before = bands[name]["top"]
            bot_after = bands[name]["bot"]  # stock surface after this band

            z_band = bot_after
            pitch_band = pitch0

            # crop to changed area for big savings
            if cam_crop:
                z_band, pitch_band = _crop_band_surface(top_before, bot_after,
                                                        eps_mm=cam_crop_eps,
                                                        margin_px=cam_crop_margin_px,
                                                        pitch_mm=pitch0)

            # cap triangle count if requested
            z_band, pitch_band = _downsample_to_triangle_budget(z_band, pitch_band, cam_max_tris)

            is_last = idx == len(names)
            z_base = stock_bottom - (base_mm_last if is_last else 0.0)

            out = mesh_dir / f"stock_after_{idx:02d}_{name}.stl"
            _emit(out, z_band, pitch_band, z_base, True, top_z, cam_z_exag)
            cam_files.append(str(out))

    # --- PROOF options (unchanged logic, kept here for completeness) ---
    proof_cfg = stl_cfg.get("proof", {}) if isinstance(stl_cfg.get("proof"), dict) else {}
    proof_enable = _b(proof_cfg, "enable", True)
    proof_dir = mesh_dir / "proof"
    proof_files: list[str] = []
    if proof_enable:
        proof_dir.mkdir(parents=True, exist_ok=True)
        tgt_w = proof_cfg.get("target_size_mm", {}).get("width") if isinstance(proof_cfg.get("target_size_mm"), dict) else proof_cfg.get("target_width_mm")
        tgt_h = proof_cfg.get("target_size_mm", {}).get("height") if isinstance(proof_cfg.get("target_size_mm"), dict) else proof_cfg.get("target_height_mm")
        tgt_w_mm = float(tgt_w) if tgt_w is not None else None
        tgt_h_mm = float(tgt_h) if tgt_h is not None else None

        proof_add_walls = _b(proof_cfg, "add_skirt", True)
        proof_z_exag = _f(proof_cfg, "z_exaggeration", 1.25)
        proof_base_mm = _f(proof_cfg, "base_mm", 6.0)
        proof_per_band = _b(proof_cfg, "per_band", False)
        max_tris = _i(proof_cfg, "max_triangles", 2_000_000)

        # final proof
        z_ds, pitch_ds = _downsample_if_needed(z0, pitch0, max_tris)
        pitch_ds = _retarget_pitch(z_ds, pitch_ds, tgt_w_mm, tgt_h_mm)
        proof_final = proof_dir / "proof_final.stl"
        _emit(proof_final, z_ds, pitch_ds, stock_bottom - proof_base_mm, proof_add_walls, top_z, proof_z_exag)
        proof_files.append(str(proof_final))

        # per-band proofs (optional)
        if proof_per_band and isinstance(bands, dict):
            names = _ordered_band_names(plan_result, bands)
            for idx, name in enumerate(names, 1):
                surface = bands[name]["bot"]
                z_ds_b, pitch_ds_b = _downsample_if_needed(surface, pitch0, max_tris)
                pitch_ds_b = _retarget_pitch(z_ds_b, pitch_ds_b, tgt_w_mm, tgt_h_mm)
                out = proof_dir / f"proof_after_{idx:02d}_{name}.stl"
                _emit(out, z_ds_b, pitch_ds_b, stock_bottom - proof_base_mm, True, top_z, proof_z_exag)
                proof_files.append(str(out))

    return {
        "ok": True,
        "enabled": True,
        "cam": cam_files,
        "proof": proof_files,
        "mesh_dir": str(mesh_dir),
    }
