"""Unit tests for CLI introspection commands.

Stage 7 acceptance tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from skills.mill_ui.cli.introspect import dump_ast, dump_removal_intent


def test_dump_ast_minimal_layout():
    """Test dump-ast with minimal shape layout."""
    layout_data = {
        "sheet": {"width_mm": 200.0, "height_mm": 100.0, "thickness_mm": 12.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 50.0, "h_mm": 30.0},
                "placement": {"center_xy_mm": [60.0, 40.0]},
                "feature": {"type": "profile", "depth": "through"},
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        # Dump AST
        ast_json = dump_ast(temp_path)

        # Parse output
        ast_data = json.loads(ast_json)

        # Verify structure
        assert "sheet" in ast_data
        assert ast_data["sheet"]["width_mm"] == 200.0
        assert ast_data["sheet"]["thickness_mm"] == 12.0
        assert "items" in ast_data
        assert len(ast_data["items"]) == 1
        assert ast_data["items"][0]["kind"] == "shape"

    finally:
        Path(temp_path).unlink()


def test_dump_ast_deterministic():
    """Test that dump-ast produces deterministic output."""
    layout_data = {
        "sheet": {"width_mm": 100.0, "height_mm": 100.0, "thickness_mm": 19.0},
        "items": [
            {
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": 20.0},
                "placement": {"center_xy_mm": [50.0, 50.0]},
                "feature": {"type": "hole", "depth_mm": 12.0},
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        # Dump AST multiple times
        output1 = dump_ast(temp_path)
        output2 = dump_ast(temp_path)
        output3 = dump_ast(temp_path)

        # Verify deterministic (identical output)
        assert output1 == output2 == output3

    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_profile():
    """Test dump-removal-intent with profile operation."""
    layout_data = {
        "sheet": {"width_mm": 300.0, "height_mm": 200.0, "thickness_mm": 19.1},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 200.0, "h_mm": 100.0},
                "placement": {"center_xy_mm": [150.0, 100.0]},
                "feature": {"type": "profile", "depth": "through", "side": "outside"},
                "shape_id": "outer_rect",
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        # Dump RemovalIntent
        removal_json = dump_removal_intent(temp_path)

        # Parse output
        removal_data = json.loads(removal_json)

        # Verify structure
        assert isinstance(removal_data, list)
        assert len(removal_data) == 1

        intent = removal_data[0]
        assert intent["region_id"] == "profile_outer_rect"
        assert intent["z_top"] == 0.0
        assert intent["z_bottom"] == -19.1
        assert intent["depth_mm"] == pytest.approx(19.1)
        assert "bounds" in intent
        assert intent["bounds"]["x_min"] == pytest.approx(50.0)  # 150 - 100
        assert intent["bounds"]["x_max"] == pytest.approx(250.0)  # 150 + 100

    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_pocket():
    """Test dump-removal-intent with pocket operation."""
    layout_data = {
        "sheet": {"width_mm": 200.0, "height_mm": 200.0, "thickness_mm": 12.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 80.0, "h_mm": 40.0},
                "placement": {"center_xy_mm": [100.0, 100.0]},
                "feature": {"type": "pocket", "depth_mm": 6.0},
                "shape_id": "center_pocket",
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        removal_json = dump_removal_intent(temp_path)
        removal_data = json.loads(removal_json)

        assert len(removal_data) == 1
        intent = removal_data[0]
        assert intent["region_id"] == "pocket_center_pocket"
        assert intent["depth_mm"] == pytest.approx(6.0)
        assert intent["metadata"]["hint_type"] == "pocket"

    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_hole():
    """Test dump-removal-intent with hole operation."""
    layout_data = {
        "sheet": {"width_mm": 150.0, "height_mm": 150.0, "thickness_mm": 19.0},
        "items": [
            {
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": 6.35},
                "placement": {"center_xy_mm": [50.0, 50.0]},
                "feature": {"type": "hole", "depth_mm": 12.0},
                "shape_id": "mount_hole",
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        removal_json = dump_removal_intent(temp_path)
        removal_data = json.loads(removal_json)

        assert len(removal_data) == 1
        intent = removal_data[0]
        assert intent["region_id"] == "hole_mount_hole"
        assert intent["metadata"]["hint_type"] == "hole"
        assert intent["metadata"]["shape"] == "Circle"

    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_multiple_operations():
    """Test dump-removal-intent with multiple operations."""
    layout_data = {
        "sheet": {"width_mm": 400.0, "height_mm": 300.0, "thickness_mm": 19.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 300.0, "h_mm": 200.0},
                "placement": {"center_xy_mm": [200.0, 150.0]},
                "feature": {"type": "profile", "depth": "through", "side": "outside"},
                "shape_id": "outer",
            },
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 100.0, "h_mm": 50.0},
                "placement": {"center_xy_mm": [200.0, 150.0]},
                "feature": {"type": "pocket", "depth_mm": 5.0},
                "shape_id": "inner_pocket",
            },
            {
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": 8.0},
                "placement": {"center_xy_mm": [120.0, 100.0]},
                "feature": {"type": "hole", "depth_mm": 12.0},
                "shape_id": "corner_hole",
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        removal_json = dump_removal_intent(temp_path)
        removal_data = json.loads(removal_json)

        # Verify we got 3 RemovalIntent records
        assert len(removal_data) == 3

        # Verify region IDs
        region_ids = {r["region_id"] for r in removal_data}
        assert "profile_outer" in region_ids
        assert "pocket_inner_pocket" in region_ids
        assert "hole_corner_hole" in region_ids

    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_bounds_calculation():
    """Test that bounds are correctly calculated in dump output."""
    layout_data = {
        "sheet": {"width_mm": 200.0, "height_mm": 200.0, "thickness_mm": 12.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 100.0, "h_mm": 60.0},
                "placement": {"center_xy_mm": [150.0, 100.0]},
                "feature": {"type": "pocket", "depth_mm": 8.0},
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        removal_json = dump_removal_intent(temp_path)
        removal_data = json.loads(removal_json)

        intent = removal_data[0]
        bounds = intent["bounds"]

        # Verify bounds: center (150, 100), w=100, h=60
        assert bounds["x_min"] == pytest.approx(100.0)  # 150 - 50
        assert bounds["x_max"] == pytest.approx(200.0)  # 150 + 50
        assert bounds["y_min"] == pytest.approx(70.0)   # 100 - 30
        assert bounds["y_max"] == pytest.approx(130.0)  # 100 + 30

    finally:
        Path(temp_path).unlink()


def test_dump_ast_parses_successfully():
    """Test that dumped AST can be parsed back successfully."""
    layout_data = {
        "sheet": {"width_mm": 250.0, "height_mm": 150.0, "thickness_mm": 18.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 50.0, "h_mm": 40.0},
                "placement": {"center_xy_mm": [100.0, 75.0]},
                "feature": {"type": "profile", "depth": "through"},
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        # Dump AST
        ast_json = dump_ast(temp_path)

        # Verify it's valid JSON
        ast_data = json.loads(ast_json)

        # Verify we can write it back and parse again
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            f2.write(ast_json)
            temp_path2 = f2.name

        try:
            # Should be able to load the dumped AST
            ast_json2 = dump_ast(temp_path2)
            assert ast_json == ast_json2  # Should be identical (deterministic)

        finally:
            Path(temp_path2).unlink()

    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_real_template():
    """Test dump-removal-intent with real template layout (ClampBar)."""
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip("ClampBar layout not found")

    removal_json = dump_removal_intent(str(layout_path))
    removal_data = json.loads(removal_json)

    # ClampBar template should produce multiple regions
    assert len(removal_data) > 0

    # Verify we got profile and pocket regions
    region_ids = [r["region_id"] for r in removal_data]
    has_profile = any("profile_" in rid for rid in region_ids)
    has_pocket = any("pocket_" in rid for rid in region_ids)

    assert has_profile
    assert has_pocket
