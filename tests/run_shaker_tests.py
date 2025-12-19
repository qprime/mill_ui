"""Standalone test runner for Stage 10 Shaker template tests (without pytest).

Run from repository root: PYTHONPATH=. python3 -m tests.run_shaker_tests
"""

import json
import sys
import tempfile
from pathlib import Path

from templates import Shaker
from adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
)
from export import render_svg_with_removal_intent


def test_shaker_v2_basic_panel():
    """Test Shaker generates valid AST for basic panel."""
    print("Running test_shaker_v2_basic_panel...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_with_anchors():
    """Test Shaker with anchor screw recesses."""
    print("Running test_shaker_v2_with_anchors...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_removal_intent_generation():
    """Test Shaker AST → RemovalIntent conversion."""
    print("Running test_shaker_v2_removal_intent_generation...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_geometry_verification():
    """Test Shaker geometry matches specification."""
    print("Running test_shaker_v2_geometry_verification...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_svg_export():
    """Test Shaker can be exported to SVG for visual verification."""
    print("Running test_shaker_v2_svg_export...")

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

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_shaker_v2_inner_dimensions():
    """Test Shaker with inner dimensions specified."""
    print("Running test_shaker_v2_inner_dimensions...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_no_panel_recess():
    """Test Shaker without panel recess (frame only)."""
    print("Running test_shaker_v2_no_panel_recess...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_invalid_dimensions():
    """Test Shaker rejects invalid dimensions."""
    print("Running test_shaker_v2_invalid_dimensions...")

    params = {
        "outer_w": 0.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
    }

    try:
        Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)
        assert False, "Expected ValueError for invalid dimensions"
    except ValueError as e:
        assert "Invalid Shaker dimensions" in str(e)

    print("  ✓ PASS")
    return True


def test_shaker_v2_ast_json_serialization():
    """Test Shaker AST can be serialized to JSON."""
    print("Running test_shaker_v2_ast_json_serialization...")

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

    print("  ✓ PASS")
    return True


def test_shaker_v2_end_to_end_pipeline_validation():
    """Test complete pipeline: params → AST → RemovalIntent → planner hints.

    This is the flagship Stage 10 validation test demonstrating the full v2 pipeline.
    Validates pipeline up to planner integration. G-code generation requires native
    C++ library which may not be available in all environments.
    """
    print("Running test_shaker_v2_end_to_end_pipeline_validation...")

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
    ast = Shaker.expand_to_ast(params, sheet_thickness_mm=sheet_thickness_mm)
    assert len(ast.items) == 2, f"Expected 2 AST items (profile + pocket), got {len(ast.items)}"
    print(f"  [1/4] ✓ Generated {len(ast.items)} AST items")

    # 3. Convert AST to RemovalIntent
    from adapters.hints_to_removal import (
        profile_hint_to_removal_intent,
        pocket_hint_to_removal_intent,
    )

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

    assert len(removal_intents) == 2, f"Expected 2 RemovalIntent regions, got {len(removal_intents)}"
    print(f"  [2/4] ✓ Generated {len(removal_intents)} RemovalIntent regions")

    # 4. Convert to v1 hints
    from adapters.removal_to_planner import removal_intents_to_v1_hints

    hints = removal_intents_to_v1_hints(removal_intents, kerf_width_mm=3.175)

    assert "profiles" in hints, "Expected 'profiles' in hints"
    assert "pockets" in hints, "Expected 'pockets' in hints"
    assert len(hints["profiles"]) == 1, f"Expected 1 profile hint, got {len(hints['profiles'])}"
    assert len(hints["pockets"]) == 1, f"Expected 1 pocket hint, got {len(hints['pockets'])}"
    print(f"  [3/4] ✓ Converted to v1 planner hints ({len(hints['profiles'])} profiles, {len(hints['pockets'])} pockets)")

    # 5. Verify planner integration (if native library available)
    try:
        from cam.config import Config
        from cam.model.machine import Machine
        from cam.model.material import Material
        from cam.model.stock import Stock
        from cam.planner.passes import plan_passes

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

        config = Config(safe_z_mm=5.0, merge_epsilon_mm=0.1)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(
            width=ast.sheet.width_mm,
            height=ast.sheet.height_mm,
            thickness=sheet_thickness_mm
        )

        passes, summary = plan_passes(
            hints,
            config=config,
            tool_db=tool_db,
            material=material,
            machine=machine,
            stock=stock,
            safe_z=5.0,
        )

        assert len(passes) > 0, "Expected at least 1 planned pass"
        print(f"  [4/4] ✓ Planner integration validated ({len(passes)} passes planned)")

    except RuntimeError as e:
        if "native._native is not available" in str(e):
            print(f"  [4/4] ⊘ Planner execution skipped (native C++ library not available)")
            print("         Pipeline validated up to planner integration")
        else:
            raise

    print("  ✓ PASS - End-to-end pipeline validation complete")
    return True


if __name__ == "__main__":
    tests = [
        test_shaker_v2_basic_panel,
        test_shaker_v2_with_anchors,
        test_shaker_v2_removal_intent_generation,
        test_shaker_v2_geometry_verification,
        test_shaker_v2_svg_export,
        test_shaker_v2_inner_dimensions,
        test_shaker_v2_no_panel_recess,
        test_shaker_v2_invalid_dimensions,
        test_shaker_v2_ast_json_serialization,
        test_shaker_v2_end_to_end_pipeline_validation,
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

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} Shaker template tests passed")

    sys.exit(0 if all(results) else 1)
