from __future__ import annotations

from diagram_ir import Circle, DiagramIR, LayerIR, Line, Point2D, Polyline, Rect, Text
from diagram_render.render_svg import (
    DARK_DIAGRAM_THEME,
    DIAGRAM_THEMES,
    PRINT_DIAGRAM_THEME,
    DiagramTheme,
    StyleSpec,
    render_diagram_svg,
)
from ir.removal_intent import Bounds2D


def _make_diagram(
    bounds: Bounds2D | None = None,
    layers: tuple | None = None,
) -> DiagramIR:
    if bounds is None:
        bounds = Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100)
    if layers is None:
        layers = ()
    return DiagramIR(bounds=bounds, layers=layers)


def test_render_empty_diagram():
    diagram = _make_diagram()
    svg = render_diagram_svg(diagram)

    assert "<svg" in svg
    assert "</svg>" in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_viewbox_present():
    diagram = _make_diagram(Bounds2D(0, 200, 0, 150))
    svg = render_diagram_svg(diagram)

    assert "viewBox=" in svg


def test_dark_theme_background():
    diagram = _make_diagram()
    svg = render_diagram_svg(diagram, theme="dark")

    assert "#1a1a1a" in svg


def test_print_theme_background():
    diagram = _make_diagram()
    svg = render_diagram_svg(diagram, theme="print")

    assert "#ffffff" in svg


def test_render_rect():
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Rect(x=10, y=10, width=50, height=30, style_token="profile"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram)

    assert "<rect" in svg
    assert 'id="TEST_LAYER"' in svg


def test_render_circle():
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Circle(cx=50, cy=50, radius=20, style_token="hole"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram)

    assert "<circle" in svg


def test_render_line():
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Line(x1=10, y1=10, x2=90, y2=90, style_token="dimension"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram)

    assert "<line" in svg


def test_render_text():
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Text(x=50, y=50, content="Hello", style_token="label"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram)

    assert "<text" in svg
    assert "Hello" in svg


def test_render_polyline_open():
    points = (Point2D(10, 10), Point2D(50, 10), Point2D(50, 50))
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Polyline(points=points, closed=False, style_token="profile"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram)

    assert "<polyline" in svg


def test_render_polyline_closed():
    points = (Point2D(10, 10), Point2D(50, 10), Point2D(50, 50), Point2D(10, 50))
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Polyline(points=points, closed=True, style_token="profile"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram)

    assert "<path" in svg
    assert " Z" in svg


def test_style_applied():
    layer = LayerIR(
        name="TEST_LAYER",
        items=(Rect(x=10, y=10, width=50, height=30, style_token="pocket"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram, theme="dark")

    assert "#6496c8" in svg


def test_multiple_layers():
    layer1 = LayerIR(
        name="LAYER_A",
        items=(Rect(x=10, y=10, width=30, height=30, style_token="profile"),),
    )
    layer2 = LayerIR(
        name="LAYER_B",
        items=(Circle(cx=70, cy=50, radius=15, style_token="hole"),),
    )
    diagram = _make_diagram(layers=(layer1, layer2))
    svg = render_diagram_svg(diagram)

    assert 'id="LAYER_A"' in svg
    assert 'id="LAYER_B"' in svg


def test_theme_object():
    custom_theme = DiagramTheme(
        background="#000000",
        foreground="#ff0000",
        style_map={"custom": {"stroke": "#00ff00", "fill": "none", "stroke-width": "3"}},
    )

    layer = LayerIR(
        name="TEST_LAYER",
        items=(Rect(x=10, y=10, width=50, height=30, style_token="custom"),),
    )
    diagram = _make_diagram(layers=(layer,))
    svg = render_diagram_svg(diagram, theme=custom_theme)

    assert "#000000" in svg
    assert "#00ff00" in svg


def test_style_spec_dataclass():
    spec = StyleSpec(
        stroke="#ff0000",
        stroke_width=2.0,
        fill="#00ff00",
        fill_opacity=0.5,
    )
    assert spec.stroke == "#ff0000"
    assert spec.stroke_width == 2.0
    assert spec.fill == "#00ff00"
    assert spec.fill_opacity == 0.5


def test_diagram_theme_get_style():
    theme = DARK_DIAGRAM_THEME
    style = theme.get_style("profile")

    assert style["stroke"] == "#e8e8e8"
    assert style["stroke-width"] == "2"


def test_diagram_theme_get_style_fallback():
    theme = DARK_DIAGRAM_THEME
    style = theme.get_style("nonexistent_token")

    assert "stroke" in style
    assert style["stroke"] == theme.foreground


def test_diagram_theme_style_attrs():
    theme = DARK_DIAGRAM_THEME
    attrs = theme.style_attrs("pocket")

    assert attrs == theme.get_style("pocket")


def test_themes_dict():
    assert "dark" in DIAGRAM_THEMES
    assert "print" in DIAGRAM_THEMES
    assert DIAGRAM_THEMES["dark"] == DARK_DIAGRAM_THEME
    assert DIAGRAM_THEMES["print"] == PRINT_DIAGRAM_THEME


def test_deterministic_output():
    layer = LayerIR(
        name="TEST",
        items=(
            Rect(x=10, y=10, width=50, height=30, style_token="profile"),
            Circle(cx=70, cy=50, radius=15, style_token="hole"),
        ),
    )
    diagram = _make_diagram(layers=(layer,))

    svg1 = render_diagram_svg(diagram)
    svg2 = render_diagram_svg(diagram)

    assert svg1 == svg2


def test_edge_callout_rendered():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={
            "sheet_thickness": "19",
            "edge_profiles": [
                {"type": "chamfer", "distance_mm": 3.0, "items": ["panel_a"]},
            ],
            "edge_allowances": [],
        },
    )
    svg = render_diagram_svg(diagram)

    assert "EDGE_CALLOUTS" in svg
    assert "SECTION A" in svg
    assert "callout_A_box" in svg
    assert "panel_a" in svg


def test_edge_callout_fillet_has_arc():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={
            "sheet_thickness": "19",
            "edge_profiles": [
                {"type": "fillet", "radius_mm": 5.0, "items": ["panel_b"]},
            ],
            "edge_allowances": [],
        },
    )
    svg = render_diagram_svg(diagram)

    assert "SECTION A" in svg
    assert "R5.0" in svg
    assert " A " in svg


def test_no_callout_when_no_profiles():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={
            "sheet_thickness": "19",
            "edge_profiles": [],
            "edge_allowances": [],
        },
    )
    svg = render_diagram_svg(diagram)

    assert "EDGE_CALLOUTS" not in svg


def test_edge_allowance_in_notes():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={
            "sheet_width": "200",
            "sheet_height": "200",
            "sheet_thickness": "19",
            "edge_profiles": [],
            "edge_allowances": [{"rough_allowance_mm": 0.5, "finish_allowance_mm": 0.1}],
        },
    )
    svg = render_diagram_svg(diagram)

    assert "Edge Allowances:" in svg
    assert "Rough: 0.50mm" in svg
    assert "Finish: 0.10mm" in svg


def test_multiple_callouts():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={
            "sheet_thickness": "19",
            "edge_profiles": [
                {"type": "chamfer", "distance_mm": 3.0, "items": ["panel_a"]},
                {"type": "fillet", "radius_mm": 5.0, "items": ["panel_b"]},
            ],
            "edge_allowances": [],
        },
    )
    svg = render_diagram_svg(diagram)

    assert "SECTION A" in svg
    assert "SECTION B" in svg
    assert "callout_A_box" in svg
    assert "callout_B_box" in svg


def test_section_markers_on_shapes():
    profile_layer = LayerIR(
        name="PROFILE_CUTS",
        items=(
            Rect(x=20, y=30, width=60, height=40, style_token="profile", id="panel_a"),
            Rect(x=120, y=30, width=60, height=40, style_token="profile", id="panel_b"),
        ),
    )
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(profile_layer,),
        metadata={
            "sheet_thickness": "19",
            "edge_profiles": [
                {"type": "chamfer", "distance_mm": 3.0, "items": ["panel_a"]},
                {"type": "fillet", "radius_mm": 5.0, "items": ["panel_b"]},
            ],
            "edge_allowances": [],
        },
    )
    svg = render_diagram_svg(diagram)

    assert "<circle" in svg
    assert svg.count('dominant-baseline="central"') >= 2


def _beam_structure_spliced():
    return [
        {
            "name": "long_rail",
            "length_mm": 2000.0,
            "width_mm": 100.0,
            "thickness_mm": 19.0,
            "layer_count": 3,
            "total_thickness_mm": 57.0,
            "role": "RAIL",
            "layers": [
                {
                    "layer_index": 0,
                    "segments": [
                        {"index": 0, "start_mm": 0.0, "end_mm": 1200.0, "length_mm": 1200.0},
                        {"index": 1, "start_mm": 1200.0, "end_mm": 2000.0, "length_mm": 800.0},
                    ],
                },
                {
                    "layer_index": 1,
                    "segments": [
                        {"index": 0, "start_mm": 0.0, "end_mm": 800.0, "length_mm": 800.0},
                        {"index": 1, "start_mm": 800.0, "end_mm": 2000.0, "length_mm": 1200.0},
                    ],
                },
                {
                    "layer_index": 2,
                    "segments": [
                        {"index": 0, "start_mm": 0.0, "end_mm": 400.0, "length_mm": 400.0},
                        {"index": 1, "start_mm": 400.0, "end_mm": 1600.0, "length_mm": 1200.0},
                        {"index": 2, "start_mm": 1600.0, "end_mm": 2000.0, "length_mm": 400.0},
                    ],
                },
            ],
        }
    ]


def test_beam_assembly_rendered():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={"beam_structures": _beam_structure_spliced()},
    )
    svg = render_diagram_svg(diagram)
    assert "BEAM_ASSEMBLIES" in svg
    assert "ASSEMBLY: long_rail" in svg
    assert "L0" in svg
    assert "L1" in svg
    assert "L2" in svg
    assert "S0" in svg
    assert "S1" in svg


def test_beam_assembly_spliced_has_stagger_note():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={"beam_structures": _beam_structure_spliced()},
    )
    svg = render_diagram_svg(diagram)
    assert "butt joints staggered (BM-9)" in svg


def test_no_beam_assembly_when_empty():
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={"beam_structures": []},
    )
    svg = render_diagram_svg(diagram)
    assert "BEAM_ASSEMBLIES" not in svg


def test_beam_assembly_single_layer():
    beam_data = [
        {
            "name": "short_post",
            "length_mm": 500.0,
            "width_mm": 76.0,
            "thickness_mm": 19.0,
            "layer_count": 1,
            "total_thickness_mm": 19.0,
            "role": "POST",
            "layers": [
                {
                    "layer_index": 0,
                    "segments": [
                        {"index": 0, "start_mm": 0.0, "end_mm": 500.0, "length_mm": 500.0},
                    ],
                },
            ],
        }
    ]
    diagram = DiagramIR(
        bounds=Bounds2D(x_min=0, x_max=200, y_min=0, y_max=200),
        layers=(),
        metadata={"beam_structures": beam_data},
    )
    svg = render_diagram_svg(diagram)
    assert "ASSEMBLY: short_post" in svg
    assert "L0" in svg
    assert "butt joints staggered" not in svg
