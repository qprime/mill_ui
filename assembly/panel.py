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
    dogbone: DogboneSpec | None = None

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

    def __post_init__(self) -> None:
        if self.position_from_edge_mm < 0:
            raise ValueError(f"DadoSpec: position_from_edge_mm must be non-negative, got {self.position_from_edge_mm}")
        if self.width_mm <= 0:
            raise ValueError(f"DadoSpec: width_mm must be positive, got {self.width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"DadoSpec: depth_mm must be positive, got {self.depth_mm}")
        valid_edges = ("top", "bottom", "left", "right")
        if self.edge not in valid_edges:
            raise ValueError(f"DadoSpec: edge must be one of {valid_edges}, got '{self.edge}'")
        valid_orientations = ("horizontal", "vertical")
        if self.orientation not in valid_orientations:
            raise ValueError(f"DadoSpec: orientation must be one of {valid_orientations}, got '{self.orientation}'")


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


__all__ = [
    "DadoSpec",
    "Edge",
    "NotchSpec",
    "PanelRole",
    "PanelSpec",
    "Point2D",
]
