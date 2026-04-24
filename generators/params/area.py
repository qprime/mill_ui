from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from generators.core import BaseParams, resolve_major_spacing, resolve_minor_spacing
from generators.params.measurement_base import MeasurementParamsBase


@dataclass(frozen=True)
class FlatPocketParams(BaseParams):
    depth_mm: float
    allowance_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.depth_mm <= 0:
            raise ValueError(f"FlatPocketParams: depth_mm must be positive, got {self.depth_mm}")
        if self.allowance_mm < 0:
            raise ValueError(f"FlatPocketParams: allowance_mm must be non-negative, got {self.allowance_mm}")


@dataclass(frozen=True)
class GridParams(BaseParams):
    spacing_x_mm: float
    spacing_y_mm: float
    line_width_mm: float
    depth_mm: float
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.spacing_x_mm <= 0:
            raise ValueError(f"GridParams: spacing_x_mm must be positive, got {self.spacing_x_mm}")
        if self.spacing_y_mm <= 0:
            raise ValueError(f"GridParams: spacing_y_mm must be positive, got {self.spacing_y_mm}")
        if self.line_width_mm <= 0:
            raise ValueError(f"GridParams: line_width_mm must be positive, got {self.line_width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"GridParams: depth_mm must be positive, got {self.depth_mm}")


@dataclass(frozen=True)
class RaisedPanelParams(BaseParams):
    border_width_mm: float
    border_depth_mm: float
    field_depth_mm: float
    angle_degrees: float = 15.0

    def __post_init__(self) -> None:
        if self.border_width_mm <= 0:
            raise ValueError(f"RaisedPanelParams: border_width_mm must be positive, got {self.border_width_mm}")
        if self.border_depth_mm <= 0:
            raise ValueError(f"RaisedPanelParams: border_depth_mm must be positive, got {self.border_depth_mm}")
        if self.field_depth_mm < 0:
            raise ValueError(f"RaisedPanelParams: field_depth_mm must be non-negative, got {self.field_depth_mm}")
        if self.field_depth_mm >= self.border_depth_mm:
            raise ValueError(
                f"RaisedPanelParams: field_depth_mm ({self.field_depth_mm}) must be less than "
                f"border_depth_mm ({self.border_depth_mm}) for raised effect"
            )
        if self.angle_degrees <= 0 or self.angle_degrees >= 90:
            raise ValueError(f"RaisedPanelParams: angle_degrees must be between 0 and 90, got {self.angle_degrees}")


@dataclass(frozen=True)
class LinePatternParams(BaseParams):
    angle_deg: float = 0.0
    spacing_mm: float = 25.0
    line_width_mm: float = 4.0
    depth_mm: float = 3.0

    def __post_init__(self) -> None:
        if self.spacing_mm <= 0:
            raise ValueError(f"LinePatternParams: spacing_mm must be positive, got {self.spacing_mm}")
        if self.line_width_mm <= 0:
            raise ValueError(f"LinePatternParams: line_width_mm must be positive, got {self.line_width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"LinePatternParams: depth_mm must be positive, got {self.depth_mm}")


@dataclass(frozen=True)
class ConcentricBorderParams(BaseParams):
    insets_mm: tuple[float, ...]
    groove_width_mm: float = 3.0
    depth_mm: float = 2.0

    def __post_init__(self) -> None:
        if not self.insets_mm:
            raise ValueError("ConcentricBorderParams: insets_mm must contain at least one value")
        for i, inset in enumerate(self.insets_mm):
            if inset <= 0:
                raise ValueError(f"ConcentricBorderParams: insets_mm[{i}] must be positive, got {inset}")
        if self.groove_width_mm <= 0:
            raise ValueError(f"ConcentricBorderParams: groove_width_mm must be positive, got {self.groove_width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"ConcentricBorderParams: depth_mm must be positive, got {self.depth_mm}")


@dataclass(frozen=True)
class XPanelParams(BaseParams):
    bar_width_mm: float
    depth_mm: float

    def __post_init__(self) -> None:
        if self.bar_width_mm <= 0:
            raise ValueError(f"XPanelParams: bar_width_mm must be positive, got {self.bar_width_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"XPanelParams: depth_mm must be positive, got {self.depth_mm}")


@dataclass(frozen=True)
class FlutingParams(BaseParams):
    spacing_mm: float
    depth_mm: float
    ramp_mm: float = 10.0
    angle_deg: float = 0.0
    inset_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.spacing_mm <= 0:
            raise ValueError(f"FlutingParams: spacing_mm must be positive, got {self.spacing_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"FlutingParams: depth_mm must be positive, got {self.depth_mm}")
        if self.ramp_mm < 0:
            raise ValueError(f"FlutingParams: ramp_mm must be non-negative, got {self.ramp_mm}")
        if self.inset_mm < 0:
            raise ValueError(f"FlutingParams: inset_mm must be non-negative, got {self.inset_mm}")


@dataclass(frozen=True)
class GridLinesParams(BaseParams):
    unit: Literal["metric", "imperial", "custom"] = "metric"
    spacing_mm: float | None = None
    minor_spacing_mm: float | None = None
    depth_mm: float = 0.3
    minor_lines: bool = False

    def __post_init__(self) -> None:
        valid_units = ("metric", "imperial", "custom")
        if self.unit not in valid_units:
            raise ValueError(f"GridLinesParams: unit must be one of {valid_units}, got '{self.unit}'")

        if self.unit == "custom" and self.spacing_mm is None:
            raise ValueError("GridLinesParams: spacing_mm required for custom unit")

        major_spacing = self.get_major_spacing()
        if major_spacing <= 0:
            raise ValueError(f"GridLinesParams: major_spacing must be positive, got {major_spacing}")

        if self.minor_lines:
            minor_spacing = self.get_minor_spacing()
            if minor_spacing <= 0:
                raise ValueError(f"GridLinesParams: minor_spacing must be positive, got {minor_spacing}")

        if self.depth_mm <= 0:
            raise ValueError(f"GridLinesParams: depth_mm must be positive, got {self.depth_mm}")

    def get_major_spacing(self) -> float:
        if self.spacing_mm is not None:
            return self.spacing_mm
        return resolve_major_spacing(self.unit, self.spacing_mm)

    def get_minor_spacing(self) -> float:
        if self.minor_spacing_mm is not None:
            return self.minor_spacing_mm
        return resolve_minor_spacing(self.unit, self.minor_spacing_mm)


@dataclass(frozen=True)
class MeasurementGridParams(MeasurementParamsBase):
    depth_mm: float = 0.5


@dataclass(frozen=True)
class HoleGridParams(BaseParams):
    spacing_mm: float
    diameter_mm: float
    depth_mm: Literal["through"] | float
    pattern: Literal["rectangular", "hexagonal", "offset"] = "rectangular"
    inset_mm: float = 0.0
    align: Literal["center", "corner"] = "center"

    def __post_init__(self) -> None:
        if self.spacing_mm <= 0:
            raise ValueError(f"HoleGridParams: spacing_mm must be positive, got {self.spacing_mm}")
        if self.diameter_mm <= 0:
            raise ValueError(f"HoleGridParams: diameter_mm must be positive, got {self.diameter_mm}")
        if self.diameter_mm >= self.spacing_mm:
            raise ValueError(
                f"HoleGridParams: diameter_mm ({self.diameter_mm}) must be less than "
                f"spacing_mm ({self.spacing_mm}) to avoid overlapping holes"
            )
        if self.depth_mm != "through":
            if not isinstance(self.depth_mm, (int, float)):
                raise ValueError(f"HoleGridParams: depth_mm must be 'through' or a number, got {self.depth_mm}")
            if self.depth_mm <= 0:
                raise ValueError(f"HoleGridParams: depth_mm must be positive when numeric, got {self.depth_mm}")
        valid_patterns = ("rectangular", "hexagonal", "offset")
        if self.pattern not in valid_patterns:
            raise ValueError(f"HoleGridParams: pattern must be one of {valid_patterns}, got '{self.pattern}'")
        if self.inset_mm < 0:
            raise ValueError(f"HoleGridParams: inset_mm must be non-negative, got {self.inset_mm}")
        valid_aligns = ("center", "corner")
        if self.align not in valid_aligns:
            raise ValueError(f"HoleGridParams: align must be one of {valid_aligns}, got '{self.align}'")


@dataclass(frozen=True)
class RadialPocketParams(BaseParams):
    rays: int
    depth_mm: float
    bar_width_mm: float = 0.0
    shape: Literal["triangle", "arc"] = "triangle"
    center_shape: str | None = None
    center_size_mm: float | None = None
    start_angle_deg: float = 0.0
    end_angle_deg: float = 360.0
    radius_mm: float | None = None

    def __post_init__(self) -> None:
        if self.rays < 2:
            raise ValueError(f"RadialPocketParams: rays must be >= 2, got {self.rays}")
        if self.depth_mm <= 0:
            raise ValueError(f"RadialPocketParams: depth_mm must be positive, got {self.depth_mm}")
        if self.bar_width_mm < 0:
            raise ValueError(f"RadialPocketParams: bar_width_mm must be non-negative, got {self.bar_width_mm}")
        valid_center_shapes = ("circle", "square", "diamond", "hexagon")
        if self.center_shape is not None and self.center_shape not in valid_center_shapes:
            raise ValueError(
                f"RadialPocketParams: center_shape must be one of {valid_center_shapes}, got '{self.center_shape}'"
            )
        if self.center_shape is not None and self.center_size_mm is None:
            raise ValueError("RadialPocketParams: center_size_mm required when center_shape is set")
        if self.center_size_mm is not None and self.center_size_mm <= 0:
            raise ValueError(f"RadialPocketParams: center_size_mm must be positive, got {self.center_size_mm}")
        valid_shapes = ("triangle", "arc")
        if self.shape not in valid_shapes:
            raise ValueError(f"RadialPocketParams: shape must be one of {valid_shapes}, got '{self.shape}'")


@dataclass(frozen=True)
class RadialTickParams(BaseParams):
    rays: int
    depth_mm: float
    minor_subdivisions: int = 0
    tick_length_mm: float | None = None
    minor_tick_length_mm: float | None = None
    inward: bool = False
    labels: bool = False
    label_list: tuple[str, ...] | None = None
    label_height_mm: float = 3.0
    start_angle_deg: float = 0.0
    end_angle_deg: float = 360.0
    radius_mm: float | None = None

    def __post_init__(self) -> None:
        if self.rays < 1:
            raise ValueError(f"RadialTickParams: rays must be >= 1, got {self.rays}")
        if self.depth_mm <= 0:
            raise ValueError(f"RadialTickParams: depth_mm must be positive, got {self.depth_mm}")
        if self.minor_subdivisions < 0:
            raise ValueError(
                f"RadialTickParams: minor_subdivisions must be non-negative, got {self.minor_subdivisions}"
            )
        if self.label_height_mm <= 0:
            raise ValueError(f"RadialTickParams: label_height_mm must be positive, got {self.label_height_mm}")


@dataclass(frozen=True)
class RadialLabelParams(BaseParams):
    rays: int
    depth_mm: float
    values: tuple[str, ...] | None = None
    label_height_mm: float = 3.0
    start_angle_deg: float = 0.0
    end_angle_deg: float = 360.0
    radius_mm: float | None = None

    def __post_init__(self) -> None:
        if self.rays < 1:
            raise ValueError(f"RadialLabelParams: rays must be >= 1, got {self.rays}")
        if self.depth_mm <= 0:
            raise ValueError(f"RadialLabelParams: depth_mm must be positive, got {self.depth_mm}")
        if self.label_height_mm <= 0:
            raise ValueError(f"RadialLabelParams: label_height_mm must be positive, got {self.label_height_mm}")
        if self.values is not None and len(self.values) != self.rays:
            raise ValueError(f"RadialLabelParams: values length ({len(self.values)}) must match rays ({self.rays})")


@dataclass(frozen=True)
class RadialSvgParams(BaseParams):
    rays: int
    depth_mm: float
    svg_path: str
    feature_type: Literal["engrave", "pocket", "profile"] = "engrave"
    scale_mode: Literal["fit", "fill", "none"] = "fit"
    svg_unit_mm: float = 1.0
    rotate_element: bool = True
    start_angle_deg: float = 0.0
    end_angle_deg: float = 360.0
    radius_mm: float | None = None
    stamp_size_mm: float | None = None

    def __post_init__(self) -> None:
        if self.rays < 1:
            raise ValueError(f"RadialSvgParams: rays must be >= 1, got {self.rays}")
        if self.depth_mm <= 0:
            raise ValueError(f"RadialSvgParams: depth_mm must be positive, got {self.depth_mm}")
        if not self.svg_path or not self.svg_path.strip():
            raise ValueError("RadialSvgParams: svg_path cannot be empty")


@dataclass(frozen=True)
class HeightfieldToolEntryParams:
    tool: str
    role: str = "rough"
    stepover_frac: float = 0.6
    stepdown_mm: float | None = None

    def __post_init__(self) -> None:
        if not self.tool or not self.tool.strip():
            raise ValueError("HeightfieldToolEntryParams: tool name cannot be empty")
        if self.role != "rough":
            raise ValueError(
                f"HeightfieldToolEntryParams: role must be 'rough' (finish not yet implemented — see #3), "
                f"got {self.role!r}"
            )
        if not (0.0 < self.stepover_frac <= 1.0):
            raise ValueError(f"HeightfieldToolEntryParams: stepover_frac must be in (0, 1], got {self.stepover_frac}")
        if self.stepdown_mm is not None and self.stepdown_mm <= 0:
            raise ValueError(f"HeightfieldToolEntryParams: stepdown_mm must be positive, got {self.stepdown_mm}")


@dataclass(frozen=True)
class HeightfieldParams(BaseParams):
    image_path: str
    width_mm: float
    height_mm: float
    depth_mm: float
    white_is_high: bool = True
    tools: tuple[HeightfieldToolEntryParams, ...] = ()

    def __post_init__(self) -> None:
        if not self.image_path or not self.image_path.strip():
            raise ValueError("HeightfieldParams: image_path cannot be empty")
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError(
                f"HeightfieldParams: width_mm and height_mm must be positive, "
                f"got width_mm={self.width_mm}, height_mm={self.height_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(f"HeightfieldParams: depth_mm must be positive, got {self.depth_mm}")


__all__ = [
    "ConcentricBorderParams",
    "FlatPocketParams",
    "FlutingParams",
    "GridLinesParams",
    "GridParams",
    "HeightfieldParams",
    "HeightfieldToolEntryParams",
    "HoleGridParams",
    "LinePatternParams",
    "MeasurementGridParams",
    "RadialLabelParams",
    "RadialPocketParams",
    "RadialSvgParams",
    "RadialTickParams",
    "RaisedPanelParams",
    "XPanelParams",
]
