# path: skills/cam_generator_v4/planner.py  
# desc: Orchestrate CAM planning with border support
# api: plan
# tags: cam,planning,border

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

__all__ = ["plan"]

_Move = Dict[str, float]

def _norm01(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32, copy=False)
    mn, mx = float(np.min(a)), float(np.max(a))
    if mx <= mn + 1e-12:
        return np.zeros_like(a, dtype=np.uint8)
    return ((a - mn) / (mx - mn) * 255.0).astype(np.uint8)

def _append_border_if_enabled(pass_cfg: Dict[str, Any], cfg: Dict[str, Any], moves: List[_Move]) -> List[_Move]:
    """Add border toolpath if enabled in pass config."""
    border = pass_cfg.get("border") or {}
    if not border.get("enable", False):
        return moves

    bounds = tuple(cfg["heightmap"]["bounds_mm"])
    tool = pass_cfg.get("tool", {}) or {}
    tool_diam = float(tool.get("diameter_mm", 0.0) or 0.0)

    # Get border parameters
    stepover = border.get("stepover_mm", None)
    if stepover is None:
        stepover = float(pass_cfg.get("stepover_mm", 0.0) or (0.6 * tool_diam))

    inset = float(border.get("inset_mm", 2.0))
    width = float(border.get("width_mm", 4.0))
    depth = float(border.get("depth_mm", cfg["heightmap"].get("max_depth_mm", 1.0)))
    feed = float(pass_cfg.get("feed_mm_per_min", 800.0))

    # Generate border moves outside the carving area
    border_moves = generate_rect_border_moves(
        bounds_mm=bounds,
        inset_mm=inset,  # positive inset puts border outside the carving area
        width_mm=width,
        target_depth_mm=depth,
        stepover_mm=stepover,
        feed_mm_min=feed,
        climb_ccw=True,
    )
    
    if not border_moves:
        return moves
    
    # Put border moves first so they're cut before the main carving
    return border_moves + moves

def plan(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main planning function that orchestrates the entire CAM process.
    
    Steps:
    1. Load heightmap
    2. Compute pass bands  
    3. Generate toolpaths for each pass
    4. Add borders if configured
    5. Save debug images
    """
    hm = load_heightmap(cfg)
    S = hm["z_mm"].astype(np.float32, copy=False)
    pitch = float(hm["pixel_pitch_mm"])
    Zs = float(cfg["stock"]["top_z_mm"])

    bands = make_bands(S, Zs, pitch, cfg)

    # Save debug images
    reports_dir = Path(cfg["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name, b in bands["pass_bands"].items():
        Image.fromarray(_norm01(b["top"])).save(reports_dir / f"band_{name}_top.png")
        Image.fromarray(_norm01(b["bot"])).save(reports_dir / f"band_{name}_bot.png")
        Image.fromarray(_norm01(b["dz"])).save(reports_dir / f"band_{name}_dz.png")

    passes_out: List[Dict[str, Any]] = []
    
    for p in cfg["passes"]:
        name = str(p["name"])
        role = str(p.get("role"))
        band = bands["pass_bands"][name]

        # Generate base toolpath based on role
        if role == "rough":
            moves = plan_rough(
                name,
                band["top"],
                band["bot"],
                pitch,
                float(p.get("stepover_mm") or 0.75 * float(p["tool"].get("diameter_mm") or 1.0)),
                float(p.get("stepdown_mm") or 0.5 * float(p["tool"].get("diameter_mm") or 1.0)),
                float(cfg["stock"]["safe_z_mm"]),
                float(p.get("feed_mm_per_min") or 1000.0),
                float(p.get("plunge_mm_per_min") or 400.0),
            )
        elif role == "finish":
            moves = plan_finish(
                name,
                S,                  # follow final surface
                band["top"],        # stock plane
                band["bot"],        # S
                pitch,
                float(p.get("stepover_mm") or 0.4 * float(p["tool"].get("diameter_mm") or 1.0)),
                float(cfg["stock"]["safe_z_mm"]),
                float(p.get("feed_mm_per_min") or 1200.0),
                float(p.get("plunge_mm_per_min") or 400.0),
            )
        else:
            moves = []

        # Add border if configured
        moves = _append_border_if_enabled(p, cfg, moves)

        passes_out.append({"name": name, "role": role, "tool": p["tool"], "moves": moves})

    return {
        "project_name": cfg.get("project_name") or "cam_v4",
        "pixel_pitch_mm": pitch,
        "passes": passes_out,
        "bands": bands,
    }