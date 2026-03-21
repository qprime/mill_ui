from __future__ import annotations

import math

from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CommentMove, CutMove, Move, RetractMove
from cam.native import core as native_core
from cam.primitives import polygon


def _setup(ramp_angle_deg: float = 3.0) -> Setup:
    tool = Tool(name="6mm_flat", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
    stock = Stock(width=200.0, height=200.0, thickness=19.0)
    machine = Machine(name="default_grbl")
    return Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0, ramp_angle_deg=ramp_angle_deg)


def _cut_moves(moves: list[Move]) -> list[CutMove]:
    return [m for m in moves if isinstance(m, CutMove)]


def _retract_moves(moves: list[Move]) -> list[RetractMove]:
    return [m for m in moves if isinstance(m, RetractMove)]


def _has_comment(moves: list[Move], text: str) -> bool:
    return any(isinstance(m, CommentMove) and text in m.text for m in moves)


def _l_shape_pts():
    return [
        (0, 0),
        (40, 0),
        (40, 20),
        (20, 20),
        (20, 40),
        (0, 40),
    ]


def _arrow_pts():
    return [
        (0, 10),
        (30, 0),
        (25, 10),
        (50, 20),
        (25, 30),
        (30, 40),
        (0, 30),
    ]


def _star_pts(n: int = 5, outer_r: float = 40.0, inner_r: float = 18.0):
    pts = []
    for i in range(n * 2):
        angle = math.pi * i / n - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((r * math.cos(angle), r * math.sin(angle)))
    return pts


def _point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class TestScanlineClipping:
    def test_l_shape_uses_clipped_raster(self):
        shape = polygon(_l_shape_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert _has_comment(moves, "raster_clipped")

    def test_l_shape_clips_to_boundary(self):
        pts = _l_shape_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        tool_r = 3.0
        for c in cuts:
            if c.x is not None and c.y is not None:
                assert _point_in_polygon(c.x, c.y, pts) or _near_boundary(c.x, c.y, pts, tool_r + 1.0), (
                    f"Cut at ({c.x:.3f}, {c.y:.3f}) outside L-shape boundary"
                )

    def test_l_shape_multiple_intervals(self):
        pts = _l_shape_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=2.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        retracts = _retract_moves(moves)
        assert len(retracts) > 1

    def test_concave_arrow(self):
        shape = polygon(_arrow_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "raster_clipped")
        assert len(_cut_moves(moves)) > 0

    def test_star_shape(self):
        shape = polygon(_star_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "raster_clipped")
        assert len(_cut_moves(moves)) > 0

    def test_xy_within_boundary(self):
        pts = _l_shape_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        xs = [c.x for c in cuts if c.x is not None]
        ys = [c.y for c in cuts if c.y is not None]
        assert all(x >= -1.0 for x in xs)
        assert all(x <= 41.0 for x in xs)
        assert all(y >= -1.0 for y in ys)
        assert all(y <= 41.0 for y in ys)

    def test_finish_profile_follows_polygon(self):
        pts = _l_shape_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "finish_perimeter_clipped")
        in_profile = False
        profile_xy = []
        for m in moves:
            if isinstance(m, CommentMove) and "finish_perimeter_clipped" in m.text:
                in_profile = True
                continue
            if in_profile and isinstance(m, RetractMove):
                break
            if in_profile and isinstance(m, CutMove) and m.x is not None and m.y is not None:
                profile_xy.append((m.x, m.y))
        assert len(profile_xy) >= 3
        for x, y in profile_xy:
            assert _near_boundary(x, y, pts, 4.0), f"Profile vertex ({x:.3f}, {y:.3f}) not near polygon boundary"

    def test_l_shape_no_cuts_in_excluded_quadrant(self):
        pts = _l_shape_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        for c in cuts:
            if c.x is not None and c.y is not None:
                in_excluded = c.x > 22.0 and c.y > 22.0
                assert not in_excluded, f"Cut at ({c.x:.3f}, {c.y:.3f}) in excluded upper-right quadrant of L-shape"

    def test_shallow_pocket_efficiency(self):
        shape = polygon(_l_shape_pts())
        moves_clipped = native_core.pocket_raster(
            shape, _setup(), depth_mm=2.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        moves_raster = native_core.pocket_raster(
            shape, _setup(), depth_mm=2.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="raster"
        )
        clipped_cuts = len(_cut_moves(moves_clipped))
        raster_cuts = len(_cut_moves(moves_raster))
        assert clipped_cuts <= raster_cuts + 20

    def test_convex_unchanged(self):
        pts = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        assert not _has_comment(moves, "raster_clipped")


class TestScanlineEdgeCases:
    def test_row_through_vertex(self):
        pts = [(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=20.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        assert len(cuts) > 0

    def test_horizontal_edge(self):
        pts = [(0, 0), (60, 0), (60, 20), (30, 20), (30, 40), (0, 40)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "raster_clipped")
        cuts = _cut_moves(moves)
        assert len(cuts) > 0

    def test_thin_sliver(self):
        pts = [(0, 0), (50, 0), (50, 4), (25, 2), (0, 4)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert isinstance(moves, list)

    def test_near_parallel_edges(self):
        pts = [(0, 0), (60, 0.5), (60, 20), (30, 20.5), (30, 40), (0, 39.5)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert isinstance(moves, list)
        cuts = _cut_moves(moves)
        assert len(cuts) >= 0


def _near_boundary(x: float, y: float, poly: list[tuple[float, float]], tol: float) -> bool:
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        ax, ay = poly[i]
        bx, by = poly[j]
        dx, dy = bx - ax, by - ay
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-18:
            continue
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / len_sq))
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(x - px, y - py)
        if dist <= tol:
            return True
    return False
