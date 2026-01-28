import pytest

from assembly import (
    AssemblyParams,
    AssemblyTopology,
    ButtJoineryStrategy,
    FingerJoineryStrategy,
    box_topology,
    frameless_cabinet_topology,
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


class TestFramelessCabinetTopology:
    def test_basic_carcass_has_four_panels(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
        )
        assert "left_side" in topo.faces
        assert "right_side" in topo.faces
        assert "top" in topo.faces
        assert "bottom" in topo.faces
        assert len(topo.faces) == 4

    def test_side_panel_dimensions(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
        )
        left = topo.faces["left_side"]
        assert left.polygon[1][0] == 560
        assert left.polygon[2][1] == 720

    def test_between_sides_cap_style(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            cap_style="between_sides",
        )
        top = topo.faces["top"]
        expected_width = 600 - 2 * 18
        assert top.polygon[1][0] == expected_width

    def test_over_sides_cap_style(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            cap_style="over_sides",
        )
        top = topo.faces["top"]
        assert top.polygon[1][0] == 600

    def test_captured_back_creates_back_panel(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            back="captured",
            back_thickness_mm=6,
            back_inset_mm=18,
            back_dado_depth_mm=6,
        )
        assert "back" in topo.faces

    def test_captured_back_creates_dados(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            back="captured",
            back_thickness_mm=6,
            back_inset_mm=18,
        )
        back_dados = [f for f in topo.mating_features if f.mates_with == "back"]
        assert len(back_dados) == 4

    def test_fixed_shelves_creates_shelf_faces(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            fixed_shelves=2,
        )
        assert "shelf_01" in topo.faces
        assert "shelf_02" in topo.faces

    def test_fixed_shelves_creates_dados_in_sides(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            fixed_shelves=2,
        )
        shelf_dados = [f for f in topo.mating_features if f.mates_with and f.mates_with.startswith("shelf")]
        assert len(shelf_dados) == 4

    def test_vertical_partitions_creates_partition_faces(self):
        topo = frameless_cabinet_topology(
            width_mm=1200,
            depth_mm=300,
            height_mm=900,
            thickness_mm=18,
            vertical_partitions=3,
        )
        assert "partition_01" in topo.faces
        assert "partition_02" in topo.faces
        assert "partition_03" in topo.faces

    def test_vertical_partitions_creates_dados_in_top_bottom(self):
        topo = frameless_cabinet_topology(
            width_mm=1200,
            depth_mm=300,
            height_mm=900,
            thickness_mm=18,
            vertical_partitions=2,
        )
        partition_dados = [f for f in topo.mating_features if f.mates_with and f.mates_with.startswith("partition")]
        assert len(partition_dados) == 4

    def test_finger_joinery_creates_mating_edges(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            joinery="finger",
            cap_style="between_sides",
        )
        assert len(topo.mating_edges) == 4

    def test_butt_joinery_no_mating_edges(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            joinery="butt",
        )
        assert len(topo.mating_edges) == 0

    def test_full_carcass_panel_generation(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            back="captured",
            back_thickness_mm=6,
            back_inset_mm=18,
            fixed_shelves=2,
        )
        params = AssemblyParams(
            topology=topo,
            joinery_strategy=ButtJoineryStrategy(),
        )
        panels = generate_assembly_panels(params)
        panel_names = {p.name for p in panels}
        assert "left_side" in panel_names
        assert "right_side" in panel_names
        assert "top" in panel_names
        assert "bottom" in panel_names
        assert "back" in panel_names
        assert "shelf_01" in panel_names
        assert "shelf_02" in panel_names

    def test_shelf_setback_affects_shelf_depth(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            fixed_shelves=1,
            shelf_setback_front_mm=20,
            shelf_setback_back_mm=10,
        )
        shelf = topo.faces["shelf_01"]
        expected_depth = 560 - 20 - 10
        assert shelf.polygon[2][1] == expected_depth

    def test_no_top_excludes_top_panel(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            include_top=False,
        )
        assert "top" not in topo.faces

    def test_no_bottom_excludes_bottom_panel(self):
        topo = frameless_cabinet_topology(
            width_mm=600,
            depth_mm=560,
            height_mm=720,
            thickness_mm=18,
            include_bottom=False,
        )
        assert "bottom" not in topo.faces
