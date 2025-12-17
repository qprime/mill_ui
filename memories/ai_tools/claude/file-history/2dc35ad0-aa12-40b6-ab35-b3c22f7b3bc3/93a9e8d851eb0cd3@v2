"""Standalone test runner for Stage 9 SVG rendering tests (without pytest).

Run from repository root: python3 -m skills.mill_ui.v2.tests.run_svg_tests
"""

import sys
import tempfile
from pathlib import Path

from skills.mill_ui.v2.ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from skills.mill_ui.v2.ir.removal_intent import RemovalIntent, Bounds2D, Allowance, Constraints
from skills.mill_ui.v2.export import render_svg_with_removal_intent


def test_render_svg_minimal_layout():
    """Test SVG rendering with minimal layout."""
    print("Running test_render_svg_minimal_layout...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=100.0, thickness_mm=12.0),
        items=[
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 50.0, "h_mm": 30.0}),
                placement=Placement(center_xy_mm=(100.0, 50.0)),
                feature=Feature(type="profile", depth="through"),
                shape_id="test_rect",
            )
        ],
    )

    intent = RemovalIntent(
        region_id="profile_test_rect",
        bounds=Bounds2D(x_min=75.0, x_max=125.0, y_min=35.0, y_max=65.0),
        z_top=0.0,
        z_bottom=-12.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, [intent], temp_path)

        svg_path = Path(temp_path)
        assert svg_path.exists()
        assert svg_path.stat().st_size > 0

        svg_content = svg_path.read_text()
        assert '<?xml version' in svg_content
        assert '<svg' in svg_content
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg_content
        assert '</svg>' in svg_content

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_svg_contains_removal_intent_layer():
    """Test that SVG contains RemovalIntent overlay elements."""
    print("Running test_svg_contains_removal_intent_layer...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=150.0, height_mm=150.0, thickness_mm=19.0),
        items=[
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 20.0}),
                placement=Placement(center_xy_mm=(75.0, 75.0)),
                feature=Feature(type="hole", depth="12.0", depth_mm=12.0),
                shape_id="test_hole",
            )
        ],
    )

    intent = RemovalIntent(
        region_id="hole_test_hole",
        bounds=Bounds2D(x_min=65.0, x_max=85.0, y_min=65.0, y_max=85.0),
        z_top=0.0,
        z_bottom=-12.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, [intent], temp_path)

        svg_content = Path(temp_path).read_text()

        assert 'id="removal_intent_bounds"' in svg_content
        assert 'stroke="red"' in svg_content
        assert 'hole_test_hole' in svg_content

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_svg_with_kerf_compensation():
    """Test SVG rendering with kerf offset visualization."""
    print("Running test_svg_with_kerf_compensation...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0),
        items=[
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 40.0, "h_mm": 40.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="kerf_rect",
            )
        ],
    )

    intent = RemovalIntent(
        region_id="profile_kerf_rect",
        bounds=Bounds2D(x_min=30.0, x_max=70.0, y_min=30.0, y_max=70.0),
        z_top=0.0,
        z_bottom=-12.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=1.5),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, [intent], temp_path)

        svg_content = Path(temp_path).read_text()

        assert 'id="kerf_offsets"' in svg_content
        assert 'stroke="blue"' in svg_content
        assert 'stroke-dasharray' in svg_content

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_svg_multiple_removal_intents():
    """Test SVG with multiple RemovalIntent regions."""
    print("Running test_svg_multiple_removal_intents...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=300.0, height_mm=200.0, thickness_mm=19.0),
        items=[
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 100.0}),
                placement=Placement(center_xy_mm=(150.0, 100.0)),
                feature=Feature(type="profile", depth="through"),
                shape_id="outer",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 80.0, "h_mm": 40.0}),
                placement=Placement(center_xy_mm=(150.0, 100.0)),
                feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                shape_id="inner",
            ),
        ],
    )

    intents = [
        RemovalIntent(
            region_id="profile_outer",
            bounds=Bounds2D(x_min=50.0, x_max=250.0, y_min=50.0, y_max=150.0),
            z_top=0.0,
            z_bottom=-19.0,
            allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
            constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
            metadata={},
        ),
        RemovalIntent(
            region_id="pocket_inner",
            bounds=Bounds2D(x_min=110.0, x_max=190.0, y_min=80.0, y_max=120.0),
            z_top=0.0,
            z_bottom=-5.0,
            allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
            constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
            metadata={},
        ),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, intents, temp_path)

        svg_content = Path(temp_path).read_text()

        assert 'profile_outer' in svg_content
        assert 'pocket_inner' in svg_content
        assert svg_content.count('stroke="red"') >= 2

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_svg_viewbox_dimensions():
    """Test that SVG viewBox matches sheet dimensions with margin."""
    print("Running test_svg_viewbox_dimensions...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=250.0, height_mm=180.0, thickness_mm=12.0),
        items=[],
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, [], temp_path)

        svg_content = Path(temp_path).read_text()

        # ViewBox should be sheet + 10mm margin on all sides
        assert 'viewBox="0 0 270.0 200.0"' in svg_content

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


def test_svg_rounded_rect_rendering():
    """Test SVG rendering with RoundedRect shape."""
    print("Running test_svg_rounded_rect_rendering...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0),
        items=[
            Item(
                kind="shape",
                type="RoundedRect",
                geometry=Geometry(data={"w_mm": 60.0, "h_mm": 40.0, "corner_radius_mm": 5.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth="through"),
                shape_id="rounded",
            )
        ],
    )

    intent = RemovalIntent(
        region_id="profile_rounded",
        bounds=Bounds2D(x_min=20.0, x_max=80.0, y_min=30.0, y_max=70.0),
        z_top=0.0,
        z_bottom=-12.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=[], islands=[], tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={},
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
        temp_path = f.name

    try:
        render_svg_with_removal_intent(ast, [intent], temp_path)

        svg_content = Path(temp_path).read_text()

        assert 'rx="5.0"' in svg_content or 'rx="5"' in svg_content
        assert 'ry="5.0"' in svg_content or 'ry="5"' in svg_content

        print("  ✓ PASS")
        return True
    finally:
        Path(temp_path).unlink()


if __name__ == "__main__":
    tests = [
        test_render_svg_minimal_layout,
        test_svg_contains_removal_intent_layer,
        test_svg_with_kerf_compensation,
        test_svg_multiple_removal_intents,
        test_svg_viewbox_dimensions,
        test_svg_rounded_rect_rendering,
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

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} SVG rendering tests passed")

    sys.exit(0 if all(results) else 1)
