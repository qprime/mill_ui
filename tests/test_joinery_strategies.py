import pytest

from assembly.core import Interface, InterfaceType
from assembly.panel import PanelSpec, Edge, NotchSpec
from assembly.joinery import Butt, Finger


class TestButtJoineryStrategy:
    def test_valid_for_all_interfaces(self):
        strategy = Butt()
        for itype in InterfaceType:
            assert itype in strategy.valid_interfaces

    def test_returns_no_notches(self):
        strategy = Butt()
        panel_a = PanelSpec(name="a", width_mm=100, height_mm=50, thickness_mm=6.0)
        panel_b = PanelSpec(name="b", width_mm=50, height_mm=100, thickness_mm=6.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", strategy)
        result_a, result_b = strategy.apply(interface, panel_a, panel_b)
        assert len(result_a.notches) == 0
        assert len(result_b.notches) == 0


class TestFingerJoineryStrategy:
    def test_valid_for_side_to_side(self):
        strategy = Finger(width_mm=12.0)
        assert InterfaceType.SIDE_TO_SIDE in strategy.valid_interfaces

    def test_valid_for_top(self):
        strategy = Finger(width_mm=12.0)
        assert InterfaceType.TOP in strategy.valid_interfaces

    def test_valid_for_bottom(self):
        strategy = Finger(width_mm=12.0)
        assert InterfaceType.BOTTOM in strategy.valid_interfaces

    def test_not_valid_for_internal(self):
        strategy = Finger(width_mm=12.0)
        assert InterfaceType.INTERNAL not in strategy.valid_interfaces

    def test_returns_finger_notches(self):
        strategy = Finger(width_mm=12.0, clearance_mm=0.1)
        panel_a = PanelSpec(name="front", width_mm=100, height_mm=50, thickness_mm=6.0)
        panel_b = PanelSpec(name="left_side", width_mm=50, height_mm=50, thickness_mm=6.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", strategy)
        result_a, result_b = strategy.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) > 0
        assert len(result_b.notches) > 0
        assert all(isinstance(n, NotchSpec) for n in result_a.notches)
        assert all(isinstance(n, NotchSpec) for n in result_b.notches)
        assert all(n.depth_mm == 6.0 for n in result_a.notches)
        assert all(n.depth_mm == 6.0 for n in result_b.notches)

    def test_finger_count_mode(self):
        strategy = Finger(count=5, clearance_mm=0.15)
        panel_a = PanelSpec(name="front", width_mm=100, height_mm=50, thickness_mm=6.0)
        panel_b = PanelSpec(name="left_side", width_mm=50, height_mm=50, thickness_mm=6.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", strategy)
        result_a, result_b = strategy.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) > 0
        assert len(result_b.notches) > 0

    def test_default_clearance(self):
        strategy = Finger(width_mm=12.0)
        assert strategy.clearance_mm == 0.12

    def test_phase_alternation(self):
        strategy = Finger(width_mm=12.0)
        panel_a = PanelSpec(name="front", width_mm=100, height_mm=50, thickness_mm=6.0)
        panel_b = PanelSpec(name="left_side", width_mm=50, height_mm=50, thickness_mm=6.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", strategy)
        result_a, result_b = strategy.apply(interface, panel_a, panel_b)

        positions_a = set(n.u_start_mm for n in result_a.notches)
        positions_b = set(n.u_start_mm for n in result_b.notches)
        assert positions_a != positions_b
