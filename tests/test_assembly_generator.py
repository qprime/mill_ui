import pytest

from assembly import (
    AssemblyParams,
    AssemblyTopology,
    ButtJoineryStrategy,
    FingerJoineryStrategy,
    box_topology,
    generate_assembly_panels,
)
from joints.profiles import FingerJointProfile


class TestGenerateAssemblyPanels:
    def test_butt_joint_box_no_edge_joints(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="butt",
            include_bottom=True,
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=ButtJoineryStrategy(),
        )
        panels = generate_assembly_panels(params)

        assert len(panels) == 5

        for panel in panels:
            assert len(panel.edge_joints) == 0

    def test_finger_joint_box_has_profiles(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
            bottom_style="captured",
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=FingerJoineryStrategy(finger_width_mm=12.0),
        )
        panels = generate_assembly_panels(params)

        front_panel = next(p for p in panels if p.name == "front")
        assert 1 in front_panel.edge_joints
        assert 3 in front_panel.edge_joints
        assert isinstance(front_panel.edge_joints[1], FingerJointProfile)
        assert isinstance(front_panel.edge_joints[3], FingerJointProfile)

    def test_panel_polygons_match_faces(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=FingerJoineryStrategy(finger_width_mm=12.0),
        )
        panels = generate_assembly_panels(params)

        for panel in panels:
            assert panel.polygon == topo.faces[panel.name].polygon

    def test_dado_features_converted_to_specs(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
            bottom_style="dado",
            dado_inset_mm=10.0,
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=FingerJoineryStrategy(finger_width_mm=12.0),
        )
        panels = generate_assembly_panels(params)

        front_panel = next(p for p in panels if p.name == "front")
        assert len(front_panel.dados) == 1
        assert front_panel.dados[0].position_from_edge_mm == 10.0
        assert front_panel.dados[0].edge == "bottom"

    def test_phase_assignment_ensures_interlock(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=False,
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=FingerJoineryStrategy(finger_width_mm=12.0),
        )
        panels = generate_assembly_panels(params)

        panel_by_name = {p.name: p for p in panels}

        front = panel_by_name["front"]
        left = panel_by_name["left_side"]

        front_left_profile = front.edge_joints.get(3)
        left_right_profile = left.edge_joints.get(1)

        assert front_left_profile is not None
        assert left_right_profile is not None
        assert front_left_profile.phase != left_right_profile.phase

    def test_edge_overrides(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=False,
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=FingerJoineryStrategy(finger_width_mm=12.0),
            edge_overrides={
                ("front", 1): ButtJoineryStrategy(),
            },
        )
        panels = generate_assembly_panels(params)

        front = next(p for p in panels if p.name == "front")
        assert 1 not in front.edge_joints or front.edge_joints.get(1) is None
