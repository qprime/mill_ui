from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from layout_ast.layout import LayoutAST


def test_parse_minimal_layout():
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

        assert ast.sheet.width_mm == 200.0
        assert ast.sheet.height_mm == 100.0
        assert ast.sheet.thickness_mm == 12.0

        assert len(ast.items) == 1
        item = ast.items[0]
        assert item.kind == "shape"
        assert item.type == "Rect"
        assert item.geometry is not None
        assert item.placement is not None
        assert item.feature is not None
        assert item.geometry.data["w_mm"] == 50.0
        assert item.geometry.data["h_mm"] == 30.0
        assert item.placement.center_xy_mm == (60.0, 40.0)
        assert item.feature.type == "profile"
        assert item.feature.is_through

        assert ast.config == {}
    finally:
        Path(temp_path).unlink()


def test_parse_layout_with_multiple_items():
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

        assert ast.sheet.width_mm == 300.0
        assert ast.sheet.height_mm == 200.0
        assert ast.sheet.thickness_mm == 18.0

        assert len(ast.items) == 3

        item0 = ast.items[0]
        assert item0.type == "Rect"
        assert item0.feature is not None
        assert item0.feature.type == "profile"
        assert item0.feature.side == "outside"
        assert item0.shape_id == "rect1"

        item1 = ast.items[1]
        assert item1.type == "Circle"
        assert item1.geometry is not None
        assert item1.feature is not None
        assert item1.geometry.data["diameter_mm"] == 20.0
        assert item1.feature.type == "hole"
        assert item1.feature.depth_mm == 10.0
        assert item1.shape_id == "hole1"

        item2 = ast.items[2]
        assert item2.type == "Rect"
        assert item2.feature is not None
        assert item2.feature.type == "pocket"
        assert item2.feature.depth_mm == 5.0
        assert item2.shape_id is None

        assert ast.config["material"] == "MDF"
        assert ast.config["tool_db"] == "default"
    finally:
        Path(temp_path).unlink()


def test_parse_empty_items():
    layout_data: dict[str, Any] = {
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
    layout_data: dict[str, Any] = {
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
    with pytest.raises(FileNotFoundError, match="Layout file not found"):
        LayoutAST.from_json("/nonexistent/path/layout.json")


def test_parse_preserves_numeric_precision():
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
        item0 = ast.items[0]
        assert item0.placement is not None
        assert item0.feature is not None
        assert item0.placement.center_xy_mm == (60.35, 40.75)
        assert item0.feature.depth_mm == 3.175
    finally:
        Path(temp_path).unlink()


def test_parse_rejects_template_item():
    layout_data = {
        "sheet": {"width_mm": 200.0, "height_mm": 100.0, "thickness_mm": 12.0},
        "items": [{"kind": "template", "type": "ShakerDoor", "id": "door", "params": {"length_mm": 200.0}}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="no longer supported"):
            LayoutAST.from_json(temp_path)
    finally:
        Path(temp_path).unlink()


def test_face_and_min_web_survive_json_roundtrip():
    from layout_ast.emitters import emit_layout_json
    from layout_ast.layout import Feature, Geometry, Item, Placement, Sheet

    ast = LayoutAST(
        sheet=Sheet(width_mm=400.0, height_mm=600.0, thickness_mm=19.0, min_web_mm=4.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 35.0}),
                placement=Placement(center_xy_mm=(40.0, 100.0)),
                feature=Feature(type="pocket", depth_mm=12.5, face="back"),
                shape_id="hinge_cup",
            ),
        ),
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(emit_layout_json(ast))
        temp_path = f.name

    try:
        reparsed = LayoutAST.from_json(temp_path)
        assert reparsed.sheet.min_web_mm == 4.0
        feature = reparsed.items[0].feature
        assert feature is not None
        assert feature.face == "back"
    finally:
        Path(temp_path).unlink()


def test_out_of_band_face_rejected_by_json_reader():
    document = {
        "sheet": {"width_mm": 400.0, "height_mm": 600.0, "thickness_mm": 19.0},
        "items": [
            {
                "kind": "shape",
                "type": "Circle",
                "shape_id": "hinge_cup",
                "geometry": {"diameter_mm": 35.0},
                "placement": {"center_xy_mm": [40.0, 100.0]},
                "feature": {"type": "pocket", "depth_mm": 12.5, "face": "Back"},
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(document, f)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Invalid face 'Back'"):
            LayoutAST.from_json(temp_path)
    finally:
        Path(temp_path).unlink()
