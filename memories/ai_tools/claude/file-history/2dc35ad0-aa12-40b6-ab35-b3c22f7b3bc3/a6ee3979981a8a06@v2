"""Round-trip tests for LayoutAST JSON emission.

Stage 3 acceptance tests: json → AST → json preserves semantics.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from skills.mill_ui.v2.ast.layout import LayoutAST


def test_roundtrip_minimal_shape_layout():
    """Test round-trip for minimal shape-based layout."""
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
        # Parse
        ast = LayoutAST.from_json(temp_path)

        # Emit
        json_str = ast.to_json()

        # Parse emitted JSON
        emitted_data = json.loads(json_str)

        # Verify semantic equivalence
        assert emitted_data["sheet"]["width_mm"] == layout_data["sheet"]["width_mm"]
        assert emitted_data["sheet"]["height_mm"] == layout_data["sheet"]["height_mm"]
        assert emitted_data["sheet"]["thickness_mm"] == layout_data["sheet"]["thickness_mm"]
        assert len(emitted_data["items"]) == len(layout_data["items"])

        # Verify item details
        emitted_item = emitted_data["items"][0]
        original_item = layout_data["items"][0]
        assert emitted_item["kind"] == original_item["kind"]
        assert emitted_item["type"] == original_item["type"]
        assert emitted_item["geometry"]["w_mm"] == original_item["geometry"]["w_mm"]
        assert emitted_item["feature"]["type"] == original_item["feature"]["type"]
    finally:
        Path(temp_path).unlink()


def test_roundtrip_cnc_clamp_v1_layout():
    """Test round-trip for real cnc_clamp_v1 template layout."""
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip(f"Test layout not found: {layout_path}")

    # Parse original
    ast = LayoutAST.from_json(str(layout_path))

    # Emit to JSON
    json_str = ast.to_json()

    # Parse emitted JSON into new AST
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_path = f.name

    try:
        ast2 = LayoutAST.from_json(temp_path)

        # Verify semantic equivalence
        assert ast2.project == ast.project
        assert ast2.kerf_width_mm == ast.kerf_width_mm
        assert ast2.sheet.width_mm == ast.sheet.width_mm
        assert ast2.sheet.height_mm == ast.sheet.height_mm
        assert ast2.sheet.thickness_mm == ast.sheet.thickness_mm
        assert len(ast2.items) == len(ast.items)

        # Verify template item
        item1 = ast.items[0]
        item2 = ast2.items[0]
        assert item2.kind == item1.kind
        assert item2.type == item1.type
        assert item2.id == item1.id
        assert item2.params == item1.params
    finally:
        Path(temp_path).unlink()


def test_roundtrip_mandelbrot_demo_layout():
    """Test round-trip for mandelbrot_demo layout."""
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "mandelbrot_demo" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip(f"Test layout not found: {layout_path}")

    # Parse original
    ast = LayoutAST.from_json(str(layout_path))

    # Emit to JSON
    json_str = ast.to_json()

    # Parse emitted JSON
    emitted_data = json.loads(json_str)

    # Verify semantic equivalence
    assert emitted_data["project"] == "mandelbrot_demo"
    assert emitted_data["kerf_width_mm"] == 3.175
    assert emitted_data["sheet"]["width_mm"] == 400.0
    assert len(emitted_data["items"]) == 1
    assert emitted_data["items"][0]["kind"] == "template"
    assert emitted_data["items"][0]["type"] == "MandelbrotOutlineFill"


def test_roundtrip_cnc_clamp_part_a_layout():
    """Test round-trip for cnc_clamp-part_a_layout."""
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp-part_a_layout" / "input" / "layout.json"

    if not layout_path.exists():
        pytest.skip(f"Test layout not found: {layout_path}")

    # Parse original
    ast = LayoutAST.from_json(str(layout_path))

    # Emit to JSON
    json_str = ast.to_json()

    # Parse emitted JSON
    emitted_data = json.loads(json_str)

    # Verify semantic equivalence
    assert emitted_data["layout"]["cols"] == 2
    assert emitted_data["layout"]["rows"] == 2
    assert len(emitted_data["items"]) == 1


def test_deterministic_emission():
    """Test that emitted JSON is deterministic (hash-stable)."""
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
        # Parse once
        ast = LayoutAST.from_json(temp_path)

        # Emit multiple times
        json_str1 = ast.to_json()
        json_str2 = ast.to_json()
        json_str3 = ast.to_json()

        # Verify identical output
        assert json_str1 == json_str2
        assert json_str2 == json_str3

        # Verify hash stability
        hash1 = hashlib.sha256(json_str1.encode()).hexdigest()
        hash2 = hashlib.sha256(json_str2.encode()).hexdigest()
        hash3 = hashlib.sha256(json_str3.encode()).hexdigest()

        assert hash1 == hash2 == hash3
    finally:
        Path(temp_path).unlink()


def test_roundtrip_with_config():
    """Test round-trip preserves config field."""
    layout_data = {
        "sheet": {"width_mm": 200.0, "height_mm": 100.0, "thickness_mm": 12.0},
        "items": [],
        "config": {"material": "MDF", "tool_db": "default"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        ast = LayoutAST.from_json(temp_path)
        json_str = ast.to_json()
        emitted_data = json.loads(json_str)

        assert emitted_data["config"]["material"] == "MDF"
        assert emitted_data["config"]["tool_db"] == "default"
    finally:
        Path(temp_path).unlink()


def test_roundtrip_multiple_items():
    """Test round-trip with multiple shape items."""
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
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        ast = LayoutAST.from_json(temp_path)
        json_str = ast.to_json()
        emitted_data = json.loads(json_str)

        assert len(emitted_data["items"]) == 2
        assert emitted_data["items"][0]["shape_id"] == "rect1"
        assert emitted_data["items"][1]["shape_id"] == "hole1"
        assert emitted_data["items"][1]["feature"]["depth_mm"] == 10.0
    finally:
        Path(temp_path).unlink()
