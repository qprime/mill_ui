import pytest

from assembly.beam import BeamRole, BeamSpec
from assembly.core import Assembly, Interface, InterfaceType
from assembly.joinery import Butt, Captured
from assembly.panel import PanelRole, PanelSpec


class TestAssemblyWithBeams:
    def test_assembly_accepts_beam_member(self):
        beam = BeamSpec(
            name="post",
            length_mm=500,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            role=BeamRole.POST,
        )
        assembly = Assembly(
            members={"post": beam},
            interfaces=(),
        )
        assert "post" in assembly.members

    def test_assembly_panels_property_returns_only_panels(self):
        beam = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"post": beam, "shelf": panel},
            interfaces=(),
        )
        assert "shelf" in assembly.panels
        assert "post" not in assembly.panels

    def test_assembly_validates_beam_members(self):
        beam = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"post": beam, "shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "post", "left", "shelf", "right", Butt()),),
        )
        assembly.validate()

    def test_assembly_validates_unknown_beam_member(self):
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "nonexistent", "left", "shelf", "right", Butt()),),
        )
        with pytest.raises(ValueError, match="Unknown member"):
            assembly.validate()


class TestAssemblyResolveWithBeams:
    def test_resolve_expands_single_layer_beam(self):
        beam = BeamSpec(name="panel_beam", length_mm=500, width_mm=76, thickness_mm=19, layers=1)
        assembly = Assembly(
            members={"panel_beam": beam},
            interfaces=(),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        assert len(resolved) == 1
        assert resolved[0].name == "panel_beam"
        assert resolved[0].width_mm == 500
        assert resolved[0].height_mm == 76

    def test_resolve_expands_multi_layer_beam(self):
        beam = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        assembly = Assembly(
            members={"post": beam},
            interfaces=(),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        assert len(resolved) == 3
        panel_names = [p.name for p in resolved]
        assert "post_L0" in panel_names
        assert "post_L1" in panel_names
        assert "post_L2" in panel_names

    def test_resolve_expands_spliced_beam(self):
        beam = BeamSpec(name="long_rail", length_mm=2000, width_mm=100, thickness_mm=19, layers=3)
        assembly = Assembly(
            members={"long_rail": beam},
            interfaces=(),
            sheet_size=1200,
        )
        resolved = assembly.resolve()
        assert len(resolved) > 3


class TestBeamToBeamInterface:
    def test_beam_to_beam_butt_interface(self):
        post = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        rail = BeamSpec(name="rail", length_mm=400, width_mm=50, thickness_mm=19, layers=3)
        assembly = Assembly(
            members={"post": post, "rail": rail},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "post", "left", "rail", "right", Butt()),),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        assert len(resolved) == 6


class TestBeamToPanelInterface:
    def test_beam_to_panel_butt_interface(self):
        post = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"post": post, "shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "post", "left", "shelf", "right", Butt()),),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        assert len(resolved) == 4

    def test_beam_to_panel_captured_interface_creates_dados(self):
        post = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"post": post, "shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "post", "left", "shelf", "right", Captured()),),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        post_panels = [p for p in resolved if p.name.startswith("post")]
        outer_layer_panels = [p for p in post_panels if "_L0" in p.name or "_L2" in p.name]
        assert len(outer_layer_panels) == 2
        for p in outer_layer_panels:
            assert len(p.dados) > 0


class TestOuterLayerSelection:
    def test_outer_layers_for_3_layer_beam(self):
        beam = BeamSpec(name="beam", length_mm=500, width_mm=76, thickness_mm=19, layers=3)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"beam": beam, "shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "beam", "left", "shelf", "right", Captured()),),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        beam_panels = [p for p in resolved if p.name.startswith("beam")]
        panels_with_dados = [p for p in beam_panels if len(p.dados) > 0]
        panel_names_with_dados = [p.name for p in panels_with_dados]
        assert "beam_L0" in panel_names_with_dados
        assert "beam_L2" in panel_names_with_dados
        assert "beam_L1" not in panel_names_with_dados

    def test_outer_layers_for_5_layer_beam(self):
        beam = BeamSpec(name="beam", length_mm=500, width_mm=76, thickness_mm=19, layers=5)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"beam": beam, "shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "beam", "left", "shelf", "right", Captured()),),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        beam_panels = [p for p in resolved if p.name.startswith("beam")]
        panels_with_dados = [p for p in beam_panels if len(p.dados) > 0]
        panel_names_with_dados = [p.name for p in panels_with_dados]
        assert "beam_L0" in panel_names_with_dados
        assert "beam_L4" in panel_names_with_dados
        assert "beam_L1" not in panel_names_with_dados
        assert "beam_L2" not in panel_names_with_dados
        assert "beam_L3" not in panel_names_with_dados

    def test_single_layer_beam_all_panels_participate(self):
        beam = BeamSpec(name="beam", length_mm=500, width_mm=76, thickness_mm=19, layers=1)
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"beam": beam, "shelf": panel},
            interfaces=(Interface(InterfaceType.SIDE_TO_SIDE, "beam", "left", "shelf", "right", Captured()),),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        beam_panels = [p for p in resolved if p.name == "beam"]
        assert len(beam_panels) == 1
        assert len(beam_panels[0].dados) > 0


class TestMixedAssembly:
    def test_mixed_beams_and_panels(self):
        post = BeamSpec(name="post", length_mm=500, width_mm=76, thickness_mm=19, layers=3, role=BeamRole.POST)
        rail = BeamSpec(name="rail", length_mm=400, width_mm=50, thickness_mm=19, layers=3, role=BeamRole.RAIL)
        shelf = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19)
        assembly = Assembly(
            members={"post": post, "rail": rail, "shelf": shelf},
            interfaces=(
                Interface(InterfaceType.SIDE_TO_SIDE, "post", "left", "rail", "right", Butt()),
                Interface(InterfaceType.SIDE_TO_SIDE, "rail", "left", "shelf", "right", Butt()),
            ),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        assert len(resolved) == 7

    def test_resolve_preserves_panel_roles(self):
        panel = PanelSpec(name="shelf", width_mm=400, height_mm=300, thickness_mm=19, role=PanelRole.SHELF)
        assembly = Assembly(
            members={"shelf": panel},
            interfaces=(),
            sheet_size=1000,
        )
        resolved = assembly.resolve()
        assert len(resolved) == 1
        assert resolved[0].role == PanelRole.SHELF
