from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from adapters.ast_to_removal import ast_to_removal_intents
from core.constants import FeatureType, ShapeType
from layout_ast.compositional import HeightfieldGen
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def _write_synthetic_png(path: Path, size: int = 32) -> None:
    xs = np.linspace(-1.0, 1.0, size)
    ys = np.linspace(-1.0, 1.0, size)
    xx, yy = np.meshgrid(xs, ys)
    heights = np.clip(1.0 - np.sqrt(xx * xx + yy * yy), 0.0, 1.0)
    arr = (heights * 65535).astype(np.uint16)
    Image.fromarray(arr, mode="I;16").save(path, format="PNG")


def _minimal_pml(image_rel: str) -> str:
    return f"""Sheet:
  width: 200mm
  height: 200mm
  thickness: 19mm
  material: mdf

children:
- Rect:
    id: relief
    at:
      x: 100mm
      y: 100mm
      width: 120mm
      height: 120mm
    children:
      - Heightfield:
          image: {image_rel}
          size:
            width: 100mm
            height: 100mm
          depth: 4mm
          white_is_high: true
          tools:
            - tool: 1_4_flat
              role: rough
              stepover: 60%
              stepdown: 2mm
"""


def test_heightfield_pml_parses_to_ast_node(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    ast = parse_pml_yaml(_minimal_pml("relief.png"))
    rect = ast.root.children[0].child
    assert isinstance(rect.children[0], HeightfieldGen)
    hf = rect.children[0]
    assert hf.image_path == "relief.png"
    assert hf.width_mm == 100.0
    assert hf.height_mm == 100.0
    assert hf.depth_mm == 4.0
    assert hf.white_is_high is True


def test_heightfield_pml_round_trip(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    source = _minimal_pml("relief.png")
    ast1 = parse_pml_yaml(source)
    formatted = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted)
    assert ast1 == ast2


def test_heightfield_resolves_to_flat_item(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    hf_items = [i for i in flat.items if i.type == ShapeType.HEIGHTFIELD]
    assert len(hf_items) == 1
    item = hf_items[0]
    assert item.feature is not None
    assert item.feature.type == FeatureType.HEIGHTFIELD
    assert item.feature.depth_mm == 4.0
    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 100.0
    assert item.geometry.data["h_mm"] == 100.0
    assert item.geometry.data["white_is_high"] is True
    assert str(tmp_path / "relief.png") == item.geometry.data["image_path"]


def test_heightfield_item_to_removal_intent(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    hf_intents = [i for i in intents if i.depth_profile.mode == "heightfield"]
    assert len(hf_intents) == 1
    intent = hf_intents[0]
    assert intent.hint_type == FeatureType.HEIGHTFIELD
    assert intent.depth_profile.z_top == 0.0
    assert intent.depth_profile.z_bottom == -4.0
    assert intent.depth_profile.white_is_high is True
    assert intent.bounds.width == pytest.approx(100.0)
    assert intent.bounds.height == pytest.approx(100.0)


def test_heightfield_intent_bounds_match_pml_size(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    intent = next(i for i in intents if i.depth_profile.mode == "heightfield")
    cx, cy = intent.bounds.center
    assert cx == pytest.approx(100.0)
    assert cy == pytest.approx(100.0)


def test_heightfield_intent_routes_to_planner_bucket(tmp_path: Path):
    from adapters.removal_to_planner import removal_intents_to_planner_input

    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)

    planner_input = removal_intents_to_planner_input(intents)
    assert planner_input.profiles == ()
    assert planner_input.pockets == ()
    assert len(planner_input.heightfields) == 1
    hf = planner_input.heightfields[0]
    assert hf.width_mm == 100.0
    assert hf.height_mm == 100.0
    assert hf.depth_mm == 4.0
    assert len(hf.tools) == 1
    assert hf.tools[0].tool_name == "1_4_flat"


def test_heightfield_blueprint_svg_embeds_image_and_border(tmp_path: Path):
    from export.blueprint_svg import render_blueprint_svg

    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    svg = render_blueprint_svg(flat, theme="dark", y_origin="back")
    assert "HEIGHTFIELD_OVERLAYS" in svg
    assert "data:image/png;base64," in svg
    assert 'class="heightfield-border"' in svg or "heightfield-border" in svg


def test_heightfield_blueprint_svg_print_theme_has_border(tmp_path: Path):
    from export.blueprint_svg import render_blueprint_svg

    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    svg = render_blueprint_svg(flat, theme="print", y_origin="back")
    assert "HEIGHTFIELD_OVERLAYS" in svg
    assert ".heightfield-border" in svg
    assert "#cc6600" in svg


def test_heightfield_svg_image_right_side_up_in_back_origin(tmp_path: Path):
    """Y-flip regression: in back-origin SVG, the Image y must be transformed consistently with its Rect border
    so the image is placed within the same visual bounds (right-side-up)."""
    from xml.etree import ElementTree as ET

    from export.blueprint_svg import render_blueprint_svg

    _write_synthetic_png(tmp_path / "relief.png")
    comp_ast = replace(parse_pml_yaml(_minimal_pml("relief.png")), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    svg = render_blueprint_svg(flat, theme="dark", y_origin="back")

    root = ET.fromstring(svg)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    images = root.findall(".//svg:image", ns)
    assert len(images) == 1
    image_el = images[0]
    image_y = float(image_el.attrib["y"])
    image_h = float(image_el.attrib["height"])

    borders = [r for r in root.findall(".//svg:rect", ns) if r.attrib.get("id", "").endswith("_border")]
    assert len(borders) == 1
    border_el = borders[0]
    border_y = float(border_el.attrib["y"])
    border_h = float(border_el.attrib["height"])

    assert abs(image_y - border_y) < 0.01
    assert abs(image_h - border_h) < 0.01
