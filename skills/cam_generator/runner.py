# path: skills/cam_generator/runner.py
# # desc: CLI entry wrapper for multi-pass CAM pipeline.
# api: run_cam_pipeline
# tags: cam

import argparse
from pathlib import Path
import shutil

from skills.cam_generator.pipeline import generate_passes
from skills.cam_generator.time_estimator import estimate_cut_time

def run_cam_pipeline(job_name, base_dir=None, verbose=True):
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
    else:
        base_dir = Path(base_dir).resolve()

    mem_root = base_dir / "memories" / "cam_projects"
    project_folder = mem_root / job_name

    image_path = project_folder / "input" / "image.png"
    config_path = project_folder / "config" / "default_passes.yaml"
    job_config_path = project_folder / "config" / "job_config.yaml"
    output_folder = project_folder / "cam_output"

    for p, label in [
        (image_path, "input image"),
        (config_path, "default_passes.yaml"),
        (job_config_path, "job_config.yaml"),
    ]:
        if not p.exists():
            raise FileNotFoundError(f"[!] Required {label} not found: {p}")

    if output_folder.exists():
        shutil.rmtree(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    shutil.copy(config_path, output_folder / "default_passes.yaml")
    shutil.copy(job_config_path, output_folder / "job_config.yaml")

    if verbose:
        print(f"[+] Input image: {image_path}")
        print(f"[+] Configs: {config_path}, {job_config_path}")
        print(f"[+] Output folder: {output_folder}")

    generate_passes(
        image_path=image_path,
        config_path=output_folder / "default_passes.yaml",
        output_dir=output_folder,
        margin_mm=3.0,
        job_config_path=output_folder / "job_config.yaml",
    )

    for gcode_file in output_folder.glob("*.nc"):
        with open(gcode_file) as f:
            lines = f.read().splitlines()
        minutes = estimate_cut_time(lines)
        if verbose:
            print(f"{gcode_file.name}: {minutes:.1f} min")

def main():
    parser = argparse.ArgumentParser(
        description="Generate CNC toolpaths and G-code for a CLIFF-AI CAM job."
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Job/project name (matches subfolder in memories/cam_projects/)",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Override CLIFF-AI project root (default: parent of this script)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output.",
    )
    args = parser.parse_args()

    run_cam_pipeline(
        job_name=args.job,
        base_dir=args.base_dir,
        verbose=not args.quiet,
    )

if __name__ == "__main__":
    main()
