from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Literal, Union

if TYPE_CHECKING:
    from assembly.beam import BeamSpec
    from assembly.joinery import JoineryStrategy
    from assembly.panel import PanelSpec

EdgeName = Literal["top", "bottom", "left", "right"]
MemberSpec = Union["PanelSpec", "BeamSpec"]


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
    position_along_edge_a_mm: float | None = None
    position_along_edge_b_mm: float | None = None

    def validate(self) -> None:
        if self.type not in self.joinery.valid_interfaces:
            raise ValueError(f"{type(self.joinery).__name__} not valid for {self.type.name}")


def _is_beam_spec(member: MemberSpec) -> bool:
    from assembly.beam import BeamSpec

    return isinstance(member, BeamSpec)


def _expand_beams(
    members: dict[str, MemberSpec],
    sheet_size: float,
) -> tuple[dict[str, PanelSpec], dict[str, list[str]]]:
    from assembly.beam import BeamSpec
    from assembly.panel import PanelSpec as PS

    expanded_panels: dict[str, PS] = {}
    beam_expansion_map: dict[str, list[str]] = {}

    for name, member in members.items():
        if isinstance(member, BeamSpec):
            panels = member.expand(sheet_size)
            panel_names = [p.name for p in panels]
            beam_expansion_map[name] = panel_names
            for p in panels:
                expanded_panels[p.name] = p
        else:
            expanded_panels[name] = member

    return expanded_panels, beam_expansion_map


def _get_outer_layer_panels(
    beam_name: str,
    beam: BeamSpec,
    beam_expansion_map: dict[str, list[str]],
    expanded_panels: dict[str, PanelSpec],
) -> list[PanelSpec]:
    panel_names = beam_expansion_map.get(beam_name, [])
    if not panel_names:
        return []

    layer_count = beam.layer_count

    if layer_count == 1:
        return [expanded_panels[n] for n in panel_names]

    outer_panels: list[PanelSpec] = []
    for panel_name in panel_names:
        if (
            "_L0_" in panel_name
            or panel_name.endswith("_L0")
            or f"_L{layer_count - 1}_" in panel_name
            or panel_name.endswith(f"_L{layer_count - 1}")
        ):
            outer_panels.append(expanded_panels[panel_name])

    return outer_panels


@dataclass(frozen=True)
class Assembly:
    members: dict[str, MemberSpec]
    interfaces: tuple[Interface, ...]
    sheet_size: float = 2440.0

    @property
    def panels(self) -> dict[str, PanelSpec]:
        from assembly.panel import PanelSpec as PS

        return {k: v for k, v in self.members.items() if isinstance(v, PS)}

    def validate(self) -> None:
        for interface in self.interfaces:
            interface.validate()
            if interface.panel_a not in self.members:
                raise ValueError(f"Unknown member: {interface.panel_a}")
            if interface.panel_b not in self.members:
                raise ValueError(f"Unknown member: {interface.panel_b}")

    def resolve(self) -> list[PanelSpec]:
        from assembly.beam import BeamSpec
        from assembly.panel import PanelSpec as PS

        self.validate()

        expanded_panels, beam_expansion_map = _expand_beams(self.members, self.sheet_size)

        panel_notches: dict[str, list] = {name: [] for name in expanded_panels}
        panel_dados: dict[str, list] = {name: [] for name in expanded_panels}

        for interface in self.interfaces:
            member_a = self.members[interface.panel_a]
            member_b = self.members[interface.panel_b]

            if isinstance(member_a, BeamSpec):
                joinery_panels_a = _get_outer_layer_panels(
                    interface.panel_a, member_a, beam_expansion_map, expanded_panels
                )
            else:
                joinery_panels_a = [expanded_panels[interface.panel_a]]

            if isinstance(member_b, BeamSpec):
                joinery_panels_b = _get_outer_layer_panels(
                    interface.panel_b, member_b, beam_expansion_map, expanded_panels
                )
            else:
                joinery_panels_b = [expanded_panels[interface.panel_b]]

            for panel_a in joinery_panels_a:
                for panel_b in joinery_panels_b:
                    updated_a, updated_b = interface.joinery.apply(interface, panel_a, panel_b)

                    panel_notches[panel_a.name].extend(updated_a.notches)
                    panel_notches[panel_b.name].extend(updated_b.notches)
                    panel_dados[panel_a.name].extend(updated_a.dados)
                    panel_dados[panel_b.name].extend(updated_b.dados)

        result: list[PS] = []
        for name, panel in expanded_panels.items():
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
    "Assembly",
    "EdgeName",
    "Interface",
    "InterfaceType",
    "MemberSpec",
    "RemovalKind",
]
