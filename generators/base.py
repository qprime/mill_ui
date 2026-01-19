"""Generator protocol and base classes for the domain/generator system.

Generators are deterministic functions that produce LayoutAST Items within a domain.
This module defines:

1. The Generator protocol (structural typing contract)
2. Base parameter classes with validation
3. Common utilities shared across generators

Two generator classes exist:
- Area generators: operate over the 2D interior of a domain (pockets, patterns)
- Loop generators: operate on boundary loops of a domain (profiles, beads)

Usage:
    from generators.base import GeneratorResult, FlatPocketParams
    from generators.area.flat import flat_pocket_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = FlatPocketParams(depth_mm=6.0)
    items = flat_pocket_generator(domain, params)

See Also:
    - docs/domain_generator_design.md Section 4.2 for generator contract
    - generators/area/ for area generator implementations
    - generators/loop/ for loop generator implementations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from domains import Domain

from layout_ast.layout import Item


# =============================================================================
# Type Aliases
# =============================================================================

# Generator output type
GeneratorResult = list[Item]

# Loop selection modes for loop generators
LoopSelection = Literal["outer_only", "inner_only", "all_loops"] | list[int]


# =============================================================================
# Generator Protocol
# =============================================================================

@runtime_checkable
class Generator(Protocol):
    """Protocol defining the generator interface.

    Generators are deterministic functions that:
    - Receive a domain and typed parameters
    - Operate in domain-local coordinates internally
    - Emit zero or more LayoutAST Items in sheet coordinates
    - Never modify the input domain
    - Raise on invalid parameters (unless allow_empty=True)

    This protocol is for documentation and type checking. Generators can be
    implemented as functions or classes that match this signature.
    """

    def __call__(
        self,
        domain: Domain,
        params: Any,
        *,
        allow_empty: bool = False,
    ) -> GeneratorResult:
        """Generate Items within the given domain.

        Args:
            domain: The domain defining the region for generation
            params: Typed parameter object specific to this generator
            allow_empty: If True, return empty list instead of raising when
                generation cannot produce output (e.g., domain too small)

        Returns:
            List of LayoutAST Items with geometry in sheet coordinates

        Raises:
            ValueError: If parameters are invalid or domain is unsuitable
                (unless allow_empty=True)
        """
        ...


# =============================================================================
# Parameter Base Classes
# =============================================================================

@dataclass(frozen=True)
class BaseParams(ABC):
    """Base class for generator parameter objects.

    All parameter classes should inherit from this and implement validation.
    Parameters are frozen dataclasses to ensure immutability and hashability.
    """

    @abstractmethod
    def validate(self) -> None:
        """Validate parameter values.

        Raises:
            ValueError: If any parameter is invalid, with actionable message
        """
        ...


@dataclass(frozen=True)
class FlatPocketParams(BaseParams):
    """Parameters for flat pocket area generator.

    A flat pocket removes material uniformly within the domain boundary,
    creating a recessed area at the specified depth.

    Attributes:
        depth_mm: Depth of the pocket in millimeters (must be positive)
        allowance_mm: Optional inward allowance from domain boundary (default 0)
    """

    depth_mm: float
    allowance_mm: float = 0.0

    def validate(self) -> None:
        if self.depth_mm <= 0:
            raise ValueError(
                f"FlatPocketParams: depth_mm must be positive, got {self.depth_mm}"
            )
        if self.allowance_mm < 0:
            raise ValueError(
                f"FlatPocketParams: allowance_mm must be non-negative, got {self.allowance_mm}"
            )


@dataclass(frozen=True)
class ProfileParams(BaseParams):
    """Parameters for profile loop generator.

    A profile cut follows the boundary of a domain, cutting through or to
    a specified depth. The cut can be on the inside, outside, or on the line.

    Attributes:
        side: Cut position relative to the boundary line
            - "outside": Cut outside the geometry (material outside boundary removed)
            - "inside": Cut inside the geometry (material inside boundary removed)
            - "on": Cut on the line (split the material)
        depth: Depth specification
            - "through": Cut completely through the material
            - float: Cut to specific depth in mm
        loop_selection: Which loops to profile
            - "outer_only": Profile only the outer boundary
            - "inner_only": Profile only inner boundaries (holes)
            - "all_loops": Profile all boundaries
            - list[int]: Profile specific loop indices (0=outer, 1+=inner)
        tab_count: Number of holding tabs (0 for none)
        tab_width_mm: Width of each tab in mm
        tab_height_mm: Height of tabs above cut depth in mm
    """

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

        # Validate loop_selection
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
    """Parameters for wave pattern area generator.

    A wave generator creates a sinusoidal pattern across the domain interior,
    producing parallel grooves or ridges at the specified depth.

    Attributes:
        amplitude_mm: Height of wave peaks from centerline in mm (half peak-to-peak)
        wavelength_mm: Distance between adjacent wave peaks in mm
        depth_mm: Depth of wave grooves in mm (positive value)
        direction_rad: Direction of wave propagation in radians (0 = along X-axis)
            The wave crests are perpendicular to this direction.
        phase_rad: Phase offset in radians (0 to 2*pi)
        tool_width_mm: Width of cutting tool for generating toolpath lines.
            Waves are rendered as parallel lines spaced by this amount.
        wave_count: Number of complete waves (None = fit as many as domain allows)
    """

    amplitude_mm: float
    wavelength_mm: float
    depth_mm: float
    direction_rad: float = 0.0
    phase_rad: float = 0.0
    tool_width_mm: float = 3.175  # 1/8" default
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
class GridParams(BaseParams):
    """Parameters for grid pattern area generator.

    A grid generator creates a crosshatch pattern of perpendicular lines
    across the domain interior at the specified depth.

    Attributes:
        spacing_x_mm: Horizontal spacing between vertical lines in mm
        spacing_y_mm: Vertical spacing between horizontal lines in mm
        line_width_mm: Width of grid lines in mm (typically tool diameter)
        depth_mm: Depth of grid grooves in mm (positive value)
        offset_x_mm: X offset for grid origin within domain (default 0)
        offset_y_mm: Y offset for grid origin within domain (default 0)
    """

    spacing_x_mm: float
    spacing_y_mm: float
    line_width_mm: float
    depth_mm: float
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0

    def validate(self) -> None:
        if self.spacing_x_mm <= 0:
            raise ValueError(
                f"GridParams: spacing_x_mm must be positive, got {self.spacing_x_mm}"
            )
        if self.spacing_y_mm <= 0:
            raise ValueError(
                f"GridParams: spacing_y_mm must be positive, got {self.spacing_y_mm}"
            )
        if self.line_width_mm <= 0:
            raise ValueError(
                f"GridParams: line_width_mm must be positive, got {self.line_width_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"GridParams: depth_mm must be positive, got {self.depth_mm}"
            )


@dataclass(frozen=True)
class RaisedPanelParams(BaseParams):
    """Parameters for raised panel area generator.

    Creates the traditional "raised panel" look by generating geometry for
    both an angled border and a center field. The border is cut deeper at
    the outer edge and shallower toward the center, creating the classic
    beveled appearance. The center field is cut to a uniform shallow depth,
    appearing "raised" relative to the surrounding border.

    Attributes:
        border_width_mm: Width of the angled border in mm
        border_depth_mm: Depth at outer edge of border in mm (deeper)
        field_depth_mm: Depth of center field in mm (shallower = more raised)
        angle_degrees: Angle of the bevel in degrees (typical: 10-20°).
            This is informational metadata for the CAM planner; actual
            toolpath angle is computed from border_width and depth difference.
    """

    border_width_mm: float
    border_depth_mm: float
    field_depth_mm: float
    angle_degrees: float = 15.0

    def validate(self) -> None:
        if self.border_width_mm <= 0:
            raise ValueError(
                f"RaisedPanelParams: border_width_mm must be positive, got {self.border_width_mm}"
            )
        if self.border_depth_mm <= 0:
            raise ValueError(
                f"RaisedPanelParams: border_depth_mm must be positive, got {self.border_depth_mm}"
            )
        if self.field_depth_mm < 0:
            raise ValueError(
                f"RaisedPanelParams: field_depth_mm must be non-negative, got {self.field_depth_mm}"
            )
        if self.field_depth_mm >= self.border_depth_mm:
            raise ValueError(
                f"RaisedPanelParams: field_depth_mm ({self.field_depth_mm}) must be less than "
                f"border_depth_mm ({self.border_depth_mm}) for raised effect"
            )
        if self.angle_degrees <= 0 or self.angle_degrees >= 90:
            raise ValueError(
                f"RaisedPanelParams: angle_degrees must be between 0 and 90, got {self.angle_degrees}"
            )


@dataclass(frozen=True)
class ChamferParams(BaseParams):
    """Parameters for chamfer loop generator.

    Creates angled edge cuts along domain boundaries for presentation edges.
    The chamfer is defined by its horizontal width and vertical depth, which
    together determine the chamfer angle.

    Attributes:
        width_mm: Horizontal width of chamfer in mm
        depth_mm: Vertical depth of chamfer in mm
        loop_selection: Which loops to chamfer
            - "outer_only": Chamfer only the outer boundary
            - "inner_only": Chamfer only inner boundaries (holes)
            - "all_loops": Chamfer all boundaries
            - list[int]: Chamfer specific loop indices (0=outer, 1+=inner)
    """

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

        # Validate loop_selection (same logic as ProfileParams)
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
        """Compute chamfer angle from width and depth."""
        import math
        return math.degrees(math.atan2(self.depth_mm, self.width_mm))


@dataclass(frozen=True)
class BeadParams(BaseParams):
    """Parameters for bead loop generator.

    A bead generator creates a decorative groove/bead along domain boundaries.
    Unlike profile cuts which separate parts, beads are decorative features
    that stay within the material.

    Attributes:
        width_mm: Width of the bead groove in mm
        depth_mm: Depth of the bead groove in mm (positive value)
        offset_mm: Distance from boundary to bead centerline in mm
            Positive = inward from outer boundary / outward from holes
        loop_selection: Which loops to apply bead to
            - "outer_only": Bead only the outer boundary
            - "inner_only": Bead only inner boundaries (holes)
            - "all_loops": Bead all boundaries
            - list[int]: Bead specific loop indices (0=outer, 1+=inner)
    """

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

        # Validate loop_selection (same logic as ProfileParams)
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
class LinePatternParams(BaseParams):
    """Parameters for line pattern area generator.

    Creates parallel line grooves across a domain at arbitrary angles.
    Lines are clipped to the domain boundary.

    Attributes:
        angle_deg: Angle of lines in degrees (0=horizontal, 90=vertical, 45=diagonal)
        spacing_mm: Distance between line centers in mm
        line_width_mm: Width of each groove in mm (typically tool diameter)
        depth_mm: Depth of grooves in mm (positive value)
    """

    angle_deg: float = 0.0
    spacing_mm: float = 25.0
    line_width_mm: float = 4.0
    depth_mm: float = 3.0

    def validate(self) -> None:
        if self.spacing_mm <= 0:
            raise ValueError(
                f"LinePatternParams: spacing_mm must be positive, got {self.spacing_mm}"
            )
        if self.line_width_mm <= 0:
            raise ValueError(
                f"LinePatternParams: line_width_mm must be positive, got {self.line_width_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"LinePatternParams: depth_mm must be positive, got {self.depth_mm}"
            )


@dataclass(frozen=True)
class ConcentricBorderParams(BaseParams):
    """Parameters for concentric border generator.

    Creates nested contour-following borders (inset loops) as groove patterns.
    Each border is a groove at the specified inset distance from the domain edge.

    Attributes:
        insets_mm: Tuple of inset distances from domain boundary (e.g., (15.0, 30.0, 45.0))
        groove_width_mm: Width of each groove in mm (typically tool diameter)
        depth_mm: Depth of grooves in mm (positive value)
    """

    insets_mm: tuple[float, ...]
    groove_width_mm: float = 3.0
    depth_mm: float = 2.0

    def validate(self) -> None:
        if not self.insets_mm:
            raise ValueError(
                "ConcentricBorderParams: insets_mm must contain at least one value"
            )
        for i, inset in enumerate(self.insets_mm):
            if inset <= 0:
                raise ValueError(
                    f"ConcentricBorderParams: insets_mm[{i}] must be positive, got {inset}"
                )
        if self.groove_width_mm <= 0:
            raise ValueError(
                f"ConcentricBorderParams: groove_width_mm must be positive, got {self.groove_width_mm}"
            )
        if self.depth_mm <= 0:
            raise ValueError(
                f"ConcentricBorderParams: depth_mm must be positive, got {self.depth_mm}"
            )


# =============================================================================
# Generator Utilities
# =============================================================================

def generate_shape_id(prefix: str, index: int = 0, suffix: str = "") -> str:
    """Generate a unique shape ID for generator output.

    Args:
        prefix: Generator type prefix (e.g., "pocket", "profile")
        index: Sequential index for multiple items from same generator
        suffix: Optional suffix for additional context

    Returns:
        Shape ID string like "generated_pocket_001" or "generated_profile_outer"
    """
    parts = ["generated", prefix]
    if suffix:
        parts.append(suffix)
    else:
        parts.append(f"{index:03d}")
    return "_".join(parts)


def validate_domain_for_generation(
    domain: Domain,
    min_area_mm2: float = 0.01,
    *,
    allow_empty: bool = False,
    generator_name: str = "Generator",
) -> bool:
    """Validate that a domain is suitable for generation.

    Args:
        domain: The domain to validate
        min_area_mm2: Minimum area required (default 0.01 mm^2)
        allow_empty: If True, return False instead of raising
        generator_name: Name for error messages

    Returns:
        True if valid

    Raises:
        ValueError: If domain is too small and allow_empty is False
    """
    if domain.area_mm2 < min_area_mm2:
        if allow_empty:
            return False
        raise ValueError(
            f"{generator_name}: Domain area {domain.area_mm2:.4f}mm^2 is below "
            f"minimum {min_area_mm2}mm^2"
        )
    return True


__all__ = [
    # Protocol
    "Generator",
    "GeneratorResult",
    # Parameter classes
    "BaseParams",
    "FlatPocketParams",
    "ProfileParams",
    "WaveParams",
    "GridParams",
    "BeadParams",
    "RaisedPanelParams",
    "ChamferParams",
    "LinePatternParams",
    "ConcentricBorderParams",
    # Type aliases
    "LoopSelection",
    # Utilities
    "generate_shape_id",
    "validate_domain_for_generation",
]
