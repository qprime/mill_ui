from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from layout_ast.layout import LayoutAST


def test_roundtrip_minimal_shape_layout():
    layout_data: dict[str, Any] = {
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
        json_str = ast.to_json()
        emitted_data = json.loads(json_str)

        assert emitted_data["sheet"]["width_mm"] == layout_data["sheet"]["width_mm"]
        assert emitted_data["sheet"]["height_mm"] == layout_data["sheet"]["height_mm"]
        assert emitted_data["sheet"]["thickness_mm"] == layout_data["sheet"]["thickness_mm"]
        assert len(emitted_data["items"]) == len(layout_data["items"])

        emitted_item = emitted_data["items"][0]
        original_item = layout_data["items"][0]
        assert emitted_item["kind"] == original_item["kind"]
        assert emitted_item["type"] == original_item["type"]
        assert emitted_item["geometry"]["w_mm"] == original_item["geometry"]["w_mm"]
        assert emitted_item["feature"]["type"] == original_item["feature"]["type"]
    finally:
        Path(temp_path).unlink()


def test_roundtrip_cnc_clamp_v1_layout():
    layout_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "memories"
        / "cam_projects"
        / "sheet_layouts"
        / "cnc_clamp_v1"
        / "input"
        / "layout.json"
    )

    if not layout_path.exists():
        pytest.skip("Test layout not found")

    ast = LayoutAST.from_json(str(layout_path))
    json_str = ast.to_json()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_path = f.name

    try:
        ast2 = LayoutAST.from_json(temp_path)

        assert ast2.project == ast.project
        assert ast2.kerf_width_mm == ast.kerf_width_mm
        assert ast2.sheet.width_mm == ast.sheet.width_mm
        assert ast2.sheet.height_mm == ast.sheet.height_mm
        assert ast2.sheet.thickness_mm == ast.sheet.thickness_mm
        assert len(ast2.items) == len(ast.items)

        item1 = ast.items[0]
        item2 = ast2.items[0]
        assert item2.kind == item1.kind
        assert item2.type == item1.type
        assert item2.id == item1.id
        assert item2.params == item1.params
    finally:
        Path(temp_path).unlink()


def test_roundtrip_cnc_clamp_part_a_layout():
    layout_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "memories"
        / "cam_projects"
        / "sheet_layouts"
        / "cnc_clamp-part_a_layout"
        / "input"
        / "layout.json"
    )

    if not layout_path.exists():
        pytest.skip("Test layout not found")

    ast = LayoutAST.from_json(str(layout_path))
    json_str = ast.to_json()
    emitted_data = json.loads(json_str)

    assert emitted_data["layout"]["cols"] == 2
    assert emitted_data["layout"]["rows"] == 2
    assert len(emitted_data["items"]) == 1


def test_deterministic_emission():
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

        json_str1 = ast.to_json()
        json_str2 = ast.to_json()
        json_str3 = ast.to_json()

        assert json_str1 == json_str2
        assert json_str2 == json_str3

        hash1 = hashlib.sha256(json_str1.encode()).hexdigest()
        hash2 = hashlib.sha256(json_str2.encode()).hexdigest()
        hash3 = hashlib.sha256(json_str3.encode()).hexdigest()

        assert hash1 == hash2 == hash3
    finally:
        Path(temp_path).unlink()


def test_roundtrip_with_config():
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


def test_roundtrip_all_feature_fields():
    layout_data = {
        "sheet": {"width_mm": 300.0, "height_mm": 300.0, "thickness_mm": 19.0},
        "items": [
            {
                "kind": "shape",
                "type": "Rect",
                "geometry": {"w_mm": 200.0, "h_mm": 200.0},
                "placement": {"center_xy_mm": [150.0, 150.0]},
                "feature": {
                    "type": "profile",
                    "depth": "through",
                    "side": "outside",
                    "corner_cleanup_tool_diameter_mm": 3.0,
                    "dogbone": {"style": "t-bone_x", "diameter_mm": 6.0, "overcut_mm": 0.5},
                    "rest": {"tool_diameter_mm": 3.0, "rough_allowance_mm": 0.3, "finish_allowance_mm": 0.1},
                    "tab_count": 4,
                    "tab_height_mm": 3.0,
                    "tab_width_mm": 10.0,
                    "onion_skin_mm": 0.2,
                    "bevel_width_mm": 2.0,
                    "bevel_angle_deg": 45.0,
                    "bevel_inner_depth_mm": 1.0,
                    "chamfer_width_mm": 1.5,
                    "chamfer_angle_deg": 30.0,
                    "roundover_radius_mm": 3.0,
                    "feeds_override": {
                        "rpm": 18000.0,
                        "feed_xy": 1500.0,
                        "feed_z": 500.0,
                        "depth_per_pass": 2.0,
                        "stepover_percent": 40.0,
                    },
                },
                "shape_id": "full_feature",
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        ast = LayoutAST.from_json(temp_path)
        feat = ast.items[0].feature
        assert feat is not None

        assert feat.corner_cleanup_tool_diameter_mm == 3.0
        assert feat.dogbone is not None
        assert feat.dogbone.style == "t-bone_x"
        assert feat.dogbone.diameter_mm == 6.0
        assert feat.dogbone.overcut_mm == 0.5
        assert feat.rest is not None
        assert feat.rest.tool_diameter_mm == 3.0
        assert feat.rest.rough_allowance_mm == 0.3
        assert feat.rest.finish_allowance_mm == 0.1
        assert feat.tab_count == 4
        assert feat.tab_height_mm == 3.0
        assert feat.tab_width_mm == 10.0
        assert feat.onion_skin_mm == 0.2
        assert feat.roundover_radius_mm == 3.0
        assert feat.feeds_override is not None
        assert feat.feeds_override.rpm == 18000.0
        assert feat.feeds_override.feed_xy == 1500.0

        json_str = ast.to_json()
        emitted = json.loads(json_str)
        ef = emitted["items"][0]["feature"]

        assert ef["dogbone"]["style"] == "t-bone_x"
        assert ef["dogbone"]["diameter_mm"] == 6.0
        assert ef["rest"]["tool_diameter_mm"] == 3.0
        assert ef["onion_skin_mm"] == 0.2
        assert ef["roundover_radius_mm"] == 3.0
        assert ef["feeds_override"]["rpm"] == 18000.0

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            f2.write(json_str)
            temp_path2 = f2.name

        ast2 = LayoutAST.from_json(temp_path2)
        feat2 = ast2.items[0].feature
        assert feat == feat2
        Path(temp_path2).unlink()
    finally:
        Path(temp_path).unlink()
