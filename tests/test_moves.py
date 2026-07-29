from __future__ import annotations

import dataclasses
from typing import get_args

import pytest

from cam.model.tool import Tool
from cam.moves import (
    CommentMove,
    CutMove,
    DwellMove,
    MotionMove,
    Move,
    RapidMove,
    RetractMove,
    SetFeedMove,
    SetRpmMove,
    XYMove,
)
from cam.native import _native  # type: ignore[attr-defined]
from cam.native.core import _dict_to_move, post_gcode
from cam.post.gcode import _move_to_dict


def test_comment_move_construction():
    m = CommentMove(text="hello")
    assert m.text == "hello"


def test_set_rpm_move_construction():
    m = SetRpmMove(rpm=12000.0)
    assert m.rpm == 12000.0


def test_set_feed_move_construction():
    m = SetFeedMove(feed=900.0)
    assert m.feed == 900.0


def test_rapid_move_defaults():
    m = RapidMove()
    assert m.x is None
    assert m.y is None
    assert m.z is None


def test_rapid_move_with_coords():
    m = RapidMove(x=10.0, y=20.0, z=5.0)
    assert m.x == 10.0
    assert m.y == 20.0
    assert m.z == 5.0


def test_cut_move_defaults():
    m = CutMove()
    assert m.x is None
    assert m.y is None
    assert m.z is None
    assert m.feed is None


def test_retract_move_construction():
    m = RetractMove(z=6.0)
    assert m.z == 6.0


def test_frozen_dataclasses_immutable():
    m = RapidMove(x=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.x = 2.0  # type: ignore[misc]


def test_xymove_isinstance():
    assert isinstance(RapidMove(), XYMove)
    assert isinstance(CutMove(), XYMove)
    assert not isinstance(RetractMove(z=5.0), XYMove)
    assert not isinstance(CommentMove(text="x"), XYMove)


def test_motionmove_isinstance():
    assert isinstance(RapidMove(), MotionMove)
    assert isinstance(CutMove(), MotionMove)
    assert isinstance(RetractMove(z=5.0), MotionMove)
    assert not isinstance(CommentMove(text="x"), MotionMove)
    assert not isinstance(SetRpmMove(rpm=100.0), MotionMove)


def test_move_to_dict_comment():
    d = _move_to_dict(CommentMove(text="foo"))
    assert d == {"kind": "comment", "text": "foo"}


def test_move_to_dict_set_rpm():
    d = _move_to_dict(SetRpmMove(rpm=12000.0))
    assert d == {"kind": "set_rpm", "rpm": 12000.0}


def test_move_to_dict_set_feed():
    d = _move_to_dict(SetFeedMove(feed=900.0))
    assert d == {"kind": "set_feed", "feed": 900.0}


def test_move_to_dict_rapid():
    d = _move_to_dict(RapidMove(x=1.0, y=2.0, z=3.0))
    assert d == {"kind": "rapid", "x": 1.0, "y": 2.0, "z": 3.0}


def test_move_to_dict_cut():
    d = _move_to_dict(CutMove(x=1.0, y=2.0, z=-5.0, feed=900.0))
    assert d == {"kind": "cut", "x": 1.0, "y": 2.0, "z": -5.0, "feed": 900.0}


def test_move_to_dict_retract():
    d = _move_to_dict(RetractMove(z=6.0))
    assert d == {"kind": "retract", "z": 6.0}


def test_move_to_dict_rapid_with_margin():
    d = _move_to_dict(RapidMove(x=100.0, y=200.0, z=5.0), margin_mm=10.0)
    assert d == {"kind": "rapid", "x": 110.0, "y": 210.0, "z": 5.0}


def test_move_to_dict_cut_with_margin():
    d = _move_to_dict(CutMove(x=100.0, y=200.0, z=-5.0, feed=900.0), margin_mm=10.0)
    assert d == {"kind": "cut", "x": 110.0, "y": 210.0, "z": -5.0, "feed": 900.0}


def test_move_to_dict_rapid_with_margin_and_front_flip():
    d = _move_to_dict(
        RapidMove(x=100.0, y=200.0, z=5.0),
        margin_mm=10.0,
        sheet_height=800.0,
        y_origin="front",
    )
    assert d == {"kind": "rapid", "x": 110.0, "y": 800.0 - 210.0, "z": 5.0}


def test_move_to_dict_cut_with_margin_and_front_flip():
    d = _move_to_dict(
        CutMove(x=100.0, y=200.0, z=-5.0, feed=900.0),
        margin_mm=10.0,
        sheet_height=800.0,
        y_origin="front",
    )
    assert d == {"kind": "cut", "x": 110.0, "y": 800.0 - 210.0, "z": -5.0, "feed": 900.0}


def test_move_to_dict_preserves_none_xy_with_margin():
    d = _move_to_dict(RapidMove(z=5.0), margin_mm=10.0)
    assert d == {"kind": "rapid", "x": None, "y": None, "z": 5.0}


def test_move_to_dict_preserves_none_y_with_front_flip():
    d = _move_to_dict(
        CutMove(x=100.0, z=-5.0, feed=900.0),
        margin_mm=10.0,
        sheet_height=800.0,
        y_origin="front",
    )
    assert d == {"kind": "cut", "x": 110.0, "y": None, "z": -5.0, "feed": 900.0}


def test_move_to_dict_non_xy_move_ignores_margin():
    d = _move_to_dict(SetRpmMove(rpm=10000.0), margin_mm=10.0)
    assert d == {"kind": "set_rpm", "rpm": 10000.0}


def test_dict_to_move_comment_sparse():
    m = _dict_to_move({"kind": "comment", "text": "test"})
    assert isinstance(m, CommentMove)
    assert m.text == "test"


def test_dict_to_move_comment_dense():
    m = _dict_to_move(
        {
            "kind": "comment",
            "text": "dense",
            "x": None,
            "y": None,
            "z": None,
            "feed": None,
            "rpm": None,
        }
    )
    assert isinstance(m, CommentMove)
    assert m.text == "dense"


def test_dict_to_move_set_rpm():
    m = _dict_to_move({"kind": "set_rpm", "rpm": 14000.0})
    assert isinstance(m, SetRpmMove)
    assert m.rpm == 14000.0


def test_dict_to_move_set_feed():
    m = _dict_to_move({"kind": "set_feed", "feed": 800.0})
    assert isinstance(m, SetFeedMove)
    assert m.feed == 800.0


def test_dict_to_move_rapid():
    m = _dict_to_move({"kind": "rapid", "x": 10.0, "y": 20.0, "z": 5.0})
    assert isinstance(m, RapidMove)
    assert m.x == 10.0
    assert m.y == 20.0
    assert m.z == 5.0


def test_dict_to_move_rapid_sparse():
    m = _dict_to_move({"kind": "rapid", "z": 5.0})
    assert isinstance(m, RapidMove)
    assert m.x is None
    assert m.y is None
    assert m.z == 5.0


def test_dict_to_move_cut():
    m = _dict_to_move({"kind": "cut", "x": 5.0, "y": None, "z": -3.0, "feed": 900.0})
    assert isinstance(m, CutMove)
    assert m.x == 5.0
    assert m.y is None
    assert m.z == -3.0
    assert m.feed == 900.0


def test_dict_to_move_retract():
    m = _dict_to_move({"kind": "retract", "z": 6.0})
    assert isinstance(m, RetractMove)
    assert m.z == 6.0


def test_dict_to_move_unknown_kind():
    with pytest.raises(ValueError, match="Unknown move kind"):
        _dict_to_move({"kind": "bogus"})


def test_post_gcode_rejects_unknown_move_kind():
    with pytest.raises(
        ValueError,
        match=(
            r"post_gcode: move\.kind must be one of "
            r"comment\|set_rpm\|set_feed\|rapid\|cut\|retract\|dwell, got 'bogus'"
        ),
    ):
        post_gcode([{"kind": "bogus"}])


def test_round_trip_rapid():
    m = RapidMove(x=1.5, y=2.5, z=3.5)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_cut():
    m = CutMove(x=1.0, y=None, z=-5.0, feed=800.0)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_comment():
    m = CommentMove(text="roundtrip")
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_set_rpm():
    m = SetRpmMove(rpm=15000.0)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_set_feed():
    m = SetFeedMove(feed=1200.0)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_retract():
    m = RetractMove(z=7.5)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_dwell():
    m = DwellMove(seconds=1.5)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_post_gcode_round_trips_all_seven_kinds():
    moves: list[dict] = [
        {"kind": "comment", "text": "all kinds"},
        {"kind": "set_rpm", "rpm": 12000.0},
        {"kind": "set_feed", "feed": 900.0},
        {"kind": "rapid", "x": 10.0, "y": 20.0, "z": 5.0},
        {"kind": "cut", "x": 30.0, "y": 40.0, "z": -3.0, "feed": 600.0},
        {"kind": "retract", "z": 6.0},
        {"kind": "dwell", "seconds": 2.0},
    ]
    text = post_gcode(moves)
    assert "(all kinds)" in text
    assert "S12000" in text
    assert "F900" in text
    assert "G0 X10" in text
    assert "X30" in text and "Y40" in text and "Z-3" in text
    assert "Z6" in text
    assert "G4 P2" in text


TOOL = Tool(name="em6", diameter=6.0, rpm=12000.0, feed_xy=900.0, feed_z=300.0)
SQUARE = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0), (0.0, 0.0)]
FACE = {"outer": SQUARE, "depth": 5.0, "safe_z": 5.0}
HOLES = [{"x": 10.0, "y": 10.0, "diameter": 6.0, "depth": 5.0}]
BORE_HOLE = {"x": 10.0, "y": 10.0, "diameter": 12.0, "depth": 5.0}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 0.001])
def test_plan_profile_rejects_invalid_step_down(bad):
    with pytest.raises(ValueError, match=r"plan_profile: step_down_mm must be finite"):
        _native.plan_profile(SQUARE, TOOL, 5.0, bad, 5.0, 0.0)


def test_plan_profile_rejects_negative_step_down_names_value():
    with pytest.raises(ValueError, match=r"step_down_mm .* got -1"):
        _native.plan_profile(SQUARE, TOOL, 5.0, -1.0, 5.0, 0.0)


def test_plan_profile_zero_step_down_uses_default():
    assert _native.plan_profile(SQUARE, TOOL, 5.0, 0.0, 5.0, 0.0)


def test_plan_drill_rejects_subfloor_peck():
    with pytest.raises(ValueError, match=r"plan_drill: peck_mm must be finite"):
        _native.plan_drill(HOLES, TOOL, 0.001, 5.0)


def test_plan_drill_zero_peck_uses_default():
    assert _native.plan_drill(HOLES, TOOL, 0.0, 5.0)


def test_plan_bore_rejects_subfloor_step_down():
    with pytest.raises(ValueError, match=r"plan_bore_helical: step_down_mm must be finite"):
        _native.plan_bore_helical(BORE_HOLE, TOOL, 0.001, 5.0)


def test_plan_bore_zero_step_down_uses_default():
    assert _native.plan_bore_helical(BORE_HOLE, TOOL, 0.0, 5.0)


def test_pocket_rejects_subfloor_step_down():
    with pytest.raises(ValueError, match=r"plan_pocket: step_down_mm must be finite and >= 0.01"):
        _native.plan_pocket(FACE, TOOL, 3.0, 1e-9, 0.0, "spiral")


def test_pocket_rejects_subfloor_step_down_reports_full_precision_value():
    with pytest.raises(ValueError, match=r"got 0\.0003333333333333333"):
        _native.plan_pocket(FACE, TOOL, 3.0, 1.0 / 3000.0, 0.0, "spiral")


def test_pocket_rejects_negative_step_over():
    with pytest.raises(ValueError, match=r"plan_pocket: step_over_mm must be finite"):
        _native.plan_pocket(FACE, TOOL, -1.0, 2.0, 0.0, "spiral")


def test_pocket_accepts_floor_step_down():
    assert _native.plan_pocket(FACE, TOOL, 3.0, 0.01, 0.0, "spiral")


def test_pocket_none_step_down_still_defaults():
    assert _native.plan_pocket(FACE, TOOL, 3.0, None, 0.0, "spiral")


def test_pocket_zero_step_over_still_clamps():
    assert _native.plan_pocket(FACE, TOOL, 0.0, 2.0, 0.0, "spiral")


def test_pocket_resolved_default_step_down_names_the_binding():
    tiny = Tool(name="tiny", diameter=0.0199, rpm=12000.0, feed_xy=900.0, feed_z=300.0)
    with pytest.raises(ValueError, match=r"plan_pocket: resolved step_down_mm must be finite and >= 0.01"):
        _native.plan_pocket(FACE, tiny, 3.0, None, 0.0, "spiral")


def test_pocket_explicit_step_down_bypasses_resolved_default():
    tiny = Tool(name="tiny", diameter=0.0199, rpm=12000.0, feed_xy=900.0, feed_z=300.0)
    assert _native.plan_pocket(FACE, tiny, 3.0, 0.5, 0.0, "spiral")


def _native_planner_dicts() -> dict[str, list[dict]]:
    return {
        "plan_pocket": _native.plan_pocket(FACE, TOOL, 3.0, 2.0, 0.0, "raster"),
        "plan_profile": _native.plan_profile(SQUARE, TOOL, 5.0, 2.0, 5.0, 0.0),
        "plan_drill": _native.plan_drill(HOLES, TOOL, 2.0, 5.0),
        "plan_bore_helical": _native.plan_bore_helical(BORE_HOLE, TOOL, 2.0, 5.0),
    }


_EMITTED_PAYLOAD_FIELDS = {
    CommentMove: ("text",),
    SetRpmMove: ("rpm",),
    SetFeedMove: ("feed",),
    RapidMove: ("x", "y", "z"),
    CutMove: ("x", "y", "z", "feed"),
    RetractMove: ("z",),
    DwellMove: ("seconds",),
}


@pytest.mark.parametrize("planner", sorted(_native_planner_dicts()))
def test_native_emitter_kinds_all_decode(planner):
    dicts = _native_planner_dicts()[planner]
    assert dicts
    for d in dicts:
        move = _dict_to_move(d)
        for field in _EMITTED_PAYLOAD_FIELDS[type(move)]:
            assert getattr(move, field) == d[field]


def test_native_emitter_covers_all_kinds_except_dwell():
    kinds = {d["kind"] for dicts in _native_planner_dicts().values() for d in dicts}
    assert kinds == {"comment", "cut", "rapid", "retract", "set_feed", "set_rpm"}


def test_every_move_union_member_has_a_native_kind():
    samples: dict[type, dict] = {
        CommentMove: {"kind": "comment", "text": "x"},
        SetRpmMove: {"kind": "set_rpm", "rpm": 12000.0},
        SetFeedMove: {"kind": "set_feed", "feed": 900.0},
        RapidMove: {"kind": "rapid", "x": 1.0, "y": 2.0, "z": 5.0},
        CutMove: {"kind": "cut", "x": 1.0, "y": 2.0, "z": -3.0, "feed": 600.0},
        RetractMove: {"kind": "retract", "z": 6.0},
        DwellMove: {"kind": "dwell", "seconds": 1.0},
    }
    assert set(get_args(Move)) == set(samples)
    for sample in samples.values():
        assert post_gcode([sample])


def test_retract_absent_z_resolves_to_safe_z():
    assert "G0 Z5.000" in post_gcode([{"kind": "retract", "z": None}], safe_z=5.0)
    assert "G0 Z5.000" in post_gcode([{"kind": "retract"}], safe_z=5.0)
