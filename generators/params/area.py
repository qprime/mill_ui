from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from core.constants import GOLDEN_ANGLE_DEG
from domains.domain import JoinStyle, Point2D
from generators.core import BaseParams, resolve_major_spacing, resolve_minor_spacing
from generators.params.measurement_base import MeasurementParamsBase
from generators.radial_utils import closest_pair_distance, spiral_positions
from layout_ast.layout import RestSpec

_SPIRAL_TOLERANCE_MM = 1e-9


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
    depth_mm: float = 2.0
    groove_width_mm: float | None = 3.0
    join_style: JoinStyle = "mitre"
    mode: Literal["pocket", "engrave"] = "pocket"

    def __post_init__(self) -> None:
        if not self.insets_mm:
            raise ValueError("ConcentricBorderParams: insets_mm must contain at least one value")
        for i, inset in enumerate(self.insets_mm):
            if inset <= 0:
                raise ValueError(f"ConcentricBorderParams: insets_mm[{i}] must be positive, got {inset}")
        if len(set(self.insets_mm)) != len(self.insets_mm):
            raise ValueError(f"ConcentricBorderParams: insets_mm contains a duplicate inset: {self.insets_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"ConcentricBorderParams: depth_mm must be positive, got {self.depth_mm}")
        if self.join_style not in ("mitre", "round", "bevel"):
            raise ValueError(
                f"ConcentricBorderParams: join_style must be 'mitre', 'round' or 'bevel', got {self.join_style!r}"
            )
        if self.mode == "engrave":
            if self.groove_width_mm is not None:
                raise ValueError(
                    "ConcentricBorderParams: groove_width_mm is only valid for pocket mode; "
                    "pass groove_width_mm=None for engrave mode"
                )
            return
        if self.mode != "pocket":
            raise ValueError(f"ConcentricBorderParams: mode must be 'pocket' or 'engrave', got {self.mode!r}")
        if self.groove_width_mm is None or self.groove_width_mm <= 0:
            raise ValueError(
                f"ConcentricBorderParams: groove_width_mm must be positive in pocket mode, got {self.groove_width_mm}"
            )
        for shallow, deep in pairwise(sorted(self.insets_mm)):
            if deep - shallow < self.groove_width_mm:
                raise ValueError(
                    f"ConcentricBorderParams: insets {shallow} and {deep} are closer than "
                    f"groove_width_mm {self.groove_width_mm}; the rings would overlap"
                )


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


def _validate_spiral(
    name: str,
    count: int,
    spacing_mm: float,
    angle_deg: float,
    motif_extent_mm: float,
) -> None:
    if count < 1:
        raise ValueError(f"{name}: count must be >= 1, got {count}")
    if spacing_mm <= 0:
        raise ValueError(f"{name}: spacing_mm must be positive, got {spacing_mm}")
    if motif_extent_mm <= 0:
        raise ValueError(f"{name}: motif extent must be positive, got {motif_extent_mm}")
    points = [point for point, _ in spiral_positions(count, spacing_mm, angle_deg)]
    closest = closest_pair_distance(points)
    if motif_extent_mm >= closest - _SPIRAL_TOLERANCE_MM:
        raise ValueError(
            f"{name}: motif extent {motif_extent_mm:.3f}mm must be less than the closest-pair distance "
            f"{closest:.3f}mm of the {count} spiral points (spacing {spacing_mm}mm, angle {angle_deg} deg) "
            f"to avoid overlapping motifs"
        )


def _validate_radius_scaling(
    name: str,
    scale_with_radius: bool,
    min_size_mm: float | None,
    size_mm: float,
) -> None:
    if not scale_with_radius:
        if min_size_mm is not None:
            raise ValueError(f"{name}: min_size_mm requires scale_with_radius")
        return
    if min_size_mm is None:
        raise ValueError(f"{name}: scale_with_radius requires min_size_mm")
    if min_size_mm <= 0:
        raise ValueError(f"{name}: min_size_mm must be positive, got {min_size_mm}")
    if min_size_mm > size_mm:
        raise ValueError(f"{name}: min_size_mm ({min_size_mm}) must not exceed the motif size ({size_mm})")


@dataclass(frozen=True)
class PhyllotaxisHoleParams(BaseParams):
    count: int
    spacing_mm: float
    diameter_mm: float
    depth_mm: Literal["through"] | float
    angle_deg: float = GOLDEN_ANGLE_DEG

    def __post_init__(self) -> None:
        if self.depth_mm != "through":
            if not isinstance(self.depth_mm, (int, float)):
                raise ValueError(f"PhyllotaxisHoleParams: depth_mm must be 'through' or a number, got {self.depth_mm}")
            if self.depth_mm <= 0:
                raise ValueError(f"PhyllotaxisHoleParams: depth_mm must be positive when numeric, got {self.depth_mm}")
        _validate_spiral("PhyllotaxisHoleParams", self.count, self.spacing_mm, self.angle_deg, self.diameter_mm)


@dataclass(frozen=True)
class PhyllotaxisPocketParams(BaseParams):
    count: int
    spacing_mm: float
    diameter_mm: float
    depth_mm: float
    angle_deg: float = GOLDEN_ANGLE_DEG
    scale_with_radius: bool = False
    min_size_mm: float | None = None

    def __post_init__(self) -> None:
        if self.depth_mm <= 0:
            raise ValueError(f"PhyllotaxisPocketParams: depth_mm must be positive, got {self.depth_mm}")
        _validate_spiral("PhyllotaxisPocketParams", self.count, self.spacing_mm, self.angle_deg, self.diameter_mm)
        _validate_radius_scaling("PhyllotaxisPocketParams", self.scale_with_radius, self.min_size_mm, self.diameter_mm)


@dataclass(frozen=True)
class PhyllotaxisSvgParams(BaseParams):
    count: int
    spacing_mm: float
    svg_path: str
    size_mm: float
    depth_mm: float
    angle_deg: float = GOLDEN_ANGLE_DEG
    scale_with_radius: bool = False
    min_size_mm: float | None = None
    feature_type: Literal["engrave", "pocket"] = "engrave"
    rotate_element: bool = True

    def __post_init__(self) -> None:
        if not self.svg_path or not self.svg_path.strip():
            raise ValueError("PhyllotaxisSvgParams: svg_path cannot be empty")
        valid_features = ("engrave", "pocket")
        if self.feature_type not in valid_features:
            raise ValueError(
                f"PhyllotaxisSvgParams: feature_type must be one of {valid_features}, got '{self.feature_type}'"
            )
        if self.size_mm <= 0:
            raise ValueError(f"PhyllotaxisSvgParams: size_mm must be positive, got {self.size_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"PhyllotaxisSvgParams: depth_mm must be positive, got {self.depth_mm}")
        _validate_spiral(
            "PhyllotaxisSvgParams", self.count, self.spacing_mm, self.angle_deg, self.size_mm * math.sqrt(2)
        )
        _validate_radius_scaling("PhyllotaxisSvgParams", self.scale_with_radius, self.min_size_mm, self.size_mm)


def _validate_curve_shared(
    name: str,
    depth_mm: float,
    size_mm: float | None,
    tolerance_mm: float,
    min_length_mm: float,
) -> None:
    if depth_mm <= 0:
        raise ValueError(f"{name}: depth_mm must be positive, got {depth_mm}")
    if size_mm is not None and size_mm <= 0:
        raise ValueError(f"{name}: size_mm must be positive, got {size_mm}")
    if tolerance_mm <= 0:
        raise ValueError(f"{name}: tolerance_mm must be positive, got {tolerance_mm}")
    if min_length_mm < 0:
        raise ValueError(f"{name}: min_length_mm must be non-negative, got {min_length_mm}")


@dataclass(frozen=True)
class RoseCurveParams(BaseParams):
    lobes: int
    depth_mm: float
    size_mm: float | None = None
    rotation_deg: float = 0.0
    tolerance_mm: float = 0.05
    min_length_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.lobes < 1:
            raise ValueError(f"RoseCurveParams: lobes must be >= 1, got {self.lobes}")
        _validate_curve_shared("RoseCurveParams", self.depth_mm, self.size_mm, self.tolerance_mm, self.min_length_mm)


@dataclass(frozen=True)
class SpirographLayerParams:
    points: int
    step: int
    pens: tuple[float, ...]
    mode: Literal["inside", "outside"] = "inside"
    rotation_deg: float = 0.0
    rotation_step_deg: float = 0.0
    depth_mm: float | None = None

    def __post_init__(self) -> None:
        if self.points < 1:
            raise ValueError(f"SpirographLayerParams: points must be >= 1, got {self.points}")
        if self.step < 1:
            raise ValueError(f"SpirographLayerParams: step must be >= 1, got {self.step}")
        factor = math.gcd(self.points, self.step)
        if factor > 1:
            raise ValueError(
                f"SpirographLayerParams: points {self.points} and step {self.step} share a factor of {factor}; "
                f"the same figure is points {self.points // factor}, step {self.step // factor}"
            )
        valid_modes = ("inside", "outside")
        if self.mode not in valid_modes:
            raise ValueError(f"SpirographLayerParams: mode must be one of {valid_modes}, got '{self.mode}'")
        if self.mode == "inside" and self.step >= self.points:
            raise ValueError(
                f"SpirographLayerParams: step ({self.step}) must be less than points ({self.points}) for mode 'inside'"
            )
        if not self.pens:
            raise ValueError("SpirographLayerParams: pens must not be empty")
        for pen in self.pens:
            if pen < 0:
                raise ValueError(f"SpirographLayerParams: pen values must be non-negative, got {pen}")
        if self.rotation_step_deg != 0 and len(self.pens) < 2:
            raise ValueError(
                f"SpirographLayerParams: rotation_step_deg ({self.rotation_step_deg}) needs 2 or more pen values, "
                f"got {len(self.pens)}"
            )
        if self.rotation_step_deg == 0 and len(set(self.pens)) < len(self.pens):
            raise ValueError(
                f"SpirographLayerParams: pens {self.pens} repeat a value without a rotation_step_deg, "
                "so those strands would coincide"
            )
        if self.depth_mm is not None and self.depth_mm <= 0:
            raise ValueError(f"SpirographLayerParams: depth_mm must be positive, got {self.depth_mm}")


@dataclass(frozen=True)
class SpirographCurveParams(BaseParams):
    layers: tuple[SpirographLayerParams, ...]
    depth_mm: float
    size_mm: float | None = None
    rotation_deg: float = 0.0
    tolerance_mm: float = 0.05
    min_length_mm: float = 0.0
    max_cut_length_mm: float = 50000.0

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError("SpirographCurveParams: layers must not be empty")
        if self.max_cut_length_mm <= 0:
            raise ValueError(f"SpirographCurveParams: max_cut_length_mm must be positive, got {self.max_cut_length_mm}")
        _validate_curve_shared(
            "SpirographCurveParams", self.depth_mm, self.size_mm, self.tolerance_mm, self.min_length_mm
        )


@dataclass(frozen=True)
class LissajousCurveParams(BaseParams):
    frequency_x: int
    frequency_y: int
    depth_mm: float
    phase_deg: float = 90.0
    width_mm: float | None = None
    height_mm: float | None = None
    size_mm: float | None = None
    rotation_deg: float = 0.0
    tolerance_mm: float = 0.05
    min_length_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.frequency_x < 1:
            raise ValueError(f"LissajousCurveParams: frequency_x must be >= 1, got {self.frequency_x}")
        if self.frequency_y < 1:
            raise ValueError(f"LissajousCurveParams: frequency_y must be >= 1, got {self.frequency_y}")
        if self.width_mm is not None and self.width_mm <= 0:
            raise ValueError(f"LissajousCurveParams: width_mm must be positive, got {self.width_mm}")
        if self.height_mm is not None and self.height_mm <= 0:
            raise ValueError(f"LissajousCurveParams: height_mm must be positive, got {self.height_mm}")
        _validate_curve_shared(
            "LissajousCurveParams", self.depth_mm, self.size_mm, self.tolerance_mm, self.min_length_mm
        )


@dataclass(frozen=True)
class SuperformulaCurveParams(BaseParams):
    m: int
    n1: float
    n2: float
    n3: float
    depth_mm: float
    a: float = 1.0
    b: float = 1.0
    size_mm: float | None = None
    rotation_deg: float = 0.0
    tolerance_mm: float = 0.05
    min_length_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.m < 1:
            raise ValueError(f"SuperformulaCurveParams: m must be >= 1, got {self.m}")
        for name, value in (("n1", self.n1), ("n2", self.n2), ("n3", self.n3), ("a", self.a), ("b", self.b)):
            if value <= 0:
                raise ValueError(f"SuperformulaCurveParams: {name} must be positive, got {value}")
        _validate_curve_shared(
            "SuperformulaCurveParams", self.depth_mm, self.size_mm, self.tolerance_mm, self.min_length_mm
        )


@dataclass(frozen=True)
class HarmonographPendulumParams:
    axis: Literal["x", "y"]
    amplitude_mm: float
    frequency: float
    phase_deg: float = 0.0
    damping: float = 0.0

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y"):
            raise ValueError(f"HarmonographPendulumParams: axis must be 'x' or 'y', got {self.axis!r}")
        if self.amplitude_mm <= 0:
            raise ValueError(f"HarmonographPendulumParams: amplitude_mm must be positive, got {self.amplitude_mm}")
        if self.frequency <= 0:
            raise ValueError(f"HarmonographPendulumParams: frequency must be positive, got {self.frequency}")
        if self.damping < 0:
            raise ValueError(f"HarmonographPendulumParams: damping must be non-negative, got {self.damping}")


@dataclass(frozen=True)
class HarmonographCurveParams(BaseParams):
    cycles: float
    pendulums: tuple[HarmonographPendulumParams, ...]
    depth_mm: float
    size_mm: float | None = None
    rotation_deg: float = 0.0
    tolerance_mm: float = 0.05
    min_length_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.cycles <= 0:
            raise ValueError(f"HarmonographCurveParams: cycles must be positive, got {self.cycles}")
        axes = {pendulum.axis for pendulum in self.pendulums}
        for axis in ("x", "y"):
            if axis not in axes:
                raise ValueError(f"HarmonographCurveParams: pendulums need at least one on axis '{axis}'")
        _validate_curve_shared(
            "HarmonographCurveParams", self.depth_mm, self.size_mm, self.tolerance_mm, self.min_length_mm
        )


@dataclass(frozen=True)
class VoronoiParams(BaseParams):
    depth_mm: float
    seed_count: int | None = None
    points: tuple[Point2D, ...] | None = None
    seed: int = 0
    min_spacing_mm: float | None = None
    margin_mm: float = 0.0
    mode: Literal["engrave", "pocket"] = "engrave"
    line_width_mm: float | None = None
    cell_inset_mm: float = 0.0
    min_length_mm: float = 0.0
    rest: RestSpec | None = None

    def __post_init__(self) -> None:
        if self.depth_mm <= 0:
            raise ValueError(f"VoronoiParams: depth_mm must be positive, got {self.depth_mm}")
        self._validate_seed_source()
        for name, value in (
            ("margin_mm", self.margin_mm),
            ("cell_inset_mm", self.cell_inset_mm),
            ("min_length_mm", self.min_length_mm),
        ):
            if value < 0:
                raise ValueError(f"VoronoiParams: {name} must be non-negative, got {value}")
        self._validate_mode()

    def _validate_seed_source(self) -> None:
        if (self.seed_count is None) == (self.points is None):
            raise ValueError("VoronoiParams: give exactly one of seed_count or points")
        if self.seed < 0:
            raise ValueError(f"VoronoiParams: seed must be a non-negative integer, got {self.seed}")
        if self.min_spacing_mm is not None and self.min_spacing_mm <= 0:
            raise ValueError(f"VoronoiParams: min_spacing_mm must be positive when given, got {self.min_spacing_mm}")
        if self.seed_count is not None:
            if self.seed_count < 2:
                raise ValueError(f"VoronoiParams: seed_count must be at least 2, got {self.seed_count}")
            return
        if len(set(self.points or ())) < 2:
            raise ValueError("VoronoiParams: points must include at least 2 distinct locations")
        for name, ignored in (
            ("seed", self.seed != 0),
            ("min_spacing_mm", self.min_spacing_mm is not None),
            ("margin_mm", self.margin_mm != 0),
        ):
            if ignored:
                raise ValueError(f"VoronoiParams: {name} applies only to seed_count and would be ignored with points")

    def _validate_mode(self) -> None:
        if self.mode == "engrave":
            if self.line_width_mm is not None:
                raise ValueError("VoronoiParams: line_width_mm is only valid in pocket mode")
            if self.cell_inset_mm != 0:
                raise ValueError("VoronoiParams: cell_inset_mm is only valid in pocket mode")
            if self.rest is not None:
                raise ValueError("VoronoiParams: rest is only valid in pocket mode")
            return
        if self.mode != "pocket":
            raise ValueError(f"VoronoiParams: mode must be 'engrave' or 'pocket', got {self.mode!r}")
        if self.line_width_mm is None or self.line_width_mm <= 0:
            raise ValueError(f"VoronoiParams: line_width_mm must be positive in pocket mode, got {self.line_width_mm}")
        if self.min_length_mm != 0:
            raise ValueError("VoronoiParams: min_length_mm is only valid in engrave mode")


@dataclass(frozen=True)
class StringArtParams(BaseParams):
    anchors: int
    rule: Literal["multiply", "skip", "mirror"]
    depth_mm: float
    factor: int | None = None
    step: int | None = None
    phase_deg: float = 0.0
    min_length_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.anchors < 3:
            raise ValueError(f"StringArtParams: anchors must be at least 3, got {self.anchors}")
        if self.depth_mm <= 0:
            raise ValueError(f"StringArtParams: depth_mm must be positive, got {self.depth_mm}")
        if self.min_length_mm < 0:
            raise ValueError(f"StringArtParams: min_length_mm must be non-negative, got {self.min_length_mm}")
        if self.rule not in ("multiply", "skip", "mirror"):
            raise ValueError(f"StringArtParams: rule must be 'multiply', 'skip' or 'mirror', got {self.rule!r}")
        self._validate_rule_keys()

    def _validate_rule_keys(self) -> None:
        if self.rule != "multiply" and self.factor is not None:
            raise ValueError(f"StringArtParams: factor is only valid with rule 'multiply', not {self.rule!r}")
        if self.rule != "skip" and self.step is not None:
            raise ValueError(f"StringArtParams: step is only valid with rule 'skip', not {self.rule!r}")
        if self.rule == "multiply" and (self.factor is None or self.factor < 2):
            raise ValueError(f"StringArtParams: rule 'multiply' requires factor >= 2, got {self.factor}")
        if self.rule == "skip" and (self.step is None or not 1 <= self.step < self.anchors):
            raise ValueError(
                f"StringArtParams: rule 'skip' requires 1 <= step < anchors ({self.anchors}), got {self.step}"
            )


@dataclass(frozen=True)
class HeightfieldToolEntryParams:
    tool: str
    role: str = "rough"
    stepover_frac: float = 0.6
    stepdown_mm: float | None = None
    angle_deg: float | None = None

    def __post_init__(self) -> None:
        if not self.tool or not self.tool.strip():
            raise ValueError("HeightfieldToolEntryParams: tool name cannot be empty")
        if self.role not in ("rough", "finish"):
            raise ValueError(f"HeightfieldToolEntryParams: role must be 'rough' or 'finish', got {self.role!r}")
        if not (0.0 < self.stepover_frac <= 1.0):
            raise ValueError(f"HeightfieldToolEntryParams: stepover_frac must be in (0, 1], got {self.stepover_frac}")
        if self.stepdown_mm is not None and self.stepdown_mm <= 0:
            raise ValueError(f"HeightfieldToolEntryParams: stepdown_mm must be positive, got {self.stepdown_mm}")
        if self.role == "finish" and self.stepdown_mm is not None:
            raise ValueError("HeightfieldToolEntryParams: stepdown_mm not valid for finish role (single-pass)")
        if self.role == "rough" and self.angle_deg is not None:
            raise ValueError("HeightfieldToolEntryParams: angle_deg only valid for finish role")
        if self.role == "finish" and self.angle_deg is None:
            raise ValueError("HeightfieldToolEntryParams: finish role requires angle_deg")


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
    "HarmonographCurveParams",
    "HarmonographPendulumParams",
    "HeightfieldParams",
    "HeightfieldToolEntryParams",
    "HoleGridParams",
    "LinePatternParams",
    "LissajousCurveParams",
    "MeasurementGridParams",
    "PhyllotaxisHoleParams",
    "PhyllotaxisPocketParams",
    "PhyllotaxisSvgParams",
    "RadialLabelParams",
    "RadialPocketParams",
    "RadialSvgParams",
    "RadialTickParams",
    "RaisedPanelParams",
    "RoseCurveParams",
    "SpirographCurveParams",
    "SpirographLayerParams",
    "SuperformulaCurveParams",
    "XPanelParams",
]
