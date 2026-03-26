from __future__ import annotations

import math

from cam.config import Config
from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CommentMove, CutMove, Move, RapidMove, RetractMove
from cam.native import core as native_core
from cam.primitives import polygon, rectangle
from cam.shape import Shape2D
from cam.transforms import Transform2D, place


def _setup(ramp_angle_deg: float = 3.0) -> Setup:
    tool = Tool(name="6mm_flat", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
    stock = Stock(width=200.0, height=200.0, thickness=19.0)
    machine = Machine(name="default_grbl")
    return Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0, ramp_angle_deg=ramp_angle_deg)


def _rect_shape(w: float = 50.0, h: float = 50.0) -> Shape2D:
    return place(rectangle(w, h), Transform2D(tx=10.0, ty=10.0))


def _cut_moves(moves: list[Move]) -> list[CutMove]:
    return [m for m in moves if isinstance(m, CutMove)]


def _retract_moves(moves: list[Move]) -> list[RetractMove]:
    return [m for m in moves if isinstance(m, RetractMove)]


def _rapid_moves(moves: list[Move]) -> list[RapidMove]:
    return [m for m in moves if isinstance(m, RapidMove)]


def _comment_texts(moves: list[Move]) -> list[str]:
    return [m.text for m in moves if isinstance(m, CommentMove)]


def _has_comment(moves: list[Move], text: str) -> bool:
    return any(isinstance(m, CommentMove) and text in m.text for m in moves)


def _planar_face(pts: list[tuple[float, float]], depth: float = 6.0) -> dict:
    return {"z": 0.0, "depth": depth, "safe_z": 5.0, "outer": pts, "holes": []}


def _rect_pts(w: float = 50.0, h: float = 50.0, cx: float = 25.0, cy: float = 25.0):
    return [
        (cx - w / 2, cy - h / 2),
        (cx + w / 2, cy - h / 2),
        (cx + w / 2, cy + h / 2),
        (cx - w / 2, cy + h / 2),
    ]


def _triangle_pts(base: float = 60.0, height: float = 50.0):
    return [
        (0.0, 0.0),
        (base, 0.0),
        (base / 2, height),
    ]


def _pentagon_pts(radius: float = 30.0):
    pts = []
    for i in range(5):
        angle = 2 * math.pi * i / 5 - math.pi / 2
        pts.append((radius * math.cos(angle), radius * math.sin(angle)))
    return pts


def _l_shape_pts():
    return [
        (0, 0),
        (40, 0),
        (40, 20),
        (20, 20),
        (20, 40),
        (0, 40),
    ]


class TestConvexGeometry:
    def test_is_convex_rectangle(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert len(moves) > 0
        assert _has_comment(moves, "pocket_spiral")

    def test_is_convex_triangle(self):
        pts = _triangle_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert len(moves) > 0
        assert _has_comment(moves, "pocket_spiral")

    def test_is_convex_pentagon(self):
        pts = _pentagon_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert len(moves) > 0
        assert _has_comment(moves, "pocket_spiral")

    def test_is_convex_l_shape(self):
        pts = _l_shape_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert _has_comment(moves, "concave polygon: raster clipped to boundary")
        assert _has_comment(moves, "pocket_raster_clipped")

    def test_inset_rectangle(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        assert len(cuts) > 0
        for c in cuts:
            if c.x is not None:
                assert c.x >= 10.0 - 0.01
                assert c.x <= 60.0 + 0.01

    def test_inset_collapse(self):
        tiny = place(rectangle(5.0, 5.0), Transform2D(tx=10.0, ty=10.0))
        moves = native_core.pocket_raster(
            tiny, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        assert len(cuts) <= 6

    def test_inset_preserves_convexity(self):
        pts = _pentagon_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")

    def test_inset_near_degenerate(self):
        pts = [(0.0, 0.0), (100.0, 0.0), (50.0, 2.0)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert isinstance(moves, list)

    def test_inset_flat_trapezoid(self):
        pts = [(0.0, 0.0), (50.0, 0.0), (48.0, 30.0), (2.0, 30.0)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")


class TestPocketSpiralRect:
    def test_generates_moves(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        assert len(cuts) > 0

    def test_continuous_path(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        in_layer = False
        for m in moves:
            if isinstance(m, CutMove) and m.z is not None and m.z < 0:
                in_layer = True
            if in_layer and isinstance(m, RetractMove):
                in_layer = False
            if in_layer:
                assert not isinstance(m, RapidMove), "Rapid move found within a cutting layer"

    def test_one_retract_per_layer(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        retracts = _retract_moves(moves)
        assert len(retracts) == 3

    def test_cw_winding(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        assert len(xy_cuts) >= 4
        total_cross = 0.0
        for i in range(len(xy_cuts) - 2):
            ax, ay = xy_cuts[i]
            bx, by = xy_cuts[i + 1]
            cx, cy = xy_cuts[i + 2]
            cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            total_cross += cross
        assert total_cross <= 0.0, "Spiral should be CW (negative cross product sum)"

    def test_xy_within_pocket(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        for c in cuts:
            if c.x is not None:
                assert c.x >= 10.0 - 0.1
                assert c.x <= 60.0 + 0.1
            if c.y is not None:
                assert c.y >= 10.0 - 0.1
                assert c.y <= 60.0 + 0.1

    def test_ramp_entry_per_layer(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        ramp_cuts = [
            c for c in _cut_moves(moves) if c.x is not None and c.y is not None and c.z is not None and c.z < 0
        ]
        assert len(ramp_cuts) >= 3

    def test_small_pocket_single_ring(self):
        tiny = place(rectangle(4.0, 4.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            tiny, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        retracts = _retract_moves(moves)
        assert len(retracts) <= 1

    def test_outermost_lap_on_boundary(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        if xy_cuts:
            all_xs = [p[0] for p in xy_cuts]
            tool_r = 3.0
            assert min(all_xs) <= 10.0 + tool_r + 1.0
            assert max(all_xs) >= 60.0 - tool_r - 2 * 2.0

    def test_near_square(self):
        shape = place(rectangle(20.0, 21.0), Transform2D(tx=10.0, ty=10.0))
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        retracts = _retract_moves(moves)
        assert len(retracts) == 1

    def test_non_even_stepover(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=3.0, stepover_mm=3.7, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        retracts = _retract_moves(moves)
        assert len(retracts) == 1


class TestPocketSpiralConvexPolygon:
    def test_triangle_spiral(self):
        shape = polygon(_triangle_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        assert len(_cut_moves(moves)) > 0

    def test_pentagon_spiral(self):
        shape = polygon(_pentagon_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")

    def test_polygon_continuous(self):
        shape = polygon(_pentagon_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        in_layer = False
        for m in moves:
            if isinstance(m, CutMove) and m.z is not None and m.z < 0:
                in_layer = True
            if in_layer and isinstance(m, RetractMove):
                in_layer = False
            if in_layer:
                assert not isinstance(m, RapidMove)

    def test_polygon_xy_within_boundary(self):
        pts = _pentagon_pts(radius=30.0)
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        for c in cuts:
            if c.x is not None and c.y is not None:
                dist = math.hypot(c.x, c.y)
                assert dist <= 30.0 + 0.5

    def test_polygon_lap_shrinks(self):
        shape = polygon(_pentagon_pts(radius=40.0))
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        if len(xy_cuts) > 10:
            first_dists = [math.hypot(x, y) for x, y in xy_cuts[:5]]
            last_dists = [math.hypot(x, y) for x, y in xy_cuts[-5:]]
            assert max(last_dists) < max(first_dists) + 1.0

    def test_polygon_residual(self):
        shape = polygon(_pentagon_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        retracts = _retract_moves(moves)
        assert len(retracts) == 1

    def test_flat_trapezoid_spiral(self):
        pts = [(0.0, 0.0), (60.0, 0.0), (55.0, 25.0), (5.0, 25.0)]
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        assert len(_retract_moves(moves)) == 1


def _small_tool_setup(ramp_angle_deg: float = 3.0) -> Setup:
    tool = Tool(name="2mm_flat", diameter=2.0, rpm=18000, feed_xy=2000, feed_z=300)
    stock = Stock(width=200.0, height=200.0, thickness=19.0)
    machine = Machine(name="default_grbl")
    return Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0, ramp_angle_deg=ramp_angle_deg)


class TestSpiralSliverPass:
    def test_elongated_rect_clears_center(self):
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, _small_tool_setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        center_y = 5.0
        center_cuts = [p for p in xy_cuts if abs(p[1] - center_y) < 0.5]
        assert len(center_cuts) >= 2
        xs = [p[0] for p in center_cuts]
        assert max(xs) - min(xs) > 30.0

    def test_elongated_rect_continuous(self):
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, _small_tool_setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        in_layer = False
        for m in moves:
            if isinstance(m, CutMove) and m.z is not None and m.z < 0:
                in_layer = True
            if in_layer and isinstance(m, RetractMove):
                in_layer = False
            if in_layer:
                assert not isinstance(m, RapidMove), "Rapid move found within a cutting layer"

    def test_elongated_rect_one_retract_per_layer(self):
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, _small_tool_setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        retracts = _retract_moves(moves)
        assert len(retracts) == 1

    def test_elongated_vertical_rect(self):
        shape = place(rectangle(10.0, 100.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, _small_tool_setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        center_x = 5.0
        center_cuts = [p for p in xy_cuts if abs(p[0] - center_x) < 0.5]
        assert len(center_cuts) >= 2
        ys = [p[1] for p in center_cuts]
        assert max(ys) - min(ys) > 30.0

    def test_large_tool_no_sliver(self):
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=0.0, ty=0.0))
        moves_without = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves_without)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        center_y = 5.0
        center_cuts = [p for p in xy_cuts if abs(p[1] - center_y) < 0.1]
        assert len(center_cuts) == 0

    def test_sliver_within_pocket_bounds(self):
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=5.0, ty=5.0))
        moves = native_core.pocket_raster(
            shape, _small_tool_setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        for c in cuts:
            if c.x is not None:
                assert c.x >= 5.0 - 0.1
                assert c.x <= 105.0 + 0.1
            if c.y is not None:
                assert c.y >= 5.0 - 0.1
                assert c.y <= 15.0 + 0.1

    def test_multi_depth_sliver(self):
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, _small_tool_setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        retracts = _retract_moves(moves)
        assert len(retracts) == 3

    def test_short_dim_at_threshold_no_sliver(self):
        tool = Tool(name="4mm_flat", diameter=4.0, rpm=18000, feed_xy=2000, feed_z=300)
        stock = Stock(width=200.0, height=200.0, thickness=19.0)
        machine = Machine(name="default_grbl")
        setup = Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0, ramp_angle_deg=3.0)
        shape = place(rectangle(100.0, 12.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, setup, depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        center_y = 6.0
        center_cuts = [p for p in xy_cuts if abs(p[1] - center_y) < 0.1]
        assert len(center_cuts) == 0

    def test_short_dim_just_above_threshold(self):
        tool = Tool(name="1mm_flat", diameter=1.0, rpm=18000, feed_xy=2000, feed_z=300)
        stock = Stock(width=200.0, height=200.0, thickness=19.0)
        machine = Machine(name="default_grbl")
        setup = Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0, ramp_angle_deg=3.0)
        shape = place(rectangle(100.0, 10.0), Transform2D(tx=0.0, ty=0.0))
        moves = native_core.pocket_raster(
            shape, setup, depth_mm=3.0, stepover_mm=3.0, stepdown_mm=3.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        center_y = 5.0
        center_cuts = [p for p in xy_cuts if abs(p[1] - center_y) < 0.5]
        assert len(center_cuts) >= 2


class TestConcaveFallback:
    def test_concave_uses_clipped_raster(self):
        shape = polygon(_l_shape_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_raster_clipped")

    def test_concave_emits_clipped_comment(self):
        shape = polygon(_l_shape_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        assert _has_comment(moves, "concave polygon: raster clipped to boundary")

    def test_concave_still_produces_moves(self):
        shape = polygon(_l_shape_pts())
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="spiral"
        )
        cuts = _cut_moves(moves)
        assert len(cuts) > 0


class TestPocketStrategyConfig:
    def test_config_default_is_spiral(self):
        cfg = Config()
        assert cfg.pocket_strategy == "spiral"

    def test_config_raster_fallback(self):
        cfg = Config(pocket_strategy="raster")
        assert cfg.pocket_strategy == "raster"

    def test_env_var_override(self):
        cfg = Config.from_env(environ={"CAM_POCKET_STRATEGY": "raster"})
        assert cfg.pocket_strategy == "raster"

    def test_spiral_skips_finish_profile(self):
        from cam.path.strategies import pocket_then_finish_profile

        setup = _setup()
        shape = _rect_shape()
        moves = pocket_then_finish_profile(shape, setup, total_depth_mm=6.0, pocket_strategy="spiral")
        assert not _has_comment(moves, "finish profile pass")

    def test_raster_still_emits_finish(self):
        from cam.path.strategies import pocket_then_finish_profile

        setup = _setup()
        shape = _rect_shape()
        moves = pocket_then_finish_profile(shape, setup, total_depth_mm=6.0, pocket_strategy="raster")
        assert _has_comment(moves, "finish profile pass")


class TestPocketSpiralIntegration:
    def test_raster_strategy_produces_raster(self):
        moves = native_core.pocket_raster(
            _rect_shape(), _setup(), depth_mm=6.0, stepover_mm=2.0, stepdown_mm=2.0, strategy="raster"
        )
        assert _has_comment(moves, "pocket_raster")
        assert not _has_comment(moves, "pocket_spiral")

    def test_polygon_pocket_not_rectangularized(self):
        pts = _triangle_pts()
        shape = polygon(pts)
        moves = native_core.pocket_raster(
            shape, _setup(), depth_mm=3.0, stepover_mm=2.0, stepdown_mm=3.0, strategy="spiral"
        )
        assert _has_comment(moves, "pocket_spiral")
        cuts = _cut_moves(moves)
        xy_cuts = [(c.x, c.y) for c in cuts if c.x is not None and c.y is not None]
        for x, y in xy_cuts:
            if y > 1.0:
                assert x >= -1.0
                assert x <= 61.0
