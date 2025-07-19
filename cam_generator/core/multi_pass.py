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

    # Load pass config + job-level config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    job_config = load_job_config(job_config_path)

    safe_height = job_config.get("safe_height", 5.0)
    feedrate = job_config.get("default_feedrate", 300)
    units = job_config.get("units", "mm")

    basename = image_path.stem
    heightmap, scale_xy = load_heightmap(str(image_path), scale_xy=0.1, scale_z=1.0)

    # Apply margin crop
    if margin_mm > 0:
        margin_px = int(margin_mm / scale_xy)
        heightmap = heightmap[
            margin_px : -margin_px if margin_px else None,
            margin_px : -margin_px if margin_px else None,
        ]

    # Compute slope map for adaptive stepover
    slope_map = compute_slope_map(heightmap, scale_xy)

    if pass_names is None:
        pass_names = ["coarse", "medium", "fine"]

    for pass_name in pass_names:
        pass_cfg = config[pass_name]
        z_scale = pass_cfg.get("z_scale", 2.0)
        tool_dia = pass_cfg["tool_diameter"]
        stepover = pass_cfg["stepover"]

        # Z-scaling
        scaled_map = heightmap * (z_scale / heightmap.max())

        # Raster path
        path = generate_raster_xyz_path(
            scaled_map,
            scale_xy=scale_xy,
            stepover=stepover,
            direction="zigzag-x",
            z_clamp=pass_cfg.get("z_clamp", None),
            slope_map=slope_map,
            adaptive=True
        )


        # Optional headers/footers
        header_path = Path("config/header.gcode")
        footer_path = Path("config/footer.gcode")
        header_lines = header_path.read_text().splitlines() if header_path.exists() else []
        footer_lines = footer_path.read_text().splitlines() if footer_path.exists() else []

        # Emit G-code
        gcode = emit_gcode_from_path(
            path,
            feedrate=feedrate,
            safe_height=safe_height,
            ramp_distance=5.0,
            units=units,
            header_lines=header_lines,
            footer_lines=footer_lines
        )

        # Optimize
        path, removed = reduce_colinear_path(path)
        print(f"    [•] Removed {removed} colinear points from {pass_name} pass")

        path, deduped = deduplicate_path(path)
        print(f"    [•] Removed {deduped} duplicate points from {pass_name} pass")

        # Write output
        outfile = output_dir / f"{basename}_{pass_name}.nc"
        write_gcode(gcode, outfile)
        print(f"[✓] Wrote {outfile}")
