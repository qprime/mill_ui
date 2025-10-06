from __future__ import annotations

from skills.mill_ui.compositions.cabinets.shaker import Shaker


def test_shaker_allows_inner_dimensions():
    # If only inner_w/inner_h provided, outer should be computed as inner + 2*stile/rail
    params = {
        "inner_w": 200.0,
        "inner_h": 300.0,
        "stile_w": 70.0,
        "rail_h": 70.0,
        "panel_recess": 6.0,
    }
    shapes = Shaker().expand(params, thickness_mm=18.0)
    assert any(s.get("id") == "door:outer" for s in shapes)
    outer = next(s for s in shapes if s.get("id") == "door:outer")
    geom = outer.get("geometry") or {}
    assert geom.get("w_mm") == 200.0 + 2.0 * 70.0
    assert geom.get("h_mm") == 300.0 + 2.0 * 70.0


def test_shaker_border_when_requested():
    params = {
        "outer_w": 500.0,
        "outer_h": 400.0,
        "stile_w": 80.0,
        "rail_h": 70.0,
        "panel_recess": 6.0,
        "border": {
            "mode": "double_vine",
            "track_width_mm": 2.5,
        },
    }
    shapes = Shaker().expand(params, thickness_mm=18.0)
    assert any(s.get("id", "").startswith("border:vine") for s in shapes)
