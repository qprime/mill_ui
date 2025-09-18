from __future__ import annotations
from typing import Any, Dict, Tuple, List
from pathlib import Path
import numpy as np
from PIL import Image

from .heightmap_io import load_heightmap
from .bands import make_bands
from .border import generate_rect_border_moves
from .strategy_rough_zslices import plan_rough
from .strategy_raster_finish import plan_finish
from .strategy_border_rect import plan_border_rect  # NEW

__all__ = ["plan"]

_Move = Dict[str, float]

def _norm01(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32, copy=False)
    mn, mx = float(np.min(a)), float(np.max(a))
    if mx <= mn + 1e-12:
        return np.zeros_like(a, dtype=np.uint8)
    return ((a - mn) / (mx - mn) * 255.0).astype(np.uint8)

def _append_border_if_enabled(pass_cfg: Dict[str, Any], cfg: Dict[str, Any], moves: List[_Move]) -> List[_Move]:
    border = pass_cfg.get("border") or {}
    if not border.get("enable", False):
        return moves

    bounds = tuple(cfg["heightmap"]["bounds_mm"])
    tool = pass_cfg.get("tool", {}) or {}
    tool_diam = float(tool.get("diameter_mm", 0.0) or 0.0)

    stepover = border.get("stepover_mm", None)
    if stepover is None:
        stepover = float(pass_cfg.get("stepover_mm", 0.0) or (0.6 * tool_diam))

    inset = float(border.get("inset_mm", 2.0))
    width = float(border.get("width_mm", 4.0))
    depth = float(border.get("depth_mm", cfg["heightmap"].get("max_depth_mm", 1.0)))
    feed = float(pass_cfg.get("feed_mm_per_min", 800.0))

    border_moves = generate_rect_border_moves(
        bounds_mm=bounds,
        inset_mm=inset,
        width_mm=width,
        target_depth_mm=depth,
        stepover_mm=stepover,
        feed_mm_min=feed,
        climb_ccw=True,
    )

    if not border_moves:
        return moves

    return border_moves + moves

def plan(cfg: Dict[str, Any]) -> Dict[str, Any]:
    hm = load_heightmap(cfg)
    S = hm["z_mm"].astype(np.float32, copy=False)
    pitch = float(hm["pixel_pitch_mm"])
    Zs = float(cfg["stock"]["top_z_mm"])

    bands = make_bands(S, Zs, pitch, cfg)

    reports_dir = Path(cfg["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name, b in bands["pass_bands"].items():
        Image.fromarray(_norm01(b["top"])).save(reports_dir / f"band_{name}_top.png")
        Image.fromarray(_norm01(b["bot"])).save(reports_dir / f"band_{name}_bot.png")
        Image.fromarray(_norm01(b["dz"])).save(reports_dir / f"band_{name}_dz.png")

    passes_out: List[Dict[str, Any]] = []
    band_map: Dict[str, Dict[str, np.ndarray]] = bands["pass_bands"]

    for p in cfg["passes"]:
        name = str(p["name"])
        role = str(p.get("role") or "")
        strategy = str(p.get("strategy") or "")
        moves: List[_Move] = []

        # NEW: border strategy as a first-class pass using passes.yaml fields
        if strategy == "border_rect":
            moves = plan_border_rect(p, cfg["heightmap"])

        elif role == "rough":
            b = band_map.get(name)
            if b is None:
                raise KeyError(f"Missing band for pass '{name}' (role=rough)")
            moves = plan_rough(
                name,
                b["top"],
                b["bot"],
                pitch,
                float(p.get("stepover_mm") or 0.75 * float(p["tool"].get("diameter_mm") or 1.0)),
                float(p.get("stepdown_mm") or 0.5 * float(p["tool"].get("diameter_mm") or 1.0)),
                float(cfg["stock"]["safe_z_mm"]),
                float(p.get("feed_mm_per_min") or 1000.0),
                float(p.get("plunge_mm_per_min") or 400.0),
            )

        elif role == "finish":
            b = band_map.get(name)
            if b is None:
                raise KeyError(f"Missing band for pass '{name}' (role=finish)")
            moves = plan_finish(
                name,
                S,
                b["top"],
                b["bot"],
                pitch,
                float(p.get("stepover_mm") or 0.4 * float(p["tool"].get("diameter_mm") or 1.0)),
                float(cfg["stock"]["safe_z_mm"]),
                float(p.get("feed_mm_per_min") or 1200.0),
                float(p.get("plunge_mm_per_min") or 400.0),
            )

        # Optional additive per-pass border from nested config (kept for backwards-compat)
        moves = _append_border_if_enabled(p, cfg, moves)

        passes_out.append({"name": name, "role": role, "tool": p.get("tool", {}), "moves": moves})

    return {
        "project_name": cfg.get("project_name") or "cam_v4",
        "pixel_pitch_mm": pitch,
        "passes": passes_out,
        "bands": bands,
    }
