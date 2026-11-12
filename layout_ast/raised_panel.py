from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class RaisedPanelSpec:
    border_depth_mm: float
    field_depth_mm: float
    border_width_mm: float | None = None
    profile: Literal["gutter", "v_groove"] = "gutter"
    v_angle_deg: float = 90.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.border_depth_mm) or self.border_depth_mm <= 0:
            raise ValueError("RaisedPanel: border_depth must be finite and positive")
        if not math.isfinite(self.field_depth_mm) or not 0 <= self.field_depth_mm < self.border_depth_mm:
            raise ValueError("RaisedPanel: field_depth must be nonnegative and less than border_depth")
        if not math.isfinite(self.v_angle_deg) or not 0 < self.v_angle_deg < 180:
            raise ValueError("RaisedPanel: v_angle must be between 0 and 180 degrees (included angle)")
        if self.profile not in ("gutter", "v_groove"):
            raise ValueError(f"RaisedPanel: unknown profile {self.profile!r}; expected gutter or v_groove")
        if self.profile == "v_groove":
            if self.border_width_mm is not None:
                raise ValueError(
                    "RaisedPanel v_groove derives its border width from the bit angle and depths; omit border_width"
                )
        else:
            width = self.border_width_mm
            if width is None or not math.isfinite(width) or width <= 0:
                raise ValueError("RaisedPanel gutter: border_width must be finite and positive")
            if width < self.minimum_border_width_mm - 1e-9:
                raise ValueError(
                    f"RaisedPanel gutter: border_width {width}mm must be at least {self.minimum_border_width_mm:.6f}mm "
                    "to contain the V-bit at the requested depths"
                )

    @property
    def slope_run_mm(self) -> float:
        return (self.border_depth_mm - self.field_depth_mm) * math.tan(math.radians(self.v_angle_deg / 2))

    @property
    def cutter_radius_at_depth_mm(self) -> float:
        return self.border_depth_mm * math.tan(math.radians(self.v_angle_deg / 2))

    @property
    def minimum_border_width_mm(self) -> float:
        return self.cutter_radius_at_depth_mm + self.slope_run_mm

    @property
    def field_inset_mm(self) -> float:
        return self.minimum_border_width_mm if self.border_width_mm is None else self.border_width_mm

    @property
    def groove_inset_mm(self) -> float:
        return self.field_inset_mm - self.slope_run_mm

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "raised_panel",
            "border_depth_mm": self.border_depth_mm,
            "field_depth_mm": self.field_depth_mm,
            "border_width_mm": self.border_width_mm,
            "profile": self.profile,
            "v_angle_deg": self.v_angle_deg,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RaisedPanelSpec:
        return cls(
            border_depth_mm=float(data["border_depth_mm"]),
            field_depth_mm=float(data["field_depth_mm"]),
            border_width_mm=None if data.get("border_width_mm") is None else float(data["border_width_mm"]),
            profile=data.get("profile", "gutter"),
            v_angle_deg=float(data.get("v_angle_deg", 90)),
        )
