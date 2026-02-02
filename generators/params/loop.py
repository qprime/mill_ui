
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from generators.core import BaseParams, LoopSelection

EdgeSelection = Literal["top", "bottom", "left", "right"]
TextAlignment = Literal["left", "center", "right"]
TextOrientation = Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class ProfileParams(BaseParams):

    side: Literal["outside", "inside", "on"]
    depth: Literal["through"] | float
    loop_selection: LoopSelection = "outer_only"
    tab_count: int = 0
    tab_width_mm: float = 10.0
    tab_height_mm: float = 3.0

    def validate(self) -> None:
        valid_sides = ("outside", "inside", "on")
        if self.side not in valid_sides:
            raise ValueError(
                f"ProfileParams: side must be one of {valid_sides}, got '{self.side}'"
            )

        if self.depth != "through":
            if not isinstance(self.depth, (int, float)):
                raise ValueError(
                    f"ProfileParams: depth must be 'through' or a number, got {self.depth}"
                )
            if self.depth <= 0:
                raise ValueError(
                    f"ProfileParams: depth must be positive when numeric, got {self.depth}"
                )


        valid_selections = ("outer_only", "inner_only", "all_loops")
        if isinstance(self.loop_selection, str):
            if self.loop_selection not in valid_selections:
                raise ValueError(
                    f"ProfileParams: loop_selection must be one of {valid_selections} "
                    f"or a list of indices, got '{self.loop_selection}'"
                )
        elif isinstance(self.loop_selection, list):
            for idx in self.loop_selection:
                if not isinstance(idx, int) or idx < 0:
                    raise ValueError(
                        f"ProfileParams: loop_selection indices must be non-negative integers, "
                        f"got {idx}"
                    )
        else:
            raise ValueError(
                f"ProfileParams: loop_selection must be string or list, got {type(self.loop_selection)}"
            )

        if self.tab_count < 0:
            raise ValueError(
                f"ProfileParams: tab_count must be non-negative, got {self.tab_count}"
            )
        if self.tab_count > 0:
            if self.tab_width_mm <= 0:
                raise ValueError(
                    f"ProfileParams: tab_width_mm must be positive when tabs enabled, "
                    f"got {self.tab_width_mm}"
                )
            if self.tab_height_mm <= 0:
                raise ValueError(
                    f"ProfileParams: tab_height_mm must be positive when tabs enabled, "
                    f"got {self.tab_height_mm}"
                )


@dataclass(frozen=True)
class WaveParams(BaseParams):

    amplitude_mm: float
    wavelength_mm: float
    depth_mm: float
    direction_rad: float = 0.0
    phase_rad: float = 0.0
    tool_width_mm: float = 3.175
    wave_count: int | None = None

    def validate(self) -> None:
        if self.amplitude_mm <= 0:
            raise ValueError(
                f"WaveParams: amplitude_mm must be positive, got {self.amplitude_mm}"
            )
        if self.wavelength_mm <= 0:
            raise ValueError(
                f"WaveParams: wavelength_mm must be positive, got {self.wavelength_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"WaveParams: depth_mm must be positive, got {self.depth_mm}"
            )
        if self.tool_width_mm <= 0:
            raise ValueError(
                f"WaveParams: tool_width_mm must be positive, got {self.tool_width_mm}"
            )
        if self.wave_count is not None and self.wave_count <= 0:
            raise ValueError(
                f"WaveParams: wave_count must be positive or None, got {self.wave_count}"
            )


@dataclass(frozen=True)
class ChamferParams(BaseParams):

    width_mm: float
    depth_mm: float
    loop_selection: LoopSelection = "outer_only"

    def validate(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(
                f"ChamferParams: width_mm must be positive, got {self.width_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"ChamferParams: depth_mm must be positive, got {self.depth_mm}"
            )


        valid_selections = ("outer_only", "inner_only", "all_loops")
        if isinstance(self.loop_selection, str):
            if self.loop_selection not in valid_selections:
                raise ValueError(
                    f"ChamferParams: loop_selection must be one of {valid_selections} "
                    f"or a list of indices, got '{self.loop_selection}'"
                )
        elif isinstance(self.loop_selection, list):
            for idx in self.loop_selection:
                if not isinstance(idx, int) or idx < 0:
                    raise ValueError(
                        f"ChamferParams: loop_selection indices must be non-negative integers, "
                        f"got {idx}"
                    )
        else:
            raise ValueError(
                f"ChamferParams: loop_selection must be string or list, got {type(self.loop_selection)}"
            )

    @property
    def angle_degrees(self) -> float:
        return math.degrees(math.atan2(self.depth_mm, self.width_mm))


@dataclass(frozen=True)
class BeadParams(BaseParams):

    width_mm: float
    depth_mm: float
    offset_mm: float = 0.0
    loop_selection: LoopSelection = "outer_only"

    def validate(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(
                f"BeadParams: width_mm must be positive, got {self.width_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"BeadParams: depth_mm must be positive, got {self.depth_mm}"
            )


        valid_selections = ("outer_only", "inner_only", "all_loops")
        if isinstance(self.loop_selection, str):
            if self.loop_selection not in valid_selections:
                raise ValueError(
                    f"BeadParams: loop_selection must be one of {valid_selections} "
                    f"or a list of indices, got '{self.loop_selection}'"
                )
        elif isinstance(self.loop_selection, list):
            for idx in self.loop_selection:
                if not isinstance(idx, int) or idx < 0:
                    raise ValueError(
                        f"BeadParams: loop_selection indices must be non-negative integers, "
                        f"got {idx}"
                    )
        else:
            raise ValueError(
                f"BeadParams: loop_selection must be string or list, got {type(self.loop_selection)}"
            )


@dataclass(frozen=True)
class MeasurementEdgeParams(BaseParams):

    edges: tuple[EdgeSelection, ...]
    unit: Literal["metric", "imperial", "custom"] = "metric"
    minor_spacing_mm: float | None = None
    major_spacing_mm: float | None = None
    minor_length_mm: float = 3.0
    major_length_mm: float = 6.0
    depth_mm: float = 0.3
    minor_ticks: bool = True
    labels: bool = False
    label_height_mm: float = 3.0
    label_offset_mm: float | None = None
    label_interval: int = 1
    label_start: int = 0

    def validate(self) -> None:
        if not self.edges:
            raise ValueError(
                "MeasurementEdgeParams: edges must contain at least one edge"
            )

        valid_edges = ("top", "bottom", "left", "right")
        for edge in self.edges:
            if edge not in valid_edges:
                raise ValueError(
                    f"MeasurementEdgeParams: edge must be one of {valid_edges}, got '{edge}'"
                )

        valid_units = ("metric", "imperial", "custom")
        if self.unit not in valid_units:
            raise ValueError(
                f"MeasurementEdgeParams: unit must be one of {valid_units}, got '{self.unit}'"
            )

        if self.unit == "custom":
            if self.minor_spacing_mm is None:
                raise ValueError(
                    "MeasurementEdgeParams: minor_spacing_mm required for custom unit"
                )
            if self.major_spacing_mm is None:
                raise ValueError(
                    "MeasurementEdgeParams: major_spacing_mm required for custom unit"
                )

        if self.label_interval < 1:
            raise ValueError(
                f"MeasurementEdgeParams: label_interval must be >= 1, got {self.label_interval}"
            )
        if self.label_start < 0:
            raise ValueError(
                f"MeasurementEdgeParams: label_start must be >= 0, got {self.label_start}"
            )

        minor_spacing = self.get_minor_spacing()
        major_spacing = self.get_major_spacing()

        if minor_spacing <= 0:
            raise ValueError(
                f"MeasurementEdgeParams: minor_spacing must be positive, got {minor_spacing}"
            )
        if major_spacing <= 0:
            raise ValueError(
                f"MeasurementEdgeParams: major_spacing must be positive, got {major_spacing}"
            )
        if self.minor_length_mm <= 0:
            raise ValueError(
                f"MeasurementEdgeParams: minor_length_mm must be positive, got {self.minor_length_mm}"
            )
        if self.major_length_mm <= 0:
            raise ValueError(
                f"MeasurementEdgeParams: major_length_mm must be positive, got {self.major_length_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"MeasurementEdgeParams: depth_mm must be positive, got {self.depth_mm}"
            )

    def get_minor_spacing(self) -> float:
        if self.unit == "metric":
            return 1.0
        elif self.unit == "imperial":
            return 25.4 / 16
        else:
            return self.minor_spacing_mm or 1.0

    def get_major_spacing(self) -> float:
        if self.unit == "metric":
            return 10.0
        elif self.unit == "imperial":
            return 25.4
        else:
            return self.major_spacing_mm or 10.0


@dataclass(frozen=True)
class EngraveTextParams(BaseParams):

    text: str
    height_mm: float = 4.0
    depth_mm: float = 0.3
    font: str = "rowmans"
    alignment: TextAlignment = "left"
    orientation: TextOrientation = "horizontal"
    spacing_factor: float = 1.0

    def validate(self) -> None:
        if not self.text:
            raise ValueError("EngraveTextParams: text must not be empty")
        if self.height_mm <= 0:
            raise ValueError(
                f"EngraveTextParams: height_mm must be positive, got {self.height_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"EngraveTextParams: depth_mm must be positive, got {self.depth_mm}"
            )
        valid_alignments = ("left", "center", "right")
        if self.alignment not in valid_alignments:
            raise ValueError(
                f"EngraveTextParams: alignment must be one of {valid_alignments}, got '{self.alignment}'"
            )
        valid_orientations = ("horizontal", "vertical")
        if self.orientation not in valid_orientations:
            raise ValueError(
                f"EngraveTextParams: orientation must be one of {valid_orientations}, got '{self.orientation}'"
            )
        if self.spacing_factor <= 0:
            raise ValueError(
                f"EngraveTextParams: spacing_factor must be positive, got {self.spacing_factor}"
            )


__all__ = [
    "ProfileParams",
    "WaveParams",
    "ChamferParams",
    "BeadParams",
    "MeasurementEdgeParams",
    "EngraveTextParams",
    "EdgeSelection",
    "TextAlignment",
    "TextOrientation",
]
