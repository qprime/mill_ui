import pytest

from assembly.core import InterfaceType
from assembly.joinery import Butt, Captured, Finger, HalfLap
from assembly.panel import Edge, PanelRole, PanelSpec
from assembly.primitives import box, carcass, cubby


class TestBoxPrimitive:
    def test_creates_four_side_panels(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        assert "front" in assembly.panels
        assert "back" in assembly.panels
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels

    def test_front_back_have_full_width(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        assert assembly.panels["front"].width_mm == 200
        assert assembly.panels["back"].width_mm == 200

    def test_finger_sides_span_the_full_box_depth(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        assert assembly.panels["left_side"].width_mm == 150
        assert assembly.panels["right_side"].width_mm == 150

    @pytest.mark.parametrize("side_joinery", [Butt(), Captured()])
    def test_nonfinger_sides_retain_their_existing_span(self, side_joinery):
        assembly = box(width=200, length=150, height=100, thickness=6, side_joinery=side_joinery)
        assert assembly.panels["left_side"].width_mm == 138
        assert assembly.panels["right_side"].width_mm == 138

    @pytest.mark.parametrize("thickness, depth", [(6, 50), (18, 50), (18, 150)])
    def test_finger_box_side_outline_preserves_specified_dimensions(self, thickness, depth):
        from shapely.geometry import Polygon
        from shapely.geometry import box as region_box

        from assembly.notches import build_notched_polygon

        assembly = box(
            width=55,
            length=depth,
            height=40,
            thickness=thickness,
            side_joinery=Finger(width_mm=12, clearance_mm=0.2),
            top="none",
            bottom="none",
        )
        for panel in assembly.resolve():
            if panel.name not in ("left_side", "right_side"):
                continue
            outline = Polygon(build_notched_polygon(panel.width_mm, panel.height_mm, (0, 0), panel.notches))
            assert outline.is_valid
            assert outline.bounds == pytest.approx((-depth / 2, -20, depth / 2, 20))
            assert outline.covers(region_box(-depth / 2, -1, depth / 2, 1))

    def test_all_panels_have_full_height(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        for name, panel in assembly.panels.items():
            if name in ("front", "back", "left_side", "right_side"):
                assert panel.height_mm == 100

    def test_default_bottom_is_captured(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        assert "bottom" in assembly.panels
        bottom_interfaces = [i for i in assembly.interfaces if "bottom" in (i.panel_a, i.panel_b)]
        assert len(bottom_interfaces) == 4
        assert all(isinstance(i.joinery, Captured) for i in bottom_interfaces)

    def test_top_is_captured_by_default(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        assert "top" in assembly.panels
        top_interfaces = [i for i in assembly.interfaces if "top" in (i.panel_a, i.panel_b)]
        assert all(isinstance(i.joinery, Captured) for i in top_interfaces)

    def test_explicit_top(self):
        assembly = box(width=200, length=150, height=100, thickness=6, top=Captured())
        assert "top" in assembly.panels
        top_interfaces = [i for i in assembly.interfaces if "top" in (i.panel_a, i.panel_b)]
        assert len(top_interfaces) == 4

    def test_no_bottom_when_string_none_explicit(self):
        assembly = box(width=200, length=150, height=100, thickness=6, bottom="none")
        assert "bottom" not in assembly.panels

    def test_no_top_when_string_none(self):
        assembly = box(width=200, length=150, height=100, thickness=6, top="none")
        assert "top" not in assembly.panels

    def test_bottom_dimensions_account_for_side_thickness(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        bottom = assembly.panels["bottom"]
        assert bottom.width_mm == 194
        assert bottom.height_mm == 144

    @pytest.mark.parametrize(
        "cap_joinery, span, wall_height",
        [
            (Butt(), (138, 88), 80),
            (Finger(), (150, 100), 80),
            (Captured(), (144, 94), 80),
            (Captured(dado_depth_mm=1.5), (141, 91), 80),
            (Captured(receiving="b"), (150, 100), 74),
            (Captured(receiving="b", dado_depth_mm=1.5), (150, 100), 71),
        ],
    )
    def test_cap_joints_preserve_the_outside_box_dimensions(self, cap_joinery, span, wall_height):
        assembly = box(width=150, length=100, height=80, thickness=6, top=cap_joinery, bottom=cap_joinery)
        for name in ("bottom", "top"):
            cap = assembly.panels[name]
            assert (cap.width_mm, cap.height_mm) == span
        for name in ("front", "back", "left_side", "right_side"):
            assert assembly.panels[name].height_mm == wall_height

    @pytest.mark.parametrize("top", ["none", Finger(), Captured()])
    def test_one_receiving_cap_accounts_for_its_single_wall_extension(self, top):
        assembly = box(width=150, length=100, height=80, thickness=6, top=top, bottom=Captured(receiving="b"))
        assert assembly.panels["front"].height_mm == 77

    def test_finger_cap_edges_match_their_explicit_wall_interfaces(self):
        assembly = box(width=150, length=100, height=80, thickness=6, top=Finger(), bottom=Finger())
        edges = {"top": Edge.TOP, "bottom": Edge.BOTTOM, "left": Edge.LEFT, "right": Edge.RIGHT}
        for interface in assembly.interfaces:
            assert assembly.panels[interface.panel_a].edge_length(edges[interface.edge_a]) == assembly.panels[
                interface.panel_b
            ].edge_length(edges[interface.edge_b])

    @pytest.mark.parametrize("depth", [0, -1, 7])
    def test_captured_cap_depth_must_fit_the_receiving_stock(self, depth):
        with pytest.raises(ValueError, match="cap groove depth"):
            box(width=150, length=100, height=80, thickness=6, bottom=Captured(dado_depth_mm=depth))

    def test_receiving_cap_inset_requires_explicit_wall_placement(self):
        with pytest.raises(ValueError, match=r"receiving='b'.*inset"):
            box(width=150, length=100, height=80, thickness=6, bottom=Captured(receiving="b", inset_mm=2))

    def test_receiving_caps_must_leave_a_positive_wall_height(self):
        with pytest.raises(ValueError, match="wall height"):
            box(
                width=150,
                length=100,
                height=6,
                thickness=6,
                top=Captured(receiving="b"),
                bottom=Captured(receiving="b"),
            )

    def test_cap_joints_must_leave_a_positive_panel_span(self):
        with pytest.raises(ValueError, match="cap span"):
            box(width=6, length=100, height=80, thickness=6)

    def test_side_to_side_interfaces(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        side_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.SIDE_TO_SIDE]
        assert len(side_interfaces) == 4

    def test_custom_side_joinery(self):
        assembly = box(width=200, length=150, height=100, thickness=6, side_joinery=Butt())
        side_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.SIDE_TO_SIDE]
        assert all(isinstance(i.joinery, Butt) for i in side_interfaces)

    def test_panel_roles_assigned(self):
        assembly = box(width=200, length=150, height=100, thickness=6)
        assert assembly.panels["front"].role == PanelRole.FRONT
        assert assembly.panels["back"].role == PanelRole.BACK
        assert assembly.panels["left_side"].role == PanelRole.LEFT
        assert assembly.panels["right_side"].role == PanelRole.RIGHT
        assert assembly.panels["bottom"].role == PanelRole.BOTTOM

    def test_perimeter_joinery_sets_top_and_bottom_defaults(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            perimeter_joinery=Finger(width_mm=15),
        )
        top_interfaces = [i for i in assembly.interfaces if "top" in (i.panel_a, i.panel_b)]
        bottom_interfaces = [i for i in assembly.interfaces if "bottom" in (i.panel_a, i.panel_b)]
        assert len(top_interfaces) == 4
        assert len(bottom_interfaces) == 4
        assert all(isinstance(i.joinery, Finger) for i in top_interfaces)
        assert all(isinstance(i.joinery, Finger) for i in bottom_interfaces)

    def test_explicit_top_overrides_perimeter_joinery(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            perimeter_joinery=Finger(width_mm=15),
            top=Butt(),
        )
        top_interfaces = [i for i in assembly.interfaces if "top" in (i.panel_a, i.panel_b)]
        bottom_interfaces = [i for i in assembly.interfaces if "bottom" in (i.panel_a, i.panel_b)]
        assert all(isinstance(i.joinery, Butt) for i in top_interfaces)
        assert all(isinstance(i.joinery, Finger) for i in bottom_interfaces)


class TestBoxResolve:
    def test_panel_dimensions_preserved(self):
        assembly = box(
            width=200,
            length=150,
            height=100,
            thickness=6,
            side_joinery=Finger(width_mm=12),
        )
        panels = assembly.resolve()

        for panel in panels:
            original = assembly.panels[panel.name]
            assert panel.width_mm == original.width_mm
            assert panel.height_mm == original.height_mm

    def test_finger_joints_create_notches(self):
        assembly = box(
            width=200,
            length=150,
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
            length=150,
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
            length=150,
            height=100,
            thickness=6,
            bottom=Captured(),
            top=Captured(),
        )
        panels = assembly.resolve()
        names = {p.name for p in panels}
        assert names == {"front", "back", "left_side", "right_side", "bottom", "top"}


class TestCarcassPrimitive:
    @pytest.mark.parametrize("top_depth, bottom_depth, shelf_depth", [(9, 9, 9), (6, 9, 4)])
    def test_captured_caps_and_shelves_reach_their_side_grooves(self, top_depth, bottom_depth, shelf_depth):
        assembly = carcass(
            width=900,
            length=300,
            height=1100,
            thickness=18,
            top=Captured(dado_depth_mm=top_depth),
            bottom=Captured(dado_depth_mm=bottom_depth),
            fixed_shelves=3,
            shelf_joinery=Captured(dado_depth_mm=shelf_depth),
        )
        assert assembly.panels["top"].width_mm == 864 + 2 * top_depth
        assert assembly.panels["bottom"].width_mm == 864 + 2 * bottom_depth
        for i in range(1, 4):
            assert assembly.panels[f"shelf_{i}"].width_mm == 864 + 2 * shelf_depth

    @pytest.mark.parametrize("cap_style", ["between_sides", "over_sides"])
    def test_shelf_spacing_leaves_equal_clear_openings(self, cap_style):
        assembly = carcass(width=900, length=300, height=1100, thickness=18, cap_style=cap_style, fixed_shelves=3)
        positions = [
            i.position_along_edge_a_mm
            for i in assembly.interfaces
            if i.panel_a == "left_side" and i.type == InterfaceType.INTERNAL
        ]
        offset = 18 if cap_style == "between_sides" else 0
        assert positions == pytest.approx([offset + 252.5, offset + 523, offset + 793.5])
        assert all(assembly.panels[f"shelf_{i}"].width_mm == 882 for i in range(1, 4))

    def test_shelves_start_above_the_actual_toe_kick_bottom(self):
        assembly = carcass(
            width=600,
            length=560,
            height=720,
            thickness=18,
            fixed_shelves=1,
            toe_kick_height=100,
            top=Captured(),
            bottom=Captured(),
        )
        shelf = next(i for i in assembly.interfaces if i.panel_a == "left_side" and i.type == InterfaceType.INTERNAL)
        assert shelf.position_along_edge_a_mm == 401

    @pytest.mark.parametrize("top, expected_height", [("none", 1091), (Butt(), 1073)])
    def test_over_side_caps_account_for_only_their_exposed_thickness(self, top, expected_height):
        assembly = carcass(
            width=900,
            length=300,
            height=1100,
            thickness=18,
            cap_style="over_sides",
            top=top,
            bottom=Captured(receiving="b"),
        )
        assert assembly.panels["left_side"].height_mm == expected_height

    @pytest.mark.parametrize("depth", [0, -1, 19])
    def test_cap_groove_depth_must_fit_the_side_stock(self, depth):
        with pytest.raises(ValueError, match="cap groove depth"):
            carcass(width=900, length=300, height=1100, thickness=18, top=Captured(dado_depth_mm=depth))

    @pytest.mark.parametrize("style, receiving", [("between_sides", "b"), ("over_sides", "a")])
    def test_captured_cap_placement_must_agree_with_its_receiving_panel(self, style, receiving):
        with pytest.raises(ValueError, match="cap_style"):
            carcass(
                width=900, length=300, height=1100, thickness=18, cap_style=style, top=Captured(receiving=receiving)
            )

    @pytest.mark.parametrize(
        "joinery, root_depth, expected_depth",
        [("dado", 6, 6), ("{joinery: captured, dado_depth: 4mm}", 6, 4), ("captured", 0, None)],
    )
    def test_pml_shelf_depth_reaches_both_the_groove_and_the_inserted_span(self, joinery, root_depth, expected_depth):
        from adapters.ast_to_removal import ast_to_removal_intents
        from pml.yaml_parser import parse_pml_yaml
        from resolution.layout_resolver import resolve_layout

        source = f"""Sheet: {{width: 1220mm, height: 1220mm, thickness: 18mm, margin: 10mm}}
children:
- Assembly:
    type: carcass
    width: 900mm
    depth: 300mm
    height: 400mm
    thickness: 18mm
    top: none
    bottom: none
    back: none
    fixed_shelves: 1
    shelf_joinery: {joinery}
    shelf_dado_depth: {root_depth}mm
"""
        if expected_depth is None:
            with pytest.raises(ValueError, match="cap groove depth"):
                resolve_layout(parse_pml_yaml(source))
            return
        intents = ast_to_removal_intents(resolve_layout(parse_pml_yaml(source)))
        shelf = next(i for i in intents if "shelf_1" in i.region_id and i.hint_type == "profile")
        assert shelf.bounds.width == 864 + 2 * expected_depth
        grooves = [i for i in intents if i.hint_type == "pocket"]
        assert len(grooves) == 2
        assert all(i.depth_mm() == expected_depth for i in grooves)

    def test_side_panel_dimensions(self):
        assembly = carcass(width=600, length=560, height=720, thickness=18)
        left = assembly.panels["left_side"]
        assert left.width_mm == 560
        assert left.height_mm == 720

    def test_creates_sides_and_caps(self):
        assembly = carcass(width=600, length=400, height=500, thickness=18)
        assert "left_side" in assembly.panels
        assert "right_side" in assembly.panels
        assert "top" in assembly.panels
        assert "bottom" in assembly.panels

    def test_between_sides_cap_dimensions(self):
        assembly = carcass(
            width=600,
            length=400,
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
            length=400,
            height=500,
            thickness=18,
            cap_style="over_sides",
        )
        top = assembly.panels["top"]
        assert top.width_mm == 600

    def test_over_sides_reduces_side_height(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            cap_style="over_sides",
        )
        left = assembly.panels["left_side"]
        assert left.height_mm == 500 - 2 * 18

    def test_default_butt_joinery(self):
        assembly = carcass(width=600, length=400, height=500, thickness=18)
        top_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.TOP]
        assert all(isinstance(i.joinery, Butt) for i in top_interfaces)

    def test_no_top_when_none_string(self):
        assembly = carcass(width=600, length=400, height=500, thickness=18, top="none")
        assert "top" not in assembly.panels

    def test_no_bottom_when_none_string(self):
        assembly = carcass(width=600, length=400, height=500, thickness=18, bottom="none")
        assert "bottom" not in assembly.panels

    def test_fixed_shelves_creates_shelf_panels(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
        )
        assert "shelf_1" in assembly.panels
        assert "shelf_2" in assembly.panels

    def test_shelf_interfaces_are_internal(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
        )
        shelf_interfaces = [i for i in assembly.interfaces if "shelf" in i.panel_a or "shelf" in i.panel_b]
        assert all(i.type == InterfaceType.INTERNAL for i in shelf_interfaces)

    def test_shelf_joinery_default_is_captured(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            fixed_shelves=2,
        )
        shelf_interfaces = [i for i in assembly.interfaces if "shelf" in i.panel_a or "shelf" in i.panel_b]
        assert all(isinstance(i.joinery, Captured) for i in shelf_interfaces)

    def test_perimeter_joinery_sets_top_and_bottom_defaults(self):
        from assembly.joinery import Finger

        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            perimeter_joinery=Finger(width_mm=15),
        )
        top_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.TOP]
        bottom_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.BOTTOM]
        assert all(isinstance(i.joinery, Finger) for i in top_interfaces)
        assert all(isinstance(i.joinery, Finger) for i in bottom_interfaces)

    def test_explicit_top_overrides_perimeter_joinery(self):
        from assembly.joinery import Finger

        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            perimeter_joinery=Finger(width_mm=15),
            top=Butt(),
        )
        top_interfaces = [i for i in assembly.interfaces if i.type == InterfaceType.TOP]
        assert all(isinstance(i.joinery, Butt) for i in top_interfaces)

    def test_back_to_top_bottom_interfaces_emitted(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            back=Captured(),
        )
        back_top_interfaces = [
            i
            for i in assembly.interfaces
            if i.type == InterfaceType.TOP and ("back" in i.panel_a or "back" in i.panel_b)
        ]
        back_bottom_interfaces = [
            i
            for i in assembly.interfaces
            if i.type == InterfaceType.BOTTOM and ("back" in i.panel_a or "back" in i.panel_b)
        ]
        assert len(back_top_interfaces) == 1
        assert len(back_bottom_interfaces) == 1

    def test_toe_kick_creates_notches_on_sides(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
        )
        left = assembly.panels["left_side"]
        right = assembly.panels["right_side"]
        assert len(left.notches) == 1
        assert len(right.notches) == 1
        assert left.notches[0].depth_mm == 100
        assert left.notches[0].u_len_mm == 50

    def test_toe_kick_depth_default(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
        )
        left = assembly.panels["left_side"]
        assert left.notches[0].u_len_mm == 50

    def test_toe_kick_depth_custom(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
            toe_kick_setback=75,
        )
        left = assembly.panels["left_side"]
        assert left.notches[0].u_len_mm == 75

    def test_toe_kick_shortens_bottom_panel(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
            toe_kick_setback=75,
        )
        bottom = assembly.panels["bottom"]
        assert bottom.height_mm == 400 - 75

    def test_toe_kick_cover_created_between_sides(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
            toe_kick_style="between_sides",
            toe_kick_cover=True,
        )
        assert "toe_kick_cover" in assembly.panels
        cover = assembly.panels["toe_kick_cover"]
        assert cover.width_mm == 600 - 2 * 18
        assert cover.height_mm == 100

    def test_toe_kick_cover_created_over_sides(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
            toe_kick_style="over_sides",
            toe_kick_cover=True,
        )
        cover = assembly.panels["toe_kick_cover"]
        assert cover.width_mm == 600

    def test_toe_kick_cover_not_created_when_disabled(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            toe_kick_height=100,
            toe_kick_cover=False,
        )
        assert "toe_kick_cover" not in assembly.panels

    def test_back_panel_created_when_specified(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            back=Captured(),
            back_thickness=6,
        )
        assert "back" in assembly.panels
        assert assembly.panels["back"].thickness_mm == 6

    def test_back_spans_include_grooves_independently_of_rear_setback(self):
        assembly = carcass(
            width=600,
            length=400,
            height=500,
            thickness=18,
            back=Captured(),
            back_thickness=6,
            back_inset=18,
        )
        back = assembly.panels["back"]
        assert back.width_mm == 600 - 2 * 18 + 2 * 3
        assert back.height_mm == 500 - 2 * 18 + 2 * 3


class TestCarcassResolve:
    def test_full_carcass_panel_generation(self):
        assembly = carcass(
            width=600,
            length=560,
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

    def test_shelf_joinery_creates_dados_in_sides(self):
        assembly = carcass(
            width=600,
            length=400,
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
            length=300,
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
            length=300,
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
            length=300,
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
            length=300,
            height=600,
            thickness=18,
            rows=2,
            cols=3,
            perimeter_joinery=Finger(width_mm=15),
        )
        perimeter_interfaces = [i for i in assembly.interfaces if i.type in (InterfaceType.TOP, InterfaceType.BOTTOM)]
        assert len(perimeter_interfaces) == 4
        assert all(isinstance(i.joinery, Finger) for i in perimeter_interfaces)

    def test_internal_half_lap_interfaces_use_internal_joinery(self):
        assembly = cubby(
            width=900,
            length=300,
            height=600,
            thickness=18,
            rows=2,
            cols=2,
            internal_joinery=HalfLap(),
        )
        half_lap_interfaces = [
            i for i in assembly.interfaces if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == 1

    def test_shelf_partition_grid_intersections(self):
        assembly = cubby(
            width=900,
            length=300,
            height=600,
            thickness=18,
            rows=3,
            cols=3,
        )
        half_lap_interfaces = [
            i for i in assembly.interfaces if i.type == InterfaceType.INTERNAL and isinstance(i.joinery, HalfLap)
        ]
        assert len(half_lap_interfaces) == (3 - 1) * (3 - 1)

    def test_single_row_no_shelves(self):
        assembly = cubby(
            width=900,
            length=300,
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
            length=300,
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
            length=300,
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
            length=300,
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


class TestDadoSpecValidation:
    def test_valid_construction(self):
        from assembly.panel import DadoSpec

        DadoSpec(position_from_edge_mm=0, width_mm=6, depth_mm=3, edge="bottom")
        DadoSpec(position_from_edge_mm=25, width_mm=12, depth_mm=6, edge="top", orientation="vertical")

    def test_negative_position(self):
        from assembly.panel import DadoSpec

        try:
            DadoSpec(position_from_edge_mm=-1, width_mm=6, depth_mm=3, edge="bottom")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "position_from_edge_mm" in str(e)

    def test_non_positive_width(self):
        from assembly.panel import DadoSpec

        try:
            DadoSpec(position_from_edge_mm=10, width_mm=0, depth_mm=3, edge="bottom")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "width_mm must be positive" in str(e)

    def test_non_positive_depth(self):
        from assembly.panel import DadoSpec

        try:
            DadoSpec(position_from_edge_mm=10, width_mm=6, depth_mm=-1, edge="bottom")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "depth_mm must be positive" in str(e)

    def test_invalid_edge(self):
        from assembly.panel import DadoSpec

        try:
            DadoSpec(position_from_edge_mm=10, width_mm=6, depth_mm=3, edge="front")  # type: ignore[arg-type]
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "edge" in str(e).lower()

    def test_invalid_orientation(self):
        from assembly.panel import DadoSpec

        try:
            DadoSpec(position_from_edge_mm=10, width_mm=6, depth_mm=3, edge="bottom", orientation="diagonal")  # type: ignore[arg-type]
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "orientation" in str(e).lower()
