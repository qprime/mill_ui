import pytest

from assembly.core import Assembly, Interface, InterfaceType
from assembly.panel import PanelSpec, PanelRole, NotchSpec
from assembly.joinery import Butt, Finger, Captured
from assembly.primitives import box, carcass


class TestAssemblyResolve:
    def test_butt_joint_box_no_notches(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Butt(),
            bottom=None,
        )
        panels = assembly.resolve()

        assert len(panels) == 4

        for panel in panels:
            assert len(panel.notches) == 0

    def test_finger_joint_box_has_notches(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12.0),
            bottom=Captured(),
        )
        panels = assembly.resolve()

        front_panel = next(p for p in panels if p.name == "front")
        front_notches = front_panel.notches
        assert len(front_notches) > 0
        for notch in front_notches:
            assert isinstance(notch, NotchSpec)

    def test_panel_dimensions_preserved(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12.0),
        )
        panels = assembly.resolve()

        for panel in panels:
            original = assembly.panels[panel.name]
            assert panel.width_mm == original.width_mm
            assert panel.height_mm == original.height_mm

    def test_captured_bottom_creates_dados(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12.0),
            bottom=Captured(),
        )
        panels = assembly.resolve()

        front_panel = next(p for p in panels if p.name == "front")
        assert len(front_panel.dados) > 0

    def test_phase_assignment_ensures_interlock(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12.0),
            bottom=None,
        )
        panels = assembly.resolve()

        panel_by_name = {p.name: p for p in panels}

        front = panel_by_name["front"]
        left = panel_by_name["left_side"]

        front_notches = [n for n in front.notches]
        left_notches = [n for n in left.notches]

        assert len(front_notches) > 0
        assert len(left_notches) > 0
        front_positions = set(n.u_start_mm for n in front_notches)
        left_positions = set(n.u_start_mm for n in left_notches)
        assert front_positions != left_positions


class TestCarcassAssembly:
    def test_basic_carcass_has_four_panels(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
        )
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels
        assert "top" in assembly.panels
        assert "bottom" in assembly.panels
        assert len(assembly.panels) == 4

    def test_side_panel_dimensions(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
        )
        left = assembly.panels["left_side"]
        assert left.width_mm == 560
        assert left.height_mm == 720

    def test_between_sides_cap_style(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            cap_style="between_sides",
        )
        top = assembly.panels["top"]
        expected_width = 600 - 2 * 18
        assert top.width_mm == expected_width

    def test_over_sides_cap_style(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            cap_style="over_sides",
        )
        top = assembly.panels["top"]
        assert top.width_mm == 600

    def test_captured_back_creates_back_panel(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            back=Captured(),
            back_thickness=6,
            back_inset=18,
        )
        assert "back" in assembly.panels

    def test_fixed_shelves_creates_shelf_panels(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            fixed_shelves=2,
        )
        assert "shelf_1" in assembly.panels
        assert "shelf_2" in assembly.panels

    def test_vertical_partitions_creates_partition_panels(self):
        assembly = carcass(
            width=1200,
            depth=300,
            height=900,
            thickness=18,
            vertical_partitions=3,
        )
        assert "partition_1" in assembly.panels
        assert "partition_2" in assembly.panels
        assert "partition_3" in assembly.panels

    def test_full_carcass_panel_generation(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            back=Captured(),
            back_thickness=6,
            back_inset=18,
            fixed_shelves=2,
        )
        panels = assembly.resolve()
        panel_names = {p.name for p in panels}
        assert "left_side" in panel_names
        assert "right_side" in panel_names
        assert "top" in panel_names
        assert "bottom" in panel_names
        assert "back" in panel_names
        assert "shelf_1" in panel_names
        assert "shelf_2" in panel_names

    def test_no_top_excludes_top_panel(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            top=None,
        )
        assert "top" not in assembly.panels

    def test_no_bottom_excludes_bottom_panel(self):
        assembly = carcass(
            width=600,
            depth=560,
            height=720,
            thickness=18,
            bottom=None,
        )
        assert "bottom" not in assembly.panels
