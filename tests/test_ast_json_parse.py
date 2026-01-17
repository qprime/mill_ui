
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from layout_ast.layout import LayoutAST


def test_parse_minimal_layout():
    print("Running test_parse_minimal_layout...")
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
        assert item.geometry.data["w_mm"] == 50.0
        assert item.geometry.data["h_mm"] == 30.0
        assert item.placement.center_xy_mm == (60.0, 40.0)
        assert item.feature.type == "profile"
        assert item.feature.depth == "through"


        assert ast.config == {}
    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_parse_layout_with_multiple_items():
    print("Running test_parse_layout_with_multiple_items...")
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
        assert item0.feature.type == "profile"
        assert item0.feature.side == "outside"
        assert item0.shape_id == "rect1"


        item1 = ast.items[1]
        assert item1.type == "Circle"
        assert item1.geometry.data["diameter_mm"] == 20.0
        assert item1.feature.type == "hole"
        assert item1.feature.depth_mm == 10.0
        assert item1.shape_id == "hole1"


        item2 = ast.items[2]
        assert item2.type == "Rect"
        assert item2.feature.type == "pocket"
        assert item2.feature.depth_mm == 5.0
        assert item2.shape_id is None


        assert ast.config["material"] == "MDF"
        assert ast.config["tool_db"] == "default"
    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_parse_empty_items():
    print("Running test_parse_empty_items...")
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
    print("  PASS")
    return True


def test_parse_missing_sheet():
    print("Running test_parse_missing_sheet...")
    layout_data = {
        "items": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(layout_data, f)
        temp_path = f.name

    try:
        try:
            LayoutAST.from_json(temp_path)
            print("  FAIL: Expected ValueError")
            return False
        except ValueError as e:
            if "missing required 'sheet' field" in str(e):
                pass
            else:
                print(f"  FAIL: Wrong error message: {e}")
                return False
    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_parse_nonexistent_file():
    print("Running test_parse_nonexistent_file...")
    try:
        LayoutAST.from_json("/nonexistent/path/layout.json")
        print("  FAIL: Expected FileNotFoundError")
        return False
    except FileNotFoundError as e:
        if "Layout file not found" in str(e):
            pass
        else:
            print(f"  FAIL: Wrong error message: {e}")
            return False
    print("  PASS")
    return True


def test_parse_preserves_numeric_precision():
    print("Running test_parse_preserves_numeric_precision...")
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
    print("  PASS")
    return True


def test_parse_cnc_clamp_v1_layout():
    print("Running test_parse_cnc_clamp_v1_layout...")

    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  SKIP: Test layout not found: {layout_path}")
        return True

    ast = LayoutAST.from_json(str(layout_path))


    assert ast.project == "cnc_clamp_v1"
    assert ast.kerf_width_mm == 6.35
    assert ast.cam is not None
    assert ast.layout is not None


    assert ast.sheet.width_mm == 800.0
    assert ast.sheet.height_mm == 250.0
    assert ast.sheet.thickness_mm == 19.1


    assert len(ast.items) == 1
    item = ast.items[0]
    assert item.kind == "template"
    assert item.type == "ClampBar"
    assert item.id == "clamp_bar"
    assert item.params is not None
    assert "length_mm" in item.params
    assert item.params["length_mm"] == 200.0


    assert item.geometry is None
    assert item.placement is None
    assert item.feature is None
    print("  PASS")
    return True


def test_parse_mandelbrot_demo_layout():
    print("Running test_parse_mandelbrot_demo_layout...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "mandelbrot_demo" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  SKIP: Test layout not found: {layout_path}")
        return True

    ast = LayoutAST.from_json(str(layout_path))


    assert ast.project == "mandelbrot_demo"
    assert ast.kerf_width_mm == 3.175


    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 300.0
    assert ast.sheet.thickness_mm == 18.0


    assert len(ast.items) == 1
    item = ast.items[0]
    assert item.kind == "template"
    assert item.type == "MandelbrotOutlineFill"
    assert item.params is not None
    print("  PASS")
    return True


def test_parse_cnc_clamp_part_a_layout():
    print("Running test_parse_cnc_clamp_part_a_layout...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp-part_a_layout" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  SKIP: Test layout not found: {layout_path}")
        return True

    ast = LayoutAST.from_json(str(layout_path))


    assert ast.layout is not None
    assert ast.layout["cols"] == 2
    assert ast.layout["rows"] == 2


    assert len(ast.items) == 1
    item = ast.items[0]
    assert item.kind == "template"
    assert item.type == "ClampBar"
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_parse_minimal_layout,
        test_parse_layout_with_multiple_items,
        test_parse_empty_items,
        test_parse_missing_sheet,
        test_parse_nonexistent_file,
        test_parse_preserves_numeric_precision,
        test_parse_cnc_clamp_v1_layout,
        test_parse_mandelbrot_demo_layout,
        test_parse_cnc_clamp_part_a_layout,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
