from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal, cast

from assembly.core import Assembly, EdgeName, Interface, InterfaceType, MemberSpec, RemovalKind
from assembly.cubby import cubby
from assembly.joinery import Butt, Captured, Finger, JoineryStrategy
from assembly.panel import Edge, NotchSpec, PanelRole, PanelSpec


@dataclass(frozen=True)
class _CapFit:
    edge_inset_mm: float = 0.0
    wall_extension_mm: float = 0.0


def _cap_fit(joinery: JoineryStrategy | Literal["none"] | None, thickness: float) -> _CapFit:
    if joinery is None or joinery == "none" or isinstance(joinery, Finger):
        return _CapFit()
    if isinstance(joinery, Captured):
        depth = joinery.groove_depth_mm(thickness)
        if not 0 < depth <= thickness:
            raise ValueError(f"Assembly cap groove depth must be positive and at most {thickness}mm, got {depth}mm")
        if joinery.receiving == "a":
            return _CapFit(edge_inset_mm=thickness - depth)
        if joinery.inset_mm != 0:
            raise ValueError("Caps with receiving='b' and nonzero inset require explicit wall placement")
        return _CapFit(wall_extension_mm=thickness - depth)
    return _CapFit(edge_inset_mm=thickness)


def _carcass_cap_fit(
    joinery: JoineryStrategy | Literal["none"] | None,
    thickness: float,
    cap_style: Literal["between_sides", "over_sides"],
) -> _CapFit:
    fit = _cap_fit(joinery, thickness)
    if joinery is None or joinery == "none" or isinstance(joinery, Finger):
        return fit
    if isinstance(joinery, Captured):
        expected = "between_sides" if joinery.receiving == "a" else "over_sides"
        if cap_style != expected:
            raise ValueError(f"Carcass cap_style must be {expected!r} for Captured(receiving={joinery.receiving!r})")
        return fit
    return fit if cap_style == "between_sides" else _CapFit(wall_extension_mm=thickness)


def _carcass_inside_offset(joinery: JoineryStrategy | Literal["none"] | None, fit: _CapFit, thickness: float) -> float:
    if joinery is None or joinery == "none":
        return 0.0
    inset = joinery.inset_mm if isinstance(joinery, Captured) and joinery.receiving == "a" else 0.0
    return thickness - fit.wall_extension_mm + inset


@dataclass(frozen=True)
class _CarcassBackFit:
    panel: PanelSpec
    joinery: JoineryStrategy
    x_mm: float
    z_mm: float
    front_mm: float


def _carcass_back_fit(
    joint: JoineryStrategy | Literal["none"] | None,
    inside_x: tuple[float, float],
    inside_z: tuple[float, float],
    *,
    length: float,
    thickness: float,
    back_thickness: float | None,
    setback: float,
    caps: tuple[bool, bool],
) -> _CarcassBackFit | None:
    if not math.isfinite(setback) or setback < 0:
        raise ValueError("Carcass back setback must be finite and nonnegative")
    if joint is None or joint == "none":
        return None
    stock = thickness if back_thickness is None else back_thickness
    if not math.isfinite(stock) or stock <= 0:
        raise ValueError("Carcass back thickness must be finite and positive")
    depth = 0.0
    if isinstance(joint, Captured) and joint.receiving == "a":
        depth = joint.groove_depth_mm(stock)
        if not 0 < depth <= thickness:
            raise ValueError(f"Carcass back groove depth must fit {thickness}mm receiving stock, got {depth}mm")
        if joint.inset_mm not in (0, setback):
            raise ValueError("Carcass back joint inset conflicts with back_inset rear-face setback")
        if joint.dado_width_mm is not None and not math.isclose(joint.dado_width_mm, stock, rel_tol=0, abs_tol=1e-9):
            raise ValueError("Carcass back groove width must match the back thickness")
        joint = replace(joint, dado_width_mm=stock)
    elif not isinstance(joint, Butt):
        raise ValueError("Carcass back fit requires Butt or Captured(receiving='a')")
    front = length - setback - stock
    if front <= 0:
        raise ValueError("Carcass back setback and thickness leave no interior depth")
    x = inside_x[0] - depth
    z = inside_z[0] - (depth if caps[0] else 0)
    panel = PanelSpec(
        "back",
        inside_x[1] + depth - x,
        inside_z[1] + (depth if caps[1] else 0) - z,
        stock,
        role=PanelRole.BACK,
    )
    if min(panel.width_mm, panel.height_mm) <= 0:
        raise ValueError("Carcass back must leave positive panel spans")
    return _CarcassBackFit(panel, joint, x, z, front)


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
    top_fit = _cap_fit(top, thickness)
    bottom_fit = _cap_fit(bottom, thickness)
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
    if any(not math.isfinite(v) or v <= 0 for v in (width, length, height, thickness)):
        raise ValueError("Carcass dimensions must be finite and positive")
    if width <= 2 * thickness or fixed_shelves < 0:
        raise ValueError("Carcass must have positive interior width and nonnegative shelf count")
    if side_joinery is None:
        side_joinery = Butt()
    if shelf_joinery is None:
        shelf_joinery = Captured()
    default_cap_joinery = perimeter_joinery if perimeter_joinery is not None else Butt()
    if top is None:
        top = default_cap_joinery
    if bottom is None:
        bottom = default_cap_joinery

    top_fit = _carcass_cap_fit(top, thickness, cap_style)
    bottom_fit = _carcass_cap_fit(bottom, thickness, cap_style)
    side_height = height - top_fit.wall_extension_mm - bottom_fit.wall_extension_mm
    if side_height <= 0:
        raise ValueError(f"Carcass caps leave no positive side height: {side_height}mm")
    if width <= 2 * max(top_fit.edge_inset_mm, bottom_fit.edge_inset_mm):
        raise ValueError("Carcass dimensions leave no positive cap span")
    cap_width = width - 2 * thickness if cap_style == "between_sides" else width
    has_bottom, has_top = bottom is not None and bottom != "none", top is not None and top != "none"
    kick_height = toe_kick_height if toe_kick_height is not None else 0.0
    kick_setback = toe_kick_setback if toe_kick_setback is not None else (50.0 if kick_height > 0 else 0.0)
    if not math.isfinite(kick_height) or not 0 <= kick_height < side_height:
        raise ValueError("Carcass toe kick height must be finite, nonnegative and below the side height")
    if not math.isfinite(kick_setback) or not 0 <= kick_setback < length or (kick_height > 0 and kick_setback == 0):
        raise ValueError("Carcass toe kick setback must leave positive depth behind the cutout")
    if kick_height > 0 and bottom_fit.wall_extension_mm > 0:
        raise ValueError("Carcass raised toe-kick bottom requires a between-side cap")
    if kick_height > 0 and has_bottom and not isinstance(bottom, (Butt, Captured)):
        raise ValueError("Carcass toe-kick bottom requires Butt or Captured(receiving='a')")
    bottom_offset = _carcass_inside_offset(bottom, bottom_fit, thickness)
    if kick_height > 0 and has_bottom:
        bottom_offset = kick_height + thickness
    top_offset = _carcass_inside_offset(top, top_fit, thickness)
    if bottom_offset >= side_height - top_offset:
        raise ValueError("Carcass caps and toe kick leave no positive interior height")
    side_z = bottom_fit.wall_extension_mm
    back_fit = _carcass_back_fit(
        back,
        (thickness, width - thickness),
        (side_z + bottom_offset, side_z + side_height - top_offset),
        length=length,
        thickness=thickness,
        back_thickness=back_thickness,
        setback=back_inset,
        caps=(has_bottom, has_top),
    )

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
            width_mm=width - 2 * top_fit.edge_inset_mm,
            height_mm=length,
            thickness_mm=thickness,
            role=PanelRole.TOP,
        )
        panels["top"] = top_panel
        interfaces.append(Interface(InterfaceType.TOP, "left_side", "top", "top", "left", top))
        interfaces.append(Interface(InterfaceType.TOP, "right_side", "top", "top", "right", top))

    if kick_height > 0:
        kick_notch = NotchSpec(
            edge=Edge.BOTTOM,
            u_start_mm=0.0,
            u_len_mm=kick_setback,
            depth_mm=kick_height,
        )
        panels["left_side"] = cast(PanelSpec, panels["left_side"]).with_notches((kick_notch,))
        panels["right_side"] = cast(PanelSpec, panels["right_side"]).with_notches(
            (replace(kick_notch, u_start_mm=length - kick_setback),)
        )

    if bottom is not None and bottom != "none":
        bottom_len = length - kick_setback if kick_height > 0 else length
        bottom_panel = PanelSpec(
            name="bottom",
            width_mm=width - 2 * bottom_fit.edge_inset_mm,
            height_mm=bottom_len,
            thickness_mm=thickness,
            role=PanelRole.BOTTOM,
        )
        panels["bottom"] = bottom_panel
        bottom_dado_position = kick_height if kick_height > 0 else None
        interfaces.append(
            Interface(
                InterfaceType.BOTTOM,
                "left_side",
                "bottom",
                "bottom",
                "left",
                bottom,
                position_along_edge_a_mm=bottom_dado_position,
                contact_span_mm=(length - bottom_len, length),
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
                contact_span_mm=(0, bottom_len),
            )
        )

    if kick_height > 0 and toe_kick_cover:
        kick_cover_width = cap_width if toe_kick_style == "between_sides" else width
        kick_cover = PanelSpec(
            name="toe_kick_cover",
            width_mm=kick_cover_width,
            height_mm=kick_height,
            thickness_mm=thickness,
            role=PanelRole.FRONT,
        )
        panels["toe_kick_cover"] = kick_cover

    if back_fit is not None:
        panels["back"] = back_fit.panel
        side_edges: tuple[tuple[str, EdgeName, EdgeName], ...] = (
            ("left_side", "right", "left"),
            ("right_side", "left", "right"),
        )
        for name, edge, back_edge in side_edges:
            interfaces.append(
                Interface(
                    InterfaceType.SIDE_TO_SIDE,
                    name,
                    edge,
                    "back",
                    back_edge,
                    back_fit.joinery,
                    position_along_edge_a_mm=back_inset,
                    contact_span_mm=(back_fit.z_mm - side_z, back_fit.z_mm + back_fit.panel.height_mm - side_z),
                )
            )
        if back_fit.joinery.removal_kind == RemovalKind.FACE:
            cap_edges: tuple[tuple[EdgeName, InterfaceType, EdgeName, _CapFit], ...] = (
                ("top", InterfaceType.TOP, "bottom", top_fit),
                ("bottom", InterfaceType.BOTTOM, "top", bottom_fit),
            )
            for name, kind, edge, cap_fit in cap_edges:
                if name in panels:
                    cap = cast(PanelSpec, panels[name])
                    interfaces.append(
                        Interface(
                            kind,
                            name,
                            edge,
                            "back",
                            name,
                            back_fit.joinery,
                            position_along_edge_a_mm=back_inset,
                            contact_span_mm=(
                                max(0, back_fit.x_mm - cap_fit.edge_inset_mm),
                                min(cap.width_mm, back_fit.x_mm + back_fit.panel.width_mm - cap_fit.edge_inset_mm),
                            ),
                        )
                    )

    if fixed_shelves > 0:
        if isinstance(shelf_joinery, Captured) and shelf_joinery.receiving != "a":
            raise ValueError("Carcass shelves require Captured(receiving='a')")
        shelf_x = width - 2 * _cap_fit(shelf_joinery, thickness).edge_inset_mm
        shelf_y = back_fit.front_mm if back_fit is not None else length
        if shelf_back_support and back_fit is not None and isinstance(shelf_joinery, Captured):
            engagement = shelf_joinery.groove_depth_mm(thickness)
            if not 0 < engagement <= back_fit.panel.thickness_mm:
                raise ValueError("Carcass shelf support groove depth must fit the back stock")
            shelf_y += engagement
        interior_height = side_height - top_offset - bottom_offset
        shelf_spacing = (interior_height - fixed_shelves * thickness) / (fixed_shelves + 1)
        if shelf_spacing <= 0 or min(shelf_x, shelf_y) <= 0:
            raise ValueError("Carcass shelves must leave positive panel spans and clear openings")

        for i in range(fixed_shelves):
            shelf = PanelSpec(
                name=f"shelf_{i + 1}",
                width_mm=shelf_x,
                height_mm=shelf_y,
                thickness_mm=thickness,
                role=PanelRole.SHELF,
            )
            panels[f"shelf_{i + 1}"] = shelf
            shelf_position = bottom_offset + (i + 1) * shelf_spacing + i * thickness
            interfaces.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "left_side",
                    "bottom",
                    f"shelf_{i + 1}",
                    "left",
                    shelf_joinery,
                    position_along_edge_a_mm=shelf_position,
                    contact_span_mm=(0, shelf_y),
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
                    contact_span_mm=(length - shelf_y, length),
                )
            )
            if shelf_back_support and back_fit is not None:
                back_shelf_position = side_z + shelf_position - back_fit.z_mm
                interfaces.append(
                    Interface(
                        InterfaceType.INTERNAL,
                        "back",
                        "bottom",
                        f"shelf_{i + 1}",
                        "top",
                        shelf_joinery,
                        position_along_edge_a_mm=back_shelf_position,
                        contact_span_mm=(
                            max(0, (width - shelf_x) / 2 - back_fit.x_mm),
                            min(back_fit.panel.width_mm, (width + shelf_x) / 2 - back_fit.x_mm),
                        ),
                    )
                )

    return Assembly(members=panels, interfaces=tuple(interfaces))


__all__ = [
    "box",
    "carcass",
    "cubby",
]
