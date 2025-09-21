from __future__ import annotations

from skills.mill_ui.cad.native.core import build_model


def test_build_model_creates_parts_for_touching_rectangles():
    sheet = {"width_mm": 200.0, "height_mm": 120.0, "thickness_mm": 18.0}
    shapes = [
        {
            "id": "left",
            "type": "Rect",
            "geometry": {"w_mm": 100.0, "h_mm": 200.0},
            "feature": {"type": "profile", "depth": "through"},
            "placement": {"center_xy_mm": [0.0, 0.0]},
        },
        {
            "id": "right",
            "type": "Rect",
            "geometry": {"w_mm": 100.0, "h_mm": 200.0},
            "feature": {"type": "profile", "depth": "through"},
            "placement": {"center_xy_mm": [100.0, 0.0]},
        },
    ]

    model = build_model(sheet, shapes, kerf_mm=3.175, include_floating_parts=True)

    assert len(model.parts) == 2
    ids = {part.id for part in model.parts}
    assert ids == {"left", "right"}


def test_build_model_handles_explicit_gap():
    sheet = {"width_mm": 200.0, "height_mm": 120.0, "thickness_mm": 18.0}
    shapes = [
        {
            "id": "left",
            "type": "Rect",
            "geometry": {"w_mm": 100.0, "h_mm": 200.0},
            "feature": {"type": "profile", "depth": "through"},
            "placement": {"center_xy_mm": [0.0, 0.0]},
        },
        {
            "id": "right",
            "type": "Rect",
            "geometry": {"w_mm": 100.0, "h_mm": 200.0},
            "feature": {"type": "profile", "depth": "through"},
            "placement": {"center_xy_mm": [110.0, 0.0]},
        },
    ]

    model = build_model(sheet, shapes, kerf_mm=0.0, include_floating_parts=True)

    assert len(model.parts) == 2
    widths = {round(part.width_mm, 4) for part in model.parts}
    assert widths == {100.0}
