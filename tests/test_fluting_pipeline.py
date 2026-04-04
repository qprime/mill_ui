from __future__ import annotations

import pytest

from adapters.ast_to_removal import item_to_removal_intent
from adapters.removal_to_planner import _intent_to_feature_input
from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CutMove, RapidMove, RetractMove
from cam.ops.engrave import engrave_lines_ramped
from layout_ast.layout import Feature, Geometry, Item, Placement
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def _make_engrave_line_item(
    start: tuple[float, float],
    end: tuple[float, float],
    depth_mm: float = 3.0,
    ramp_mm: float | None = 15.0,
) -> Item:
    cx = (start[0] + end[0]) / 2
    cy = (start[1] + end[1]) / 2
    return Item(
        kind="shape",
        type="Line",
        geometry=Geometry(
            data={
                "start": [start[0] - cx, start[1] - cy],
                "end": [end[0] - cx, end[1] - cy],
                "width_mm": 0.5,
            }
        ),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(type="engrave", depth_mm=depth_mm, ramp_mm=ramp_mm),
        shape_id="test_flute_0",
    )


def _make_setup(safe_z: float = 6.0) -> Setup:
    tool = Tool(name="test_engrave", diameter=1.0, rpm=20000, feed_xy=400.0, feed_z=100.0)
    stock = Stock(width=300.0, height=200.0, thickness=19.0)
    machine = Machine()
    return Setup(stock=stock, tool=tool, machine=machine, safe_z=safe_z)


# =============================================================================
# IR-Level Tests: ramp_mm survives adapter chain
# =============================================================================


def test_fluting_ramp_survives_to_removal_intent():
    item = _make_engrave_line_item((50, 50), (250, 50), ramp_mm=15.0)
    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
    assert intent.ramp_mm == 15.0


def test_fluting_ramp_survives_to_feature_input():
    item = _make_engrave_line_item((50, 50), (250, 50), ramp_mm=15.0)
    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
    feature_input = _intent_to_feature_input(intent)
    assert feature_input.ramp_mm == 15.0


def test_fluting_ramp_none_when_absent():
    item = _make_engrave_line_item((50, 50), (250, 50), ramp_mm=None)
    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
    assert intent.ramp_mm is None
    feature_input = _intent_to_feature_input(intent)
    assert feature_input.ramp_mm is None


def test_fluting_removal_intent_to_dict_includes_ramp():
    item = _make_engrave_line_item((50, 50), (250, 50), ramp_mm=15.0)
    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
    d = intent.to_dict()
    assert d["ramp_mm"] == 15.0


def test_fluting_removal_intent_to_dict_excludes_ramp_when_none():
    item = _make_engrave_line_item((50, 50), (250, 50), ramp_mm=None)
    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
    d = intent.to_dict()
    assert "ramp_mm" not in d


def test_fluting_feature_input_to_dict_includes_ramp():
    item = _make_engrave_line_item((50, 50), (250, 50), ramp_mm=15.0)
    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
    feature_input = _intent_to_feature_input(intent)
    d = feature_input.to_dict()
    assert d["ramp_mm"] == 15.0


# =============================================================================
# G-code Tests: engrave_lines_ramped
# =============================================================================


def test_ramped_engrave_z_profile():
    setup = _make_setup()
    lines = [[(0.0, 0.0), (100.0, 0.0)]]
    moves = engrave_lines_ramped(lines, setup, z=-3.0, ramp_mm=10.0)
    motion = [m for m in moves if isinstance(m, (RapidMove, CutMove, RetractMove))]
    z_values = [m.z for m in motion if m.z is not None]
    assert 0.0 in z_values
    assert -3.0 in z_values
    assert z_values[-1] == 6.0


def test_ramped_engrave_short_line():
    setup = _make_setup()
    lines = [[(0.0, 0.0), (10.0, 0.0)]]
    moves = engrave_lines_ramped(lines, setup, z=-3.0, ramp_mm=20.0)
    cut_moves = [m for m in moves if isinstance(m, CutMove) and m.z is not None and m.z < 0]
    assert len(cut_moves) == 1
    assert cut_moves[0].z == -3.0
    assert cut_moves[0].x == pytest.approx(5.0, abs=0.01)


def test_ramped_engrave_zero_ramp():
    setup = _make_setup()
    lines = [[(0.0, 0.0), (100.0, 0.0)]]
    moves = engrave_lines_ramped(lines, setup, z=-3.0, ramp_mm=0.0)
    motion = [m for m in moves if isinstance(m, (RapidMove, CutMove, RetractMove))]
    z_sequence = [m.z for m in motion if m.z is not None]
    assert -3.0 in z_sequence
    assert z_sequence[-1] == 6.0


def test_ramped_engrave_constant_section():
    setup = _make_setup()
    lines = [[(0.0, 0.0), (100.0, 0.0)]]
    moves = engrave_lines_ramped(lines, setup, z=-3.0, ramp_mm=10.0)
    cut_moves_no_z = [m for m in moves if isinstance(m, CutMove) and m.x is not None and m.z is None]
    assert len(cut_moves_no_z) == 1
    assert cut_moves_no_z[0].x == pytest.approx(90.0, abs=0.01)


def test_ramped_engrave_move_count():
    setup = _make_setup()
    lines = [[(0.0, 0.0), (100.0, 0.0)]]
    moves = engrave_lines_ramped(lines, setup, z=-3.0, ramp_mm=10.0)
    rapid_count = sum(1 for m in moves if isinstance(m, RapidMove))
    cut_count = sum(1 for m in moves if isinstance(m, CutMove))
    assert rapid_count == 1
    assert cut_count >= 4


# =============================================================================
# PML Round-Trip Tests
# =============================================================================


def test_fluting_json_round_trip_feature_ramp():
    from layout_ast.emitters import _feature_to_dict
    from layout_ast.parsers import _parse_feature

    feature = Feature(type="engrave", depth_mm=3.0, ramp_mm=15.0)
    d = _feature_to_dict(feature)
    assert d["ramp_mm"] == 15.0

    restored = _parse_feature(d)
    assert restored.ramp_mm == 15.0
    assert restored.depth_mm == 3.0
    assert restored.type == "engrave"


def test_fluting_json_round_trip_feature_ramp_none():
    from layout_ast.emitters import _feature_to_dict
    from layout_ast.parsers import _parse_feature

    feature = Feature(type="engrave", depth_mm=3.0)
    d = _feature_to_dict(feature)
    assert "ramp_mm" not in d

    restored = _parse_feature(d)
    assert restored.ramp_mm is None


def test_fluting_pml_round_trip():
    from pml.yaml_formatter import format_pml_yaml

    pml = """\
Sheet:
  width: 300mm
  height: 200mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: test_panel
    children:
    - Fluting:
        spacing: 20mm
        depth: 3mm
        ramp: 15mm
        angle: 45
        inset: 10mm
"""
    ast1 = parse_pml_yaml(pml)
    yaml_out = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(yaml_out)
    layout1 = resolve_layout(ast1)
    layout2 = resolve_layout(ast2)
    assert len(layout1.items) == len(layout2.items)
    for a, b in zip(layout1.items, layout2.items, strict=True):
        assert a.type == b.type
        if a.feature and b.feature:
            assert a.feature.ramp_mm == b.feature.ramp_mm
            assert a.feature.depth_mm == b.feature.depth_mm
