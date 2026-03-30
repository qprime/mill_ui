from cam.shape import Shape2D
from cam.types import Transform2D


def place(shape: Shape2D, t: Transform2D) -> Shape2D:
    return Shape2D(tuple(t.apply(p) for p in shape.points))


__all__ = ["Transform2D", "place"]
