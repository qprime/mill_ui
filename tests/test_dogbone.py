from __future__ import annotations

import math

import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.planner.passes.pocket import _dogbone_center
from cam.planner.passes.tools import normalize_tool_entries
from layout_ast.layout import DogboneSpec, Feature, Geometry, Item, LayoutAST, Placement, Sheet


def _make_pocket_ast(dogbone: DogboneSpec | None = None) -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(type="pocket", depth_mm=6.0, dogbone=dogbone),
                shape_id="panel",
            ),
        ),
    )


TOOL_DB = [
    {"name": "1/8_endmill", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
    {"name": "1/4_endmill", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
]


class TestDogboneSpec:
    def test_defaults(self):
        spec = DogboneSpec()
        assert spec.style == "dogbone"
        assert spec.diameter_mm is None
        assert spec.overcut_mm == 0.0

    def test_explicit_values(self):
        spec = DogboneSpec(style="t-bone_x", diameter_mm=3.175, overcut_mm=0.5)
        assert spec.style == "t-bone_x"
        assert spec.diameter_mm == 3.175
        assert spec.overcut_mm == 0.5

    def test_invalid_style(self):
        with pytest.raises(ValueError, match="Invalid dogbone style"):
            DogboneSpec(style="invalid")

    def test_negative_diameter(self):
        with pytest.raises(ValueError, match="diameter_mm must be positive"):
            DogboneSpec(diameter_mm=-1.0)

    def test_zero_diameter(self):
        with pytest.raises(ValueError, match="diameter_mm must be positive"):
            DogboneSpec(diameter_mm=0.0)

    def test_negative_overcut(self):
        with pytest.raises(ValueError, match="overcut_mm must be >= 0"):
            DogboneSpec(overcut_mm=-0.1)


class TestDogboneIRPropagation:
    def test_dogbone_true_propagates_to_ir(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        assert len(intents) == 1
        assert intents[0].dogbone is not None
        assert intents[0].dogbone.style == "dogbone"

    def test_dogbone_none_no_ir_field(self):
        ast = _make_pocket_ast(dogbone=None)
        intents = ast_to_removal_intents(ast)
        assert len(intents) == 1
        assert intents[0].dogbone is None

    def test_dogbone_tbone_x_propagates(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec(style="t-bone_x", diameter_mm=3.175))
        intents = ast_to_removal_intents(ast)
        assert intents[0].dogbone is not None
        assert intents[0].dogbone.style == "t-bone_x"
        assert intents[0].dogbone.diameter_mm == 3.175

    def test_dogbone_overcut_propagates(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec(overcut_mm=0.5))
        intents = ast_to_removal_intents(ast)
        assert intents[0].dogbone is not None
        assert intents[0].dogbone.overcut_mm == 0.5


class TestDogboneAdapterToPlanner:
    def test_dogbone_generates_planner_input(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        assert len(planner_input.dogbones) == 1
        db = planner_input.dogbones[0]
        assert db.style == "dogbone"
        assert db.pocket_id == "panel"
        assert len(db.corners) == 4

    def test_no_dogbone_no_planner_input(self):
        ast = _make_pocket_ast(dogbone=None)
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)
        assert len(planner_input.dogbones) == 0

    def test_dogbone_corners_match_pocket(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        corners = planner_input.dogbones[0].corners
        assert (50.0, 35.0) in corners
        assert (150.0, 35.0) in corners
        assert (150.0, 115.0) in corners
        assert (50.0, 115.0) in corners

    def test_dogbone_depth_matches_pocket(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        assert planner_input.dogbones[0].depth_mm == 6.0

    def test_explicit_diameter_propagates(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec(diameter_mm=3.175))
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        assert planner_input.dogbones[0].tool_diameter_mm == 3.175

    def test_none_diameter_propagates(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        assert planner_input.dogbones[0].tool_diameter_mm is None

    def test_non_rect_raises(self):
        ast = LayoutAST(
            sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="Circle",
                    geometry=Geometry(data={"diameter_mm": 80}),
                    placement=Placement(center_xy_mm=(100, 75)),
                    feature=Feature(type="pocket", depth_mm=6.0, dogbone=DogboneSpec()),
                    shape_id="round_pocket",
                ),
            ),
        )
        intents = ast_to_removal_intents(ast)
        with pytest.raises(ValueError, match="only supported for rectangular"):
            removal_intents_to_planner_input(intents)


class TestDogboneCenterComputation:
    def test_diagonal_offsets_toward_interior(self):
        pocket_center = (100.0, 75.0)
        r = 1.5875
        inv_sqrt2 = 1.0 / math.sqrt(2.0)

        bl = _dogbone_center((50.0, 35.0), pocket_center, "dogbone", r)
        assert bl[0] == pytest.approx(50.0 + r * inv_sqrt2)
        assert bl[1] == pytest.approx(35.0 + r * inv_sqrt2)

        br = _dogbone_center((150.0, 35.0), pocket_center, "dogbone", r)
        assert br[0] == pytest.approx(150.0 - r * inv_sqrt2)
        assert br[1] == pytest.approx(35.0 + r * inv_sqrt2)

        tr = _dogbone_center((150.0, 115.0), pocket_center, "dogbone", r)
        assert tr[0] == pytest.approx(150.0 - r * inv_sqrt2)
        assert tr[1] == pytest.approx(115.0 - r * inv_sqrt2)

        tl = _dogbone_center((50.0, 115.0), pocket_center, "dogbone", r)
        assert tl[0] == pytest.approx(50.0 + r * inv_sqrt2)
        assert tl[1] == pytest.approx(115.0 - r * inv_sqrt2)

    def test_tbone_x_offsets(self):
        pocket_center = (100.0, 75.0)
        r = 1.5875

        bl = _dogbone_center((50.0, 35.0), pocket_center, "t-bone_x", r)
        assert bl[0] == pytest.approx(50.0 + r)
        assert bl[1] == pytest.approx(35.0)

        br = _dogbone_center((150.0, 35.0), pocket_center, "t-bone_x", r)
        assert br[0] == pytest.approx(150.0 - r)
        assert br[1] == pytest.approx(35.0)

    def test_tbone_y_offsets(self):
        pocket_center = (100.0, 75.0)
        r = 1.5875

        bl = _dogbone_center((50.0, 35.0), pocket_center, "t-bone_y", r)
        assert bl[0] == pytest.approx(50.0)
        assert bl[1] == pytest.approx(35.0 + r)

        tr = _dogbone_center((150.0, 115.0), pocket_center, "t-bone_y", r)
        assert tr[0] == pytest.approx(150.0)
        assert tr[1] == pytest.approx(115.0 - r)

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown dogbone style"):
            _dogbone_center((50.0, 35.0), (100.0, 75.0), "invalid", 1.0)


class TestDogbonePlanner:
    def test_dogbone_generates_pass(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(width=200, height=150, thickness=19)

        passes, _summary = plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(TOOL_DB),
            material=material,
            machine=machine,
            stock=stock,
        )

        ops = [p.op for p in passes]
        assert "pocket" in ops
        assert "dogbone" in ops

    def test_dogbone_uses_smallest_tool_when_no_diameter(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(width=200, height=150, thickness=19)

        passes, _ = plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(TOOL_DB),
            material=material,
            machine=machine,
            stock=stock,
        )

        dogbone_pass = next(p for p in passes if p.op == "dogbone")
        assert dogbone_pass.tool_selection.diameter == 3.175

    def test_dogbone_uses_explicit_diameter(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec(diameter_mm=6.35))
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(width=200, height=150, thickness=19)

        passes, _ = plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(TOOL_DB),
            material=material,
            machine=machine,
            stock=stock,
        )

        dogbone_pass = next(p for p in passes if p.op == "dogbone")
        assert dogbone_pass.tool_selection.diameter == 6.35

    def test_dogbone_explicit_tool_not_found_raises(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec(diameter_mm=2.0))
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(width=200, height=150, thickness=19)

        with pytest.raises(ValueError, match=r"2\.0mm not found in tool_db"):
            plan_passes(
                planner_input,
                config=config,
                tool_db=normalize_tool_entries(TOOL_DB),
                material=material,
                machine=machine,
                stock=stock,
            )

    def test_dogbone_generates_moves(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec())
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(width=200, height=150, thickness=19)

        passes, _ = plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(TOOL_DB),
            material=material,
            machine=machine,
            stock=stock,
        )

        dogbone_pass = next(p for p in passes if p.op == "dogbone")
        assert len(dogbone_pass.moves) > 0

    def test_dogbone_without_flag_no_pass(self):
        ast = _make_pocket_ast(dogbone=None)
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        material = Material(name="MDF")
        machine = Machine()
        stock = Stock(width=200, height=150, thickness=19)

        passes, _ = plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(TOOL_DB),
            material=material,
            machine=machine,
            stock=stock,
        )

        ops = [p.op for p in passes]
        assert "dogbone" not in ops


class TestDogboneAxisAligned:
    def test_corner_shares_x_with_reference(self):
        r = 1.5875
        reference = (50.0, 75.0)
        corner = (50.0, 35.0)
        result = _dogbone_center(corner, reference, "dogbone", r)
        assert result[0] == pytest.approx(50.0)
        assert result[1] == pytest.approx(35.0 + r)

    def test_corner_shares_y_with_reference(self):
        r = 1.5875
        reference = (100.0, 35.0)
        corner = (50.0, 35.0)
        result = _dogbone_center(corner, reference, "dogbone", r)
        assert result[0] == pytest.approx(50.0 + r)
        assert result[1] == pytest.approx(35.0)

    def test_tbone_x_shares_x_with_reference(self):
        r = 1.5875
        reference = (50.0, 75.0)
        corner = (50.0, 35.0)
        result = _dogbone_center(corner, reference, "t-bone_x", r)
        assert result[0] == pytest.approx(50.0)
        assert result[1] == pytest.approx(35.0)

    def test_tbone_y_shares_y_with_reference(self):
        r = 1.5875
        reference = (100.0, 35.0)
        corner = (50.0, 35.0)
        result = _dogbone_center(corner, reference, "t-bone_y", r)
        assert result[0] == pytest.approx(50.0)
        assert result[1] == pytest.approx(35.0)

    def test_notch_two_corners_axis_aligned(self):
        r = 1.5875
        reference = (100.0, 75.0)
        left_corner = (50.0, 75.0)
        right_corner = (150.0, 75.0)

        left = _dogbone_center(left_corner, reference, "dogbone", r)
        assert left[0] == pytest.approx(50.0 + r)
        assert left[1] == pytest.approx(75.0)

        right = _dogbone_center(right_corner, reference, "dogbone", r)
        assert right[0] == pytest.approx(150.0 - r)
        assert right[1] == pytest.approx(75.0)


class TestDogboneRoundtrip:
    def test_planner_input_roundtrip(self):
        ast = _make_pocket_ast(dogbone=DogboneSpec(style="t-bone_x", diameter_mm=3.175, overcut_mm=0.5))
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        hints = planner_input.to_hints_dict()
        from cam.planner.planner_input import PlannerInput

        restored = PlannerInput.from_hints_dict(hints)
        assert len(restored.dogbones) == 1
        db = restored.dogbones[0]
        assert db.style == "t-bone_x"
        assert db.tool_diameter_mm == 3.175
        assert db.overcut_mm == 0.5
        assert len(db.corners) == 4

    def test_roundtrip_with_reference_point(self):
        from cam.planner.planner_input import DogboneInput, PlannerInput

        db_input = DogboneInput(
            id="notch_dogbone",
            pocket_id="notch_pocket",
            corners=((10.0, 5.0), (20.0, 5.0)),
            style="dogbone",
            tool_diameter_mm=3.175,
            depth_mm=9.0,
            reference_point=(15.0, 25.0),
        )
        planner_input = PlannerInput(
            units="mm",
            kerf_width_mm=3.175,
            min_channel_width_mm=6.0,
            dogbones=(db_input,),
        )

        hints = planner_input.to_hints_dict()
        restored = PlannerInput.from_hints_dict(hints)
        assert len(restored.dogbones) == 1
        db = restored.dogbones[0]
        assert db.reference_point == (15.0, 25.0)
        assert len(db.corners) == 2
        assert db.style == "dogbone"
        assert db.tool_diameter_mm == 3.175
