from skills.mill_ui.apps.compose_cam import _apply_grid_layout


def test_layout_pattern_repeats_items():
    items = [
        {
            "kind": "template",
            "type": "Shaker",
            "id": "door",
            "params": {
                "outer_w": 100.0,
                "outer_h": 200.0,
                "stile_w": 20.0,
                "rail_h": 20.0,
            },
        }
    ]
    layout = {
        "cols": 2,
        "rows": 2,
        "fit": "tight",
        "border_mm": 0.0,
        "pattern": True,
    }

    _apply_grid_layout(400.0, 400.0, layout, items, kerf_hint=0.0)

    assert len(items) == 4
    ids = {item.get("id") for item in items}
    assert len(ids) == 4
    for item in items:
        assert "center_xy_mm" in item.get("placement", {})
