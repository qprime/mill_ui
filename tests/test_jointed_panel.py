import pytest
from generators.panels import JointedPanelParams, jointed_panel_generator
from joints.profiles import FingerJointProfile


class TestJointedPanelParams:
    def test_validation_positive_dimensions(self):
        with pytest.raises(ValueError, match="width_mm must be positive"):
            JointedPanelParams(width_mm=0, height_mm=50, edge_joints={}).validate()

        with pytest.raises(ValueError, match="height_mm must be positive"):
            JointedPanelParams(width_mm=100, height_mm=-1, edge_joints={}).validate()

    def test_validation_invalid_edge_name(self):
        with pytest.raises(ValueError, match="invalid edge name"):
            JointedPanelParams(
                width_mm=100,
                height_mm=50,
                edge_joints={"north": FingerJointProfile(depth_mm=6.0, count=5)},
            ).validate()

    def test_valid_params(self):
        params = JointedPanelParams(
            width_mm=100,
            height_mm=50,
            edge_joints={
                "bottom": FingerJointProfile(depth_mm=6.0, count=5),
            },
        )
        params.validate()


class TestJointedPanelGenerator:
    def test_simple_rectangle_no_joints(self):
        params = JointedPanelParams(
            width_mm=100,
            height_mm=50,
            edge_joints={},
        )
        items = jointed_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].feature.type == "profile"
        assert "points" in items[0].geometry.data

    def test_panel_with_finger_joints(self):
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)
        params = JointedPanelParams(
            width_mm=100,
            height_mm=50,
            edge_joints={"bottom": profile, "top": profile},
        )
        items = jointed_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert len(items[0].geometry.data["points"]) > 4

    def test_panel_with_part_name(self):
        params = JointedPanelParams(
            width_mm=100,
            height_mm=50,
            edge_joints={},
            part_name="FRONT",
        )
        items = jointed_panel_generator(params, center=(50, 25))

        assert "front" in items[0].shape_id.lower()

    def test_panel_all_four_joints(self):
        profile = FingerJointProfile(depth_mm=6.0, count=5, clearance_mm=0.0)
        params = JointedPanelParams(
            width_mm=100,
            height_mm=100,
            edge_joints={
                "bottom": profile,
                "right": FingerJointProfile(depth_mm=6.0, count=5, phase=1, clearance_mm=0.0),
                "top": profile,
                "left": FingerJointProfile(depth_mm=6.0, count=5, phase=1, clearance_mm=0.0),
            },
        )
        items = jointed_panel_generator(params, center=(50, 50))

        assert len(items) == 1
        geom = items[0].geometry
        assert len(geom.data["points"]) > 4

    def test_panel_profile_is_through_cut(self):
        params = JointedPanelParams(
            width_mm=100,
            height_mm=50,
            edge_joints={},
        )
        items = jointed_panel_generator(params, center=(50, 25))

        assert items[0].feature.depth == "through"

    def test_panel_with_opposing_phases(self):
        profile_phase0 = FingerJointProfile(depth_mm=6.0, count=5, phase=0, clearance_mm=0.0)
        profile_phase1 = FingerJointProfile(depth_mm=6.0, count=5, phase=1, clearance_mm=0.0)
        params = JointedPanelParams(
            width_mm=100,
            height_mm=50,
            edge_joints={"left": profile_phase0, "right": profile_phase1},
        )
        items = jointed_panel_generator(params, center=(50, 25))

        assert len(items) == 1
