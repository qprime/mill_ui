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
from assembly.notches import NotchSpec, notch_to_polyline


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

    domain = Domain.from_rectangle(
        width_mm=params.width_mm,
        height_mm=params.height_mm,
        center=center,
    )

    profile_params = ProfileParams(
        side="outside",
        depth="through",
    )

    shape_id = shape_id_prefix
    if params.part_name:
        shape_id = f"{shape_id_prefix}_{params.part_name.lower()}"

    items = list(profile_generator(
        domain,
        profile_params,
        allow_empty=allow_empty,
        shape_id_prefix=shape_id,
        sheet_thickness_mm=params.sheet_thickness_mm,
        label=label,
    ))

    if params.notches:
        half_w = params.width_mm / 2
        half_h = params.height_mm / 2
        polygon = (
            (center[0] - half_w, center[1] - half_h),
            (center[0] + half_w, center[1] - half_h),
            (center[0] + half_w, center[1] + half_h),
            (center[0] - half_w, center[1] + half_h),
        )

        for i, notch in enumerate(params.notches):
            polyline_pts = notch_to_polyline(polygon, notch)
            if not polyline_pts:
                continue

            center_x = sum(p[0] for p in polyline_pts) / len(polyline_pts)
            center_y = sum(p[1] for p in polyline_pts) / len(polyline_pts)
            relative_pts = [(p[0] - center_x, p[1] - center_y) for p in polyline_pts]

            notch_item = Item(
                kind="shape",
                type="Polyline",
                geometry=Geometry(data={
                    "points": relative_pts,
                    "closed": False,
                }),
                placement=Placement(center_xy_mm=(center_x, center_y)),
                feature=Feature(
                    type="profile",
                    depth="through",
                    side="on",
                ),
                shape_id=f"{shape_id}_notch_{i}",
            )
            items.append(notch_item)

    return items


__all__ = ["NotchedPanelParams", "notched_panel_generator"]
