import pytest

from assembly.core import Assembly, Interface, InterfaceType
from assembly.panel import PanelSpec, PanelRole, Edge, NotchSpec, DadoSpec
from assembly.joinery import Butt, Finger, Step, Rabbet, HalfLap, Captured, Dado


class TestButtJoinery:
    def test_returns_unchanged_panels(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", Butt())

        result_a, result_b = Butt().apply(interface, panel_a, panel_b)

        assert result_a.notches == ()
        assert result_b.notches == ()
        assert result_a.dados == ()
        assert result_b.dados == ()


class TestFingerJoinery:
    def test_creates_notches_on_both_panels(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", Finger(width_mm=12))

        result_a, result_b = Finger(width_mm=12).apply(interface, panel_a, panel_b)

        assert len(result_a.notches) > 0
        assert len(result_b.notches) > 0

    def test_notch_depth_equals_mating_panel_thickness(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 8)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", Finger(width_mm=12))

        result_a, result_b = Finger(width_mm=12).apply(interface, panel_a, panel_b)

        for notch in result_a.notches:
            assert notch.depth_mm == 8
        for notch in result_b.notches:
            assert notch.depth_mm == 6

    def test_notches_alternate_between_panels(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", Finger(width_mm=10))

        result_a, result_b = Finger(width_mm=10).apply(interface, panel_a, panel_b)

        positions_a = {n.u_start_mm for n in result_a.notches}
        positions_b = {n.u_start_mm for n in result_b.notches}

        assert positions_a.isdisjoint(positions_b)

    def test_odd_finger_count(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", Finger(width_mm=12))

        result_a, result_b = Finger(width_mm=12).apply(interface, panel_a, panel_b)

        total_notches = len(result_a.notches) + len(result_b.notches)
        assert total_notches >= 3

    def test_clearance_applied(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        clearance = 0.2
        finger = Finger(width_mm=25, clearance_mm=clearance)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", finger)

        result_a, result_b = finger.apply(interface, panel_a, panel_b)

        for notch in result_a.notches:
            if notch.u_start_mm > 0.1 and notch.u_start_mm + notch.u_len_mm < 49.9:
                expected_width = 50 / 3 + clearance / 2
                assert abs(notch.u_len_mm - expected_width) < 0.5

    def test_finger_count_mode(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        finger = Finger(count=5)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", finger)

        result_a, result_b = finger.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) > 0
        assert len(result_b.notches) > 0


class TestStepJoinery:
    def test_creates_single_notch_per_panel(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        step = Step()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", step)

        result_a, result_b = step.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) == 1
        assert len(result_b.notches) == 1

    def test_notch_spans_full_edge(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        step = Step()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", step)

        result_a, result_b = step.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].u_start_mm == 0.0
        assert result_a.notches[0].u_len_mm == 50
        assert result_b.notches[0].u_start_mm == 0.0

    def test_default_depth_ratio(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 8)
        step = Step()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", step)

        result_a, result_b = step.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].depth_mm == 4
        assert result_b.notches[0].depth_mm == 3

    def test_custom_depth_ratio(self):
        panel_a = PanelSpec("front", 100, 50, 10)
        panel_b = PanelSpec("left_side", 50, 50, 10)
        step = Step(depth_ratio=0.3)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", step)

        result_a, result_b = step.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].depth_mm == 3
        assert result_b.notches[0].depth_mm == 3


class TestRabbetJoinery:
    def test_creates_notch_on_receiving_panel_only(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        rabbet = Rabbet(receiving="a")
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", rabbet)

        result_a, result_b = rabbet.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) == 1
        assert len(result_b.notches) == 0

    def test_receiving_b(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        rabbet = Rabbet(receiving="b")
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", rabbet)

        result_a, result_b = rabbet.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) == 0
        assert len(result_b.notches) == 1

    def test_notch_depth_includes_clearance(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 8)
        clearance = 0.15
        rabbet = Rabbet(receiving="a", clearance_mm=clearance)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", rabbet)

        result_a, result_b = rabbet.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].depth_mm == 8 + clearance

    def test_custom_depth(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 8)
        rabbet = Rabbet(depth_mm=4.0, clearance_mm=0.1)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left_side", rabbet)

        result_a, result_b = rabbet.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].depth_mm == 4.1


class TestHalfLapJoinery:
    def test_creates_dado_on_both_panels(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(InterfaceType.INTERNAL, "shelf_1", "partition_1", half_lap)

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 1
        assert len(result_b.dados) == 1

    def test_dado_depth_is_half_thickness(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(InterfaceType.INTERNAL, "shelf_1", "partition_1", half_lap)

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 9
        assert result_b.dados[0].depth_mm == 9

    def test_dado_width_matches_mating_thickness_with_fitment(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 12)
        fitment = 0.2
        half_lap = HalfLap(fitment_mm=fitment)
        interface = Interface(InterfaceType.INTERNAL, "shelf_1", "partition_1", half_lap)

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].width_mm == 12 + fitment
        assert result_b.dados[0].width_mm == 18 + fitment


class TestCapturedJoinery:
    def test_creates_dado_on_side_panel(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured()
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 1
        assert len(result_b.dados) == 0

    def test_dado_edge_is_bottom_for_bottom_interface(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured()
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].edge == "bottom"

    def test_dado_edge_is_top_for_top_interface(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("top", 500, 400, 18, role=PanelRole.TOP)
        captured = Captured()
        interface = Interface(InterfaceType.TOP, "left_side", "top", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].edge == "top"

    def test_custom_dado_depth(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured(dado_depth_mm=6.0)
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 6.0

    def test_default_dado_depth_is_half_cap_thickness(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 12, role=PanelRole.BOTTOM)
        captured = Captured()
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 6.0

    def test_inset_positions_dado(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured(inset_mm=10.0)
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].position_from_edge_mm == 10.0


class TestDadoJoinery:
    def test_creates_dado_on_receiving_panel(self):
        panel_a = PanelSpec("side", 400, 300, 18)
        panel_b = PanelSpec("shelf", 350, 300, 18)
        dado = Dado(receiving="a")
        interface = Interface(InterfaceType.INTERNAL, "side", "shelf", dado)

        result_a, result_b = dado.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 1
        assert len(result_b.dados) == 0

    def test_receiving_b(self):
        panel_a = PanelSpec("shelf", 350, 300, 18)
        panel_b = PanelSpec("side", 400, 300, 18)
        dado = Dado(receiving="b")
        interface = Interface(InterfaceType.INTERNAL, "shelf", "side", dado)

        result_a, result_b = dado.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 0
        assert len(result_b.dados) == 1

    def test_dado_width_matches_mating_thickness_with_fitment(self):
        panel_a = PanelSpec("side", 400, 300, 18)
        panel_b = PanelSpec("shelf", 350, 300, 12)
        fitment = 0.3
        dado = Dado(fitment_mm=fitment)
        interface = Interface(InterfaceType.INTERNAL, "side", "shelf", dado)

        result_a, result_b = dado.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].width_mm == 12 + fitment

    def test_custom_dado_depth(self):
        panel_a = PanelSpec("side", 400, 300, 18)
        panel_b = PanelSpec("shelf", 350, 300, 18)
        dado = Dado(depth_mm=8.0)
        interface = Interface(InterfaceType.INTERNAL, "side", "shelf", dado)

        result_a, result_b = dado.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 8.0

    def test_default_depth_is_half_mating_thickness(self):
        panel_a = PanelSpec("side", 400, 300, 18)
        panel_b = PanelSpec("shelf", 350, 300, 12)
        dado = Dado()
        interface = Interface(InterfaceType.INTERNAL, "side", "shelf", dado)

        result_a, result_b = dado.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 6.0

    def test_inset_positions_dado(self):
        panel_a = PanelSpec("side", 400, 300, 18)
        panel_b = PanelSpec("shelf", 350, 300, 18)
        dado = Dado(inset_mm=20.0)
        interface = Interface(InterfaceType.INTERNAL, "side", "shelf", dado)

        result_a, result_b = dado.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].position_from_edge_mm == 20.0


class TestNotchSpecValidation:
    def test_rejects_negative_u_start(self):
        with pytest.raises(ValueError, match="u_start_mm must be non-negative"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=-1, u_len_mm=10, depth_mm=5)

    def test_rejects_zero_u_len(self):
        with pytest.raises(ValueError, match="u_len_mm must be positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=0, depth_mm=5)

    def test_rejects_negative_u_len(self):
        with pytest.raises(ValueError, match="u_len_mm must be positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=-5, depth_mm=5)

    def test_rejects_zero_depth(self):
        with pytest.raises(ValueError, match="depth_mm must be positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=10, depth_mm=0)

    def test_rejects_negative_depth(self):
        with pytest.raises(ValueError, match="depth_mm must be positive"):
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=0, u_len_mm=10, depth_mm=-3)
