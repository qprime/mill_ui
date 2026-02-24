import pytest

from assembly.notches import (
    finger_joints_to_notches,
    notch_to_polyline,
    validate_notch_fits_edge,
    validate_notches_no_overlap,
)
from assembly.panel import Edge, NotchSpec


class TestNotchSpec:
    def test_basic_creation(self):
        notch = NotchSpec(
            edge=Edge.BOTTOM,
            u_start_mm=10.0,
            u_len_mm=20.0,
            depth_mm=6.0,
        )
        assert notch.edge == Edge.BOTTOM
        assert notch.edge_index == 0
        assert notch.u_start_mm == 10.0
        assert notch.u_len_mm == 20.0
        assert notch.depth_mm == 6.0
        assert notch.shape == "rectangular"

    def test_invalid_edge_value_raises(self):
        with pytest.raises(ValueError):
            NotchSpec(edge=Edge(-1), u_start_mm=0, u_len_mm=10, depth_mm=5)

    def test_negative_u_start_raises(self):
        with pytest.raises(ValueError, match="u_start_mm must be non-negative"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=-5, u_len_mm=10, depth_mm=5)

    def test_zero_u_len_raises(self):
        with pytest.raises(ValueError, match="u_len_mm must be positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=0, depth_mm=5)

    def test_zero_depth_raises(self):
        with pytest.raises(ValueError, match="depth_mm must be positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=10, depth_mm=0)

    def test_with_corner_radius(self):
        notch = NotchSpec(
            edge=Edge.BOTTOM,
            u_start_mm=0,
            u_len_mm=20,
            depth_mm=10,
            shape_params={"corner_radius_mm": 2.0},
        )
        assert notch.shape_params["corner_radius_mm"] == 2.0


class TestValidateNotchFitsEdge:
    def test_notch_fits(self):
        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=10, u_len_mm=20, depth_mm=5)
        validate_notch_fits_edge(notch, edge_length=100)

    def test_notch_at_edge_boundary(self):
        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=80, u_len_mm=20, depth_mm=5)
        validate_notch_fits_edge(notch, edge_length=100)

    def test_notch_exceeds_edge_raises(self):
        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=90, u_len_mm=20, depth_mm=5)
        with pytest.raises(ValueError, match="exceeds edge length"):
            validate_notch_fits_edge(notch, edge_length=100)


class TestValidateNotchesNoOverlap:
    def test_no_overlap(self):
        notches = [
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=10, depth_mm=5),
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=20, u_len_mm=10, depth_mm=5),
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=40, u_len_mm=10, depth_mm=5),
        ]
        validate_notches_no_overlap(notches)

    def test_adjacent_notches_ok(self):
        notches = [
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=10, depth_mm=5),
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=10, u_len_mm=10, depth_mm=5),
        ]
        validate_notches_no_overlap(notches)

    def test_overlapping_notches_raises(self):
        notches = [
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=15, depth_mm=5),
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=10, u_len_mm=15, depth_mm=5),
        ]
        with pytest.raises(ValueError, match="Overlapping notches"):
            validate_notches_no_overlap(notches)

    def test_notches_on_different_edges_ok(self):
        notches = [
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=50, depth_mm=5),
            NotchSpec(edge=Edge.RIGHT, u_start_mm=0, u_len_mm=50, depth_mm=5),
        ]
        validate_notches_no_overlap(notches)


class TestNotchToPolyline:
    def test_basic_rectangular_notch_bottom_edge(self):
        polygon = ((0, 0), (100, 0), (100, 50), (0, 50))
        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=20, u_len_mm=20, depth_mm=10)

        pts = notch_to_polyline(polygon, notch)

        assert len(pts) == 4
        assert pts[0] == pytest.approx((20, 0), abs=1e-6)
        assert pts[1] == pytest.approx((20, 10), abs=1e-6)
        assert pts[2] == pytest.approx((40, 10), abs=1e-6)
        assert pts[3] == pytest.approx((40, 0), abs=1e-6)

    def test_notch_on_right_edge(self):
        polygon = ((0, 0), (100, 0), (100, 50), (0, 50))
        notch = NotchSpec(edge=Edge.RIGHT, u_start_mm=10, u_len_mm=15, depth_mm=8)

        pts = notch_to_polyline(polygon, notch)

        assert len(pts) == 4
        assert pts[0][0] == pytest.approx(100, abs=1e-6)
        assert pts[0][1] == pytest.approx(10, abs=1e-6)

    def test_notch_on_top_edge(self):
        polygon = ((0, 0), (100, 0), (100, 50), (0, 50))
        notch = NotchSpec(edge=Edge.TOP, u_start_mm=30, u_len_mm=20, depth_mm=10)

        pts = notch_to_polyline(polygon, notch)

        assert len(pts) == 4
        assert pts[0][1] == pytest.approx(50, abs=1e-6)

    def test_notch_on_left_edge(self):
        polygon = ((0, 0), (100, 0), (100, 50), (0, 50))
        notch = NotchSpec(edge=Edge.LEFT, u_start_mm=10, u_len_mm=20, depth_mm=10)

        pts = notch_to_polyline(polygon, notch)

        assert len(pts) == 4
        assert pts[0][0] == pytest.approx(0, abs=1e-6)

    def test_invalid_edge_index_raises(self):
        with pytest.raises(ValueError):
            Edge(4)


class TestFingerJointsToNotches:
    def test_basic_finger_joints_count(self):
        notches = finger_joints_to_notches(
            edge_index=0,
            edge_length=100,
            depth_mm=6,
            phase=0,
            count=5,
        )

        assert len(notches) > 0
        assert all(isinstance(n, NotchSpec) for n in notches)

    def test_phase_0_vs_phase_1(self):
        notches_phase0 = finger_joints_to_notches(
            edge_index=0,
            edge_length=100,
            depth_mm=6,
            phase=0,
            count=5,
        )
        notches_phase1 = finger_joints_to_notches(
            edge_index=0,
            edge_length=100,
            depth_mm=6,
            phase=1,
            count=5,
        )

        positions_0 = set(n.u_start_mm for n in notches_phase0)
        positions_1 = set(n.u_start_mm for n in notches_phase1)
        assert positions_0 != positions_1

    def test_finger_joints_width_based(self):
        notches = finger_joints_to_notches(
            edge_index=0,
            edge_length=100,
            depth_mm=6,
            phase=0,
            width_mm=10,
        )

        assert len(notches) > 0

    def test_must_specify_one_of_width_or_count(self):
        with pytest.raises(ValueError, match="Specify exactly one"):
            finger_joints_to_notches(
                edge_index=0,
                edge_length=100,
                depth_mm=6,
                phase=0,
            )

    def test_finger_joints_all_have_same_depth(self):
        notches = finger_joints_to_notches(
            edge_index=0,
            edge_length=100,
            depth_mm=6,
            phase=0,
            count=5,
        )

        for notch in notches:
            assert notch.depth_mm == 6

    def test_finger_joints_same_edge_index(self):
        notches = finger_joints_to_notches(
            edge_index=2,
            edge_length=100,
            depth_mm=6,
            phase=0,
            count=5,
        )

        for notch in notches:
            assert notch.edge_index == 2

    def test_clearance_represents_total_looseness(self):
        edge_length = 100.0
        count = 7
        clearance = 0.2
        finger_width = edge_length / count

        notches = finger_joints_to_notches(
            edge_index=0,
            edge_length=edge_length,
            depth_mm=6,
            phase=0,
            count=count,
            clearance_mm=clearance,
        )

        i = 3
        expected_start = i * finger_width - clearance / 4
        notch = min(notches, key=lambda n: abs(n.u_start_mm - expected_start))
        assert notch.u_start_mm == pytest.approx(expected_start)

        assert notch.u_len_mm == pytest.approx(finger_width + clearance / 2)
