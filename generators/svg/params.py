from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from generators.core import BaseParams


@dataclass(frozen=True)
class SVGPathParams(BaseParams):
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
            raise ValueError(f"SVGPathParams: depth_mm must be positive, got {self.depth_mm}")

        if self.tolerance <= 0:
            raise ValueError(f"SVGPathParams: tolerance must be positive, got {self.tolerance}")

        if self.svg_unit_mm <= 0:
            raise ValueError(f"SVGPathParams: svg_unit_mm must be positive, got {self.svg_unit_mm}")

        valid_features = ("engrave", "pocket", "profile")
        if self.feature_type not in valid_features:
            raise ValueError(f"SVGPathParams: feature_type must be one of {valid_features}, got '{self.feature_type}'")

        valid_scales = ("fit", "fill", "none")
        if self.scale_mode not in valid_scales:
            raise ValueError(f"SVGPathParams: scale_mode must be one of {valid_scales}, got '{self.scale_mode}'")


__all__ = [
    "SVGPathParams",
]
