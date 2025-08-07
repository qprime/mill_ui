# path: pipelines/cam_generator/runner.py
# type: CAM pipeline runner
# tags: cam, pipeline, CNC, toolpath, G-code
# owner: cliff
# depends_on: multi_pass.py, preview.py, time_estimator.py
# description: Orchestrates the execution of CAM pipeline steps for CNC G-code generation.

import argparse
from pathlib import Path
import shutil

from pipelines.cam_generator.core.multi_pass import generate_all_passes
from pipelines.cam_generator.core.preview import preview_toolpath
from pipelines.cam_generator.core.time_estimator import estimate_cut_time

def run_cam_pipeline(job_name, base_dir=None, enable_preview=True, verbose=True):
    """
    Run CAM toolpath + G-code pipeline for a single job.

    Args:
        job_name (str): Name of the job folder in memoriescam_projects/
        base_dir (Path or str): CLIFF-AI project root (default: auto-detect from cwd)
        enable_preview (bool): Whether to generate PNG previews for G-code
        verbose (bool): Print status and file paths
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent  # .../cliff_ai/
    else:
        base_dir = Path(base_dir).resolve()

    mem_root = base_dir / "memory" / "cam_projects"
    project_folder = mem_root / job_name

    image_path = project_folder / "input" / "image.png"
    config_path = project_folder / "config" / "default_passes.yaml"
    job_config_path = project_folder / "config" / "job_config.yaml"
    output_folder = project_folder / "cam_output"

    # Checks
    for p, label in [
        (image_path, "input image"),
        (config_path, "default_passes.yaml"),
        (job_config_path, "job_config.yaml"),
    ]:
        if not p.exists():
            raise FileNotFoundError(f"[!] Required {label} not found: {p}")

    # Clean/create output folder
    if output_folder.exists():
        shutil.rmtree(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Copy configs to output for traceability
    shutil.copy(config_path, output_folder / "default_passes.yaml")
    shutil.copy(job_config_path, output_folder / "job_config.yaml")

    if verbose:
        print(f"[+] Input image: {image_path}")
        print(f"[+] Configs: {config_path}, {job_config_path}")
        print(f"[+] Output folder: {output_folder}")

    generate_all_passes(
        image_path=image_path,
        config_path=output_folder / "default_passes.yaml",
        output_dir=output_folder,
        margin_mm=3.0,
        job_config_path=output_folder / "job_config.yaml",  # or wherever you copied it
    )


    if enable_preview:
        for gcode_file in output_folder.glob("*.nc"):
            with open(gcode_file) as f:
                lines = f.read().splitlines()
            preview_toolpath(
                lines,
                z_fade=True,
                show=False,
                save_path=f"{gcode_file.with_suffix('.png')}",
            )
            minutes = estimate_cut_time(lines)
            if verbose:
                print(f"{gcode_file.name}: {minutes:.1f} min")

# --- CLI Entrypoint ---

def main():
    parser = argparse.ArgumentParser(
        description="Generate CNC toolpaths and G-code for a CLIFF-AI CAM job."
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Job/project name (matches subfolder in memoriescam_projects/)",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip PNG preview generation.",
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
        enable_preview=not args.no_preview,
        verbose=not args.quiet,
    )

if __name__ == "__main__":
    main()
