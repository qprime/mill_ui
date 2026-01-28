import pytest

from assembly.joinery import ButtJoineryStrategy, FingerJoineryStrategy
from assembly.topology import FaceSpec, MatingEdge
from assembly.notches import NotchSpec


class TestButtJoineryStrategy:
    def test_supports_any_angle(self):
        strategy = ButtJoineryStrategy()
        assert strategy.supports_angle(90.0)
        assert strategy.supports_angle(45.0)
        assert strategy.supports_angle(120.0)

    def test_returns_no_notches(self):
        strategy = ButtJoineryStrategy()
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (50, 0), (50, 100), (0, 100)), thickness_mm=6.0),
        }
        edge = MatingEdge(face_a="a", edge_index_a=1, face_b="b", edge_index_b=3)
        notches_a, notches_b = strategy.compute_notches(edge, faces, 0, 1)
        assert len(notches_a) == 0
        assert len(notches_b) == 0

    def test_joinery_type(self):
        strategy = ButtJoineryStrategy()
        assert strategy.joinery_type == "butt"


class TestFingerJoineryStrategy:
    def test_supports_90_degrees(self):
        strategy = FingerJoineryStrategy(finger_width_mm=12.0)
        assert strategy.supports_angle(90.0)
        assert strategy.supports_angle(89.5)
        assert strategy.supports_angle(90.5)

    def test_does_not_support_non_90_angles(self):
        strategy = FingerJoineryStrategy(finger_width_mm=12.0)
        assert not strategy.supports_angle(45.0)
        assert not strategy.supports_angle(70.5)
        assert not strategy.supports_angle(120.0)

    def test_returns_finger_notches(self):
        strategy = FingerJoineryStrategy(finger_width_mm=12.0, clearance_mm=0.1)
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (50, 0), (50, 100), (0, 100)), thickness_mm=6.0),
        }
        edge = MatingEdge(face_a="a", edge_index_a=1, face_b="b", edge_index_b=3)
        notches_a, notches_b = strategy.compute_notches(edge, faces, 0, 1)

        assert len(notches_a) > 0
        assert len(notches_b) > 0
        assert all(isinstance(n, NotchSpec) for n in notches_a)
        assert all(isinstance(n, NotchSpec) for n in notches_b)
        assert all(n.edge_index == 1 for n in notches_a)
        assert all(n.edge_index == 3 for n in notches_b)
        assert all(n.depth_mm == 6.0 for n in notches_a)
        assert all(n.depth_mm == 6.0 for n in notches_b)

    def test_finger_count_mode(self):
        strategy = FingerJoineryStrategy(finger_count=5, clearance_mm=0.15)
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (50, 0), (50, 100), (0, 100)), thickness_mm=6.0),
        }
        edge = MatingEdge(face_a="a", edge_index_a=1, face_b="b", edge_index_b=3)
        notches_a, notches_b = strategy.compute_notches(edge, faces, 0, 1)

        assert len(notches_a) > 0
        assert len(notches_b) > 0

    def test_joinery_type(self):
        strategy = FingerJoineryStrategy(finger_width_mm=12.0)
        assert strategy.joinery_type == "finger"

    def test_default_clearance(self):
        strategy = FingerJoineryStrategy(finger_width_mm=12.0)
        assert strategy.clearance_mm == 0.12

    def test_phase_alternation(self):
        strategy = FingerJoineryStrategy(finger_width_mm=12.0)
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (50, 0), (50, 100), (0, 100)), thickness_mm=6.0),
        }
        edge = MatingEdge(face_a="a", edge_index_a=1, face_b="b", edge_index_b=3)
        notches_a, notches_b = strategy.compute_notches(edge, faces, 0, 1)

        positions_a = set(n.u_start_mm for n in notches_a)
        positions_b = set(n.u_start_mm for n in notches_b)
        assert positions_a != positions_b
