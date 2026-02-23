from __future__ import annotations

from dataclasses import replace

from cam.moves import (
    CommentMove,
    CutMove,
    Move,
    MotionMove,
    RapidMove,
    RetractMove,
    SetFeedMove,
    SetRpmMove,
)


def move_comment(text: str) -> CommentMove:
    return CommentMove(text=text)


def move_set_feed(feed: float) -> SetFeedMove:
    return SetFeedMove(feed=feed)


def move_set_rpm(rpm: float) -> SetRpmMove:
    return SetRpmMove(rpm=rpm)


def move_rapid(x=None, y=None, z=None) -> RapidMove:
    return RapidMove(x=x, y=y, z=z)


def move_cut(x=None, y=None, z=None, feed=None) -> CutMove:
    return CutMove(x=x, y=y, z=z, feed=feed)


def move_retract(z: float) -> RetractMove:
    return RetractMove(z=z)


def offset_moves_z(moves: list[Move], offset: float) -> list[Move]:
    if offset <= 0.0:
        return moves
    adjusted: list[Move] = []
    for mv in moves:
        if isinstance(mv, MotionMove) and mv.z is not None:
            z_val = float(mv.z)
            if z_val <= 0.0:
                adjusted.append(replace(mv, z=z_val - offset))
                continue
        adjusted.append(mv)
    return adjusted
