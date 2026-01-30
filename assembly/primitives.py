from __future__ import annotations

from typing import Literal

from assembly.core import Assembly, Interface, InterfaceType
from assembly.joinery import Butt, Finger, Captured, HalfLap, JoineryStrategy
from assembly.panel import PanelRole, PanelSpec


def box(
    width: float,
    depth: float,
    height: float,
    thickness: float,
    side_joinery: JoineryStrategy = Finger(),
    top: JoineryStrategy | Literal["none"] | None = None,
    bottom: JoineryStrategy | Literal["none"] | None = Captured(),
) -> Assembly:
    front = PanelSpec(
        name="front",
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.FRONT,
    )
    back = PanelSpec(
        name="back",
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.BACK,
    )
    left = PanelSpec(
        name="left_side",
        width_mm=depth - 2 * thickness,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=depth - 2 * thickness,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.RIGHT,
    )

    panels: dict[str, PanelSpec] = {
        "front": front,
        "back": back,
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
        bottom_width = width - 2 * thickness
        bottom_depth = depth - 2 * thickness
        bottom_panel = PanelSpec(
            name="bottom",
            width_mm=bottom_width,
            height_mm=bottom_depth,
            thickness_mm=thickness,
            role=PanelRole.BOTTOM,
        )
        panels["bottom"] = bottom_panel

        interfaces.append(Interface(InterfaceType.BOTTOM, "front", "bottom", "bottom", "top", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "back", "bottom", "bottom", "top", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "right_side", "bottom", "bottom", "right", bottom))

    if top is not None and top != "none":
        top_width = width - 2 * thickness
        top_depth = depth - 2 * thickness
        top_panel = PanelSpec(
            name="top",
            width_mm=top_width,
            height_mm=top_depth,
            thickness_mm=thickness,
            role=PanelRole.TOP,
        )
        panels["top"] = top_panel

        interfaces.append(Interface(InterfaceType.TOP, "front", "top", "top", "top", top))
        interfaces.append(Interface(InterfaceType.TOP, "back", "top", "top", "top", top))
        interfaces.append(Interface(InterfaceType.TOP, "left_side", "top", "top", "left", top))
        interfaces.append(Interface(InterfaceType.TOP, "right_side", "top", "top", "right", top))

    return Assembly(panels=panels, interfaces=tuple(interfaces))


def carcass(
    width: float,
    depth: float,
    height: float,
    thickness: float,
    side_joinery: JoineryStrategy = Butt(),
    cap_style: Literal["between_sides", "over_sides"] = "between_sides",
    top: JoineryStrategy | Literal["none"] | None = Butt(),
    bottom: JoineryStrategy | Literal["none"] | None = Butt(),
    back: JoineryStrategy | Literal["none"] | None = None,
    back_thickness: float | None = None,
    back_inset: float = 0.0,
    fixed_shelves: int = 0,
    shelf_joinery: JoineryStrategy = Captured(),
    shelf_back_support: bool = False,
    vertical_partitions: int = 0,
    partition_joinery: JoineryStrategy = Captured(),
) -> Assembly:
    if cap_style == "between_sides":
        side_height = height
        cap_width = width - 2 * thickness
    else:
        side_height = height - 2 * thickness
        cap_width = width

    left = PanelSpec(
        name="left_side",
        width_mm=depth,
        height_mm=side_height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=depth,
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
            height_mm=depth,
            thickness_mm=thickness,
            role=PanelRole.TOP,
        )
        panels["top"] = top_panel
        interfaces.append(Interface(InterfaceType.TOP, "left_side", "top", "top", "left", top))
        interfaces.append(Interface(InterfaceType.TOP, "right_side", "top", "top", "right", top))

    if bottom is not None and bottom != "none":
        bottom_panel = PanelSpec(
            name="bottom",
            width_mm=cap_width,
            height_mm=depth,
            thickness_mm=thickness,
            role=PanelRole.BOTTOM,
        )
        panels["bottom"] = bottom_panel
        interfaces.append(Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", bottom))
        interfaces.append(Interface(InterfaceType.BOTTOM, "right_side", "bottom", "bottom", "right", bottom))

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

    if fixed_shelves > 0:
        shelf_width = cap_width
        shelf_depth = depth - back_inset if back_inset else depth
        interior_height = side_height
        if top is not None and top != "none":
            interior_height -= thickness
        if bottom is not None and bottom != "none":
            interior_height -= thickness
        shelf_spacing = interior_height / (fixed_shelves + 1)
        bottom_offset = thickness if (bottom is not None and bottom != "none") else 0.0

        for i in range(fixed_shelves):
            shelf = PanelSpec(
                name=f"shelf_{i+1}",
                width_mm=shelf_width,
                height_mm=shelf_depth,
                thickness_mm=thickness,
                role=PanelRole.SHELF,
            )
            panels[f"shelf_{i+1}"] = shelf
            shelf_position = bottom_offset + (i + 1) * shelf_spacing - thickness / 2
            interfaces.append(
                Interface(InterfaceType.INTERNAL, "left_side", "right", f"shelf_{i+1}", "left", shelf_joinery, position_mm=shelf_position)
            )
            interfaces.append(
                Interface(InterfaceType.INTERNAL, "right_side", "left", f"shelf_{i+1}", "right", shelf_joinery, position_mm=shelf_position)
            )
            if shelf_back_support and "back" in panels:
                interfaces.append(
                    Interface(InterfaceType.INTERNAL, "back", "bottom", f"shelf_{i+1}", "top", shelf_joinery, position_mm=shelf_position)
                )

    if vertical_partitions > 0:
        partition_height = side_height - 2 * thickness if cap_style == "between_sides" else side_height
        partition_depth = depth - back_inset if back_inset else depth
        for i in range(vertical_partitions):
            partition = PanelSpec(
                name=f"partition_{i+1}",
                width_mm=partition_depth,
                height_mm=partition_height,
                thickness_mm=thickness,
                role=PanelRole.PARTITION,
            )
            panels[f"partition_{i+1}"] = partition
            if "top" in panels:
                interfaces.append(
                    Interface(InterfaceType.INTERNAL, "top", "bottom", f"partition_{i+1}", "top", partition_joinery)
                )
            if "bottom" in panels:
                interfaces.append(
                    Interface(InterfaceType.INTERNAL, "bottom", "top", f"partition_{i+1}", "bottom", partition_joinery)
                )

    return Assembly(panels=panels, interfaces=tuple(interfaces))


def cubby(
    width: float,
    depth: float,
    height: float,
    thickness: float,
    rows: int,
    cols: int,
    perimeter_joinery: JoineryStrategy = Finger(),
    shelf_joinery: JoineryStrategy = Captured(),
    partition_joinery: JoineryStrategy = Captured(),
    internal_joinery: JoineryStrategy = HalfLap(),
    back: JoineryStrategy | Literal["none"] | None = None,
    back_thickness: float | None = None,
    back_inset: float = 0.0,
    back_internal_support: bool = True,
) -> Assembly:
    cell_width = (width - 2 * thickness) / cols
    cell_height = (height - 2 * thickness) / rows

    top = PanelSpec(
        name="top",
        width_mm=width - 2 * thickness,
        height_mm=depth,
        thickness_mm=thickness,
        role=PanelRole.TOP,
    )
    bottom = PanelSpec(
        name="bottom",
        width_mm=width - 2 * thickness,
        height_mm=depth,
        thickness_mm=thickness,
        role=PanelRole.BOTTOM,
    )
    left = PanelSpec(
        name="left_side",
        width_mm=depth,
        height_mm=height,
        thickness_mm=thickness,
        role=PanelRole.LEFT,
    )
    right = PanelSpec(
        name="right_side",
        width_mm=depth,
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
        shelf_depth = depth - back_inset if back_inset else depth
        for i in range(rows - 1):
            shelf = PanelSpec(
                name=f"shelf_{i+1}",
                width_mm=width - 2 * thickness,
                height_mm=shelf_depth,
                thickness_mm=thickness,
                role=PanelRole.SHELF,
            )
            panels[f"shelf_{i+1}"] = shelf

            shelf_position = (i + 1) * cell_height - thickness / 2
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "left_side",
                    "bottom",
                    f"shelf_{i+1}",
                    "left",
                    shelf_joinery,
                    position_mm=shelf_position,
                )
            )
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "right_side",
                    "bottom",
                    f"shelf_{i+1}",
                    "right",
                    shelf_joinery,
                    position_mm=shelf_position,
                )
            )

    if cols > 1:
        partition_depth = depth - back_inset if back_inset else depth
        for j in range(cols - 1):
            partition = PanelSpec(
                name=f"partition_{j+1}",
                width_mm=partition_depth,
                height_mm=height - 2 * thickness,
                thickness_mm=thickness,
                role=PanelRole.PARTITION,
            )
            panels[f"partition_{j+1}"] = partition

            partition_position = (j + 1) * cell_width - thickness / 2
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "top",
                    "left",
                    f"partition_{j+1}",
                    "top",
                    partition_joinery,
                    position_mm=partition_position,
                )
            )
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "bottom",
                    "left",
                    f"partition_{j+1}",
                    "bottom",
                    partition_joinery,
                    position_mm=partition_position,
                )
            )

    for i in range(rows - 1):
        for j in range(cols - 1):
            position_on_shelf = (j + 1) * cell_width - thickness / 2
            position_on_partition = (i + 1) * cell_height - thickness / 2
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    f"shelf_{i+1}",
                    "bottom",
                    f"partition_{j+1}",
                    "left",
                    internal_joinery,
                    position_mm=position_on_shelf,
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
            for i in range(rows - 1):
                shelf_position = (i + 1) * cell_height - thickness / 2
                interfaces.append(
                    Interface(
                        InterfaceType.INTERNAL,
                        "back",
                        "bottom",
                        f"shelf_{i+1}",
                        "top",
                        shelf_joinery,
                        position_mm=shelf_position,
                    )
                )

            for j in range(cols - 1):
                partition_position = (j + 1) * cell_width - thickness / 2
                interfaces.append(
                    Interface(
                        InterfaceType.INTERNAL,
                        "back",
                        "left",
                        f"partition_{j+1}",
                        "right",
                        partition_joinery,
                        position_mm=partition_position,
                    )
                )

    return Assembly(panels=panels, interfaces=tuple(interfaces))


__all__ = [
    "box",
    "carcass",
    "cubby",
]
