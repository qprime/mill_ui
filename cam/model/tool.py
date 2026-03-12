from dataclasses import dataclass
from typing import Literal

ToolKind = Literal["flat", "ball", "v", "roundover"]


@dataclass(frozen=True)
class Tool:
    name: str
    diameter: float
    kind: ToolKind = "flat"
    rpm: float = 12000.0
    feed_xy: float = 800.0
    feed_z: float = 300.0
    v_angle_deg: float | None = None
    roundover_radius_mm: float | None = None
