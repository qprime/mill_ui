from dataclasses import dataclass

from cam.types import Vec2
from domains.domain import Bounds2D


@dataclass(frozen=True)
class Shape2D:
    points: tuple[Vec2, ...]

    def bounds(self) -> Bounds2D:
        return Bounds2D.from_points([(p.x, p.y) for p in self.points])
