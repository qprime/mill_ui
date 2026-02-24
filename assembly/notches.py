from __future__ import annotations

import math
from typing import cast

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import orient, unary_union

from assembly.panel import Edge, NotchSpec
from domains.domain import Point2D


def validate_notch_fits_edge(notch: NotchSpec, edge_length: float) -> None:
    if notch.u_start_mm + notch.u_len_mm > edge_length + 1e-6:
        raise ValueError(
            f"Notch exceeds edge length: u_start={notch.u_start_mm}mm + "
            f"u_len={notch.u_len_mm}mm = {notch.u_start_mm + notch.u_len_mm}mm > "
            f"edge_length={edge_length}mm"
        )


def validate_notches_no_overlap(notches: list[NotchSpec]) -> None:
    by_edge: dict[int, list[NotchSpec]] = {}
    for n in notches:
        by_edge.setdefault(n.edge_index, []).append(n)

    for edge_idx, edge_notches in by_edge.items():
        sorted_notches = sorted(edge_notches, key=lambda x: x.u_start_mm)
        for i in range(len(sorted_notches) - 1):
            a = sorted_notches[i]
            b = sorted_notches[i + 1]
            if a.u_start_mm + a.u_len_mm > b.u_start_mm + 1e-6:
                raise ValueError(
                    f"Overlapping notches on edge {edge_idx}: "
                    f"[{a.u_start_mm}, {a.u_start_mm + a.u_len_mm}] overlaps "
                    f"[{b.u_start_mm}, {b.u_start_mm + b.u_len_mm}]"
                )


def notch_to_polyline(
    polygon: tuple[Point2D, ...],
    notch: NotchSpec,
) -> list[Point2D]:
    n_verts = len(polygon)
    if notch.edge_index < 0 or notch.edge_index >= n_verts:
        raise IndexError(f"edge_index {notch.edge_index} out of range for polygon with {n_verts} vertices")

    p0 = polygon[notch.edge_index]
    p1 = polygon[(notch.edge_index + 1) % n_verts]

    edge_dx = p1[0] - p0[0]
    edge_dy = p1[1] - p0[1]
    edge_len = math.sqrt(edge_dx * edge_dx + edge_dy * edge_dy)

    if edge_len < 1e-10:
        return []

    dx = edge_dx / edge_len
    dy = edge_dy / edge_len

    inward_nx = -dy
    inward_ny = dx

    notch_start_x = p0[0] + dx * notch.u_start_mm
    notch_start_y = p0[1] + dy * notch.u_start_mm
    notch_end_x = p0[0] + dx * (notch.u_start_mm + notch.u_len_mm)
    notch_end_y = p0[1] + dy * (notch.u_start_mm + notch.u_len_mm)

    depth = notch.depth_mm
    corner_radius = notch.shape_params.get("corner_radius_mm", 0.0)

    if notch.shape == "rectangular":
        if corner_radius > 0:
            r = min(corner_radius, notch.u_len_mm / 2, depth / 2)
            segs = 8
            pts: list[Point2D] = []
            pts.append((notch_start_x, notch_start_y))
            for i in range(segs + 1):
                angle = math.pi / 2 * i / segs
                ax = notch_start_x + r * (1 - math.cos(angle)) * inward_nx + r * math.sin(angle) * dx
                ay = notch_start_y + r * (1 - math.cos(angle)) * inward_ny + r * math.sin(angle) * dy
                pts.append((ax, ay))

            inner_start_x = notch_start_x + inward_nx * depth + dx * r
            inner_start_y = notch_start_y + inward_ny * depth + dy * r
            inner_end_x = notch_end_x + inward_nx * depth - dx * r
            inner_end_y = notch_end_y + inward_ny * depth - dy * r
            pts.append((inner_start_x, inner_start_y))
            pts.append((inner_end_x, inner_end_y))

            for i in range(segs + 1):
                angle = math.pi / 2 * (1 - i / segs)
                ax = notch_end_x + r * (1 - math.cos(angle)) * inward_nx - r * math.sin(angle) * dx
                ay = notch_end_y + r * (1 - math.cos(angle)) * inward_ny - r * math.sin(angle) * dy
                pts.append((ax, ay))
            pts.append((notch_end_x, notch_end_y))
            return pts
        else:
            inner_start_x = notch_start_x + inward_nx * depth
            inner_start_y = notch_start_y + inward_ny * depth
            inner_end_x = notch_end_x + inward_nx * depth
            inner_end_y = notch_end_y + inward_ny * depth

            return [
                (notch_start_x, notch_start_y),
                (inner_start_x, inner_start_y),
                (inner_end_x, inner_end_y),
                (notch_end_x, notch_end_y),
            ]
    else:
        inner_start_x = notch_start_x + inward_nx * depth
        inner_start_y = notch_start_y + inward_ny * depth
        inner_end_x = notch_end_x + inward_nx * depth
        inner_end_y = notch_end_y + inward_ny * depth

        return [
            (notch_start_x, notch_start_y),
            (inner_start_x, inner_start_y),
            (inner_end_x, inner_end_y),
            (notch_end_x, notch_end_y),
        ]


def build_notched_polygon(
    width_mm: float,
    height_mm: float,
    center: tuple[float, float],
    notches: tuple[NotchSpec, ...] | list[NotchSpec],
) -> tuple[Point2D, ...]:
    cx, cy = center
    half_w = width_mm / 2
    half_h = height_mm / 2

    base = box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    if not notches:
        result_oriented = orient(base, sign=1.0)
        return tuple(cast(tuple[float, float], c) for c in result_oriented.exterior.coords[:-1])

    notch_boxes = []
    for notch in notches:
        edge_idx = int(notch.edge_index)
        if edge_idx < 0 or edge_idx > 3:
            continue

        u_start = max(0.0, float(notch.u_start_mm))
        u_len = max(0.0, float(notch.u_len_mm))
        depth = max(0.0, float(notch.depth_mm))
        if u_len <= 0.0 or depth <= 0.0:
            continue

        if edge_idx == 0:
            x_min = cx - half_w + u_start
            x_max = x_min + u_len
            y_min = cy - half_h
            y_max = y_min + depth
        elif edge_idx == 1:
            y_min = cy - half_h + u_start
            y_max = y_min + u_len
            x_max = cx + half_w
            x_min = x_max - depth
        elif edge_idx == 2:
            x_min = cx - half_w + u_start
            x_max = x_min + u_len
            y_max = cy + half_h
            y_min = y_max - depth
        else:
            y_min = cy - half_h + u_start
            y_max = y_min + u_len
            x_min = cx - half_w
            x_max = x_min + depth

        x_min = max(cx - half_w, x_min)
        x_max = min(cx + half_w, x_max)
        y_min = max(cy - half_h, y_min)
        y_max = min(cy + half_h, y_max)

        if x_max <= x_min or y_max <= y_min:
            continue

        notch_boxes.append(box(x_min, y_min, x_max, y_max))

    geom: BaseGeometry
    if notch_boxes:
        cutout = unary_union(notch_boxes)
        geom = base.difference(cutout)
    else:
        geom = base

    geom = orient(geom, sign=1.0)

    if geom.is_empty:
        return tuple(cast(tuple[float, float], c) for c in base.exterior.coords[:-1])

    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)

    if not isinstance(geom, Polygon):
        return tuple(cast(tuple[float, float], c) for c in base.exterior.coords[:-1])

    return tuple(cast(tuple[float, float], c) for c in geom.exterior.coords[:-1])


def finger_joints_to_notches(
    edge_index: int,
    edge_length: float,
    depth_mm: float,
    phase: int,
    width_mm: float | None = None,
    count: int | None = None,
    clearance_mm: float = 0.12,
) -> list[NotchSpec]:
    if (width_mm is None) == (count is None):
        raise ValueError("Specify exactly one of width_mm or count")

    assert width_mm is not None
    n = count if count is not None else round(edge_length / width_mm)

    n = max(3, n)
    if n % 2 == 0:
        n += 1

    finger_width = edge_length / n

    notches: list[NotchSpec] = []
    for i in range(n):
        is_notch = (i % 2 == 1) == (phase == 0)
        if is_notch:
            boundary_expansion = clearance_mm / 4
            u_start = i * finger_width - boundary_expansion
            u_end = (i + 1) * finger_width + boundary_expansion
            u_start = max(0.0, u_start)
            u_end = min(edge_length, u_end)
            if u_end - u_start <= 1e-9:
                continue
            notch = NotchSpec(
                edge=Edge(edge_index),
                u_start_mm=u_start,
                u_len_mm=u_end - u_start,
                depth_mm=depth_mm,
            )
            notches.append(notch)

    return notches


__all__ = [
    "build_notched_polygon",
    "finger_joints_to_notches",
    "notch_to_polyline",
    "validate_notch_fits_edge",
    "validate_notches_no_overlap",
]
