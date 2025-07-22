import os
from pathlib import Path
from datetime import datetime
from cam_generator.core.multi_pass import generate_all_passes
from cam_generator.core.preview import preview_toolpath
from cam_generator.core.time_estimator import estimate_cut_time

# === User Parameters ===
job_name = "Dragon1"  # must match folder in ../cliff_ai/memory/images/
ENABLE_PREVIEW = True

# === Paths ===
image_root = Path("/home/squinlan/cliff_ai/memory/images")
output_root = Path("output")

# === Step 1: Resolve input image path ===
image_folder = image_root / job_name
image_path = image_folder / "image.png"
if not image_path.exists():
    raise FileNotFoundError(f"Expected image not found at: {image_path}")

# === Step 2: Create numbered output folder ===
existing = sorted(output_root.glob(f"*_{job_name}"))
next_index = len(existing)
output_folder = output_root / f"{next_index:02d}_{job_name}"
output_folder.mkdir(parents=True, exist_ok=False)

print(f"[+] Output will be saved to: {output_folder}")

# === Step 3: Run generation ===
generate_all_passes(
    image_path=image_path,
    config_path="config/default_passes.yaml",
    output_dir=output_folder,
    margin_mm=3.0
)

# === Step 4: Preview (optional) ===
if ENABLE_PREVIEW:
    for gcode_file in output_folder.glob("*.nc"):
        with open(gcode_file) as f:
            lines = f.read().splitlines()
        preview_toolpath(lines, z_fade=True, show=False, save_path=f"{gcode_file.with_suffix('.png')}")
        minutes = estimate_cut_time(lines)
        print(f"{gcode_file.name}: {minutes:.1f} min")
