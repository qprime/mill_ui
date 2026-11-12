from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from assembly.core import Assembly, Interface, InterfaceType, MemberSpec, RemovalKind
from assembly.cubby import cubby
from assembly.joinery import Butt, Captured, Finger, JoineryStrategy
from assembly.panel import Edge, NotchSpec, PanelRole, PanelSpec


@dataclass(frozen=True)
class _BoxCapFit:
    edge_inset_mm: float = 0.0
    wall_extension_mm: float = 0.0


def _box_cap_fit(joinery: JoineryStrategy | Literal["none"] | None, thickness: float) -> _BoxCapFit:
    if joinery is None or joinery == "none" or isinstance(joinery, Finger):
        return _BoxCapFit()
    if isinstance(joinery, Captured):
        depth = joinery.groove_depth_mm(thickness)
        if not 0 < depth <= thickness:
            raise ValueError(f"Box cap groove depth must be positive and at most {thickness}mm, got {depth}mm")
        if joinery.receiving == "a":
            return _BoxCapFit(edge_inset_mm=thickness - depth)
        if joinery.inset_mm != 0:
            raise ValueError("Box caps with receiving='b' and nonzero inset require explicit wall placement")
        return _BoxCapFit(wall_extension_mm=thickness - depth)
    return _BoxCapFit(edge_inset_mm=thickness)


def box(
    width: float,
    length: float,
    height: float,
    thickness: float,
    side_joinery: JoineryStrategy | None = None,
    perimeter_joinery: JoineryStrategy | None = None,
    top: JoineryStrategy | Literal["none"] | None = None,
    bottom: JoineryStrategy | Literal["none"] | None = None,
) -> Assembly:
    if side_joinery is None:
        side_joinery = Finger()
    default_cap_joinery = perimeter_joinery if perimeter_joinery is not None else Captured()
    if top is None:
        top = default_cap_joinery
    if bottom is None:
        bottom = default_cap_joinery
    top_fit = _box_cap_fit(top, thickness)
    bottom_fit = _box_cap_fit(bottom, thickness)
    wall_height = height - top_fit.wall_extension_mm - bottom_fit.wall_extension_mm
    if wall_height <= 0:
        raise ValueError(f"Box cap joints leave no positive wall height: {wall_height}mm")
    if min(width, length) <= 2 * max(top_fit.edge_inset_mm, bottom_fit.edge_inset_mm):
        raise ValueError("Box dimensions leave no positive cap span")
    side_width = length if isinstance(side_joinery, Finger) else length - 2 * thickness
    front = PanelSpec(
        name="front",
        width_mm=width,
        height_mm=wall_height,
        thickness_mm=thickness,
        role=PanelRole.FRONT,
    )
    back_panel = PanelSpec(
        name="back",
        width_mm=width,
        height_mm=wall_height,
        thickness_mm=thickness,
        role=PanelRole.BACK,
    )
    left = PanelSpec(
        name="left_side",
        width_mm=side_width,
        height_mm=wall_height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=side_width,
        height_mm=wall_height,
        thickness_mm=thickness,
        role=PanelRole.RIGHT,
    )

    panels: dict[str, MemberSpec] = {
        "front": front,
        "back": back_panel,
        "left_side": left,
        "right_side": right,
    }

    interfaces: list[Interface] = [
        Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", side_joinery),
        Interface(InterfaceType.SIDE_TO_SIDE, "front", "right", "right_side", "left", side_joinery),
        Interface(InterfaceType.SIDE_TO_SIDE, "back", "right", "left_side", "left", side_joinery),
        Interface(InterfaceType.SIDE_TO_SIDE, "back", "left", "right_side", "right", side_joinery),
    ]

    if bottom is not None and bottom != "none":
        bottom_x = width - 2 * bottom_fit.edge_inset_mm
        bottom_y = length - 2 * bottom_fit.edge_inset_mm
        bottom_panel = PanelSpec(
            name="bottom",
            width_mm=bottom_x,
            height_mm=bottom_y,
            thickness_mm=thickness,
            role=PanelRole.BOTTOM,
        )
        panels["bottom"] = bottom_panel

        interfaces.append(Interface(InterfaceType.BOTTOM, "front", "bottom", "bottom", "top", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "back", "bottom", "bottom", "bottom", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "right_side", "bottom", "bottom", "right", bottom))

    if top is not None and top != "none":
        top_x = width - 2 * top_fit.edge_inset_mm
        top_y = length - 2 * top_fit.edge_inset_mm
        top_panel = PanelSpec(
            name="top",
            width_mm=top_x,
            height_mm=top_y,
            thickness_mm=thickness,
            role=PanelRole.TOP,
        )
        panels["top"] = top_panel

        interfaces.append(Interface(InterfaceType.TOP, "front", "top", "top", "top", top))
        interfaces.append(Interface(InterfaceType.TOP, "back", "top", "top", "bottom", top))
        interfaces.append(Interface(InterfaceType.TOP, "left_side", "top", "top", "left", top))
        interfaces.append(Interface(InterfaceType.TOP, "right_side", "top", "top", "right", top))

    return Assembly(members=panels, interfaces=tuple(interfaces))


def carcass(  # noqa: C901 — conditional builder (defer refactor)
    width: float,
    length: float,
    height: float,
    thickness: float,
    side_joinery: JoineryStrategy | None = None,
    cap_style: Literal["between_sides", "over_sides"] = "between_sides",
    perimeter_joinery: JoineryStrategy | None = None,
    top: JoineryStrategy | Literal["none"] | None = None,
    bottom: JoineryStrategy | Literal["none"] | None = None,
    back: JoineryStrategy | Literal["none"] | None = None,
    back_thickness: float | None = None,
    back_inset: float = 0.0,
    fixed_shelves: int = 0,
    shelf_joinery: JoineryStrategy | None = None,
    shelf_back_support: bool = False,
    toe_kick_height: float | None = None,
    toe_kick_setback: float | None = None,
    toe_kick_style: Literal["between_sides", "over_sides"] = "between_sides",
    toe_kick_cover: bool = True,
) -> Assembly:
    if side_joinery is None:
        side_joinery = Butt()
    if shelf_joinery is None:
        shelf_joinery = Captured()
    default_cap_joinery = perimeter_joinery if perimeter_joinery is not None else Butt()
    if top is None:
        top = default_cap_joinery
    if bottom is None:
        bottom = default_cap_joinery

    if cap_style == "between_sides":
        side_height = height
        cap_width = width - 2 * thickness
    else:
        side_height = height - 2 * thickness
        cap_width = width

    left = PanelSpec(
        name="left_side",
        width_mm=length,
        height_mm=side_height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=length,
        height_mm=side_height,
        thickness_mm=thickness,
        role=PanelRole.RIGHT,
    )

    panels: dict[str, MemberSpec] = {
        "left_side": left,
        "right_side": right,
    }

    interfaces: list[Interface] = []

    if top is not None and top != "none":
        top_panel = PanelSpec(
            name="top",
            width_mm=cap_width,
            height_mm=length,
            thickness_mm=thickness,
            role=PanelRole.TOP,
        )
        panels["top"] = top_panel
        interfaces.append(Interface(InterfaceType.TOP, "left_side", "top", "top", "left", top))
        interfaces.append(Interface(InterfaceType.TOP, "right_side", "top", "top", "right", top))

    effective_toe_kick_setback = (
        toe_kick_setback if toe_kick_setback is not None else (50.0 if toe_kick_height else 0.0)
    )
    effective_toe_kick_height = toe_kick_height if toe_kick_height is not None else 0.0

    if effective_toe_kick_height > 0:
        kick_notch = NotchSpec(
            edge=Edge.BOTTOM,
            u_start_mm=0.0,
            u_len_mm=effective_toe_kick_setback,
            depth_mm=effective_toe_kick_height,
        )
        panels["left_side"] = cast(PanelSpec, panels["left_side"]).with_notches((kick_notch,))
        panels["right_side"] = cast(PanelSpec, panels["right_side"]).with_notches((kick_notch,))

    if bottom is not None and bottom != "none":
        bottom_len = length - effective_toe_kick_setback if effective_toe_kick_height > 0 else length
        bottom_panel = PanelSpec(
            name="bottom",
            width_mm=cap_width,
            height_mm=bottom_len,
            thickness_mm=thickness,
            role=PanelRole.BOTTOM,
        )
        panels["bottom"] = bottom_panel
        bottom_dado_position = effective_toe_kick_height if effective_toe_kick_height > 0 else None
        interfaces.append(
            Interface(
                InterfaceType.BOTTOM,
                "left_side",
                "bottom",
                "bottom",
                "left",
                bottom,
                position_along_edge_a_mm=bottom_dado_position,
            )
        )
        interfaces.append(
            Interface(
                InterfaceType.BOTTOM,
                "right_side",
                "bottom",
                "bottom",
                "right",
                bottom,
                position_along_edge_a_mm=bottom_dado_position,
            )
        )

    if effective_toe_kick_height > 0 and toe_kick_cover:
        kick_cover_width = cap_width if toe_kick_style == "between_sides" else width
        kick_cover = PanelSpec(
            name="toe_kick_cover",
            width_mm=kick_cover_width,
            height_mm=effective_toe_kick_height,
            thickness_mm=thickness,
            role=PanelRole.FRONT,
        )
        panels["toe_kick_cover"] = kick_cover

    if back is not None and back != "none":
        back_width = width - 2 * back_inset if back_inset else width
        back_height = height - 2 * back_inset if back_inset else height
        back_panel = PanelSpec(
            name="back",
            width_mm=back_width,
            height_mm=back_height,
            thickness_mm=thickness,
            role=PanelRole.BACK,
        )
        panels["back"] = back_panel
        back_joinery: JoineryStrategy
        if back_thickness and isinstance(back, Captured):
            back_joinery = Captured(
                dado_depth_mm=back.dado_depth_mm,
                dado_width_mm=back_thickness,
                inset_mm=back.inset_mm,
                fitment_mm=back.fitment_mm,
            )
        else:
            back_joinery = back
        interfaces.append(Interface(InterfaceType.SIDE_TO_SIDE, "left_side", "right", "back", "left", back_joinery))
        interfaces.append(Interface(InterfaceType.SIDE_TO_SIDE, "right_side", "left", "back", "right", back_joinery))
        if back_joinery.removal_kind == RemovalKind.FACE:
            if "top" in panels:
                interfaces.append(Interface(InterfaceType.TOP, "top", "top", "back", "top", back_joinery))
            if "bottom" in panels:
                interfaces.append(Interface(InterfaceType.BOTTOM, "bottom", "bottom", "back", "bottom", back_joinery))

    if fixed_shelves > 0:
        shelf_x = cap_width
        shelf_y = length - back_inset if back_inset else length
        interior_height = side_height
        if top is not None and top != "none":
            interior_height -= thickness
        if bottom is not None and bottom != "none":
            interior_height -= thickness
        shelf_spacing = interior_height / (fixed_shelves + 1)
        bottom_offset = thickness if (bottom is not None and bottom != "none") else 0.0

        for i in range(fixed_shelves):
            shelf = PanelSpec(
                name=f"shelf_{i + 1}",
                width_mm=shelf_x,
                height_mm=shelf_y,
                thickness_mm=thickness,
                role=PanelRole.SHELF,
            )
            panels[f"shelf_{i + 1}"] = shelf
            shelf_position = bottom_offset + (i + 1) * shelf_spacing - thickness / 2
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "left_side",
                    "bottom",
                    f"shelf_{i + 1}",
                    "left",
                    shelf_joinery,
                    position_along_edge_a_mm=shelf_position,
                )
            )
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "right_side",
                    "bottom",
                    f"shelf_{i + 1}",
                    "right",
                    shelf_joinery,
                    position_along_edge_a_mm=shelf_position,
                )
            )
            if shelf_back_support and "back" in panels:
                back_shelf_position = shelf_position - back_inset
                interfaces.append(
                    Interface(
                        InterfaceType.INTERNAL,
                        "back",
                        "bottom",
                        f"shelf_{i + 1}",
                        "top",
                        shelf_joinery,
                        position_along_edge_a_mm=back_shelf_position,
                    )
                )

    return Assembly(members=panels, interfaces=tuple(interfaces))


__all__ = [
    "box",
    "carcass",
    "cubby",
]
