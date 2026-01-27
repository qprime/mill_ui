import pytest
from generators.assemblies import BoxParams, DadoSpec, FingerStrategy, PanelSpec, compute_box_panels
from joints.profiles import FingerJointProfile


class TestFingerStrategy:
    def test_by_count_valid(self):
        strategy = FingerStrategy(mode="by_count", value=5)
        assert strategy.mode == "by_count"
        assert strategy.value == 5

    def test_by_size_valid(self):
        strategy = FingerStrategy(mode="by_size", value=12.0)
        assert strategy.mode == "by_size"
        assert strategy.value == 12.0

    def test_by_count_requires_positive_int(self):
        with pytest.raises(ValueError, match="by_count"):
            FingerStrategy(mode="by_count", value=0)

        with pytest.raises(ValueError, match="by_count"):
            FingerStrategy(mode="by_count", value=-1)

    def test_by_size_requires_positive(self):
        with pytest.raises(ValueError, match="by_size"):
            FingerStrategy(mode="by_size", value=0)

        with pytest.raises(ValueError, match="by_size"):
            FingerStrategy(mode="by_size", value=-5.0)


class TestBoxParams:
    def test_valid_finger_box(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
        )
        assert params.joinery == "finger"

    def test_valid_butt_box(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
        )
        assert params.joinery == "butt"

    def test_finger_requires_strategy(self):
        with pytest.raises(ValueError, match="finger_strategy required"):
            BoxParams(
                outer_width_mm=200,
                outer_depth_mm=150,
                outer_height_mm=100,
                thickness_mm=6,
                joinery="finger",
            )

    def test_positive_dimensions_required(self):
        with pytest.raises(ValueError, match="outer_width_mm"):
            BoxParams(
                outer_width_mm=0,
                outer_depth_mm=150,
                outer_height_mm=100,
                thickness_mm=6,
                joinery="butt",
            )


class TestComputeBoxPanels:
    def test_butt_box_panel_count(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
            include_bottom=True,
            include_lid=False,
        )
        panels = compute_box_panels(params)

        assert len(panels) == 5
        names = [p.name for p in panels]
        assert "front" in names
        assert "back" in names
        assert "left_side" in names
        assert "right_side" in names
        assert "bottom" in names

    def test_finger_box_panel_count(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            include_bottom=True,
            include_lid=True,
        )
        panels = compute_box_panels(params)

        assert len(panels) == 6
        names = [p.name for p in panels]
        assert "top" in names

    def test_finger_box_front_has_finger_joints(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")

        assert isinstance(front.edge_joints["left"], FingerJointProfile)
        assert isinstance(front.edge_joints["right"], FingerJointProfile)
        assert front.edge_joints["top"] is None
        assert front.edge_joints["bottom"] is None

    def test_finger_box_phase_assignments(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        left = next(p for p in panels if p.name == "left_side")

        assert front.edge_joints["left"].phase == 0
        assert left.edge_joints["right"].phase == 1

    def test_panel_dimensions_finger_joint(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert front.width_mm == 200
        assert front.height_mm == 100 - 2 * 6

        left = next(p for p in panels if p.name == "left_side")
        assert left.width_mm == 150 - 2 * 6
        assert left.height_mm == 100 - 2 * 6

        bottom = next(p for p in panels if p.name == "bottom")
        assert bottom.width_mm == 200 - 2 * 6
        assert bottom.height_mm == 150 - 2 * 6

    def test_mating_edges_symmetric(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        left = next(p for p in panels if p.name == "left_side")

        assert front.mating_edges["left"] == "left_side.right"
        assert left.mating_edges["right"] == "front.left"

    def test_no_bottom_option(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
            include_bottom=False,
        )
        panels = compute_box_panels(params)

        names = [p.name for p in panels]
        assert "bottom" not in names
        assert len(panels) == 4

    def test_clearance_passed_to_profiles(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            clearance_mm=0.2,
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert front.edge_joints["left"].clearance_mm == 0.2


class TestBottomTopStyles:
    def test_captured_bottom_default_dimensions(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="captured",
        )
        panels = compute_box_panels(params)

        bottom = next(p for p in panels if p.name == "bottom")
        assert bottom.width_mm == 200 - 2 * 6
        assert bottom.height_mm == 150 - 2 * 6
        assert len(bottom.dados) == 0

    def test_finger_bottom_dimensions(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="finger",
        )
        panels = compute_box_panels(params)

        bottom = next(p for p in panels if p.name == "bottom")
        assert bottom.width_mm == 200
        assert bottom.height_mm == 150

    def test_finger_bottom_has_finger_joints(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="finger",
        )
        panels = compute_box_panels(params)

        bottom = next(p for p in panels if p.name == "bottom")
        assert isinstance(bottom.edge_joints["top"], FingerJointProfile)
        assert isinstance(bottom.edge_joints["bottom"], FingerJointProfile)
        assert isinstance(bottom.edge_joints["left"], FingerJointProfile)
        assert isinstance(bottom.edge_joints["right"], FingerJointProfile)

    def test_finger_bottom_walls_have_bottom_edge_fingers(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="finger",
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        left = next(p for p in panels if p.name == "left_side")

        assert isinstance(front.edge_joints["bottom"], FingerJointProfile)
        assert isinstance(left.edge_joints["bottom"], FingerJointProfile)

    def test_finger_bottom_wall_height_adjustment(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="finger",
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert front.height_mm == 100 - 6

    def test_dado_bottom_dimensions(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="dado",
        )
        panels = compute_box_panels(params)

        bottom = next(p for p in panels if p.name == "bottom")
        dado_depth = 6 / 2
        assert bottom.width_mm == 200 - 2 * 6 + 2 * dado_depth
        assert bottom.height_mm == 150 - 2 * 6 + 2 * dado_depth

    def test_dado_bottom_walls_have_dado_specs(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="dado",
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert len(front.dados) == 1
        assert front.dados[0].edge == "bottom"
        assert front.dados[0].width_mm == 6
        assert front.dados[0].depth_mm == 3

    def test_dado_bottom_inset(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            bottom_style="dado",
            dado_inset_mm=10.0,
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert front.dados[0].position_from_edge_mm == 10.0

    def test_finger_top_with_lid(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            include_lid=True,
            top_style="finger",
        )
        panels = compute_box_panels(params)

        top = next(p for p in panels if p.name == "top")
        assert top.width_mm == 200
        assert top.height_mm == 150
        assert isinstance(top.edge_joints["top"], FingerJointProfile)

    def test_dado_top_with_lid(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            include_lid=True,
            top_style="dado",
            dado_drop_mm=5.0,
        )
        panels = compute_box_panels(params)

        top = next(p for p in panels if p.name == "top")
        dado_depth = 6 / 2
        assert top.width_mm == 200 - 2 * 6 + 2 * dado_depth
        assert top.height_mm == 150 - 2 * 6 + 2 * dado_depth

        front = next(p for p in panels if p.name == "front")
        top_dado = next(d for d in front.dados if d.edge == "top")
        assert top_dado.position_from_edge_mm == 5.0

    def test_finger_bottom_and_top(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            include_lid=True,
            bottom_style="finger",
            top_style="finger",
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert front.height_mm == 100

        assert isinstance(front.edge_joints["bottom"], FingerJointProfile)
        assert isinstance(front.edge_joints["top"], FingerJointProfile)

    def test_dado_bottom_and_dado_top(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
            include_lid=True,
            bottom_style="dado",
            top_style="dado",
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert len(front.dados) == 2

        bottom_dado = next(d for d in front.dados if d.edge == "bottom")
        top_dado = next(d for d in front.dados if d.edge == "top")
        assert bottom_dado is not None
        assert top_dado is not None

    def test_butt_joint_dado_bottom(self):
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
            bottom_style="dado",
        )
        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert len(front.dados) == 1
        assert front.dados[0].edge == "bottom"


class TestDadoSpec:
    def test_dado_spec_creation(self):
        dado = DadoSpec(
            position_from_edge_mm=5.0,
            width_mm=6.0,
            depth_mm=3.0,
            edge="bottom",
        )
        assert dado.position_from_edge_mm == 5.0
        assert dado.width_mm == 6.0
        assert dado.depth_mm == 3.0
        assert dado.edge == "bottom"

    def test_dado_spec_frozen(self):
        dado = DadoSpec(
            position_from_edge_mm=5.0,
            width_mm=6.0,
            depth_mm=3.0,
            edge="bottom",
        )
        with pytest.raises(AttributeError):
            dado.width_mm = 10.0
