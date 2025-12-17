"""Shared-edge seam detection and exterior offset handling."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple, TYPE_CHECKING

from skills.mill_ui.cam.types import Vec2
from skills.mill_ui.cam.shape import Shape2D
from skills.mill_ui.cam.ops.profile import profile_outline

from .profile import ensure_center, rect_shape
from .tools import ToolSelection, stepdown_for_tool

if TYPE_CHECKING:
    from skills.mill_ui.cam.config import Config
    from . import PassRecord


@dataclass(frozen=True)
class _Edge:
    orient: str  # "v" or "h"
    coord: float
    a: float
    b: float
    rect_id: str
    minx: float
    miny: float
    maxx: float
    maxy: float

    @property
    def length(self) -> float:
        return abs(self.b - self.a)


def _rect_edges(cx: float, cy: float, w: float, h: float, rect_id: str) -> List[_Edge]:
    minx, miny = cx - w / 2.0, cy - h / 2.0
    maxx, maxy = cx + w / 2.0, cy + h / 2.0
    return [
        _Edge("v", minx, miny, maxy, rect_id, minx, miny, maxx, maxy),
        _Edge("v", maxx, miny, maxy, rect_id, minx, miny, maxx, maxy),
        _Edge("h", miny, minx, maxx, rect_id, minx, miny, maxx, maxy),
        _Edge("h", maxy, minx, maxx, rect_id, minx, miny, maxx, maxy),
    ]


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    lo = max(min(a1, a2), min(b1, b2))
    hi = min(max(a1, a2), max(b1, b2))
    return max(0.0, hi - lo)


def merge_rect_profiles(
    rect_profiles: Sequence[Mapping[str, Any]],
    *,
    record: "PassRecord",
    tool: ToolSelection,
    config: "Config",
    cut_through_mm: float,
) -> int:
    if not rect_profiles:
        return 0

    merge_tol = max(config.merge_epsilon_mm, 1e-6)
    min_overlap_mm = max(config.min_overlap_mm, 0.0)
    min_overlap_ratio = max(config.min_overlap_ratio, 0.0)

    edges: List[_Edge] = []
    rect_depths: Dict[str, float] = {}
    rect_lookup: Dict[str, Mapping[str, Any]] = {}

    for idx, rec in enumerate(rect_profiles):
        rect_id = str(rec.get("id") or f"rect@{idx}")
        cx, cy = ensure_center(rec)
        geom = rec.get("geometry") or {}
        width = float(geom.get("w_mm", 0.0))
        height = float(geom.get("h_mm", 0.0))
        depth = float(rec.get("depth_mm", 0.0))
        rect_depths[rect_id] = depth
        rect_lookup[rect_id] = rec
        edges.extend(_rect_edges(cx, cy, width, height, rect_id))

    buckets: Dict[Tuple[str, int], List[_Edge]] = {}
    for edge in edges:
        buckets.setdefault((edge.orient, int(round(edge.coord / merge_tol))), []).append(edge)

    setup = record.setup
    seam_count = 0
    used_pairs: set[Tuple[str, str, int]] = set()
    tool_radius = float(tool.diameter) * 0.5
    step_down = stepdown_for_tool(tool)

    for key, bucket_edges in buckets.items():
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
                pair_id = tuple(sorted((a.rect_id, b.rect_id))) + (int(round(a.coord * 1e3)),)
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
                    seam_shape = Shape2D([Vec2(x, y0), Vec2(x, y1)])
                else:
                    y = 0.5 * (a.coord + b.coord)
                    x0 = max(min(a.a, a.b), min(b.a, b.b))
                    x1 = min(max(a.a, a.b), max(b.a, b.b))
                    seam_shape = Shape2D([Vec2(x0, y), Vec2(x1, y)])

                depth = max(rect_depths[a.rect_id], rect_depths[b.rect_id]) + cut_through_mm
                moves = profile_outline(seam_shape, setup, depth=depth, step_down=step_down)
                record.add_moves(moves, increment=1)
                seam_count += 1
                used_pairs.add(pair_id)

    for edge in edges:
        bucket = buckets.get((edge.orient, int(round(edge.coord / merge_tol))), [])
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
            x_off = edge.coord - tool_radius if math.isclose(edge.coord, edge.minx, abs_tol=merge_tol) else edge.coord + tool_radius
            seam_shape = Shape2D([Vec2(x_off, edge.a), Vec2(x_off, edge.b)])
        else:
            y_off = edge.coord - tool_radius if math.isclose(edge.coord, edge.miny, abs_tol=merge_tol) else edge.coord + tool_radius
            seam_shape = Shape2D([Vec2(edge.a, y_off), Vec2(edge.b, y_off)])
        moves = profile_outline(seam_shape, setup, depth=rect_depth, step_down=step_down)
        record.add_moves(moves, increment=1)

    return seam_count


__all__ = ["merge_rect_profiles"]
