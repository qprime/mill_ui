import pytest

from assembly.core import Assembly, Interface, InterfaceType
from assembly.panel import PanelSpec, PanelRole, Edge
from assembly.joinery import Butt, Finger, HalfLap
from assembly.primitives import box, cubby


class TestPanelSpec:
    def test_edge_count(self):
        panel = PanelSpec(
            name="rect",
            width_mm=100,
            height_mm=50,
            thickness_mm=6.0,
        )
        assert len(panel.polygon) == 4

    def test_edge_length(self):
        panel = PanelSpec(
            name="rect",
            width_mm=100,
            height_mm=50,
            thickness_mm=6.0,
        )
        assert panel.edge_length(Edge.BOTTOM) == 100.0
        assert panel.edge_length(Edge.RIGHT) == 50.0
        assert panel.edge_length(Edge.TOP) == 100.0
        assert panel.edge_length(Edge.LEFT) == 50.0


class TestAssemblyValidation:
    def test_validates_missing_panel(self):
        panels = {
            "a": PanelSpec(name="a", width_mm=100, height_mm=50, thickness_mm=6.0),
        }
        interfaces = (
            Interface(InterfaceType.SIDE_TO_SIDE, "a", "left", "b", "right", Butt()),
        )
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown member: b"):
            assembly.validate()

    def test_validates_interface_joinery_compatibility(self):
        panels = {
            "a": PanelSpec(name="a", width_mm=100, height_mm=50, thickness_mm=6.0),
            "b": PanelSpec(name="b", width_mm=100, height_mm=50, thickness_mm=6.0),
        }
        interfaces = (
            Interface(InterfaceType.INTERNAL, "a", "bottom", "b", "top", Finger(width_mm=12)),
        )
        assembly = Assembly(members=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            assembly.validate()


class TestBoxAssembly:
    def test_basic_finger_box_has_4_side_panels(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            top="none",
            bottom="none",
        )
        assert len(assembly.panels) == 4
        assert "front" in assembly.panels
        assert "back" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels

    def test_box_with_bottom_has_5_panels(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            top="none",
        )
        assert len(assembly.panels) == 5
        assert "bottom" in assembly.panels

    def test_default_box_has_6_panels(self):
        from assembly.joinery import Captured
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
        )
        assert len(assembly.panels) == 6
        assert "top" in assembly.panels
        assert "bottom" in assembly.panels
        assert "top" in assembly.panels

    def test_finger_joint_dimensions(self):
        from assembly.joinery import Captured
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            bottom=Captured(),
        )
        front = assembly.panels["front"]
        left = assembly.panels["left_side"]
        bottom = assembly.panels["bottom"]

        assert front.edge_length(Edge.BOTTOM) == 200.0
        assert front.height_mm == 100

        assert left.width_mm == 150 - 12
        assert left.height_mm == 100

        assert bottom.width_mm == 200 - 12
        assert bottom.height_mm == 150 - 12

    def test_validates_successfully(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
        )
        assembly.validate()


class TestCubbyAssembly:
    def test_2x2_cubby_has_correct_panels(self):
        assembly = cubby(
            width=300,
            length=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        assert len(assembly.panels) == 6
        assert "top" in assembly.panels
        assert "bottom" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels
        assert "shelf_1" in assembly.panels
        assert "partition_1" in assembly.panels

    def test_3x3_cubby_has_correct_panels(self):
        assembly = cubby(
            width=450,
            length=200,
            height=450,
            thickness=18,
            rows=3,
            cols=3,
        )
        assert len(assembly.panels) == 8
        assert "shelf_1" in assembly.panels
        assert "shelf_2" in assembly.panels
        assert "partition_1" in assembly.panels
        assert "partition_2" in assembly.panels

    def test_cubby_panel_dimensions(self):
        width = 900
        depth = 300
        height = 600
        thickness = 18

        assembly = cubby(
            width=width,
            length=depth,
            height=height,
            thickness=thickness,
            rows=2,
            cols=3,
        )

        assert assembly.panels["top"].width_mm == width - 2 * thickness
        assert assembly.panels["top"].height_mm == depth
        assert assembly.panels["bottom"].width_mm == width - 2 * thickness
        assert assembly.panels["bottom"].height_mm == depth
        assert assembly.panels["left_side"].width_mm == depth
        assert assembly.panels["left_side"].height_mm == height
        assert assembly.panels["right_side"].width_mm == depth
        assert assembly.panels["right_side"].height_mm == height

        assert assembly.panels["shelf_1"].width_mm == width - 2 * thickness
        assert assembly.panels["shelf_1"].height_mm == depth
        assert assembly.panels["partition_1"].width_mm == depth
        assert assembly.panels["partition_1"].height_mm == height - 2 * thickness

    def test_cubby_half_lap_interfaces_have_both_positions(self):
        assembly = cubby(
            width=300,
            length=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        half_lap_interfaces = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == 1
        assert half_lap_interfaces[0].position_along_edge_a_mm is not None
        assert half_lap_interfaces[0].position_along_edge_b_mm is not None

    def test_3x3_cubby_intersection_positions(self):
        width = 450
        height = 450
        thickness = 18
        rows = 3
        cols = 3

        cell_width = (width - 2 * thickness) / cols
        cell_height = (height - 2 * thickness) / rows

        assembly = cubby(
            width=width,
            length=200,
            height=height,
            thickness=thickness,
            rows=rows,
            cols=cols,
        )

        half_lap_interfaces = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == 4

        positions_a = sorted([i.position_along_edge_a_mm for i in half_lap_interfaces])
        positions_b = sorted([i.position_along_edge_b_mm for i in half_lap_interfaces])

        expected_partition_1_pos = cell_width - thickness / 2
        expected_partition_2_pos = 2 * cell_width - thickness / 2
        expected_shelf_1_pos = cell_height - thickness / 2
        expected_shelf_2_pos = 2 * cell_height - thickness / 2

        assert expected_partition_1_pos in positions_a
        assert expected_partition_2_pos in positions_a
        assert expected_shelf_1_pos in positions_b
        assert expected_shelf_2_pos in positions_b

    def test_asymmetric_cubby_3x2_positions(self):
        width = 900
        height = 600
        thickness = 18
        rows = 2
        cols = 3

        cell_width = (width - 2 * thickness) / cols
        cell_height = (height - 2 * thickness) / rows

        assembly = cubby(
            width=width,
            length=300,
            height=height,
            thickness=thickness,
            rows=rows,
            cols=cols,
        )

        half_lap_interfaces = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == 2

        for interface in half_lap_interfaces:
            assert interface.position_along_edge_a_mm != interface.position_along_edge_b_mm

        positions_a = {i.position_along_edge_a_mm for i in half_lap_interfaces}
        expected_pos_on_shelf_1 = cell_width - thickness / 2
        expected_pos_on_shelf_2 = 2 * cell_width - thickness / 2
        assert positions_a == {expected_pos_on_shelf_1, expected_pos_on_shelf_2}

        positions_b = {i.position_along_edge_b_mm for i in half_lap_interfaces}
        expected_pos_on_partition = cell_height - thickness / 2
        assert positions_b == {expected_pos_on_partition}

    def test_cubby_validates_successfully(self):
        assembly = cubby(
            width=300,
            length=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        assembly.validate()

    def test_cubby_shelf_to_side_uses_captured_joinery(self):
        from assembly.joinery import Captured
        assembly = cubby(
            width=300,
            length=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        shelf_to_side = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL
            and isinstance(i.joinery, Captured)
            and "shelf" in i.panel_b
        ]
        assert len(shelf_to_side) == 2

    def test_cubby_partition_to_cap_uses_captured_joinery(self):
        from assembly.joinery import Captured
        assembly = cubby(
            width=300,
            length=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        partition_to_cap = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL
            and isinstance(i.joinery, Captured)
            and "partition" in i.panel_b
        ]
        assert len(partition_to_cap) == 2
