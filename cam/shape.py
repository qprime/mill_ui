from dataclasses import dataclass
from typing import List
from cam.types import Vec2, Bounds

@dataclass
class Shape2D:
    points: List[Vec2]
    def bounds(self) -> Bounds:
        return Bounds.from_points(self.points)
