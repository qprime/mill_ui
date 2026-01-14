"""MaxRects bin packing algorithm for sheet nesting.

MaxRects tracks all maximal free rectangles (which can overlap) and uses
various heuristics to select the best placement. This typically achieves
better utilization than guillotine packing, especially for mixed part sizes.

Algorithm:
1. Start with one free rectangle (the full bin)
2. For each part (sorted by area, largest first):
   a. Find best free rectangle using selected heuristic
   b. Place part in corner of free rectangle
   c. Split ALL free rectangles that intersect the placed part
   d. Remove any free rectangles fully contained in others
3. Return list of placements

Heuristics:
- Best Area Fit (BAF): Minimize leftover area
- Best Short Side Fit (BSSF): Minimize leftover on shorter side
- Best Long Side Fit (BLSF): Minimize leftover on longer side
- Contact Point (CP): Maximize edges touching other parts or bin edges

Reference:
  Jukka Jylänki, "A Thousand Ways to Pack the Bin"
  http://clb.confined.space/files/RectangleBinPack.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MaxRectsHeuristic(Enum):
    """Heuristic for selecting free rectangle."""
    BEST_AREA_FIT = "baf"
    BEST_SHORT_SIDE_FIT = "bssf"
    BEST_LONG_SIDE_FIT = "blsf"
    CONTACT_POINT = "cp"


@dataclass
class FreeRect:
    """A rectangular region of free space."""
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

    def can_fit(self, part_w: float, part_h: float, gap: float = 0.0) -> bool:
        """Check if part (plus gap) fits in this rectangle."""
        needed_w = part_w + gap
        needed_h = part_h + gap
        return self.width >= needed_w and self.height >= needed_h

    def intersects(self, other: "FreeRect") -> bool:
        """Check if this rectangle intersects another."""
        return not (
            self.right <= other.x or
            other.right <= self.x or
            self.top <= other.y or
            other.top <= self.y
        )

    def contains(self, other: "FreeRect") -> bool:
        """Check if this rectangle fully contains another."""
        return (
            self.x <= other.x and
            self.y <= other.y and
            self.right >= other.right and
            self.top >= other.top
        )


@dataclass
class PlacementResult:
    """Result of placing a part."""
    x: float  # Center X
    y: float  # Center Y
    rotated: bool
    metadata: Any


def _score_baf(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    """Best Area Fit: minimize leftover area."""
    needed_w = part_w + gap
    needed_h = part_h + gap
    return rect.area - (needed_w * needed_h)


def _score_bssf(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    """Best Short Side Fit: minimize leftover on shorter side."""
    needed_w = part_w + gap
    needed_h = part_h + gap
    leftover_w = rect.width - needed_w
    leftover_h = rect.height - needed_h
    return min(leftover_w, leftover_h)


def _score_blsf(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    """Best Long Side Fit: minimize leftover on longer side."""
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
    parts_info: dict,  # metadata -> (width, height)
) -> float:
    """Contact Point: maximize edges touching bin edges or other parts.

    Returns negative score (more contact = lower/better score).
    """
    needed_w = part_w + gap
    needed_h = part_h + gap

    # Part bounds if placed in bottom-left of rect
    px1, py1 = rect.x, rect.y
    px2, py2 = rect.x + needed_w, rect.y + needed_h

    contact = 0.0

    # Contact with bin edges
    if px1 <= 0:
        contact += needed_h
    if py1 <= 0:
        contact += needed_w
    if px2 >= bin_width:
        contact += needed_h
    if py2 >= bin_height:
        contact += needed_w

    # Contact with other placed parts
    for p in placements:
        pw, ph = parts_info.get(id(p.metadata), (0, 0))
        if p.rotated:
            pw, ph = ph, pw

        # Placed part bounds
        ox1 = p.x - pw / 2
        oy1 = p.y - ph / 2
        ox2 = p.x + pw / 2
        oy2 = p.y + ph / 2

        # Check for adjacency (within gap tolerance)
        tolerance = gap + 0.1

        # Right edge of placed part touches left edge of new part
        if abs(ox2 - px1) < tolerance:
            overlap = min(oy2, py2) - max(oy1, py1)
            if overlap > 0:
                contact += overlap

        # Left edge of placed part touches right edge of new part
        if abs(ox1 - px2) < tolerance:
            overlap = min(oy2, py2) - max(oy1, py1)
            if overlap > 0:
                contact += overlap

        # Top edge of placed part touches bottom edge of new part
        if abs(oy2 - py1) < tolerance:
            overlap = min(ox2, px2) - max(ox1, px1)
            if overlap > 0:
                contact += overlap

        # Bottom edge of placed part touches top edge of new part
        if abs(oy1 - py2) < tolerance:
            overlap = min(ox2, px2) - max(ox1, px1)
            if overlap > 0:
                contact += overlap

    # Return negative (more contact = better = lower score)
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
    placements: list[PlacementResult] = None,
    parts_info: dict = None,
) -> tuple[int, bool] | None:
    """Find best free rectangle for a part.

    Returns:
        (index, rotated) or None if no fit found
    """
    best_idx = -1
    best_rotated = False
    best_score = float("inf")
    best_secondary = float("inf")

    for i, rect in enumerate(free_rects):
        for rotated in [False, True]:
            if rotated and not allow_rotation:
                continue
            if rotated and part_w == part_h:
                continue  # No point rotating square

            pw = part_h if rotated else part_w
            ph = part_w if rotated else part_h

            if not rect.can_fit(pw, ph, gap):
                continue

            # Calculate score based on heuristic
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
                    rect, pw, ph, gap,
                    bin_width, bin_height,
                    placements or [], parts_info or {}
                )
                secondary = _score_baf(rect, pw, ph, gap)
            else:
                score = _score_bssf(rect, pw, ph, gap)
                secondary = _score_baf(rect, pw, ph, gap)

            # Use secondary score as tiebreaker
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
    """Split a free rectangle around a placed part.

    Creates up to 4 new rectangles from the remaining space.
    """
    # Placed part bounds (including gap)
    px1 = placed_x
    py1 = placed_y
    px2 = placed_x + placed_w + gap
    py2 = placed_y + placed_h + gap

    new_rects = []

    # Left piece
    if px1 > free_rect.x:
        new_rects.append(FreeRect(
            x=free_rect.x,
            y=free_rect.y,
            width=px1 - free_rect.x,
            height=free_rect.height,
        ))

    # Right piece
    if px2 < free_rect.right:
        new_rects.append(FreeRect(
            x=px2,
            y=free_rect.y,
            width=free_rect.right - px2,
            height=free_rect.height,
        ))

    # Bottom piece
    if py1 > free_rect.y:
        new_rects.append(FreeRect(
            x=free_rect.x,
            y=free_rect.y,
            width=free_rect.width,
            height=py1 - free_rect.y,
        ))

    # Top piece
    if py2 < free_rect.top:
        new_rects.append(FreeRect(
            x=free_rect.x,
            y=py2,
            width=free_rect.width,
            height=free_rect.top - py2,
        ))

    return new_rects


def _prune_contained_rects(free_rects: list[FreeRect]) -> list[FreeRect]:
    """Remove rectangles that are fully contained within others."""
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
    """Pack rectangles into a single bin using MaxRects algorithm.

    Args:
        parts: List of (width, height, allow_rotation, metadata) tuples
        bin_width: Available bin width (after margins)
        bin_height: Available bin height (after margins)
        gap: Required gap between parts (kerf)
        sort_by_area: Sort parts by area descending
        heuristic: Selection heuristic (default: Best Area Fit)

    Returns:
        List of PlacementResult for successfully placed parts.
    """
    if bin_width <= 0 or bin_height <= 0:
        return []

    # Create working list with indices
    indexed_parts = [(i, w, h, rot, meta) for i, (w, h, rot, meta) in enumerate(parts)]

    # Sort by area (largest first)
    if sort_by_area:
        indexed_parts.sort(key=lambda p: p[1] * p[2], reverse=True)

    # Build parts_info for contact point heuristic
    parts_info = {}
    for _, w, h, _, meta in indexed_parts:
        parts_info[id(meta)] = (w, h)

    # Initialize with single free rectangle
    free_rects = [FreeRect(x=0, y=0, width=bin_width, height=bin_height)]

    placements = []

    for orig_idx, part_w, part_h, allow_rotation, metadata in indexed_parts:
        # Find best rectangle
        result = _find_best_rect(
            part_w, part_h, free_rects, gap, allow_rotation,
            heuristic, bin_width, bin_height, placements, parts_info
        )

        if result is None:
            continue

        rect_idx, rotated = result
        rect = free_rects[rect_idx]

        # Actual dimensions after rotation
        actual_w = part_h if rotated else part_w
        actual_h = part_w if rotated else part_h

        # Place in bottom-left corner of selected rect
        placed_x = rect.x
        placed_y = rect.y

        # Center position
        center_x = placed_x + actual_w / 2
        center_y = placed_y + actual_h / 2

        placements.append(PlacementResult(
            x=center_x,
            y=center_y,
            rotated=rotated,
            metadata=metadata,
        ))

        # Split ALL free rectangles that intersect the placed part
        placed_rect = FreeRect(
            x=placed_x,
            y=placed_y,
            width=actual_w + gap,
            height=actual_h + gap,
        )

        new_free_rects = []
        for free_rect in free_rects:
            if free_rect.intersects(placed_rect):
                # Split this rectangle
                splits = _split_free_rect(
                    free_rect, placed_x, placed_y, actual_w, actual_h, gap
                )
                new_free_rects.extend(splits)
            else:
                # Keep unchanged
                new_free_rects.append(free_rect)

        # Prune contained rectangles
        free_rects = _prune_contained_rects(new_free_rects)

    return placements


__all__ = [
    "MaxRectsHeuristic",
    "FreeRect",
    "PlacementResult",
    "maxrects_pack",
]
