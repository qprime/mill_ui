from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, pairwise
from math import hypot
from typing import TYPE_CHECKING

from shapely import get_parts
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import orient, unary_union

from cam.ops.profile import profile_outline
from cam.planner.planner_input import FeatureInput
from cam.shape import Shape2D
from cam.types import Vec2

from .profile import offset_polygon_shape, offset_rect_shape, offset_rounded_rect_shape, polygon_shape
from .tools import ToolSelection, stepdown_for_tool

if TYPE_CHECKING:
    from cam.config import Config

    from . import PassRecord

_CENTERLINE_PRECISION_MM = 1e-9


@dataclass(frozen=True)
class SharedProfileGroup:
    profile_indices: tuple[int, ...]
    depth_mm: float
    seams: tuple[Shape2D, ...]
    outlines: tuple[Shape2D, ...]
    unshared_contours: tuple[Shape2D, ...] = ()
    seam_contributors: tuple[tuple[int, ...], ...] = ()
    seam_feature_ids: tuple[tuple[str, ...], ...] = ()


class ProfileClearanceError(ValueError):
    def __init__(self, message: str, extra_gap_mm: float):
        super().__init__(message)
        self.extra_gap_mm = extra_gap_mm


def profile_material_region(profile: FeatureInput) -> Polygon:
    cx, cy = profile.center_xy_mm
    geometry = profile.geometry.geometry
    if profile.shape.lower() == "polygon":
        region = Polygon([(cx + x, cy + y) for x, y in geometry.points or ()])
    elif profile.shape.lower() == "circle":
        from shapely.geometry import Point

        region = Point(cx, cy).buffer(float(geometry.diameter_mm or 0) / 2, quad_segs=128)
    elif profile.shape.lower() == "roundedrect":
        fallback = geometry.radius_mm or 0.0
        radii = {
            "tl": geometry.radius_tl_mm,
            "tr": geometry.radius_tr_mm,
            "br": geometry.radius_br_mm,
            "bl": geometry.radius_bl_mm,
        }
        shape = offset_rounded_rect_shape(
            float(geometry.w_mm or 0),
            float(geometry.h_mm or 0),
            {key: fallback if value is None else value for key, value in radii.items()},
            profile.center_xy_mm,
            0,
        )
        if shape is None:
            raise ValueError(f"Profile '{profile.id}' has no retained rounded rectangle")
        region = Polygon([(point.x, point.y) for point in shape.points])
    else:
        half_w = float(geometry.w_mm or 0.0) / 2
        half_h = float(geometry.h_mm or 0.0) / 2
        region = box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)
    if region.is_empty or not region.is_valid or region.area <= 0:
        raise ValueError(f"Profile '{profile.id}' has no valid retained polygon")
    return region


def validate_profile_clearance(
    profiles: Sequence[FeatureInput], tool_diameter_mm: float, *, holding: bool = False
) -> None:
    outside = [profile for profile in profiles if profile.side == "outside" and profile.depth_mm > 0]
    regions: list[Polygon] = []
    for profile in outside:
        region = profile_material_region(profile)
        treatment = profile.edge_treatment
        if treatment is not None and treatment.type == "allowance":
            allowance = max(0.0, treatment.rough_allowance_mm or 0.0, treatment.finish_allowance_mm or 0.0)
            region = region.buffer(allowance, join_style="mitre")
        regions.append(region)
    for a, b in combinations(range(len(outside)), 2):
        held = holding or any(p.tabs is not None or (p.onion_skin_mm or 0) > 0 for p in (outside[a], outside[b]))
        required = tool_diameter_mm * (2 if held else 1)
        gap = regions[a].distance(regions[b])
        if gap < required - _CENTERLINE_PRECISION_MM:
            reason = " to preserve protected holding stock" if held else " to preserve nominal dimensions"
            raise ProfileClearanceError(
                f"Outside profiles '{outside[a].id}' and '{outside[b].id}' have {gap:.6f}mm clearance "
                f"after profile allowances; need {required:.6f}mm for the selected cutter{reason}",
                required - gap,
            )


def _merge_eligible(profile: FeatureInput) -> bool:
    return (
        profile.shape.lower() in {"rect", "polygon"}
        and profile.side == "outside"
        and profile.depth_mm > 0
        and profile.start_depth_mm == 0
        and profile.tabs is None
        and profile.onion_skin_mm is None
        and profile.edge_treatment is None
        and profile.feeds_override is None
        and profile.ramp_mm is None
    )


def _centerline_region(profile: FeatureInput, tool_diameter_mm: float) -> Polygon:
    geometry = profile.geometry.geometry
    shape = (
        offset_polygon_shape(list(geometry.points or ()), profile.center_xy_mm, tool_diameter_mm / 2)
        if profile.shape.lower() == "polygon"
        else offset_rect_shape(
            float(geometry.w_mm or 0), float(geometry.h_mm or 0), profile.center_xy_mm, tool_diameter_mm / 2
        )
    )
    if shape is None:
        raise ValueError(f"Cannot construct outside profile '{profile.id}'")
    region = Polygon([(p.x, p.y) for p in shape.points])
    if not isinstance(region, Polygon) or region.is_empty:
        raise ValueError(f"Outside profile '{profile.id}' has no polygonal region")
    return orient(region, sign=1.0)


def _segments(region: Polygon) -> list[LineString]:
    points = list(region.exterior.coords)
    return [LineString((a, b)) for a, b in pairwise(points) if a != b]


def _opposite(a: LineString, b: LineString) -> bool:
    ax, ay = a.coords[0]
    bx, by = a.coords[-1]
    cx, cy = b.coords[0]
    dx, dy = b.coords[-1]
    return (bx - ax) * (dx - cx) + (by - ay) * (dy - cy) < 0


def _coincident_overlap(first: LineString, second: LineString) -> LineString | None:
    ax, ay = first.coords[0]
    bx, by = first.coords[-1]
    ux, uy = (bx - ax) / first.length, (by - ay) / first.length
    projections: list[float] = []
    for x, y in second.coords:
        if abs((x - ax) * uy - (y - ay) * ux) > _CENTERLINE_PRECISION_MM:
            return None
        projections.append((x - ax) * ux + (y - ay) * uy)
    start = max(0.0, min(projections))
    end = min(first.length, max(projections))
    if end <= start:
        return None
    return LineString([(ax + ux * start, ay + uy * start), (ax + ux * end, ay + uy * end)])


def _shared_seams(
    profiles: Sequence[FeatureInput], regions: dict[int, Polygon], tool_diameter_mm: float, config: Config
) -> list[tuple[int, int, Shape2D]]:
    seams: list[tuple[int, int, Shape2D]] = []
    segments = {index: _segments(region) for index, region in regions.items()}
    for a, b in combinations(regions, 2):
        if profiles[a].depth_mm != profiles[b].depth_mm:
            continue
        if regions[a].distance(regions[b]) > _CENTERLINE_PRECISION_MM:
            continue
        for first in segments[a]:
            for second in segments[b]:
                if not _opposite(first, second):
                    continue
                shared = _coincident_overlap(first, second)
                required = max(
                    config.min_overlap_mm, min(first.length, second.length) * config.min_overlap_ratio, tool_diameter_mm
                )
                if isinstance(shared, LineString) and shared.length >= required:
                    shape = Shape2D(tuple(Vec2(float(x), float(y)) for x, y in shared.coords))
                    seams.append((a, b, shape))
    return seams


def _atomic_seams(seams: Sequence[Shape2D]) -> tuple[Shape2D, ...]:
    noded = unary_union([LineString([(p.x, p.y) for p in seam.points]) for seam in seams])
    return tuple(
        Shape2D(tuple(Vec2(float(x), float(y)) for x, y in line.coords))
        for line in get_parts(noded)
        if isinstance(line, LineString) and line.length > _CENTERLINE_PRECISION_MM
    )


def _align_region(region: Polygon, seams: Sequence[Shape2D]) -> Polygon:
    endpoints = [Point(point.x, point.y) for seam in seams for point in seam.points]
    aligned: list[tuple[float, float]] = []
    for edge in _segments(region):
        candidates = [
            (edge.project(point), (point.x, point.y))
            for point in endpoints
            if edge.distance(point) <= _CENTERLINE_PRECISION_MM
        ]
        start = (float(edge.coords[0][0]), float(edge.coords[0][1]))
        end = (float(edge.coords[-1][0]), float(edge.coords[-1][1]))
        if not any(distance <= _CENTERLINE_PRECISION_MM for distance, _ in candidates):
            candidates.append((0.0, start))
        if not any(edge.length - distance <= _CENTERLINE_PRECISION_MM for distance, _ in candidates):
            candidates.append((edge.length, end))
        for _, point in sorted(candidates):
            if not aligned or hypot(point[0] - aligned[-1][0], point[1] - aligned[-1][1]) > _CENTERLINE_PRECISION_MM:
                aligned.append(point)
    if (
        len(aligned) > 1
        and hypot(aligned[0][0] - aligned[-1][0], aligned[0][1] - aligned[-1][1]) <= _CENTERLINE_PRECISION_MM
    ):
        aligned[-1] = aligned[0]
    polygon = Polygon(aligned)
    if not polygon.is_valid:
        raise ValueError("Coincident profile precision alignment produced an invalid contour")
    return polygon


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


def _unshared_contours(regions: Sequence[Polygon], boundary: Polygon, seams: Sequence[Shape2D]) -> tuple[Shape2D, ...]:
    planned = unary_union([boundary.boundary, *(LineString([(p.x, p.y) for p in seam.points]) for seam in seams)])
    contours: list[Shape2D] = []
    for region in regions:
        for part in get_parts(region.boundary.difference(planned)):
            if isinstance(part, LineString) and part.length > _CENTERLINE_PRECISION_MM:
                contours.append(Shape2D(tuple(Vec2(float(x), float(y)) for x, y in part.coords)))
    return tuple(contours)


def merge_profiles(
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
        group_seams = _atomic_seams([shape for a, b, shape in seams if a in indices and b in indices])
        aligned = [_align_region(regions[index], group_seams) for index in indices]
        region = unary_union(aligned)
        if not isinstance(region, Polygon):
            raise ValueError(f"Shared profiles {indices} do not form one connected centerline region")
        region = orient(region, sign=1.0)
        outlines = tuple(polygon_shape(list(ring.coords), (0.0, 0.0)) for ring in (region.exterior, *region.interiors))
        unshared = _unshared_contours(aligned, region, group_seams)
        for shape in (*group_seams, *outlines, *unshared):
            path = LineString([(p.x, p.y) for p in shape.points])
            if any(
                path.distance(profile_material_region(profiles[index])) < tool_diameter_mm / 2 - 1e-7
                for index in indices
            ):
                raise ValueError(f"Shared profiles {indices}: compensated cutter sweep enters retained material")
        contributors = tuple(
            tuple(
                sorted(
                    {
                        index
                        for a, b, original in seams
                        if LineString([(p.x, p.y) for p in original.points])
                        .buffer(_CENTERLINE_PRECISION_MM)
                        .covers(LineString([(p.x, p.y) for p in seam.points]))
                        for index in (a, b)
                    }
                )
            )
            for seam in group_seams
        )
        groups.append(
            SharedProfileGroup(
                indices,
                profiles[indices[0]].depth_mm,
                group_seams,
                outlines,
                unshared,
                contributors,
                tuple(tuple(profiles[index].id for index in seam_indices) for seam_indices in contributors),
            )
        )
    return tuple(groups)


def plan_shared_profiles(
    groups: Sequence[SharedProfileGroup],
    *,
    record: PassRecord,
    tool: ToolSelection,
    cut_through_mm: float,
    feature_ids: tuple[str, ...],
) -> int:
    for group in groups:
        group_ids = feature_ids
        seam_ids = group.seam_feature_ids or tuple(group_ids for _ in group.seams)
        shapes = [
            *zip(group.seams, seam_ids, strict=True),
            *((shape, group_ids) for shape in (*group.unshared_contours, *group.outlines)),
        ]
        for shape, contributors in shapes:
            record.add_moves(
                profile_outline(
                    shape,
                    record.setup,
                    group.depth_mm + cut_through_mm,
                    step_down=stepdown_for_tool(tool),
                    reverse_open_passes=True,
                ),
                feature_ids=contributors,
                increment=1,
            )
    return sum(len(group.seams) for group in groups)


__all__ = [
    "SharedProfileGroup",
    "merge_profiles",
    "plan_shared_profiles",
    "profile_material_region",
    "validate_profile_clearance",
]
