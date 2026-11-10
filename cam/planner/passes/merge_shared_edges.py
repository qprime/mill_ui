from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

from shapely import set_precision
from shapely.geometry import Polygon, box
from shapely.ops import orient, unary_union

from cam.ops.profile import profile_outline
from cam.planner.planner_input import FeatureInput
from cam.shape import Shape2D
from cam.types import Vec2

from .profile import offset_rect_shape, polygon_shape
from .tools import ToolSelection, stepdown_for_tool

if TYPE_CHECKING:
    from cam.config import Config

    from . import PassRecord

_CENTERLINE_PRECISION_MM = 1e-9


@dataclass(frozen=True)
class _Edge:
    orient: str
    coord: float
    a: float
    b: float
    profile_index: int
    outward: int

    @property
    def length(self) -> float:
        return abs(self.b - self.a)


@dataclass(frozen=True)
class SharedProfileGroup:
    profile_indices: tuple[int, ...]
    depth_mm: float
    seams: tuple[Shape2D, ...]
    outlines: tuple[Shape2D, ...]


def _rect_edges(cx: float, cy: float, w: float, h: float, profile_index: int) -> list[_Edge]:
    x_min, y_min = cx - w / 2.0, cy - h / 2.0
    x_max, y_max = cx + w / 2.0, cy + h / 2.0
    return [
        _Edge("v", x_min, y_min, y_max, profile_index, -1),
        _Edge("v", x_max, y_min, y_max, profile_index, 1),
        _Edge("h", y_min, x_min, x_max, profile_index, -1),
        _Edge("h", y_max, x_min, x_max, profile_index, 1),
    ]


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    lo = max(min(a1, a2), min(b1, b2))
    hi = min(max(a1, a2), max(b1, b2))
    return max(0.0, hi - lo)


def _material_region(profile: FeatureInput) -> Polygon:
    cx, cy = profile.center_xy_mm
    half_w = float(profile.geometry.geometry.w_mm or 0.0) / 2
    half_h = float(profile.geometry.geometry.h_mm or 0.0) / 2
    return box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def validate_rect_profile_clearance(profiles: Sequence[FeatureInput], tool_diameter_mm: float) -> None:
    outside = [profile for profile in profiles if profile.side == "outside" and profile.depth_mm > 0]
    regions: list[Polygon] = []
    for profile in outside:
        region = _material_region(profile)
        treatment = profile.edge_treatment
        if treatment is not None and treatment.type == "allowance":
            allowance = max(0.0, treatment.rough_allowance_mm or 0.0, treatment.finish_allowance_mm or 0.0)
            region = region.buffer(allowance, join_style="mitre")
        regions.append(region)
    for a, b in combinations(range(len(outside)), 2):
        gap = regions[a].distance(regions[b])
        if gap < tool_diameter_mm - _CENTERLINE_PRECISION_MM:
            raise ValueError(
                f"Rectangle profiles '{outside[a].id}' and '{outside[b].id}' have {gap:.6f}mm clearance "
                "after profile allowances; "
                f"need {tool_diameter_mm:.6f}mm for the selected cutter to preserve nominal dimensions"
            )


def _merge_eligible(profile: FeatureInput) -> bool:
    return (
        profile.side == "outside"
        and profile.depth_mm > 0
        and profile.start_depth_mm == 0
        and profile.tabs is None
        and profile.onion_skin_mm is None
        and profile.edge_treatment is None
        and profile.feeds_override is None
        and profile.ramp_mm is None
    )


def _centerline_region(profile: FeatureInput, tool_diameter_mm: float) -> Polygon:
    shape = offset_rect_shape(
        float(profile.geometry.geometry.w_mm or 0.0),
        float(profile.geometry.geometry.h_mm or 0.0),
        profile.center_xy_mm,
        tool_diameter_mm / 2,
    )
    if shape is None:
        raise ValueError(f"Cannot construct outside profile for rectangle '{profile.id}'")
    region = set_precision(Polygon([(p.x, p.y) for p in shape.points]), _CENTERLINE_PRECISION_MM)
    if not isinstance(region, Polygon) or region.is_empty:
        raise ValueError(f"Outside profile for rectangle '{profile.id}' has no polygonal region")
    return region


def _shared_seams(
    profiles: Sequence[FeatureInput], regions: dict[int, Polygon], tool_diameter_mm: float, config: Config
) -> list[tuple[int, int, Shape2D]]:
    buckets: dict[tuple[str, int], list[_Edge]] = {}
    for index, region in regions.items():
        x0, y0, x1, y1 = region.bounds
        for edge in _rect_edges((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, index):
            buckets.setdefault((edge.orient, round(edge.coord / _CENTERLINE_PRECISION_MM)), []).append(edge)
    seams: list[tuple[int, int, Shape2D]] = []
    for edges in buckets.values():
        for a, b in combinations(edges, 2):
            if a.profile_index == b.profile_index or a.outward == b.outward:
                continue
            if profiles[a.profile_index].depth_mm != profiles[b.profile_index].depth_mm:
                continue
            overlap = _overlap_len(a.a, a.b, b.a, b.b)
            required = max(config.min_overlap_mm, min(a.length, b.length) * config.min_overlap_ratio, tool_diameter_mm)
            if overlap < required:
                continue
            start, end = max(a.a, b.a), min(a.b, b.b)
            coord = a.coord
            points = (
                (Vec2(coord, start), Vec2(coord, end)) if a.orient == "v" else (Vec2(start, coord), Vec2(end, coord))
            )
            seams.append((a.profile_index, b.profile_index, Shape2D(points)))
    return seams


def _connected_profiles(seams: Sequence[tuple[int, int, Shape2D]]) -> list[tuple[int, ...]]:
    adjacent: dict[int, set[int]] = {}
    for a, b, _ in seams:
        adjacent.setdefault(a, set()).add(b)
        adjacent.setdefault(b, set()).add(a)
    remaining = set(adjacent)
    groups: list[tuple[int, ...]] = []
    while remaining:
        pending = [min(remaining)]
        component: set[int] = set()
        while pending:
            index = pending.pop()
            if index in component:
                continue
            component.add(index)
            pending.extend(sorted(adjacent[index] - component))
        remaining -= component
        groups.append(tuple(sorted(component)))
    return groups


def merge_rect_profiles(
    profiles: Sequence[FeatureInput], *, tool_diameter_mm: float, config: Config
) -> tuple[SharedProfileGroup, ...]:
    if config.merge_epsilon_mm <= 0:
        return ()
    regions = {
        index: _centerline_region(profile, tool_diameter_mm)
        for index, profile in enumerate(profiles)
        if _merge_eligible(profile)
    }
    seams = _shared_seams(profiles, regions, tool_diameter_mm, config)
    groups: list[SharedProfileGroup] = []
    for indices in _connected_profiles(seams):
        region = unary_union([regions[index] for index in indices])
        if not isinstance(region, Polygon):
            raise ValueError(f"Shared rectangle profiles {indices} do not form one connected centerline region")
        region = orient(region, sign=1.0)
        outlines = tuple(polygon_shape(list(ring.coords), (0.0, 0.0)) for ring in (region.exterior, *region.interiors))
        group_seams = tuple(shape for a, b, shape in seams if a in indices and b in indices)
        groups.append(SharedProfileGroup(indices, profiles[indices[0]].depth_mm, group_seams, outlines))
    return tuple(groups)


def plan_shared_rect_profiles(
    groups: Sequence[SharedProfileGroup], *, record: PassRecord, tool: ToolSelection, cut_through_mm: float
) -> int:
    for group in groups:
        for shape in (*group.seams, *group.outlines):
            record.add_moves(
                profile_outline(
                    shape, record.setup, group.depth_mm + cut_through_mm, step_down=stepdown_for_tool(tool)
                ),
                increment=1,
            )
    return sum(len(group.seams) for group in groups)


__all__ = ["SharedProfileGroup", "merge_rect_profiles", "plan_shared_rect_profiles", "validate_rect_profile_clearance"]
