import hashlib
import sys
from typing import Any

from adapters.hints_to_removal import (
    hole_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    profile_hint_to_removal_intent,
)
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.planner.passes.tools import normalize_tool_entries
from cam.planner.planner_input import FeatureInput, GeometryInput, PlannerInput
from cam.post.gcode import write_gcode
from ir.removal_intent import ShapeGeometry

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


def _generate_gcode(
    planner_input: PlannerInput,
    stock: Stock,
    material: Material,
    machine: Machine,
) -> str:
    passes, _ = plan_passes(
        planner_input,
        config=Config(),
        tool_db=normalize_tool_entries(TOOL_DB),
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    gcode_parts = []
    for p in passes:
        gcode = write_gcode(
            p.moves,
            safe_z=p.setup.safe_z,
        )
        gcode_parts.append(gcode)

    return "\n".join(gcode_parts)


def _planner_input_from_hints(
    profiles=None,
    pockets=None,
    holes=None,
    engraves=None,
    kerf_width_mm=3.175,
) -> PlannerInput:
    def _to_feature(hint: dict[str, Any]) -> FeatureInput:
        shape = hint.get("shape", "Rect")
        geom = hint.get("geometry", {})
        points_raw = geom.get("points")
        points = tuple((float(p[0]), float(p[1])) for p in points_raw) if points_raw else None
        shape_geometry = ShapeGeometry(
            w_mm=float(geom["w_mm"]) if "w_mm" in geom else None,
            h_mm=float(geom["h_mm"]) if "h_mm" in geom else None,
            diameter_mm=float(geom["diameter_mm"]) if "diameter_mm" in geom else None,
            points=points,
        )
        return FeatureInput(
            id=hint.get("id", ""),
            shape=shape,
            geometry=GeometryInput(shape=shape, geometry=shape_geometry),
            center_xy_mm=tuple(hint.get("center_xy_mm", (0.0, 0.0))),
            depth_mm=float(hint.get("depth_mm", 0.0)),
            start_depth_mm=float(hint.get("start_depth_mm", 0.0)),
            side=hint.get("side"),
        )

    return PlannerInput(
        kerf_width_mm=kerf_width_mm,
        profiles=tuple(_to_feature(p) for p in (profiles or [])),
        pockets=tuple(_to_feature(p) for p in (pockets or [])),
        holes=tuple(_to_feature(h) for h in (holes or [])),
        engraves=tuple(_to_feature(e) for e in (engraves or [])),
    )


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

    planner_input_v1 = _planner_input_from_hints(profiles=[profile_hint])
    gcode_v1 = _generate_gcode(planner_input_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)

    intent = profile_hint_to_removal_intent(profile_hint, sheet_thickness_mm=sheet_thickness)
    planner_input_v2 = removal_intents_to_planner_input([intent], kerf_width_mm=3.175)
    gcode_v2 = _generate_gcode(planner_input_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)

    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"

    print(f"  ✓ PASS (hash: {hash_v1[:16]}...)")
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

    planner_input_v1 = _planner_input_from_hints(pockets=[pocket_hint])
    gcode_v1 = _generate_gcode(planner_input_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)

    intent = pocket_hint_to_removal_intent(pocket_hint)
    planner_input_v2 = removal_intents_to_planner_input([intent], kerf_width_mm=3.175)
    gcode_v2 = _generate_gcode(planner_input_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)

    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"

    print(f"  ✓ PASS (hash: {hash_v1[:16]}...)")
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

    planner_input_v1 = _planner_input_from_hints(holes=[hole_hint])
    gcode_v1 = _generate_gcode(planner_input_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)

    intent = hole_hint_to_removal_intent(hole_hint)
    planner_input_v2 = removal_intents_to_planner_input([intent], kerf_width_mm=3.175)
    gcode_v2 = _generate_gcode(planner_input_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)

    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"

    print(f"  ✓ PASS (hash: {hash_v1[:16]}...)")
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

    planner_input_v1 = _planner_input_from_hints(
        profiles=[profile_hint],
        pockets=[pocket_hint],
        holes=[hole_hint],
    )
    gcode_v1 = _generate_gcode(planner_input_v1, stock, material, machine)
    hash_v1 = _hash_gcode(gcode_v1)

    profile_intent = profile_hint_to_removal_intent(profile_hint, sheet_thickness_mm=sheet_thickness)
    pocket_intent = pocket_hint_to_removal_intent(pocket_hint)
    hole_intent = hole_hint_to_removal_intent(hole_hint)
    planner_input_v2 = removal_intents_to_planner_input(
        [profile_intent, pocket_intent, hole_intent],
        kerf_width_mm=3.175,
    )
    gcode_v2 = _generate_gcode(planner_input_v2, stock, material, machine)
    hash_v2 = _hash_gcode(gcode_v2)

    assert hash_v1 == hash_v2, f"G-code mismatch:\nv1 hash: {hash_v1}\nv2 hash: {hash_v2}"
    assert gcode_v1 == gcode_v2, "G-code should be byte-identical"

    print(f"  ✓ PASS (hash: {hash_v1[:16]}...)")
    return True


if __name__ == "__main__":
    tests = [
        test_profile_gcode_equivalence,
        test_pocket_gcode_equivalence,
        test_hole_gcode_equivalence,
        test_mixed_operations_gcode_equivalence,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} G-code equivalence tests passed")

    if all(results):
        print("\n✓ BYTE-IDENTICAL: v2 adapter path produces identical G-code to v1 direct path")
    else:
        print("\n✗ EQUIVALENCE FAILED: G-code differs between paths")

    sys.exit(0 if all(results) else 1)
