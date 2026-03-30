from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cam.ops.profile import profile_outline
from cam.planner.planner_input import FeatureInput
from cam.shape import Shape2D
from cam.types import Vec2

from .tools import ToolSelection, stepdown_for_tool

if TYPE_CHECKING:
    from cam.config import Config

    from . import PassRecord


@dataclass(frozen=True)
class _Edge:
    orient: str
    coord: float
    a: float
    b: float
    rect_id: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def length(self) -> float:
        return abs(self.b - self.a)


def _rect_edges(cx: float, cy: float, w: float, h: float, rect_id: str) -> list[_Edge]:
    x_min, y_min = cx - w / 2.0, cy - h / 2.0
    x_max, y_max = cx + w / 2.0, cy + h / 2.0
    return [
        _Edge("v", x_min, y_min, y_max, rect_id, x_min, y_min, x_max, y_max),
        _Edge("v", x_max, y_min, y_max, rect_id, x_min, y_min, x_max, y_max),
        _Edge("h", y_min, x_min, x_max, rect_id, x_min, y_min, x_max, y_max),
        _Edge("h", y_max, x_min, x_max, rect_id, x_min, y_min, x_max, y_max),
    ]


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    lo = max(min(a1, a2), min(b1, b2))
    hi = min(max(a1, a2), max(b1, b2))
    return max(0.0, hi - lo)


def _find_and_cut_seams(
    buckets: dict[tuple[str, int], list[_Edge]],
    rect_depths: dict[str, float],
    *,
    record: PassRecord,
    tool: ToolSelection,
    merge_tol: float,
    min_overlap_mm: float,
    min_overlap_ratio: float,
    cut_through_mm: float,
) -> int:
    setup = record.setup
    step_down = stepdown_for_tool(tool)
    seam_count = 0
    used_pairs: set[tuple[str, str, int]] = set()

    for _, bucket_edges in buckets.items():
        if len(bucket_edges) < 2:
            continue
        n = len(bucket_edges)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = bucket_edges[i], bucket_edges[j]
                if a.rect_id == b.rect_id:
                    continue
                if a.orient != b.orient:
                    continue
                if abs(a.coord - b.coord) > merge_tol:
                    continue
                sorted_ids = sorted((a.rect_id, b.rect_id))
                pair_id: tuple[str, str, int] = (sorted_ids[0], sorted_ids[1], round(a.coord * 1e3))
                if pair_id in used_pairs:
                    continue
                overlap = _overlap_len(a.a, a.b, b.a, b.b)
                min_length = min(a.length, b.length)
                required = max(min_overlap_mm, min_length * min_overlap_ratio, float(tool.diameter))
                if overlap < required:
                    continue

                if a.orient == "v":
                    x = 0.5 * (a.coord + b.coord)
                    y0 = max(min(a.a, a.b), min(b.a, b.b))
                    y1 = min(max(a.a, a.b), max(b.a, b.b))
                    seam_shape = Shape2D((Vec2(x, y0), Vec2(x, y1)))
                else:
                    y = 0.5 * (a.coord + b.coord)
                    x0 = max(min(a.a, a.b), min(b.a, b.b))
                    x1 = min(max(a.a, a.b), max(b.a, b.b))
                    seam_shape = Shape2D((Vec2(x0, y), Vec2(x1, y)))

                depth = max(rect_depths[a.rect_id], rect_depths[b.rect_id]) + cut_through_mm
                moves = profile_outline(seam_shape, setup, depth_mm=depth, step_down=step_down)
                record.add_moves(moves, increment=1)
                seam_count += 1
                used_pairs.add(pair_id)

    return seam_count


def _cut_unpaired_edges(
    edges: list[_Edge],
    buckets: dict[tuple[str, int], list[_Edge]],
    rect_depths: dict[str, float],
    *,
    record: PassRecord,
    tool: ToolSelection,
    merge_tol: float,
    min_overlap_mm: float,
    min_overlap_ratio: float,
    cut_through_mm: float,
) -> None:
    setup = record.setup
    tool_radius = float(tool.diameter) * 0.5
    step_down = stepdown_for_tool(tool)

    for edge in edges:
        bucket = buckets.get((edge.orient, round(edge.coord / merge_tol)), [])
        has_partner = False
        for other in bucket:
            if other.rect_id == edge.rect_id:
                continue
            if abs(other.coord - edge.coord) > merge_tol:
                continue
            overlap = _overlap_len(edge.a, edge.b, other.a, other.b)
            min_length = min(edge.length, other.length)
            required = max(min_overlap_mm, min_length * min_overlap_ratio)
            if overlap >= required:
                has_partner = True
                break
        if has_partner:
            continue

        rect_depth = rect_depths[edge.rect_id] + cut_through_mm
        if edge.orient == "v":
            x_off = (
                edge.coord - tool_radius
                if math.isclose(edge.coord, edge.x_min, abs_tol=merge_tol)
                else edge.coord + tool_radius
            )
            seam_shape = Shape2D((Vec2(x_off, edge.a), Vec2(x_off, edge.b)))
        else:
            y_off = (
                edge.coord - tool_radius
                if math.isclose(edge.coord, edge.y_min, abs_tol=merge_tol)
                else edge.coord + tool_radius
            )
            seam_shape = Shape2D((Vec2(edge.a, y_off), Vec2(edge.b, y_off)))
        moves = profile_outline(seam_shape, setup, depth_mm=rect_depth, step_down=step_down)
        record.add_moves(moves, increment=1)


def merge_rect_profiles(
    rect_profiles: Sequence[FeatureInput],
    *,
    record: PassRecord,
    tool: ToolSelection,
    config: Config,
    cut_through_mm: float,
) -> int:
    if not rect_profiles:
        return 0

    merge_tol = max(config.merge_epsilon_mm, 1e-6)
    min_overlap_mm = max(config.min_overlap_mm, 0.0)
    min_overlap_ratio = max(config.min_overlap_ratio, 0.0)

    edges: list[_Edge] = []
    rect_depths: dict[str, float] = {}

    for idx, rec in enumerate(rect_profiles):
        rect_id = rec.id or f"rect@{idx}"
        cx, cy = rec.center_xy_mm
        width = float(rec.geometry.geometry.w_mm or 0.0)
        height = float(rec.geometry.geometry.h_mm or 0.0)
        depth = rec.depth_mm
        rect_depths[rect_id] = depth
        edges.extend(_rect_edges(cx, cy, width, height, rect_id))

    buckets: dict[tuple[str, int], list[_Edge]] = {}
    for edge in edges:
        buckets.setdefault((edge.orient, round(edge.coord / merge_tol)), []).append(edge)

    seam_count = _find_and_cut_seams(
        buckets,
        rect_depths,
        record=record,
        tool=tool,
        merge_tol=merge_tol,
        min_overlap_mm=min_overlap_mm,
        min_overlap_ratio=min_overlap_ratio,
        cut_through_mm=cut_through_mm,
    )

    _cut_unpaired_edges(
        edges,
        buckets,
        rect_depths,
        record=record,
        tool=tool,
        merge_tol=merge_tol,
        min_overlap_mm=min_overlap_mm,
        min_overlap_ratio=min_overlap_ratio,
        cut_through_mm=cut_through_mm,
    )

    return seam_count


__all__ = ["merge_rect_profiles"]
