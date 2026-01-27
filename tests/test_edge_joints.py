import pytest
from domains import Domain, apply_edge_joint, apply_edge_joints
from joints.profiles import FingerJointProfile


class TestApplyEdgeJoint:
    def test_apply_to_bottom_edge(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)

        result = apply_edge_joint(domain, 0, profile)

        assert len(result.outer_boundary) > 4
        assert result.bounds.x_min == pytest.approx(0.0, abs=1e-6)
        assert result.bounds.x_max == pytest.approx(100.0, abs=1e-6)

    def test_apply_to_right_edge(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=3, clearance_mm=0.0)

        result = apply_edge_joint(domain, 1, profile)

        assert len(result.outer_boundary) > 4
        assert result.bounds.x_max >= 100.0

    def test_apply_to_top_edge(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)

        result = apply_edge_joint(domain, 2, profile)

        assert len(result.outer_boundary) > 4
        assert result.bounds.y_max >= 50.0

    def test_apply_to_left_edge(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=3, clearance_mm=0.0)

        result = apply_edge_joint(domain, 3, profile)

        assert len(result.outer_boundary) > 4

    def test_invalid_edge_index_raises(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=5)

        with pytest.raises(IndexError):
            apply_edge_joint(domain, 4, profile)

        with pytest.raises(IndexError):
            apply_edge_joint(domain, -1, profile)

    def test_preserves_inner_boundaries(self):
        outer = Domain.from_rectangle(100, 100, center=(50, 50))
        inner = Domain.from_rectangle(40, 40, center=(50, 50))
        frame_result = outer.subtract(inner)
        frame = frame_result.domains[0]

        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)
        result = apply_edge_joint(frame, 0, profile)

        assert len(result.inner_boundaries) == 1

    def test_preserves_local_origin(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)

        result = apply_edge_joint(domain, 0, profile)

        assert result.local_origin == pytest.approx(domain.local_origin, abs=1e-6)

    def test_preserves_local_rotation(self):
        import math
        domain = Domain.from_rectangle(100, 50, center=(50, 25), rotation_rad=math.pi / 4)
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)

        result = apply_edge_joint(domain, 0, profile)

        assert result.local_rotation_rad == pytest.approx(domain.local_rotation_rad, abs=1e-6)


class TestApplyEdgeJoints:
    def test_apply_multiple_edges(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)

        result = apply_edge_joints(domain, {0: profile, 2: profile})

        assert len(result.outer_boundary) > 4

    def test_apply_all_four_edges(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)

        result = apply_edge_joints(domain, {0: profile, 1: profile, 2: profile, 3: profile})

        assert len(result.outer_boundary) > 4
        assert result.polygon.is_valid

    def test_empty_dict_returns_unchanged(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))

        result = apply_edge_joints(domain, {})

        assert len(result.outer_boundary) == len(domain.outer_boundary)

    def test_different_profiles_per_edge(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile_bottom = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)
        profile_top = FingerJointProfile(depth_mm=6.0, count=7, clearance_mm=0.0)

        result = apply_edge_joints(domain, {0: profile_bottom, 2: profile_top})

        assert result.polygon.is_valid

    def test_phase_0_and_1_on_opposite_edges(self):
        domain = Domain.from_rectangle(100, 50, center=(50, 25))
        profile_phase0 = FingerJointProfile(depth_mm=6.0, count=5, phase=0, clearance_mm=0.0)
        profile_phase1 = FingerJointProfile(depth_mm=6.0, count=5, phase=1, clearance_mm=0.0)

        result = apply_edge_joints(domain, {0: profile_phase0, 2: profile_phase1})

        assert result.polygon.is_valid
