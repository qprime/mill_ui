"""Standalone runner for Stage 10 end-to-end pipeline test."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from skills.mill_ui.templates import Shaker
from skills.mill_ui.adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
)
from skills.mill_ui.adapters.removal_to_planner import removal_intents_to_v1_hints
from skills.mill_ui.cam.config import Config
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.planner.passes import plan_passes
from skills.mill_ui.cam.post.gcode import write_gcode


def test_end_to_end_pipeline():
    """Test complete pipeline: params → AST → RemovalIntent → planner → G-code."""
    print("Running end-to-end pipeline test...")

    # 1. Start with template parameters
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }
    sheet_thickness_mm = 19.0

    # 2. Expand to AST
    print("\n[1] Expanding params to AST...")
    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=sheet_thickness_mm)
    print(f"  ✓ Generated {len(ast.items)} AST items")

    # 3. Convert AST to RemovalIntent
    print("\n[2] Converting AST to RemovalIntent...")
    removal_intents = []
    for item in ast.items:
        if item.kind != "shape" or not item.feature or not item.geometry or not item.placement:
            continue

        hint = {
            "id": item.shape_id or "",
            "shape": item.type,
            "geometry": item.geometry.data,
            "center_xy_mm": item.placement.center_xy_mm,
            "depth_mm": item.feature.depth_mm or ast.sheet.thickness_mm,
        }

        if item.feature.type == "profile":
            if item.feature.side:
                hint["side"] = item.feature.side
            intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=ast.sheet.thickness_mm)
        elif item.feature.type == "pocket":
            intent = pocket_hint_to_removal_intent(hint)
        else:
            continue

        removal_intents.append(intent)

    print(f"  ✓ Generated {len(removal_intents)} RemovalIntent regions")
    for intent in removal_intents:
        hint_type = intent.metadata.get("hint_type", "unknown")
        depth = intent.depth_mm()
        print(f"    - {hint_type}: depth={depth:.1f}mm, bounds={intent.bounds}")

    # 4. Convert to v1 hints
    print("\n[3] Converting RemovalIntent to v1 planner hints...")
    hints = removal_intents_to_v1_hints(removal_intents, kerf_width_mm=3.175)
    print(f"  ✓ Generated hints: {len(hints['profiles'])} profiles, {len(hints['pockets'])} pockets")

    # 5. Plan passes
    print("\n[4] Planning CAM passes...")
    tool_db = [
        {
            "name": "1_8_endmill",
            "diameter": 3.175,
            "kind": "flat",
            "rpm": 14000,
            "feed_xy": 900,
            "feed_z": 300,
        }
    ]

    config = Config(
        safe_z_mm=5.0,
        merge_epsilon_mm=0.1,
    )

    material = Material(name="MDF")
    machine = Machine()
    stock = Stock(width=ast.sheet.width_mm, height=ast.sheet.height_mm, thickness=sheet_thickness_mm)

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=5.0,
    )

    print(f"  ✓ Generated {len(passes)} passes")
    for pass_dict in passes:
        print(f"    - {pass_dict['op']}: {len(pass_dict['moves'])} moves, tool={pass_dict['tool']['name']}")

    # 6. Verify safety
    print("\n[5] Verifying safety constraints...")
    unsafe_count = 0
    for pass_dict in passes:
        setup = pass_dict["setup"]
        for move in pass_dict["moves"]:
            if "z" in move:
                if move.get("kind") == "retract" or move.get("retract"):
                    if move["z"] < setup.safe_z:
                        unsafe_count += 1

    if unsafe_count > 0:
        print(f"  ✗ Found {unsafe_count} unsafe retract moves!")
        return False
    else:
        print("  ✓ All retracts respect safe-Z")

    # 7. Generate G-code
    print("\n[6] Generating G-code...")
    all_gcode_lines = []
    for pass_dict in passes:
        moves = pass_dict["moves"]
        if not moves:
            continue

        gcode = write_gcode(
            moves,
            unit="mm",
            prec=3,
            safe_z=5.0,
            header=["G90", "G21"],
            footer=["M5", "M2"],
        )

        all_gcode_lines.extend(gcode.split("\n"))

    print(f"  ✓ Generated {len(all_gcode_lines)} G-code lines")

    # 8. Verify G-code safety
    print("\n[7] Verifying G-code safety...")
    unsafe_z_count = 0
    for line in all_gcode_lines:
        line = line.strip()
        if line.startswith("G") and "Z" in line:
            parts = line.split()
            for part in parts:
                if part.startswith("Z"):
                    try:
                        z_val = float(part[1:])
                        if z_val < -sheet_thickness_mm - 1.0:
                            unsafe_z_count += 1
                    except ValueError:
                        pass

    if unsafe_z_count > 0:
        print(f"  ✗ Found {unsafe_z_count} unsafe Z-depth moves!")
        return False
    else:
        print("  ✓ All Z-depths respect stock thickness")

    # Success!
    print("\n" + "="*60)
    print("✅ END-TO-END PIPELINE VALIDATION COMPLETE")
    print("="*60)
    print(f"  AST items:              {len(ast.items)}")
    print(f"  RemovalIntent regions:  {len(removal_intents)}")
    print(f"  Planner passes:         {len(passes)}")
    print(f"  G-code lines:           {len(all_gcode_lines)}")
    print(f"  Safety violations:      0")
    print("="*60)

    return True


if __name__ == "__main__":
    try:
        success = test_end_to_end_pipeline()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
