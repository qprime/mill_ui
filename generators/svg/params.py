"""Parameter classes for SVG-based generators.

Provides typed parameter objects for generators that use SVG paths as input.

Limitations:
    - Fill rules (even-odd, nonzero) are not interpreted; all closed paths
      are treated as solid polygons without holes
    - Nested paths (e.g., holes in letters) are not supported; use pre-processed
      SVGs with separate inner/outer contours
    - SVG coordinates are treated as unitless; see scale_mode and svg_unit_mm
      for controlling physical sizing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from generators.base import BaseParams


@dataclass(frozen=True)
class SVGPathParams(BaseParams):
    """Parameters for SVG path-based generators.

    Enables generators to use SVG paths as input geometry. The path is parsed,
    curves are flattened to polylines, and the result is scaled/positioned
    within the target domain.

    Attributes:
        svg_path: SVG path data string (the 'd' attribute value)
            Example: "M0,0 L100,0 L100,100 L0,100 Z"
        depth_mm: Depth for the generated feature in mm (positive value)
        tolerance: Maximum deviation for curve flattening in mm
            Smaller values produce smoother curves but more points
        feature_type: Type of feature to generate
            - "engrave": Surface engraving/groove
            - "pocket": Area pocket removal
            - "profile": Boundary cut
        scale_mode: How to scale the SVG to fit the domain
            - "fit": Scale uniformly to fit within domain bounds (default)
            - "fill": Scale to fill domain (may crop)
            - "none": Use SVG coordinates directly, scaled by svg_unit_mm
        svg_unit_mm: Conversion factor from SVG units to mm (default: 1.0)
            Only used when scale_mode="none". For example, if your SVG uses
            pixels at 96 DPI, set svg_unit_mm=25.4/96 to convert to mm.
        center: If True, center the SVG within the domain
        invert_y: If True, flip Y coordinates (SVG Y increases downward,
            CAM Y typically increases upward). Default True.

    Note:
        File-based SVG loading is not supported at the generator level to
        maintain determinism. Load SVG content at a higher layer (template
        or orchestration) and pass the path string via svg_path.
    """

    svg_path: str
    depth_mm: float
    tolerance: float = 0.1
    feature_type: Literal["engrave", "pocket", "profile"] = "engrave"
    scale_mode: Literal["fit", "fill", "none"] = "fit"
    svg_unit_mm: float = 1.0
    center: bool = True
    invert_y: bool = True

    def validate(self) -> None:
        if not self.svg_path or not self.svg_path.strip():
            raise ValueError("SVGPathParams: svg_path cannot be empty")

        if self.depth_mm <= 0:
            raise ValueError(
                f"SVGPathParams: depth_mm must be positive, got {self.depth_mm}"
            )

        if self.tolerance <= 0:
            raise ValueError(
                f"SVGPathParams: tolerance must be positive, got {self.tolerance}"
            )

        if self.svg_unit_mm <= 0:
            raise ValueError(
                f"SVGPathParams: svg_unit_mm must be positive, got {self.svg_unit_mm}"
            )

        valid_features = ("engrave", "pocket", "profile")
        if self.feature_type not in valid_features:
            raise ValueError(
                f"SVGPathParams: feature_type must be one of {valid_features}, "
                f"got '{self.feature_type}'"
            )

        valid_scales = ("fit", "fill", "none")
        if self.scale_mode not in valid_scales:
            raise ValueError(
                f"SVGPathParams: scale_mode must be one of {valid_scales}, "
                f"got '{self.scale_mode}'"
            )


__all__ = [
    "SVGPathParams",
]
