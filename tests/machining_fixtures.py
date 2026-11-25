from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def write_machining_configuration(root: Path) -> Path:
    cutters = [
        ("test_profile", 9.525, 25.4, "compression", 2, None, None, 2400, 600, 6),
        ("test_pocket", 9.525, 25.4, "straight", 1, None, None, 1800, 450, 4),
        ("test_flat_6", 6.35, 25.4, "upcut_spiral", 2, None, None, 3600, 1188, 3),
        ("test_flat_3", 3.175, 12.7, "upcut_spiral", 2, None, None, 2160, 712.8, 2),
        ("test_detail", 3.175, 20.64, "downcut_spiral", 2, None, None, 1800, 594, 2),
        ("test_long_flat", 12.7, 38.1, "straight", 2, None, None, 1680, 420, 4),
        ("test_v60", 12.7, 12, "v_bit", 1, 60, None, 1800, 450, 1),
        ("test_v90", 12.7, 12, "v_bit", 1, 90, None, 1800, 450, 1),
        ("test_engraver", 1, 5, "engraving", 1, None, None, 1200, 300, 0.5),
        ("test_ball", 3.19, 22, "ball", 2, None, None, 1800, 594, 1),
        ("test_ball_small", 1.6, 26, "ball", 2, None, None, 800, 200, 0.5),
        ("test_ball_medium", 6.35, 25.4, "ball", 2, None, None, 2880, 720, 2),
        ("test_ball_long", 3.175, 25.4, "ball", 2, None, None, 1200, 300, 1),
        ("test_rougher", 9.525, 31.75, "upcut_spiral", 3, None, None, 4320, 2160, 6),
        ("test_surface", 25.4, 10.2, "straight", 4, None, None, 4800, 1200, 1),
        ("test_roundover", 12, 13, "roundover", 2, None, 6, 720, 180, 1),
    ]
    endmills = []
    parameters: dict[str, dict[str, Any]] = {
        role: {} for role in ("profile", "pocket", "hole", "surface", "vcarve", "engrave", "roundover", "specialty")
    }
    for name, diameter, reach, kind, flutes, angle, radius, xy, z, stepdown in cutters:
        tool = {
            "name": name,
            "diameter_mm": diameter,
            "flute_length_mm": reach,
            "shank_diameter_mm": diameter,
            "flutes": flutes,
            "type": kind,
        }
        if angle is not None:
            tool["v_angle_deg"] = angle
        if radius is not None:
            tool["roundover_radius_mm"] = radius
        endmills.append(tool)
        roles = (
            ("profile", "pocket", "hole", "surface", "specialty")
            if kind in {"straight", "compression", "upcut_spiral", "downcut_spiral"}
            else ("vcarve", "engrave", "specialty")
            if kind == "v_bit"
            else ("roundover", "specialty")
            if kind == "roundover"
            else ("engrave", "specialty")
        )
        for role in roles:
            parameters[role][name] = {
                "rpm": 12000,
                "feed_xy": xy,
                "feed_z": z,
                "depth_per_pass": stepdown,
                "stepover_percent": 40,
            }
    assignments = {
        "profile": ["test_profile", "test_flat_6", "test_detail", "test_long_flat"],
        "pocket": ["test_pocket", "test_flat_6", "test_detail"],
        "hole": ["test_flat_6", "test_detail"],
        "surface": ["test_surface"],
        "vcarve": ["test_v90", "test_v60"],
        "engrave": ["test_engraver"],
        "roundover": ["test_roundover"],
        "specialty": ["test_detail", "test_flat_6", "test_long_flat"],
    }
    machine = {
        "name": "Test router",
        "envelope": {"x_min": 0, "y_min": 0, "x_max": 1300, "y_max": 1300, "z_min": -77, "z_max": 0},
        "defaults": {"safe_z_mm": 3, "park_z_mm": 18},
        "cutting_preset": "test_cutting",
        "controller": {"work_coord_system": "G54", "spindle_dwell_s": 5},
        "capabilities": {"max_feed_xy": 10000, "max_feed_z": 5000, "rapid_z": 1000},
    }
    files = {
        "defaults.yml": {"machine": "test_router", "recipe_machine": "test_router"},
        "cnc/test_router.yml": machine,
        "endmills.yml": {"endmills": endmills},
        "cutting_presets/test_cutting.yml": {
            "name": "Test cutting",
            "materials": {
                material: {"roles": assignments, "parameters": parameters} for material in ("mdf", "plywood")
            },
        },
    }
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            yaml.dump(data, handle)
    return root
