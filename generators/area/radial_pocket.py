from __future__ import annotations

import math
from typing import TYPE_CHECKING

from shapely.geometry import Polygon as ShapelyPolygon

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import RadialPocketParams
from generators.radial_utils import generate_angular_positions, radial_point
from generators.utils import iter_polygons, shapely_to_item
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def _center_island_polygon(
    center: tuple[float, float],
    shape: str,
    size_mm: float,
) -> ShapelyPolygon:
    half = size_mm / 2
    cx, cy = center

    if shape == "circle":
        n = 64
        return ShapelyPolygon(
            [(cx + half * math.cos(2 * math.pi * i / n), cy + half * math.sin(2 * math.pi * i / n)) for i in range(n)]
        )
    elif shape == "square":
        return ShapelyPolygon(
            [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)]
        )
    elif shape == "diamond":
        return ShapelyPolygon([(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)])
    elif shape == "hexagon":
        return ShapelyPolygon(
            [(cx + half * math.cos(math.pi / 3 * i), cy + half * math.sin(math.pi / 3 * i)) for i in range(6)]
        )
    else:
        raise ValueError(f"Unknown center_shape: {shape}")


def _build_wedge_triangle(
    center: tuple[float, float],
    radius: float,
    angle1_deg: float,
    angle2_deg: float,
    bar_width_mm: float,
) -> ShapelyPolygon:
    mid_angle = (angle1_deg + angle2_deg) / 2
    half_span_rad = math.radians((angle2_deg - angle1_deg) / 2)

    if bar_width_mm > 0 and half_span_rad > 0:
        bar_offset_rad = math.atan2(bar_width_mm / 2, radius) if radius > 0 else 0
    else:
        bar_offset_rad = 0

    inner_angle1 = angle1_deg + math.degrees(bar_offset_rad)
    inner_angle2 = angle2_deg - math.degrees(bar_offset_rad)

    if inner_angle1 >= inner_angle2:
        return ShapelyPolygon()

    if bar_width_mm > 0:
        center_offset = bar_width_mm / (2 * math.sin(half_span_rad)) if half_span_rad > 0 else bar_width_mm
    else:
        center_offset = 0

    apex = radial_point(center, center_offset, mid_angle)
    tip1 = radial_point(center, radius, inner_angle1)
    tip2 = radial_point(center, radius, inner_angle2)

    return ShapelyPolygon([apex, tip1, tip2])


def _build_wedge_arc(
    center: tuple[float, float],
    radius: float,
    angle1_deg: float,
    angle2_deg: float,
    bar_width_mm: float,
    arc_segments: int = 32,
) -> ShapelyPolygon:
    mid_angle = (angle1_deg + angle2_deg) / 2
    half_span_rad = math.radians((angle2_deg - angle1_deg) / 2)

    if bar_width_mm > 0 and half_span_rad > 0:
        bar_offset_rad = math.atan2(bar_width_mm / 2, radius) if radius > 0 else 0
    else:
        bar_offset_rad = 0

    inner_angle1 = angle1_deg + math.degrees(bar_offset_rad)
    inner_angle2 = angle2_deg - math.degrees(bar_offset_rad)

    if inner_angle1 >= inner_angle2:
        return ShapelyPolygon()

    if bar_width_mm > 0:
        center_offset = bar_width_mm / (2 * math.sin(half_span_rad)) if half_span_rad > 0 else bar_width_mm
    else:
        center_offset = 0

    arc_points = []
    span = inner_angle2 - inner_angle1
    for i in range(arc_segments + 1):
        a = inner_angle1 + span * i / arc_segments
        arc_points.append(radial_point(center, radius, a))

    apex = radial_point(center, center_offset, mid_angle)
    points = [apex, *arc_points]
    return ShapelyPolygon(points)


def radial_pocket_generator(
    domain: Domain,
    params: RadialPocketParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "radial_pocket",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RadialPocketGenerator",
    ):
        return []

    bounds = domain.bounds
    center = (bounds.x_min + bounds.width / 2, bounds.y_min + bounds.height / 2)
    radius = params.radius_mm if params.radius_mm is not None else min(bounds.width, bounds.height) / 2

    positions = generate_angular_positions(
        rays=params.rays,
        minor_subdivisions=0,
        start_deg=params.start_angle_deg,
        end_deg=params.end_angle_deg,
    )

    angles = [ang for ang, _ in positions]

    is_full = abs(params.end_angle_deg - params.start_angle_deg) >= 360.0
    if is_full:
        angles.append(angles[0] + 360.0)

    center_island = None
    if params.center_shape and params.center_size_mm:
        center_island = _center_island_polygon(center, params.center_shape, params.center_size_mm)

    items: list[Item] = []
    for i in range(len(angles) - 1):
        a1 = angles[i]
        a2 = angles[i + 1]

        if params.shape == "arc":
            wedge = _build_wedge_arc(center, radius, a1, a2, params.bar_width_mm)
        else:
            wedge = _build_wedge_triangle(center, radius, a1, a2, params.bar_width_mm)

        if wedge.is_empty:
            continue

        if center_island and not center_island.is_empty:
            diff = wedge.difference(center_island)
            if diff.is_empty:
                continue
            wedge = diff  # type: ignore[assignment]

        for poly in iter_polygons(wedge):
            if poly.is_empty or poly.area < 0.01:
                continue
            item = shapely_to_item(
                polygon=poly,
                feature_type="pocket",
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, len(items), f"wedge_{i}"),
            )
            items.append(item)

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RadialPocketGenerator: No wedges fit within domain. "
            f"Domain: {bounds.width:.1f}x{bounds.height:.1f}mm, rays: {params.rays}"
        )

    return items


__all__ = ["radial_pocket_generator"]
