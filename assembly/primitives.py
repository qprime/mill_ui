from __future__ import annotations

from typing import Literal

from assembly.core import Assembly, Interface, InterfaceType, RemovalKind
from assembly.joinery import Butt, Captured, Finger, HalfLap, JoineryStrategy
from assembly.panel import Edge, NotchSpec, PanelRole, PanelSpec


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
    front = PanelSpec(
        name="front",
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.FRONT,
    )
    back_panel = PanelSpec(
        name="back",
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.BACK,
    )
    left = PanelSpec(
        name="left_side",
        width_mm=length - 2 * thickness,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=length - 2 * thickness,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.RIGHT,
    )

    panels: dict[str, PanelSpec] = {
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
        bottom_x = width - 2 * thickness
        bottom_y = length - 2 * thickness
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
        top_x = width - 2 * thickness
        top_y = length - 2 * thickness
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


def carcass(
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

    panels: dict[str, PanelSpec] = {
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
        panels["left_side"] = panels["left_side"].with_notches((kick_notch,))
        panels["right_side"] = panels["right_side"].with_notches((kick_notch,))

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


def cubby(
    width: float,
    length: float,
    height: float,
    thickness: float,
    rows: int,
    cols: int,
    perimeter_joinery: JoineryStrategy | None = None,
    shelf_joinery: JoineryStrategy | None = None,
    partition_joinery: JoineryStrategy | None = None,
    internal_joinery: JoineryStrategy | None = None,
    back: JoineryStrategy | Literal["none"] | None = None,
    back_thickness: float | None = None,
    back_inset: float = 0.0,
    back_internal_support: bool = True,
) -> Assembly:
    if perimeter_joinery is None:
        perimeter_joinery = Finger()
    if shelf_joinery is None:
        shelf_joinery = Captured()
    if partition_joinery is None:
        partition_joinery = Captured()
    if internal_joinery is None:
        internal_joinery = HalfLap()
    cell_width = (width - 2 * thickness) / cols
    cell_height = (height - 2 * thickness) / rows

    top = PanelSpec(
        name="top",
        width_mm=width - 2 * thickness,
        height_mm=length,
        thickness_mm=thickness,
        role=PanelRole.TOP,
    )
    bottom = PanelSpec(
        name="bottom",
        width_mm=width - 2 * thickness,
        height_mm=length,
        thickness_mm=thickness,
        role=PanelRole.BOTTOM,
    )
    left = PanelSpec(
        name="left_side",
        width_mm=length,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=length,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.RIGHT,
    )

    panels: dict[str, PanelSpec] = {
        "top": top,
        "bottom": bottom,
        "left_side": left,
        "right_side": right,
    }

    interfaces: list[Interface] = [
        Interface(InterfaceType.TOP, "top", "left", "left_side", "top", perimeter_joinery),
        Interface(InterfaceType.TOP, "top", "right", "right_side", "top", perimeter_joinery),
        Interface(InterfaceType.BOTTOM, "bottom", "left", "left_side", "bottom", perimeter_joinery),
        Interface(InterfaceType.BOTTOM, "bottom", "right", "right_side", "bottom", perimeter_joinery),
    ]

    if rows > 1:
        shelf_y = length - back_inset if back_inset else length
        for i in range(rows - 1):
            shelf = PanelSpec(
                name=f"shelf_{i + 1}",
                width_mm=width - 2 * thickness,
                height_mm=shelf_y,
                thickness_mm=thickness,
                role=PanelRole.SHELF,
            )
            panels[f"shelf_{i + 1}"] = shelf

            shelf_position = (i + 1) * cell_height - thickness / 2
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

    if cols > 1:
        partition_y = length - back_inset if back_inset else length
        for j in range(cols - 1):
            partition = PanelSpec(
                name=f"partition_{j + 1}",
                width_mm=partition_y,
                height_mm=height - 2 * thickness,
                thickness_mm=thickness,
                role=PanelRole.PARTITION,
            )
            panels[f"partition_{j + 1}"] = partition

            partition_position = (j + 1) * cell_width - thickness / 2
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "top",
                    "left",
                    f"partition_{j + 1}",
                    "top",
                    partition_joinery,
                    position_along_edge_a_mm=partition_position,
                )
            )
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "bottom",
                    "left",
                    f"partition_{j + 1}",
                    "bottom",
                    partition_joinery,
                    position_along_edge_a_mm=partition_position,
                )
            )

    for i in range(rows - 1):
        for j in range(cols - 1):
            position_on_shelf = (j + 1) * cell_width - thickness / 2
            position_on_partition = (i + 1) * cell_height - thickness / 2
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    f"shelf_{i + 1}",
                    "bottom",
                    f"partition_{j + 1}",
                    "left",
                    internal_joinery,
                    position_along_edge_a_mm=position_on_shelf,
                    position_along_edge_b_mm=position_on_partition,
                )
            )

    if back is not None and back != "none":
        bt = back_thickness if back_thickness else thickness / 3
        back_panel = PanelSpec(
            name="back",
            width_mm=width - 2 * back_inset,
            height_mm=height - 2 * back_inset,
            thickness_mm=bt,
            role=PanelRole.BACK,
        )
        panels["back"] = back_panel
        interfaces.append(Interface(InterfaceType.SIDE_TO_SIDE, "left_side", "right", "back", "left", back))
        interfaces.append(Interface(InterfaceType.SIDE_TO_SIDE, "right_side", "left", "back", "right", back))
        interfaces.append(Interface(InterfaceType.TOP, "top", "top", "back", "top", back))
        interfaces.append(Interface(InterfaceType.BOTTOM, "bottom", "bottom", "back", "bottom", back))

        if back_internal_support:
            back_cell_width = (width - 2 * back_inset) / cols
            back_cell_height = (height - 2 * back_inset) / rows

            for i in range(rows - 1):
                back_shelf_position = (i + 1) * back_cell_height - thickness / 2
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

            for j in range(cols - 1):
                back_partition_position = (j + 1) * back_cell_width - thickness / 2
                interfaces.append(
                    Interface(
                        InterfaceType.INTERNAL,
                        "back",
                        "left",
                        f"partition_{j + 1}",
                        "right",
                        partition_joinery,
                        position_along_edge_a_mm=back_partition_position,
                    )
                )

    return Assembly(members=panels, interfaces=tuple(interfaces))


__all__ = [
    "box",
    "carcass",
    "cubby",
]
