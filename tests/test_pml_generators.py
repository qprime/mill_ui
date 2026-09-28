from __future__ import annotations

import math
from dataclasses import replace

import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from layout_ast.compositional import (
    ChamferGen,
    PocketGen,
    ProfileGen,
    RaisedPanelGen,
    SplitGrid,
    SplitHorizontal,
    SplitVertical,
    WaveGen,
)
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout
from validation import check_overlap

PARSE_CASES = [
    pytest.param(
        "Profile:\n            side: outside\n            depth: through",
        ProfileGen,
        {"side": "outside", "depth": "through"},
        id="profile_outside_through",
    ),
    pytest.param(
        "Profile:\n            side: inside\n            depth: 10mm",
        ProfileGen,
        {"side": "inside", "depth": 10.0},
        id="profile_inside_depth",
    ),
    pytest.param(
        "Pocket:\n            depth: 6mm",
        PocketGen,
        {"depth_mm": 6.0},
        id="pocket",
    ),
    pytest.param(
        "RaisedPanel:\n            border_width: 25mm\n            border_depth: 6mm\n            field_depth: 2mm",
        RaisedPanelGen,
        {"border_width_mm": 25.0, "border_depth_mm": 6.0, "field_depth_mm": 2.0},
        id="raised_panel",
    ),
    pytest.param(
        "Chamfer:\n            width: 5mm\n            depth: 3mm",
        ChamferGen,
        {"width_mm": 5.0, "depth_mm": 3.0},
        id="chamfer",
    ),
    pytest.param(
        "Wave:\n            count: 5\n            amplitude: 10mm\n            wavelength: 60mm\n            groove: 3mm\n            depth: 2mm",
        WaveGen,
        {"wave_count": 5, "amplitude_mm": 10.0, "wavelength_mm": 60.0, "groove_width_mm": 3.0, "depth_mm": 2.0},
        id="wave",
    ),
]


@pytest.mark.parametrize("gen_yaml, expected_type, expected_fields", PARSE_CASES)
def test_parse_generator(gen_yaml, expected_type, expected_fields):
    pml = f"""
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - {gen_yaml}
"""
    ast = parse_pml_yaml(pml)
    gen = ast.root.children[0].children[0]
    assert isinstance(gen, expected_type)
    for attr, value in expected_fields.items():
        assert getattr(gen, attr) == value, f"{attr}: expected {value}, got {getattr(gen, attr)}"


def test_parse_split_horizontal():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - SplitHorizontal:
            count: 3
            gap: 20mm
            children:
              - Pocket:
                  depth: 6mm
"""
    ast = parse_pml_yaml(pml)
    split_h = ast.root.children[0].children[0]
    assert isinstance(split_h, SplitHorizontal)
    assert split_h.n == 3
    assert split_h.gap_mm == 20.0
    assert len(split_h.children) == 1
    assert isinstance(split_h.children[0], PocketGen)


def test_parse_split_vertical():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - SplitVertical:
            count: 2
            gap: 15mm
            children:
              - Pocket:
                  depth: 4mm
"""
    ast = parse_pml_yaml(pml)
    split_v = ast.root.children[0].children[0]
    assert isinstance(split_v, SplitVertical)
    assert split_v.n == 2
    assert split_v.gap_mm == 15.0
    assert len(split_v.children) == 1


def test_parse_split_grid():
    pml = """
Sheet:
  width: 500mm
  height: 700mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - SplitGrid:
            rows: 2
            cols: 2
            gap: 35mm
            children:
              - RaisedPanel:
                  border_width: 25mm
                  border_depth: 6mm
                  field_depth: 2mm
"""
    ast = parse_pml_yaml(pml)
    split_g = ast.root.children[0].children[0]
    assert isinstance(split_g, SplitGrid)
    assert split_g.rows == 2
    assert split_g.cols == 2
    assert split_g.gap_mm == 35.0
    assert len(split_g.children) == 1
    assert isinstance(split_g.children[0], RaisedPanelGen)


def test_resolve_profile_gen():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    assert len(ast.items) == 2

    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    assert len(profile_items) == 1

    profile_item = profile_items[0]
    assert profile_item.feature is not None
    assert profile_item.feature.side == "outside"
    assert profile_item.feature.is_through


def test_resolve_pocket_gen():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Pocket:
            depth: 6mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    pocket_items = [i for i in ast.items if i.shape_id and i.shape_id.startswith("generated_pocket")]
    assert len(pocket_items) == 1

    pocket_item = pocket_items[0]
    assert pocket_item.feature is not None
    assert pocket_item.feature.type == "pocket"
    assert pocket_item.feature.depth_mm == 6.0


def test_resolve_raised_panel_gen():
    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - RaisedPanel:
            border_width: 25mm
            border_depth: 6mm
            field_depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    border_items = [i for i in ast.items if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 1, f"Expected 1 border item, got {len(border_items)}"
    assert len(field_items) == 1, f"Expected 1 field item, got {len(field_items)}"

    assert border_items[0].feature is not None
    assert border_items[0].feature.type == "bevel", f"Expected bevel, got {border_items[0].feature.type}"
    assert border_items[0].feature.depth_mm == 6.0
    assert field_items[0].feature is not None
    assert field_items[0].feature.type == "pocket", f"Expected pocket, got {field_items[0].feature.type}"
    assert field_items[0].feature.depth_mm == 2.0


def test_resolve_split_grid_with_raised_panel():
    pml = """
Sheet:
  width: 500mm
  height: 700mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - SplitGrid:
            rows: 2
            cols: 2
            gap: 35mm
            children:
              - RaisedPanel:
                  border_width: 25mm
                  border_depth: 6mm
                  field_depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    border_items = [i for i in ast.items if i.shape_id and "_border" in i.shape_id]
    field_items = [i for i in ast.items if i.shape_id and "_field" in i.shape_id]

    assert len(border_items) == 4, f"Expected 4 border items, got {len(border_items)}"
    assert len(field_items) == 4, f"Expected 4 field items, got {len(field_items)}"


def test_resolve_wave_gen():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Wave:
            count: 5
            amplitude: 10mm
            wavelength: 60mm
            groove: 3mm
            depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    wave_items = [i for i in ast.items if i.shape_id and "wave" in i.shape_id]
    assert len(wave_items) >= 1, f"Expected wave items, got {len(wave_items)}"

    for item in wave_items:
        assert item.feature is not None
        assert item.feature.type == "engrave", f"Expected engrave, got {item.feature.type}"
        assert item.feature.depth_mm == 2.0


def test_example_shaker_door():
    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: 50mm
            children:
              - Pocket:
                  depth: 6mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    assert len(ast.items) >= 3

    feature_types = {i.feature.type for i in ast.items if i.feature}
    assert "profile" in feature_types
    assert "pocket" in feature_types


def test_example_four_panel_door():
    pml = """
Sheet:
  width: 500mm
  height: 700mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: 65mm
            children:
              - SplitGrid:
                  rows: 2
                  cols: 2
                  gap: 35mm
                  children:
                    - RaisedPanel:
                        border_width: 25mm
                        border_depth: 6mm
                        field_depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    raised_items = [i for i in ast.items if i.shape_id and ("_border" in i.shape_id or "_field" in i.shape_id)]

    assert len(profile_items) >= 1, "Should have at least one profile"
    assert len(raised_items) == 8, f"Should have 8 raised panel items (4 borders + 4 fields), got {len(raised_items)}"


def test_example_wave_texture_panel():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Wave:
            count: 5
            amplitude: 10mm
            wavelength: 60mm
            groove: 3mm
            depth: 2mm
"""
    comp_ast = parse_pml_yaml(pml)
    ast = resolve_layout(comp_ast)

    profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
    wave_items = [i for i in ast.items if i.shape_id and "wave" in i.shape_id]

    assert len(profile_items) >= 1, "Should have profile"
    assert len(wave_items) >= 1, "Should have wave engrave items"


def test_curve_rose_resolves_to_polyline_engraves():
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
            lobes: 5
            depth: 0.3mm
"""
    ast = resolve_layout(parse_pml_yaml(pml))

    curves = [item for item in ast.items if item.type == "Polyline"]
    assert len(curves) == 1
    assert curves[0].feature is not None
    assert curves[0].feature.type == "engrave"
    assert curves[0].feature.depth_mm == pytest.approx(0.3)
    assert curves[0].shape_id is not None
    assert curves[0].shape_id.startswith("generated_rose")


def test_phyllotaxis_resolves_holes():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Circle:
      id: disc
      diameter: 200mm
      at: {x: 150mm, y: 150mm}
      children:
        - Phyllotaxis:
            count: 400
            spacing: 7mm
            depth: through
            element:
              type: hole
              diameter: 5mm
"""
    ast = resolve_layout(parse_pml_yaml(pml))

    holes = [item for item in ast.items if item.feature is not None and item.feature.type == "hole"]
    assert 0 < len(holes) < 400
    disc = next(item for item in ast.items if item.shape_id == "disc")
    assert disc.placement is not None
    for hole in holes:
        assert hole.type == "Circle"
        assert hole.feature is not None
        assert hole.feature.is_through
        assert hole.placement is not None
        assert math.dist(hole.placement.center_xy_mm, disc.placement.center_xy_mm) + 2.5 <= 100.0


_PHYLLOTAXIS_SVG_FILE_PML = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Phyllotaxis:
            count: 30
            spacing: 10mm
            depth: 0.3mm
            element:
              type: svg
              path: motif.svg
              size: 6mm
"""


def test_phyllotaxis_svg_file_resolves_against_source_dir(tmp_path):
    (tmp_path / "motif.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 L 20 10 L 0 20 Z"/></svg>'
    )
    ast = resolve_layout(replace(parse_pml_yaml(_PHYLLOTAXIS_SVG_FILE_PML), source_dir=str(tmp_path)))

    motifs = [item for item in ast.items if item.shape_id and item.shape_id.startswith("generated_phyllotaxis_svg")]
    assert len(motifs) == 30
    assert all(item.feature is not None and item.feature.type == "engrave" for item in motifs)


def test_phyllotaxis_svg_file_without_source_dir_raises():
    with pytest.raises(ValueError, match=r"Phyllotaxis SVG references file 'motif\.svg'"):
        resolve_layout(parse_pml_yaml(_PHYLLOTAXIS_SVG_FILE_PML))


def _spirograph_pml(pen: str) -> str:
    return f"""
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
            depth: 0.3mm
            layers:
              - points: 5
                step: 2
                pen: {pen}
"""


def test_curve_spirograph_resolves_to_polyline_engrave():
    ast = resolve_layout(parse_pml_yaml(_spirograph_pml("0.8")))

    curves = [item for item in ast.items if item.type == "Polyline"]
    assert len(curves) == 1
    assert curves[0].feature is not None
    assert curves[0].feature.type == "engrave"
    assert curves[0].shape_id is not None
    assert curves[0].shape_id.startswith("generated_spirograph")


def test_curve_spirograph_pen_sweep_resolves_count_strands():
    ast = resolve_layout(parse_pml_yaml(_spirograph_pml("{from: 1.0, to: 0.4, count: 4}")))

    curves = [item for item in ast.items if item.type == "Polyline"]
    assert len(curves) == 4
    assert all(curve.geometry is not None and curve.geometry.data["is_open"] is False for curve in curves)


def test_curve_spirograph_same_depth_strands_pass_overlap_check():
    ast = resolve_layout(parse_pml_yaml(_spirograph_pml("{from: 1.2, to: 0.4, count: 3}")))

    assert check_overlap(ast_to_removal_intents(ast)).errors == []


def test_curve_spirograph_sweep_rejects_count_below_two():
    with pytest.raises(ValueError, match="count must be at least 2"):
        resolve_layout(parse_pml_yaml(_spirograph_pml("{from: 1.0, to: 0.4, count: 1}")))


def test_curve_lissajous_resolves_to_polyline_engrave():
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
            frequency_x: 3
            frequency_y: 2
            depth: 0.3mm
"""
    ast = resolve_layout(parse_pml_yaml(pml))

    curves = [item for item in ast.items if item.type == "Polyline"]
    assert len(curves) == 1
    assert curves[0].feature is not None
    assert curves[0].feature.type == "engrave"
    assert curves[0].shape_id is not None
    assert curves[0].shape_id.startswith("generated_lissajous")


def test_curve_superformula_resolves_to_polyline_engrave():
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
            type: superformula
            m: 5
            n1: 2
            n2: 7
            n3: 7
            depth: 0.3mm
"""
    ast = resolve_layout(parse_pml_yaml(pml))

    curves = [item for item in ast.items if item.type == "Polyline"]
    assert len(curves) == 1
    assert curves[0].feature is not None
    assert curves[0].feature.type == "engrave"
    assert curves[0].shape_id is not None
    assert curves[0].shape_id.startswith("generated_superformula")


def test_curve_harmonograph_resolves_to_polyline_engrave():
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
            type: harmonograph
            cycles: 40
            pendulums:
              - {axis: x, amplitude: 60mm, frequency: 2, phase: 90, damping: 0.02}
              - {axis: y, amplitude: 60mm, frequency: 3, damping: 0.02}
            depth: 0.3mm
"""
    ast = resolve_layout(parse_pml_yaml(pml))

    curves = [item for item in ast.items if item.type == "Polyline"]
    assert len(curves) == 1
    assert curves[0].feature is not None
    assert curves[0].feature.type == "engrave"
    assert curves[0].shape_id is not None
    assert curves[0].shape_id.startswith("generated_harmonograph")


def _voronoi_pml(voronoi: str) -> str:
    return f"""
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Circle:
      id: disc
      diameter: 200mm
      at: {{x: 150mm, y: 150mm}}
      children:
        - Voronoi: {voronoi}
"""


def test_voronoi_resolves_engraves():
    ast = resolve_layout(parse_pml_yaml(_voronoi_pml("{seed_count: 40, seed: 7, min_spacing: 12mm, depth: 0.5mm}")))

    engraves = [item for item in ast.items if item.feature is not None and item.feature.type == "engrave"]
    assert engraves
    for item in engraves:
        assert item.type == "Polyline"
        assert item.shape_id is not None
        assert item.shape_id.startswith("generated_voronoi")
        assert item.placement is not None
        assert math.dist(item.placement.center_xy_mm, (150.0, 150.0)) < 100.0


def test_voronoi_resolves_pockets():
    ast = resolve_layout(
        parse_pml_yaml(
            _voronoi_pml("{seed_count: 12, seed: 3, min_spacing: 20mm, mode: pocket, line_width: 4mm, depth: 3mm}")
        )
    )

    pockets = [item for item in ast.items if item.feature is not None and item.feature.type == "pocket"]
    assert len(pockets) == 12
    for item in pockets:
        assert item.type == "Polygon"
        assert item.feature is not None
        assert item.feature.depth_mm == 3.0


def test_voronoi_unsatisfiable_spacing_propagates():
    ast = parse_pml_yaml(_voronoi_pml("{seed_count: 40, min_spacing: 60mm, depth: 0.5mm}"))

    with pytest.raises(ValueError, match="of 40 seeds"):
        resolve_layout(ast)


def test_string_art_resolves_to_polyline_engraves():
    pml = """
Sheet:
  width: 300mm
  height: 300mm
  thickness: 19mm

children:
  - Circle:
      id: disc
      diameter: 200mm
      at: {x: 150mm, y: 150mm}
      children:
        - StringArt: {anchors: 72, rule: multiply, factor: 2, depth: 0.3mm}
"""
    ast = resolve_layout(parse_pml_yaml(pml))

    engraves = [item for item in ast.items if item.feature is not None and item.feature.type == "engrave"]
    assert len(engraves) == 70
    for item in engraves:
        assert item.type == "Polyline"
        assert item.feature is not None
        assert item.feature.depth_mm == 0.3
        assert item.shape_id is not None
        assert item.shape_id.startswith("generated_string_art")
