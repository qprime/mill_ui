from __future__ import annotations

import json
from pathlib import Path

from skills.image_pipeline.versioning import version_latest_image


def test_version_latest_image(tmp_path: Path):
    input_dir = tmp_path / "memories" / "cam_projects" / "proj" / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "image.json").write_text(
        json.dumps({
            "subject": "test",
            "persona": "mira",
            "style": "flat_plane",
            "size": "1024x1024",
            "metadata": {},
        }, indent=2),
        encoding="utf-8",
    )
    data = b"\x89PNG\r\n\x1a\n" + b"x" * 10
    (input_dir / "image.png").write_bytes(data)

    versioned = version_latest_image(input_dir)
    assert versioned.exists()
    assert versioned.name.startswith("image-") and versioned.suffix == ".png"
    # image.png restored
    assert (input_dir / "image.png").read_bytes() == data
    cfg = json.loads((input_dir / "image.json").read_text(encoding="utf-8"))
    assert cfg.get("image") == "image.png"

