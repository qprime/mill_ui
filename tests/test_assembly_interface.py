import pytest

from assembly.core import Assembly, Interface, InterfaceType, RemovalKind
from assembly.panel import PanelSpec, PanelRole, Edge, NotchSpec, DadoSpec
from assembly.joinery import Butt, Finger, Step, Rabbet, HalfLap, Captured, Dado


class TestInterfaceTypeValidation:
    def test_butt_valid_for_all_interface_types(self):
        joinery = Butt()
        for itype in InterfaceType:
            interface = Interface(itype, "a", "b", joinery)
            interface.validate()

    def test_finger_valid_for_side_to_side(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", joinery)
        interface.validate()

    def test_finger_valid_for_top(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.TOP, "a", "b", joinery)
        interface.validate()

    def test_finger_valid_for_bottom(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.BOTTOM, "a", "b", joinery)
        interface.validate()

    def test_finger_invalid_for_internal(self):
        joinery = Finger(width_mm=12.0)
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            interface.validate()

    def test_step_valid_for_side_to_side(self):
        joinery = Step()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", joinery)
        interface.validate()

    def test_step_invalid_for_internal(self):
        joinery = Step()
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            interface.validate()

    def test_rabbet_valid_for_side_to_side(self):
        joinery = Rabbet()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", joinery)
        interface.validate()

    def test_rabbet_invalid_for_internal(self):
        joinery = Rabbet()
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            interface.validate()

    def test_half_lap_valid_for_internal(self):
        joinery = HalfLap()
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        interface.validate()

    def test_half_lap_invalid_for_side_to_side(self):
        joinery = HalfLap()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", joinery)
        with pytest.raises(ValueError, match="not valid for SIDE_TO_SIDE"):
            interface.validate()

    def test_half_lap_invalid_for_top(self):
        joinery = HalfLap()
        interface = Interface(InterfaceType.TOP, "a", "b", joinery)
        with pytest.raises(ValueError, match="not valid for TOP"):
            interface.validate()

    def test_captured_valid_for_top(self):
        joinery = Captured()
        interface = Interface(InterfaceType.TOP, "a", "b", joinery)
        interface.validate()

    def test_captured_valid_for_bottom(self):
        joinery = Captured()
        interface = Interface(InterfaceType.BOTTOM, "a", "b", joinery)
        interface.validate()

    def test_captured_valid_for_side_to_side(self):
        joinery = Captured()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", joinery)
        interface.validate()

    def test_captured_valid_for_internal(self):
        joinery = Captured()
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        interface.validate()

    def test_dado_valid_for_top(self):
        joinery = Dado()
        interface = Interface(InterfaceType.TOP, "a", "b", joinery)
        interface.validate()

    def test_dado_valid_for_bottom(self):
        joinery = Dado()
        interface = Interface(InterfaceType.BOTTOM, "a", "b", joinery)
        interface.validate()

    def test_dado_valid_for_internal(self):
        joinery = Dado()
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        interface.validate()

    def test_dado_invalid_for_side_to_side(self):
        joinery = Dado()
        interface = Interface(InterfaceType.SIDE_TO_SIDE, "a", "b", joinery)
        with pytest.raises(ValueError, match="not valid for SIDE_TO_SIDE"):
            interface.validate()

    def test_edge_joinery_rejects_internal_interface(self):
        joinery = Finger(width_mm=12.0)
        assert joinery.removal_kind == RemovalKind.EDGE
        interface = Interface(InterfaceType.INTERNAL, "a", "b", joinery)
        with pytest.raises(ValueError):
            interface.validate()


class TestAssemblyValidation:
    def test_validates_unknown_panel_a(self):
        panels = {
            "front": PanelSpec("front", 100, 50, 6),
        }
        interfaces = (
            Interface(InterfaceType.SIDE_TO_SIDE, "nonexistent", "front", Butt()),
        )
        assembly = Assembly(panels=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown panel: nonexistent"):
            assembly.validate()

    def test_validates_unknown_panel_b(self):
        panels = {
            "front": PanelSpec("front", 100, 50, 6),
        }
        interfaces = (
            Interface(InterfaceType.SIDE_TO_SIDE, "front", "nonexistent", Butt()),
        )
        assembly = Assembly(panels=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown panel: nonexistent"):
            assembly.validate()

    def test_validates_interface_joinery_compatibility(self):
        panels = {
            "shelf": PanelSpec("shelf", 100, 50, 6, role=PanelRole.SHELF),
            "partition": PanelSpec("partition", 50, 80, 6, role=PanelRole.PARTITION),
        }
        interfaces = (
            Interface(InterfaceType.INTERNAL, "shelf", "partition", Finger(width_mm=12)),
        )
        assembly = Assembly(panels=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            assembly.validate()


class TestRemovalKindClassification:
    def test_butt_has_no_removal(self):
        assert Butt().removal_kind == RemovalKind.NONE

    def test_finger_has_edge_removal(self):
        assert Finger().removal_kind == RemovalKind.EDGE

    def test_step_has_edge_removal(self):
        assert Step().removal_kind == RemovalKind.EDGE

    def test_rabbet_has_edge_removal(self):
        assert Rabbet().removal_kind == RemovalKind.EDGE

    def test_half_lap_has_face_removal(self):
        assert HalfLap().removal_kind == RemovalKind.FACE

    def test_captured_has_face_removal(self):
        assert Captured().removal_kind == RemovalKind.FACE

    def test_dado_has_face_removal(self):
        assert Dado().removal_kind == RemovalKind.FACE
