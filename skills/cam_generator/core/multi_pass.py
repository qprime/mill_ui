# path: skills/cam_generator/core/multi_pass.py
# # desc: Main pipeline: load, build passes, emit gcode, report.
# api: generate_all_passes
# tags: cam

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import json
import numpy as np
from scipy.ndimage import gaussian_filter, zoom, distance_transform_edt

from skills.cam_generator.analysis.curvature import compute_slope_map
from skills.cam_generator.core.gcode_writer import write_gcode
from skills.cam_generator.core.loader import load_heightmap
from skills.cam_generator.core.pass_reporter import PassReporter
from skills.cam_generator.core.settings import load_settings
from skills.cam_generator.core.time_estimator import estimate_cut_time
from skills.cam_generator.core.toggles import get_enabled_algorithms
from skills.cam_generator.gcode.emit_gcode import emit_gcode_from_path
from skills.cam_generator.optimizers.prune_redundant import deduplicate_path
from skills.cam_generator.optimizers.reduce_colinear import reduce_colinear_path
from skills.cam_generator.path_builders.border import generate_border_path
from skills.cam_generator.path_builders.raster import generate_raster_xyz_path

def _fail(where: str, err: Exception) -> None:
    raise RuntimeError(f"{where} error: {type(err).__name__}: {err}") from err

def _ensure(cond: bool, where: str, msg: str) -> None:
    if not cond:
        raise RuntimeError(f"{where} failed: {msg}")

def _normalize(heightmap: np.ndarray, percentiles: Optional[Sequence[float]], gamma: float) -> np.ndarray:
    try:
        h = heightmap
        _ensure(isinstance(h, np.ndarray) and h.size > 0, "_normalize", "empty heightmap")
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
    except Exception as e:
        _fail("_normalize", e)

def _apply_zero_threshold(n: np.ndarray, thresh: Optional[float], thresh_pct: Optional[float]) -> np.ndarray:
    try:
        if thresh_pct is not None:
            t = float(np.percentile(n, float(thresh_pct)))
            return np.clip((n - t) / max(1e-6, 1.0 - t), 0.0, 1.0)
        if thresh is not None:
            t = float(thresh)
            return np.clip((n - t) / max(1e-6, 1.0 - t), 0.0, 1.0)
        return n
    except Exception as e:
        _fail("_apply_zero_threshold", e)

def _smooth_mm(
    zmap_mm: np.ndarray,
    method: str,
    relief_mm: float,
    base_relief: float,
    base_sigma: float,
    bilateral: Mapping[str, float],
) -> np.ndarray:
    try:
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
    except Exception as e:
        _fail("_smooth_mm", e)

def _surface_from_path(
    path: List[List[Tuple[float, float, float]]],
    target_shape: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    try:
        h = len(path)
        _ensure(h > 0, "_surface_from_path", "empty path")
        w = max(len(r) for r in path) if h else 0
        _ensure(w > 0, "_surface_from_path", "empty rows in path")
        surf = np.full((h, w), np.nan, dtype=np.float32)
        for y, row in enumerate(path):
            for x, pt in enumerate(row):
                surf[y, x] = pt[2]
        if target_shape:
            f0 = target_shape[0] / max(1, surf.shape[0])
            f1 = target_shape[1] / max(1, surf.shape[1])
            surf = zoom(surf, (f0, f1), order=1)
        return surf
    except Exception as e:
        _fail("_surface_from_path", e)

def _detect_conflicts(surfaces: Dict[str, np.ndarray]) -> List[Dict[str, float]]:
    try:
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
    except Exception as e:
        _fail("_detect_conflicts", e)

def _load_cfgs_and_image(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    job_config_path: Optional[Path],
) -> Tuple[dict, dict, np.ndarray, float, str, dict]:
    try:
        job_root = Path(job_config_path).parent.parent if job_config_path else Path(output_dir).parent
        s = load_settings(job_root)
        heightmap, scale_xy = load_heightmap(str(image_path), job_config_path=s.paths["job_path"], scale_xy=0.1, scale_z=1.0)
        _ensure(isinstance(heightmap, np.ndarray) and heightmap.size > 0, "_load_cfgs_and_image", "empty heightmap")
        basename = Path(image_path).stem
        enabled = get_enabled_algorithms(s.job)
        _ensure(isinstance(s.passes, dict) and len(s.passes) > 0, "_load_cfgs_and_image", "no passes found in settings")
        return s.passes, s.job, heightmap, scale_xy, basename, enabled
    except Exception as e:
        _fail("_load_cfgs_and_image", e)

def _apply_margin(heightmap: np.ndarray, scale_xy: float, margin_mm: float) -> np.ndarray:
    try:
        if margin_mm <= 0:
            return heightmap
        mpx = int(margin_mm / scale_xy)
        if mpx <= 0:
            return heightmap
        h0, w0 = heightmap.shape
        _ensure(h0 > 2 * mpx and w0 > 2 * mpx, "_apply_margin", "margin exceeds image bounds")
        return heightmap[mpx:-mpx, mpx:-mpx]
    except Exception as e:
        _fail("_apply_margin", e)

def _prepare_norm_map(heightmap: np.ndarray, job_cfg: dict) -> np.ndarray:
    try:
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
    except Exception as e:
        _fail("_prepare_norm_map", e)

def _depth_map_mm(norm_map: np.ndarray, job_cfg: dict, pass_cfg: dict) -> Tuple[np.ndarray, float]:
    try:
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
        _ensure(np.isfinite(zmin) and np.isfinite(zmax) and zmin != zmax, "_depth_map_mm", f"bad depth map zmin={zmin}, zmax={zmax}")
        return zmap_mm, relief_mm
    except Exception as e:
        _fail("_depth_map_mm", e)

def layerize_path_by_stepdown(
    path: List[List[Tuple[float, float, float]]],
    z_stepdown: float,
    min_last_layer: float = 0.0,
    insert_blank_between_layers: bool = True,
    tol: float = 1e-6,
) -> List[List[Tuple[float, float, float]]]:
    if not path or z_stepdown <= 0:
        return path

    z_min = min(pt[2] for r in path for pt in r)
    if z_min >= 0.0:
        return path

    limits: List[float] = []
    d = -float(z_stepdown)
    while d > z_min:
        limits.append(d)
        d -= float(z_stepdown)
    if not limits or limits[-1] > z_min:
        limits.append(z_min)
    if min_last_layer > 0 and len(limits) >= 1:
        last_delta = limits[-1] - z_min
        if last_delta > min_last_layer:
            limits.insert(len(limits)-1, z_min + min_last_layer)

    layered: List[List[Tuple[float, float, float]]] = []
    prev_limit: float | None = None

    for L in limits:
        layer_had_work = False

        for row in path:
            row_L   = [(x, y, max(z, L)) for (x, y, z) in row]
            if prev_limit is None:
                if row_L:
                    layered.append(row_L)
                    layer_had_work = True
                continue

            row_prev = [(x, y, max(z, prev_limit)) for (x, y, z) in row]

            seg: List[Tuple[float, float, float]] = []
            in_seg = False
            for (pL, pP) in zip(row_L, row_prev):
                changed = (pL[2] < pP[2] - tol)
                if changed:
                    if not in_seg:
                        seg = [pL]
                        in_seg = True
                    else:
                        seg.append(pL)
                else:
                    if in_seg:
                        if seg:
                            layered.append(seg)
                            layer_had_work = True
                        seg = []
                        in_seg = False
            if in_seg and seg:
                layered.append(seg)
                layer_had_work = True

        if insert_blank_between_layers and layer_had_work:
            layered.append([])

        prev_limit = L

    if layered and not layered[-1]:
        layered.pop()

    return layered

def _build_path(
    zmap_mm: np.ndarray,
    pass_cfg: dict,
    enabled: dict,
    scale_xy: float,
    border_margin: float,
    slope_map: Optional[np.ndarray],
    skip_mask: Optional[np.ndarray] = None,
) -> List[List[Tuple[float, float, float]]]:
    try:
        def _gen(mask):
            return generate_raster_xyz_path(
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
                skip_mask=mask,
            )

        path = _gen(skip_mask)

        if not isinstance(path, list) or len(path) == 0:
            path = _gen(None)

        _ensure(isinstance(path, list) and len(path) > 0, "_build_path", "empty path")

        zb = float(pass_cfg.get("z_buffer", 0.0))
        if zb > 0.0:
            for row in path:
                for i, (x, y, z) in enumerate(row):
                    row[i] = (x, y, z + zb)

        z_stepdown = float(pass_cfg.get("z_stepdown", 0.0) or 0.0)
        min_last = float(pass_cfg.get("min_last_layer", 0.0) or 0.0)
        if z_stepdown > 0.0:
            insert_blanks = bool(pass_cfg.get("layer_full_retract", True))
            path = layerize_path_by_stepdown(
                path,
                z_stepdown=z_stepdown,
                min_last_layer=min_last,
                insert_blank_between_layers=insert_blanks,
            )
            _ensure(isinstance(path, list) and len(path) > 0, "_build_path", "empty layered path")

        return path
    except Exception as e:
        _fail("_build_path", e)

def _compute_diameter_keepout_mask(
    fine_zmap_mm: np.ndarray,
    coarse_limit_mm: float,
    scale_xy_mm: float,
    tool_diam_mm: float,
    xy_clear_mm: float = 0.5,
) -> np.ndarray:
    deeper = fine_zmap_mm > (float(coarse_limit_mm) + 1e-6)

    if not deeper.any() or not (~deeper).any():
        return np.zeros_like(deeper, dtype=bool)

    dist_in_mm  = distance_transform_edt(deeper)   * float(scale_xy_mm)
    dist_out_mm = distance_transform_edt(~deeper)  * float(scale_xy_mm)
    dist_to_boundary_mm = np.minimum(dist_in_mm, dist_out_mm)

    keepout_radius_mm = float(tool_diam_mm) * 0.5 + float(xy_clear_mm)

    skip = dist_to_boundary_mm < keepout_radius_mm
    return skip

def _path_lengths_mm(path: List[List[Tuple[float, float, float]]]) -> Tuple[float, float]:
    xy = 0.0
    zz = 0.0
    for row in path:
        if not row: continue
        prev = row[0]
        for pt in row[1:]:
            dx = pt[0] - prev[0]
            dy = pt[1] - prev[1]
            dz = pt[2] - prev[2]
            xy += (dx*dx + dy*dy) ** 0.5
            zz += abs(dz)
            prev = pt
    return xy, zz

def _emit_gcode_for_pass(
    name: str,
    path: List[List[Tuple[float, float, float]]],
    heightmap: np.ndarray,
    scale_xy: float,
    job_cfg: dict,
    feed: float,
    units: str,
    border_margin: float,
    safe_height: float,
    enabled: dict,
    ramp_distance: Optional[float] = None,
) -> List[str]:
    try:
        gcode: List[str] = []
        gcode.append("G21" if units == "mm" else "G20")
        gcode.append("G90")
        gcode.append(f"G0 Z{safe_height:.3f}")

        if ramp_distance is None:
            ramp_distance = 5.0 if enabled.get("ramp", True) else 0.0

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
            path, feed, safe_height, float(ramp_distance), units, [], []
        )
        gcode.extend(main_g)
        _ensure(len(gcode) > 3, "_emit_gcode_for_pass", "no toolpath emitted")
        return gcode
    except Exception as e:
        _fail("_emit_gcode_for_pass", e)

def _optimize_and_report(
    name: str,
    path: List[List[Tuple[float, float, float]]],
    gcode: List[str],
    feed: float,
    reporter: PassReporter,
    output_dir: Path,
    basename: str,
    enabled: dict,
) -> Tuple[List[List[Tuple[float, float, float]]], np.ndarray]:
    try:
        if enabled.get("colinear", True):
            path, _ = reduce_colinear_path(path)
        if enabled.get("dedupe", True):
            path, _ = deduplicate_path(path)

        pts = sum(len(r) for r in path)
        _ensure(pts > 0, "_optimize_and_report", "zero points after optimize")
        zvals = [pt[2] for r in path for pt in r]
        runtime = estimate_cut_time(gcode)  # estimator now robust/auto-units
        xy_mm, z_mm = _path_lengths_mm(path)
        reporter.add_pass_report(name, pts, min(zvals), max(zvals), runtime, 0, 0, [], xy_km=xy_mm/1000.0, z_km=z_mm/1000.0)

        outfile = output_dir / f"{basename}_{name}.nc"
        write_gcode(gcode, outfile)
        print(f"[pass:{name}] wrote {outfile}")
        surface = _surface_from_path(path)
        return path, surface
    except Exception as e:
        _fail("_optimize_and_report", e)

def _finalize_validation(paths: Dict[str, List[List[Tuple[float, float, float]]]], surfaces: Dict[str, np.ndarray], output_dir: Path) -> None:
    try:
        if len(surfaces) < 2:
            print("[validation] skipped (need >=2 surfaces)")
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
            print(f"[validation] FAIL: {len(violations)} violations → {report_path.name}")
        else:
            print("[validation] PASS")
    except Exception as e:
        _fail("_finalize_validation", e)

def generate_all_passes(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    pass_names: Optional[Sequence[str]] = None,
    margin_mm: float = 0.0,
    job_config_path: Optional[Path] = None,
) -> None:
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        print("[stage] init output dir")
    except Exception as e:
        _fail("generate_all_passes:init_output_dir", e)

    try:
        cfg_passes, job_cfg, heightmap, scale_xy, basename, enabled = _load_cfgs_and_image(
            image_path, config_path, output_dir, job_config_path
        )
        print("[stage] loaded settings + heightmap")
    except Exception as e:
        _fail("generate_all_passes:load_cfgs_and_image", e)

    try:
        border_margin = float(job_cfg.get("border_margin", 2.0))
        safe_height = float(job_cfg.get("safe_height", 5.0))
        default_feed = float(job_cfg.get("default_feedrate", 300))
        units = str(job_cfg.get("units", "mm"))
        print(f"[cfg] units={units} safe_z={safe_height} border={border_margin} feed={default_feed}")
    except Exception as e:
        _fail("generate_all_passes:parse_job_cfg", e)

    try:
        heightmap = _apply_margin(heightmap, scale_xy, margin_mm)
        norm_map = _prepare_norm_map(heightmap, job_cfg)
        slope_map = compute_slope_map(heightmap, scale_xy) if enabled.get("adaptive_stepover", True) else None
        print("[stage] preprocessed maps")
    except Exception as e:
        _fail("generate_all_passes:preprocess", e)

    role_order = ["coarse", "medium", "fine"]
    try:
        if pass_names is None:
            pass_names = [p for p in role_order if p in cfg_passes]
        _ensure(isinstance(pass_names, Sequence) and len(pass_names) > 0, "generate_all_passes:select_passes", "no passes selected")
        print(f"[stage] selected passes: {list(pass_names)}")
    except Exception as e:
        _fail("generate_all_passes:select_passes", e)

    reporter = PassReporter(basename, output_dir)
    paths: Dict[str, List[List[Tuple[float, float, float]]]] = {}
    surfaces: Dict[str, np.ndarray] = {}

    for name in pass_names:
        try:
            p = cfg_passes[name]
            feed = float(p.get("max_feedrate", default_feed))

            zmap_mm, _relief_mm = _depth_map_mm(norm_map, job_cfg, p)

            skip_mask = None
            if name == "coarse" and ("fine" in cfg_passes) and bool(p.get("diameter_keepout", True)):
                fine_zmap_mm, _ = _depth_map_mm(norm_map, job_cfg, cfg_passes["fine"])

                zc = p.get("z_clamp", [-1e-6, 0.0])
                if isinstance(zc, (list, tuple)) and len(zc) == 2:
                    coarse_min_z = float(zc[0]) + float(p.get("z_buffer", 0.0))
                elif isinstance(zc, dict) and "min" in zc:
                    coarse_min_z = float(zc["min"]) + float(p.get("z_buffer", 0.0))
                else:
                    coarse_min_z = 0.0 + float(p.get("z_buffer", 0.0))

                coarse_height_limit = -coarse_min_z

                skip_mask = _compute_diameter_keepout_mask(
                    fine_zmap_mm=fine_zmap_mm,
                    coarse_limit_mm=coarse_height_limit,
                    scale_xy_mm=scale_xy,
                    tool_diam_mm=float(p.get("tool_diameter", 6.35)),
                    xy_clear_mm=float(p.get("xy_clearance", 0.5)),
                )

            path = _build_path(zmap_mm, p, enabled, scale_xy, border_margin, slope_map, skip_mask=skip_mask)

            ramp_dist = float(p.get("ramp_distance", 5.0 if enabled.get("ramp", True) else 0.0))

            gcode = _emit_gcode_for_pass(
                name, path, heightmap, scale_xy, job_cfg, feed, units,
                border_margin, safe_height, enabled, ramp_distance=ramp_dist
            )
            _ensure(len(gcode) > 0, f"generate_all_passes:emit_gcode:{name}", "empty gcode")
            path, surface = _optimize_and_report(name, path, gcode, feed, reporter, output_dir, basename, enabled)
            paths[name] = path
            surfaces[name] = surface
            print(f"[stage] pass done: {name}")
        except Exception as e:
            _fail(f"generate_all_passes:pass:{name}", e)

    try:
        reporter.print_summary()
        reporter.write_json()
        _finalize_validation(paths, surfaces, output_dir)
        print("[stage] reporting + validation complete")
    except Exception as e:
        _fail("generate_all_passes:reporting", e)
