# path: pipelines/cam_generator/core/multi_pass.py
# type: CAM processing
# tags: cam, generator, multi-pass, gcode, path-optimization
# owner: cliff
# depends_on: loader.py, job_loader.py, gcode_writer.py, raster.py, emit_gcode.py, reduce_colinear.py, prune_redundant.py, curvature.py, pass_reporter.py, time_estimator.py, toggles.py
# description: Orchestrates multi-pass CAM path generation, G-code writing, and validation.

import os
from pathlib import Path
import numpy as np
import yaml
import json
from scipy.ndimage import zoom

from pipelines.cam_generator.core.loader import load_heightmap
from pipelines.cam_generator.core.job_loader import load_job_config
from pipelines.cam_generator.core.gcode_writer import write_gcode
from pipelines.cam_generator.path_builders.raster import generate_raster_xyz_path
from pipelines.cam_generator.gcode.emit_gcode import emit_gcode_from_path
from pipelines.cam_generator.optimizers.reduce_colinear import reduce_colinear_path
from pipelines.cam_generator.optimizers.prune_redundant import deduplicate_path
from pipelines.cam_generator.analysis.curvature import compute_slope_map
from pipelines.cam_generator.core.pass_reporter import PassReporter
from pipelines.cam_generator.core.time_estimator import estimate_cut_time
from pipelines.cam_generator.core.toggles import get_enabled_algorithms


def generate_surface_map(path, target_shape=None):
    height = len(path)
    width = max(len(row) for row in path)
    surface = np.full((height, width), np.nan, dtype=np.float32)
    for y, row in enumerate(path):
        for x, pt in enumerate(row):
            surface[y, x] = pt[2]
    if target_shape:
        zoom_factors = (
            target_shape[0] / surface.shape[0],
            target_shape[1] / surface.shape[1],
        )
        surface = zoom(surface, zoom_factors, order=1)
    return surface


def detect_pass_conflicts(surfaces):
    violations = []

    def compare(upper_name, lower_name):
        upper = surfaces[upper_name]
        lower = surfaces[lower_name]
        diff = upper - lower
        mask = diff < 0
        indices = np.argwhere(mask)
        for y, x in indices:
            violations.append(
                {
                    "x": int(x),
                    "y": int(y),
                    "violator": upper_name,
                    "target": lower_name,
                    "depth_diff": float(diff[y, x]),
                }
            )

    if "coarse" in surfaces and "medium" in surfaces:
        compare("coarse", "medium")
    if "coarse" in surfaces and "fine" in surfaces:
        compare("coarse", "fine")
    if "medium" in surfaces and "fine" in surfaces:
        compare("medium", "fine")
    return violations


def generate_all_passes(
    image_path,
    config_path,
    output_dir,
    pass_names=None,
    margin_mm=0.0,
    job_config_path=None,   # <-- now defaults to None, must be explicitly passed!
):
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # Use job_config_path provided, or fallback to default (legacy support)
    if job_config_path is None:
        job_config_path = "config/job_config.yaml"
    job_config = load_job_config(job_config_path)
    enabled = get_enabled_algorithms(job_config)
    border_margin = job_config.get("border_margin", 2.0)
    safe_height = job_config.get("safe_height", 5.0)
    default_feedrate = job_config.get("default_feedrate", 300)
    units = job_config.get("units", "mm")
    basename = image_path.stem
    # --- Pass job_config_path to load_heightmap!
    heightmap, scale_xy = load_heightmap(
        str(image_path),
        job_config_path=job_config_path,
        scale_xy=0.1,
        scale_z=1.0,
    )
    if margin_mm > 0:
        margin_px = int(margin_mm / scale_xy)
        heightmap = heightmap[
            margin_px : -margin_px if margin_px else None,
            margin_px : -margin_px if margin_px else None,
        ]
    slope_map = (
        compute_slope_map(heightmap, scale_xy) if enabled["adaptive_stepover"] else None
    )
    pass_roles = ["coarse", "medium", "fine"]
    if pass_names is None:
        pass_names = [p for p in pass_roles if p in config]
    reporter = PassReporter(basename, output_dir)
    paths = {}
    surface_maps = {}
    for pass_name in pass_names:
        pass_cfg = config[pass_name]
        z_scale = pass_cfg.get("z_scale", 2.0)
        tool_dia = pass_cfg["tool_diameter"]
        stepover = pass_cfg["stepover"]
        pass_feedrate = pass_cfg.get("max_feedrate", default_feedrate)
        scaled_map = heightmap * (z_scale / heightmap.max())
        path = generate_raster_xyz_path(
            scaled_map,
            scale_xy=scale_xy,
            stepover=stepover,
            direction="zigzag-x",
            z_clamp=pass_cfg.get("z_clamp", None),
            slope_map=slope_map,
            adaptive=enabled["adaptive_stepover"],
            offset_x=border_margin,
            offset_y=border_margin,
            z_smooth_kernel=pass_cfg.get("z_smooth_kernel", 3),
        )
        z_buffer = pass_cfg.get("z_buffer", 0.0)
        if z_buffer > 0:
            for row in path:
                for i, (x, y, z) in enumerate(row):
                    row[i] = (x, y, z + z_buffer)
        gcode = []
        gcode.append("G21" if units == "mm" else "G20")
        gcode.append("G90 ; Absolute positioning")
        gcode.append(f"G0 Z{safe_height :.3f}")
        if pass_name == "coarse" and job_config.get("add_border", False):
            from pipelines.cam_generator.path_builders.border import generate_border_path
            height_px, width_px = heightmap.shape
            width_mm = width_px * scale_xy + 2 * border_margin
            height_mm = height_px * scale_xy + 2 * border_margin
            z_vals = [pt[2] for row in path for pt in row]
            border_depth = min(z_vals)
            border_path = generate_border_path(
                width_mm, height_mm, border_depth, margin=border_margin
            )
            border_gcode = emit_gcode_from_path(
                border_path, pass_feedrate, safe_height, 5.0, units, [], []
            )
            gcode.extend(border_gcode)
        main_gcode = emit_gcode_from_path(
            path,
            pass_feedrate,
            safe_height,
            5.0 if enabled["ramp"] else 0.0,
            units,
            [],
            [],
        )
        gcode.extend(main_gcode)
        if enabled["colinear"]:
            path, removed = reduce_colinear_path(path)
        if enabled["dedupe"]:
            path, deduped = deduplicate_path(path)
        point_count = sum(len(row) for row in path)
        z_vals = [pt[2] for row in path for pt in row]
        runtime = estimate_cut_time(gcode, pass_feedrate)
        reporter.add_pass_report(
            pass_name, point_count, min(z_vals), max(z_vals), runtime, 0, 0, []
        )
        outfile = output_dir / f"{basename}_{pass_name}.nc"
        write_gcode(gcode, outfile)
        print(f"[✓] Wrote {outfile}")
        paths[pass_name] = path
        surface_maps[pass_name] = generate_surface_map(path)
    reporter.print_summary()
    reporter.write_json()
    if len(surface_maps) >= 2:
        print("[🔍] Validating toolpath passes...")
        target_shape = (
            surface_maps["fine"].shape
            if "fine" in surface_maps
            else list(surface_maps.values())[-1].shape
        )
        resized = {
            name: generate_surface_map(paths[name], target_shape)
            for name in surface_maps
        }
        violations = detect_pass_conflicts(resized)
        validation_path = output_dir / "validation_report.json"
        with open(validation_path, "w") as f:
            json.dump(
                {
                    "status": "pass" if not violations else "fail",
                    "violation_count": len(violations),
                    "violations": violations,
                },
                f,
                indent=2,
            )
        if violations:
            print(
                f"[❌] Toolpath validation failed with {len(violations)} violations."
            )
            print(f"     See {validation_path.name} for details.")
        else:
            print("[✅] Toolpath validation passed.")
