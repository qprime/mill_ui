import os
from pathlib import Path
from cam_generator.core.loader import load_heightmap
from cam_generator.core.toolpath import generate_raster_toolpath
from cam_generator.core.gcode_writer import write_gcode
from cam_generator.core.job_loader import load_job_config
import yaml

def generate_all_passes(image_path, config_path, output_dir, pass_names=None, margin_mm=0.0, job_config_path="config/job_config.yaml"):
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    job_config = load_job_config(job_config_path)
    safe_height = job_config.get("safe_height", 5.0)
    feedrate = job_config.get("default_feedrate", 300)
    units = job_config.get("units", "mm")

    basename = image_path.stem
    heightmap, scale_xy = load_heightmap(str(image_path), scale_xy=0.1, scale_z=1.0)

    if margin_mm > 0:
        margin_px = int(margin_mm / scale_xy)
        heightmap = heightmap[
            margin_px : -margin_px if margin_px else None,
            margin_px : -margin_px if margin_px else None,
        ]

    if pass_names is None:
        pass_names = ["coarse", "medium", "fine"]

    for pass_name in pass_names:
        pass_cfg = config[pass_name]
        z_scale = pass_cfg.get("z_scale", 2.0)
        tool_dia = pass_cfg["tool_diameter"]
        stepover = pass_cfg["stepover"]

        scaled_map = heightmap * (z_scale / heightmap.max())

        gcode = generate_raster_toolpath(
            scaled_map,
            scale_xy=scale_xy,
            tool_diameter=tool_dia,
            stepover=stepover,
            direction="zigzag-x",
            z_clamp=pass_cfg.get("z_clamp", None),
            z_safe=safe_height,
            feedrate=feedrate,
            units=units
        )

        outfile = output_dir / f"{basename}_{pass_name}.nc"
        write_gcode(gcode, outfile)
        print(f"[✓] Wrote {outfile}")
