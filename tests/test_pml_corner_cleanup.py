#!/usr/bin/env python3

from pml import parse_pml, format_pml
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


def test_pml_parse_corner_cleanup():
    pml_text = """
sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm corner_cleanup 3.175mm
"""

    ast = parse_pml(pml_text)

    assert len(ast.items) == 1
    item = ast.items[0]

    assert item.shape_id == "panel"
    assert item.type == "Rect"
    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0
    assert item.feature.corner_cleanup_tool_diameter_mm == 3.175


def test_pml_format_corner_cleanup():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(
                    type="pocket",
                    depth=6.0,
                    corner_cleanup_tool_diameter_mm=3.175
                ),
                shape_id="panel"
            ),
        )
    )

    pml_output = format_pml(ast)


    assert "corner_cleanup" in pml_output
    assert "pocket" in pml_output
    assert "3.17mm" in pml_output or "3.18mm" in pml_output


def test_pml_roundtrip_corner_cleanup():
    pml_input = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm corner_cleanup 3.175mm
"""


    ast1 = parse_pml(pml_input)
    pml_middle = format_pml(ast1)
    ast2 = parse_pml(pml_middle)


    assert abs(ast1.items[0].feature.corner_cleanup_tool_diameter_mm - ast2.items[0].feature.corner_cleanup_tool_diameter_mm) < 0.01
    assert ast1.items[0].feature.depth_mm == ast2.items[0].feature.depth_mm


def test_pml_pocket_without_corner_cleanup():
    pml_text = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm
"""

    ast = parse_pml(pml_text)
    item = ast.items[0]

    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0
    assert item.feature.corner_cleanup_tool_diameter_mm is None


def test_pml_corner_cleanup_error_invalid_token():
    pml_text = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm invalid_token 3.175mm
"""

    try:
        parse_pml(pml_text)
        assert False, "Expected parse error"
    except Exception as e:
        error_msg = str(e).lower()
        assert "unexpected token" in error_msg or "expected 'corner_cleanup'" in error_msg or "expected end of line" in error_msg


def test_pml_corner_cleanup_through_depth():
    pml_text = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket through corner_cleanup 3.175mm
"""

    ast = parse_pml(pml_text)
    item = ast.items[0]

    assert item.feature.type == "pocket"
    assert item.feature.depth == "through"
    assert item.feature.corner_cleanup_tool_diameter_mm == 3.175


if __name__ == "__main__":
    print("Running PML corner cleanup syntax tests...")

    test_pml_parse_corner_cleanup()
    print("✓ test_pml_parse_corner_cleanup")

    test_pml_format_corner_cleanup()
    print("✓ test_pml_format_corner_cleanup")

    test_pml_roundtrip_corner_cleanup()
    print("✓ test_pml_roundtrip_corner_cleanup")

    test_pml_pocket_without_corner_cleanup()
    print("✓ test_pml_pocket_without_corner_cleanup")

    test_pml_corner_cleanup_error_invalid_token()
    print("✓ test_pml_corner_cleanup_error_invalid_token")

    test_pml_corner_cleanup_through_depth()
    print("✓ test_pml_corner_cleanup_through_depth")

    print("\nAll PML corner cleanup tests passed!")
