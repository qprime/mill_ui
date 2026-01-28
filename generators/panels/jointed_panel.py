from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domains import Domain
from generators.base import (
    BaseParams,
    GeneratorResult,
)
from generators.loop.profile import profile_generator
from generators.base import ProfileParams
from layout_ast.layout import Item, Geometry, Placement, Feature
from assembly.notches import NotchSpec, build_notched_polygon


EdgeName = Literal["top", "bottom", "left", "right"]

EDGE_NAME_TO_INDEX: dict[EdgeName, int] = {
    "bottom": 0,
    "right": 1,
    "top": 2,
    "left": 3,
}


@dataclass(frozen=True)
class NotchedPanelParams(BaseParams):
    width_mm: float
    height_mm: float
    notches: tuple[NotchSpec, ...] = ()
    part_name: str | None = None
    sheet_thickness_mm: float | None = None

    def validate(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(
                f"NotchedPanelParams: width_mm must be positive, got {self.width_mm}"
            )
        if self.height_mm <= 0:
            raise ValueError(
                f"NotchedPanelParams: height_mm must be positive, got {self.height_mm}"
            )


def notched_panel_generator(
    params: NotchedPanelParams,
    *,
    center: tuple[float, float] = (0.0, 0.0),
    allow_empty: bool = False,
    shape_id_prefix: str = "panel",
    label: str | None = None,
) -> GeneratorResult:
    params.validate()

    shape_id = shape_id_prefix
    if params.part_name:
        shape_id = f"{shape_id_prefix}_{params.part_name.lower()}"

    if params.notches:
        polygon_pts = build_notched_polygon(
            params.width_mm,
            params.height_mm,
            center,
            params.notches,
        )

        if len(polygon_pts) < 3:
            if allow_empty:
                return []
            raise ValueError("build_notched_polygon returned fewer than 3 points")

        cx = sum(p[0] for p in polygon_pts) / len(polygon_pts)
        cy = sum(p[1] for p in polygon_pts) / len(polygon_pts)
        relative_pts = [[p[0] - cx, p[1] - cy] for p in polygon_pts]

        item = Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data={"points": relative_pts}),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=Feature(
                type="profile",
                depth="through",
                side="outside",
            ),
            shape_id=f"{shape_id}_0_outer",
            label=label,
        )
        return [item]

    domain = Domain.from_rectangle(
        width_mm=params.width_mm,
        height_mm=params.height_mm,
        center=center,
    )

    profile_params = ProfileParams(
        side="outside",
        depth="through",
    )

    items = list(profile_generator(
        domain,
        profile_params,
        allow_empty=allow_empty,
        shape_id_prefix=shape_id,
        sheet_thickness_mm=params.sheet_thickness_mm,
        label=label,
    ))

    return items


__all__ = ["NotchedPanelParams", "notched_panel_generator"]
