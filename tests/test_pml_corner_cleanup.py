#!/usr/bin/env python3

from pml.yaml_parser import parse_pml_yaml, PMLParseError
from pml.yaml_formatter import format_pml_yaml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


def test_pml_parse_corner_cleanup():
    print("Running test_pml_parse_corner_cleanup...")

    pml_text = """
Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
        corner_cleanup: 3.175mm
"""

    ast = parse_pml_yaml(pml_text)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.shape_id == "panel"
    assert item.type == "Rect"
    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0
    assert item.feature.corner_cleanup_tool_diameter_mm == 3.175

    print("  ✓ PASS")
    return True


def test_pml_format_corner_cleanup():
    print("Running test_pml_format_corner_cleanup...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(
                    type="pocket",
                    depth_mm=6.0,
                    corner_cleanup_tool_diameter_mm=3.175
                ),
                shape_id="panel"
            ),
        )
    )

    pml = """
Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
        corner_cleanup: 3.175mm
"""

    comp_ast = parse_pml_yaml(pml)
    pml_output = format_pml_yaml(comp_ast)

    assert "corner_cleanup" in pml_output
    assert "pocket" in pml_output.lower() or "Pocket" in pml_output
    assert "3.17" in pml_output or "3.18" in pml_output

    print("  ✓ PASS")
    return True


def test_pml_roundtrip_corner_cleanup():
    print("Running test_pml_roundtrip_corner_cleanup...")

    pml_input = """
Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
        corner_cleanup: 3.175mm
"""

    ast1 = parse_pml_yaml(pml_input)
    pml_middle = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(pml_middle)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert abs(flat1.items[0].feature.corner_cleanup_tool_diameter_mm - flat2.items[0].feature.corner_cleanup_tool_diameter_mm) < 0.01
    assert flat1.items[0].feature.depth_mm == flat2.items[0].feature.depth_mm

    print("  ✓ PASS")
    return True


def test_pml_pocket_without_corner_cleanup():
    print("Running test_pml_pocket_without_corner_cleanup...")

    pml_text = """
Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
"""

    ast = parse_pml_yaml(pml_text)
    flat = resolve_layout(ast)
    item = flat.items[0]

    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0
    assert item.feature.corner_cleanup_tool_diameter_mm is None

    print("  ✓ PASS")
    return True


def test_pml_corner_cleanup_error_invalid_token():
    print("Running test_pml_corner_cleanup_error_invalid_token...")

    pml_text = """
Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
        invalid_field: 3.175mm
"""

    ast = parse_pml_yaml(pml_text)
    flat = resolve_layout(ast)
    assert flat.items[0].feature.corner_cleanup_tool_diameter_mm is None

    print("  ✓ PASS")
    return True


def test_pml_corner_cleanup_through_depth():
    print("Running test_pml_corner_cleanup_through_depth...")

    pml_text = """
Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: through
        corner_cleanup: 3.175mm
"""

    ast = parse_pml_yaml(pml_text)
    flat = resolve_layout(ast)
    item = flat.items[0]

    assert item.feature.type == "pocket"
    assert item.feature.depth == "through"
    assert item.feature.corner_cleanup_tool_diameter_mm == 3.175

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    import sys

    tests = [
        test_pml_parse_corner_cleanup,
        test_pml_format_corner_cleanup,
        test_pml_roundtrip_corner_cleanup,
        test_pml_pocket_without_corner_cleanup,
        test_pml_corner_cleanup_error_invalid_token,
        test_pml_corner_cleanup_through_depth,
    ]

    print("Running PML corner cleanup syntax tests...")

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{len(tests)} corner cleanup tests passed")
    sys.exit(0 if failed == 0 else 1)
