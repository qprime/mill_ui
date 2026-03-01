from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from generators.core import BaseParams, resolve_major_spacing, resolve_minor_spacing


@dataclass(frozen=True)
class MeasurementParamsBase(BaseParams):
    unit: Literal["metric", "imperial", "custom"] = "metric"
    minor_spacing_mm: float | None = None
    major_spacing_mm: float | None = None
    minor_length_mm: float = 3.0
    major_length_mm: float = 6.0
    depth_mm: float = 0.5
    minor_ticks: bool = True
    labels: bool = False
    label_height_mm: float = 3.0
    label_offset_mm: float | None = None
    label_interval: int = 1
    label_start: int = 0

    def _validate_common(self, name: str) -> None:
        valid_units = ("metric", "imperial", "custom")
        if self.unit not in valid_units:
            raise ValueError(f"{name}: unit must be one of {valid_units}, got '{self.unit}'")

        if self.unit == "custom":
            if self.minor_spacing_mm is None:
                raise ValueError(f"{name}: minor_spacing_mm required for custom unit")
            if self.major_spacing_mm is None:
                raise ValueError(f"{name}: major_spacing_mm required for custom unit")

        if self.label_interval < 1:
            raise ValueError(f"{name}: label_interval must be >= 1, got {self.label_interval}")
        if self.label_start < 0:
            raise ValueError(f"{name}: label_start must be >= 0, got {self.label_start}")

        minor_spacing = self.get_minor_spacing()
        major_spacing = self.get_major_spacing()

        if minor_spacing <= 0:
            raise ValueError(f"{name}: minor_spacing must be positive, got {minor_spacing}")
        if major_spacing <= 0:
            raise ValueError(f"{name}: major_spacing must be positive, got {major_spacing}")
        if self.minor_length_mm <= 0:
            raise ValueError(f"{name}: minor_length_mm must be positive, got {self.minor_length_mm}")
        if self.major_length_mm <= 0:
            raise ValueError(f"{name}: major_length_mm must be positive, got {self.major_length_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"{name}: depth_mm must be positive, got {self.depth_mm}")

    def get_minor_spacing(self) -> float:
        return resolve_minor_spacing(self.unit, self.minor_spacing_mm)

    def get_major_spacing(self) -> float:
        return resolve_major_spacing(self.unit, self.major_spacing_mm)

    def validate(self) -> None:
        self._validate_common(type(self).__name__)


__all__ = ["MeasurementParamsBase"]
