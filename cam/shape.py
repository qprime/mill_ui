from dataclasses import dataclass
from typing import List
from skills.mill_ui.cam.types import Vec2, Bounds

@dataclass
class Shape2D:
    points: List[Vec2]   # closed polyline
    def bounds(self) -> Bounds:
        return Bounds.from_points(self.points)
