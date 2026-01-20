
from __future__ import annotations

from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.config import Config


TOOL_DB = [
    {
        "name": "1_8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    },
]


def _make_test_fixtures():
    stock = Stock(width=300.0, height=200.0, thickness=19.0)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")
    config = Config()
    return stock, material, machine, config


def test_polygon_triangle_profile():
    stock, material, machine, config = _make_test_fixtures()

    hints = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [{
            "id": "triangle",
            "shape": "Polygon",
            "geometry": {"points": [(0, 0), (50, 0), (25, 43)]},
            "center_xy_mm": (100, 100),
            "depth_mm": 19.0,
            "side": "outside",
        }],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    assert len(passes[0]["moves"]) > 0

    gcode = write_gcode(passes[0]["moves"], unit="mm", prec=3, safe_z=5.0)
    lines = gcode.splitlines()
    assert len(lines) > 10
    assert any("G1" in line for line in lines)


def test_polygon_l_shape_profile():
    stock, material, machine, config = _make_test_fixtures()

    hints = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [{
            "id": "l_shape",
            "shape": "Polygon",
            "geometry": {
                "points": [
                    (0, 0), (60, 0), (60, 30),
                    (30, 30), (30, 60), (0, 60)
                ]
            },
            "center_xy_mm": (150, 100),
            "depth_mm": 19.0,
            "side": "outside",
        }],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    gcode = write_gcode(passes[0]["moves"], unit="mm", prec=3, safe_z=5.0)
    assert "G1" in gcode


def test_roundedrect_uniform_radius_profile():
    stock, material, machine, config = _make_test_fixtures()

    hints = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [{
            "id": "rounded_panel",
            "shape": "RoundedRect",
            "geometry": {
                "w_mm": 200.0,
                "h_mm": 100.0,
                "radius_mm": 15.0,
            },
            "center_xy_mm": (150, 100),
            "depth_mm": 19.0,
            "side": "outside",
        }],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    gcode = write_gcode(passes[0]["moves"], unit="mm", prec=3, safe_z=5.0)
    assert "G1" in gcode
    assert len(gcode.splitlines()) > 50


def test_roundedrect_selective_corners_profile():
    stock, material, machine, config = _make_test_fixtures()

    hints = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [{
            "id": "table_top",
            "shape": "RoundedRect",
            "geometry": {
                "w_mm": 200.0,
                "h_mm": 100.0,
                "radius_tl_mm": 20.0,
                "radius_tr_mm": 20.0,
                "radius_br_mm": 0.0,
                "radius_bl_mm": 0.0,
            },
            "center_xy_mm": (150, 100),
            "depth_mm": 19.0,
            "side": "outside",
        }],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    gcode = write_gcode(passes[0]["moves"], unit="mm", prec=3, safe_z=5.0)
    assert "G1" in gcode


def test_polygon_inside_cut():
    stock, material, machine, config = _make_test_fixtures()

    hints = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [{
            "id": "cutout",
            "shape": "Polygon",
            "geometry": {"points": [(0, 0), (80, 0), (80, 60), (0, 60)]},
            "center_xy_mm": (150, 100),
            "depth_mm": 19.0,
            "side": "inside",
        }],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    gcode = write_gcode(passes[0]["moves"], unit="mm", prec=3, safe_z=5.0)
    assert "G1" in gcode


def test_roundedrect_inside_cut():
    stock, material, machine, config = _make_test_fixtures()

    hints = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [{
            "id": "window_cutout",
            "shape": "RoundedRect",
            "geometry": {
                "w_mm": 100.0,
                "h_mm": 60.0,
                "radius_mm": 10.0,
            },
            "center_xy_mm": (150, 100),
            "depth_mm": 19.0,
            "side": "inside",
        }],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    gcode = write_gcode(passes[0]["moves"], unit="mm", prec=3, safe_z=5.0)
    assert "G1" in gcode


if __name__ == "__main__":
    test_polygon_triangle_profile()
    test_polygon_l_shape_profile()
    test_roundedrect_uniform_radius_profile()
    test_roundedrect_selective_corners_profile()
    test_polygon_inside_cut()
    test_roundedrect_inside_cut()
    print("All tests passed!")
