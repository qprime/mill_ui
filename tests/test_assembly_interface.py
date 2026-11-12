from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import Point, Polygon

from assembly.core import Assembly, Interface, InterfaceType, MemberSpec, RemovalKind
from assembly.joinery import Butt, Captured, Finger, HalfLap
from assembly.panel import DadoSpec, Edge, NotchSpec, PanelRole, PanelSpec


class TestAssemblyRemovalPreservation:
    @pytest.mark.parametrize("field", ["notches", "dados"])
    def test_a_strategy_cannot_drop_existing_cuts(self, field):
        class DroppingJoint(Butt):
            def apply(self, interface, panel_a, panel_b):
                return replace(panel_a, **{field: ()}), panel_b

        source = PanelSpec(
            "source", 100, 80, 6, notches=(NotchSpec(Edge.BOTTOM, 0, 10, 12),), dados=(DadoSpec(15, 6.2, 3, "top"),)
        )
        peer = PanelSpec("peer", 80, 80, 6)
        joint = Interface(InterfaceType.SIDE_TO_SIDE, "source", "right", "peer", "left", DroppingJoint())
        with pytest.raises(ValueError, match="member 'source' must preserve"):
            Assembly(members={"source": source, "peer": peer}, interfaces=(joint,)).resolve()

    @pytest.mark.parametrize("interface_count", [0, 1, 2])
    @pytest.mark.parametrize("source_is_a", [True, False])
    def test_original_notches_and_dados_survive_once(self, interface_count, source_is_a):
        source = PanelSpec(
            "source",
            100,
            80,
            6,
            notches=(NotchSpec(Edge.BOTTOM, 0, 10, 12),),
            dados=(DadoSpec(20, 6.2, 3, "top"),),
            role=PanelRole.LEFT,
            origin=(14, 28),
        )
        members: dict[str, MemberSpec] = {
            "source": source,
            **{f"peer_{i}": PanelSpec(f"peer_{i}", 80, 80, 6) for i in range(2)},
        }
        interfaces = tuple(
            Interface(
                InterfaceType.SIDE_TO_SIDE,
                "source" if source_is_a else f"peer_{i}",
                "right",
                f"peer_{i}" if source_is_a else "source",
                "left",
                Butt(),
            )
            for i in range(interface_count)
        )
        assembly = Assembly(members=members, interfaces=interfaces)
        resolved = {p.name: p for p in assembly.resolve()}
        assert resolved["source"] == source
        assert assembly.members["source"] == source
        assert {p.name: p for p in assembly.resolve()} == resolved

    def test_new_joint_cuts_append_without_repeating_source_cuts(self):
        source = PanelSpec(
            "source", 100, 80, 6, notches=(NotchSpec(Edge.BOTTOM, 0, 10, 12),), dados=(DadoSpec(15, 6.2, 3, "top"),)
        )
        members: dict[str, MemberSpec] = {
            "source": source,
            "shelf": PanelSpec("shelf", 80, 80, 6),
            "divider": PanelSpec("divider", 80, 80, 6),
        }
        captured = Interface(InterfaceType.INTERNAL, "source", "bottom", "shelf", "left", Captured(), 30)
        half_lap = Interface(InterfaceType.INTERNAL, "source", "top", "divider", "bottom", HalfLap(), 40, 20)
        actual = {p.name: p for p in Assembly(members=members, interfaces=(captured, half_lap)).resolve()}
        assert len(actual["source"].notches) == 2
        assert len(actual["source"].dados) == 2
        assert actual["source"].notches[0] == source.notches[0]
        assert actual["source"].dados[0] == source.dados[0]
        assert actual["source"].notches[1].u_start_mm == 40
        assert actual["source"].dados[1].position_from_edge_mm == 30

    def test_explicit_new_cut_equal_to_an_original_cut_is_still_retained(self):
        source = PanelSpec("source", 100, 80, 6, dados=(DadoSpec(15, 6.2, 3, "bottom"),))
        peer = PanelSpec("peer", 80, 80, 6)
        joint = Interface(InterfaceType.INTERNAL, "source", "bottom", "peer", "left", Captured(dogbone=None), 15)
        source = replace(source, dados=(replace(source.dados[0], dogbone=None),))
        result = Assembly(members={"source": source, "peer": peer}, interfaces=(joint,)).resolve()[0]
        assert result.dados == (source.dados[0], source.dados[0])

    def test_open_carcass_toe_notches_reach_the_removal_intent(self):
        from adapters.ast_to_removal import ast_to_removal_intents
        from pml.yaml_parser import parse_pml_yaml
        from resolution.layout_resolver import resolve_layout

        source = Path(__file__).parent / "fixtures/assemblies/notched_open_sides.pml.yml"
        intents = ast_to_removal_intents(resolve_layout(parse_pml_yaml(source.read_text())))
        profiles = [i for i in intents if i.hint_type == "profile"]
        assert len(profiles) == 2
        assert all(i.shape == "Polygon" and i.shape_geometry.points is not None for i in profiles)
        for intent in profiles:
            region = Polygon(intent.shape_geometry.points)
            notch_x = -280 + 37.5 if "left_side" in intent.region_id else 280 - 37.5
            assert not region.covers(Point(notch_x, -360 + 50))
            assert region.covers(Point(notch_x, -360 + 125))


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
        panels: dict[str, Any] = {
            "front": PanelSpec("front", 100, 50, 6),
        }
        interfaces = (Interface(InterfaceType.SIDE_TO_SIDE, "nonexistent", "left", "front", "right", Butt()),)
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown member: nonexistent"):
            assembly.validate()

    def test_validates_unknown_panel_b(self):
        panels: dict[str, Any] = {
            "front": PanelSpec("front", 100, 50, 6),
        }
        interfaces = (Interface(InterfaceType.SIDE_TO_SIDE, "front", "left", "nonexistent", "right", Butt()),)
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown member: nonexistent"):
            assembly.validate()

    def test_validates_interface_joinery_compatibility(self):
        panels: dict[str, Any] = {
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
