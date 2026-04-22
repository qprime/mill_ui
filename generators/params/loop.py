from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from generators.core import BaseParams, LoopSelection
from generators.params.measurement_base import MeasurementParamsBase

EdgeSelection = Literal["top", "bottom", "left", "right"]
TextAlignment = Literal["left", "center", "right"]
TextOrientation = Literal["horizontal", "vertical"]


def validate_loop_selection(loop_selection: LoopSelection, param_name: str) -> None:
    valid_selections = ("outer_only", "inner_only", "all_loops")
    if isinstance(loop_selection, str):
        if loop_selection not in valid_selections:
            raise ValueError(
                f"{param_name}: loop_selection must be one of {valid_selections} "
                f"or a list of indices, got '{loop_selection}'"
            )
    elif isinstance(loop_selection, list):
        for idx in loop_selection:
            if not isinstance(idx, int) or idx < 0:
                raise ValueError(f"{param_name}: loop_selection indices must be non-negative integers, got {idx}")
    else:
        raise ValueError(f"{param_name}: loop_selection must be string or list, got {type(loop_selection)}")


@dataclass(frozen=True)
class ProfileParams(BaseParams):
    side: Literal["outside", "inside", "on"]
    depth: Literal["through"] | float
    loop_selection: LoopSelection = "outer_only"
    tab_count: int = 0
    tab_width_mm: float = 10.0
    tab_height_mm: float = 3.0
    onion_skin_mm: float | None = None

    def __post_init__(self) -> None:
        valid_sides = ("outside", "inside", "on")
        if self.side not in valid_sides:
            raise ValueError(f"ProfileParams: side must be one of {valid_sides}, got '{self.side}'")

        if self.depth != "through":
            if not isinstance(self.depth, (int, float)):
                raise ValueError(f"ProfileParams: depth must be 'through' or a number, got {self.depth}")
            if self.depth <= 0:
                raise ValueError(f"ProfileParams: depth must be positive when numeric, got {self.depth}")

        validate_loop_selection(self.loop_selection, "ProfileParams")

        if self.tab_count < 0:
            raise ValueError(f"ProfileParams: tab_count must be non-negative, got {self.tab_count}")
        if self.tab_count > 0:
            if self.tab_width_mm <= 0:
                raise ValueError(
                    f"ProfileParams: tab_width_mm must be positive when tabs enabled, got {self.tab_width_mm}"
                )
            if self.tab_height_mm <= 0:
                raise ValueError(
                    f"ProfileParams: tab_height_mm must be positive when tabs enabled, got {self.tab_height_mm}"
                )

        if self.onion_skin_mm is not None and self.onion_skin_mm <= 0.0:
            raise ValueError(f"ProfileParams: onion_skin_mm must be positive when set, got {self.onion_skin_mm}")
        if self.onion_skin_mm is not None and self.tab_count > 0:
            raise ValueError("ProfileParams: onion_skin_mm and tabs cannot be combined")


@dataclass(frozen=True)
class WaveParams(BaseParams):
    amplitude_mm: float
    wavelength_mm: float
    depth_mm: float
    direction_rad: float = 0.0
    phase_rad: float = 0.0
    tool_width_mm: float = 3.175
    wave_count: int | None = None

    def __post_init__(self) -> None:
        if self.amplitude_mm <= 0:
            raise ValueError(f"WaveParams: amplitude_mm must be positive, got {self.amplitude_mm}")
        if self.wavelength_mm <= 0:
            raise ValueError(f"WaveParams: wavelength_mm must be positive, got {self.wavelength_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"WaveParams: depth_mm must be positive, got {self.depth_mm}")
        if self.tool_width_mm <= 0:
            raise ValueError(f"WaveParams: tool_width_mm must be positive, got {self.tool_width_mm}")
        if self.wave_count is not None and self.wave_count <= 0:
            raise ValueError(f"WaveParams: wave_count must be positive or None, got {self.wave_count}")


@dataclass(frozen=True)
class ChamferParams(BaseParams):
    width_mm: float
    depth_mm: float
    loop_selection: LoopSelection = "outer_only"

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(f"ChamferParams: width_mm must be positive, got {self.width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"ChamferParams: depth_mm must be positive, got {self.depth_mm}")

        validate_loop_selection(self.loop_selection, "ChamferParams")

    @property
    def angle_degrees(self) -> float:
        return math.degrees(math.atan2(self.depth_mm, self.width_mm))


@dataclass(frozen=True)
class BeadParams(BaseParams):
    width_mm: float
    depth_mm: float
    offset_mm: float = 0.0
    loop_selection: LoopSelection = "outer_only"

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(f"BeadParams: width_mm must be positive, got {self.width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"BeadParams: depth_mm must be positive, got {self.depth_mm}")

        validate_loop_selection(self.loop_selection, "BeadParams")


@dataclass(frozen=True)
class MeasurementEdgeParams(MeasurementParamsBase):
    edges: tuple[EdgeSelection, ...] = ()
    depth_mm: float = 0.3

    def __post_init__(self) -> None:
        if not self.edges:
            raise ValueError("MeasurementEdgeParams: edges must contain at least one edge")

        valid_edges = ("top", "bottom", "left", "right")
        for edge in self.edges:
            if edge not in valid_edges:
                raise ValueError(f"MeasurementEdgeParams: edge must be one of {valid_edges}, got '{edge}'")

        super().__post_init__()


@dataclass(frozen=True)
class EngraveTextParams(BaseParams):
    text: str
    height_mm: float = 4.0
    depth_mm: float = 0.3
    font: str = "rowmans"
    alignment: TextAlignment = "left"
    orientation: TextOrientation = "horizontal"
    spacing_factor: float = 1.0

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("EngraveTextParams: text must not be empty")
        if self.height_mm <= 0:
            raise ValueError(f"EngraveTextParams: height_mm must be positive, got {self.height_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"EngraveTextParams: depth_mm must be positive, got {self.depth_mm}")
        valid_alignments = ("left", "center", "right")
        if self.alignment not in valid_alignments:
            raise ValueError(f"EngraveTextParams: alignment must be one of {valid_alignments}, got '{self.alignment}'")
        valid_orientations = ("horizontal", "vertical")
        if self.orientation not in valid_orientations:
            raise ValueError(
                f"EngraveTextParams: orientation must be one of {valid_orientations}, got '{self.orientation}'"
            )
        if self.spacing_factor <= 0:
            raise ValueError(f"EngraveTextParams: spacing_factor must be positive, got {self.spacing_factor}")
        from generators.area.engrave_text import VALID_FONT_NAMES

        if self.font not in VALID_FONT_NAMES:
            raise ValueError(f"EngraveTextParams: font must be one of {sorted(VALID_FONT_NAMES)}, got '{self.font}'")


__all__ = [
    "BeadParams",
    "ChamferParams",
    "EdgeSelection",
    "EngraveTextParams",
    "MeasurementEdgeParams",
    "ProfileParams",
    "TextAlignment",
    "TextOrientation",
    "WaveParams",
]
