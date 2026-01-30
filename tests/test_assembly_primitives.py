import pytest

from assembly.core import Assembly, InterfaceType
from assembly.panel import PanelSpec, PanelRole, Edge
from assembly.joinery import Butt, Finger, Captured, HalfLap
from assembly.primitives import box, carcass, cubby


class TestBoxPrimitive:
    def test_creates_four_side_panels(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        assert "front" in assembly.panels
        assert "back" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels

    def test_front_back_have_full_width(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        assert assembly.panels["front"].width_mm == 200
        assert assembly.panels["back"].width_mm == 200

    def test_sides_have_reduced_width_for_joinery(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        assert assembly.panels["left_side"].width_mm == 150 - 2 * 6
        assert assembly.panels["right_side"].width_mm == 150 - 2 * 6

    def test_all_panels_have_full_height(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        for name, panel in assembly.panels.items():
            if name in ("front", "back", "left_side", "right_side"):
                assert panel.height_mm == 100

    def test_default_bottom_is_captured(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        assert "bottom" in assembly.panels
        bottom_interfaces = [i for i in assembly.interfaces if "bottom" in (i.panel_a, i.panel_b)]
        assert len(bottom_interfaces) == 4
        assert all(isinstance(i.joinery, Captured) for i in bottom_interfaces)

    def test_no_top_by_default(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        assert "top" not in assembly.panels

    def test_explicit_top(self):
        assembly = box(width=200, depth=150, height=100, thickness=6, top=Captured())
        assert "top" in assembly.panels
        top_interfaces = [i for i in assembly.interfaces if "top" in (i.panel_a, i.panel_b)]
        assert len(top_interfaces) == 4

    def test_no_bottom_when_none(self):
        assembly = box(width=200, depth=150, height=100, thickness=6, bottom=None)
        assert "bottom" not in assembly.panels

    def test_no_bottom_when_string_none(self):
        assembly = box(width=200, depth=150, height=100, thickness=6, bottom="none")
        assert "bottom" not in assembly.panels

    def test_bottom_dimensions_account_for_side_thickness(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        bottom = assembly.panels["bottom"]
        assert bottom.width_mm == 200 - 2 * 6
        assert bottom.height_mm == 150 - 2 * 6

    def test_side_to_side_interfaces(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        side_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.SIDE_TO_SIDE]
        assert len(side_interfaces) == 4

    def test_custom_side_joinery(self):
        assembly = box(width=200, depth=150, height=100, thickness=6, side_joinery=Butt())
        side_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.SIDE_TO_SIDE]
        assert all(isinstance(i.joinery, Butt) for i in side_interfaces)

    def test_panel_roles_assigned(self):
        assembly = box(width=200, depth=150, height=100, thickness=6)
        assert assembly.panels["front"].role == PanelRole.FRONT
        assert assembly.panels["back"].role == PanelRole.BACK
        assert assembly.panels["left_side"].role == PanelRole.LEFT
        assert assembly.panels["right_side"].role == PanelRole.RIGHT
        assert assembly.panels["bottom"].role == PanelRole.BOTTOM


class TestBoxResolve:
    def test_finger_joints_create_notches(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            bottom=None,
        )
        panels = assembly.resolve()
        front = next(p for p in panels if p.name == "front")
        assert len(front.notches) > 0

    def test_captured_bottom_creates_dados(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
            bottom=Captured(),
        )
        panels = assembly.resolve()
        front = next(p for p in panels if p.name == "front")
        assert len(front.dados) > 0

    def test_resolve_returns_all_panels(self):
        assembly = box(
            width=200,
            depth=150,
            height=100,
            thickness=6,
            bottom=Captured(),
            top=Captured(),
        )
        panels = assembly.resolve()
        names = {p.name for p in panels}
        assert names == {"front", "back", "left_side", "right_side", "bottom", "top"}


class TestCarcassPrimitive:
    def test_creates_sides_and_caps(self):
        assembly = carcass(width=600, depth=400, height=500, thickness=18)
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels
        assert "top" in assembly.panels
        assert "bottom" in assembly.panels

    def test_between_sides_cap_dimensions(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            cap_style="between_sides",
        )
        top = assembly.panels["top"]
        assert top.width_mm == 600 - 2 * 18
        assert top.height_mm == 400

    def test_over_sides_cap_dimensions(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            cap_style="over_sides",
        )
        top = assembly.panels["top"]
        assert top.width_mm == 600

    def test_over_sides_reduces_side_height(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            cap_style="over_sides",
        )
        left = assembly.panels["left_side"]
        assert left.height_mm == 500 - 2 * 18

    def test_default_butt_joinery(self):
        assembly = carcass(width=600, depth=400, height=500, thickness=18)
        top_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.TOP]
        assert all(isinstance(i.joinery, Butt) for i in top_interfaces)

    def test_no_top_when_none(self):
        assembly = carcass(width=600, depth=400, height=500, thickness=18, top=None)
        assert "top" not in assembly.panels

    def test_no_bottom_when_none(self):
        assembly = carcass(width=600, depth=400, height=500, thickness=18, bottom=None)
        assert "bottom" not in assembly.panels

    def test_fixed_shelves_creates_shelf_panels(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
        )
        assert "shelf_1" in assembly.panels
        assert "shelf_2" in assembly.panels

    def test_shelf_interfaces_are_internal(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
        )
        shelf_interfaces = [
            i for i in assembly.interfaces
            if "shelf" in i.panel_a or "shelf" in i.panel_b
        ]
        assert all(i.type == InterfaceType.INTERNAL for i in shelf_interfaces)

    def test_shelf_joinery_default_is_captured(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
        )
        shelf_interfaces = [
            i for i in assembly.interfaces
            if "shelf" in i.panel_a or "shelf" in i.panel_b
        ]
        assert all(isinstance(i.joinery, Captured) for i in shelf_interfaces)

    def test_vertical_partitions_creates_partition_panels(self):
        assembly = carcass(
            width=1200,
            depth=400,
            height=500,
            thickness=18,
            vertical_partitions=3,
        )
        assert "partition_1" in assembly.panels
        assert "partition_2" in assembly.panels
        assert "partition_3" in assembly.panels

    def test_partition_interfaces_are_internal(self):
        assembly = carcass(
            width=1200,
            depth=400,
            height=500,
            thickness=18,
            vertical_partitions=2,
        )
        partition_interfaces = [
            i for i in assembly.interfaces
            if "partition" in i.panel_a or "partition" in i.panel_b
        ]
        assert all(i.type == InterfaceType.INTERNAL for i in partition_interfaces)

    def test_back_panel_created_when_specified(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            back=Captured(),
            back_thickness=6,
        )
        assert "back" in assembly.panels
        assert assembly.panels["back"].thickness_mm == 18

    def test_back_inset_affects_back_dimensions(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            back=Captured(),
            back_thickness=6,
            back_inset=18,
        )
        back = assembly.panels["back"]
        assert back.width_mm == 600 - 2 * 18
        assert back.height_mm == 500 - 2 * 18


class TestCarcassResolve:
    def test_shelf_joinery_creates_dados_in_sides(self):
        assembly = carcass(
            width=600,
            depth=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
            shelf_joinery=Captured(),
        )
        panels = assembly.resolve()
        left = next(p for p in panels if p.name == "left_side")
        assert len(left.dados) == 2


class TestCubbyPrimitive:
    def test_creates_perimeter_panels(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=2,
            cols=3,
        )
        assert "top" in assembly.panels
        assert "bottom" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels

    def test_creates_internal_shelves(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=3,
            cols=2,
        )
        assert "shelf_1" in assembly.panels
        assert "shelf_2" in assembly.panels

    def test_creates_internal_partitions(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=2,
            cols=4,
        )
        assert "partition_1" in assembly.panels
        assert "partition_2" in assembly.panels
        assert "partition_3" in assembly.panels

    def test_perimeter_interfaces_use_perimeter_joinery(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=2,
            cols=3,
            perimeter_joinery=Finger(width_mm=15),
        )
        perimeter_interfaces = [
            i for i in assembly.interfaces
            if i.type in (InterfaceType.TOP, InterfaceType.BOTTOM)
        ]
        assert len(perimeter_interfaces) == 4
        assert all(isinstance(i.joinery, Finger) for i in perimeter_interfaces)

    def test_internal_half_lap_interfaces_use_internal_joinery(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=2,
            cols=2,
            internal_joinery=HalfLap(),
        )
        half_lap_interfaces = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == 1

    def test_shelf_partition_grid_intersections(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=3,
            cols=3,
        )
        half_lap_interfaces = [
            i for i in assembly.interfaces
            if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == (3 - 1) * (3 - 1)

    def test_single_row_no_shelves(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=1,
            cols=3,
        )
        shelf_panels = [name for name in assembly.panels if "shelf" in name]
        assert len(shelf_panels) == 0

    def test_single_col_no_partitions(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=3,
            cols=1,
        )
        partition_panels = [name for name in assembly.panels if "partition" in name]
        assert len(partition_panels) == 0


class TestCubbyResolve:
    def test_finger_perimeter_creates_notches(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=2,
            cols=2,
            perimeter_joinery=Finger(width_mm=15),
        )
        panels = assembly.resolve()
        top = next(p for p in panels if p.name == "top")
        assert len(top.notches) > 0

    def test_half_lap_internal_creates_notches(self):
        assembly = cubby(
            width=900,
            depth=300,
            height=600,
            thickness=18,
            rows=2,
            cols=2,
            internal_joinery=HalfLap(),
        )
        panels = assembly.resolve()
        shelf = next(p for p in panels if p.name == "shelf_1")
        partition = next(p for p in panels if p.name == "partition_1")
        assert len(shelf.notches) > 0
        assert len(partition.notches) > 0


class TestPanelSpec:
    def test_edge_length_horizontal(self):
        panel = PanelSpec("test", width_mm=100, height_mm=50, thickness_mm=6)
        assert panel.edge_length(Edge.BOTTOM) == 100
        assert panel.edge_length(Edge.TOP) == 100

    def test_edge_length_vertical(self):
        panel = PanelSpec("test", width_mm=100, height_mm=50, thickness_mm=6)
        assert panel.edge_length(Edge.LEFT) == 50
        assert panel.edge_length(Edge.RIGHT) == 50

    def test_polygon_centered_at_origin(self):
        panel = PanelSpec("test", width_mm=100, height_mm=50, thickness_mm=6)
        poly = panel.polygon
        assert poly == ((-50, -25), (50, -25), (50, 25), (-50, 25))

    def test_polygon_with_custom_origin(self):
        panel = PanelSpec("test", width_mm=100, height_mm=50, thickness_mm=6, origin=(100, 100))
        poly = panel.polygon
        assert poly == ((50, 75), (150, 75), (150, 125), (50, 125))

    def test_with_notches_returns_new_panel(self):
        panel = PanelSpec("test", width_mm=100, height_mm=50, thickness_mm=6)
        from assembly.panel import NotchSpec
        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=10, u_len_mm=20, depth_mm=6)
        new_panel = panel.with_notches((notch,))
        assert len(new_panel.notches) == 1
        assert len(panel.notches) == 0

    def test_with_dados_returns_new_panel(self):
        panel = PanelSpec("test", width_mm=100, height_mm=50, thickness_mm=6)
        from assembly.panel import DadoSpec
        dado = DadoSpec(position_from_edge_mm=10, width_mm=6, depth_mm=3, edge="bottom")
        new_panel = panel.with_dados((dado,))
        assert len(new_panel.dados) == 1
        assert len(panel.dados) == 0
