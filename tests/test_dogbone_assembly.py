from __future__ import annotations

import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from assembly.core import Interface, InterfaceType
from assembly.joinery import Captured
from assembly.panel import DadoSpec, PanelSpec
from assembly.primitives import box
from layout_ast.layout import (
    DogboneSpec,
    Feature,
    Geometry,
    Item,
    LayoutAST,
    Placement,
    Sheet,
)
from pml.yaml_parser import _parse_interface_config


class TestDadoSpecDogbone:
    def test_default_none(self):
        dado = DadoSpec(
            position_from_edge_mm=10.0,
            width_mm=18.0,
            depth_mm=9.0,
            edge="bottom",
        )
        assert dado.dogbone is None

    def test_explicit_dogbone(self):
        spec = DogboneSpec()
        dado = DadoSpec(
            position_from_edge_mm=10.0,
            width_mm=18.0,
            depth_mm=9.0,
            edge="bottom",
            dogbone=spec,
        )
        assert dado.dogbone is not None
        assert dado.dogbone.style == "dogbone"

    def test_tbone_style(self):
        spec = DogboneSpec(style="t-bone_x", diameter_mm=3.175)
        dado = DadoSpec(
            position_from_edge_mm=10.0,
            width_mm=18.0,
            depth_mm=9.0,
            edge="left",
            dogbone=spec,
        )
        assert dado.dogbone is not None
        assert dado.dogbone.style == "t-bone_x"
        assert dado.dogbone.diameter_mm == 3.175


class TestCapturedDogbonePropagation:
    def test_captured_no_dogbone_default(self):
        panel_a = PanelSpec("side", 400, 500, 18)
        panel_b = PanelSpec("shelf", 364, 350, 18)
        interface = Interface(
            InterfaceType.INTERNAL,
            "side",
            "left",
            "shelf",
            "right",
            Captured(),
            position_along_edge_a_mm=200.0,
        )

        result_a, _result_b = Captured().apply(interface, panel_a, panel_b)
        for dado in result_a.dados:
            assert dado.dogbone is None

    def test_captured_propagates_dogbone(self):
        panel_a = PanelSpec("side", 400, 500, 18)
        panel_b = PanelSpec("shelf", 364, 350, 18)
        strategy = Captured(dogbone=DogboneSpec())
        interface = Interface(
            InterfaceType.INTERNAL,
            "side",
            "left",
            "shelf",
            "right",
            strategy,
            position_along_edge_a_mm=200.0,
        )

        result_a, _result_b = strategy.apply(interface, panel_a, panel_b)
        assert len(result_a.dados) == 1
        assert result_a.dados[0].dogbone is not None
        assert result_a.dados[0].dogbone.style == "dogbone"

    def test_captured_propagates_tbone_style(self):
        spec = DogboneSpec(style="t-bone_y", overcut_mm=0.3)
        strategy = Captured(dogbone=spec)
        panel_a = PanelSpec("side", 400, 500, 18)
        panel_b = PanelSpec("shelf", 364, 350, 18)
        interface = Interface(
            InterfaceType.INTERNAL,
            "side",
            "left",
            "shelf",
            "right",
            strategy,
            position_along_edge_a_mm=200.0,
        )

        result_a, _ = strategy.apply(interface, panel_a, panel_b)
        assert result_a.dados[0].dogbone is not None
        assert result_a.dados[0].dogbone.style == "t-bone_y"
        assert result_a.dados[0].dogbone.overcut_mm == 0.3

    def test_captured_receiving_b_propagates_dogbone(self):
        strategy = Captured(dogbone=DogboneSpec(), receiving="b")
        panel_a = PanelSpec("top", 400, 350, 18)
        panel_b = PanelSpec("side", 400, 500, 18)
        interface = Interface(
            InterfaceType.TOP,
            "top",
            "bottom",
            "side",
            "top",
            strategy,
        )

        _result_a, result_b = strategy.apply(interface, panel_a, panel_b)
        assert len(result_b.dados) == 1
        assert result_b.dados[0].dogbone is not None

    def test_box_captured_bottom_with_dogbone(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            bottom=Captured(dogbone=DogboneSpec()),
        )
        panels = assembly.resolve()

        dados_with_dogbone = [dado for panel in panels for dado in panel.dados if dado.dogbone is not None]
        assert len(dados_with_dogbone) > 0

    def test_box_captured_bottom_without_dogbone(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            bottom=Captured(),
        )
        panels = assembly.resolve()

        for panel in panels:
            for dado in panel.dados:
                assert dado.dogbone is None


class TestInterfaceConfigDogboneParsing:
    def test_no_dogbone(self):
        config = _parse_interface_config({"joinery": "captured"})
        assert config.dogbone is None

    def test_dogbone_true(self):
        config = _parse_interface_config({"joinery": "captured", "dogbone": True})
        assert config.dogbone is True

    def test_dogbone_dict_defaults(self):
        config = _parse_interface_config({"joinery": "captured", "dogbone": {"style": "dogbone"}})
        assert isinstance(config.dogbone, DogboneSpec)
        assert config.dogbone.style == "dogbone"
        assert config.dogbone.diameter_mm is None
        assert config.dogbone.overcut_mm == 0.0

    def test_dogbone_dict_explicit(self):
        config = _parse_interface_config(
            {
                "joinery": "captured",
                "dogbone": {
                    "style": "t-bone_x",
                    "diameter": "3.175mm",
                    "overcut": "0.5mm",
                },
            }
        )
        assert isinstance(config.dogbone, DogboneSpec)
        assert config.dogbone.style == "t-bone_x"
        assert config.dogbone.diameter_mm == 3.175
        assert config.dogbone.overcut_mm == 0.5


class TestDadoDogboneThroughPipeline:
    def _make_dado_ast(self, dogbone: DogboneSpec | None = None) -> LayoutAST:
        return LayoutAST(
            sheet=Sheet(width_mm=500, height_mm=500, thickness_mm=18, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": 18.2, "h_mm": 400.0}),
                    placement=Placement(center_xy_mm=(100.0, 250.0)),
                    feature=Feature(type="pocket", depth_mm=9.0, dogbone=dogbone),
                    shape_id="dado_slot",
                ),
            ),
        )

    def test_dado_with_dogbone_generates_planner_input(self):
        ast = self._make_dado_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        assert len(planner_input.dogbones) == 1
        db = planner_input.dogbones[0]
        assert db.style == "dogbone"
        assert db.pocket_id == "dado_slot"
        assert len(db.corners) == 4
        assert db.depth_mm == 9.0

    def test_dado_without_dogbone_no_planner_input(self):
        ast = self._make_dado_ast(dogbone=None)
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        assert len(planner_input.dogbones) == 0

    def test_dado_dogbone_corners_match_geometry(self):
        ast = self._make_dado_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        corners = planner_input.dogbones[0].corners
        assert len(corners) == 4

        cx, cy = 100.0, 250.0
        half_w, half_h = 18.2 / 2, 400.0 / 2
        expected = sorted(
            [
                (cx - half_w, cy - half_h),
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy + half_h),
            ]
        )
        assert sorted(corners) == pytest.approx(expected, abs=0.01)

    def test_dado_tbone_x_propagates(self):
        spec = DogboneSpec(style="t-bone_x", diameter_mm=3.175)
        ast = self._make_dado_ast(dogbone=spec)
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        db = planner_input.dogbones[0]
        assert db.style == "t-bone_x"
        assert db.tool_diameter_mm == 3.175
