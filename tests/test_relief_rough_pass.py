from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.moves import CutMove, RapidMove
from cam.planner.passes import PassAccumulator
from cam.planner.passes.relief.rough import plan_heightfield_passes
from cam.planner.passes.tools import ToolSelection
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def _write_gradient_png(path: Path, size: int = 32) -> None:
    xs = np.linspace(-1.0, 1.0, size)
    ys = np.linspace(-1.0, 1.0, size)
    xx, yy = np.meshgrid(xs, ys)
    heights = np.clip(1.0 - np.sqrt(xx * xx + yy * yy), 0.0, 1.0)
    arr = (heights * 65535).astype(np.uint16)
    Image.fromarray(arr, mode="I;16").save(path, format="PNG")


_PML_TWO_TOOLS = """Sheet:
  width: 200mm
  height: 200mm
  thickness: 19mm
  material: mdf

children:
- Rect:
    id: relief
    at: {{ x: 100mm, y: 100mm, width: 120mm, height: 120mm }}
    children:
      - Heightfield:
          image: {image}
          size: {{ width: 100mm, height: 100mm }}
          depth: 4mm
          white_is_high: true
          tools:
            - tool: tool_6
              role: rough
              stepover: 60%
              stepdown: 2mm
            - tool: tool_3
              role: rough
              stepover: 50%
              stepdown: 1mm
"""


def _fake_tool(name: str, diameter: float) -> ToolSelection:
    return ToolSelection(
        name=name,
        diameter=diameter,
        kind="flat",
        rpm=18000.0,
        feed_xy=1800.0,
        feed_z=600.0,
    )


def _fake_machine() -> Machine:
    return Machine(name="test")


def _build_planner_input(tmp_path: Path):
    _write_gradient_png(tmp_path / "relief.png")
    pml = _PML_TWO_TOOLS.format(image="relief.png")
    comp_ast = replace(parse_pml_yaml(pml), source_dir=str(tmp_path))
    flat = resolve_layout(comp_ast)
    intents = ast_to_removal_intents(flat)
    return removal_intents_to_planner_input(intents)


def test_rough_pass_produces_one_record_per_tool(tmp_path: Path):
    planner_input = _build_planner_input(tmp_path)
    tool_db = [_fake_tool("tool_6", 6.0), _fake_tool("tool_3", 3.0)]
    accumulator = PassAccumulator(
        machine=_fake_machine(),
        stock=Stock(width=200.0, height=200.0, thickness=19.0),
        safe_z=5.0,
        prime_spindle=False,
    )
    plan_heightfield_passes(planner_input.heightfields, accumulator=accumulator, tool_db=tool_db, config=Config())
    records = accumulator.passes()
    assert len(records) == 2
    diameters = sorted(r.tool_selection.diameter for r in records)
    assert diameters == [3.0, 6.0]


def test_rough_pass_emits_z_stepped_slices(tmp_path: Path):
    planner_input = _build_planner_input(tmp_path)
    tool_db = [_fake_tool("tool_6", 6.0), _fake_tool("tool_3", 3.0)]
    accumulator = PassAccumulator(
        machine=_fake_machine(),
        stock=Stock(width=200.0, height=200.0, thickness=19.0),
        safe_z=5.0,
        prime_spindle=False,
    )
    plan_heightfield_passes(planner_input.heightfields, accumulator=accumulator, tool_db=tool_db, config=Config())
    records = accumulator.passes()
    record_6 = next(r for r in records if abs(r.tool_selection.diameter - 6.0) < 1e-6)

    cut_zs = [m.z for m in record_6.moves if isinstance(m, CutMove) and m.z is not None]
    assert len(cut_zs) > 0
    assert min(cut_zs) >= -4.0 - 1e-3


def test_rough_pass_rapids_only_at_or_above_safe_z(tmp_path: Path):
    planner_input = _build_planner_input(tmp_path)
    tool_db = [_fake_tool("tool_6", 6.0), _fake_tool("tool_3", 3.0)]
    accumulator = PassAccumulator(
        machine=_fake_machine(),
        stock=Stock(width=200.0, height=200.0, thickness=19.0),
        safe_z=5.0,
        prime_spindle=False,
    )
    plan_heightfield_passes(planner_input.heightfields, accumulator=accumulator, tool_db=tool_db, config=Config())
    for record in accumulator.passes():
        for move in record.moves:
            if isinstance(move, RapidMove) and move.z is not None:
                assert move.z >= 5.0 - 1e-3, f"rapid below safe_z: {move}"


def test_rough_pass_never_cuts_below_depth(tmp_path: Path):
    planner_input = _build_planner_input(tmp_path)
    tool_db = [_fake_tool("tool_6", 6.0), _fake_tool("tool_3", 3.0)]
    accumulator = PassAccumulator(
        machine=_fake_machine(),
        stock=Stock(width=200.0, height=200.0, thickness=19.0),
        safe_z=5.0,
        prime_spindle=False,
    )
    plan_heightfield_passes(planner_input.heightfields, accumulator=accumulator, tool_db=tool_db, config=Config())
    depth_mm = 4.0
    for record in accumulator.passes():
        for move in record.moves:
            if isinstance(move, CutMove) and move.z is not None:
                assert move.z >= -depth_mm - 1e-3, f"cut below bottom: z={move.z}"


def test_rough_pass_missing_tool_errors(tmp_path: Path):
    planner_input = _build_planner_input(tmp_path)
    tool_db = [_fake_tool("other_tool", 5.0)]
    accumulator = PassAccumulator(
        machine=_fake_machine(),
        stock=Stock(width=200.0, height=200.0, thickness=19.0),
        safe_z=5.0,
        prime_spindle=False,
    )
    with pytest.raises(ValueError, match="not found"):
        plan_heightfield_passes(planner_input.heightfields, accumulator=accumulator, tool_db=tool_db, config=Config())
