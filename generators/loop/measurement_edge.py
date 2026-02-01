from __future__ import annotations

from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch, sheet_to_local
from generators.base import (
    GeneratorResult,
    MeasurementEdgeParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.area.engrave_text import engrave_number_label
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def _clip_line_to_domain(
    line_start: tuple[float, float],
    line_end: tuple[float, float],
    domain: Domain,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    from shapely.geometry import LineString

    line = LineString([line_start, line_end])
    polygon = domain.polygon

    intersection = line.intersection(polygon)

    if intersection.is_empty:
        return []

    segments = []

    if intersection.geom_type == "LineString":
        coords = list(intersection.coords)
        if len(coords) >= 2:
            segments.append(
                ((coords[0][0], coords[0][1]), (coords[-1][0], coords[-1][1]))
            )
    elif intersection.geom_type == "MultiLineString":
        for geom in intersection.geoms:
            coords = list(geom.coords)
            if len(coords) >= 2:
                segments.append(
                    ((coords[0][0], coords[0][1]), (coords[-1][0], coords[-1][1]))
                )

    return segments


def measurement_edge_generator(
    domain: Domain,
    params: MeasurementEdgeParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "measurement_edge",
) -> GeneratorResult:
    params.validate()

    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="MeasurementEdgeGenerator",
    ):
        return []

    local_bounds = _get_local_bounds(domain)
    local_x_min = local_bounds["x_min"]
    local_x_max = local_bounds["x_max"]
    local_y_min = local_bounds["y_min"]
    local_y_max = local_bounds["y_max"]

    minor_spacing = params.get_minor_spacing()
    major_spacing = params.get_major_spacing()
    minor_length = params.minor_length_mm
    major_length = params.major_length_mm

    items: list[Item] = []
    item_index = 0

    def is_major_tick(pos: float, origin: float) -> bool:
        offset = abs(pos - origin)
        return abs(offset % major_spacing) < 0.001 or abs(offset % major_spacing - major_spacing) < 0.001

    def add_tick(
        start_local: tuple[float, float],
        end_local: tuple[float, float],
        suffix: str,
    ) -> None:
        nonlocal item_index
        sheet_points = local_to_sheet_batch([start_local, end_local], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]

        clipped = _clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            item = _create_line_item(
                start=seg_start,
                end=seg_end,
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index, suffix),
            )
            items.append(item)
            item_index += 1

    x_origin = local_x_min
    y_origin = local_y_min

    edges_set = set(params.edges)

    if params.label_offset_mm is not None:
        label_offset = params.label_offset_mm
    else:
        label_offset = major_length + params.label_height_mm * 0.8
    label_index = 0

    has_left = "left" in edges_set
    has_bottom = "bottom" in edges_set

    label_spacing = int(major_spacing) * params.label_interval

    def should_label(value: int) -> bool:
        if value < params.label_start:
            return False
        return (value - params.label_start) % label_spacing == 0

    def add_label(
        local_pos: tuple[float, float],
        value: int,
        orientation: str,
        alignment: str = "center",
        vertical_alignment: str = "center",
    ) -> None:
        nonlocal label_index
        if not params.labels:
            return
        sheet_pos = local_to_sheet_batch([local_pos], domain)[0]
        label_items = engrave_number_label(
            value=value,
            position=sheet_pos,
            height_mm=params.label_height_mm,
            depth_mm=params.depth_mm,
            alignment=alignment,
            vertical_alignment=vertical_alignment,
            orientation=orientation,
            shape_id_prefix=f"{shape_id_prefix}_label_{label_index}",
        )
        items.extend(label_items)
        label_index += 1

    if "bottom" in edges_set or "top" in edges_set:
        x = x_origin
        first_major = True
        while x <= local_x_max + 0.001:
            is_major = is_major_tick(x, x_origin)
            if is_major or params.minor_ticks:
                tick_length = major_length if is_major else minor_length

                if "bottom" in edges_set:
                    add_tick(
                        (x, local_y_min),
                        (x, local_y_min + tick_length),
                        "bottom",
                    )

                if "top" in edges_set:
                    add_tick(
                        (x, local_y_max),
                        (x, local_y_max - tick_length),
                        "top",
                    )

            if is_major:
                value = int(round(x - x_origin))
                skip_label = first_major and has_left and value == 0
                if value >= 0 and not skip_label and should_label(value):
                    if "bottom" in edges_set:
                        add_label((x, local_y_min - label_offset), value, "horizontal")
                    if "top" in edges_set:
                        add_label((x, local_y_max + label_offset), value, "horizontal")
                first_major = False

            x += minor_spacing

    if "left" in edges_set or "right" in edges_set:
        y = y_origin
        first_major = True
        while y <= local_y_max + 0.001:
            is_major = is_major_tick(y, y_origin)
            if is_major or params.minor_ticks:
                tick_length = major_length if is_major else minor_length

                if "left" in edges_set:
                    add_tick(
                        (local_x_min, y),
                        (local_x_min + tick_length, y),
                        "left",
                    )

                if "right" in edges_set:
                    add_tick(
                        (local_x_max, y),
                        (local_x_max - tick_length, y),
                        "right",
                    )

            if is_major:
                value = int(round(y - y_origin))
                skip_label = first_major and has_bottom and value == 0
                if value >= 0 and not skip_label and should_label(value):
                    if "left" in edges_set:
                        add_label((local_x_min - label_offset, y), value, "vertical", "center", "bottom")
                    if "right" in edges_set:
                        add_label((local_x_max + label_offset, y), value, "vertical", "center", "top")
                first_major = False

            y += minor_spacing

    if not items and not allow_empty:
        raise ValueError(
            "MeasurementEdgeGenerator: Could not generate any tick marks. "
            "Domain may be too small for the specified spacing."
        )

    return items


def _create_line_item(
    start: tuple[float, float],
    end: tuple[float, float],
    depth_mm: float,
    shape_id: str,
) -> Item:
    cx = (start[0] + end[0]) / 2
    cy = (start[1] + end[1]) / 2

    geometry_data = {
        "start": [start[0] - cx, start[1] - cy],
        "end": [end[0] - cx, end[1] - cy],
        "width_mm": 0.5,
    }

    return Item(
        kind="shape",
        type="Line",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(
            type="engrave",
            depth=str(depth_mm),
            depth_mm=depth_mm,
        ),
        shape_id=shape_id,
    )


def _get_local_bounds(domain: Domain) -> dict[str, float]:
    local_points = [
        sheet_to_local(pt, domain)
        for pt in domain.outer_boundary
    ]

    xs = [p[0] for p in local_points]
    ys = [p[1] for p in local_points]

    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


__all__ = ["measurement_edge_generator"]
