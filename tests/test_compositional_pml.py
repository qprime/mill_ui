from __future__ import annotations

from pathlib import Path

import pytest

from layout_ast.compositional import (
    Panel,
    Rect,
)
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import PMLParseError, parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def approx_eq(a, b, rel=1e-6):
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_simple_rect():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      children:
        - Profile:
            side: outside
            depth: through
"""
    ast = parse_pml_yaml(pml)
    assert ast.sheet.width_mm == 400.0
    assert ast.sheet.height_mm == 600.0
    assert ast.sheet.thickness_mm == 19.0

    assert isinstance(ast.root, Panel)
    assert len(ast.root.children) == 1
    rect = ast.root.children[0]
    assert isinstance(rect, Rect)
    assert rect.id == "outer"


def test_rect_with_inset():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Inset:
      distance: 25mm
      children:
        - Rect:
            id: panel
            feature:
              type: pocket
              depth: 6mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0


def test_frame_with_pocket():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 50mm
            children:
              - Rect:
                  id: inner
                  feature:
                    type: pocket
                    depth: 6mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry is not None
    assert outer.geometry.data["w_mm"] == 400.0
    assert outer.feature is not None
    assert outer.feature.type == "profile"

    inner = flat.items[1]
    assert inner.shape_id == "inner"
    assert inner.feature is not None
    assert inner.feature.type == "pocket"

    assert inner.geometry is not None
    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0


def test_grid_with_pockets():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Grid:
      rows: 2
      cols: 2
      gap: 10mm
      children:
        - Cell:
            children:
              - Rect:
                  feature:
                    type: pocket
                    depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 4

    for item in flat.items:
        assert item.feature is not None
        assert item.feature.type == "pocket"

        assert item.geometry is not None
        assert approx_eq(item.geometry.data["w_mm"], 195.0)
        assert approx_eq(item.geometry.data["h_mm"], 195.0)


def test_component_definition_and_use():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

components:
  SimplePanel:
    body:
      - Rect:
          id: panel
          feature:
            type: pocket
            depth: 6mm

children:
  - UseComponent:
      name: SimplePanel
"""
    ast = parse_pml_yaml(pml)

    assert "SimplePanel" in ast.components
    comp_def = ast.components["SimplePanel"]
    assert comp_def.name == "SimplePanel"

    flat = resolve_layout(ast)
    assert len(flat.items) == 1
    assert flat.items[0].shape_id == "panel"


def test_place_with_components():
    pml = """
Sheet:
  width: 1000mm
  height: 1000mm
  thickness: 19mm

components:
  Panel:
    body:
      - Rect:
          id: outer
          feature:
            type: profile
            side: outside
            depth: through

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 50mm
      children:
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 4

    first = flat.items[0]

    assert first.geometry is not None
    assert approx_eq(first.geometry.data["w_mm"], 475.0)


def test_acceptance_stage12_gold_exemplar():
    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm

project: acceptance_test_grid_panels

components:
  GridPanel:
    body:
      - Rect:
          id: panel_outer
          feature:
            type: profile
            side: outside
            depth: through
          children:
            - Frame:
                width: 40mm
                children:
                  - Grid:
                      rows: 2
                      cols: 2
                      gap: 10mm
                      children:
                        - Cell:
                            children:
                              - Rect:
                                  id: cell_rect
                                  feature:
                                    type: pocket
                                    depth: 5mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 100mm
      children:
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
"""

    ast = parse_pml_yaml(pml)

    assert ast.sheet.width_mm == 1200
    assert ast.sheet.height_mm == 1200
    assert ast.sheet.thickness_mm == 19
    assert ast.project == "acceptance_test_grid_panels"
    assert "GridPanel" in ast.components

    flat = resolve_layout(ast)

    assert len(flat.items) == 20

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 4

    assert len(pocket_items) == 16

    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"

    first_outer = flat.items[0]
    assert first_outer.shape_id == "panel_outer"
    assert first_outer.geometry is not None
    assert approx_eq(first_outer.geometry.data["w_mm"], 550.0)
    assert approx_eq(first_outer.geometry.data["h_mm"], 550.0)

    first_pocket = pocket_items[0]
    assert first_pocket.geometry is not None
    assert approx_eq(first_pocket.geometry.data["w_mm"], 230.0)
    assert approx_eq(first_pocket.geometry.data["h_mm"], 230.0)


def test_roundtrip_preserves_semantics():
    original_pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

project: test_roundtrip

components:
  TestPanel:
    body:
      - Rect:
          id: outer
          feature:
            type: profile
            side: outside
            depth: through
          children:
            - Frame:
                width: 50mm
                children:
                  - Rect:
                      id: inner
                      feature:
                        type: pocket
                        depth: 6mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 20mm
      children:
        - UseComponent:
            name: TestPanel
        - UseComponent:
            name: TestPanel
        - UseComponent:
            name: TestPanel
        - UseComponent:
            name: TestPanel
"""

    ast1 = parse_pml_yaml(original_pml)

    canonical_pml = format_pml_yaml(ast1)

    ast2 = parse_pml_yaml(canonical_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)

    types1 = [item.feature.type if item.feature else None for item in flat1.items]
    types2 = [item.feature.type if item.feature else None for item in flat2.items]
    assert types1 == types2


def test_error_handling_unknown_keyword():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - UnknownNode:
      value: 123
"""
    try:
        parse_pml_yaml(pml)
        raise AssertionError("Expected PMLParseError")
    except PMLParseError:
        pass


def test_formatter_produces_canonical_output():
    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm

project: test_canonical

components:
  Panel:
    body:
      - Rect:
          id: outer
          feature:
            type: profile
            side: outside
            depth: through
          children:
            - Frame:
                width: 40mm
                children:
                  - Grid:
                      rows: 2
                      cols: 2
                      gap: 10mm
                      children:
                        - Cell:
                            children:
                              - Rect:
                                  id: cell_rect
                                  feature:
                                    type: pocket
                                    depth: 5mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 100mm
      children:
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
        - UseComponent:
            name: Panel
"""

    ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(ast)

    assert "Sheet:" in formatted
    assert "project:" in formatted
    assert "components:" in formatted

    ast2 = parse_pml_yaml(formatted)
    formatted2 = format_pml_yaml(ast2)
    assert formatted == formatted2


def test_grid_without_explicit_cell():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Grid:
      rows: 2
      cols: 2
      gap: 0mm
      children:
        - Cell:
            children:
              - Rect:
                  feature:
                    type: pocket
                    depth: 5mm
"""
    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 4


def test_project_optional():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
"""
    ast = parse_pml_yaml(pml)
    assert ast.project is None

    flat = resolve_layout(ast)
    assert len(flat.items) == 1


def _beam_pml(features_block: str) -> str:
    return f"""
Sheet:
  width: 800mm
  height: 600mm
  thickness: 19mm

children:
  - Beam:
      name: post
      length: 500mm
      width: 76mm
      thickness: 19mm
      layers: 3
{features_block}
"""


def test_beam_carved_design_rejected():
    pml = _beam_pml(
        """      face_features:
        - CarvedDesign:
            x: 100mm
            y: 38mm
            design: rosette
            depth: 3mm
"""
    )

    try:
        parse_pml_yaml(pml)
        raise AssertionError("expected PMLParseError")
    except PMLParseError as exc:
        assert "CarvedDesign" in str(exc)
        assert "face_features[0]" in str(exc)


def test_beam_chamfer_rejected():
    pml = _beam_pml(
        """      edge_features:
        - Chamfer:
            edge: top
            width: 3mm
"""
    )

    try:
        parse_pml_yaml(pml)
        raise AssertionError("expected PMLParseError")
    except PMLParseError as exc:
        assert "Chamfer" in str(exc)


def test_beam_end_cap_rejected_at_its_own_index():
    pml = _beam_pml(
        """      end_features:
        - Tenon:
            end: left
            extension: 38mm
            width: 76mm
            height: 19mm
        - EndCap:
            end: right
            profile: rounded
"""
    )

    try:
        parse_pml_yaml(pml)
        raise AssertionError("expected PMLParseError")
    except PMLParseError as exc:
        assert "EndCap" in str(exc)
        assert "end_features[1]" in str(exc)


def test_beam_supported_features_parse_and_resolve():
    pml = _beam_pml(
        """      face_features:
        - DrillHole:
            x: 100mm
            y: 38mm
            diameter: 10mm
        - SquareMortise:
            x: 250mm
            y: 38mm
            width: 38mm
            height: 50mm
            depth: 19mm
      edge_features:
        - EdgeDado:
            edge: top
            position: 400mm
            width: 19mm
            depth: 9.5mm
        - Rabbet:
            edge: bottom
            width: 12mm
            depth: 6mm
      end_features:
        - Tenon:
            end: left
            extension: 38mm
            width: 76mm
            height: 19mm
        - Tenon:
            end: right
            extension: 38mm
            width: 76mm
            height: 19mm
"""
    )

    flat = resolve_layout(parse_pml_yaml(pml))

    holes = [i for i in flat.items if i.feature and i.feature.type == "hole"]
    pockets = [i for i in flat.items if i.feature and i.feature.type == "pocket"]
    assert len(holes) == 3
    assert len(pockets) == 6


def test_curve_rose_round_trip():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Curve:
            type: rose
            lobes: 4
            depth: 0.3mm
            size: 120mm
            rotation: 22.5
            tolerance: 0.02mm
            min_length: 3mm
"""
    formatted = format_pml_yaml(parse_pml_yaml(pml))

    for key in ("type: rose", "lobes: 4", "size: 120mm", "rotation: 22.5", "tolerance: 0.02mm", "min_length: 3mm"):
        assert key in formatted

    assert format_pml_yaml(parse_pml_yaml(formatted)) == formatted


def test_curve_unknown_type_rejected():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Curve:
            type: hexagram
            depth: 0.3mm
"""
    with pytest.raises(PMLParseError, match="Known types: rose, spirograph, lissajous"):
        parse_pml_yaml(pml)


def test_curve_rejects_children():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Curve:
      type: rose
      lobes: 3
      depth: 0.3mm
      children:
        - Pocket: {depth: 2mm}
"""
    with pytest.raises(PMLParseError, match="does not accept 'children'"):
        parse_pml_yaml(pml)


def test_curve_spirograph_round_trip():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Curve:
            type: spirograph
            fixed_radius: 60mm
            rolling_radius: 21mm
            pen_offset: 15mm
            mode: outside
            revolutions: 3
            depth: 0.3mm
            size: 120mm
            rotation: 15
            tolerance: 0.02mm
            min_length: 2mm
"""
    formatted = format_pml_yaml(parse_pml_yaml(pml))

    for key in (
        "type: spirograph",
        "fixed_radius: 60mm",
        "rolling_radius: 21mm",
        "pen_offset: 15mm",
        "mode: outside",
        "revolutions: 3",
        "size: 120mm",
        "rotation: 15",
        "tolerance: 0.02mm",
        "min_length: 2mm",
    ):
        assert key in formatted

    assert format_pml_yaml(parse_pml_yaml(formatted)) == formatted


def test_curve_lissajous_round_trip():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Curve:
            type: lissajous
            frequency_x: 5
            frequency_y: 4
            phase: 45
            width: 160mm
            height: 100mm
            depth: 0.3mm
            size: 120mm
            rotation: 15
            tolerance: 0.02mm
            min_length: 2mm
"""
    formatted = format_pml_yaml(parse_pml_yaml(pml))

    for key in (
        "type: lissajous",
        "frequency_x: 5",
        "frequency_y: 4",
        "phase: 45",
        "width: 160mm",
        "height: 100mm",
        "size: 120mm",
        "rotation: 15",
        "tolerance: 0.02mm",
        "min_length: 2mm",
    ):
        assert key in formatted

    assert format_pml_yaml(parse_pml_yaml(formatted)) == formatted


def test_phyllotaxis_round_trip():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Phyllotaxis:
            count: 12
            spacing: 8mm
            angle: 100.5
            depth: 3mm
            scale_with_radius: true
            min_size: 3mm
            element:
              type: pocket
              diameter: 6mm
"""
    ast = parse_pml_yaml(pml)
    formatted = format_pml_yaml(ast)

    for key in ("count: 12", "spacing: 8mm", "angle: 100.5", "scale_with_radius: true", "min_size: 3mm"):
        assert key in formatted

    assert parse_pml_yaml(formatted) == ast


def _phyllotaxis_pml(shared: str, element: str) -> str:
    return f"""
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Phyllotaxis:
            count: 50
            spacing: 10mm
            depth: 0.3mm
{shared}
            element:
{element}
"""


def test_phyllotaxis_rejects_scale_with_radius_on_hole():
    pml = _phyllotaxis_pml(
        "            scale_with_radius: true\n            min_size: 2mm",
        "              type: hole\n              diameter: 5mm",
    )
    with pytest.raises(PMLParseError, match="not supported for hole"):
        parse_pml_yaml(pml)


def test_phyllotaxis_rejects_svg_scale_key():
    pml = _phyllotaxis_pml(
        "",
        "              type: svg\n              path: 'M 0 0 L 1 1'\n              size: 6mm\n              scale: fill",
    )
    with pytest.raises(PMLParseError, match="does not accept 'scale'"):
        parse_pml_yaml(pml)


def test_phyllotaxis_rejects_min_size_without_scale_with_radius():
    pml = _phyllotaxis_pml("            min_size: 2mm", "              type: pocket\n              diameter: 5mm")
    with pytest.raises(PMLParseError, match="requires 'scale_with_radius: true'"):
        parse_pml_yaml(pml)


def test_phyllotaxis_rejects_scale_with_radius_without_min_size():
    pml = _phyllotaxis_pml(
        "            scale_with_radius: true", "              type: pocket\n              diameter: 5mm"
    )
    with pytest.raises(PMLParseError, match="requires 'min_size'"):
        parse_pml_yaml(pml)


def test_phyllotaxis_rejects_unknown_element_type():
    pml = _phyllotaxis_pml("", "              type: star")
    with pytest.raises(PMLParseError, match="Known types: hole, pocket, svg"):
        parse_pml_yaml(pml)


def _concentric_pml(body: str) -> str:
    return f"""
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - ConcentricBorder:
{body}
"""


def test_concentric_count_form_round_trips():
    ast = parse_pml_yaml(
        _concentric_pml(
            "            count: 6\n            step: 8mm\n            start: 12mm\n"
            "            join: round\n            mode: engrave\n            depth: 0.5mm"
        )
    )
    formatted = format_pml_yaml(ast)

    assert "count: 6" in formatted
    assert "insets:" not in formatted
    assert parse_pml_yaml(formatted) == ast


def test_concentric_rejects_insets_and_count():
    pml = _concentric_pml(
        "            insets: [15mm]\n            count: 3\n            step: 8mm\n            groove: 3mm\n            depth: 2mm"
    )
    with pytest.raises(PMLParseError, match=r"either 'insets' or 'count' \+ 'step', not both"):
        parse_pml_yaml(pml)


def test_concentric_rejects_count_without_step():
    pml = _concentric_pml("            count: 3\n            groove: 3mm\n            depth: 2mm")
    with pytest.raises(PMLParseError, match="requires either 'insets' or both 'count' and 'step'"):
        parse_pml_yaml(pml)


def test_concentric_engrave_rejects_groove():
    pml = _concentric_pml(
        "            insets: [15mm]\n            mode: engrave\n            groove: 3mm\n            depth: 1mm"
    )
    with pytest.raises(PMLParseError, match="'groove' is not valid with 'mode: engrave'"):
        parse_pml_yaml(pml)


def test_concentric_rejects_non_positive_step():
    pml = _concentric_pml(
        "            count: 3\n            step: 0mm\n            groove: 3mm\n            depth: 2mm"
    )
    with pytest.raises(PMLParseError, match="'step' must be positive"):
        parse_pml_yaml(pml)


def test_concentric_rejects_step_below_groove():
    pml = _concentric_pml(
        "            count: 5\n            step: 2mm\n            groove: 3mm\n            depth: 2mm"
    )
    with pytest.raises(PMLParseError, match=r"'step' \(2\.0mm\) is less than 'groove' \(3\.0mm\)"):
        parse_pml_yaml(pml)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            "            insets: [15mm]\n            start: 5mm\n            groove: 3mm\n            depth: 2mm",
            "'start' is only valid with 'count' and 'step'",
        ),
        (
            "            count: 0\n            step: 8mm\n            groove: 3mm\n            depth: 2mm",
            "'count' must be at least 1",
        ),
        (
            "            count: 3\n            step: 8mm\n            start: -5mm\n            groove: 3mm\n            depth: 2mm",
            "'start' must be positive",
        ),
        ("            insets: [15mm]\n            depth: 2mm", "'mode: pocket' requires 'groove'"),
    ],
    ids=["start_with_insets", "count_zero", "negative_start", "pocket_without_groove"],
)
def test_concentric_rejects_invalid_forms(body, message):
    with pytest.raises(PMLParseError, match=message):
        parse_pml_yaml(_concentric_pml(body))


RECIPE_PML_FILES = sorted((Path(__file__).parent.parent / "docs" / "recipes").glob("*/*.pml.yml"))


def test_recipe_round_trip_finds_recipes():
    assert RECIPE_PML_FILES


@pytest.mark.parametrize("pml_path", RECIPE_PML_FILES, ids=lambda p: p.parent.name)
def test_recipe_round_trips_to_identical_ast(pml_path: Path):
    ast = parse_pml_yaml(pml_path.read_text())
    assert parse_pml_yaml(format_pml_yaml(ast)) == ast


def test_sheet_material_round_trips():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm
  material: plywood

children:
  - Rect:
      id: panel
"""
    ast = parse_pml_yaml(pml)
    assert ast.sheet.material == "plywood"
    assert parse_pml_yaml(format_pml_yaml(ast)) == ast


def test_radial_label_round_trips():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: dial
      children:
        - Radial:
            rays: 4
            depth: 0.3mm
            start_angle: 90
            radius: 80mm
            element:
              type: label
              values: [N, E, S, W]
              height: 6mm
"""
    ast = parse_pml_yaml(pml)
    assert parse_pml_yaml(format_pml_yaml(ast)) == ast


def test_surface_stepover_keeps_full_precision():
    pml = f"""
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

Surface:
  depth-per-pass: 0.5mm
  stepover: {100 / 3}%

children:
  - Rect:
      id: panel
"""
    ast = parse_pml_yaml(pml)
    assert ast.surface is not None
    assert parse_pml_yaml(format_pml_yaml(ast)) == ast


_NON_DEFAULT_NODES = [
    pytest.param("Shell: {wall: 12mm, interior: pocket, depth: 6mm}", id="shell_numeric_depth"),
    pytest.param(
        "SvgStamp: {path: 'M 0 0 L 10 0 L 10 10 Z', depth: 1.5mm, feature: pocket, scale: none, "
        "svg_unit: 0.5, center: false, invert_y: false}",
        id="svg_stamp",
    ),
    pytest.param(
        "Radial: {rays: 6, depth: 3mm, start_angle: 10, end_angle: 180, radius: 70mm, "
        "element: {type: pocket, bar_width: 4mm, shape: arc, center_shape: hexagon, center_size: 20mm}}",
        id="radial_pocket",
    ),
    pytest.param(
        "Radial: {rays: 12, depth: 0.3mm, minor_subdivisions: 4, element: {type: tick, tick_length: 9mm, "
        "minor_tick_length: 4mm, inward: true, labels: true, label_list: [a, b, c, d, e, f, g, h, i, j, k, l], "
        "label_height: 5mm}}",
        id="radial_tick",
    ),
    pytest.param(
        "Radial: {rays: 5, depth: 0.3mm, element: {type: svg, path: 'M 0 0 L 20 10 L 0 20 Z', feature: pocket, "
        "scale: fill, svg_unit: 2.0, rotate: false, size: 25mm}}",
        id="radial_svg",
    ),
]


@pytest.mark.parametrize("node_yaml", _NON_DEFAULT_NODES)
def test_non_default_node_keys_round_trip(node_yaml: str):
    pml = f"""
Sheet: {{width: 300mm, height: 300mm, thickness: 19mm}}
children:
  - Rect:
      id: panel
      children:
        - {node_yaml}
"""
    ast = parse_pml_yaml(pml)
    assert parse_pml_yaml(format_pml_yaml(ast)) == ast


def test_non_default_surface_keys_round_trip():
    pml = """
Sheet: {width: 300mm, height: 300mm, thickness: 19mm}
Surface:
  depth-per-pass: 0.4mm
  passes: 3
  stepover: 55%
  direction: y
  margin-overrun: 5mm
  cool_every: 4
  cool_dwell: 2.5s
children:
  - Rect: {id: panel}
"""
    ast = parse_pml_yaml(pml)
    assert parse_pml_yaml(format_pml_yaml(ast)) == ast
