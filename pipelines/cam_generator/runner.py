import os
from pathlib import Path
from datetime import datetime
import shutil

from cam_generator.core.multi_pass import generate_all_passes
from cam_generator.core.preview import preview_toolpath
from cam_generator.core.time_estimator import estimate_cut_time

# === User Parameters ===
job_name = "Flamingo6"  # Folder name inside image_root
ENABLE_PREVIEW = True

# === Paths ===
image_root = Path("/home/squinlan/cliff_ai/memory/cam_projects")
output_root = Path("output")

# === Resolve project paths ===
project_folder = image_root / job_name
image_path = project_folder / "input" / "image.png"
config_path = project_folder / "config" / "default_passes.yaml"
job_config_path = project_folder / "config" / "job_config.yaml"

if not image_path.exists():
    raise FileNotFoundError(f"[!] image.png not found at {image_path}")
if not config_path.exists():
    raise FileNotFoundError(f"[!] default_passes.yaml not found at {config_path}")
if not job_config_path.exists():
    raise FileNotFoundError(f"[!] job_config.yaml not found at {job_config_path}")

# === Create next available output folder ===
existing = sorted(output_root.glob(f"*_{job_name}"))
next_index = len(existing)
output_folder = output_root / f"{next_index:02d}_{job_name}"
output_folder.mkdir(parents=True, exist_ok=False)

print(f"[+] Output folder: {output_folder}")

# === Save config snapshot for reproducibility ===
shutil.copy(config_path, output_folder / "default_passes.yaml")
shutil.copy(job_config_path, output_folder / "job_config.yaml")

# === Run CAM pass generation ===
generate_all_passes(
    image_path=image_path,
    config_path=output_folder / "default_passes.yaml",  # use the snapshot
    output_dir=output_folder,
    margin_mm=3.0,
    job_config_path=output_folder / "job_config.yaml"   # use the snapshot
)

# === Optional preview and timing summary ===
if ENABLE_PREVIEW:
    for gcode_file in output_folder.glob("*.nc"):
        with open(gcode_file) as f:
            lines = f.read().splitlines()
        preview_toolpath(lines, z_fade=True, show=False, save_path=f"{gcode_file.with_suffix('.png')}")
        minutes = estimate_cut_time(lines)
        print(f"{gcode_file.name}: {minutes:.1f} min")
