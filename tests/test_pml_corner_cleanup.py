#!/usr/bin/env python3
"""Tests for PML corner cleanup syntax."""

from pml import parse_pml, format_pml
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


def test_pml_parse_corner_cleanup():
    """Test parsing PML with corner_cleanup syntax."""
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
    """Test formatting AST with corner cleanup to PML."""
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

    # Check that corner_cleanup appears in output
    assert "corner_cleanup" in pml_output
    assert "pocket" in pml_output
    assert "3.17mm" in pml_output or "3.18mm" in pml_output


def test_pml_roundtrip_corner_cleanup():
    """Test PML roundtrip with corner cleanup preserves semantics."""
    pml_input = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm corner_cleanup 3.175mm
"""

    # Parse → Format → Parse
    ast1 = parse_pml(pml_input)
    pml_middle = format_pml(ast1)
    ast2 = parse_pml(pml_middle)

    # Should be semantically equivalent (within formatting precision)
    # Note: Formatter uses 2 decimal places, so 3.175 → 3.17
    assert abs(ast1.items[0].feature.corner_cleanup_tool_diameter_mm - ast2.items[0].feature.corner_cleanup_tool_diameter_mm) < 0.01
    assert ast1.items[0].feature.depth_mm == ast2.items[0].feature.depth_mm


def test_pml_pocket_without_corner_cleanup():
    """Test that pocket without corner_cleanup parses correctly."""
    pml_text = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm
"""

    ast = parse_pml(pml_text)
    item = ast.items[0]

    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0
    assert item.feature.corner_cleanup_tool_diameter_mm is None


def test_pml_corner_cleanup_error_invalid_token():
    """Test error when invalid token after pocket depth."""
    pml_text = """sheet 200mm 150mm 19mm

rect panel at 100mm,75mm size 100mm,80mm pocket 6mm invalid_token 3.175mm
"""

    try:
        parse_pml(pml_text)
        assert False, "Expected parse error"
    except Exception as e:
        assert "unexpected token" in str(e).lower() or "expected 'corner_cleanup'" in str(e).lower()


def test_pml_corner_cleanup_through_depth():
    """Test corner_cleanup with 'through' depth."""
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
