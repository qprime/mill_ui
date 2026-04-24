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


def test_heightfield_tool_assignment_rejects_finish():
    with pytest.raises(ValueError, match="finish not yet implemented"):
        HeightfieldToolAssignment(tool_name="1_4_ball", role="finish", stepover_frac=0.5, stepdown_mm=1.0)


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


def test_pml_finish_role_rejected(tmp_path: Path):
    _write_synthetic_png(tmp_path / "relief.png")
    tools_block = """          tools:
            - tool: 1mm_ball
              role: finish
              stepover: 30%
              stepdown: 0.5mm"""
    with pytest.raises(PMLParseError, match="finish role not yet implemented"):
        parse_pml_yaml(_pml_with_tools("relief.png", tools_block))


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
