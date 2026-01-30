from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from assembly.joinery import JoineryStrategy
    from assembly.panel import PanelSpec

EdgeName = Literal["top", "bottom", "left", "right"]


class InterfaceType(Enum):
    SIDE_TO_SIDE = auto()
    TOP = auto()
    BOTTOM = auto()
    INTERNAL = auto()


class RemovalKind(Enum):
    EDGE = auto()
    FACE = auto()
    NONE = auto()


@dataclass(frozen=True)
class Interface:
    type: InterfaceType
    panel_a: str
    edge_a: EdgeName
    panel_b: str
    edge_b: EdgeName
    joinery: JoineryStrategy
    position_mm: float | None = None
    position_along_edge_b_mm: float | None = None

    def validate(self) -> None:
        if self.type not in self.joinery.valid_interfaces:
            raise ValueError(
                f"{type(self.joinery).__name__} not valid for {self.type.name}"
            )


@dataclass(frozen=True)
class Assembly:
    panels: dict[str, PanelSpec]
    interfaces: tuple[Interface, ...]

    def validate(self) -> None:
        for interface in self.interfaces:
            interface.validate()
            if interface.panel_a not in self.panels:
                raise ValueError(f"Unknown panel: {interface.panel_a}")
            if interface.panel_b not in self.panels:
                raise ValueError(f"Unknown panel: {interface.panel_b}")

    def resolve(self) -> list[PanelSpec]:
        from assembly.panel import PanelSpec as PS

        self.validate()

        panel_notches: dict[str, list] = {name: [] for name in self.panels}
        panel_dados: dict[str, list] = {name: [] for name in self.panels}

        for interface in self.interfaces:
            panel_a = self.panels[interface.panel_a]
            panel_b = self.panels[interface.panel_b]

            updated_a, updated_b = interface.joinery.apply(
                interface, panel_a, panel_b
            )

            panel_notches[interface.panel_a].extend(updated_a.notches)
            panel_notches[interface.panel_b].extend(updated_b.notches)
            panel_dados[interface.panel_a].extend(updated_a.dados)
            panel_dados[interface.panel_b].extend(updated_b.dados)

        result: list[PanelSpec] = []
        for name, panel in self.panels.items():
            resolved = PS(
                name=panel.name,
                width_mm=panel.width_mm,
                height_mm=panel.height_mm,
                thickness_mm=panel.thickness_mm,
                notches=tuple(panel_notches[name]),
                dados=tuple(panel_dados[name]),
                role=panel.role,
                origin=panel.origin,
            )
            result.append(resolved)

        return result


__all__ = [
    "EdgeName",
    "InterfaceType",
    "RemovalKind",
    "Interface",
    "Assembly",
]
