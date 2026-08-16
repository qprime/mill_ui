import re
import tempfile
from pathlib import Path

import pytest

from export.blueprint_svg import render_blueprint_svg
from layout_ast.compositional import CompositionalLayoutAST, Frame, PocketGen, ProfileGen, Rect
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet
from resolution.layout_resolver import LayoutResolver

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "blueprint_golden"


def test_svg_output_deterministic():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=100.0, thickness_mm=12.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 50.0, "h_mm": 30.0}),
                placement=Placement(center_xy_mm=(100.0, 50.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="test_rect",
            ),
        ),
    )

    svg1 = render_blueprint_svg(ast, theme="dark")
    svg2 = render_blueprint_svg(ast, theme="dark")

    assert svg1 == svg2, "SVG output should be deterministic"


def test_required_layers_exist():
    ast = LayoutAST(
        sheet=Sheet(width_mm=150.0, height_mm=150.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 20.0}),
                placement=Placement(center_xy_mm=(75.0, 75.0)),
                feature=Feature(type="hole", depth_mm=12.0),
                shape_id="test_hole",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    required_layers = [
        'id="SHEET_OUTLINE"',
        'id="HOLES"',
    ]

    for layer in required_layers:
        assert layer in svg, f"Layer {layer} missing from SVG"

    assert "<circle" in svg, "Hole should be rendered as circle"


def _create_shaker_ast(
    outer_w: float, outer_h: float, stile_w: float, rail_h: float, panel_recess: float, sheet_thickness: float
) -> LayoutAST:
    sheet = Sheet(width_mm=outer_w, height_mm=outer_h, thickness_mm=sheet_thickness, margin_mm=0.0)
    root = Rect(
        children=(
            ProfileGen(side="outside", depth="through"),
            Frame(
                width_mm=stile_w,
                children=(PocketGen(depth_mm=panel_recess),),
            ),
        ),
        id="door",
    )
    comp_ast = CompositionalLayoutAST(sheet=sheet, components={}, root=root)
    resolver = LayoutResolver(comp_ast)
    return resolver.resolve()


def test_shaker_dimensions():
    ast = _create_shaker_ast(
        outer_w=400.0,
        outer_h=600.0,
        stile_w=50.0,
        rail_h=50.0,
        panel_recess=6.0,
        sheet_thickness=19.0,
    )

    svg = render_blueprint_svg(ast, theme="dark")

    assert "PROFILE_CUTS" in svg
    assert "POCKET_REGIONS" in svg


def test_theme_toggle():
    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 40.0, "h_mm": 40.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rect",
            ),
        ),
    )

    svg_dark = render_blueprint_svg(ast, theme="dark")
    svg_print = render_blueprint_svg(ast, theme="print")

    assert "#1a1a1a" in svg_dark, "Dark theme should have dark background"
    assert "#ffffff" in svg_print, "Print theme should have white background"

    def extract_rects(svg):
        return re.findall(r'<rect[^>]*width="[^"]*"[^>]*height="[^"]*"[^>]*/>', svg)

    dark_rects = extract_rects(svg_dark)
    print_rects = extract_rects(svg_print)

    assert len(dark_rects) == len(print_rects), "Themes should not change geometry count"


def test_multiple_feature_types():
    ast = LayoutAST(
        sheet=Sheet(width_mm=300.0, height_mm=200.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 100.0}),
                placement=Placement(center_xy_mm=(150.0, 100.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="outer",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 80.0, "h_mm": 40.0}),
                placement=Placement(center_xy_mm=(150.0, 100.0)),
                feature=Feature(type="pocket", depth_mm=5.0),
                shape_id="inner",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 10.0}),
                placement=Placement(center_xy_mm=(80.0, 60.0)),
                feature=Feature(type="hole", depth_mm=0.0, is_through=True),
                shape_id="hole1",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    assert 'class="profile-cuts"' in svg
    assert 'class="pocket-regions"' in svg
    assert 'class="holes"' in svg

    assert svg.count("<rect") >= 3
    assert svg.count("<circle") >= 1


def test_viewbox_dimensions():
    ast = LayoutAST(
        sheet=Sheet(width_mm=250.0, height_mm=180.0, thickness_mm=12.0, margin_mm=0.0),
        items=(),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    assert "viewBox=" in svg, "SVG should have viewBox attribute"
    assert "width=" in svg, "SVG should have width attribute"
    assert "height=" in svg, "SVG should have height attribute"


def test_rounded_rect_rendering():
    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="RoundedRect",
                geometry=Geometry(data={"w_mm": 60.0, "h_mm": 40.0, "r_mm": 5.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rounded",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    assert "<svg" in svg
    assert 'id="PROFILE_CUTS"' in svg


def test_golden_file_simple_profile():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=150.0, thickness_mm=12.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100.0, "h_mm": 80.0}),
                placement=Placement(center_xy_mm=(100.0, 75.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="simple_rect",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")
    golden_path = GOLDEN_DIR / "simple_profile_dark.svg"

    svg_normalized = _normalize_svg(svg)

    if golden_path.exists():
        golden_svg = golden_path.read_text(encoding="utf-8")
        golden_normalized = _normalize_svg(golden_svg)
        assert svg_normalized == golden_normalized, f"SVG differs from golden file: {golden_path}"
    else:
        import os

        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            raise AssertionError(f"Golden file missing in CI: {golden_path}")

        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(svg, encoding="utf-8")


def test_golden_file_shaker_door():
    ast = _create_shaker_ast(
        outer_w=400.0,
        outer_h=600.0,
        stile_w=50.0,
        rail_h=50.0,
        panel_recess=6.0,
        sheet_thickness=19.0,
    )

    svg = render_blueprint_svg(ast, theme="dark")
    golden_path = GOLDEN_DIR / "shaker_door_dark.svg"

    svg_normalized = _normalize_svg(svg)

    if golden_path.exists():
        golden_svg = golden_path.read_text(encoding="utf-8")
        golden_normalized = _normalize_svg(golden_svg)
        assert svg_normalized == golden_normalized, f"SVG differs from golden file: {golden_path}"
    else:
        import os

        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            raise AssertionError(f"Golden file missing in CI: {golden_path}")

        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(svg, encoding="utf-8")


def test_dimension_rendering():
    ast = LayoutAST(
        sheet=Sheet(width_mm=300.0, height_mm=200.0, thickness_mm=12.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100.0, "h_mm": 60.0}),
                placement=Placement(center_xy_mm=(100.0, 100.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rect1",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 80.0, "h_mm": 50.0}),
                placement=Placement(center_xy_mm=(200.0, 100.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rect2",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="dark")

    assert 'id="DIMENSIONS"' in svg, "Should have DIMENSIONS layer"
    assert "<line" in svg, "Should have dimension lines"
    assert "<polygon" in svg, "Should have arrowheads"


def test_pdf_export():
    ast = LayoutAST(
        sheet=Sheet(width_mm=100.0, height_mm=100.0, thickness_mm=12.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 40.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="circle",
            ),
        ),
    )

    svg = render_blueprint_svg(ast, theme="print")

    try:
        from export.blueprint_pdf import svg_to_pdf

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            svg_to_pdf(svg, pdf_path)

            assert pdf_path.exists(), "PDF file was not created"
            assert pdf_path.stat().st_size > 0, "PDF file is empty"

    except ImportError:
        pytest.skip("cairosvg not installed")


def _normalize_svg(svg_text: str) -> str:

    normalized = re.sub(r">\s+<", "><", svg_text)

    normalized = "\n".join(line.strip() for line in normalized.split("\n"))

    normalized = "\n".join(line for line in normalized.split("\n") if line)
    return normalized


def _two_face_ast() -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=400.0, height_mm=300.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100.0, "h_mm": 80.0}),
                placement=Placement(center_xy_mm=(100.0, 100.0)),
                feature=Feature(type="pocket", depth_mm=6.0),
                shape_id="front_pocket",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 35.0}),
                placement=Placement(center_xy_mm=(300.0, 60.0)),
                feature=Feature(type="pocket", depth_mm=12.5, face="back"),
                shape_id="hinge_cup",
            ),
        ),
    )


def test_back_svg_generated_when_back_items_present():
    from cam.pipeline import run_pipeline

    result = run_pipeline(_two_face_ast(), kerf_mm=3.175, min_channel_width_mm=6.0)

    assert result.svg_back is not None
    assert result.svg is not None
    assert "BACK FACE" in result.svg_back
    assert "BACK FACE" not in result.svg


def test_back_svg_absent_for_single_face_job():
    from cam.pipeline import run_pipeline

    ast = _two_face_ast()
    single_face = LayoutAST(sheet=ast.sheet, items=(ast.items[0],))

    result = run_pipeline(single_face, kerf_mm=3.175, min_channel_width_mm=6.0)

    assert result.svg_back is None


def test_back_view_renders_mirrored_geometry():
    from cam.pipeline import run_pipeline

    ast = _two_face_ast()
    result = run_pipeline(ast, kerf_mm=3.175, min_channel_width_mm=6.0)

    authored_view = render_blueprint_svg(LayoutAST(sheet=ast.sheet, items=(ast.items[1],)))
    authored_cy = [float(m) for m in re.findall(r'<circle[^>]*\scy="([-\d.]+)"', authored_view)]
    assert result.svg_back is not None
    back_cy = [float(m) for m in re.findall(r'<circle[^>]*\scy="([-\d.]+)"', result.svg_back)]

    assert authored_cy == pytest.approx([240.0])
    assert back_cy == pytest.approx([60.0])


def test_front_view_omits_back_items():
    from cam.pipeline import run_pipeline

    result = run_pipeline(_two_face_ast(), kerf_mm=3.175, min_channel_width_mm=6.0)

    assert result.svg is not None
    assert "hinge_cup" not in result.svg
