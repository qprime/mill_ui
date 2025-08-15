# path: skills/cam_generator/core/pipeline.py
# # desc: Main pipeline: load, build passes, emit gcode, report. (refactored w/ Pipeline state)
# api: generate_all_passes
# tags: cam

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import json
import numpy as np
from scipy.ndimage import distance_transform_edt

# existing absolute imports kept intact
from skills.cam_generator.curvature import compute_slope_map
from skills.cam_generator.gcode_writer import write_gcode
from skills.cam_generator.loader import load_heightmap
from skills.cam_generator.pass_reporter import PassReporter
from skills.cam_generator.settings import load_settings
from skills.cam_generator.time_estimator import estimate_cut_time
from skills.cam_generator.toggles import get_enabled_algorithms
from skills.cam_generator.emit_gcode import emit_gcode_from_path
from skills.cam_generator.prune_redundant import deduplicate_path
from skills.cam_generator.reduce_colinear import reduce_colinear_path
from skills.cam_generator.border import generate_border_path
from skills.cam_generator.raster import generate_raster_xyz_path

# new small, flat modules (add the files we discussed in the same folder)
from skills.cam_generator.math_ops import normalize, applyZeroThreshold, smoothMM
from skills.cam_generator.path_ops import surfaceFromPath, layerizePathByStepdown, pathLengthsMM
from skills.cam_generator.validation import detectConflicts

PathPoint = Tuple[float, float, float]
PathRow   = List[PathPoint]
Toolpath  = List[PathRow]

# ------- small error helpers (unchanged semantics) -------

def _fail(where: str, err: Exception) -> None:
    raise RuntimeError(f"{where} error: {type(err).__name__}: {err}") from err

def _ensure(cond: bool, where: str, msg: str) -> None:
    if not cond:
        raise RuntimeError(f"{where} failed: {msg}")


# ------- Pipeline state holder -------


@dataclass
class Pipeline:
    # immutable inputs/settings
    image_path: Path
    config_path: Path
    output_dir: Path
    job_config_path: Optional[Path]
    passes_cfg: Mapping[str, Mapping]
    job_cfg: Mapping
    enabled: Mapping[str, bool]

    # run params (lifted once from job_cfg)
    border_margin: float
    safe_height: float
    default_feed: float
    units: str
    scale_xy: float
    basename: str

    # maps
    heightmap: np.ndarray
    norm_map: np.ndarray
    slope_map: Optional[np.ndarray] = None

    # per-pass artifacts
    paths_by_name: Dict[str, List[List[Tuple[float, float, float]]]] = field(default_factory=dict)
    surfaces_by_name: Dict[str, np.ndarray] = field(default_factory=dict)

    # NEW: z-map cache to avoid recomputation (e.g., coarse needing fine)
    zmap_mm_by_name: Dict[str, np.ndarray] = field(default_factory=dict)


# ------- tightly-coupled helpers that should remain local to the pipeline -------

def _load_cfgs_and_image(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    job_config_path: Optional[Path],
) -> Tuple[dict, dict, np.ndarray, float, str, dict]:
    try:
        job_root = Path(job_config_path).parent.parent if job_config_path else Path(output_dir).parent
        s = load_settings(job_root)
        heightmap, scale_xy = load_heightmap(
            str(image_path),
            job_config_path=s.paths["job_path"],
            scale_xy=0.1,
            scale_z=1.0,
        )
        _ensure(isinstance(heightmap, np.ndarray) and heightmap.size > 0, "_load_cfgs_and_image", "empty heightmap")
        basename = Path(image_path).stem
        enabled = get_enabled_algorithms(s.job)
        _ensure(isinstance(s.passes, dict) and len(s.passes) > 0, "_load_cfgs_and_image", "no passes found in settings")
        return s.passes, s.job, heightmap, float(scale_xy), basename, enabled
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

def _prepare_norm_map(heightmap: np.ndarray, job_cfg: Mapping) -> np.ndarray:
    try:
        n = normalize(
            heightmap,
            job_cfg.get("normalize_percentiles", None),
            float(job_cfg.get("gamma", 1.0)),
        )
        return applyZeroThreshold(
            n,
            job_cfg.get("zero_threshold", None),
            job_cfg.get("zero_threshold_percentile", None),
        )
    except Exception as e:
        _fail("_prepare_norm_map", e)

def _depth_map_mm(norm_map: np.ndarray, job_cfg: Mapping, pass_cfg: Mapping) -> Tuple[np.ndarray, float]:
    try:
        relief_cfg = job_cfg.get("desired_relief_height_mm", None)
        z_scale = float(pass_cfg.get("z_scale", 2.0))
        relief_mm = float(relief_cfg) if relief_cfg is not None else z_scale
        floor_mm = float(job_cfg.get("relief_floor_mm", 0.0))

        zmap_mm = floor_mm + norm_map * relief_mm
        zmap_mm = smoothMM(
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
        # enforce dtype
        zmap_mm = zmap_mm.astype("float32", copy=False)

        zmin, zmax = float(np.nanmin(zmap_mm)), float(np.nanmax(zmap_mm))
        _ensure(np.isfinite(zmin) and np.isfinite(zmax) and zmin != zmax, "_depth_map_mm", f"bad depth map zmin={zmin}, zmax={zmax}")
        return zmap_mm, relief_mm
    except Exception as e:
        _fail("_depth_map_mm", e)

def _build_path(
    zmap_mm: np.ndarray,
    pass_cfg: Mapping,
    enabled: Mapping[str, bool],
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
            path = layerizePathByStepdown(
                path,
                z_stepdown=z_stepdown,
                min_last_layer=min_last,
                insert_blank_between_layers=insert_blanks,
            )
            _ensure(isinstance(path, list) and len(path) > 0, "_build_path", "empty layered path")

        # NEW: hard guard against “flat” Z (common regression class)
        z_vals = [pt[2] for r in path for pt in r]
        _ensure(len(z_vals) > 0, "_build_path", "no points in toolpath")
        if len(z_vals) > 1:
            z_min = min(z_vals); z_max = max(z_vals)
            _ensure(abs(z_max - z_min) > 1e-6, "_build_path", "flat Z path (no variation)")

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

def _emit_gcode_for_pass(
    name: str,
    path: List[List[Tuple[float, float, float]]],
    heightmap: np.ndarray,
    scale_xy: float,
    job_cfg: Mapping,
    feed: float,
    units: str,
    border_margin: float,
    safe_height: float,
    enabled: Mapping[str, bool],
    ramp_distance: Optional[float] = None,
) -> List[str]:
    try:
        gcode: List[str] = []
        gcode.append("G21" if units == "mm" else "G20")
        gcode.append("G90")
        gcode.append(f"G0 Z{safe_height:.3f}")

        # ramp_distance already canonicalized upstream; default only if missing
        if ramp_distance is None:
            ramp_distance = 5.0 if enabled.get("ramp", True) else 0.0

        # NEW: centralized border emission (defaults to single-pass; supports multi-pass if configured)
        border_g = _emit_border_gcode_from_jobcfg(
            pass_name=name,
            path=path,
            heightmap=heightmap,
            scale_xy=scale_xy,
            border_margin=border_margin,
            safe_height=safe_height,
            units=units,
            feed=feed,
            job_cfg=job_cfg,
        )
        if border_g:
            gcode.extend(border_g)

        # Main path emission (unchanged)
        main_g = emit_gcode_from_path(path, feed, safe_height, float(ramp_distance), units, [], [])
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
    enabled: Mapping[str, bool],
) -> Tuple[List[List[Tuple[float, float, float]]], np.ndarray]:
    try:
        if enabled.get("colinear", True):
            path, _ = reduce_colinear_path(path)
        if enabled.get("dedupe", True):
            path, _ = deduplicate_path(path)

        pts = sum(len(r) for r in path)
        _ensure(pts > 0, "_optimize_and_report", "zero points after optimize")
        zvals = [pt[2] for r in path for pt in r]
        runtime = estimate_cut_time(gcode)
        xy_mm, z_mm = pathLengthsMM(path)
        reporter.add_pass_report(name, pts, min(zvals), max(zvals), runtime, 0, 0, [], xy_km=xy_mm/1000.0, z_km=z_mm/1000.0)

        outfile = output_dir / f"{basename}_{name}.nc"
        write_gcode(gcode, outfile)
        print(f"[pass:{name}] wrote {outfile}")
        surface = surfaceFromPath(path)
        return path, surface
    except Exception as e:
        _fail("_optimize_and_report", e)

def _finalize_validation(paths: Dict[str, List[List[Tuple[float, float, float]]]], surfaces: Dict[str, np.ndarray], output_dir: Path) -> None:
    try:
        if len(surfaces) < 2:
            print("[validation] skipped (need >=2 surfaces)")
            return
        target = surfaces["fine"].shape if "fine" in surfaces else list(surfaces.values())[-1].shape
        resized = {k: surfaceFromPath(paths[k], target) for k in surfaces}
        violations = detectConflicts(resized)
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

def _canonicalize_passes(
    passes_cfg: Mapping[str, Mapping],
    default_feed: float,
    enabled: Mapping[str, bool],
) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for name, p in passes_cfg.items():
        spec = dict(p)  # copy, keep unknown keys intact

        if "stepover" not in spec:
            _ensure(False, "_canonicalize_passes", f"pass '{name}' missing 'stepover'")
        spec["stepover"] = float(spec["stepover"])
        _ensure(spec["stepover"] > 0.0, "_canonicalize_passes", f"pass '{name}' stepover <= 0")

        # numeric fields with the same defaults used elsewhere in the pipeline
        spec["z_buffer"]        = float(p.get("z_buffer", 0.0))
        spec["z_stepdown"]      = float(p.get("z_stepdown", 0.0))
        spec["min_last_layer"]  = float(p.get("min_last_layer", 0.0))
        spec["tool_diameter"]   = float(p.get("tool_diameter", 6.35))
        spec["xy_clearance"]    = float(p.get("xy_clearance", 0.5))
        spec["max_feedrate"]    = float(p.get("max_feedrate", default_feed))
        spec["z_scale"]         = float(p.get("z_scale", 2.0))

        # ints
        spec["z_smooth_kernel"] = int(p.get("z_smooth_kernel", 3))
        if spec["z_smooth_kernel"] < 1:
            spec["z_smooth_kernel"] = 1

        # bools
        spec["layer_full_retract"] = bool(p.get("layer_full_retract", True))
        spec["diameter_keepout"]   = bool(p.get("diameter_keepout", True))

        # ramp default depends on global 'ramp' toggle
        default_ramp = 5.0 if enabled.get("ramp", True) else 0.0
        spec["ramp_distance"] = float(p.get("ramp_distance", default_ramp))

        # leave z_clamp shape as-is (list/tuple/dict) for downstream compatibility
        out[name] = spec
    return out

def _get_zmap_mm(pipeline: Pipeline, pass_name: str) -> Tuple[np.ndarray, float]:
    """
    Compute or reuse the Z-map (mm) for a given pass.
    Returns (zmap_mm, relief_mm). Caches zmap_mm in pipeline.zmap_mm_by_name.
    """
    if pass_name in pipeline.zmap_mm_by_name:
        # Relief is not cached; recompute lightweight relief_mm from config consistently
        p = pipeline.passes_cfg[pass_name]
        relief_cfg = pipeline.job_cfg.get("desired_relief_height_mm", None)
        z_scale = float(p.get("z_scale", 2.0))
        relief_mm = float(relief_cfg) if relief_cfg is not None else z_scale
        return pipeline.zmap_mm_by_name[pass_name], relief_mm

    p = pipeline.passes_cfg[pass_name]
    zmap_mm, relief_mm = _depth_map_mm(pipeline.norm_map, pipeline.job_cfg, p)
    pipeline.zmap_mm_by_name[pass_name] = zmap_mm
    return zmap_mm, relief_mm

def _select_passes(pipeline: Pipeline, pass_names: Optional[Sequence[str]]) -> List[str]:
    """
    Resolve pass execution order.
    Priority:
      1) Explicit pass_names argument (filtered to available)
      2) job_cfg['passes_order'] (string 'coarse,fine' or list)
      3) default role order: ['coarse','medium','fine']
      4) fallback: whatever passes are available (dict order)
    """
    available = list(pipeline.passes_cfg.keys())
    available_set = set(available)

    # 1) CLI / caller-provided list wins (filtered)
    if pass_names:
        seq = [str(n) for n in pass_names if str(n) in available_set]
        _ensure(len(seq) > 0, "_select_passes", "no valid passes from argument")
        return seq

    # 2) Config-provided order
    order = pipeline.job_cfg.get("passes_order", None)
    if order is not None:
        if isinstance(order, str):
            raw = [x.strip() for x in order.replace(";", ",").split(",") if x.strip()]
        elif isinstance(order, Sequence):
            raw = [str(x) for x in order]
        else:
            raw = []

        seq: List[str] = []
        seen = set()
        for name in raw:
            if name in available_set and name not in seen:
                seq.append(name)
                seen.add(name)
        if seq:
            return seq

    # 3) Default role order
    role_order = ["coarse", "medium", "fine"]
    seq = [n for n in role_order if n in available_set]
    if seq:
        return seq

    # 4) Last resort: whatever is defined
    _ensure(len(available) > 0, "_select_passes", "no passes available")
    return available

# Defaults used only if job_config omits them (keeps current behavior)
DEFAULTS = {
    "border_stepdown": 0.0,           # 0.0 => single-pass border (current behavior)
    "border_min_last_layer": 0.0,
    "border_layer_full_retract": True,
}

def _should_emit_border(job_cfg: Mapping, pass_name: str) -> bool:
    # Same rule as before: only on coarse, and only if add_border is true.
    return pass_name == "coarse" and bool(job_cfg.get("add_border", False))

def _emit_border_gcode_from_jobcfg(
    pass_name: str,
    path: List[List[Tuple[float, float, float]]],
    heightmap: np.ndarray,
    scale_xy: float,
    border_margin: float,
    safe_height: float,
    units: str,
    feed: float,
    job_cfg: Mapping,
) -> List[str]:
    """
    Builds border path and emits G-code.
    - Default: single-pass (backwards-compatible).
    - If job_config sets border_stepdown > 0, layerize the border like other paths.
    """
    if not _should_emit_border(job_cfg, pass_name):
        return []

    # Frame dims in mm, same as before
    h_px, w_px = heightmap.shape
    w_mm = w_px * scale_xy + 2 * border_margin
    h_mm = h_px * scale_xy + 2 * border_margin

    # Border depth: match the min Z used by the current pass path (unchanged behavior)
    z_vals_tmp = [pt[2] for r in path for pt in r]
    border_depth = min(z_vals_tmp) if z_vals_tmp else 0.0

    # Build the rectangular border path
    border_path = generate_border_path(w_mm, h_mm, border_depth, margin=border_margin)

    # Optional: multi-pass border controlled by job_config
    stepdown = float(job_cfg.get("border_stepdown", DEFAULTS["border_stepdown"]))
    if stepdown > 0.0:
        min_last   = float(job_cfg.get("border_min_last_layer", DEFAULTS["border_min_last_layer"]))
        full_retr  = bool(job_cfg.get("border_layer_full_retract", DEFAULTS["border_layer_full_retract"]))
        border_path = layerizePathByStepdown(
            border_path,
            z_stepdown=stepdown,
            min_last_layer=min_last,
            insert_blank_between_layers=full_retr,
        )

    # Keep the same ramp distance as original border emission (fixed 5.0)
    border_g = emit_gcode_from_path(border_path, feed, safe_height, 5.0, units, [], [])
    return border_g

def _print_pass_hints(
    name: str,
    pass_cfg: Mapping,
    zmap_mm: np.ndarray,
    path: List[List[Tuple[float, float, float]]],
    pipeline: "Pipeline",
) -> None:
    # Z dynamic ranges
    try:
        zmap_min = float(np.nanmin(zmap_mm))
        zmap_max = float(np.nanmax(zmap_mm))
        zmap_rng = zmap_max - zmap_min
    except Exception:
        zmap_rng = 0.0

    z_vals = [pt[2] for r in path for pt in r] if path else []
    path_rng = (max(z_vals) - min(z_vals)) if z_vals else 0.0

    tool_diam = float(pass_cfg.get("tool_diameter", 6.35))
    stepover  = float(pass_cfg.get("stepover", max(0.2, tool_diam * 0.1)))
    z_step    = float(pass_cfg.get("z_stepdown", 0.0))
    fine_like = (name.lower() == "fine")

    # 1) Flattening: path Z-range suspiciously small vs source range
    if fine_like:
        if zmap_rng > 0.3 and path_rng < max(0.10, 0.2 * zmap_rng):
            print(f"[hint:{name}] path Z range ({path_rng:.3f}mm) is low vs zmap ({zmap_rng:.3f}mm) → fine may look flat. "
                  f"Try: increase image relief, reduce coarse z_buffer, or loosen z_clamp on fine.")

    # 2) Banding risk: stepover too large for the tool
    if stepover > tool_diam * 0.25:
        print(f"[hint:{name}] stepover {stepover:.3f}mm > 25% of tool {tool_diam:.3f}mm → risk of visible scallops/lines. "
              f"Try stepover ≤ {tool_diam*0.15:.3f}mm.")

    # 3) Gouge/deflection risk: large stepdown on fine
    if fine_like and z_step > 0.8:
        print(f"[hint:{name}] z_stepdown {z_step:.2f}mm is large for fine detail → risk of chatter/gouges. Try 0.3–0.6mm.")

    # 4) Coarse/fine interplay using ACTUAL path depths (if both exist)
    if fine_like and "coarse" in pipeline.paths_by_name:
        try:
            cmin = min(pt[2] for r in pipeline.paths_by_name["coarse"] for pt in r) if pipeline.paths_by_name["coarse"] else 0.0
            fmin = min(z_vals) if z_vals else 0.0
            sep = abs(fmin - cmin)
            if sep < 0.15:
                print(f"[hint:{name}] coarse/fine depth separation only ~{sep:.2f}mm → fine may have little material to cut. "
                      f"Increase coarse z_buffer (e.g., 0.2–0.5mm).")
        except Exception:
            pass



################################

def prepare_pipeline(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    margin_mm: float = 0.0,
    job_config_path: Optional[Path] = None,
) -> Pipeline:
    # Stage 1: init output dir
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        print("[stage] init output dir")
    except Exception as e:
        _fail("prepare_pipeline:init_output_dir", e)

    # Stage 2: load settings + heightmap
    try:
        cfg_passes, job_cfg, heightmap, scale_xy, basename, enabled = _load_cfgs_and_image(
            image_path, config_path, output_dir, job_config_path
        )
        print("[stage] loaded settings + heightmap")
    except Exception as e:
        _fail("prepare_pipeline:load_cfgs_and_image", e)

    # Stage 3: parse job cfg
    try:
        border_margin = float(job_cfg.get("border_margin", 2.0))
        safe_height   = float(job_cfg.get("safe_height", 5.0))
        default_feed  = float(job_cfg.get("default_feedrate", 300))
        units         = str(job_cfg.get("units", "mm"))
        print(f"[cfg] units={units} safe_z={safe_height} border={border_margin} feed={default_feed}")
    except Exception as e:
        _fail("prepare_pipeline:parse_job_cfg", e)

    # Stage 4: preprocess maps (+ dtype/shape enforcement)
    try:
        # enforce 2-D float32 early
        _ensure(isinstance(heightmap, np.ndarray) and heightmap.size > 0, "prepare_pipeline:preprocess", "heightmap empty")
        _ensure(heightmap.ndim == 2, "prepare_pipeline:preprocess", f"heightmap ndim={heightmap.ndim}, expected 2")
        heightmap = heightmap.astype("float32", copy=False)

        heightmap = _apply_margin(heightmap, scale_xy, margin_mm)

        norm_map  = _prepare_norm_map(heightmap, job_cfg).astype("float32", copy=False)

        slope_map = compute_slope_map(heightmap, scale_xy) if enabled.get("adaptive_stepover", True) else None
        if slope_map is not None and isinstance(slope_map, np.ndarray):
            slope_map = slope_map.astype("float32", copy=False)

        print("[stage] preprocessed maps")
    except Exception as e:
        _fail("prepare_pipeline:preprocess", e)

    # Stage 4.5 — canonicalize pass specs once
    try:
        cfg_passes = _canonicalize_passes(cfg_passes, default_feed, enabled)
    except Exception as e:
        _fail("prepare_pipeline:canonicalize_passes", e)

    return Pipeline(
        image_path=image_path,
        config_path=config_path,
        output_dir=output_dir,
        job_config_path=job_config_path,
        passes_cfg=cfg_passes,
        job_cfg=job_cfg,
        enabled=enabled,
        border_margin=border_margin,
        safe_height=safe_height,
        default_feed=default_feed,
        units=units,
        scale_xy=scale_xy,
        basename=basename,
        heightmap=heightmap,
        norm_map=norm_map,
        slope_map=slope_map,
    )



def generate_pass(pipeline: Pipeline, name: str, reporter: PassReporter) -> Tuple[List[List[Tuple[float,float,float]]], np.ndarray]:
    try:
        p = pipeline.passes_cfg[name]
        feed = float(p.get("max_feedrate", pipeline.default_feed))

        # Use cache-or-compute for this pass
        zmap_mm, _relief_mm = _get_zmap_mm(pipeline, name)
        zmin_map = float(np.nanmin(zmap_mm)); zmax_map = float(np.nanmax(zmap_mm))
        print(f"[debug:{name}] zmap_mm range: {zmin_map:.3f}..{zmax_map:.3f} mm")

        # Coarse keep-out may need fine's z-map; reuse via cache to avoid recompute
        skip_mask = None
        if name == "coarse" and ("fine" in pipeline.passes_cfg) and bool(p.get("diameter_keepout", True)):
            fine_zmap_mm, _ = _get_zmap_mm(pipeline, "fine")

            zc = p.get("z_clamp", [-1e-6, 0.0])
            if isinstance(zc, (list, tuple)) and len(zc) == 2:
                coarse_min_z = float(zc[0]) + float(p.get("z_buffer", 0.0))
            elif isinstance(zc, dict) and "min" in zc:
                coarse_min_z = float(zc["min"]) + float(p.get("z_buffer", 0.0))
            else:
                # if no clamp provided, assume near-surface limit (common config)
                coarse_min_z = 0.0 + float(p.get("z_buffer", 0.0))

            coarse_height_limit = -coarse_min_z

            skip_mask = _compute_diameter_keepout_mask(
                fine_zmap_mm=fine_zmap_mm,
                coarse_limit_mm=coarse_height_limit,
                scale_xy_mm=pipeline.scale_xy,
                tool_diam_mm=float(p.get("tool_diameter", 6.35)),
                xy_clear_mm=float(p.get("xy_clearance", 0.5)),
            )

            # NEW: guard degenerate keep-out (all or none masked)
            if isinstance(skip_mask, np.ndarray) and skip_mask.size:
                cover = float(skip_mask.mean())
                pct = cover * 100.0
                if cover >= 0.95 or cover <= 0.01:
                    print(f"[debug:{name}] keepout masked: {pct:.1f}% → disabling keepout (degenerate)")
                    skip_mask = None
                else:
                    print(f"[debug:{name}] keepout masked: {pct:.1f}% of area")

        path = _build_path(
            zmap_mm,
            p,
            pipeline.enabled,
            pipeline.scale_xy,
            pipeline.border_margin,
            pipeline.slope_map,
            skip_mask=skip_mask,
        )

        # Canonicalized ramp distance
        ramp_dist = float(p.get("ramp_distance"))

        gcode = _emit_gcode_for_pass(
            name,
            path,
            pipeline.heightmap,
            pipeline.scale_xy,
            pipeline.job_cfg,
            feed,
            pipeline.units,
            pipeline.border_margin,
            pipeline.safe_height,
            pipeline.enabled,
            ramp_distance=ramp_dist,
        )
        _ensure(len(gcode) > 0, f"generate_pass:emit_gcode:{name}", "empty gcode")

        # quick path stats before optimize/report writes files
        zvals = [pt[2] for r in path for pt in r]
        if zvals:
            print(f"[debug:{name}] path Z range: {min(zvals):.3f}..{max(zvals):.3f} mm  | pts={sum(len(r) for r in path)}  stepover={p['stepover']}  z_stepdown={p.get('z_stepdown',0)}")

        # Hints
        _print_pass_hints(name, p, zmap_mm, path, pipeline)

        path, surface = _optimize_and_report(
            name,
            path,
            gcode,
            feed,
            reporter,
            pipeline.output_dir,
            pipeline.basename,
            pipeline.enabled,
        )

        pipeline.paths_by_name[name] = path
        pipeline.surfaces_by_name[name] = surface
        print(f"[stage] pass done: {name}")
        return path, surface
    except Exception as e:
        _fail(f"generate_pass:{name}", e)





# ------- public API -------

def generate_passes(
    image_path: Path,
    config_path: Path,
    output_dir: Path,
    pass_names: Optional[Sequence[str]] = None,
    margin_mm: float = 0.0,
    job_config_path: Optional[Path] = None,
) -> None:
    """
    Orchestrator: build Pipeline, choose pass order, run each pass, then report/validate.
    Keeps previous logging format.
    """
    pipeline = prepare_pipeline(
        image_path=image_path,
        config_path=config_path,
        output_dir=output_dir,
        margin_mm=margin_mm,
        job_config_path=job_config_path,
    )

    # Resolve pass execution order (no dependency on _select_passes)
    available = list(pipeline.passes_cfg.keys())
    aset = set(available)

    if pass_names:
        selected = [str(n) for n in pass_names if str(n) in aset]
        if not selected:
            _fail("generate_passes:select_passes", "no valid passes from argument")
    else:
        order = pipeline.job_cfg.get("passes_order", None)
        if isinstance(order, str):
            raw = [x.strip() for x in order.replace(";", ",").split(",") if x.strip()]
        elif isinstance(order, Sequence):
            raw = [str(x) for x in order]
        else:
            raw = []

        selected = []
        seen = set()
        for n in raw:
            if n in aset and n not in seen:
                selected.append(n); seen.add(n)

        if not selected:
            role_order = ["coarse", "medium", "fine"]
            selected = [n for n in role_order if n in aset] or available

    print(f"[stage] selected passes: {list(selected)}")

    reporter = PassReporter(pipeline.basename, pipeline.output_dir)

    for name in selected:
        generate_pass(pipeline, name, reporter)

    try:
        reporter.print_summary()
        reporter.write_json()
        _finalize_validation(pipeline.paths_by_name, pipeline.surfaces_by_name, pipeline.output_dir)
        print("[stage] reporting + validation complete")
    except Exception as e:
        _fail("generate_passes:reporting", e)


# Back-compat: anything still importing the old name will continue to work
generate_all_passes = generate_passes
