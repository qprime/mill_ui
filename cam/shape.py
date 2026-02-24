from dataclasses import dataclass

from cam.types import Bounds, Vec2


@dataclass
class Shape2D:
    points: list[Vec2]

    def bounds(self) -> Bounds:
        return Bounds.from_points(self.points)
