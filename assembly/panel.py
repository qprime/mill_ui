from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Any, Literal

from domains.domain import Point2D
from layout_ast.layout import DogboneSpec


class PanelRole(Enum):
    LEFT = auto()
    RIGHT = auto()
    FRONT = auto()
    BACK = auto()
    TOP = auto()
    BOTTOM = auto()
    SHELF = auto()
    PARTITION = auto()


class Edge(Enum):
    BOTTOM = 0
    RIGHT = 1
    TOP = 2
    LEFT = 3


@dataclass(frozen=True)
class NotchSpec:
    edge: Edge
    u_start_mm: float
    u_len_mm: float
    depth_mm: float
    shape: str = "rectangular"
    shape_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.u_start_mm < 0:
            raise ValueError(f"u_start_mm must be non-negative, got {self.u_start_mm}")
        if self.u_len_mm <= 0:
            raise ValueError(f"u_len_mm must be positive, got {self.u_len_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"depth_mm must be positive, got {self.depth_mm}")

    @property
    def edge_index(self) -> int:
        return self.edge.value


@dataclass(frozen=True)
class DadoSpec:
    position_from_edge_mm: float
    width_mm: float
    depth_mm: float
    edge: Literal["top", "bottom", "left", "right"]
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    dogbone: DogboneSpec | None = None


@dataclass(frozen=True)
class PanelSpec:
    name: str
    width_mm: float
    height_mm: float
    thickness_mm: float
    notches: tuple[NotchSpec, ...] = ()
    dados: tuple[DadoSpec, ...] = ()
    role: PanelRole | None = None
    origin: Point2D = (0.0, 0.0)

    @property
    def polygon(self) -> tuple[Point2D, ...]:
        ox, oy = self.origin
        hw, hh = self.width_mm / 2, self.height_mm / 2
        return (
            (ox - hw, oy - hh),
            (ox + hw, oy - hh),
            (ox + hw, oy + hh),
            (ox - hw, oy + hh),
        )

    def edge_length(self, edge: Edge) -> float:
        if edge in (Edge.BOTTOM, Edge.TOP):
            return self.width_mm
        return self.height_mm

    def with_notches(self, notches: tuple[NotchSpec, ...]) -> PanelSpec:
        return replace(self, notches=self.notches + notches)

    def with_dados(self, dados: tuple[DadoSpec, ...]) -> PanelSpec:
        return replace(self, dados=self.dados + dados)


def validate_notch_fits_edge(notch: NotchSpec, edge_length: float) -> None:
    if notch.u_start_mm + notch.u_len_mm > edge_length + 1e-6:
        raise ValueError(
            f"Notch exceeds edge length: u_start={notch.u_start_mm}mm + "
            f"u_len={notch.u_len_mm}mm = {notch.u_start_mm + notch.u_len_mm}mm > "
            f"edge_length={edge_length}mm"
        )


def validate_notches_no_overlap(notches: list[NotchSpec]) -> None:
    by_edge: dict[Edge, list[NotchSpec]] = {}
    for n in notches:
        by_edge.setdefault(n.edge, []).append(n)

    for edge, edge_notches in by_edge.items():
        sorted_notches = sorted(edge_notches, key=lambda x: x.u_start_mm)
        for i in range(len(sorted_notches) - 1):
            a = sorted_notches[i]
            b = sorted_notches[i + 1]
            if a.u_start_mm + a.u_len_mm > b.u_start_mm + 1e-6:
                raise ValueError(
                    f"Overlapping notches on edge {edge.name}: "
                    f"[{a.u_start_mm}, {a.u_start_mm + a.u_len_mm}] overlaps "
                    f"[{b.u_start_mm}, {b.u_start_mm + b.u_len_mm}]"
                )


__all__ = [
    "DadoSpec",
    "Edge",
    "NotchSpec",
    "PanelRole",
    "PanelSpec",
    "Point2D",
    "validate_notch_fits_edge",
    "validate_notches_no_overlap",
]
