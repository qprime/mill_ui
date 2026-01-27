from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Point2D = tuple[float, float]


@runtime_checkable
class JointProfile(Protocol):
    depth_mm: float

    def compute_edge_geometry(
        self,
        edge_start: Point2D,
        edge_end: Point2D,
    ) -> list[Point2D]:
        ...


def _distance(p0: Point2D, p1: Point2D) -> float:
    return math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2)


def _normalize(dx: float, dy: float) -> tuple[float, float]:
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-10:
        return (0.0, 0.0)
    return (dx / length, dy / length)


@dataclass(frozen=True)
class FingerJointProfile:
    depth_mm: float
    width_mm: float | None = None
    count: int | None = None
    phase: Literal[0, 1] = 0
    clearance_mm: float = 0.1

    def __post_init__(self) -> None:
        if (self.width_mm is None) == (self.count is None):
            raise ValueError("Specify exactly one of width_mm or count")
        if self.depth_mm <= 0:
            raise ValueError(f"depth_mm must be positive, got {self.depth_mm}")
        if self.width_mm is not None and self.width_mm <= 0:
            raise ValueError(f"width_mm must be positive, got {self.width_mm}")
        if self.count is not None and self.count < 1:
            raise ValueError(f"count must be at least 1, got {self.count}")
        if self.clearance_mm < 0:
            raise ValueError(f"clearance_mm must be non-negative, got {self.clearance_mm}")

    def _compute_finger_count(self, edge_length: float) -> int:
        if self.count is not None:
            n = self.count
        else:
            n = round(edge_length / self.width_mm)

        n = max(3, n)
        if n % 2 == 0:
            n += 1
        return n

    def compute_edge_geometry(
        self,
        edge_start: Point2D,
        edge_end: Point2D,
    ) -> list[Point2D]:
        """Generate finger joint vertices along an edge.

        For a horizontal edge from left to right:
        - Outward normal points downward (negative Y)
        - Fingers protrude in outward direction
        - Phase 0 starts with a finger (protrusion)
        - Phase 1 starts with a notch (at baseline)

        The output is a sequence of vertices that replaces the straight edge
        with a finger/notch pattern. Vertices trace the edge from start to end,
        going "out" at finger positions and staying at baseline for notches.
        """
        edge_length = _distance(edge_start, edge_end)
        if edge_length < 1e-10:
            return [edge_start, edge_end]

        dx = edge_end[0] - edge_start[0]
        dy = edge_end[1] - edge_start[1]
        d = _normalize(dx, dy)

        n_out = (d[1], -d[0])

        finger_count = self._compute_finger_count(edge_length)
        finger_width = edge_length / finger_count

        def point_at(t: float, offset: float = 0.0) -> Point2D:
            return (
                edge_start[0] + d[0] * t + n_out[0] * offset,
                edge_start[1] + d[1] * t + n_out[1] * offset,
            )

        vertices: list[Point2D] = []

        for i in range(finger_count):
            is_finger = (i % 2 == 0) == (self.phase == 0)
            seg_start_t = i * finger_width
            seg_end_t = (i + 1) * finger_width

            depth = self.depth_mm if is_finger else 0.0

            if i == 0:
                vertices.append(point_at(seg_start_t, depth))
            else:
                prev_is_finger = ((i - 1) % 2 == 0) == (self.phase == 0)
                if prev_is_finger != is_finger:
                    vertices.append(point_at(seg_start_t, self.depth_mm if prev_is_finger else 0.0))
                    vertices.append(point_at(seg_start_t, depth))

            if i == finger_count - 1:
                vertices.append(point_at(seg_end_t, depth))

        return vertices
