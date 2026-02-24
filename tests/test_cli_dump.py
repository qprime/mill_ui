
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from cli.introspect import dump_ast, dump_removal_intent


def approx_eq(a, b, rel=1e-6):
    """Check if two values are approximately equal."""
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_dump_ast_minimal_layout():
    print("Running test_dump_ast_minimal_layout...")
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

        ast_json = dump_ast(temp_path)


        ast_data = json.loads(ast_json)


        assert "sheet" in ast_data
        assert ast_data["sheet"]["width_mm"] == 200.0
        assert ast_data["sheet"]["thickness_mm"] == 12.0
        assert "items" in ast_data
        assert len(ast_data["items"]) == 1
        assert ast_data["items"][0]["kind"] == "shape"

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_ast_deterministic():
    print("Running test_dump_ast_deterministic...")
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

        output1 = dump_ast(temp_path)
        output2 = dump_ast(temp_path)
        output3 = dump_ast(temp_path)


        assert output1 == output2 == output3

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_removal_intent_profile():
    print("Running test_dump_removal_intent_profile...")
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

        removal_json = dump_removal_intent(temp_path)


        removal_data = json.loads(removal_json)


        assert isinstance(removal_data, list)
        assert len(removal_data) == 1

        intent = removal_data[0]
        assert intent["region_id"] == "profile_outer_rect"
        # Access z values via depth_profile (Stage 10 schema)
        assert intent["depth_profile"]["z_top"] == 0.0
        assert intent["depth_profile"]["z_bottom"] == -19.1
        assert approx_eq(intent["depth_mm"], 19.1)
        assert "bounds" in intent
        assert approx_eq(intent["bounds"]["x_min"], 50.0)
        assert approx_eq(intent["bounds"]["x_max"], 250.0)

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_removal_intent_pocket():
    print("Running test_dump_removal_intent_pocket...")
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
        assert approx_eq(intent["depth_mm"], 6.0)
        assert intent["hint_type"] == "pocket"

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_removal_intent_hole():
    print("Running test_dump_removal_intent_hole...")
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
        assert intent["hint_type"] == "hole"
        assert intent["shape"] == "Circle"

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_removal_intent_multiple_operations():
    print("Running test_dump_removal_intent_multiple_operations...")
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


        assert len(removal_data) == 3


        region_ids = {r["region_id"] for r in removal_data}
        assert "profile_outer" in region_ids
        assert "pocket_inner_pocket" in region_ids
        assert "hole_corner_hole" in region_ids

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_removal_intent_bounds_calculation():
    print("Running test_dump_removal_intent_bounds_calculation...")
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


        assert approx_eq(bounds["x_min"], 100.0)
        assert approx_eq(bounds["x_max"], 200.0)
        assert approx_eq(bounds["y_min"], 70.0)
        assert approx_eq(bounds["y_max"], 130.0)

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_ast_parses_successfully():
    print("Running test_dump_ast_parses_successfully...")
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

        ast_json = dump_ast(temp_path)


        ast_data = json.loads(ast_json)


        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            f2.write(ast_json)
            temp_path2 = f2.name

        try:

            ast_json2 = dump_ast(temp_path2)
            assert ast_json == ast_json2

        finally:
            Path(temp_path2).unlink()

    finally:
        Path(temp_path).unlink()
    print("  PASS")
    return True


def test_dump_removal_intent_real_template():
    print("Running test_dump_removal_intent_real_template...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        print("  SKIP: ClampBar layout not found")
        return True

    removal_json = dump_removal_intent(str(layout_path))
    removal_data = json.loads(removal_json)


    assert len(removal_data) > 0


    region_ids = [r["region_id"] for r in removal_data]
    has_profile = any("profile_" in rid for rid in region_ids)
    has_pocket = any("pocket_" in rid for rid in region_ids)

    assert has_profile
    assert has_pocket
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_dump_ast_minimal_layout,
        test_dump_ast_deterministic,
        test_dump_removal_intent_profile,
        test_dump_removal_intent_pocket,
        test_dump_removal_intent_hole,
        test_dump_removal_intent_multiple_operations,
        test_dump_removal_intent_bounds_calculation,
        test_dump_ast_parses_successfully,
        test_dump_removal_intent_real_template,
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
