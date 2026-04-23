from __future__ import annotations

import dataclasses

import pytest

from cam.moves import (
    CommentMove,
    CutMove,
    MotionMove,
    RapidMove,
    RetractMove,
    SetFeedMove,
    SetRpmMove,
    XYMove,
)
from cam.native.core import _dict_to_move
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


def test_round_trip_rapid():
    m = RapidMove(x=1.5, y=2.5, z=3.5)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_cut():
    m = CutMove(x=1.0, y=None, z=-5.0, feed=800.0)
    assert _dict_to_move(_move_to_dict(m)) == m


def test_round_trip_comment():
    m = CommentMove(text="roundtrip")
    assert _dict_to_move(_move_to_dict(m)) == m
