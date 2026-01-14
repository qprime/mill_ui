"""Guillotine bin packing algorithm for sheet nesting.

The guillotine algorithm divides free space into rectangular regions using
full-width or full-height cuts. This matches CNC workflow where operators
often make spanning cuts to break down sheets.

Algorithm:
1. Start with one free rectangle (the usable sheet area)
2. For each part (sorted by area, largest first):
   a. Find best-fitting free rectangle
   b. Place part in corner of free rectangle
   c. Split remaining space using guillotine cut (horizontal or vertical)
3. Return list of placements

Heuristic:
- Best Short Side Fit (BSSF): Choose rectangle that minimizes leftover
  on the shorter side after placing the part.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FreeRect:
    """A rectangular region of free space.

    Coordinates are bottom-left corner relative to sheet origin.
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        """Area of this free rectangle."""
        return self.width * self.height

    def can_fit(self, part_w: float, part_h: float, gap: float = 0.0) -> bool:
        """Check if part (plus gap) fits in this rectangle."""
        # Include gap on right and top edges
        needed_w = part_w + gap
        needed_h = part_h + gap
        return self.width >= needed_w and self.height >= needed_h

    def can_fit_rotated(self, part_w: float, part_h: float, gap: float = 0.0) -> bool:
        """Check if part fits when rotated 90 degrees."""
        return self.can_fit(part_h, part_w, gap)


@dataclass
class PlacementResult:
    """Result of placing a part."""

    x: float  # Center X
    y: float  # Center Y
    rotated: bool
    metadata: Any  # Passed through from input


def _score_fit(rect: FreeRect, part_w: float, part_h: float, gap: float) -> float:
    """Score how well a part fits in a rectangle (lower is better).

    Uses Best Short Side Fit (BSSF) heuristic.
    """
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
    """Find best free rectangle for a part.

    Args:
        part_w: Part width
        part_h: Part height
        free_rects: List of available free rectangles
        gap: Required gap between parts
        allow_rotation: Whether 90-degree rotation is allowed

    Returns:
        (index, rotated) or None if no fit found
    """
    best_idx = -1
    best_rotated = False
    best_score = float("inf")

    for i, rect in enumerate(free_rects):
        # Try normal orientation
        if rect.can_fit(part_w, part_h, gap):
            score = _score_fit(rect, part_w, part_h, gap)
            if score < best_score:
                best_score = score
                best_idx = i
                best_rotated = False

        # Try rotated orientation
        if allow_rotation and part_w != part_h:
            if rect.can_fit(part_h, part_w, gap):
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
    """Split free rectangle after placing a part using guillotine cut.

    Places part in bottom-left corner. Splits remaining space into
    two new rectangles using the split that maximizes the larger piece.

    Args:
        rect: The free rectangle being split
        part_w: Placed part width (after rotation if any)
        part_h: Placed part height (after rotation if any)
        gap: Required gap between parts

    Returns:
        List of 0-2 new free rectangles
    """
    # Space taken by part (including gap)
    taken_w = part_w + gap
    taken_h = part_h + gap

    # Remaining dimensions
    right_w = rect.width - taken_w
    top_h = rect.height - taken_h

    new_rects = []

    # Two possible split orientations:
    # 1. Horizontal split: right rect gets full remaining height
    # 2. Vertical split: top rect gets full remaining width

    # Calculate areas for each split to choose better one
    # Horizontal split creates:
    #   - Right: (right_w) x (rect.height)
    #   - Top: (taken_w) x (top_h)
    horiz_right_area = right_w * rect.height if right_w > 0 else 0
    horiz_top_area = taken_w * top_h if top_h > 0 else 0

    # Vertical split creates:
    #   - Right: (right_w) x (taken_h)
    #   - Top: (rect.width) x (top_h)
    vert_right_area = right_w * taken_h if right_w > 0 else 0
    vert_top_area = rect.width * top_h if top_h > 0 else 0

    # Choose split that maximizes larger remaining piece
    horiz_max = max(horiz_right_area, horiz_top_area)
    vert_max = max(vert_right_area, vert_top_area)

    if horiz_max >= vert_max:
        # Horizontal split
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
        # Vertical split
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
    parts: list[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
    gap: float = 0.0,
    sort_by_area: bool = True,
) -> list[PlacementResult]:
    """Pack rectangles into a single bin using guillotine algorithm.

    Args:
        parts: List of (width, height, allow_rotation, metadata) tuples
        bin_width: Available bin width (after margins)
        bin_height: Available bin height (after margins)
        gap: Required gap between parts (kerf)
        sort_by_area: Sort parts by area descending (usually better packing)

    Returns:
        List of PlacementResult for successfully placed parts.
        Parts that don't fit are omitted.
    """
    if bin_width <= 0 or bin_height <= 0:
        return []

    # Create working list with indices for tracking
    indexed_parts = [(i, w, h, rot, meta) for i, (w, h, rot, meta) in enumerate(parts)]

    # Sort by area (largest first) for better packing
    if sort_by_area:
        indexed_parts.sort(key=lambda p: p[1] * p[2], reverse=True)

    # Initialize with single free rectangle (full bin)
    free_rects = [FreeRect(x=0, y=0, width=bin_width, height=bin_height)]

    placements = []

    for orig_idx, part_w, part_h, allow_rotation, metadata in indexed_parts:
        # Find best rectangle for this part
        result = _find_best_rect(part_w, part_h, free_rects, gap, allow_rotation)

        if result is None:
            # Part doesn't fit anywhere
            continue

        rect_idx, rotated = result
        rect = free_rects[rect_idx]

        # Determine actual dimensions after rotation
        actual_w = part_h if rotated else part_w
        actual_h = part_w if rotated else part_h

        # Calculate center position (part placed in bottom-left of rect)
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

        # Remove used rectangle and add new ones from split
        new_rects = _split_rectangle(rect, actual_w, actual_h, gap)
        free_rects.pop(rect_idx)
        free_rects.extend(new_rects)

    return placements


def _compute_utilization(
    placements: list[PlacementResult],
    parts: list[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
) -> float:
    """Compute material utilization for a packing result.

    Internal helper for testing. Production code should use SheetLayout.utilization
    which computes from actual NestedPart dimensions.

    Note: This matches parts by metadata equality, so metadata must be unique
    per part for correct results.

    Args:
        placements: Results from guillotine_pack
        parts: Original parts list (to get dimensions)
        bin_width: Bin width
        bin_height: Bin height

    Returns:
        Utilization ratio (0.0 to 1.0)
    """
    if bin_width <= 0 or bin_height <= 0:
        return 0.0

    placed_area = 0.0
    for placement in placements:
        # Find matching part by metadata
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
