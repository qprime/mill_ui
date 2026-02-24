from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from nesting.types import FreeRect, PlacementResult


def _score_fit(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    needed_w = part_w + gap
    needed_h = part_h + gap
    leftover_w = rect.width - needed_w
    leftover_h = rect.height - needed_h
    return min(leftover_w, leftover_h)


def _find_best_rect(
    part_w: float,
    part_h: float,
    free_rects: list[FreeRect],
    gap: float,
    allow_rotation: bool,
) -> tuple[int, bool] | None:
    best_idx = -1
    best_rotated = False
    best_score = float("inf")

    for i, rect in enumerate(free_rects):
        if rect.can_fit(part_w, part_h, gap):
            score = _score_fit(rect, part_w, part_h, gap)
            if score < best_score:
                best_score = score
                best_idx = i
                best_rotated = False

        if allow_rotation and part_w != part_h and rect.can_fit(part_h, part_w, gap):
            score = _score_fit(rect, part_h, part_w, gap)
            if score < best_score:
                best_score = score
                best_idx = i
                best_rotated = True

    if best_idx < 0:
        return None
    return (best_idx, best_rotated)


def _split_rectangle(
    rect: FreeRect,
    part_w: float,
    part_h: float,
    gap: float,
) -> list[FreeRect]:

    taken_w = part_w + gap
    taken_h = part_h + gap

    right_w = rect.width - taken_w
    top_h = rect.height - taken_h

    new_rects = []

    horiz_right_area = right_w * rect.height if right_w > 0 else 0
    horiz_top_area = taken_w * top_h if top_h > 0 else 0

    vert_right_area = right_w * taken_h if right_w > 0 else 0
    vert_top_area = rect.width * top_h if top_h > 0 else 0

    horiz_max = max(horiz_right_area, horiz_top_area)
    vert_max = max(vert_right_area, vert_top_area)

    if horiz_max >= vert_max:
        if right_w > 0:
            new_rects.append(
                FreeRect(
                    x=rect.x + taken_w,
                    y=rect.y,
                    width=right_w,
                    height=rect.height,
                )
            )
        if top_h > 0:
            new_rects.append(
                FreeRect(
                    x=rect.x,
                    y=rect.y + taken_h,
                    width=taken_w,
                    height=top_h,
                )
            )
    else:
        if right_w > 0:
            new_rects.append(
                FreeRect(
                    x=rect.x + taken_w,
                    y=rect.y,
                    width=right_w,
                    height=taken_h,
                )
            )
        if top_h > 0:
            new_rects.append(
                FreeRect(
                    x=rect.x,
                    y=rect.y + taken_h,
                    width=rect.width,
                    height=top_h,
                )
            )

    return new_rects


def guillotine_pack(
    parts: Sequence[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
    gap: float = 0.0,
    sort_by_area: bool = True,
) -> list[PlacementResult]:
    if bin_width <= 0 or bin_height <= 0:
        return []

    indexed_parts = [(i, w, h, rot, meta) for i, (w, h, rot, meta) in enumerate(parts)]

    if sort_by_area:
        indexed_parts.sort(key=lambda p: p[1] * p[2], reverse=True)

    free_rects = [FreeRect(x=0, y=0, width=bin_width, height=bin_height)]

    placements = []

    for _, part_w, part_h, allow_rotation, metadata in indexed_parts:
        result = _find_best_rect(part_w, part_h, free_rects, gap, allow_rotation)

        if result is None:
            continue

        rect_idx, rotated = result
        rect = free_rects[rect_idx]

        actual_w = part_h if rotated else part_w
        actual_h = part_w if rotated else part_h

        center_x = rect.x + actual_w / 2
        center_y = rect.y + actual_h / 2

        placements.append(
            PlacementResult(
                x=center_x,
                y=center_y,
                rotated=rotated,
                metadata=metadata,
            )
        )

        new_rects = _split_rectangle(rect, actual_w, actual_h, gap)
        free_rects.pop(rect_idx)
        free_rects.extend(new_rects)

    return placements


def _compute_utilization(
    placements: list[PlacementResult],
    parts: Sequence[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
) -> float:
    if bin_width <= 0 or bin_height <= 0:
        return 0.0

    placed_area = 0.0
    for placement in placements:
        for w, h, _, meta in parts:
            if meta == placement.metadata:
                placed_area += w * h
                break

    bin_area = bin_width * bin_height
    return placed_area / bin_area if bin_area > 0 else 0.0


__all__ = [
    "FreeRect",
    "PlacementResult",
    "guillotine_pack",
]
