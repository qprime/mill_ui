"""Tests for LayoutAST JSON parsing.

Stage 2 acceptance tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from skills.mill_ui.v2.ast.layout import LayoutAST


def test_parse_minimal_layout():
    """Test parsing minimal valid layout."""
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
        ast = LayoutAST.from_json(temp_path)

        # Verify sheet
        assert ast.sheet.width_mm == 200.0
        assert ast.sheet.height_mm == 100.0
        assert ast.sheet.thickness_mm == 12.0

        # Verify items
        assert len(ast.items) == 1
        item = ast.items[0]
        assert item.kind == "shape"
        assert item.type == "Rect"
        assert item.geometry.data["w_mm"] == 50.0
        assert item.geometry.data["h_mm"] == 30.0
        assert item.placement.center_xy_mm == (60.0, 40.0)
        assert item.feature.type == "profile"
        assert item.feature.depth == "through"

        # Verify config (empty by default)
        assert ast.config == {}
    finally:
        Path(temp_path).unlink()


def test_parse_layout_with_multiple_items():
    """Test parsing layout with multiple items."""
    layout_data = {
        "sheet": {"width_mm": 300.0, "height_mm": 200.0, "thickness_mm": 18.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 50.0, "h_mm": 30.0},
                "placement": {"center_xy_mm": [60.0, 40.0]},
                "feature": {"type": "profile", "depth": "through", "side": "outside"},
                "shape_id": "rect1",
            },
            {
                "kind": "shape",
                "type": "Circle",
                "geometry": {"diameter_mm": 20.0},
                "placement": {"center_xy_mm": [150.0, 100.0]},
                "feature": {"type": "hole", "depth_mm": 10.0},
                "shape_id": "hole1",
            },
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 40.0, "h_mm": 40.0},
                "placement": {"center_xy_mm": [240.0, 160.0]},
                "feature": {"type": "pocket", "depth_mm": 5.0},
            },
        ],
        "config": {"material": "MDF", "tool_db": "default"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        ast = LayoutAST.from_json(temp_path)

        # Verify sheet
        assert ast.sheet.width_mm == 300.0
        assert ast.sheet.height_mm == 200.0
        assert ast.sheet.thickness_mm == 18.0

        # Verify item count
        assert len(ast.items) == 3

        # Verify first item (profile with side)
        item0 = ast.items[0]
        assert item0.type == "Rect"
        assert item0.feature.type == "profile"
        assert item0.feature.side == "outside"
        assert item0.shape_id == "rect1"

        # Verify second item (hole with depth_mm)
        item1 = ast.items[1]
        assert item1.type == "Circle"
        assert item1.geometry.data["diameter_mm"] == 20.0
        assert item1.feature.type == "hole"
        assert item1.feature.depth_mm == 10.0
        assert item1.shape_id == "hole1"

        # Verify third item (pocket, no shape_id)
        item2 = ast.items[2]
        assert item2.type == "Rect"
        assert item2.feature.type == "pocket"
        assert item2.feature.depth_mm == 5.0
        assert item2.shape_id is None

        # Verify config
        assert ast.config["material"] == "MDF"
        assert ast.config["tool_db"] == "default"
    finally:
        Path(temp_path).unlink()


def test_parse_empty_items():
    """Test parsing layout with no items."""
    layout_data = {
        "sheet": {"width_mm": 100.0, "height_mm": 100.0, "thickness_mm": 6.0},
        "items": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        ast = LayoutAST.from_json(temp_path)
        assert len(ast.items) == 0
        assert ast.sheet.width_mm == 100.0
    finally:
        Path(temp_path).unlink()


def test_parse_missing_sheet():
    """Test that missing sheet field raises ValueError."""
    layout_data = {
        "items": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="missing required 'sheet' field"):
            LayoutAST.from_json(temp_path)
    finally:
        Path(temp_path).unlink()


def test_parse_nonexistent_file():
    """Test that nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Layout file not found"):
        LayoutAST.from_json("/nonexistent/path/layout.json")


def test_parse_preserves_numeric_precision():
    """Test that numeric values are preserved with proper precision."""
    layout_data = {
        "sheet": {"width_mm": 203.2, "height_mm": 101.6, "thickness_mm": 12.7},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 50.8, "h_mm": 30.5},
                "placement": {"center_xy_mm": [60.35, 40.75]},
                "feature": {"type": "pocket", "depth_mm": 3.175},
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        ast = LayoutAST.from_json(temp_path)
        assert ast.sheet.width_mm == 203.2
        assert ast.sheet.thickness_mm == 12.7
        assert ast.items[0].placement.center_xy_mm == (60.35, 40.75)
        assert ast.items[0].feature.depth_mm == 3.175
    finally:
        Path(temp_path).unlink()


def test_parse_cnc_clamp_v1_layout():
    """Test parsing real cnc_clamp_v1 layout (template-based v1 structure)."""
    # Path relative to repository root
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip(f"Test layout not found: {layout_path}")

    ast = LayoutAST.from_json(str(layout_path))

    # Verify top-level v1 fields
    assert ast.project == "cnc_clamp_v1"
    assert ast.kerf_width_mm == 6.35
    assert ast.cam is not None
    assert ast.layout is not None

    # Verify sheet
    assert ast.sheet.width_mm == 800.0
    assert ast.sheet.height_mm == 250.0
    assert ast.sheet.thickness_mm == 19.1

    # Verify items
    assert len(ast.items) == 1
    item = ast.items[0]
    assert item.kind == "template"
    assert item.type == "ClampBar"
    assert item.id == "clamp_bar"
    assert item.params is not None
    assert "length_mm" in item.params
    assert item.params["length_mm"] == 200.0

    # Verify template items don't have shape fields
    assert item.geometry is None
    assert item.placement is None
    assert item.feature is None


def test_parse_mandelbrot_demo_layout():
    """Test parsing mandelbrot_demo layout (template-based)."""
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "mandelbrot_demo" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip(f"Test layout not found: {layout_path}")

    ast = LayoutAST.from_json(str(layout_path))

    # Verify project
    assert ast.project == "mandelbrot_demo"
    assert ast.kerf_width_mm == 3.175

    # Verify sheet
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 300.0
    assert ast.sheet.thickness_mm == 18.0

    # Verify template item
    assert len(ast.items) == 1
    item = ast.items[0]
    assert item.kind == "template"
    assert item.type == "MandelbrotOutlineFill"
    assert item.params is not None


def test_parse_cnc_clamp_part_a_layout():
    """Test parsing cnc_clamp-part_a_layout (template with cols/rows)."""
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp-part_a_layout" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip(f"Test layout not found: {layout_path}")

    ast = LayoutAST.from_json(str(layout_path))

    # Verify layout config
    assert ast.layout is not None
    assert ast.layout["cols"] == 2
    assert ast.layout["rows"] == 2

    # Verify template item
    assert len(ast.items) == 1
    item = ast.items[0]
    assert item.kind == "template"
    assert item.type == "ClampBar"
