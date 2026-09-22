from __future__ import annotations

import math
from itertools import pairwise

import pytest
from shapely.geometry import Point as ShapelyPoint

from domains import Domain
from generators.core import GeneratorSkipError
from generators.curves import (
    lissajous_curve_generator,
    rose_curve_generator,
    sample_parametric,
    spirograph_curve_generator,
)
from generators.params.area import LissajousCurveParams, RoseCurveParams, SpirographCurveParams
from layout_ast.layout import Item


def _absolute_points(item: Item) -> list[tuple[float, float]]:
    assert item.placement is not None
    assert item.geometry is not None
    cx, cy = item.placement.center_xy_mm
    return [(cx + x, cy + y) for x, y in item.geometry.data["points"]]


def _piece_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def _cyclic_radius_maxima(points: list[tuple[float, float]], center: tuple[float, float]) -> int:
    ring = points[:-1] if math.dist(points[0], points[-1]) < 1e-9 else points
    radii = [math.dist(p, center) for p in ring]
    n = len(radii)
    return sum(1 for i in range(n) if radii[i] > radii[i - 1] and radii[i] >= radii[(i + 1) % n])


def _axis_maxima(points: list[tuple[float, float]], axis: int) -> int:
    ring = points[:-1] if math.dist(points[0], points[-1]) < 1e-9 else points
    values = [p[axis] for p in ring]
    n = len(values)
    return sum(1 for i in range(n) if values[i] > values[i - 1] and values[i] >= values[(i + 1) % n])


def _cyclic_radius_minima(points: list[tuple[float, float]], center: tuple[float, float]) -> int:
    ring = points[:-1] if math.dist(points[0], points[-1]) < 1e-9 else points
    radii = [math.dist(p, center) for p in ring]
    n = len(radii)
    return sum(1 for i in range(n) if radii[i] < radii[i - 1] and radii[i] <= radii[(i + 1) % n])


class TestSampleParametric:
    def test_straight_line_uses_only_seed_points(self):
        points = sample_parametric(lambda t: (t, 0.0), 0.0, 10.0, tolerance_mm=0.01, initial_segments=5)
        assert len(points) == 6
        assert points[0] == (0.0, 0.0)
        assert points[-1] == (10.0, 0.0)

    def test_circle_refines_to_tolerance(self):
        points = sample_parametric(
            lambda t: (math.cos(t), math.sin(t)),
            0.0,
            2 * math.pi,
            tolerance_mm=0.01,
            initial_segments=8,
        )
        assert len(points) > 9
        for a, b in pairwise(points):
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            assert 1.0 - math.hypot(*mid) <= 0.01 + 1e-9

    def test_coarse_seed_still_refines_lobes(self):
        def bump(t: float) -> tuple[float, float]:
            return (t, math.exp(-((t - 0.5) ** 2) / 0.002))

        points = sample_parametric(bump, 0.0, 1.0, tolerance_mm=0.01, initial_segments=1)
        assert any(abs(x - 0.5) < 0.02 and y > 0.98 for x, y in points)

    def test_point_budget_raises(self):
        with pytest.raises(ValueError, match="point budget"):
            sample_parametric(
                lambda t: (math.cos(t), math.sin(t)),
                0.0,
                2 * math.pi,
                tolerance_mm=1e-9,
                initial_segments=8,
                max_points=100,
            )

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"tolerance_mm": 0.0, "initial_segments": 4}, id="zero_tolerance"),
            pytest.param({"tolerance_mm": 0.1, "initial_segments": 0}, id="zero_segments"),
        ],
    )
    def test_invalid_arguments_raise(self, kwargs):
        with pytest.raises(ValueError):
            sample_parametric(lambda t: (t, 0.0), 0.0, 1.0, **kwargs)

    def test_reversed_range_raises(self):
        with pytest.raises(ValueError, match="t_end"):
            sample_parametric(lambda t: (t, 0.0), 1.0, 1.0, tolerance_mm=0.1, initial_segments=4)


class TestRoseCurveParams:
    def test_rejects_lobes_below_one(self):
        with pytest.raises(ValueError, match="lobes"):
            RoseCurveParams(lobes=0, depth_mm=0.3)

    def test_rejects_nonpositive_tolerance(self):
        with pytest.raises(ValueError, match="tolerance_mm"):
            RoseCurveParams(lobes=3, depth_mm=0.3, tolerance_mm=0.0)


class TestRoseCurveGenerator:
    def _square(self) -> Domain:
        return Domain.from_rectangle(200, 200, center=(100, 100))

    def test_closes_on_itself(self):
        items = rose_curve_generator(self._square(), RoseCurveParams(lobes=5, depth_mm=0.3))
        assert len(items) == 1
        points = _absolute_points(items[0])
        assert points[0] == points[-1]
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is False
        assert all(math.dist(a, b) > 0 for a, b in pairwise(points))

    def test_odd_lobes_petal_count(self):
        items = rose_curve_generator(self._square(), RoseCurveParams(lobes=5, depth_mm=0.3))
        assert _cyclic_radius_maxima(_absolute_points(items[0]), (100, 100)) == 5

    def test_even_lobes_petal_count(self):
        items = rose_curve_generator(self._square(), RoseCurveParams(lobes=4, depth_mm=0.3))
        assert _cyclic_radius_maxima(_absolute_points(items[0]), (100, 100)) == 8

    def test_default_size_is_90_percent(self):
        domain = Domain.from_rectangle(200, 100, center=(100, 50))
        items = rose_curve_generator(domain, RoseCurveParams(lobes=3, depth_mm=0.3))
        max_radius = max(math.dist(p, (100, 50)) for p in _absolute_points(items[0]))
        assert max_radius == pytest.approx(45.0, abs=0.05)

    def test_rotation_moves_first_petal(self):
        base = rose_curve_generator(self._square(), RoseCurveParams(lobes=3, depth_mm=0.3))
        rotated = rose_curve_generator(self._square(), RoseCurveParams(lobes=3, depth_mm=0.3, rotation_deg=30.0))

        def first_petal_angle(items: list[Item]) -> float:
            start = _absolute_points(items[0])[0]
            assert math.dist(start, (100, 100)) == pytest.approx(90.0)
            return math.degrees(math.atan2(start[1] - 100, start[0] - 100))

        assert first_petal_angle(rotated) - first_petal_angle(base) == pytest.approx(30.0, abs=0.5)

    def test_clips_to_circle_domain(self):
        domain = Domain.from_circle(200, center=(100, 100))
        items = rose_curve_generator(domain, RoseCurveParams(lobes=3, depth_mm=0.3, size_mm=240.0))
        assert len(items) > 1
        inflated = domain.polygon.buffer(1e-6)
        for item in items:
            assert item.geometry is not None
            assert item.geometry.data["is_open"] is True
            for x, y in _absolute_points(item):
                assert inflated.contains(ShapelyPoint(x, y))

    def test_clipped_closed_curve_joins_at_start_point(self):
        domain = Domain.from_rectangle(300, 120, center=(150, 60))
        items = rose_curve_generator(domain, RoseCurveParams(lobes=3, depth_mm=0.3, size_mm=240.0))
        assert len(items) > 1
        start = (150 + 120, 60)
        for item in items:
            points = _absolute_points(item)
            assert math.dist(points[-1], start) > 1e-6

    def test_min_length_drops_short_pieces(self):
        domain = Domain.from_circle(200, center=(100, 100))
        items = rose_curve_generator(domain, RoseCurveParams(lobes=3, depth_mm=0.3, size_mm=240.0, min_length_mm=50.0))
        assert items
        for item in items:
            assert _piece_length(_absolute_points(item)) >= 50.0

    def test_deterministic(self):
        params = RoseCurveParams(lobes=7, depth_mm=0.3, rotation_deg=10.0)
        first = rose_curve_generator(self._square(), params)
        second = rose_curve_generator(self._square(), params)
        assert [i.geometry.data for i in first if i.geometry] == [i.geometry.data for i in second if i.geometry]

    def test_outside_domain_skips_or_empty(self):
        domain = Domain(
            outer_boundary=((0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)),
            local_origin=(500.0, 500.0),
        )
        params = RoseCurveParams(lobes=3, depth_mm=0.3, size_mm=40.0)
        with pytest.raises(GeneratorSkipError):
            rose_curve_generator(domain, params)
        assert rose_curve_generator(domain, params, allow_empty=True) == []


class TestSpirographCurveParams:
    def test_inside_requires_rolling_smaller(self):
        with pytest.raises(ValueError, match="rolling_radius"):
            SpirographCurveParams(fixed_radius_mm=20, rolling_radius_mm=20, pen_offset_mm=5, depth_mm=0.3)

    def test_outside_allows_larger_rolling(self):
        SpirographCurveParams(fixed_radius_mm=20, rolling_radius_mm=30, pen_offset_mm=5, depth_mm=0.3, mode="outside")

    def test_rejects_negative_pen_offset(self):
        with pytest.raises(ValueError, match="pen_offset"):
            SpirographCurveParams(fixed_radius_mm=60, rolling_radius_mm=21, pen_offset_mm=-1, depth_mm=0.3)

    def test_rejects_bad_mode(self):
        with pytest.raises(ValueError, match="mode"):
            SpirographCurveParams(
                fixed_radius_mm=60,
                rolling_radius_mm=21,
                pen_offset_mm=5,
                depth_mm=0.3,
                mode="around",  # type: ignore[arg-type]
            )

    def test_rejects_zero_revolutions(self):
        with pytest.raises(ValueError, match="revolutions"):
            SpirographCurveParams(
                fixed_radius_mm=60, rolling_radius_mm=21, pen_offset_mm=5, depth_mm=0.3, revolutions=0
            )


class TestSpirographCurveGenerator:
    def _square(self) -> Domain:
        return Domain.from_rectangle(300, 300, center=(150, 150))

    def _params(self, **overrides) -> SpirographCurveParams:
        base = {"fixed_radius_mm": 60.0, "rolling_radius_mm": 21.0, "pen_offset_mm": 15.0, "depth_mm": 0.3}
        return SpirographCurveParams(**{**base, **overrides})

    def test_closes_after_reduced_denominator_turns(self):
        items = spirograph_curve_generator(self._square(), self._params())
        assert len(items) == 1
        points = _absolute_points(items[0])
        assert points[0] == points[-1]
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is False
        assert _cyclic_radius_maxima(points, (150, 150)) == 20

    def test_epitrochoid_closes(self):
        items = spirograph_curve_generator(self._square(), self._params(mode="outside"))
        assert len(items) == 1
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is False

    def test_hypocycloid_three_cusps(self):
        items = spirograph_curve_generator(self._square(), self._params(rolling_radius_mm=20.0, pen_offset_mm=20.0))
        points = _absolute_points(items[0])
        assert _cyclic_radius_minima(points, (150, 150)) == 3
        assert min(math.dist(p, (150, 150)) for p in points) == pytest.approx(20.0, abs=0.1)

    def test_pen_offset_zero_is_circle(self):
        items = spirograph_curve_generator(self._square(), self._params(rolling_radius_mm=20.0, pen_offset_mm=0.0))
        for p in _absolute_points(items[0]):
            assert math.dist(p, (150, 150)) == pytest.approx(40.0, abs=0.1)

    def test_revolutions_not_multiple_is_open(self):
        items = spirograph_curve_generator(self._square(), self._params(revolutions=3))
        assert len(items) == 1
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is True
        points = _absolute_points(items[0])
        assert math.dist(points[0], points[-1]) > 1.0

    def test_size_scales_outer_diameter(self):
        items = spirograph_curve_generator(self._square(), self._params(size_mm=100.0))
        max_radius = max(math.dist(p, (150, 150)) for p in _absolute_points(items[0]))
        assert max_radius == pytest.approx(50.0, abs=0.1)

    def test_large_denominator_raises(self):
        with pytest.raises(ValueError, match="revolutions"):
            spirograph_curve_generator(self._square(), self._params(rolling_radius_mm=21.001))

    def test_near_miss_ratio_closes_within_tolerance(self):
        items = spirograph_curve_generator(self._square(), self._params(rolling_radius_mm=21.37))
        assert len(items) == 1
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is False

    def test_near_miss_ratio_stays_open_under_tight_tolerance(self):
        items = spirograph_curve_generator(self._square(), self._params(rolling_radius_mm=21.37, tolerance_mm=0.01))
        assert len(items) == 1
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is True

    def test_clips_to_circle_domain(self):
        domain = Domain.from_circle(80, center=(150, 150))
        items = spirograph_curve_generator(domain, self._params())
        assert len(items) > 1
        inflated = domain.polygon.buffer(1e-6)
        for item in items:
            for x, y in _absolute_points(item):
                assert inflated.contains(ShapelyPoint(x, y))

    def test_deterministic(self):
        params = self._params(rotation_deg=12.0)
        first = spirograph_curve_generator(self._square(), params)
        second = spirograph_curve_generator(self._square(), params)
        assert [i.geometry.data for i in first if i.geometry] == [i.geometry.data for i in second if i.geometry]


class TestLissajousCurveParams:
    def test_rejects_zero_frequency(self):
        with pytest.raises(ValueError, match="frequency_x"):
            LissajousCurveParams(frequency_x=0, frequency_y=2, depth_mm=0.3)

    def test_rejects_nonpositive_width(self):
        with pytest.raises(ValueError, match="width_mm"):
            LissajousCurveParams(frequency_x=3, frequency_y=2, depth_mm=0.3, width_mm=0.0)


class TestLissajousCurveGenerator:
    def _square(self) -> Domain:
        return Domain.from_rectangle(200, 200, center=(100, 100))

    def _params(self, **overrides) -> LissajousCurveParams:
        base = {"frequency_x": 3, "frequency_y": 2, "depth_mm": 0.3}
        return LissajousCurveParams(**{**base, **overrides})

    def _extents(self, items: list[Item], center: tuple[float, float]) -> tuple[float, float]:
        points = _absolute_points(items[0])
        return (
            max(abs(x - center[0]) for x, _ in points),
            max(abs(y - center[1]) for _, y in points),
        )

    def test_closes_on_itself(self):
        items = lissajous_curve_generator(self._square(), self._params())
        assert len(items) == 1
        points = _absolute_points(items[0])
        assert points[0] == points[-1]
        assert items[0].geometry is not None
        assert items[0].geometry.data["is_open"] is False

    def test_axis_maxima_match_frequencies(self):
        items = lissajous_curve_generator(self._square(), self._params())
        points = _absolute_points(items[0])
        assert _axis_maxima(points, 0) == 3
        assert _axis_maxima(points, 1) == 2

    def test_common_factor_is_reduced(self):
        reduced = lissajous_curve_generator(self._square(), self._params(frequency_x=3, frequency_y=2))
        unreduced = lissajous_curve_generator(self._square(), self._params(frequency_x=6, frequency_y=4))
        assert [i.geometry.data for i in reduced if i.geometry] == [i.geometry.data for i in unreduced if i.geometry]

    def test_equal_frequencies_quarter_phase_is_ellipse(self):
        items = lissajous_curve_generator(
            self._square(), self._params(frequency_x=1, frequency_y=1, width_mm=160.0, height_mm=100.0)
        )
        assert self._extents(items, (100, 100)) == pytest.approx((80.0, 50.0), abs=0.1)

    def test_equal_frequencies_zero_phase_is_line(self):
        items = lissajous_curve_generator(
            self._square(),
            self._params(frequency_x=1, frequency_y=1, phase_deg=0.0, width_mm=160.0, height_mm=100.0),
        )
        for x, y in _absolute_points(items[0]):
            assert abs((y - 100) / 50 - (x - 100) / 80) < 1e-3

    def test_box_defaults_to_90_percent(self):
        domain = Domain.from_rectangle(200, 100, center=(100, 50))
        items = lissajous_curve_generator(domain, self._params())
        assert self._extents(items, (100, 50)) == pytest.approx((90.0, 45.0), abs=0.1)

    def test_size_fills_missing_dimensions(self):
        items = lissajous_curve_generator(self._square(), self._params(size_mm=120.0, width_mm=160.0))
        assert self._extents(items, (100, 100)) == pytest.approx((80.0, 60.0), abs=0.1)

    def test_rotation_rotates_box(self):
        items = lissajous_curve_generator(
            self._square(),
            self._params(frequency_x=1, frequency_y=1, width_mm=160.0, height_mm=100.0, rotation_deg=90.0),
        )
        assert self._extents(items, (100, 100)) == pytest.approx((50.0, 80.0), abs=0.1)

    def test_clips_to_circle_domain(self):
        domain = Domain.from_circle(100, center=(100, 100))
        items = lissajous_curve_generator(domain, self._params(size_mm=140.0))
        assert len(items) > 1
        inflated = domain.polygon.buffer(1e-6)
        for item in items:
            for x, y in _absolute_points(item):
                assert inflated.contains(ShapelyPoint(x, y))

    def test_deterministic(self):
        params = self._params(frequency_x=5, frequency_y=4, phase_deg=45.0)
        first = lissajous_curve_generator(self._square(), params)
        second = lissajous_curve_generator(self._square(), params)
        assert [i.geometry.data for i in first if i.geometry] == [i.geometry.data for i in second if i.geometry]
