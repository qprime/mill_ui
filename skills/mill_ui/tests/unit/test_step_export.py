from __future__ import annotations

from pathlib import Path

import pytest

from skills.mill_ui.cad.export.step import SheetSpec, build_step_solids, export_step, export_stl
from skills.mill_ui.cad.native.core import Solid


def _sample_shapes() -> list[dict]:
    return [
        {
            "id": "outer",
            "type": "Rect",
            "geometry": {"w_mm": 80.0, "h_mm": 40.0},
            "feature": {"type": "profile", "depth": "through"},
            "placement": {"center_xy_mm": [0.0, 0.0]},
        },
        {
            "id": "pocket",
            "type": "Rect",
            "geometry": {"w_mm": 40.0, "h_mm": 20.0},
            "feature": {"type": "pocket", "depth_mm": 5.0},
            "placement": {"center_xy_mm": [0.0, 0.0]},
        },
        {
            "id": "slot",
            "type": "Circle",
            "geometry": {"diameter_mm": 10.0},
            "feature": {"type": "profile", "depth": "through"},
            "placement": {"center_xy_mm": [40.0, 0.0]},
        },
    ]


def test_build_step_solids_returns_solid_data():
    sheet_spec = SheetSpec(width_mm=200.0, height_mm=120.0, thickness_mm=18.0)
    sheet_solid, parts = build_step_solids(sheet_spec, _sample_shapes(), kerf_mm=3.0)

    assert isinstance(sheet_solid, Solid)
    assert sheet_solid.width_mm == pytest.approx(200.0)
    assert parts
    assert all(isinstance(part, Solid) for part in parts)
    assert any(part.shape == "circle" for part in parts)


def test_export_stl_writes_ascii(tmp_path):
    sheet_spec = SheetSpec(width_mm=120.0, height_mm=60.0, thickness_mm=12.0)
    output = tmp_path / "panel.stl"

    outputs = export_stl(
        sheet_spec,
        _sample_shapes(),
        output,
        kerf_mm=3.0,
        include_sheet=True,
        include_floating_parts=True,
        mesh_tolerance_mm=0.2,
        angular_tolerance_deg=5.0,
    )

    assert outputs
    for path in outputs:
        data = Path(path).read_text(encoding="ascii")
        assert data.startswith("solid")
        assert "facet normal" in data


def test_export_step_writes_manifest(tmp_path):
    sheet_spec = SheetSpec(width_mm=180.0, height_mm=90.0, thickness_mm=16.0)
    out_path = tmp_path / "panel.step"

    export_step(sheet_spec, _sample_shapes(), out_path, kerf_mm=3.0)

    content = out_path.read_text(encoding="utf-8")
    assert "ISO-10303-21" in content
    assert "FILE_DESCRIPTION" in content
    assert "FILE_NAME" in content
