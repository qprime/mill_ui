
import json
import sys
import tempfile
from pathlib import Path

from cli.introspect import dump_ast, dump_removal_intent


def approx_equal(a: float, b: float, rel: float = 1e-9) -> bool:
    return abs(a - b) <= rel * max(abs(a), abs(b), 1.0)


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

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


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

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


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
        assert approx_equal(intent["depth_mm"], 19.1)
        assert "bounds" in intent
        assert approx_equal(intent["bounds"]["x_min"], 50.0)
        assert approx_equal(intent["bounds"]["x_max"], 250.0)

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_multiple():
    print("Running test_dump_removal_intent_multiple...")
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

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_bounds():
    print("Running test_dump_removal_intent_bounds...")
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

        assert approx_equal(bounds["x_min"], 100.0)
        assert approx_equal(bounds["x_max"], 200.0)
        assert approx_equal(bounds["y_min"], 70.0)
        assert approx_equal(bounds["y_max"], 130.0)

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_dump_removal_intent_real_template():
    print("Running test_dump_removal_intent_real_template...")


    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        print("  ⊘ SKIP: ClampBar layout not found")
        return None

    removal_json = dump_removal_intent(str(layout_path))
    removal_data = json.loads(removal_json)


    assert len(removal_data) > 0, f"Expected RemovalIntent regions, got {len(removal_data)}"


    region_ids = [r["region_id"] for r in removal_data]
    has_profile = any("profile_" in rid for rid in region_ids)
    has_pocket = any("pocket_" in rid for rid in region_ids)

    assert has_profile, "Expected at least one profile region"
    assert has_pocket, "Expected at least one pocket region"

    print(f"  ✓ PASS ({len(removal_data)} regions from template)")
    return True


if __name__ == "__main__":
    tests = [
        test_dump_ast_minimal_layout,
        test_dump_ast_deterministic,
        test_dump_removal_intent_profile,
        test_dump_removal_intent_multiple,
        test_dump_removal_intent_bounds,
        test_dump_removal_intent_real_template,
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

    # Filter out None (skipped tests) for counting
    actual_results = [r for r in results if r is not None]
    passed = sum(1 for r in actual_results if r)
    total = len(actual_results)
    skipped = len(results) - len(actual_results)

    skip_msg = f" ({skipped} skipped)" if skipped > 0 else ""
    print(f"\n{passed}/{total} CLI dump tests passed{skip_msg}")

    sys.exit(0 if all(r for r in actual_results) else 1)
