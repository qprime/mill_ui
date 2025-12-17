"""Unit tests for ShakerV2 template using v2 AST pipeline.

Stage 10 acceptance tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from skills.mill_ui.v2.templates import ShakerV2
from skills.mill_ui.v2.adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)
from skills.mill_ui.v2.export import render_svg_with_removal_intent


def test_shaker_v2_basic_panel():
    """Test ShakerV2 generates valid AST for basic panel."""
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Verify AST structure
    assert ast.sheet.thickness_mm == 19.0
    assert ast.sheet.width_mm == 450.0  # 400 + 2*25 margin
    assert ast.sheet.height_mm == 650.0  # 600 + 2*25 margin

    # Should have: outer profile + panel pocket
    assert len(ast.items) == 2

    # Verify outer profile
    outer = ast.items[0]
    assert outer.kind == "shape"
    assert outer.type == "Rect"
    assert outer.shape_id == "door:outer"
    assert outer.feature.type == "profile"
    assert outer.feature.depth == "through"

    # Verify panel pocket
    panel = ast.items[1]
    assert panel.kind == "shape"
    assert panel.type == "Rect"
    assert panel.shape_id == "door:panel"
    assert panel.feature.type == "pocket"
    assert panel.feature.depth_mm == 6.0


def test_shaker_v2_with_anchors():
    """Test ShakerV2 with anchor screw recesses."""
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

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Should have: outer profile + panel pocket + 4 anchor holes
    assert len(ast.items) == 6

    # Verify anchor holes
    anchors = [item for item in ast.items if item.shape_id and "anchor" in item.shape_id]
    assert len(anchors) == 4

    for anchor in anchors:
        assert anchor.type == "Circle"
        assert anchor.geometry.data["diameter_mm"] == 10.0
        assert anchor.feature.type == "hole"
        # Anchor depth = panel_recess + extra_depth = 5 + 3 = 8mm
        assert anchor.feature.depth_mm == 8.0


def test_shaker_v2_removal_intent_generation():
    """Test ShakerV2 AST → RemovalIntent conversion."""
    params = {
        "outer_w": 300.0,
        "outer_h": 400.0,
        "stile_w": 40.0,
        "rail_h": 40.0,
        "panel_recess": 4.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Convert AST items to hints, then to RemovalIntent
    removal_intents = []

    for item in ast.items:
        if item.kind != "shape" or not item.feature or not item.geometry or not item.placement:
            continue

        # Build hint from AST item
        hint = {
            "id": item.shape_id or "",
            "shape": item.type,
            "geometry": item.geometry.data,
            "center_xy_mm": item.placement.center_xy_mm,
            "depth_mm": item.feature.depth_mm or ast.sheet.thickness_mm,
        }

        # Convert to RemovalIntent based on feature type
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

    # Verify RemovalIntent regions
    assert len(removal_intents) == 2  # profile + pocket

    # Verify profile region
    profile_regions = [r for r in removal_intents if "profile" in r.region_id]
    assert len(profile_regions) == 1
    assert profile_regions[0].z_bottom == -19.0  # Through-cut

    # Verify pocket region
    pocket_regions = [r for r in removal_intents if "pocket" in r.region_id]
    assert len(pocket_regions) == 1
    assert pocket_regions[0].depth_mm() == 4.0


def test_shaker_v2_geometry_verification():
    """Test ShakerV2 geometry matches specification."""
    params = {
        "outer_w": 500.0,
        "outer_h": 700.0,
        "stile_w": 60.0,
        "rail_h": 60.0,
        "panel_recess": 7.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Verify outer dimensions
    outer = ast.items[0]
    assert outer.geometry.data["w_mm"] == 500.0
    assert outer.geometry.data["h_mm"] == 700.0

    # Verify panel dimensions (inner = outer - 2*stile/rail)
    panel = ast.items[1]
    expected_panel_w = 500.0 - 2 * 60.0  # 380mm
    expected_panel_h = 700.0 - 2 * 60.0  # 580mm
    assert panel.geometry.data["w_mm"] == expected_panel_w
    assert panel.geometry.data["h_mm"] == expected_panel_h

    # Verify panel depth
    assert panel.feature.depth_mm == 7.0


def test_shaker_v2_svg_export():
    """Test ShakerV2 can be exported to SVG for visual verification."""
    params = {
        "outer_w": 350.0,
        "outer_h": 450.0,
        "stile_w": 45.0,
        "rail_h": 45.0,
        "panel_recess": 5.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Convert to RemovalIntent
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

    # Render SVG
    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, removal_intents, temp_path)

        # Verify SVG exists and has content
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
    """Test ShakerV2 with inner dimensions specified."""
    params = {
        "inner_w": 300.0,
        "inner_h": 500.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Outer should be inner + 2*stile/rail
    outer = ast.items[0]
    expected_outer_w = 300.0 + 2 * 50.0  # 400mm
    expected_outer_h = 500.0 + 2 * 50.0  # 600mm
    assert outer.geometry.data["w_mm"] == expected_outer_w
    assert outer.geometry.data["h_mm"] == expected_outer_h


def test_shaker_v2_no_panel_recess():
    """Test ShakerV2 without panel recess (frame only)."""
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 0.0,  # No panel recess
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Should only have outer profile, no panel pocket
    assert len(ast.items) == 1
    assert ast.items[0].shape_id == "door:outer"


def test_shaker_v2_invalid_dimensions():
    """Test ShakerV2 rejects invalid dimensions."""
    params = {
        "outer_w": 0.0,  # Invalid
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
    }

    with pytest.raises(ValueError, match="Invalid Shaker dimensions"):
        ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)


def test_shaker_v2_ast_json_serialization():
    """Test ShakerV2 AST can be serialized to JSON."""
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Serialize to JSON
    ast_json = ast.to_json()
    ast_dict = json.loads(ast_json)

    # Verify JSON structure
    assert "sheet" in ast_dict
    assert "items" in ast_dict
    assert ast_dict["sheet"]["thickness_mm"] == 19.0
    assert len(ast_dict["items"]) == 2


def test_shaker_v2_end_to_end_pipeline():
    """Test complete pipeline: params → AST → RemovalIntent → planner → G-code.

    This is the flagship Stage 10 validation test demonstrating the full v2 pipeline.
    """
    from skills.mill_ui.core.config import Config
    from skills.mill_ui.cam.model.machine import Machine
    from skills.mill_ui.cam.model.material import Material
    from skills.mill_ui.cam.model.stock import Stock
    from skills.mill_ui.cam.planner.passes import plan_passes
    from skills.mill_ui.cam.post.gcode import write_gcode
    from skills.mill_ui.v2.adapters.removal_to_planner import removal_intents_to_v1_hints

    # 1. Start with template parameters (could come from natural language)
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }
    sheet_thickness_mm = 19.0

    # 2. Expand to AST
    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=sheet_thickness_mm)

    # Verify AST structure
    assert len(ast.items) == 2  # profile + pocket
    assert ast.sheet.thickness_mm == sheet_thickness_mm

    # 3. Convert AST items to RemovalIntent
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

    # Verify RemovalIntent count and types
    assert len(removal_intents) == 2
    profile_intents = [r for r in removal_intents if r.metadata.get("hint_type") == "profile"]
    pocket_intents = [r for r in removal_intents if r.metadata.get("hint_type") == "pocket"]
    assert len(profile_intents) == 1
    assert len(pocket_intents) == 1

    # 4. Convert RemovalIntent to v1 hints
    hints = removal_intents_to_v1_hints(removal_intents, kerf_width_mm=3.175)

    # Verify hints structure
    assert "profiles" in hints
    assert "pockets" in hints
    assert len(hints["profiles"]) == 1
    assert len(hints["pockets"]) == 1

    # 5. Plan passes using v1 planner
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

    # Verify passes were generated
    assert len(passes) > 0
    assert summary is not None

    # Safety verification
    for pass_dict in passes:
        assert "setup" in pass_dict
        setup = pass_dict["setup"]
        assert setup.safe_z == 5.0
        assert setup.stock.thickness_mm == sheet_thickness_mm

        # Verify moves respect safe-Z
        for move in pass_dict["moves"]:
            if "z" in move:
                # Retract moves should be at safe-Z or above
                if move.get("kind") == "retract" or move.get("retract"):
                    assert move["z"] >= setup.safe_z, f"Unsafe retract: {move['z']} < {setup.safe_z}"

    # 6. Generate G-code from passes
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
            header=["G90", "G21"],  # Absolute positioning, mm units
            footer=["M5", "M2"],     # Stop spindle, end program
        )

        all_gcode_lines.extend(gcode.split("\n"))

    # Verify G-code was generated
    assert len(all_gcode_lines) > 0

    # Verify G-code safety
    for line in all_gcode_lines:
        line = line.strip()
        # Check for Z moves
        if line.startswith("G") and "Z" in line:
            # Parse Z value (basic check - real validation would be more sophisticated)
            parts = line.split()
            for part in parts:
                if part.startswith("Z"):
                    try:
                        z_val = float(part[1:])
                        # Ensure we never go deeper than stock thickness (negative Z)
                        assert z_val >= -sheet_thickness_mm - 1.0, f"Unsafe Z depth: {z_val} deeper than stock {sheet_thickness_mm}mm"
                    except ValueError:
                        pass  # Non-numeric Z, skip

    # Test completed successfully - full pipeline validated
    print(f"\n✓ End-to-end pipeline validated:")
    print(f"  - AST items: {len(ast.items)}")
    print(f"  - RemovalIntent regions: {len(removal_intents)}")
    print(f"  - Planner passes: {len(passes)}")
    print(f"  - G-code lines: {len(all_gcode_lines)}")


def test_shaker_v2_removal_intent_dump():
    """Test RemovalIntent dump with region counts verification."""
    params = {
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    }

    ast = ShakerV2.expand_to_ast(params, sheet_thickness_mm=19.0)

    # Convert to RemovalIntent
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

    # Verify region counts and types
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

    # Expected: 1 outer profile + 1 panel pocket
    assert region_counts["profile"] == 1, f"Expected 1 profile, got {region_counts['profile']}"
    assert region_counts["pocket"] == 1, f"Expected 1 pocket, got {region_counts['pocket']}"
    assert region_counts["hole"] == 0
    assert region_counts["engrave"] == 0

    # Verify depths
    for intent in removal_intents:
        depth = intent.depth_mm()
        assert depth > 0.0, f"RemovalIntent depth must be positive, got {depth}"
        assert depth <= ast.sheet.thickness_mm + 1.0, f"Depth {depth}mm exceeds stock thickness {ast.sheet.thickness_mm}mm"

    print(f"\n✓ RemovalIntent dump verified:")
    print(f"  - Profiles: {region_counts['profile']}")
    print(f"  - Pockets: {region_counts['pocket']}")
    print(f"  - Holes: {region_counts['hole']}")
    print(f"  - Engraves: {region_counts['engrave']}")
