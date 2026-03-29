from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Literal

from ir.removal_intent import Bounds2D
from layout_ast.layout import Item, LayoutAST

Orientation = Literal["horizontal", "vertical"]
DimensionPlacement = Literal["shape_relative", "sheet_edge"]


@dataclass(frozen=True)
class DimensionRequest:
    orientation: Orientation
    a: float
    b: float
    anchor: float
    text: str


@dataclass(frozen=True)
class PlacedDimension:
    orientation: Orientation
    a: float
    b: float
    anchor: float
    rail: float
    text: str


class _IntervalAllocator:
    def __init__(self) -> None:
        self._levels: list[list[tuple[float, float]]] = []

    def allocate(self, start: float, end: float, padding: float) -> int:
        start, end = (start, end) if start <= end else (end, start)
        for level_index, intervals in enumerate(self._levels):
            if not any(_overlaps(start, end, other_start, other_end, padding) for other_start, other_end in intervals):
                intervals.append((start, end))
                return level_index

        self._levels.append([(start, end)])
        return len(self._levels) - 1


def collect_dimension_requests(
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    *,
    include_features: set[str] | None = None,
    deduplicate: bool = True,
    y_flip=None,
) -> list[DimensionRequest]:
    include_features = include_features or {"profile"}
    return _collect_dimension_requests(
        ast, offset_x, offset_y, include_features=include_features, deduplicate=deduplicate, y_flip=y_flip
    )


def place_on_rails(
    requests: list[DimensionRequest],
    sheet_width_mm: float,
    offset_x: float,
    offset_y: float,
    *,
    margin: float = 100.0,
    placement_mode: DimensionPlacement = "shape_relative",
) -> list[PlacedDimension]:
    base_offset = 20.0
    stack_gap = 20.0

    h_allocator = _IntervalAllocator()
    v_allocator = _IntervalAllocator()

    placed: list[PlacedDimension] = []

    for request in requests:
        a, b = (request.a, request.b) if request.a <= request.b else (request.b, request.a)

        if request.orientation == "horizontal":
            level = h_allocator.allocate(a, b, padding=15.0)
            if placement_mode == "sheet_edge":
                rail_y = offset_y - base_offset - (level * stack_gap)
            else:
                rail_y = request.anchor - base_offset - (level * stack_gap)

            min_rail_y = offset_y - margin
            if rail_y < min_rail_y:
                rail_y = min_rail_y

            placed.append(
                PlacedDimension(
                    orientation="horizontal",
                    a=a,
                    b=b,
                    anchor=request.anchor,
                    rail=rail_y,
                    text=request.text,
                )
            )
        else:
            level = v_allocator.allocate(a, b, padding=40.0)
            if placement_mode == "sheet_edge":
                rail_x = offset_x + sheet_width_mm + base_offset + (level * stack_gap)
            else:
                rail_x = request.anchor + base_offset + (level * stack_gap)

            max_rail_x = offset_x + sheet_width_mm + margin
            if rail_x > max_rail_x:
                rail_x = max_rail_x

            placed.append(
                PlacedDimension(
                    orientation="vertical",
                    a=a,
                    b=b,
                    anchor=request.anchor,
                    rail=rail_x,
                    text=request.text,
                )
            )

    return placed


def place_dimensions_on_rails(
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    *,
    margin: float = 100.0,
    include_features: set[str] | None = None,
    deduplicate: bool = True,
    y_flip=None,
    placement_mode: DimensionPlacement = "shape_relative",
) -> list[PlacedDimension]:
    requests = collect_dimension_requests(
        ast, offset_x, offset_y, include_features=include_features, deduplicate=deduplicate, y_flip=y_flip
    )
    return place_on_rails(
        requests, ast.sheet.width_mm, offset_x, offset_y, margin=margin, placement_mode=placement_mode
    )


def _collect_dimension_requests(
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    *,
    include_features: set[str],
    deduplicate: bool = True,
    y_flip=None,
) -> list[DimensionRequest]:
    yf = y_flip if y_flip is not None else (lambda y: y)
    requests: list[DimensionRequest] = []

    shape_items: list[Item] = [
        item
        for item in ast.items
        if item.kind == "shape"
        and item.feature is not None
        and item.feature.type in include_features
        and item.geometry is not None
        and item.placement is not None
        and item.shape_id is not None
    ]

    shape_items.sort(key=lambda i: (i.feature.type, i.shape_id or "", i.type))  # type: ignore[union-attr]

    dimensioned_sizes: set[tuple[str, str, int, int]] = set()

    for item in shape_items:
        bounds = _item_bounds_in_svg(item, offset_x, offset_y, y_flip=yf)
        if bounds is None:
            continue

        w = bounds.x_max - bounds.x_min
        h = bounds.y_max - bounds.y_min

        if deduplicate:
            assert item.feature is not None
            size_key = (item.feature.type, item.type, round(w), round(h))
            if size_key in dimensioned_sizes:
                continue
            dimensioned_sizes.add(size_key)

        if item.type in ("Rect", "RoundedRect"):
            requests.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=bounds.x_min,
                    b=bounds.x_max,
                    anchor=bounds.y_min,
                    text=_fmt_mm(w),
                )
            )
            requests.append(
                DimensionRequest(
                    orientation="vertical",
                    a=bounds.y_min,
                    b=bounds.y_max,
                    anchor=bounds.x_max,
                    text=_fmt_mm(h),
                )
            )
        elif item.type == "Polygon":
            requests.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=bounds.x_min,
                    b=bounds.x_max,
                    anchor=bounds.y_min,
                    text=_fmt_mm(w),
                )
            )
            requests.append(
                DimensionRequest(
                    orientation="vertical",
                    a=bounds.y_min,
                    b=bounds.y_max,
                    anchor=bounds.x_max,
                    text=_fmt_mm(h),
                )
            )
            requests.extend(_polygon_edge_requests(item, offset_x, offset_y, deduplicate=deduplicate, y_flip=yf))
        elif item.type == "Circle":
            diameter = w
            requests.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=bounds.x_min,
                    b=bounds.x_max,
                    anchor=bounds.y_min,
                    text=f"⌀{_fmt_mm_value(diameter)}mm",
                )
            )

    requests.extend(_hole_spacing_requests(ast, offset_x, offset_y, deduplicate=deduplicate, y_flip=yf))

    return requests


def _hole_centers_grouped_by_parent(
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    y_flip=None,
) -> list[list[tuple[float, float]]]:
    yf = y_flip if y_flip is not None else (lambda y: y)

    profile_bounds: list[tuple[float, float, float, float]] = []
    for item in ast.items:
        if item.kind != "shape" or item.feature is None:
            continue
        if item.feature.type != "profile":
            continue
        if item.geometry is None or item.placement is None:
            continue

        cx, cy = item.placement.center_xy_mm
        w = float(item.geometry.data.get("w_mm", item.geometry.data.get("width", 0)))
        h = float(item.geometry.data.get("h_mm", item.geometry.data.get("height", 0)))
        if w <= 0 or h <= 0:
            continue

        x_min = cx - w / 2
        x_max = cx + w / 2
        y_min = cy - h / 2
        y_max = cy + h / 2
        profile_bounds.append((x_min, y_min, x_max, y_max))

    holes_by_parent: dict[int, list[tuple[float, float]]] = {}
    unparented_holes: list[tuple[float, float]] = []

    for item in ast.items:
        if item.kind != "shape" or item.feature is None or item.feature.type != "hole":
            continue
        if item.placement is None:
            continue

        hx, hy = item.placement.center_xy_mm

        parent_idx = None
        for idx, (x_min, y_min, x_max, y_max) in enumerate(profile_bounds):
            if x_min <= hx <= x_max and y_min <= hy <= y_max:
                parent_idx = idx
                break

        svg_x = offset_x + float(hx)
        svg_y = offset_y + yf(float(hy))

        if parent_idx is not None:
            holes_by_parent.setdefault(parent_idx, []).append((svg_x, svg_y))
        else:
            unparented_holes.append((svg_x, svg_y))

    result = list(holes_by_parent.values())
    if unparented_holes:
        result.append(unparented_holes)
    return result


def _hole_spacing_requests_for_group(  # noqa: C901 — spacing logic
    centers: list[tuple[float, float]],
    seen_h_spacings: set[int],
    seen_v_spacings: set[int],
    *,
    deduplicate: bool = True,
) -> list[DimensionRequest]:
    if len(centers) < 2:
        return []

    requests: list[DimensionRequest] = []

    by_y: dict[float, list[tuple[float, float]]] = {}
    for x, y in centers:
        key = round(y, 1)
        by_y.setdefault(key, []).append((x, y))

    for _, pts in sorted(by_y.items(), key=lambda kv: kv[0]):
        if len(pts) < 2:
            continue
        pts_sorted = sorted(pts, key=lambda p: p[0])
        y_anchor = sum(p[1] for p in pts_sorted) / len(pts_sorted)
        for (x1, _), (x2, _) in itertools.pairwise(pts_sorted):
            dx = abs(x2 - x1)
            if dx < 1e-6:
                continue
            if deduplicate:
                spacing_key = round(dx)
                if spacing_key in seen_h_spacings:
                    continue
                seen_h_spacings.add(spacing_key)
            requests.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=x1,
                    b=x2,
                    anchor=y_anchor,
                    text=_fmt_mm(dx),
                )
            )

    by_x: dict[float, list[tuple[float, float]]] = {}
    for x, y in centers:
        key = round(x, 1)
        by_x.setdefault(key, []).append((x, y))

    for _, pts in sorted(by_x.items(), key=lambda kv: kv[0]):
        if len(pts) < 2:
            continue
        pts_sorted = sorted(pts, key=lambda p: p[1])
        x_anchor = sum(p[0] for p in pts_sorted) / len(pts_sorted)
        for (_, y1), (_, y2) in itertools.pairwise(pts_sorted):
            dy = abs(y2 - y1)
            if dy < 1e-6:
                continue
            if deduplicate:
                spacing_key = round(dy)
                if spacing_key in seen_v_spacings:
                    continue
                seen_v_spacings.add(spacing_key)
            requests.append(
                DimensionRequest(
                    orientation="vertical",
                    a=y1,
                    b=y2,
                    anchor=x_anchor,
                    text=_fmt_mm(dy),
                )
            )

    return requests


def _hole_spacing_requests(
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    *,
    deduplicate: bool = True,
    y_flip=None,
) -> list[DimensionRequest]:
    hole_groups = _hole_centers_grouped_by_parent(ast, offset_x, offset_y, y_flip=y_flip)

    requests: list[DimensionRequest] = []
    seen_h_spacings: set[int] = set()
    seen_v_spacings: set[int] = set()

    for group in hole_groups:
        group_requests = _hole_spacing_requests_for_group(
            group,
            seen_h_spacings,
            seen_v_spacings,
            deduplicate=deduplicate,
        )
        requests.extend(group_requests)

    return requests


def _item_bounds_in_svg(item: Item, offset_x: float, offset_y: float, y_flip=None) -> Bounds2D | None:
    yf = y_flip if y_flip is not None else (lambda y: y)
    bounds = _item_bounds(item, y_flip=yf)
    if bounds is None:
        return None
    return Bounds2D(
        x_min=bounds.x_min + offset_x,
        x_max=bounds.x_max + offset_x,
        y_min=bounds.y_min + offset_y,
        y_max=bounds.y_max + offset_y,
    )


def _item_bounds(item: Item, y_flip=None) -> Bounds2D | None:
    if item.geometry is None or item.placement is None:
        return None

    yf = y_flip if y_flip is not None else (lambda y: y)
    cx, cy = item.placement.center_xy_mm
    cy = yf(cy)
    shape_type = item.type

    if shape_type in ("Rect", "RoundedRect"):
        w = float(item.geometry.data.get("w_mm", 0.0))
        h = float(item.geometry.data.get("h_mm", 0.0))
        y_min = cy - h / 2.0
        y_max = cy + h / 2.0
        return Bounds2D(x_min=cx - w / 2.0, x_max=cx + w / 2.0, y_min=min(y_min, y_max), y_max=max(y_min, y_max))

    if shape_type == "Circle":
        diameter = item.geometry.data.get("diameter_mm")
        radius = item.geometry.data.get("radius_mm")
        r = float(radius) if radius is not None else float(diameter or 0.0) / 2.0
        return Bounds2D(x_min=cx - r, x_max=cx + r, y_min=cy - r, y_max=cy + r)

    if shape_type == "Polygon":
        points = item.geometry.data.get("points", [])
        if not points:
            return None
        orig_cx, orig_cy = item.placement.center_xy_mm
        xs = [orig_cx + p[0] for p in points]
        ys = [yf(orig_cy + p[1]) for p in points]
        return Bounds2D(x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))

    return None


def _polygon_edge_requests(
    item: Item,
    offset_x: float,
    offset_y: float,
    *,
    deduplicate: bool = True,
    y_flip=None,
) -> list[DimensionRequest]:
    if item.geometry is None or item.placement is None:
        return []

    yf = y_flip if y_flip is not None else (lambda y: y)
    points = item.geometry.data.get("points", [])
    if len(points) < 3:
        return []

    cx, cy = item.placement.center_xy_mm

    requests: list[DimensionRequest] = []
    seen_lengths: set[int] = set()

    bounds = _item_bounds(item, y_flip=yf)
    if bounds is None:
        return []

    overall_w = bounds.x_max - bounds.x_min
    overall_h = bounds.y_max - bounds.y_min

    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]

        x1, y1_raw = cx + float(p1[0]), cy + float(p1[1])
        x2, y2_raw = cx + float(p2[0]), cy + float(p2[1])
        y1 = yf(y1_raw)
        y2 = yf(y2_raw)

        dx = abs(x2 - x1)
        dy = abs(y2_raw - y1_raw)

        is_horizontal = dy < 0.1 and dx > 0.1
        is_vertical = dx < 0.1 and dy > 0.1

        if not (is_horizontal or is_vertical):
            continue

        length = dx if is_horizontal else dy

        if abs(length - overall_w) < 1.0 or abs(length - overall_h) < 1.0:
            continue

        length_key = round(length)
        if deduplicate and length_key in seen_lengths:
            continue
        seen_lengths.add(length_key)

        if is_horizontal:
            requests.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=offset_x + min(x1, x2),
                    b=offset_x + max(x1, x2),
                    anchor=offset_y + y1,
                    text=_fmt_mm(length),
                )
            )
        else:
            requests.append(
                DimensionRequest(
                    orientation="vertical",
                    a=offset_y + min(y1, y2),
                    b=offset_y + max(y1, y2),
                    anchor=offset_x + x1,
                    text=_fmt_mm(length),
                )
            )

    return requests


def _fmt_mm(value_mm: float) -> str:
    return f"{_fmt_mm_value(value_mm)}mm"


def _fmt_mm_value(value_mm: float) -> str:
    return f"{float(value_mm):.1f}"


def _overlaps(a1: float, a2: float, b1: float, b2: float, padding: float) -> bool:
    a1, a2 = (a1, a2) if a1 <= a2 else (a2, a1)
    b1, b2 = (b1, b2) if b1 <= b2 else (b2, b1)
    return not (a2 < (b1 - padding) or a1 > (b2 + padding))


__all__ = [
    "DimensionPlacement",
    "DimensionRequest",
    "Orientation",
    "PlacedDimension",
    "collect_dimension_requests",
    "place_dimensions_on_rails",
    "place_on_rails",
]
