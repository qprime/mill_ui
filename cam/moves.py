from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class CommentMove:
    text: str


@dataclass(frozen=True)
class SetRpmMove:
    rpm: float


@dataclass(frozen=True)
class SetFeedMove:
    feed: float


@dataclass(frozen=True)
class RapidMove:
    x: float | None = None
    y: float | None = None
    z: float | None = None


@dataclass(frozen=True)
class CutMove:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    feed: float | None = None


@dataclass(frozen=True)
class RetractMove:
    z: float


Move = Union[CommentMove, SetRpmMove, SetFeedMove, RapidMove, CutMove, RetractMove]

MotionMove = Union[RapidMove, CutMove, RetractMove]
XYMove = Union[RapidMove, CutMove]


__all__ = [
    "CommentMove",
    "SetRpmMove",
    "SetFeedMove",
    "RapidMove",
    "CutMove",
    "RetractMove",
    "Move",
    "MotionMove",
    "XYMove",
]
