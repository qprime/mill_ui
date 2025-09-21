from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.mill_ui.apps import compose_cam
from skills.mill_ui.core.capabilities import Capabilities


def _write_tool_db(path: Path) -> None:
    tool_db = {
        "tools": [
            {
                "tool_id": "Tool1",
                "diameter_mm": 6.0,
                "type": "flat",
                "feeds_speeds": {
                    "MDF": {
                        "rpm": 12000,
                        "feed_rate_mm_min": 800,
                        "plunge_rate_mm_min": 300,
                        "depth_per_pass_mm": 3.0,
                        "step_over_percent": 40,
                    }
                },
            }
        ]
    }
    path.write_text(json.dumps(tool_db), encoding="utf-8")


def test_demo_mode_heightfield_stl(tmp_path, monkeypatch, caplog, capsys):
    layout_dir = tmp_path / "demo"
    input_dir = layout_dir / "input"
    cam_dir = layout_dir / "CAM"
    input_dir.mkdir(parents=True)

    layout_data = {
        "sheet": {"width_mm": 200.0, "height_mm": 100.0, "thickness_mm": 12.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 50.0, "h_mm": 30.0},
                "placement": {"center_xy_mm": [60.0, 40.0]},
                "feature": {"type": "profile", "depth": "through"},
            }
        ],
    }
    layout_path = input_dir / "layout.json"
    layout_path.write_text(json.dumps(layout_data), encoding="utf-8")

    tool_db_path = tmp_path / "tool_db.json"
    _write_tool_db(tool_db_path)

    monkeypatch.setattr(
        compose_cam,
        "get_capabilities",
        lambda: Capabilities(native_cad=False),
    )

    caplog.set_level("INFO")
    exit_code = compose_cam.main([
        str(layout_path),
        "--tool-db",
        str(tool_db_path),
        "--stl",
    ])
    assert exit_code == 0

    output_lines = capsys.readouterr().out.splitlines()
    assert any(line.endswith("panel_preview.stl") for line in output_lines)
    assert (cam_dir / "panel_preview.stl").exists()
    assert "Native CAD backends unavailable" in caplog.text
