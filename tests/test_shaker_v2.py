
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from templates import Shaker
from adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)
from export import render_svg_with_removal_intent


def test_shaker_v2_basic_panel():
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


    assert ast.sheet.thickness_mm == 19.0
    assert ast.sheet.width_mm == 450.0
    assert ast.sheet.height_mm == 650.0


    assert len(ast.items) == 2


    outer = ast.items[0]
    assert outer.kind == "shape"
    assert outer.type == "Rect"
    assert outer.shape_id == "door:outer"
    assert outer.feature.type == "profile"
    assert outer.feature.depth == "through"


    panel = ast.items[1]
    assert panel.kind == "shape"
    assert panel.type == "Rect"
    assert panel.shape_id == "door:panel"
    assert panel.feature.type == "pocket"
    assert panel.feature.depth_mm == 6.0


def test_shaker_v2_with_anchors():
    params = {
        "outer_w": 350.0,
        "outer_h": 500.0,
        "stile_w": 45.0,
        "rail_h": 45.0,
        "panel_recess": 5.0,
        "anchor_recess": {
            "enabled": True,
            "diameter_mm": 10.0,
            "extra_depth_mm": 3.0,
            "offsets_mm": {"left": 20.0, "right": 20.0, "top": 20.0, "bottom": 20.0},
        },
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


    assert len(ast.items) == 6


    anchors = [item for item in ast.items if item.shape_id and "anchor" in item.shape_id]
    assert len(anchors) == 4

    for anchor in anchors:
        assert anchor.type == "Circle"
        assert anchor.geometry.data["diameter_mm"] == 10.0
        assert anchor.feature.type == "hole"

        assert anchor.feature.depth_mm == 8.0


def test_shaker_v2_removal_intent_generation():
    params = {
        "outer_w": 300.0,
        "outer_h": 400.0,
        "stile_w": 40.0,
        "rail_h": 40.0,
        "panel_recess": 4.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


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
        elif item.feature.type == "hole":
            intent = hole_hint_to_removal_intent(hint)
        else:
            continue

        removal_intents.append(intent)


    assert len(removal_intents) == 2


    profile_regions = [r for r in removal_intents if "profile" in r.region_id]
    assert len(profile_regions) == 1
    assert profile_regions[0].z_bottom == -19.0


    pocket_regions = [r for r in removal_intents if "pocket" in r.region_id]
    assert len(pocket_regions) == 1
    assert pocket_regions[0].depth_mm() == 4.0


def test_shaker_v2_geometry_verification():
    params = {
        "outer_w": 500.0,
        "outer_h": 700.0,
        "stile_w": 60.0,
        "rail_h": 60.0,
        "panel_recess": 7.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


    outer = ast.items[0]
    assert outer.geometry.data["w_mm"] == 500.0
    assert outer.geometry.data["h_mm"] == 700.0


    panel = ast.items[1]
    expected_panel_w = 500.0 - 2 * 60.0
    expected_panel_h = 700.0 - 2 * 60.0
    assert panel.geometry.data["w_mm"] == expected_panel_w
    assert panel.geometry.data["h_mm"] == expected_panel_h


    assert panel.feature.depth_mm == 7.0


def test_shaker_v2_svg_export():
    params = {
        "outer_w": 350.0,
        "outer_h": 450.0,
        "stile_w": 45.0,
        "rail_h": 45.0,
        "panel_recess": 5.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


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


    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, removal_intents, temp_path)


        svg_path = Path(temp_path)
        assert svg_path.exists()
        assert svg_path.stat().st_size > 0

        svg_content = svg_path.read_text()
        assert '<?xml version' in svg_content
        assert 'door:outer' in svg_content
        assert 'door:panel' in svg_content

    finally:
        Path(temp_path).unlink()


def test_shaker_v2_inner_dimensions():
    params = {
        "inner_w": 300.0,
        "inner_h": 500.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


    outer = ast.items[0]
    expected_outer_w = 300.0 + 2 * 50.0
    expected_outer_h = 500.0 + 2 * 50.0
    assert outer.geometry.data["w_mm"] == expected_outer_w
    assert outer.geometry.data["h_mm"] == expected_outer_h


def test_shaker_v2_no_panel_recess():
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 0.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


    assert len(ast.items) == 1
    assert ast.items[0].shape_id == "door:outer"


def test_shaker_v2_invalid_dimensions():
    params = {
        "outer_w": 0.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
    }

    with pytest.raises(ValueError, match="Invalid Shaker dimensions"):
        Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


def test_shaker_v2_ast_json_serialization():
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


    ast_json = ast.to_json()
    ast_dict = json.loads(ast_json)


    assert "sheet" in ast_dict
    assert "items" in ast_dict
    assert ast_dict["sheet"]["thickness_mm"] == 19.0
    assert len(ast_dict["items"]) == 2


def test_shaker_v2_end_to_end_pipeline():
    from cam.config import Config
    from cam.model.machine import Machine
    from cam.model.material import Material
    from cam.model.stock import Stock
    from cam.planner.passes import plan_passes
    from cam.post.gcode import write_gcode
    from adapters.removal_to_planner import removal_intents_to_v1_hints


    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }
    sheet_thickness_mm = 19.0


    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=sheet_thickness_mm)


    assert len(ast.items) == 2
    assert ast.sheet.thickness_mm == sheet_thickness_mm


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


    assert len(removal_intents) == 2
    profile_intents = [r for r in removal_intents if r.metadata.get("hint_type") == "profile"]
    pocket_intents = [r for r in removal_intents if r.metadata.get("hint_type") == "pocket"]
    assert len(profile_intents) == 1
    assert len(pocket_intents) == 1


    hints = removal_intents_to_v1_hints(removal_intents, kerf_width_mm=3.175)


    assert "profiles" in hints
    assert "pockets" in hints
    assert len(hints["profiles"]) == 1
    assert len(hints["pockets"]) == 1


    tool_db = [
        {
            "name": "1/8\" End Mill",
            "diameter_mm": 3.175,
            "flutes": 2,
            "max_doc_mm": 3.0,
            "roughing_stepover": 0.6,
            "finishing_stepover": 0.4,
        }
    ]

    config = Config(
        safe_z_mm=5.0,
        merge_epsilon_mm=0.1,
        pocket_stepover_ratio=0.6,
        pocket_stepdown_mm=1.5,
    )

    material = Material(name="MDF", max_feed_mm_min=1200.0, max_spindle_rpm=18000.0)
    machine = Machine(name="Test Mill", max_feed_mm_min=2000.0, max_spindle_rpm=24000.0)
    stock = Stock(thickness_mm=sheet_thickness_mm, top_z=0.0)

    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=5.0,
    )


    assert len(passes) > 0
    assert summary is not None


    for pass_dict in passes:
        assert "setup" in pass_dict
        setup = pass_dict["setup"]
        assert setup.safe_z == 5.0
        assert setup.stock.thickness_mm == sheet_thickness_mm


        for move in pass_dict["moves"]:
            if "z" in move:

                if move.get("kind") == "retract" or move.get("retract"):
                    assert move["z"] >= setup.safe_z, f"Unsafe retract: {move['z']} < {setup.safe_z}"


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


    assert len(all_gcode_lines) > 0


    for line in all_gcode_lines:
        line = line.strip()

        if line.startswith("G") and "Z" in line:

            parts = line.split()
            for part in parts:
                if part.startswith("Z"):
                    try:
                        z_val = float(part[1:])

                        assert z_val >= -sheet_thickness_mm - 1.0, f"Unsafe Z depth: {z_val} deeper than stock {sheet_thickness_mm}mm"
                    except ValueError:
                        pass


    print(f"\n✓ End-to-end pipeline validated:")
    print(f"  - AST items: {len(ast.items)}")
    print(f"  - RemovalIntent regions: {len(removal_intents)}")
    print(f"  - Planner passes: {len(passes)}")
    print(f"  - G-code lines: {len(all_gcode_lines)}")


def test_shaker_v2_removal_intent_dump():
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)


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


    region_counts = {
        "profile": 0,
        "pocket": 0,
        "hole": 0,
        "engrave": 0,
    }

    for intent in removal_intents:
        hint_type = intent.metadata.get("hint_type", "unknown")
        if hint_type in region_counts:
            region_counts[hint_type] += 1


    assert region_counts["profile"] == 1, f"Expected 1 profile, got {region_counts['profile']}"
    assert region_counts["pocket"] == 1, f"Expected 1 pocket, got {region_counts['pocket']}"
    assert region_counts["hole"] == 0
    assert region_counts["engrave"] == 0


    for intent in removal_intents:
        depth = intent.depth_mm()
        assert depth > 0.0, f"RemovalIntent depth must be positive, got {depth}"
        assert depth <= ast.sheet.thickness_mm + 1.0, f"Depth {depth}mm exceeds stock thickness {ast.sheet.thickness_mm}mm"

    print(f"\n✓ RemovalIntent dump verified:")
    print(f"  - Profiles: {region_counts['profile']}")
    print(f"  - Pockets: {region_counts['pocket']}")
    print(f"  - Holes: {region_counts['hole']}")
    print(f"  - Engraves: {region_counts['engrave']}")
