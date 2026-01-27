import math
import pytest
from joints.profiles import FingerJointProfile


class TestFingerJointProfile:
    def test_validation_requires_width_or_count(self):
        with pytest.raises(ValueError, match="exactly one"):
            FingerJointProfile(depth_mm=6.0)

        with pytest.raises(ValueError, match="exactly one"):
            FingerJointProfile(depth_mm=6.0, width_mm=10.0, count=5)

    def test_validation_positive_values(self):
        with pytest.raises(ValueError, match="depth_mm must be positive"):
            FingerJointProfile(depth_mm=0, width_mm=10.0)

        with pytest.raises(ValueError, match="width_mm must be positive"):
            FingerJointProfile(depth_mm=6.0, width_mm=-1.0)

        with pytest.raises(ValueError, match="count must be at least 1"):
            FingerJointProfile(depth_mm=6.0, count=0)

    def test_by_count_creates_profile(self):
        profile = FingerJointProfile(depth_mm=6.0, count=5)
        assert profile.depth_mm == 6.0
        assert profile.count == 5
        assert profile.width_mm is None

    def test_by_width_creates_profile(self):
        profile = FingerJointProfile(depth_mm=6.0, width_mm=12.0)
        assert profile.depth_mm == 6.0
        assert profile.width_mm == 12.0
        assert profile.count is None

    def test_compute_edge_geometry_basic(self):
        profile = FingerJointProfile(depth_mm=6.0, count=3, clearance_mm=0.0)
        edge_start = (0.0, 0.0)
        edge_end = (30.0, 0.0)

        vertices = profile.compute_edge_geometry(edge_start, edge_end)

        assert len(vertices) > 2
        assert vertices[0][0] == pytest.approx(0.0, abs=1e-6)
        assert vertices[-1][0] == pytest.approx(30.0, abs=1e-6)

    def test_compute_edge_geometry_phase_0_starts_with_finger(self):
        profile = FingerJointProfile(depth_mm=6.0, count=3, phase=0, clearance_mm=0.0)
        edge_start = (0.0, 0.0)
        edge_end = (30.0, 0.0)

        vertices = profile.compute_edge_geometry(edge_start, edge_end)

        assert vertices[0][1] == pytest.approx(-6.0, abs=1e-6)

    def test_compute_edge_geometry_phase_1_starts_with_notch(self):
        profile = FingerJointProfile(depth_mm=6.0, count=3, phase=1, clearance_mm=0.0)
        edge_start = (0.0, 0.0)
        edge_end = (30.0, 0.0)

        vertices = profile.compute_edge_geometry(edge_start, edge_end)

        assert vertices[0][1] == pytest.approx(0.0, abs=1e-6)

    def test_finger_count_forced_odd(self):
        profile = FingerJointProfile(depth_mm=6.0, count=4, clearance_mm=0.0)

        count = profile._compute_finger_count(100.0)
        assert count == 5

    def test_finger_count_minimum_three(self):
        profile = FingerJointProfile(depth_mm=6.0, count=1, clearance_mm=0.0)

        count = profile._compute_finger_count(100.0)
        assert count == 3

    def test_by_width_computes_count(self):
        profile = FingerJointProfile(depth_mm=6.0, width_mm=10.0, clearance_mm=0.0)

        count = profile._compute_finger_count(100.0)
        assert count % 2 == 1
        assert count >= 3

    def test_vertical_edge(self):
        profile = FingerJointProfile(depth_mm=6.0, count=3, phase=0, clearance_mm=0.0)
        edge_start = (0.0, 0.0)
        edge_end = (0.0, 30.0)

        vertices = profile.compute_edge_geometry(edge_start, edge_end)

        assert len(vertices) > 2
        assert vertices[0][0] == pytest.approx(6.0, abs=1e-6)
        assert vertices[0][1] == pytest.approx(0.0, abs=1e-6)

    def test_diagonal_edge(self):
        profile = FingerJointProfile(depth_mm=6.0, count=3, clearance_mm=0.0)
        edge_start = (0.0, 0.0)
        edge_end = (30.0, 30.0)

        vertices = profile.compute_edge_geometry(edge_start, edge_end)

        assert len(vertices) > 2
        start_dist = math.sqrt(vertices[0][0]**2 + vertices[0][1]**2)
        assert start_dist == pytest.approx(6.0, abs=1e-6) or start_dist == pytest.approx(0.0, abs=1e-6)
