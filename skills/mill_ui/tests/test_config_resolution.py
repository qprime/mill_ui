from __future__ import annotations

import json
from pathlib import Path

from skills.mill_ui.core import load_config


def test_load_config_precedence(tmp_path) -> None:
    config_json = {
        "safe_z_mm": 4.0,
        "material_name": "PLY",
        "tolerances": {
            "merge_epsilon_mm": 0.05,
            "cleanup_offset_mm": 0.2,
        },
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config_json), encoding="utf-8")

    env = {
        "CAM_SAFE_Z": "5",
        "CAM_MATERIAL": "Birch",
        "CAM_MERGE_EPS": "0.03",
    }
    cli = {"safe_z_mm": 8.0, "material_name": "Maple"}

    config = load_config(cli_args=cli, env=env, config_path=cfg_path)

    assert config.safe_z_mm == 8.0  # CLI wins
    assert config.material_name == "Maple"
    assert config.merge_epsilon_mm == 0.03  # env overrides file
    assert config.cleanup_offset_mm == 0.2  # from file
    assert isinstance(config.tool_db_path, Path)
