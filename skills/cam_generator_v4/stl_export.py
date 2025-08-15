# path: skills/cam_generator_v4/stl_export.py
# desc: Export STL meshes for CAM (surfaces) and PROOF (printable) in one run.
#       Mesh pitch is auto-derived from the finish pass stepover (always on).
# api: export_stl

from __future__ import annotations

from math import ceil, sqrt
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, List

import numpy as np

from skills.cam_generator_v4.heightmap_io import load_heightmap
from skills.cam_generator_v4.heightfield_solid import triangulate_heightfield
from skills.cam_generator_v4.stl_writer import write_binary_stl

__all__ = ["export_stl"]


# ---------- tiny config helpers ----------

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


# ---------- bands helpers ----------

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


def _ordered_band_names(plan: Mapping[str, Any], bands: Mapping[str, Any]) -> List[str]:
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
    s = max(1, int(ceil(sqrt(tris / float(max_top_tris)))))
    z2 = z[::s, ::s]
    return z2, pitch_mm * s


def _enforce_min_pitch(z: np.ndarray, pitch_mm: float, min_pitch_mm: float) -> Tuple[np.ndarray, float]:
    """
    Ensure mesh pitch is not finer than min_pitch_mm by striding.
    """
    if min_pitch_mm <= 0 or pitch_mm >= min_pitch_mm:
        return z, pitch_mm
    s = max(1, int(ceil(min_pitch_mm / float(pitch_mm))))
    z2 = z[::s, ::s]
    return z2, pitch_mm * s


# ---------- proof downsample/scale ----------

def _downsample_if_needed(z: np.ndarray, pitch_mm: float, max_top_tris: int) -> Tuple[np.ndarray, float]:
    return _downsample_to_triangle_budget(z, pitch_mm, max_top_tris)


def _retarget_pitch(z: np.ndarray, pitch_mm: float,
                    target_w_mm: Optional[float],
                    target_h_mm: Optional[float]) -> float:
    """
    Change pitch to meet target width/height in mm without resampling (keeps resolution).
    """
    if target_w_mm is None and target_h_mm is None:
        return pitch_mm
    h, w = z.shape
    pitch = pitch_mm
    if target_w_mm is not None:
        pitch = float(target_w_mm) / max(1, (w - 1))
    if target_h_mm is not None:
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
    Crop band surface to the minimal rectangle covering areas that changed.
    Returns (z_cropped, pitch_mm). If nothing changed, returns a minimal 2x2 crop.
    """
    assert top_before.shape == bot_after.shape
    changed = bot_after < (top_before - float(eps_mm))
    bbox = _bbox_from_mask(changed, margin_px)
    if bbox is None:
        h, w = bot_after.shape
        h2 = min(h, 2)
        w2 = min(w, 2)
        return bot_after[:h2, :w2], pitch_mm
    return _crop_to_bbox(bot_after, bbox), pitch_mm


# ---------- autopitch (always on) ----------

def _find_pass_by_name(cfg_passes: List[Mapping[str, Any]], name: str) -> Optional[Mapping[str, Any]]:
    for p in cfg_passes:
        if str(p.get("name", "")).lower() == str(name).lower():
            return p
    return None


def _finish_tool_diameter_mm(plan: Mapping[str, Any],
                             cfg_passes: List[Mapping[str, Any]],
                             finest_name: Optional[str]) -> Optional[float]:
    """
    Diameter from:
      1) explicitly named finest pass in cfg (if provided),
      2) else the smallest tool diameter across plan['passes'],
      3) else the smallest tool diameter across cfg_passes.
    """
    if finest_name:
        # try plan first (includes resolved tools), then cfg
        for source in (plan.get("passes") or [], cfg_passes):
            for p in source:
                if str(p.get("name", "")).lower() == finest_name.lower():
                    t = (p.get("tool") or {})
                    d = t.get("diameter_mm") if isinstance(t, dict) else None
                    if d:
                        try:
                            return float(d)
                        except Exception:
                            pass
        # fall through to auto-pick below if missing
    # pick smallest diameter seen
    best: Optional[float] = None
    for p in (plan.get("passes") or []):
        t = (p.get("tool") or {})
        d = t.get("diameter_mm") if isinstance(t, dict) else None
        if d is None:
            continue
        try:
            val = float(d)
        except Exception:
            continue
        best = val if best is None else min(best, val)
    if best is not None:
        return best
    for p in cfg_passes:
        t = (p.get("tool") or {})
        d = t.get("diameter_mm") if isinstance(t, dict) else None
        if d is None:
            continue
        try:
            val = float(d)
        except Exception:
            continue
        best = val if best is None else min(best, val)
    return best


def _stepover_mm_for_pass(plan: Mapping[str, Any],
                          cfg_passes: List[Mapping[str, Any]],
                          name: Optional[str],
                          diameter_mm: Optional[float],
                          default_frac: float) -> Optional[float]:
    """
    Stepover mm from pass (name matches), falling back to fraction*diameter.
    Recognized keys: 'stepover_mm', 'stepover_frac' (0..1), 'stepover_percent' (0..100).
    """
    def from_mapping(p: Mapping[str, Any]) -> Optional[float]:
        # exact mm
        if "stepover_mm" in p:
            try:
                v = float(p["stepover_mm"])
                if v > 0:
                    return v
            except Exception:
                pass
        # fraction
        if "stepover_frac" in p and diameter_mm:
            try:
                frac = float(p["stepover_frac"])
                if 0 < frac <= 1:
                    return frac * float(diameter_mm)
            except Exception:
                pass
        # percent
        if "stepover_percent" in p and diameter_mm:
            try:
                pct = float(p["stepover_percent"])
                if 0 < pct <= 100:
                    return (pct / 100.0) * float(diameter_mm)
            except Exception:
                pass
        return None

    if name:
        # try plan pass (resolved), then cfg pass (declared)
        for source in (plan.get("passes") or [], cfg_passes):
            for p in source:
                if str(p.get("name", "")).lower() == name.lower():
                    val = from_mapping(p)
                    if val and val > 0:
                        return val

    # fallback: look across passes and pick smallest positive stepover
    best: Optional[float] = None
    for source in (plan.get("passes") or [], cfg_passes):
        for p in source:
            val = from_mapping(p)
            if val and val > 0:
                best = val if best is None else min(best, val)
    if best and best > 0:
        return best

    # final fallback: default fraction * diameter
    if diameter_mm and diameter_mm > 0:
        return max(0.0, float(default_frac)) * float(diameter_mm)
    return None


def _autopitch_min_pitch_mm(plan: Mapping[str, Any],
                            cfg: Mapping[str, Any]) -> float:
    """
    Compute min mesh pitch from the chosen "finest" pass stepover:
        P_min = stepover_mm / 2
    Always enabled. Uses cfg['stl']['autopitch'] hints for
    finest_pass_name and default_stepover_frac (fallback).
    """
    stl_cfg = cfg.get("stl", {}) if isinstance(cfg.get("stl"), dict) else {}
    ap = stl_cfg.get("autopitch", {}) if isinstance(stl_cfg.get("autopitch"), dict) else {}

    finest_name = ap.get("finest_pass_name")
    default_frac = _f(ap, "default_stepover_frac", 0.30)

    cfg_passes = list(cfg.get("passes") or [])
    d_mm = _finish_tool_diameter_mm(plan, cfg_passes, finest_name)
    if not d_mm or d_mm <= 0.0:
        return 0.0

    s_mm = _stepover_mm_for_pass(plan, cfg_passes, finest_name, d_mm, default_frac)
    if not s_mm or s_mm <= 0.0:
        return 0.0

    return s_mm / 2.0


# ---------- main export ----------

def export_stl(plan_result: Mapping[str, Any],
               cfg: Mapping[str, Any],
               out_dir: Path) -> Dict[str, Any]:
    """
    Emits both CAM and PROOF meshes in one run.

    CAM (for FreeCAD):
      - CAM_output/meshes/relief_final.stl
      - CAM_output/meshes/stock_after_{NN}_{pass}.stl (if per_band true)
      - Auto-pitch-from-tool (always on), crop-to-changed, triangle cap.

    PROOF:
      - CAM_output/meshes/proof/proof_final.stl (+ optional per-band)
      - Retarget XY size, downsample to triangle cap, base/skirt, Z exaggeration.
    """
    stl_cfg = cfg.get("stl", {}) if isinstance(cfg.get("stl"), dict) else {}
    if not _b(stl_cfg, "enable", True):
        return {"ok": True, "enabled": False}

    hm = load_heightmap(dict(cfg))
    z0 = hm["z_mm"]
    pitch0 = float(hm["pixel_pitch_mm"])

    top_z = float(cfg["stock"]["top_z_mm"])
    max_depth = float(cfg["heightmap"]["max_depth_mm"])
    stock_bottom = top_z - max_depth

    # CAM options
    cam_add_walls = _b(stl_cfg, "add_skirt", True)
    cam_per_band = _b(stl_cfg, "per_band", True)
    cam_z_exag = _f(stl_cfg, "z_exaggeration", 1.0)
    base_mm_last = _f(stl_cfg, "base_mm_last", 0.0)
    cam_max_tris = _i(stl_cfg, "max_triangles", 0)          # 0 = unlimited
    cam_crop = _b(stl_cfg, "crop_changed", True)
    cam_crop_eps = _f(stl_cfg, "crop_eps_mm", 0.01)
    cam_crop_margin_px = _i(stl_cfg, "crop_margin_px", 4)

    # Auto pitch from tool (ALWAYS ON)
    min_pitch_tool_mm = _autopitch_min_pitch_mm(plan_result, cfg)

    mesh_dir = Path(out_dir) / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    # CAM final
    z_final, pitch_final = _enforce_min_pitch(z0, pitch0, min_pitch_tool_mm)
    z_final, pitch_final = _downsample_to_triangle_budget(z_final, pitch_final, cam_max_tris)
    final_cam = mesh_dir / "relief_final.stl"
    _emit(final_cam, z_final, pitch_final, stock_bottom, cam_add_walls, top_z, cam_z_exag)

    cam_files: List[str] = [str(final_cam)]

    # CAM per-band
    bands = _bands(plan_result) if cam_per_band else None
    if isinstance(bands, dict):
        names = _ordered_band_names(plan_result, bands)
        for idx, name in enumerate(names, 1):
            top_before = bands[name]["top"]
            bot_after = bands[name]["bot"]

            z_band, pitch_band = bot_after, pitch0
            if cam_crop:
                z_band, pitch_band = _crop_band_surface(
                    top_before, bot_after, eps_mm=cam_crop_eps,
                    margin_px=cam_crop_margin_px, pitch_mm=pitch0
                )

            # enforce tool-aware pitch, then global triangle cap
            z_band, pitch_band = _enforce_min_pitch(z_band, pitch_band, min_pitch_tool_mm)
            z_band, pitch_band = _downsample_to_triangle_budget(z_band, pitch_band, cam_max_tris)

            is_last = idx == len(names)
            z_base = stock_bottom - (base_mm_last if is_last else 0.0)

            out = mesh_dir / f"stock_after_{idx:02d}_{name}.stl"
            _emit(out, z_band, pitch_band, z_base, True, top_z, cam_z_exag)
            cam_files.append(str(out))

    # PROOF (unchanged)
    proof_cfg = stl_cfg.get("proof", {}) if isinstance(stl_cfg.get("proof"), dict) else {}
    proof_enable = _b(proof_cfg, "enable", True)
    proof_dir = mesh_dir / "proof"
    proof_files: List[str] = []
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
        "autopitch": {
            "min_pitch_tool_mm": float(min_pitch_tool_mm or 0.0),
            "max_triangles": int(cam_max_tris or 0),
        },
    }
