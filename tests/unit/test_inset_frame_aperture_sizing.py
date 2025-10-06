from __future__ import annotations

from skills.mill_ui.compositions.panels.inset_frame import InsetFrame


def test_inset_frame_allows_aperture_dimensions():
    # Outer should be computed from aperture + 2*(lip_inset + recess_inset)
    params = {
        "aperture_w_mm": 200.0,
        "aperture_h_mm": 300.0,
        "lip_inset_mm": 6.0,
        "recess_extra_inset_mm": 2.0,
        "lip_depth_mm": 4.0,
        "recess_depth_mm": 10.0,
    }
    shapes = InsetFrame().expand(params, thickness_mm=18.0)
    # First shape is the outer profile
    outer = next(s for s in shapes if s.get("id") == "frame:outer")
    geom = outer.get("geometry") or {}
    expected_w = 200.0 + 2.0 * (6.0 + 2.0)
    expected_h = 300.0 + 2.0 * (6.0 + 2.0)
    assert geom.get("w_mm") == expected_w
    assert geom.get("h_mm") == expected_h


def test_inset_frame_border_adds_decorative_shapes():
    params = {
        "outer_w_mm": 400.0,
        "outer_h_mm": 300.0,
        "lip_inset_mm": 80.0,
        "recess_extra_inset_mm": 10.0,
        "lip_depth_mm": 6.0,
        "recess_depth_mm": 12.0,
        "border": {
            "mode": "double_vine",
            "track_depth_mm": 0.5,
        },
    }
    shapes = InsetFrame().expand(params, thickness_mm=18.0)
    recess = next(s for s in shapes if s.get("id") == "frame:recess")
    feature = recess.get("feature") or {}
    assert feature.get("start_depth_mm") == 6.0
    assert any(s.get("id", "").startswith("border:vine") for s in shapes)
