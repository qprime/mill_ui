import pytest

from assembly.core import Assembly, Interface, InterfaceType
from assembly.panel import PanelSpec, PanelRole, Edge, NotchSpec, DadoSpec
from assembly.joinery import Butt, Finger, HalfLap, Captured


class TestButtJoinery:
    def test_returns_unchanged_panels(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", Butt())

        result_a, result_b = Butt().apply(interface, panel_a, panel_b)

        assert result_a.notches == ()
        assert result_b.notches == ()
        assert result_a.dados == ()
        assert result_b.dados == ()


class TestFingerJoinery:
    def test_creates_notches_on_both_panels(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", Finger(width_mm=12))

        result_a, result_b = Finger(width_mm=12).apply(interface, panel_a, panel_b)

        assert len(result_a.notches) > 0
        assert len(result_b.notches) > 0

    def test_notch_depth_equals_mating_panel_thickness(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 8)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", Finger(width_mm=12))

        result_a, result_b = Finger(width_mm=12).apply(interface, panel_a, panel_b)

        for notch in result_a.notches:
            assert notch.depth_mm == 8
        for notch in result_b.notches:
            assert notch.depth_mm == 6

    def test_notches_alternate_between_panels(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", Finger(width_mm=10))

        result_a, result_b = Finger(width_mm=10).apply(interface, panel_a, panel_b)

        positions_a = {n.u_start_mm for n in result_a.notches}
        positions_b = {n.u_start_mm for n in result_b.notches}

        assert positions_a.isdisjoint(positions_b)

    def test_odd_finger_count(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", Finger(width_mm=12))

        result_a, result_b = Finger(width_mm=12).apply(interface, panel_a, panel_b)

        total_notches = len(result_a.notches) + len(result_b.notches)
        assert total_notches >= 3

    def test_clearance_applied(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        clearance = 0.2
        finger = Finger(width_mm=25, clearance_mm=clearance)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", finger)

        result_a, result_b = finger.apply(interface, panel_a, panel_b)

        for notch in result_a.notches:
            if notch.u_start_mm > 0.1 and notch.u_start_mm + notch.u_len_mm < 49.9:
                expected_width = 50 / 3 + clearance / 2
                assert abs(notch.u_len_mm - expected_width) < 0.5

    def test_finger_count_mode(self):
        panel_a = PanelSpec("front", 100, 50, 6)
        panel_b = PanelSpec("left_side", 50, 50, 6)
        finger = Finger(count=5)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "left_side", "right", finger)

        result_a, result_b = finger.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) > 0
        assert len(result_b.notches) > 0


class TestHalfLapJoinery:
    def test_creates_notch_on_both_panels(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_mm=25.0, position_along_edge_b_mm=30.0
        )

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert len(result_a.notches) == 1
        assert len(result_b.notches) == 1

    def test_notch_depth_is_half_panel_dimension(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_mm=25.0, position_along_edge_b_mm=30.0
        )

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].depth_mm == 25
        assert result_b.notches[0].depth_mm == 25

    def test_notch_width_matches_mating_thickness_with_fitment(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 12)
        fitment = 0.2
        half_lap = HalfLap(fitment_mm=fitment)
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_mm=25.0, position_along_edge_b_mm=30.0
        )

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].u_len_mm == 12 + fitment
        assert result_b.notches[0].u_len_mm == 18 + fitment

    def test_raises_without_position_mm(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_along_edge_b_mm=30.0
        )

        with pytest.raises(ValueError, match="requires interface.position_mm"):
            half_lap.apply(interface, panel_a, panel_b)

    def test_raises_without_position_along_edge_b_mm(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_mm=25.0
        )

        with pytest.raises(ValueError, match="requires interface.position_along_edge_b_mm"):
            half_lap.apply(interface, panel_a, panel_b)

    def test_notch_position_from_interface(self):
        panel_a = PanelSpec("shelf_1", 100, 50, 18)
        panel_b = PanelSpec("partition_1", 50, 80, 18)
        half_lap = HalfLap()
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_mm=35.0, position_along_edge_b_mm=40.0
        )

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].u_start_mm == 35.0
        assert result_b.notches[0].u_start_mm == 40.0

    def test_asymmetric_positions_for_cross_lap(self):
        panel_a = PanelSpec("shelf_1", 288, 300, 18)
        panel_b = PanelSpec("partition_1", 300, 188, 18)
        half_lap = HalfLap()
        position_on_shelf = 96 - 9
        position_on_partition = 94 - 9
        interface = Interface(
            InterfaceType.INTERNAL, "shelf_1", "bottom", "partition_1", "left", half_lap,
            position_mm=position_on_shelf, position_along_edge_b_mm=position_on_partition
        )

        result_a, result_b = half_lap.apply(interface, panel_a, panel_b)

        assert result_a.notches[0].u_start_mm == position_on_shelf
        assert result_b.notches[0].u_start_mm == position_on_partition
        assert result_a.notches[0].u_start_mm != result_b.notches[0].u_start_mm


class TestCapturedJoinery:
    def test_creates_dado_on_side_panel(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured()
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 1
        assert len(result_b.dados) == 0

    def test_dado_edge_is_bottom_for_bottom_interface(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured()
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].edge == "bottom"

    def test_dado_edge_is_top_for_top_interface(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("top", 500, 400, 18, role=PanelRole.TOP)
        captured = Captured()
        interface = Interface(InterfaceType.TOP, "left_side", "top", "top", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].edge == "top"

    def test_custom_dado_depth(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured(dado_depth_mm=6.0)
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 6.0

    def test_default_dado_depth_is_half_cap_thickness(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 12, role=PanelRole.BOTTOM)
        captured = Captured()
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].depth_mm == 6.0

    def test_inset_positions_dado(self):
        panel_a = PanelSpec("left_side", 400, 300, 18)
        panel_b = PanelSpec("bottom", 500, 400, 18, role=PanelRole.BOTTOM)
        captured = Captured(inset_mm=10.0)
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_a.dados[0].position_from_edge_mm == 10.0


class TestCapturedReceivingParameter:
    def test_receiving_a_is_default(self):
        panel_a = PanelSpec("side", 400, 300, 18)
        panel_b = PanelSpec("shelf", 350, 300, 18)
        captured = Captured(receiving="a")
        interface = Interface(InterfaceType.INTERNAL, "side", "bottom", "shelf", "top", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 1
        assert len(result_b.dados) == 0

    def test_receiving_b_raises_for_internal_interface(self):
        panel_a = PanelSpec("shelf", 350, 300, 18)
        panel_b = PanelSpec("side", 400, 300, 18)
        captured = Captured(receiving="b")
        interface = Interface(InterfaceType.INTERNAL, "shelf", "top", "side", "bottom", captured)

        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            captured.apply(interface, panel_a, panel_b)

    def test_receiving_b_valid_for_side_to_side(self):
        panel_a = PanelSpec("left_side", 300, 400, 18)
        panel_b = PanelSpec("back", 500, 400, 6)
        captured = Captured(receiving="b", inset_mm=10.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "left_side", "right", "back", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 0
        assert len(result_b.dados) == 1

    def test_receiving_b_dado_on_panel_b_for_side_to_side(self):
        panel_a = PanelSpec("left_side", 300, 400, 18)
        panel_b = PanelSpec("back", 500, 400, 6)
        captured = Captured(receiving="b", inset_mm=15.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "left_side", "right", "back", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert result_b.dados[0].position_from_edge_mm == 15.0
        assert result_b.dados[0].width_mm == 18 + 0.2
        assert result_b.dados[0].depth_mm == 9.0

    def test_receiving_b_valid_for_top_interface(self):
        panel_a = PanelSpec("left_side", 300, 400, 18)
        panel_b = PanelSpec("top", 500, 300, 18)
        captured = Captured(receiving="b")
        interface = Interface(InterfaceType.TOP, "left_side", "top", "top", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 0
        assert len(result_b.dados) == 1

    def test_receiving_b_valid_for_bottom_interface(self):
        panel_a = PanelSpec("left_side", 300, 400, 18)
        panel_b = PanelSpec("bottom", 500, 300, 18)
        captured = Captured(receiving="b")
        interface = Interface(InterfaceType.BOTTOM, "left_side", "bottom", "bottom", "left", captured)

        result_a, result_b = captured.apply(interface, panel_a, panel_b)

        assert len(result_a.dados) == 0
        assert len(result_b.dados) == 1


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
