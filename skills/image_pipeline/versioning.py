# path: skills/image_pipeline/versioning.py
# type: image postprocess
# tags: image, versioning, pipeline
# owner: cliff
# depends_on: json, shutil, pathlib, datetime
# description: Helpers to version the latest generated image and update image.json pointer.

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


def version_latest_image(input_dir: Path) -> Path:
    """Rename image.png to a timestamped variant, copy it back to image.png,
    and update image.json to point to "image.png".

    Returns the versioned image path.
    Raises FileNotFoundError if required files are missing.
    """
    input_dir = Path(input_dir)
    latest = input_dir / "image.png"
    cfg_path = input_dir / "image.json"

    if not latest.exists():
        raise FileNotFoundError(f"Missing latest image: {latest}")
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config: {cfg_path}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    versioned = input_dir / f"image-{ts}.png"

    latest.rename(versioned)
    shutil.copy2(versioned, latest)

    with cfg_path.open("r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["image"] = "image.png"
    tmp = cfg_path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    tmp.replace(cfg_path)

    return versioned

