from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from assembly.notches import build_notched_polygon
from assembly.panel import Edge, NotchSpec


def _notch(
    edge: Edge = Edge.BOTTOM,
    u_start: float = 10.0,
    u_len: float = 20.0,
    depth: float = 5.0,
) -> NotchSpec:
    return NotchSpec(edge=edge, u_start_mm=u_start, u_len_mm=u_len, depth_mm=depth)


class TestBuildNotchedPolygonNoNotches:
    def test_returns_rectangle(self):
        pts = build_notched_polygon(100, 50, (50, 25), notches=[])
        assert len(pts) == 4

    def test_center_offset(self):
        pts = build_notched_polygon(100, 50, (100, 200), notches=[])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        assert min(xs) == pytest.approx(50.0)
        assert max(xs) == pytest.approx(150.0)
        assert min(ys) == pytest.approx(175.0)
        assert max(ys) == pytest.approx(225.0)


class TestBuildNotchedPolygonSingleNotch:
    def test_bottom_edge_notch(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[_notch(Edge.BOTTOM, u_start=20, u_len=20, depth=5)],
        )
        assert len(pts) > 4
        ys = [p[1] for p in pts]
        assert min(ys) == pytest.approx(0.0)
        assert max(ys) == pytest.approx(50.0)

    def test_right_edge_notch(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[_notch(Edge.RIGHT, u_start=10, u_len=15, depth=5)],
        )
        assert len(pts) > 4
        xs = [p[0] for p in pts]
        assert max(xs) == pytest.approx(100.0)

    def test_top_edge_notch(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[_notch(Edge.TOP, u_start=10, u_len=20, depth=5)],
        )
        assert len(pts) > 4
        ys = [p[1] for p in pts]
        assert max(ys) == pytest.approx(50.0)

    def test_left_edge_notch(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[_notch(Edge.LEFT, u_start=10, u_len=15, depth=5)],
        )
        assert len(pts) > 4
        xs = [p[0] for p in pts]
        assert min(xs) == pytest.approx(0.0)


class TestBuildNotchedPolygonMultipleNotches:
    def test_two_notches_same_edge(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[
                _notch(Edge.BOTTOM, u_start=5, u_len=10, depth=5),
                _notch(Edge.BOTTOM, u_start=40, u_len=10, depth=5),
            ],
        )
        assert len(pts) > 4

    def test_notches_on_all_edges(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[
                _notch(Edge.BOTTOM, u_start=30, u_len=15, depth=5),
                _notch(Edge.RIGHT, u_start=10, u_len=15, depth=5),
                _notch(Edge.TOP, u_start=30, u_len=15, depth=5),
                _notch(Edge.LEFT, u_start=10, u_len=15, depth=5),
            ],
        )
        assert len(pts) > 4


class TestBuildNotchedPolygonAreaConservation:
    def test_notch_reduces_area(self):
        from shapely.geometry import Polygon

        no_notch = build_notched_polygon(100, 50, (50, 25), notches=[])
        with_notch = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[_notch(Edge.BOTTOM, u_start=10, u_len=30, depth=10)],
        )

        area_full = Polygon(no_notch).area
        area_notched = Polygon(with_notch).area
        assert area_notched < area_full
        assert area_notched > 0


class TestBuildNotchedPolygonEdgeCases:
    @pytest.mark.parametrize("edge", list(Edge))
    def test_notches_removing_the_whole_panel_raise(self, edge):
        length, depth = (100, 50) if edge in (Edge.BOTTOM, Edge.TOP) else (50, 100)
        with pytest.raises(ValueError, match="remove the entire"):
            build_notched_polygon(100, 50, (50, 25), [_notch(edge, 0, length, depth)])

    @pytest.mark.parametrize("center", [(0, 0), (156.35, 306.35)])
    @pytest.mark.parametrize("edge", list(Edge))
    def test_notch_splitting_a_panel_raises_instead_of_selecting_a_fragment(self, edge, center):
        depth = 50 if edge in (Edge.BOTTOM, Edge.TOP) else 100
        with pytest.raises(ValueError, match="2 disconnected pieces"):
            build_notched_polygon(100, 50, center, [_notch(edge, 25, 10, depth)])

    def test_opposing_notches_that_meet_also_raise(self):
        with pytest.raises(ValueError, match="2 disconnected pieces"):
            build_notched_polygon(100, 50, (0, 0), [_notch(Edge.BOTTOM, 25, 10, 25), _notch(Edge.TOP, 25, 10, 25)])

    def test_a_thin_connected_web_is_preserved(self):
        points = build_notched_polygon(
            100, 50, (0, 0), [_notch(Edge.BOTTOM, 25, 10, 24.999), _notch(Edge.TOP, 25, 10, 24.999)]
        )
        assert Polygon(points).area == pytest.approx(4500.02)

    def test_zero_length_notch_rejected_by_spec(self):
        with pytest.raises(ValueError, match="positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=10.0, u_len_mm=0.0, depth_mm=5.0)

    def test_tiny_notch_still_produces_geometry(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[NotchSpec(edge=Edge.BOTTOM, u_start_mm=10.0, u_len_mm=0.001, depth_mm=5.0)],
        )
        assert len(pts) > 4

    def test_invalid_edge_index_skipped(self):
        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=10.0, u_len_mm=20.0, depth_mm=5.0)
        object.__setattr__(notch, "edge", type("FakeEdge", (), {"value": 5})())
        pts = build_notched_polygon(100, 50, (50, 25), notches=[notch])
        assert len(pts) == 4

    def test_overdeep_notch_clamps_to_the_panel_when_one_piece_remains(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=[_notch(Edge.BOTTOM, u_start=0, u_len=20, depth=100)],
        )
        assert Polygon(pts).bounds == (20, 0, 100, 50)
        assert Polygon(pts).area == 4000

    def test_tuple_notches_accepted(self):
        pts = build_notched_polygon(
            100,
            50,
            (50, 25),
            notches=(_notch(Edge.BOTTOM),),
        )
        assert len(pts) > 4
