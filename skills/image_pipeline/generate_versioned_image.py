# path: skills/image_pipeline/generate_versioned_image.py
# type: image generation wrapper
# tags: generate, image, versioning, pipeline
# owner: cliff
# depends_on: skills.image_pipeline.generate_image, skills.image_pipeline.versioning
# description: Invokes the existing image generator then versions the output and updates image.json pointer.

from __future__ import annotations

import sys
from pathlib import Path

from skills.image_pipeline.generate_image import generate_dalle_image
from skills.image_pipeline.versioning import version_latest_image


def generate_and_version(project_folder: str) -> int:
    base_dir = Path("memories/cam_projects") / project_folder / "input"
    json_path = base_dir / "image.json"
    png_path = base_dir / "image.png"

    # Run the existing generator (will print its own errors)
    generate_dalle_image(project_folder)

    # If the generator didn't create an image, fail clearly
    if not json_path.exists():
        print(f"[!] Missing input config after generation: {json_path}")
        return 1
    if not png_path.exists():
        print(f"[!] Image service unavailable or generation failed (no {png_path})")
        return 2

    try:
        versioned = version_latest_image(base_dir)
        print(f"[✓] Versioned image: {versioned}")
        return 0
    except Exception as exc:
        print(f"[!] Post-process failed: {exc}")
        return 3


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m skills.image_pipeline.generate_versioned_image <project_folder>")
        sys.exit(1)
    sys.exit(generate_and_version(sys.argv[1]))

