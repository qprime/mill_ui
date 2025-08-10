# path: skills/cam_generator/core/multi_pass.py
# desc: Multi-pass heightmap CAM generation with absolute relief mapping and optional border
# api: generate_all_passes
# tags: cam,gcode,relief,border

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import json
import numpy as np
import yaml
from scipy.ndimage import gaussian_filter, zoom

from skills.cam_generator.analysis.curvature import compute_slope_map
from skills.cam_generator.core.gcode_writer import write_gcode
from skills.cam_generator.core.job_loader import load_job_config
from skills.cam_generator.core.loader import load_heightmap
from skills.cam_generator.core.pass_reporter import PassReporter
from skills.cam_generator.core.time_estimator import estimate_cut_time
from skills.cam_generator.core.toggles import get_enabled_algorithms
from skills.cam_generator.gcode.emit_gcode import emit_gcode_from_path
from skills.cam_generator.optimizers.prune_redundant import deduplicate_path
from skills.cam_generator.optimizers.reduce_colinear import reduce_colinear_path
from skills.cam_generator.path_builders.border import generate_border_path
from skills.cam_generator.path_builders.raster import generate_raster_xyz_path


def _normalize(heightmap: np.ndarray, percentiles: Optional[Sequence[float]], gamma: float) -> np.ndarray:
    h = heightmap
    if percentiles and len(percentiles) == 2:
        lo, hi = float(percentiles[0]), float(percentiles[1])
        pmin = np.percentile(h, lo)
        pmax = np.percentile(h, hi)
    else:
        pmin, pmax = float(h.min()), float(h.max())
    if pmax <= pmin:
        n = np.zeros_like(h, dtype=np.float32)
    else:
        n = (h - pmin) / (pmax - pmin)
        n = np.clip(n, 0.0, 1.0).astype("float32")
    if gamma != 1.0:
        n = np.power(np.maximum(n, 1e-8), float(gamma))
    return n


def _apply_zero_threshold(n: np.ndarray, thresh: Optional[float], thresh_pct: Optional[float]) -> np.ndarray:
    if thresh_pct is not None:
        t = float(np.percentile(n, float(thresh_pct)))
        return np.clip((n - t) / max(1e-6, 1.0 - t), 0.0, 1.0)
    if thresh is not None:
        t = float(thresh)
        return np.clip((n - t) / max(1e-6, 1.0 - t), 0.0, 1.0)
    return n


def _smooth_mm(zmap_mm: np.ndarray, method: str, relief_mm: float, base_relief: float, base_sigma: float,
               bilateral: Mapping[str, float]) -> np.ndarray:
    m = method.lower()
    if m == "none":
        return zmap_mm
    if m in ("auto", "gaussian"):
        factor = max(1.0, relief_mm / max(1e-6, base_relief))
        return gaussian_filter(zmap_mm, base_sigma * factor)
    if m == "bilateral":
        import cv2
        d = int(bilateral.get("d", 5))
        sigma_color = float(bilateral.get("sigma_color", 0.5))
        sigma_space = float(bilateral.get("sigma_space", 5.0))
        return cv2.bilateralFilter(zmap_mm.astype("float32"), d, sigma_color, sigma_space)
    return zmap_mm


def _surface_from_path(path: List[List[Tuple[float, float, float]]], target_shape: Optional[Tuple[int, int]] = None) -> np.ndarray:
    h = len(path)
    w = max(len(r) for r in path) if h else 0
    surf = np.full((h, w), np.nan, dtype=np.float32)
    for y, row in enumerate(path):
        for x, pt in enumerate(row):
            surf[y, x] = pt[2]
    if target_shape:
        f0 = target_shape[0] / max(1, surf.shape[0])
        f1 = target_shape[1] / max(1, surf.shape[1])
        surf = zoom(surf, (f0, f1), order=1)
    return surf


def _detect_conflicts(surfaces: Dict[str, np.ndarray]) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []

    def cmp(a: str, b: str) -> None:
        if a in surfaces and b in surfaces:
            diff = surfaces[a] - surfaces[b]
            idx = np.argwhere(diff < 0)
            for y, x in idx:
                out.append({"x": float(x), "y": float(y), "violator": a, "target": b, "depth_diff": float(diff[y, x])})

    cmp("coarse", "medium")
    cmp("coarse", "fine")
    cmp("medium", "fine")
    return out


def _load_cfgs_and_image(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    job_config_path: Optional[Path],
) -> Tuple[dict, dict, np.ndarray, float, str, dict]:
    with open(config_path, "r") as f:
        cfg_passes = yaml.safe_load(f)
    job_cfg_path = Path(job_config_path) if job_config_path else Path("config/job_config.yaml")
    job_cfg = load_job_config(job_cfg_path)
    heightmap, scale_xy = load_heightmap(str(image_path), job_config_path=job_cfg_path, scale_xy=0.1, scale_z=1.0)
    basename = Path(image_path).stem
    enabled = get_enabled_algorithms(job_cfg)
    return cfg_passes, job_cfg, heightmap, scale_xy, basename, enabled


def _apply_margin(heightmap: np.ndarray, scale_xy: float, margin_mm: float) -> np.ndarray:
    if margin_mm <= 0:
        return heightmap
    mpx = int(margin_mm / scale_xy)
    return heightmap[mpx : -mpx if mpx else None, mpx : -mpx if mpx else None]


def _prepare_norm_map(heightmap: np.ndarray, job_cfg: dict) -> np.ndarray:
    n = _normalize(
        heightmap,
        job_cfg.get("normalize_percentiles", None),
        float(job_cfg.get("gamma", 1.0)),
    )
    return _apply_zero_threshold(
        n,
        job_cfg.get("zero_threshold", None),
        job_cfg.get("zero_threshold_percentile", None),
    )


def _depth_map_mm(norm_map: np.ndarray, job_cfg: dict, pass_cfg: dict) -> Tuple[np.ndarray, float]:
    relief_cfg = job_cfg.get("desired_relief_height_mm", None)
    z_scale = float(pass_cfg.get("z_scale", 2.0))
    relief_mm = float(relief_cfg) if relief_cfg is not None else z_scale
    floor_mm = float(job_cfg.get("relief_floor_mm", 0.0))
    zmap_mm = floor_mm + norm_map * relief_mm
    zmap_mm = _smooth_mm(
        zmap_mm,
        str(job_cfg.get("z_smooth_method", "auto")),
        relief_mm,
        float(job_cfg.get("z_smooth_base_relief_mm", 3.0)),
        float(job_cfg.get("z_smooth_base_sigma", 1.0)),
        {
            "d": float(job_cfg.get("bilateral_d", 5)),
            "sigma_color": float(job_cfg.get("bilateral_sigma_color", 0.5)),
            "sigma_space": float(job_cfg.get("bilateral_sigma_space", 5.0)),
        },
    )
    zmin, zmax = float(zmap_mm.min()), float(zmap_mm.max())
    if not np.isfinite(zmin) or not np.isfinite(zmax) or zmin == zmax:
        raise ValueError(f"bad depth map: zmin={zmin}, zmax={zmax}")
    return zmap_mm, relief_mm


def _build_path(
    zmap_mm: np.ndarray,
    pass_cfg: dict,
    enabled: dict,
    scale_xy: float,
    border_margin: float,
    slope_map: Optional[np.ndarray],
) -> list:
    path = generate_raster_xyz_path(
        zmap_mm,
        scale_xy=scale_xy,
        stepover=float(pass_cfg["stepover"]),
        direction="zigzag-x",
        z_clamp=pass_cfg.get("z_clamp", None),
        slope_map=slope_map,
        adaptive=enabled.get("adaptive_stepover", True),
        offset_x=border_margin,
        offset_y=border_margin,
        z_smooth_kernel=int(pass_cfg.get("z_smooth_kernel", 3)),
    )
    zb = float(pass_cfg.get("z_buffer", 0.0))
    if zb > 0.0:
        for row in path:
            for i, (x, y, z) in enumerate(row):
                row[i] = (x, y, z + zb)
    return path


def _emit_gcode_for_pass(
    name: str,
    path: list,
    heightmap: np.ndarray,
    scale_xy: float,
    job_cfg: dict,
    feed: float,
    units: str,
    border_margin: float,
    safe_height: float,
    enabled: dict,
) -> list:
    gcode: List[str] = []
    gcode.append("G21" if units == "mm" else "G20")
    gcode.append("G90 ; Absolute positioning")
    gcode.append(f"G0 Z{safe_height:.3f}")

    if name == "coarse" and bool(job_cfg.get("add_border", False)):
        h_px, w_px = heightmap.shape
        w_mm = w_px * scale_xy + 2 * border_margin
        h_mm = h_px * scale_xy + 2 * border_margin
        z_vals_tmp = [pt[2] for r in path for pt in r]
        border_depth = min(z_vals_tmp) if z_vals_tmp else 0.0
        border_path = generate_border_path(w_mm, h_mm, border_depth, margin=border_margin)
        border_g = emit_gcode_from_path(border_path, feed, safe_height, 5.0, units, [], [])
        gcode.extend(border_g)

    main_g = emit_gcode_from_path(
        path, feed, safe_height, 5.0 if enabled.get("ramp", True) else 0.0, units, [], []
    )
    gcode.extend(main_g)
    return gcode


def _optimize_and_report(
    name: str,
    path: list,
    gcode: list,
    feed: float,
    reporter: PassReporter,
    output_dir: Path,
    basename: str,
    enabled: dict,
) -> Tuple[list, np.ndarray]:
    if enabled.get("colinear", True):
        path, _ = reduce_colinear_path(path)
    if enabled.get("dedupe", True):
        path, _ = deduplicate_path(path)

    pts = sum(len(r) for r in path)
    zvals = [pt[2] for r in path for pt in r]
    runtime = estimate_cut_time(gcode, feed)
    reporter.add_pass_report(name, pts, min(zvals), max(zvals), runtime, 0, 0, [])

    outfile = output_dir / f"{basename}_{name}.nc"
    write_gcode(gcode, outfile)
    print(f"[✓] Wrote {outfile}")

    surface = _surface_from_path(path)
    return path, surface


def _finalize_validation(paths: Dict[str, list], surfaces: Dict[str, np.ndarray], output_dir: Path) -> None:
    if len(surfaces) < 2:
        return
    target = surfaces["fine"].shape if "fine" in surfaces else list(surfaces.values())[-1].shape
    resized = {k: _surface_from_path(paths[k], target) for k in surfaces}
    violations = _detect_conflicts(resized)
    report_path = output_dir / "validation_report.json"
    with open(report_path, "w") as f:
        json.dump(
            {"status": "pass" if not violations else "fail", "violation_count": len(violations), "violations": violations},
            f,
            indent=2,
        )
    if violations:
        print(f"[❌] Toolpath validation failed with {len(violations)} violations.")
        print(f"     See {report_path.name} for details.")
    else:
        print("[✅] Toolpath validation passed.")


def generate_all_passes(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    pass_names: Optional[Sequence[str]] = None,
    margin_mm: float = 0.0,
    job_config_path: Optional[Path] = None,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg_passes, job_cfg, heightmap, scale_xy, basename, enabled = _load_cfgs_and_image(
        image_path, config_path, output_dir, job_config_path
    )

    border_margin = float(job_cfg.get("border_margin", 2.0))
    safe_height = float(job_cfg.get("safe_height", 5.0))
    default_feed = float(job_cfg.get("default_feedrate", 300))
    units = str(job_cfg.get("units", "mm"))

    heightmap = _apply_margin(heightmap, scale_xy, margin_mm)
    norm_map = _prepare_norm_map(heightmap, job_cfg)
    slope_map = compute_slope_map(heightmap, scale_xy) if enabled.get("adaptive_stepover", True) else None

    role_order = ["coarse", "medium", "fine"]
    if pass_names is None:
        pass_names = [p for p in role_order if p in cfg_passes]

    reporter = PassReporter(basename, output_dir)
    paths: Dict[str, list] = {}
    surfaces: Dict[str, np.ndarray] = {}

    for name in pass_names:
        p = cfg_passes[name]
        feed = float(p.get("max_feedrate", default_feed))

        zmap_mm, _relief_mm = _depth_map_mm(norm_map, job_cfg, p)
        path = _build_path(zmap_mm, p, enabled, scale_xy, border_margin, slope_map)
        gcode = _emit_gcode_for_pass(
            name, path, heightmap, scale_xy, job_cfg, feed, units, border_margin, safe_height, enabled
        )
        path, surface = _optimize_and_report(name, path, gcode, feed, reporter, output_dir, basename, enabled)

        paths[name] = path
        surfaces[name] = surface

    reporter.print_summary()
    reporter.write_json()
    _finalize_validation(paths, surfaces, output_dir)