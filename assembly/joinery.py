from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from assembly.core import EdgeName, InterfaceType, RemovalKind
from assembly.panel import Edge, NotchSpec, DadoSpec, PanelSpec

if TYPE_CHECKING:
    from assembly.core import Interface


def _edge_name_to_enum(name: EdgeName) -> Edge:
    return {"top": Edge.TOP, "bottom": Edge.BOTTOM, "left": Edge.LEFT, "right": Edge.RIGHT}[name]


def _dado_orientation(edge: EdgeName) -> Literal["horizontal", "vertical"]:
    return "vertical" if edge in ("left", "right") else "horizontal"


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
        edge_a = _edge_name_to_enum(interface.edge_a)
        edge_b = _edge_name_to_enum(interface.edge_b)
        edge_length = panel_a.edge_length(edge_a)

        notches_a = _finger_joints_to_notches(
            edge=edge_a,
            edge_length=edge_length,
            depth_mm=panel_b.thickness_mm,
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
class HalfLap:
    fitment_mm: float = 0.2
    removal_kind: RemovalKind = RemovalKind.EDGE
    valid_interfaces: frozenset[InterfaceType] = frozenset({InterfaceType.INTERNAL})

    def apply(
        self,
        interface: Interface,
        panel_a: PanelSpec,
        panel_b: PanelSpec,
    ) -> tuple[PanelSpec, PanelSpec]:
        if interface.position_mm is None:
            raise ValueError(
                "HalfLap requires interface.position_mm for INTERNAL interfaces"
            )
        if interface.position_along_edge_b_mm is None:
            raise ValueError(
                "HalfLap requires interface.position_along_edge_b_mm for INTERNAL interfaces"
            )

        edge_a = _edge_name_to_enum(interface.edge_a)
        edge_b = _edge_name_to_enum(interface.edge_b)

        depth_a = panel_a.height_mm / 2 if edge_a in (Edge.BOTTOM, Edge.TOP) else panel_a.width_mm / 2
        depth_b = panel_b.height_mm / 2 if edge_b in (Edge.BOTTOM, Edge.TOP) else panel_b.width_mm / 2

        notch_a = NotchSpec(
            edge=edge_a,
            u_start_mm=interface.position_mm,
            u_len_mm=panel_b.thickness_mm + self.fitment_mm,
            depth_mm=depth_a,
        )

        notch_b = NotchSpec(
            edge=edge_b,
            u_start_mm=interface.position_along_edge_b_mm,
            u_len_mm=panel_a.thickness_mm + self.fitment_mm,
            depth_mm=depth_b,
        )

        return (
            panel_a.with_notches((notch_a,)),
            panel_b.with_notches((notch_b,)),
        )


@dataclass(frozen=True)
class Captured:
    dado_depth_mm: float | None = None
    dado_width_mm: float | None = None
    inset_mm: float = 0.0
    fitment_mm: float = 0.2
    receiving: Literal["a", "b"] = "a"
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
        if self.receiving == "b" and interface.type == InterfaceType.INTERNAL:
            raise ValueError(
                f"Captured(receiving='b') is not valid for INTERNAL interfaces. "
                f"INTERNAL interface position_mm ({interface.position_mm}) describes "
                f"panel_b's location along panel_a's edge, not a valid dado position on panel_b. "
                f"Use receiving='a' (default) for shelf/partition to side panel joints."
            )

        position = interface.position_mm if interface.position_mm is not None else self.inset_mm

        if self.receiving == "a":
            edge = interface.edge_a
            depth = self.dado_depth_mm if self.dado_depth_mm else panel_b.thickness_mm / 2
            width = self.dado_width_mm if self.dado_width_mm else panel_b.thickness_mm
            dado = DadoSpec(
                position_from_edge_mm=position,
                width_mm=width + self.fitment_mm,
                depth_mm=depth,
                edge=edge,
                orientation=_dado_orientation(edge),
            )
            return (panel_a.with_dados((dado,)), panel_b)
        else:
            edge = interface.edge_b
            depth = self.dado_depth_mm if self.dado_depth_mm else panel_a.thickness_mm / 2
            width = self.dado_width_mm if self.dado_width_mm else panel_a.thickness_mm
            dado = DadoSpec(
                position_from_edge_mm=position,
                width_mm=width + self.fitment_mm,
                depth_mm=depth,
                edge=edge,
                orientation=_dado_orientation(edge),
            )
            return (panel_a, panel_b.with_dados((dado,)))


__all__ = [
    "JoineryStrategy",
    "Butt",
    "Finger",
    "HalfLap",
    "Captured",
]
