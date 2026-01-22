
from __future__ import annotations

import hashlib
import sys
from io import StringIO
from typing import Any

from cam.model.hints import build_cam_hints
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.config import Config
from adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)
from adapters.removal_to_planner import removal_intents_to_hints


TOOL_DB = [
    {
        "name": "1_8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    },
    {
        "name": "1_4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 800,
        "feed_z": 280,
    },
]


def _hash_gcode(gcode: str) -> str:
    return hashlib.sha256(gcode.encode("utf-8")).hexdigest()


def _generate_gcode_from_hints(
    hints: dict[str, Any],
    stock: Stock,
    material: Material,
    machine: Machine,
) -> str:
    passes, _ = plan_passes(
        hints,
        config=Config(),
        tool_db=TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )


    gcode_parts = []
    for pass_record in passes:
        output = StringIO()
        write_gcode(
            moves=pass_record.moves,
            setup=pass_record.setup,
            output=output,
        )
        gcode_parts.append(output.getvalue())

    return "\n".join(gcode_parts)


def test_profile_gcode_equivalence():
    print("Running test_profile_gcode_equivalence...")

    sheet_thickness = 19.0
    stock = Stock(width=300.0, height=200.0, thickness=sheet_thickness)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")


    profile_hint = {
        "id": "outer_rect",
        "shape": "Rect",
        "geometry": {"w_mm": 200.0, "h_mm": 100.0},
        "center_xy_mm": (150.0, 100.0),
        "depth_mm": sheet_thickness,
        "side": "outside",
    }


    hints_v1 = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [profile_hint],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }
    gcode_v1 = _generate_gcode_from_hints(hints_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)


    intent = profile_hint_to_removal_intent(profile_hint, sheet_thickness_mm=sheet_thickness)
    hints_v2 = removal_intents_to_hints([intent], kerf_width_mm=3.175)
    gcode_v2 = _generate_gcode_from_hints(hints_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)


    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"
    print("  PASS")
    return True


def test_pocket_gcode_equivalence():
    print("Running test_pocket_gcode_equivalence...")
    sheet_thickness = 19.0
    stock = Stock(width=300.0, height=200.0, thickness=sheet_thickness)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")


    pocket_hint = {
        "id": "center_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 80.0, "h_mm": 40.0},
        "center_xy_mm": (150.0, 100.0),
        "depth_mm": 8.0,
    }


    hints_v1 = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [],
        "pockets": [pocket_hint],
        "holes": [],
        "engraves": [],
    }
    gcode_v1 = _generate_gcode_from_hints(hints_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)


    intent = pocket_hint_to_removal_intent(pocket_hint)
    hints_v2 = removal_intents_to_hints([intent], kerf_width_mm=3.175)
    gcode_v2 = _generate_gcode_from_hints(hints_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)


    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"
    print("  PASS")
    return True


def test_hole_gcode_equivalence():
    print("Running test_hole_gcode_equivalence...")
    sheet_thickness = 19.0
    stock = Stock(width=300.0, height=200.0, thickness=sheet_thickness)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")


    hole_hint = {
        "id": "mount_hole",
        "shape": "Circle",
        "geometry": {"diameter_mm": 6.35},
        "center_xy_mm": (50.0, 50.0),
        "depth_mm": 12.0,
    }


    hints_v1 = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [],
        "pockets": [],
        "holes": [hole_hint],
        "engraves": [],
    }
    gcode_v1 = _generate_gcode_from_hints(hints_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)


    intent = hole_hint_to_removal_intent(hole_hint)
    hints_v2 = removal_intents_to_hints([intent], kerf_width_mm=3.175)
    gcode_v2 = _generate_gcode_from_hints(hints_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)


    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"
    print("  PASS")
    return True


def test_mixed_operations_gcode_equivalence():
    print("Running test_mixed_operations_gcode_equivalence...")
    sheet_thickness = 19.0
    stock = Stock(width=400.0, height=300.0, thickness=sheet_thickness)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")


    profile_hint = {
        "id": "outer",
        "shape": "Rect",
        "geometry": {"w_mm": 300.0, "h_mm": 200.0},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": sheet_thickness,
        "side": "outside",
    }
    pocket_hint = {
        "id": "inner_pocket",
        "shape": "Rect",
        "geometry": {"w_mm": 100.0, "h_mm": 50.0},
        "center_xy_mm": (200.0, 150.0),
        "depth_mm": 6.0,
    }
    hole_hint = {
        "id": "corner_hole",
        "shape": "Circle",
        "geometry": {"diameter_mm": 6.35},
        "center_xy_mm": (120.0, 100.0),
        "depth_mm": 12.0,
    }


    hints_v1 = {
        "units": "mm",
        "kerf_width_mm": 3.175,
        "min_channel_width_mm": 6.0,
        "profiles": [profile_hint],
        "pockets": [pocket_hint],
        "holes": [hole_hint],
        "engraves": [],
    }
    gcode_v1 = _generate_gcode_from_hints(hints_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)


    profile_intent = profile_hint_to_removal_intent(profile_hint, sheet_thickness_mm=sheet_thickness)
    pocket_intent = pocket_hint_to_removal_intent(pocket_hint)
    hole_intent = hole_hint_to_removal_intent(hole_hint)
    hints_v2 = removal_intents_to_hints(
        [profile_intent, pocket_intent, hole_intent],
        kerf_width_mm=3.175,
    )
    gcode_v2 = _generate_gcode_from_hints(hints_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)


    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_profile_gcode_equivalence,
        test_pocket_gcode_equivalence,
        test_hole_gcode_equivalence,
        test_mixed_operations_gcode_equivalence,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
