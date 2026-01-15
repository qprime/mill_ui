
import hashlib
import json
import tempfile
from pathlib import Path
import sys

from layout_ast.layout import LayoutAST


def test_roundtrip_minimal_shape_layout():
    print("Running test_roundtrip_minimal_shape_layout...")
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


        json_str = ast.to_json()


        emitted_data = json.loads(json_str)


        assert emitted_data["sheet"]["width_mm"] == layout_data["sheet"]["width_mm"]
        assert len(emitted_data["items"]) == len(layout_data["items"])
        assert emitted_data["items"][0]["kind"] == layout_data["items"][0]["kind"]

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_roundtrip_cnc_clamp_v1():
    print("Running test_roundtrip_cnc_clamp_v1...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp_v1" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  ⊘ SKIP: Layout not found")
        return None


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
        assert len(ast2.items) == len(ast.items)
        assert ast2.items[0].kind == ast.items[0].kind
        assert ast2.items[0].params == ast.items[0].params

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_roundtrip_mandelbrot_demo():
    print("Running test_roundtrip_mandelbrot_demo...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "mandelbrot_demo" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  ⊘ SKIP: Layout not found")
        return None

    ast = LayoutAST.from_json(str(layout_path))
    json_str = ast.to_json()
    emitted_data = json.loads(json_str)

    assert emitted_data["project"] == "mandelbrot_demo"
    assert emitted_data["kerf_width_mm"] == 3.175
    assert emitted_data["sheet"]["width_mm"] == 400.0
    assert len(emitted_data["items"]) == 1

    print("  ✓ PASS")
    return True


def test_roundtrip_cnc_clamp_part_a():
    print("Running test_roundtrip_cnc_clamp_part_a...")
    layout_path = Path(__file__).parent.parent.parent.parent.parent / "memories" / "cam_projects" / "sheet_layouts" / "cnc_clamp-part_a_layout" / "input" / "layout.json"

    if not layout_path.exists():
        print(f"  ⊘ SKIP: Layout not found")
        return None

    ast = LayoutAST.from_json(str(layout_path))
    json_str = ast.to_json()
    emitted_data = json.loads(json_str)

    assert emitted_data["layout"]["cols"] == 2
    assert emitted_data["layout"]["rows"] == 2
    assert len(emitted_data["items"]) == 1

    print("  ✓ PASS")
    return True


def test_deterministic_emission():
    print("Running test_deterministic_emission...")
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


        assert json_str1 == json_str2 == json_str3


        hash1 = hashlib.sha256(json_str1.encode()).hexdigest()
        hash2 = hashlib.sha256(json_str2.encode()).hexdigest()
        assert hash1 == hash2

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


if __name__ == "__main__":
    tests = [
        test_roundtrip_minimal_shape_layout,
        test_roundtrip_cnc_clamp_v1,
        test_roundtrip_mandelbrot_demo,
        test_roundtrip_cnc_clamp_part_a,
        test_deterministic_emission,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            if result is not None:
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
