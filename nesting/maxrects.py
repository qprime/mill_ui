from __future__ import annotations

from enum import Enum
from typing import Any

from nesting.types import FreeRect, PlacementResult


class MaxRectsHeuristic(Enum):
    BEST_AREA_FIT = "baf"
    BEST_SHORT_SIDE_FIT = "bssf"
    BEST_LONG_SIDE_FIT = "blsf"
    CONTACT_POINT = "cp"


def _score_baf(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    needed_w = part_w + gap
    needed_h = part_h + gap
    return rect.area - (needed_w * needed_h)


def _score_bssf(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    needed_w = part_w + gap
    needed_h = part_h + gap
    leftover_w = rect.width - needed_w
    leftover_h = rect.height - needed_h
    return min(leftover_w, leftover_h)


def _score_blsf(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    needed_w = part_w + gap
    needed_h = part_h + gap
    leftover_w = rect.width - needed_w
    leftover_h = rect.height - needed_h
    return max(leftover_w, leftover_h)


def _score_contact_point(
    rect: FreeRect,
    part_w: float,
    part_h: float,
    gap: float,
    bin_width: float,
    bin_height: float,
    placements: list[PlacementResult],
    parts_info: dict,
) -> float:
    needed_w = part_w + gap
    needed_h = part_h + gap

    px1, py1 = rect.x, rect.y
    px2, py2 = rect.x + needed_w, rect.y + needed_h

    contact = 0.0

    if px1 <= 0:
        contact += needed_h
    if py1 <= 0:
        contact += needed_w
    if px2 >= bin_width:
        contact += needed_h
    if py2 >= bin_height:
        contact += needed_w

    for p in placements:
        pw, ph = parts_info.get(id(p.metadata), (0, 0))
        if p.rotated:
            pw, ph = ph, pw

        ox1 = p.x - pw / 2
        oy1 = p.y - ph / 2
        ox2 = p.x + pw / 2
        oy2 = p.y + ph / 2

        tolerance = gap + 0.1

        if abs(ox2 - px1) < tolerance:
            overlap = min(oy2, py2) - max(oy1, py1)
            if overlap > 0:
                contact += overlap

        if abs(ox1 - px2) < tolerance:
            overlap = min(oy2, py2) - max(oy1, py1)
            if overlap > 0:
                contact += overlap

        if abs(oy2 - py1) < tolerance:
            overlap = min(ox2, px2) - max(ox1, px1)
            if overlap > 0:
                contact += overlap

        if abs(oy1 - py2) < tolerance:
            overlap = min(ox2, px2) - max(ox1, px1)
            if overlap > 0:
                contact += overlap

    return -contact


def _find_best_rect(
    part_w: float,
    part_h: float,
    free_rects: list[FreeRect],
    gap: float,
    allow_rotation: bool,
    heuristic: MaxRectsHeuristic,
    bin_width: float = 0,
    bin_height: float = 0,
    placements: list[PlacementResult] | None = None,
    parts_info: dict | None = None,
) -> tuple[int, bool] | None:
    best_idx = -1
    best_rotated = False
    best_score = float("inf")
    best_secondary = float("inf")

    for i, rect in enumerate(free_rects):
        for rotated in [False, True]:
            if rotated and not allow_rotation:
                continue
            if rotated and part_w == part_h:
                continue

            pw = part_h if rotated else part_w
            ph = part_w if rotated else part_h

            if not rect.can_fit(pw, ph, gap):
                continue

            if heuristic == MaxRectsHeuristic.BEST_AREA_FIT:
                score = _score_baf(rect, pw, ph, gap)
                secondary = _score_bssf(rect, pw, ph, gap)
            elif heuristic == MaxRectsHeuristic.BEST_SHORT_SIDE_FIT:
                score = _score_bssf(rect, pw, ph, gap)
                secondary = _score_baf(rect, pw, ph, gap)
            elif heuristic == MaxRectsHeuristic.BEST_LONG_SIDE_FIT:
                score = _score_blsf(rect, pw, ph, gap)
                secondary = _score_baf(rect, pw, ph, gap)
            elif heuristic == MaxRectsHeuristic.CONTACT_POINT:
                score = _score_contact_point(
                    rect, pw, ph, gap, bin_width, bin_height, placements or [], parts_info or {}
                )
                secondary = _score_baf(rect, pw, ph, gap)
            else:
                score = _score_bssf(rect, pw, ph, gap)
                secondary = _score_baf(rect, pw, ph, gap)

            if score < best_score or (score == best_score and secondary < best_secondary):
                best_score = score
                best_secondary = secondary
                best_idx = i
                best_rotated = rotated

    if best_idx < 0:
        return None
    return (best_idx, best_rotated)


def _split_free_rect(
    free_rect: FreeRect,
    placed_x: float,
    placed_y: float,
    placed_w: float,
    placed_h: float,
    gap: float,
) -> list[FreeRect]:

    px1 = placed_x
    py1 = placed_y
    px2 = placed_x + placed_w + gap
    py2 = placed_y + placed_h + gap

    new_rects = []

    if px1 > free_rect.x:
        new_rects.append(
            FreeRect(
                x=free_rect.x,
                y=free_rect.y,
                width=px1 - free_rect.x,
                height=free_rect.height,
            )
        )

    if px2 < free_rect.right:
        new_rects.append(
            FreeRect(
                x=px2,
                y=free_rect.y,
                width=free_rect.right - px2,
                height=free_rect.height,
            )
        )

    if py1 > free_rect.y:
        new_rects.append(
            FreeRect(
                x=free_rect.x,
                y=free_rect.y,
                width=free_rect.width,
                height=py1 - free_rect.y,
            )
        )

    if py2 < free_rect.top:
        new_rects.append(
            FreeRect(
                x=free_rect.x,
                y=py2,
                width=free_rect.width,
                height=free_rect.top - py2,
            )
        )

    return new_rects


def _prune_contained_rects(free_rects: list[FreeRect]) -> list[FreeRect]:
    result = []
    for i, rect in enumerate(free_rects):
        is_contained = False
        for j, other in enumerate(free_rects):
            if i != j and other.contains(rect):
                is_contained = True
                break
        if not is_contained:
            result.append(rect)
    return result


def maxrects_pack(
    parts: list[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
    gap: float = 0.0,
    sort_by_area: bool = True,
    heuristic: MaxRectsHeuristic = MaxRectsHeuristic.BEST_AREA_FIT,
) -> list[PlacementResult]:
    if bin_width <= 0 or bin_height <= 0:
        return []

    indexed_parts = [(i, w, h, rot, meta) for i, (w, h, rot, meta) in enumerate(parts)]

    if sort_by_area:
        indexed_parts.sort(key=lambda p: p[1] * p[2], reverse=True)

    parts_info = {}
    for _, w, h, _, meta in indexed_parts:
        parts_info[id(meta)] = (w, h)

    free_rects = [FreeRect(x=0, y=0, width=bin_width, height=bin_height)]

    placements: list[PlacementResult] = []

    for _, part_w, part_h, allow_rotation, metadata in indexed_parts:
        result = _find_best_rect(
            part_w, part_h, free_rects, gap, allow_rotation, heuristic, bin_width, bin_height, placements, parts_info
        )

        if result is None:
            continue

        rect_idx, rotated = result
        rect = free_rects[rect_idx]

        actual_w = part_h if rotated else part_w
        actual_h = part_w if rotated else part_h

        placed_x = rect.x
        placed_y = rect.y

        center_x = placed_x + actual_w / 2
        center_y = placed_y + actual_h / 2

        placements.append(
            PlacementResult(
                x=center_x,
                y=center_y,
                rotated=rotated,
                metadata=metadata,
            )
        )

        placed_rect = FreeRect(
            x=placed_x,
            y=placed_y,
            width=actual_w + gap,
            height=actual_h + gap,
        )

        new_free_rects = []
        for free_rect in free_rects:
            if free_rect.intersects(placed_rect):
                splits = _split_free_rect(free_rect, placed_x, placed_y, actual_w, actual_h, gap)
                new_free_rects.extend(splits)
            else:
                new_free_rects.append(free_rect)

        free_rects = _prune_contained_rects(new_free_rects)

    return placements


__all__ = [
    "FreeRect",
    "MaxRectsHeuristic",
    "PlacementResult",
    "maxrects_pack",
]
