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
        assembly = Assembly(panels=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="Unknown panel: b"):
            assembly.validate()

    def test_validates_interface_joinery_compatibility(self):
        panels = {
            "a": PanelSpec(name="a", width_mm=100, height_mm=50, thickness_mm=6.0),
            "b": PanelSpec(name="b", width_mm=100, height_mm=50, thickness_mm=6.0),
        }
        interfaces = (
            Interface(InterfaceType.INTERNAL, "a", "bottom", "b", "top", Finger(width_mm=12)),
        )
        assembly = Assembly(panels=panels, interfaces=interfaces)
        with pytest.raises(ValueError, match="not valid for INTERNAL"):
            assembly.validate()


class TestBoxAssembly:
    def test_basic_finger_box_has_4_side_panels(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            bottom=None,
        )
        assert len(assembly.panels) == 4
        assert "front" in assembly.panels
        assert "back" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels

    def test_box_with_bottom_has_5_panels(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
        )
        assert len(assembly.panels) == 5
        assert "bottom" in assembly.panels

    def test_box_with_top_has_6_panels(self):
        from assembly.joinery import Captured
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            top=Captured(),
        )
        assert len(assembly.panels) == 6
        assert "top" in assembly.panels

    def test_finger_joint_dimensions(self):
        from assembly.joinery import Captured
        assembly = box(
            width=200,
            depth=150,
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
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
        )
        assembly.validate()


class TestCubbyAssembly:
    def test_2x2_cubby_has_correct_panels(self):
        assembly = cubby(
            width=300,
            depth=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        assert len(assembly.panels) == 6
        assert "front" in assembly.panels
        assert "back" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels
        assert "shelf_1" in assembly.panels
        assert "partition_1" in assembly.panels

    def test_3x3_cubby_has_correct_panels(self):
        assembly = cubby(
            width=450,
            depth=200,
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

    def test_cubby_internal_interfaces_have_position_mm(self):
        assembly = cubby(
            width=300,
            depth=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        internal_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.INTERNAL]
        assert len(internal_interfaces) == 1
        assert internal_interfaces[0].position_mm is not None

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
            depth=200,
            height=height,
            thickness=thickness,
            rows=rows,
            cols=cols,
        )

        internal_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.INTERNAL]
        assert len(internal_interfaces) == 4

        positions = sorted([i.position_mm for i in internal_interfaces])

        expected_partition_1_pos = cell_width - thickness / 2
        expected_partition_2_pos = 2 * cell_width - thickness / 2

        assert expected_partition_1_pos in positions
        assert expected_partition_2_pos in positions

    def test_cubby_validates_successfully(self):
        assembly = cubby(
            width=300,
            depth=200,
            height=300,
            thickness=18,
            rows=2,
            cols=2,
        )
        assembly.validate()
