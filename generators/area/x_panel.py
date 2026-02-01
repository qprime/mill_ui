
from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    GeneratorResult,
    XPanelParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def x_panel_generator(
    domain: Domain,
    params: XPanelParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "x_panel",
) -> GeneratorResult:
    params.validate()

    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="XPanelGenerator",
    ):
        return []

    bounds = domain.bounds
    w = bounds.width
    h = bounds.height
    x0 = bounds.x_min
    y0 = bounds.y_min

    half_bar = params.bar_width_mm / 2

    if w <= params.bar_width_mm * 2 or h <= params.bar_width_mm * 2:
        if allow_empty:
            return []
        raise ValueError(
            f"XPanelGenerator: Domain {w}x{h}mm too small for bar_width {params.bar_width_mm}mm"
        )

    cx = x0 + w / 2
    cy = y0 + h / 2

    items: list[Item] = []

    triangles = [
        (
            "top",
            [
                (x0 + half_bar, y0 + h - half_bar),
                (cx, cy + half_bar),
                (x0 + w - half_bar, y0 + h - half_bar),
            ],
        ),
        (
            "bottom",
            [
                (x0 + half_bar, y0 + half_bar),
                (cx, cy - half_bar),
                (x0 + w - half_bar, y0 + half_bar),
            ],
        ),
        (
            "left",
            [
                (x0 + half_bar, y0 + half_bar),
                (cx - half_bar, cy),
                (x0 + half_bar, y0 + h - half_bar),
            ],
        ),
        (
            "right",
            [
                (x0 + w - half_bar, y0 + half_bar),
                (cx + half_bar, cy),
                (x0 + w - half_bar, y0 + h - half_bar),
            ],
        ),
    ]

    for idx, (name, points) in enumerate(triangles):
        centroid_x = sum(p[0] for p in points) / 3
        centroid_y = sum(p[1] for p in points) / 3

        relative_points = [[p[0] - centroid_x, p[1] - centroid_y] for p in points]

        item = Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data={
                "points": relative_points,
            }),
            placement=Placement(center_xy_mm=(centroid_x, centroid_y)),
            feature=Feature(
                type="pocket",
                depth=str(params.depth_mm),
                depth_mm=params.depth_mm,
            ),
            shape_id=generate_shape_id(shape_id_prefix, idx, name),
        )
        items.append(item)

    return items


__all__ = ["x_panel_generator"]
