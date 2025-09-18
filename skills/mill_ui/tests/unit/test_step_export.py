from __future__ import annotations

import pytest

try:  # optional dependency
    import cadquery as cq  # type: ignore
except ImportError:  # pragma: no cover - handled by skip
    cq = None  # type: ignore

from skills.mill_ui.cad.step_export import SheetSpec, build_step_solids


@pytest.mark.skipif(cq is None, reason="cadquery is required for STEP export tests")
def test_build_step_solids_creates_sheet_and_parts():
    sheet_spec = SheetSpec(width_mm=200.0, height_mm=120.0, thickness_mm=18.0)
    shapes = [
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

    sheet_solid, parts = build_step_solids(sheet_spec, shapes, kerf_mm=3.0)

    assert sheet_solid is not None
    assert len(parts) == 1

    # Top face should have outer and inner wire due to kerf cut
    top_wires = sheet_solid.faces(">Z").wires()
    assert len(top_wires.vals()) >= 2

    # Floating part should reflect pocket cut
    floating = parts[0]
    pocket_faces = floating.faces("<Z").vals()
    assert pocket_faces, "floating part should have bottom faces after pocket cut"
