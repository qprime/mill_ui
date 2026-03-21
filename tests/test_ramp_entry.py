from __future__ import annotations

import math

from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CommentMove, CutMove, Move, RapidMove, RetractMove
from cam.ops.pocket import pocket_raster
from cam.ops.profile import profile_outline
from cam.path.strategies import onion_skin_then_finish, profile_outline_with_tabs
from cam.primitives import polygon, rectangle
from cam.shape import Shape2D
from cam.transforms import Transform2D, place


def _setup(ramp_angle_deg: float = 3.0) -> Setup:
    tool = Tool(name="6mm_flat", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
    stock = Stock(width=200.0, height=200.0, thickness=19.0)
    machine = Machine(name="default_grbl")
    return Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0, ramp_angle_deg=ramp_angle_deg)


def _rect_shape(w: float = 100.0, h: float = 80.0) -> Shape2D:
    return place(rectangle(w, h), Transform2D(tx=10.0, ty=10.0))


def _cut_moves(moves: list[Move]) -> list[CutMove]:
    return [m for m in moves if isinstance(m, CutMove)]


def _rapid_moves(moves: list[Move]) -> list[RapidMove]:
    return [m for m in moves if isinstance(m, RapidMove)]


def _has_z_only_plunge(moves: list[Move]) -> bool:
    return any(isinstance(m, CutMove) and m.z is not None and m.x is None and m.y is None for m in moves)


def _has_xyz_ramp(moves: list[Move]) -> bool:
    return any(
        isinstance(m, CutMove) and m.x is not None and m.y is not None and m.z is not None and m.z < 0 for m in moves
    )


class TestProfileRampEntry:
    def test_profile_ramp_entry_default(self):
        setup = _setup(3.0)
        shape = _rect_shape()
        moves = profile_outline(shape, setup, depth_mm=6.0, step_down=3.0)
        assert _has_xyz_ramp(moves)

    def test_profile_ramp_z_reaches_target(self):
        setup = _setup(3.0)
        shape = _rect_shape()
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        cuts = _cut_moves(moves)
        ramp_cuts = [c for c in cuts if c.x is not None and c.y is not None and c.z is not None and c.z < 0]
        assert ramp_cuts
        last_z = ramp_cuts[-1].z
        assert last_z is not None
        assert abs(last_z - (-3.0)) < 0.01

    def test_profile_ramp_distance_correct(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        cuts = _cut_moves(moves)
        ramp_cuts = [c for c in cuts if c.x is not None and c.y is not None and c.z is not None and c.z < 0]
        expected_dist = 3.0 / math.tan(math.radians(3.0))
        total_dist = 0.0
        prev: CutMove | None = None
        for c in ramp_cuts:
            if prev is not None and prev.x is not None and prev.y is not None and c.x is not None and c.y is not None:
                total_dist += math.hypot(c.x - prev.x, c.y - prev.y)
            prev = c
        assert abs(total_dist - expected_dist) < 2.0

    def test_ramp_distance_constant_across_passes(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        ramp_cuts = [
            m
            for m in moves
            if isinstance(m, CutMove) and m.x is not None and m.y is not None and m.z is not None and m.z < 0
        ]
        target_depths = {-3.0, -6.0, -9.0}
        reached_depths = set()
        for c in ramp_cuts:
            assert c.z is not None
            for d in target_depths:
                if abs(c.z - d) < 0.01:
                    reached_depths.add(d)
        assert reached_depths == target_depths

    def test_profile_open_boundary_fallback(self):
        from cam.types import Vec2 as V

        open_pts = [V(0.0, 0.0), V(100.0, 0.0), V(100.0, 80.0), V(0.0, 80.0)]
        shape = Shape2D(open_pts)
        setup = _setup(3.0)
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        assert _has_z_only_plunge(moves)


class TestPocketRampEntry:
    def test_pocket_ramp_entry_default(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = pocket_raster(shape, setup, depth_mm=3.0, stepover=3.0, stepdown=3.0)
        assert _has_xyz_ramp(moves)

    def test_pocket_ramp_within_bounds(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = pocket_raster(shape, setup, depth_mm=3.0, stepover=3.0, stepdown=3.0)
        pts = shape.points
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        for m in moves:
            if isinstance(m, CutMove) and m.x is not None:
                assert minx - 0.01 <= m.x <= maxx + 0.01
            if isinstance(m, CutMove) and m.y is not None:
                assert miny - 0.01 <= m.y <= maxy + 0.01


class TestRampFallback:
    def test_short_segment_fallback_plunge(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
        shape = polygon(pts)
        setup = _setup(3.0)
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        assert _has_z_only_plunge(moves)

    def test_short_segment_emits_warning(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
        shape = polygon(pts)
        setup = _setup(3.0)
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        comments = [m for m in moves if isinstance(m, CommentMove)]
        assert any("ramp fallback" in c.text for c in comments)

    def test_ramp_angle_zero_means_plunge(self):
        setup = _setup(0.0)
        shape = _rect_shape()
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        assert _has_z_only_plunge(moves)
        assert not _has_xyz_ramp(moves)


class TestRampFeed:
    def test_ramp_feed_is_feed_xy(self):
        setup = _setup(3.0)
        shape = _rect_shape()
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        ramp_cuts = [
            c
            for c in moves
            if isinstance(c, CutMove) and c.x is not None and c.y is not None and c.z is not None and c.z < 0
        ]
        for c in ramp_cuts:
            if c.feed is not None:
                assert c.feed == setup.tool.feed_xy


class TestRampExplicitXYZ:
    def test_ramp_explicit_xyz(self):
        setup = _setup(3.0)
        shape = _rect_shape()
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        ramp_cuts = [c for c in moves if isinstance(c, CutMove) and c.z is not None and c.z < 0]
        for c in ramp_cuts:
            if _has_xyz_ramp([c]):
                assert c.x is not None
                assert c.y is not None
                assert c.z is not None


class TestProfileKeepdown:
    def test_keepdown_no_intermediate_retracts(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        retracts = [m for m in moves if isinstance(m, RetractMove)]
        assert len(retracts) == 1

    def test_keepdown_final_retract_present(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        non_meta = [
            m for m in moves if not isinstance(m, CommentMove) and not hasattr(m, "rpm") and not hasattr(m, "feed")
        ]
        last_move = non_meta[-1]
        assert isinstance(last_move, RetractMove)

    def test_keepdown_z_progression(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        ramp_cuts = [
            m
            for m in moves
            if isinstance(m, CutMove) and m.x is not None and m.y is not None and m.z is not None and m.z < 0
        ]
        z_values: list[float] = []
        for c in ramp_cuts:
            assert c.z is not None
            z_values.append(c.z)
        for i in range(1, len(z_values)):
            assert z_values[i] <= z_values[i - 1] + 0.01

    def test_keepdown_no_rapids_between_passes(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        rapids = [m for m in moves if isinstance(m, RapidMove)]
        assert len(rapids) == 1

    def test_keepdown_disabled_when_no_ramp(self):
        setup = _setup(0.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        retracts = [m for m in moves if isinstance(m, RetractMove)]
        assert len(retracts) == 3

    def test_keepdown_disabled_for_open_boundary(self):
        from cam.types import Vec2 as V

        open_pts = [V(0.0, 0.0), V(100.0, 0.0), V(100.0, 80.0), V(0.0, 80.0)]
        shape = Shape2D(open_pts)
        setup = _setup(3.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        retracts = [m for m in moves if isinstance(m, RetractMove)]
        assert len(retracts) == 3

    def test_keepdown_single_pass_still_retracts(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=3.0, step_down=3.0)
        retracts = [m for m in moves if isinstance(m, RetractMove)]
        assert len(retracts) == 1

    def test_keepdown_invariant_ends_at_safe(self):
        setup = _setup(3.0)
        shape = _rect_shape(200.0, 200.0)
        moves = profile_outline(shape, setup, depth_mm=9.0, step_down=3.0)
        retract_moves = [m for m in moves if isinstance(m, RetractMove)]
        assert retract_moves[-1].z == setup.safe_z


class TestRampWithHoldingStrategies:
    def test_profile_tabs_with_ramp(self):
        setup = _setup(3.0)
        shape = _rect_shape()
        moves = profile_outline_with_tabs(shape, setup, depth_mm=6.0, step_down_mm=3.0, tab_count=4, tab_height_mm=2.0)
        assert len(moves) > 0
        assert _has_xyz_ramp(moves)

    def test_onion_skin_with_ramp(self):
        setup = _setup(3.0)
        shape = _rect_shape()
        moves = onion_skin_then_finish(shape, setup, total_depth_mm=6.0, skin_mm=0.5, step_down_mm=3.0)
        assert len(moves) > 0
        assert _has_xyz_ramp(moves)
