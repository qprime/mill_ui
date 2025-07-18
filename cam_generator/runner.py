
from pathlib import Path

from cam_generator.core.multi_pass import generate_all_passes
from cam_generator.core.preview import preview_toolpath
from cam_generator.core.time_estimator import estimate_cut_time

ENABLE_PREVIEW=True
def main():
    generate_all_passes(
        image_path="olive_tree_v1.jpg",
        config_path="config/default_passes.yaml",
        output_dir=".",
        margin_mm=3.0  # ← Add this for a 3mm uniform margin
    )
    if ENABLE_PREVIEW:
        from cam_generator.core.preview import preview_toolpath
        for gcode_file in Path(".").glob("olive_tree_v1_*.nc"):
            with open(gcode_file) as f:
                lines = f.read().splitlines()
            preview_toolpath(lines, z_fade=True, show=False, save_path=f"{gcode_file.stem}.png")
            minutes = estimate_cut_time(lines)
            print(f"{gcode_file.name}: {minutes:.1f} min")


if __name__ == "__main__":
    main()
