import pytest

from assembly.core import Assembly, Interface, InterfaceType, RemovalKind
from assembly.joinery import Butt, Captured, Finger, HalfLap
from assembly.panel import PanelRole, PanelSpec


class TestInterfaceTypeValidation:
    def test_butt_valid_for_all_interface_types(self):
        joinery = Butt()
        for itype in InterfaceType:
            interface = Interface(itype, "a", "left", "b", "right", joinery)
            interface.validate()

    def test_finger_valid_for_side_to_side(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "left", "b", "right", joinery)
        interface.validate()

    def test_finger_valid_for_top(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.TOP, "a", "top", "b", "bottom", joinery)
        interface.validate()

    def test_finger_valid_for_bottom(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.BOTTOM, "a", "bottom", "b", "top", joinery)
        interface.validate()

    def test_finger_invalid_for_internal(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.INTERNAL, "a", "bottom", "b", "top", joinery)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            interface.validate()

    def test_half_lap_valid_for_internal(self):
        joinery = HalfLap()
        interface = Interface(InterfaceType.INTERNAL, "a", "bottom", "b", "top", joinery)
        interface.validate()

    def test_half_lap_invalid_for_side_to_side(self):
        joinery = HalfLap()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "left", "b", "right", joinery)
        with pytest.raises(ValueError, match="not valid for SIDE_TO_SIDE"):
            interface.validate()

    def test_half_lap_invalid_for_top(self):
        joinery = HalfLap()
        interface = Interface(InterfaceType.TOP, "a", "top", "b", "bottom", joinery)
        with pytest.raises(ValueError, match="not valid for TOP"):
            interface.validate()

    def test_captured_valid_for_top(self):
        joinery = Captured()
        interface = Interface(InterfaceType.TOP, "a", "top", "b", "bottom", joinery)
        interface.validate()

    def test_captured_valid_for_bottom(self):
        joinery = Captured()
        interface = Interface(InterfaceType.BOTTOM, "a", "bottom", "b", "top", joinery)
        interface.validate()

    def test_captured_valid_for_side_to_side(self):
        joinery = Captured()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "left", "b", "right", joinery)
        interface.validate()

    def test_captured_valid_for_internal(self):
        joinery = Captured()
        interface = Interface(InterfaceType.INTERNAL, "a", "bottom", "b", "top", joinery)
        interface.validate()

    def test_captured_with_receiving_b_valid_for_side_to_side(self):
        joinery = Captured(receiving="b")
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "right", "b", "left", joinery)
        interface.validate()

    def test_edge_joinery_rejects_internal_interface(self):
        joinery = Finger(width_mm=12.0)
        assert joinery.removal_kind == RemovalKind.EDGE
        interface = Interface(InterfaceType.INTERNAL, "a", "bottom", "b", "top", joinery)
        with pytest.raises(ValueError):
            interface.validate()


class TestAssemblyValidation:
    def test_validates_unknown_panel_a(self):
        panels = {
            "front": PanelSpec("front", 100, 50, 6),
        }
        interfaces = (Interface(InterfaceType.SIDE_TO_SIDE, "nonexistent", "left", "front", "right", Butt()),)
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown member: nonexistent"):
            assembly.validate()

    def test_validates_unknown_panel_b(self):
        panels = {
            "front": PanelSpec("front", 100, 50, 6),
        }
        interfaces = (Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "nonexistent", "right", Butt()),)
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown member: nonexistent"):
            assembly.validate()

    def test_validates_interface_joinery_compatibility(self):
        panels = {
            "shelf": PanelSpec("shelf", 100, 50, 6, role=PanelRole.SHELF),
            "partition": PanelSpec("partition", 50, 80, 6, role=PanelRole.PARTITION),
        }
        interfaces = (Interface(InterfaceType.INTERNAL, "shelf", "bottom", "partition", "top", Finger(width_mm=12)),)
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            assembly.validate()


class TestRemovalKindClassification:
    def test_butt_has_no_removal(self):
        assert Butt().removal_kind == RemovalKind.NONE

    def test_finger_has_edge_removal(self):
        assert Finger().removal_kind == RemovalKind.EDGE

    def test_half_lap_has_edge_removal(self):
        assert HalfLap().removal_kind == RemovalKind.EDGE

    def test_captured_has_face_removal(self):
        assert Captured().removal_kind == RemovalKind.FACE

    def test_captured_with_receiving_b_has_face_removal(self):
        assert Captured(receiving="b").removal_kind == RemovalKind.FACE
