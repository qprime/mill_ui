from __future__ import annotations

from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.planner.passes import plan_passes
from skills.mill_ui.core import Config


def _test_hints() -> dict:
    return {
        "kerf_width_mm": 6.35,
        "profiles": [
            {
                "id": "rect_a",
                "shape": "rect",
                "geometry": {"w_mm": 50.0, "h_mm": 50.0},
                "center_xy_mm": (25.0, 25.0),
                "depth_mm": 12.0,
            },
            {
                "id": "rect_b",
                "shape": "rect",
                "geometry": {"w_mm": 50.0, "h_mm": 50.0},
                "center_xy_mm": (75.0, 25.0),
                "depth_mm": 12.0,
            },
        ],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }


def _tool_db() -> list[dict]:
    return [
        {
            "name": "Quarter",
            "diameter": 6.35,
            "kind": "flat",
            "rpm": 12000,
            "feed_xy": 800,
            "feed_z": 300,
        }
    ]


def test_merge_tolerance_can_disable_shared_edges() -> None:
    hints = _test_hints()
    stock = Stock(width=200.0, height=100.0, thickness=12.0)
    material = Material(name="MDF")
    machine = Machine(name="default")

    config_enabled = Config(merge_epsilon_mm=0.1, min_overlap_mm=0.0)
    _, summary_enabled = plan_passes(
        hints,
        config=config_enabled,
        tool_db=_tool_db(),
        material=material,
        machine=machine,
        stock=stock,
        safe_z=config_enabled.safe_z_mm,
    )
    assert summary_enabled.get("merged_seams", 0) > 0

    config_disabled = Config(merge_epsilon_mm=0.0)
    _, summary_disabled = plan_passes(
        hints,
        config=config_disabled,
        tool_db=_tool_db(),
        material=material,
        machine=machine,
        stock=stock,
        safe_z=config_disabled.safe_z_mm,
    )
    assert summary_disabled.get("merged_seams", 0) == 0
