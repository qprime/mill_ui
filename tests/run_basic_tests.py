"""Basic test runner for Stage 2 acceptance tests (without pytest).

Run from repository root: PYTHONPATH=. python3 -m tests.run_basic_tests
"""

import json
import tempfile
from pathlib import Path
import sys

from layout_ast.layout import LayoutAST


def test_parse_minimal_layout():
    """Test parsing minimal valid layout."""
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

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_parse_layout_with_multiple_items():
    """Test parsing layout with multiple items."""
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

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_parse_missing_sheet():
    """Test that missing sheet field raises ValueError."""
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
            print("  ✗ FAIL: Expected ValueError")
            return False
        except ValueError as e:
            if "missing required 'sheet' field" in str(e):
                print("  ✓ PASS")
                return True
            else:
                print(f"  ✗ FAIL: Wrong error message: {e}")
                return False
    finally:
        Path(temp_path).unlink()


def test_parse_nonexistent_file():
    """Test that nonexistent file raises FileNotFoundError."""
    print("Running test_parse_nonexistent_file...")
    try:
        LayoutAST.from_json("/nonexistent/path/layout.json")
        print("  ✗ FAIL: Expected FileNotFoundError")
        return False
    except FileNotFoundError:
        print("  ✓ PASS")
        return True


def test_parse_real_cnc_clamp_v1():
    """Test parsing real cnc_clamp_v1 layout."""
    print("Running test_parse_real_cnc_clamp_v1...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  ⊘ SKIP: Layout not found at {layout_path}")
        return None

    ast = LayoutAST.from_json(str(layout_path))
    assert ast.project == "cnc_clamp_v1"
    assert ast.sheet.width_mm == 800.0
    assert len(ast.items) == 1
    assert ast.items[0].kind == "template"
    assert ast.items[0].type == "ClampBar"
    print("  ✓ PASS")
    return True


def test_parse_real_mandelbrot_demo():
    """Test parsing real mandelbrot_demo layout."""
    print("Running test_parse_real_mandelbrot_demo...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "mandelbrot_demo" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  ⊘ SKIP: Layout not found at {layout_path}")
        return None

    ast = LayoutAST.from_json(str(layout_path))
    assert ast.project == "mandelbrot_demo"
    assert ast.sheet.width_mm == 400.0
    assert len(ast.items) == 1
    assert ast.items[0].kind == "template"
    print("  ✓ PASS")
    return True


def test_parse_real_cnc_clamp_part_a():
    """Test parsing real cnc_clamp-part_a_layout."""
    print("Running test_parse_real_cnc_clamp_part_a...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp-part_a_layout" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  ⊘ SKIP: Layout not found at {layout_path}")
        return None

    ast = LayoutAST.from_json(str(layout_path))
    assert ast.layout["cols"] == 2
    assert len(ast.items) == 1
    assert ast.items[0].kind == "template"
    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_parse_minimal_layout,
        test_parse_layout_with_multiple_items,
        test_parse_missing_sheet,
        test_parse_nonexistent_file,
        test_parse_real_cnc_clamp_v1,
        test_parse_real_mandelbrot_demo,
        test_parse_real_cnc_clamp_part_a,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            if result is not None:  # None means skipped
                results.append(result)
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")

    sys.exit(0 if all(results) else 1)
