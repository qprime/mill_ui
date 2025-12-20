"""Test suite for F002: Blueprint Proof Drawing Export.

Tests blueprint-style SVG/PDF export for pre-machining validation.
"""

import tempfile
from pathlib import Path

from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from ir.removal_intent import RemovalIntent, Bounds2D, Allowance, Constraints
from export.blueprint_svg import render_blueprint_svg
from templates import Shaker


def test_svg_output_deterministic():
    """Test that same input produces same SVG output (deterministic)."""
    print("Running test_svg_output_deterministic...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=100.0, thickness_mm=12.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 50.0, "h_mm": 30.0}),
                placement=Placement(center_xy_mm=(100.0, 50.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="test_rect",
            ),
        ),
    )

    # Render twice
    svg1 = render_blueprint_svg(ast, theme="dark")
    svg2 = render_blueprint_svg(ast, theme="dark")

    # Should be identical (no timestamps or randomness)
    assert svg1 == svg2, "SVG output should be deterministic"
    print("  ✓ PASS")


def test_required_layers_exist():
    """Test that all semantic layers are present in SVG."""
    print("Running test_required_layers_exist...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=150.0, height_mm=150.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 20.0}),
                placement=Placement(center_xy_mm=(75.0, 75.0)),
                feature=Feature(type="hole", depth="12.0"),
                shape_id="test_hole",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    # Check all required semantic layers exist
    required_layers = [
        'id="SHEET_OUTLINE"',
        'id="PROFILE_CUTS"',
        'id="POCKET_REGIONS"',
        'id="ENGRAVE_PATHS"',
        'id="HOLES"',
        'id="CONSTRUCTION"',
        'id="DIMENSIONS"',
        'id="NOTES"',
        'id="TITLE_BLOCK"',
        'id="LEGEND"',
    ]

    for layer in required_layers:
        assert layer in svg, f"Layer {layer} missing from SVG"

    print("  ✓ PASS")


def test_shaker_dimensions():
    """Test that Shaker template produces expected geometry (no dimensions yet in Part A)."""
    print("Running test_shaker_dimensions...")

    # Generate shaker door
    ast = Shaker.expand_to_ast(
        params={
            "outer_w": 400.0,
            "outer_h": 600.0,
            "stile_w": 50.0,
            "rail_h": 50.0,
            "panel_recess": 6.0,
        },
        sheet_thickness_mm=19.0,
    )

    svg = render_blueprint_svg(ast, theme="dark")

    # Check for expected geometry (profile and pocket rectangles)
    assert "PROFILE_CUTS" in svg
    assert "POCKET_REGIONS" in svg
    # Part A doesn't have dimensions yet, so just verify structure

    print("  ✓ PASS")


def test_theme_toggle():
    """Test that theme toggle changes CSS but not geometry."""
    print("Running test_theme_toggle...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 40.0, "h_mm": 40.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="rect",
            ),
        ),
    )

    svg_dark = render_blueprint_svg(ast, theme="dark")
    svg_print = render_blueprint_svg(ast, theme="print")

    # Check theme-specific colors
    assert "#1a1a1a" in svg_dark, "Dark theme should have dark background"
    assert "#ffffff" in svg_print, "Print theme should have white background"

    # Extract geometry (rect elements) - should be identical
    def extract_rects(svg):
        import re
        return re.findall(r'<rect[^>]*width="[^"]*"[^>]*height="[^"]*"[^>]*/>', svg)

    dark_rects = extract_rects(svg_dark)
    print_rects = extract_rects(svg_print)

    # Geometry should be the same (same number of rectangles)
    assert len(dark_rects) == len(print_rects), "Themes should not change geometry count"

    print("  ✓ PASS")


def test_multiple_feature_types():
    """Test SVG with multiple feature types (profile, pocket, hole)."""
    print("Running test_multiple_feature_types...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=300.0, height_mm=200.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 100.0}),
                placement=Placement(center_xy_mm=(150.0, 100.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="outer",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 80.0, "h_mm": 40.0}),
                placement=Placement(center_xy_mm=(150.0, 100.0)),
                feature=Feature(type="pocket", depth=5.0),
                shape_id="inner",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 10.0}),
                placement=Placement(center_xy_mm=(80.0, 60.0)),
                feature=Feature(type="hole", depth="through"),
                shape_id="hole1",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    # Check that different feature types are rendered
    assert 'class="profile-cuts"' in svg
    assert 'class="pocket-regions"' in svg
    assert 'class="holes"' in svg

    # Should have multiple shape elements
    assert svg.count("<rect") >= 3  # Sheet + profile + pocket
    assert svg.count("<circle") >= 1  # Hole

    print("  ✓ PASS")


def test_viewbox_dimensions():
    """Test that SVG viewBox includes margin for dimensions."""
    print("Running test_viewbox_dimensions...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=250.0, height_mm=180.0, thickness_mm=12.0),
        items=(),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    # ViewBox should be sheet + 100mm margin on all sides (changed from old 10mm)
    # 250 + 2*100 = 450, 180 + 2*100 = 380
    assert 'viewBox="0 0 450 380"' in svg or 'viewBox="0 0 450.0 380.0"' in svg

    print("  ✓ PASS")


def test_rounded_rect_rendering():
    """Test SVG rendering with RoundedRect shape."""
    print("Running test_rounded_rect_rendering...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0),
        items=(
            Item(
                kind="shape",
                type="RoundedRect",
                geometry=Geometry(data={"w_mm": 60.0, "h_mm": 40.0, "r_mm": 5.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="rounded",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    # RoundedRect rendering not implemented in Part A yet, so just check it doesn't crash
    assert "<svg" in svg
    assert 'id="PROFILE_CUTS"' in svg

    print("  ✓ PASS (RoundedRect support TBD)")


if __name__ == "__main__":
    import sys

    tests = [
        test_svg_output_deterministic,
        test_required_layers_exist,
        test_shaker_dimensions,
        test_theme_toggle,
        test_multiple_feature_types,
        test_viewbox_dimensions,
        test_rounded_rect_rendering,
    ]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} blueprint export tests passed")

    sys.exit(0 if all(results) else 1)
