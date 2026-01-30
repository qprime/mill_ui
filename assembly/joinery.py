from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from assembly.core import InterfaceType, RemovalKind
from assembly.panel import Edge, NotchSpec, DadoSpec, PanelSpec

if TYPE_CHECKING:
    from assembly.core import Interface


@runtime_checkable
class JoineryStrategy(Protocol):
    @property
    def removal_kind(self) -> RemovalKind: ...

    @property
    def valid_interfaces(self) -> frozenset[InterfaceType]: ...

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]: ...


def _finger_joints_to_notches(
    edge: Edge,
    edge_length: float,
    depth_mm: float,
    phase: int,
    width_mm: float | None = None,
    count: int | None = None,
    clearance_mm: float = 0.12,
) -> list[NotchSpec]:
    if width_mm is None and count is None:
        raise ValueError("Specify at least one of width_mm or count")

    if count is not None:
        n = count
    else:
        n = round(edge_length / width_mm)

    n = max(3, n)
    if n % 2 == 0:
        n += 1

    finger_width = edge_length / n

    notches: list[NotchSpec] = []
    for i in range(n):
        is_notch = (i % 2 == 1) == (phase == 0)
        if is_notch:
            boundary_expansion = clearance_mm / 4
            u_start = i * finger_width - boundary_expansion
            u_end = (i + 1) * finger_width + boundary_expansion
            u_start = max(0.0, u_start)
            u_end = min(edge_length, u_end)
            if u_end - u_start <= 1e-9:
                continue
            notch = NotchSpec(
                edge=edge,
                u_start_mm=u_start,
                u_len_mm=u_end - u_start,
                depth_mm=depth_mm,
            )
            notches.append(notch)

    return notches


def _get_mating_edges(
    interface_type: InterfaceType,
    role_a: str,
    role_b: str,
) -> tuple[Edge, Edge]:
    if interface_type == InterfaceType.SIDE_TO_SIDE:
        corner_map = {
            ("front", "left"): (Edge.LEFT, Edge.RIGHT),
            ("front", "right"): (Edge.RIGHT, Edge.LEFT),
            ("back", "left"): (Edge.RIGHT, Edge.LEFT),
            ("back", "right"): (Edge.LEFT, Edge.RIGHT),
            ("left", "front"): (Edge.RIGHT, Edge.LEFT),
            ("left", "back"): (Edge.LEFT, Edge.RIGHT),
            ("right", "front"): (Edge.LEFT, Edge.RIGHT),
            ("right", "back"): (Edge.RIGHT, Edge.LEFT),
        }
        return corner_map.get((role_a, role_b), (Edge.RIGHT, Edge.LEFT))
    elif interface_type == InterfaceType.TOP:
        if role_b == "top":
            return (Edge.TOP, Edge.BOTTOM)
        return (Edge.TOP, Edge.BOTTOM)
    elif interface_type == InterfaceType.BOTTOM:
        if role_b == "bottom":
            return (Edge.BOTTOM, Edge.TOP)
        return (Edge.BOTTOM, Edge.TOP)
    else:
        return (Edge.TOP, Edge.BOTTOM)


@dataclass(frozen=True)
class Butt:
    removal_kind: RemovalKind = RemovalKind.NONE
    valid_interfaces: frozenset[InterfaceType] = frozenset(InterfaceType)

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        return panel_a, panel_b


@dataclass(frozen=True)
class Finger:
    width_mm: float | None = 12.0
    count: int | None = None
    clearance_mm: float = 0.12
    removal_kind: RemovalKind = RemovalKind.EDGE
    valid_interfaces: frozenset[InterfaceType] = frozenset({
        InterfaceType.SIDE_TO_SIDE,
        InterfaceType.TOP,
        InterfaceType.BOTTOM,
    })

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        role_a = panel_a.name.lower().replace("_side", "").replace("_", "")
        role_b = panel_b.name.lower().replace("_side", "").replace("_", "")

        edge_a, edge_b = _get_mating_edges(interface.type, role_a, role_b)
        edge_length = panel_a.edge_length(edge_a)
        depth = panel_b.thickness_mm

        notches_a = _finger_joints_to_notches(
            edge=edge_a,
            edge_length=edge_length,
            depth_mm=depth,
            phase=0,
            width_mm=self.width_mm,
            count=self.count,
            clearance_mm=self.clearance_mm,
        )

        notches_b = _finger_joints_to_notches(
            edge=edge_b,
            edge_length=edge_length,
            depth_mm=panel_a.thickness_mm,
            phase=1,
            width_mm=self.width_mm,
            count=self.count,
            clearance_mm=self.clearance_mm,
        )

        return (
            panel_a.with_notches(tuple(notches_a)),
            panel_b.with_notches(tuple(notches_b)),
        )


@dataclass(frozen=True)
class Step:
    depth_ratio: float = 0.5
    clearance_mm: float = 0.12
    removal_kind: RemovalKind = RemovalKind.EDGE
    valid_interfaces: frozenset[InterfaceType] = frozenset({
        InterfaceType.SIDE_TO_SIDE,
        InterfaceType.TOP,
        InterfaceType.BOTTOM,
    })

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        role_a = panel_a.name.lower().replace("_side", "").replace("_", "")
        role_b = panel_b.name.lower().replace("_side", "").replace("_", "")

        edge_a, edge_b = _get_mating_edges(interface.type, role_a, role_b)
        edge_length = panel_a.edge_length(edge_a)

        depth_a = panel_b.thickness_mm * self.depth_ratio
        depth_b = panel_a.thickness_mm * self.depth_ratio

        notch_a = NotchSpec(
            edge=edge_a,
            u_start_mm=0.0,
            u_len_mm=edge_length,
            depth_mm=depth_a,
        )

        notch_b = NotchSpec(
            edge=edge_b,
            u_start_mm=0.0,
            u_len_mm=edge_length,
            depth_mm=depth_b,
        )

        return (
            panel_a.with_notches((notch_a,)),
            panel_b.with_notches((notch_b,)),
        )


@dataclass(frozen=True)
class Rabbet:
    depth_mm: float | None = None
    receiving: Literal["a", "b"] = "a"
    clearance_mm: float = 0.12
    removal_kind: RemovalKind = RemovalKind.EDGE
    valid_interfaces: frozenset[InterfaceType] = frozenset({
        InterfaceType.TOP,
        InterfaceType.BOTTOM,
        InterfaceType.SIDE_TO_SIDE,
    })

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        role_a = panel_a.name.lower().replace("_side", "").replace("_", "")
        role_b = panel_b.name.lower().replace("_side", "").replace("_", "")

        edge_a, edge_b = _get_mating_edges(interface.type, role_a, role_b)

        if self.receiving == "a":
            edge_length = panel_a.edge_length(edge_a)
            depth = self.depth_mm if self.depth_mm else panel_b.thickness_mm
            notch = NotchSpec(
                edge=edge_a,
                u_start_mm=0.0,
                u_len_mm=edge_length,
                depth_mm=depth + self.clearance_mm,
            )
            return (panel_a.with_notches((notch,)), panel_b)
        else:
            edge_length = panel_b.edge_length(edge_b)
            depth = self.depth_mm if self.depth_mm else panel_a.thickness_mm
            notch = NotchSpec(
                edge=edge_b,
                u_start_mm=0.0,
                u_len_mm=edge_length,
                depth_mm=depth + self.clearance_mm,
            )
            return (panel_a, panel_b.with_notches((notch,)))


@dataclass(frozen=True)
class HalfLap:
    fitment_mm: float = 0.2
    removal_kind: RemovalKind = RemovalKind.FACE
    valid_interfaces: frozenset[InterfaceType] = frozenset({InterfaceType.INTERNAL})

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        dado_a = DadoSpec(
            position_from_edge_mm=panel_a.height_mm / 2 - panel_b.thickness_mm / 2,
            width_mm=panel_b.thickness_mm + self.fitment_mm,
            depth_mm=panel_a.thickness_mm / 2,
            edge="bottom",
            orientation="horizontal",
        )

        dado_b = DadoSpec(
            position_from_edge_mm=panel_b.height_mm / 2 - panel_a.thickness_mm / 2,
            width_mm=panel_a.thickness_mm + self.fitment_mm,
            depth_mm=panel_b.thickness_mm / 2,
            edge="bottom",
            orientation="horizontal",
        )

        return (
            panel_a.with_dados((dado_a,)),
            panel_b.with_dados((dado_b,)),
        )


@dataclass(frozen=True)
class Captured:
    dado_depth_mm: float | None = None
    dado_width_mm: float | None = None
    inset_mm: float = 0.0
    fitment_mm: float = 0.2
    removal_kind: RemovalKind = RemovalKind.FACE
    valid_interfaces: frozenset[InterfaceType] = frozenset({
        InterfaceType.TOP,
        InterfaceType.BOTTOM,
        InterfaceType.SIDE_TO_SIDE,
        InterfaceType.INTERNAL,
    })

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        if interface.type in (InterfaceType.TOP, InterfaceType.BOTTOM):
            cap_panel = panel_b if panel_b.name.lower() in ("top", "bottom") else panel_a
            side_panel = panel_a if cap_panel == panel_b else panel_b
            edge: Literal["top", "bottom", "left", "right"] = "bottom" if interface.type == InterfaceType.BOTTOM else "top"
            position = self.inset_mm
        else:
            cap_panel = panel_b if "back" in panel_b.name.lower() or "shelf" in panel_b.name.lower() or "partition" in panel_b.name.lower() else panel_a
            side_panel = panel_a if cap_panel == panel_b else panel_b
            if "back" in cap_panel.name.lower():
                edge = "right"
                position = self.inset_mm
            else:
                edge = "bottom"
                position = interface.position_mm if interface.position_mm is not None else self.inset_mm

        depth = self.dado_depth_mm if self.dado_depth_mm else cap_panel.thickness_mm / 2
        width = self.dado_width_mm if self.dado_width_mm else cap_panel.thickness_mm

        if interface.type in (InterfaceType.TOP, InterfaceType.BOTTOM):
            orientation: Literal["horizontal", "vertical"] = "horizontal"
        elif "back" in cap_panel.name.lower():
            orientation = "vertical"
        else:
            orientation = "horizontal"

        dado = DadoSpec(
            position_from_edge_mm=position,
            width_mm=width + self.fitment_mm,
            depth_mm=depth,
            edge=edge,
            orientation=orientation,
        )

        if side_panel == panel_a:
            return (panel_a.with_dados((dado,)), panel_b)
        else:
            return (panel_a, panel_b.with_dados((dado,)))


@dataclass(frozen=True)
class Dado:
    depth_mm: float | None = None
    inset_mm: float = 0.0
    fitment_mm: float = 0.2
    receiving: Literal["a", "b"] = "a"
    removal_kind: RemovalKind = RemovalKind.FACE
    valid_interfaces: frozenset[InterfaceType] = frozenset({
        InterfaceType.TOP,
        InterfaceType.BOTTOM,
        InterfaceType.INTERNAL,
    })

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        if self.receiving == "a":
            depth = self.depth_mm if self.depth_mm else panel_b.thickness_mm / 2
            dado = DadoSpec(
                position_from_edge_mm=self.inset_mm,
                width_mm=panel_b.thickness_mm + self.fitment_mm,
                depth_mm=depth,
                edge="bottom",
                orientation="horizontal",
            )
            return (panel_a.with_dados((dado,)), panel_b)
        else:
            depth = self.depth_mm if self.depth_mm else panel_a.thickness_mm / 2
            dado = DadoSpec(
                position_from_edge_mm=self.inset_mm,
                width_mm=panel_a.thickness_mm + self.fitment_mm,
                depth_mm=depth,
                edge="bottom",
                orientation="horizontal",
            )
            return (panel_a, panel_b.with_dados((dado,)))


__all__ = [
    "JoineryStrategy",
    "Butt",
    "Finger",
    "Step",
    "Rabbet",
    "HalfLap",
    "Captured",
    "Dado",
]
