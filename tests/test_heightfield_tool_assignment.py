from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from adapters.ast_to_removal import ast_to_removal_intents
from domains.domain import Bounds2D
from ir.removal_intent import DepthProfile, HeightfieldToolAssignment, RemovalIntent
from pml.yaml_parser import PMLParseError, parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def _write_synthetic_png(path: Path, size: int = 32) -> None:
    arr = np.linspace(0, 65535, size * size, dtype=np.uint16).reshape(size, size)
    Image.fromarray(arr, mode="I;16").save(path, format="PNG")


def _pml_with_tools(image_rel: str, tools_block: str) -> str:
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
{tools_block}
"""


def test_heightfield_tool_assignment_valid():
    a = HeightfieldToolAssignment(tool_name="1_4_flat", role="rough", stepover_frac=0.6, stepdown_mm=2.0)
    assert a.tool_name == "1_4_flat"
    assert a.stepdown_mm == 2.0


def test_heightfield_tool_assignment_finish_role_accepted():
    a = HeightfieldToolAssignment(tool_name="1_4_ball", role="finish", stepover_frac=0.1, angle_deg=0.0)
    assert a.role == "finish"
    assert a.angle_deg == 0.0


def test_heightfield_tool_assignment_rejects_unknown_role():
    with pytest.raises(ValueError, match="must be 'rough' or 'finish'"):
        HeightfieldToolAssignment(tool_name="t", role="semi", stepover_frac=0.5)


def test_heightfield_tool_assignment_finish_requires_angle():
    with pytest.raises(ValueError, match="finish role requires angle_deg"):
        HeightfieldToolAssignment(tool_name="1_4_ball", role="finish", stepover_frac=0.1)


def test_heightfield_tool_assignment_rough_rejects_angle():
    with pytest.raises(ValueError, match="angle_deg only valid for finish"):
        HeightfieldToolAssignment(tool_name="t", role="rough", stepover_frac=0.6, angle_deg=45.0)


def test_heightfield_tool_assignment_finish_rejects_stepdown():
    with pytest.raises(ValueError, match="stepdown_mm not valid for finish"):
        HeightfieldToolAssignment(
            tool_name="1_4_ball", role="finish", stepover_frac=0.1, stepdown_mm=0.5, angle_deg=0.0
        )


def test_heightfield_tool_assignment_angle_must_be_finite():
    import math as _math

    with pytest.raises(ValueError, match="angle_deg must be finite"):
        HeightfieldToolAssignment(tool_name="t", role="finish", stepover_frac=0.1, angle_deg=_math.inf)
    with pytest.raises(ValueError, match="angle_deg must be finite"):
        HeightfieldToolAssignment(tool_name="t", role="finish", stepover_frac=0.1, angle_deg=_math.nan)


def test_heightfield_tool_assignment_positional_construction_unchanged():
    a = HeightfieldToolAssignment("6mm_flat", "rough", 0.6, 2.0)
    assert a.tool_name == "6mm_flat"
    assert a.stepdown_mm == 2.0
    assert a.angle_deg is None


def test_heightfield_tool_assignment_finish_to_dict_includes_angle():
    a = HeightfieldToolAssignment(tool_name="1mm_ball", role="finish", stepover_frac=0.12, angle_deg=90.0)
    d = a.to_dict()
    assert d["angle_deg"] == 90.0
    assert "stepdown_mm" not in d
    assert HeightfieldToolAssignment.from_dict(d) == a


def test_heightfield_tool_assignment_from_dict_finish_requires_angle():
    with pytest.raises(ValueError, match="finish role requires angle_deg"):
        HeightfieldToolAssignment.from_dict({"tool_name": "1mm_ball", "role": "finish", "stepover_frac": 0.12})


def test_heightfield_tool_assignment_rejects_bad_stepover():
    with pytest.raises(ValueError, match="stepover_frac"):
        HeightfieldToolAssignment(tool_name="t", role="rough", stepover_frac=1.5, stepdown_mm=1.0)


def test_heightfield_tool_assignment_serialization_round_trip():
    a = HeightfieldToolAssignment(tool_name="6mm_flat", role="rough", stepover_frac=0.6, stepdown_mm=2.0)
    data = a.to_dict()
    assert HeightfieldToolAssignment.from_dict(data) == a


def test_heightfield_tool_assignment_stepdown_optional_round_trip():
    a = HeightfieldToolAssignment(tool_name="6mm_flat", role="rough", stepover_frac=0.6, stepdown_mm=None)
    data = a.to_dict()
    assert "stepdown_mm" not in data
    assert HeightfieldToolAssignment.from_dict(data) == a


def test_removal_intent_requires_tools_for_heightfield():
    with pytest.raises(ValueError, match="requires at least one tool"):
        RemovalIntent(
            region_id="r",
            bounds=Bounds2D(x_min=0, x_max=10, y_min=0, y_max=10),
            depth_profile=DepthProfile.heightfield(z_top=0.0, z_bottom=-4.0, image_path="x.png"),
        )


def test_removal_intent_rejects_tools_for_non_heightfield():
    with pytest.raises(ValueError, match="only valid for heightfield"):
        RemovalIntent(
            region_id="r",
            bounds=Bounds2D(x_min=0, x_max=10, y_min=0, y_max=10),
            depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-4.0),
            heightfield_tools=(
                HeightfieldToolAssignment(tool_name="t", role="rough", stepover_frac=0.6, stepdown_mm=1.0),
            ),
        )


def test_removal_intent_rejects_duplicate_tool_names():
    with pytest.raises(ValueError, match="duplicate heightfield tool name"):
        RemovalIntent(
            region_id="r",
            bounds=Bounds2D(x_min=0, x_max=10, y_min=0, y_max=10),
            depth_profile=DepthProfile.heightfield(z_top=0.0, z_bottom=-4.0, image_path="x.png"),
            heightfield_tools=(
                HeightfieldToolAssignment(tool_name="t", role="rough", stepover_frac=0.6, stepdown_mm=1.0),
                HeightfieldToolAssignment(tool_name="t", role="rough", stepover_frac=0.5, stepdown_mm=1.0),
            ),
        )


def test_pml_tools_list_parses(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 6mm_flat
              role: rough
              stepover: 60%
              stepdown: 2mm
            - tool: 3mm_flat
              role: rough
              stepover: 50%
              stepdown: 1mm"""
    comp_ast = replace(parse_pml_yaml(_pml_with_tools("relief.png", tools_block)), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    hf_intents = [i for i in intents if i.depth_profile.mode == "heightfield"]
    assert len(hf_intents) == 1
    intent = hf_intents[0]
    assert len(intent.heightfield_tools) == 2
    names = [t.tool_name for t in intent.heightfield_tools]
    assert names == ["6mm_flat", "3mm_flat"]
    assert intent.heightfield_tools[0].stepover_frac == pytest.approx(0.6)
    assert intent.heightfield_tools[1].stepover_frac == pytest.approx(0.5)
    assert intent.heightfield_tools[0].stepdown_mm == 2.0
    assert intent.heightfield_tools[1].stepdown_mm == 1.0


def test_pml_finish_role_accepted(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 6mm_flat
              role: rough
              stepover: 60%
              stepdown: 2mm
            - tool: 1mm_ball
              role: finish
              stepover: 12%
              angle: 90"""
    comp_ast = replace(parse_pml_yaml(_pml_with_tools("relief.png", tools_block)), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    hf_intents = [i for i in intents if i.depth_profile.mode == "heightfield"]
    assert len(hf_intents) == 1
    intent = hf_intents[0]
    assert len(intent.heightfield_tools) == 2
    rough, finish = intent.heightfield_tools
    assert rough.role == "rough"
    assert finish.role == "finish"
    assert finish.angle_deg == pytest.approx(90.0)
    assert finish.stepdown_mm is None


def test_pml_finish_rejects_stepdown(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 1mm_ball
              role: finish
              stepover: 12%
              angle: 0
              stepdown: 0.5mm"""
    with pytest.raises(PMLParseError, match="must not specify 'stepdown'"):
        parse_pml_yaml(_pml_with_tools("relief.png", tools_block))


def test_pml_rough_rejects_angle(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 6mm_flat
              role: rough
              stepover: 60%
              stepdown: 2mm
              angle: 45"""
    with pytest.raises(PMLParseError, match=r"angle.*only valid on finish"):
        parse_pml_yaml(_pml_with_tools("relief.png", tools_block))


def test_pml_finish_angle_normalized_to_0_180(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 6mm_flat
              role: rough
              stepover: 60%
              stepdown: 2mm
            - tool: 1mm_ball
              role: finish
              stepover: 12%
              angle: 270"""
    comp_ast = replace(parse_pml_yaml(_pml_with_tools("relief.png", tools_block)), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    finish = intents[0].heightfield_tools[1]
    assert finish.angle_deg == pytest.approx(90.0)


def test_pml_finish_omitted_angle_defaults_to_zero(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 6mm_flat
              role: rough
              stepover: 60%
              stepdown: 2mm
            - tool: 1mm_ball
              role: finish
              stepover: 12%"""
    comp_ast = replace(parse_pml_yaml(_pml_with_tools("relief.png", tools_block)), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    finish = intents[0].heightfield_tools[1]
    assert finish.angle_deg == pytest.approx(0.0)


def test_pml_missing_tools_list_resolves_but_skips_at_ir(tmp_path: Path):
    """Without a tools: list, adapter hint conversion raises — the item is logged-and-skipped."""
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = ""
    comp_ast = replace(parse_pml_yaml(_pml_with_tools("relief.png", tools_block)), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    warnings: list[str] = []
    intents = ast_to_removal_intents(flat, warnings=warnings)
    assert not any(i.depth_profile.mode == "heightfield" for i in intents)
    assert any("tool" in w for w in warnings)
