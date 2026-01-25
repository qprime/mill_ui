
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WasteStrategy(Enum):
    LARGEST = "largest"
    SIMPLE = "simple"


@dataclass(frozen=True)
class WasteRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class PartBounds:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height


def _rects_intersect(
    ax: float, ay: float, aw: float, ah: float,
    bx: float, by: float, bw: float, bh: float,
) -> bool:
    return not (
        ax + aw <= bx or
        bx + bw <= ax or
        ay + ah <= by or
        by + bh <= ay
    )


def _split_rect_around_obstacle(
    rect_x: float, rect_y: float, rect_w: float, rect_h: float,
    obs_x: float, obs_y: float, obs_w: float, obs_h: float,
) -> list[tuple[float, float, float, float]]:
    rect_right = rect_x + rect_w
    rect_top = rect_y + rect_h
    obs_right = obs_x + obs_w
    obs_top = obs_y + obs_h

    new_rects = []

    if obs_x > rect_x:
        new_rects.append((rect_x, rect_y, obs_x - rect_x, rect_h))

    if obs_right < rect_right:
        new_rects.append((obs_right, rect_y, rect_right - obs_right, rect_h))

    if obs_y > rect_y:
        new_rects.append((rect_x, rect_y, rect_w, obs_y - rect_y))

    if obs_top < rect_top:
        new_rects.append((rect_x, obs_top, rect_w, rect_top - obs_top))

    return new_rects


def _rect_contains(
    outer_x: float, outer_y: float, outer_w: float, outer_h: float,
    inner_x: float, inner_y: float, inner_w: float, inner_h: float,
) -> bool:
    return (
        outer_x <= inner_x and
        outer_y <= inner_y and
        outer_x + outer_w >= inner_x + inner_w and
        outer_y + outer_h >= inner_y + inner_h
    )


def _prune_contained(rects: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    result = []
    for i, (x1, y1, w1, h1) in enumerate(rects):
        is_contained = False
        for j, (x2, y2, w2, h2) in enumerate(rects):
            if i != j and _rect_contains(x2, y2, w2, h2, x1, y1, w1, h1):
                is_contained = True
                break
        if not is_contained:
            result.append((x1, y1, w1, h1))
    return result


def _compute_maxrects_waste(
    sheet_width: float,
    sheet_height: float,
    margin: float,
    parts: list[PartBounds],
    min_width: float,
    min_height: float,
) -> list[WasteRect]:
    usable_x = margin
    usable_y = margin
    usable_w = sheet_width - 2 * margin
    usable_h = sheet_height - 2 * margin

    if usable_w <= 0 or usable_h <= 0:
        return []

    free_rects: list[tuple[float, float, float, float]] = [(usable_x, usable_y, usable_w, usable_h)]

    for part in parts:
        new_free_rects = []
        for rx, ry, rw, rh in free_rects:
            if _rects_intersect(rx, ry, rw, rh, part.x, part.y, part.width, part.height):
                splits = _split_rect_around_obstacle(rx, ry, rw, rh, part.x, part.y, part.width, part.height)
                new_free_rects.extend(splits)
            else:
                new_free_rects.append((rx, ry, rw, rh))
        free_rects = _prune_contained(new_free_rects)

    result = []
    for x, y, w, h in free_rects:
        if w >= min_width and h >= min_height:
            result.append(WasteRect(x=x, y=y, width=w, height=h))

    result.sort(key=lambda r: r.area, reverse=True)
    return result


def _compute_guillotine_waste(
    sheet_width: float,
    sheet_height: float,
    margin: float,
    parts: list[PartBounds],
    min_width: float,
    min_height: float,
) -> list[WasteRect]:
    usable_x = margin
    usable_y = margin
    usable_w = sheet_width - 2 * margin
    usable_h = sheet_height - 2 * margin

    if usable_w <= 0 or usable_h <= 0:
        return []

    def has_overlap(rx: float, ry: float, rw: float, rh: float) -> bool:
        for part in parts:
            if _rects_intersect(rx, ry, rw, rh, part.x, part.y, part.width, part.height):
                return True
        return False

    def find_blocking_part(rx: float, ry: float, rw: float, rh: float) -> PartBounds | None:
        for part in parts:
            if _rects_intersect(rx, ry, rw, rh, part.x, part.y, part.width, part.height):
                return part
        return None

    def decompose(rx: float, ry: float, rw: float, rh: float) -> list[WasteRect]:
        if rw < min_width or rh < min_height:
            return []

        blocker = find_blocking_part(rx, ry, rw, rh)
        if blocker is None:
            return [WasteRect(x=rx, y=ry, width=rw, height=rh)]

        results = []

        left_w = max(0, blocker.x - rx)
        if left_w >= min_width:
            results.extend(decompose(rx, ry, left_w, rh))

        right_x = blocker.right
        right_w = max(0, (rx + rw) - right_x)
        if right_w >= min_width:
            results.extend(decompose(right_x, ry, right_w, rh))

        bottom_h = max(0, blocker.y - ry)
        inner_x = max(rx, blocker.x)
        inner_right = min(rx + rw, blocker.right)
        inner_w = inner_right - inner_x
        if bottom_h >= min_height and inner_w >= min_width:
            results.extend(decompose(inner_x, ry, inner_w, bottom_h))

        top_y = blocker.top
        top_h = max(0, (ry + rh) - top_y)
        if top_h >= min_height and inner_w >= min_width:
            results.extend(decompose(inner_x, top_y, inner_w, top_h))

        return results

    result = decompose(usable_x, usable_y, usable_w, usable_h)
    result.sort(key=lambda r: r.area, reverse=True)
    return result


def compute_waste_rectangles(
    sheet_width: float,
    sheet_height: float,
    margin: float,
    parts: list[PartBounds],
    min_width: float,
    min_height: float,
    strategy: WasteStrategy = WasteStrategy.LARGEST,
) -> list[WasteRect]:
    if strategy == WasteStrategy.LARGEST:
        return _compute_maxrects_waste(
            sheet_width, sheet_height, margin, parts, min_width, min_height
        )
    else:
        return _compute_guillotine_waste(
            sheet_width, sheet_height, margin, parts, min_width, min_height
        )


__all__ = [
    "WasteStrategy",
    "WasteRect",
    "PartBounds",
    "compute_waste_rectangles",
]
