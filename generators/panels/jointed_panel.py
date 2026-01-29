from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from generators.base import (
    BaseParams,
    GeneratorResult,
)
from generators.base import generate_shape_id
from layout_ast.layout import Item, Geometry, Placement, Feature
from assembly.notches import NotchSpec
from assembly.notches import build_notched_polygon


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

    items: list[Item] = []

    # Finger-joint "notches" are edge cutouts that must be part of the final
    # part boundary. If we emit them as separate notch features, the CAM pass
    # will cut the full rectangular profile behind them. Instead, bake the
    # cutouts into the panel's profile polygon.
    outer = build_notched_polygon(
        width_mm=params.width_mm,
        height_mm=params.height_mm,
        center=center,
        notches=params.notches,
    )

    cx, cy = center
    polygon_points = [[x - cx, y - cy] for x, y in outer]
    profile_item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data={"points": polygon_points}),
        placement=Placement(center_xy_mm=center),
        feature=Feature(type="profile", side="outside", depth="through"),
        shape_id=generate_shape_id(shape_id, 0, "outer"),
        label=label,
    )
    items.append(profile_item)

    return items


__all__ = ["NotchedPanelParams", "notched_panel_generator"]
