import os
from pathlib import Path
import numpy as np
import yaml

from cam_generator.core.loader import load_heightmap
from cam_generator.core.job_loader import load_job_config
from cam_generator.core.gcode_writer import write_gcode
from path_builders.raster import generate_raster_xyz_path
from gcode.emit_gcode import emit_gcode_from_path
from optimizers.reduce_colinear import reduce_colinear_path
from optimizers.prune_redundant import deduplicate_path
from analysis.curvature import compute_slope_map
from cam_generator.core.pass_reporter import PassReporter
from cam_generator.core.time_estimator import estimate_cut_time
from cam_generator.core.toggles import get_enabled_algorithms

def generate_all_passes(
    image_path,
    config_path,
    output_dir,
    pass_names=None,
    margin_mm=0.0,
    job_config_path="config/job_config.yaml"
):
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load configs
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    job_config = load_job_config(job_config_path)
    enabled = get_enabled_algorithms(job_config)
    border_margin = job_config.get("border_margin", 2.0)

    safe_height = job_config.get("safe_height", 5.0)
    feedrate = job_config.get("default_feedrate", 300)
    units = job_config.get("units", "mm")

    basename = image_path.stem
    heightmap, scale_xy = load_heightmap(str(image_path), scale_xy=0.1, scale_z=1.0)

    # Margin crop
    if margin_mm > 0:
        margin_px = int(margin_mm / scale_xy)
        heightmap = heightmap[
            margin_px : -margin_px if margin_px else None,
            margin_px : -margin_px if margin_px else None,
        ]

    # Compute slope map if needed
    slope_map = compute_slope_map(heightmap, scale_xy) if enabled["adaptive_stepover"] else None

    if pass_names is None:
        pass_names = ["coarse", "medium", "fine"]

    reporter = PassReporter(basename, output_dir)
    final_z_min = None

    for pass_name in pass_names:
        pass_cfg = config[pass_name]
        z_scale = pass_cfg.get("z_scale", 2.0)
        tool_dia = pass_cfg["tool_diameter"]
        stepover = pass_cfg["stepover"]

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
            offset_y=border_margin
        )

        # Apply z_buffer if defined for this pass (e.g., coarse)
        z_buffer = pass_cfg.get("z_buffer", 0.0)
        if z_buffer > 0:
            for row in path:
                for i, (x, y, z) in enumerate(row):
                    row[i] = (x, y, z + z_buffer)


        header_path = Path("config/header.gcode")
        footer_path = Path("config/footer.gcode")
        header_lines = header_path.read_text().splitlines() if header_path.exists() else []
        footer_lines = footer_path.read_text().splitlines() if footer_path.exists() else []

        gcode = list(header_lines or [])
        gcode.append("G21" if units == "mm" else "G20")
        gcode.append("G90 ; Absolute positioning")
        gcode.append(f"G0 Z{safe_height:.3f}")

        if pass_name == "coarse" and job_config.get("add_border", False):
            print("[+] Adding border to coarse pass...")
            from path_builders.border import generate_border_path

            height_px, width_px = heightmap.shape
            width_mm = width_px * scale_xy + 2 * border_margin
            height_mm = height_px * scale_xy + 2 * border_margin

            z_vals = [pt[2] for row in path for pt in row]
            border_depth = min(z_vals)

            border_path = generate_border_path(width_mm, height_mm, border_depth, margin=border_margin)

            border_gcode = emit_gcode_from_path(
                border_path,
                feedrate=feedrate,
                safe_height=safe_height,
                ramp_distance=5.0 if enabled["ramp"] else 0.0,
                units=units,
                header_lines=[],
                footer_lines=[]
            )
            gcode.extend(border_gcode)

        main_gcode = emit_gcode_from_path(
            path,
            feedrate=feedrate,
            safe_height=safe_height,
            ramp_distance=5.0 if enabled["ramp"] else 0.0,
            units=units,
            header_lines=[],
            footer_lines=[]
        )
        gcode.extend(main_gcode)
        gcode.extend(footer_lines or [])

        removed = 0
        if enabled["colinear"]:
            path, removed = reduce_colinear_path(path)

        deduped = 0
        if enabled["dedupe"]:
            path, deduped = deduplicate_path(path)

        point_count = sum(len(row) for row in path)
        z_vals = [pt[2] for row in path for pt in row]
        z_min = min(z_vals)
        z_max = max(z_vals)
        runtime = estimate_cut_time(gcode, feedrate)
        final_z_min = z_min

        algos = []
        if enabled["colinear"] and removed > 0:
            algos.append("colinear")
        if enabled["dedupe"] and deduped > 0:
            algos.append("dedupe")
        if enabled["ramp"]:
            algos.append("ramp")
        if enabled["adaptive_stepover"]:
            algos.append("adaptive_stepover")

        reporter.add_pass_report(
            pass_name,
            point_count=point_count,
            z_min=z_min,
            z_max=z_max,
            time_min=runtime,
            removed_colinear=removed,
            removed_deduped=deduped,
            algorithms=algos
        )

        outfile = output_dir / f"{basename}_{pass_name}.nc"
        write_gcode(gcode, outfile)
        print(f"[✓] Wrote {outfile}")

    reporter.print_summary()
    reporter.write_json()
