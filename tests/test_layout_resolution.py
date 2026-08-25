from __future__ import annotations

import pytest

from layout_ast.compositional import (
    BeamDecl,
    BeamFeatureDecl,
    BeamLayerDecl,
    Cell,
    ComponentDef,
    CompositionalLayoutAST,
    Frame,
    Grid,
    Inset,
    Panel,
    Place,
    PocketGen,
    ProfileGen,
    Rect,
    RoundedRect,
    UseComponent,
)
from layout_ast.layout import Feature, Geometry, Item, Placement, Sheet, mirror_item_about_x
from pml import format_pml
from resolution.layout_resolver import ResolutionAssertionError, resolve_layout


def approx_eq(a, b, rel=1e-6):
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_simple_panel_with_rect():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                    id="outer",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Rect"
    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.placement is not None
    assert item.placement.center_xy_mm == (200.0, 300.0)
    assert item.feature is not None
    assert item.feature.type == "profile"


def test_panel_with_inset():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Inset(
                    amount_mm=25,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth_mm=6.0),
                            id="panel",
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.geometry is not None
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0

    assert item.placement is not None
    assert item.placement.center_xy_mm == (200.0, 300.0)


def test_frame_insets_region_for_children():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth_mm=6.0),
                                    id="inner",
                                ),
                            ),
                        ),
                    ),
                    feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                    id="outer",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry is not None
    assert outer.geometry.data["w_mm"] == 400.0
    assert outer.geometry.data["h_mm"] == 600.0
    assert outer.feature is not None
    assert outer.feature.type == "profile"

    inner = flat.items[1]
    assert inner.shape_id == "inner"
    assert inner.feature is not None
    assert inner.feature.type == "pocket"
    assert inner.geometry is not None
    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0


def test_frame_does_not_emit_profile():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth_mm=6.0),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 0, f"Frame should not emit profile, but found {len(profile_items)}"

    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1
    assert pocket_items[0].geometry is not None
    assert pocket_items[0].geometry.data["w_mm"] == 300.0
    assert pocket_items[0].geometry.data["h_mm"] == 500.0


def test_grid_subdivides_region():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=10,
                    children=(
                        Cell(
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth_mm=5.0),
                                    id="cell_pocket",
                                ),
                            )
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 4

    for item in flat.items:
        assert item.feature is not None
        assert item.feature.type == "pocket"
        assert item.geometry is not None
        assert approx_eq(item.geometry.data["w_mm"], 195.0)
        assert approx_eq(item.geometry.data["h_mm"], 195.0)


def test_component_definition_and_use():
    simple_panel = ComponentDef(
        name="SimplePanel",
        params={"recess_depth": 6.0},
        body=Rect(
            feature=Feature(type="pocket", depth_mm=6.0),
            id="panel",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        components={"SimplePanel": simple_panel},
        root=Panel(
            children=(
                UseComponent(
                    component_name="SimplePanel",
                    args={"recess_depth": 8.0},
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.shape_id == "panel"


def test_place_grid_with_components():
    shaker_panel = ComponentDef(
        name="ShakerPanel",
        params={"frame_width": 50.0, "recess_depth": 6.0},
        body=Rect(
            children=(
                Frame(
                    width_mm=50,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth_mm=6.0),
                            id="inner",
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
            id="outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=0.0),
        components={"ShakerPanel": shaker_panel},
        root=Place(
            layout=Grid(rows=2, cols=2, gap_mm=50),
            children=(
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
            ),
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 8

    first_outer = flat.items[0]
    assert first_outer.shape_id == "outer"
    assert first_outer.geometry is not None
    assert approx_eq(first_outer.geometry.data["w_mm"], 475.0)
    assert approx_eq(first_outer.geometry.data["h_mm"], 475.0)


def test_acceptance_4_instances_frame_grid_pocket():
    grid_panel = ComponentDef(
        name="GridPanel",
        params={},
        body=Rect(
            children=(
                Frame(
                    width_mm=40,
                    children=(
                        Grid(
                            rows=2,
                            cols=2,
                            gap_mm=10,
                            children=(
                                Cell(
                                    children=(
                                        Rect(
                                            feature=Feature(type="pocket", depth_mm=5.0),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
            id="panel_outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1200, height_mm=1200, thickness_mm=19, margin_mm=0.0),
        components={"GridPanel": grid_panel},
        root=Place(
            layout=Grid(rows=2, cols=2, gap_mm=100),
            children=(
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
            ),
        ),
        project="acceptance_test_grid_panels",
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 20

    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"

    pml_output = format_pml(flat)
    assert "width: 1200mm" in pml_output
    assert "project: acceptance_test_grid_panels" in pml_output
    assert "type: profile" in pml_output
    assert "type: pocket" in pml_output

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 4

    assert len(pocket_items) == 16


def test_grid_with_no_explicit_cell():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=0,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth_mm=5.0),
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 4


def test_rounded_rect_profile_inherits_geometry():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                RoundedRect(
                    radius_mm=25.0,
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.shape_id == "panel"
    assert shape_item.type == "RoundedRect"
    assert shape_item.geometry is not None
    assert shape_item.geometry.data["radius_mm"] == 25.0

    profile_item = flat.items[1]
    assert profile_item.type == "Polygon"
    assert profile_item.feature is not None
    assert profile_item.feature.type == "profile"
    assert profile_item.geometry is not None
    assert "points" in profile_item.geometry.data
    assert len(profile_item.geometry.data["points"]) > 4


def test_rounded_rect_selective_corners_profile_inherits():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                RoundedRect(
                    radius_mm=25.4,
                    corners=frozenset({"bl", "br"}),
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.type == "RoundedRect"
    assert shape_item.geometry is not None
    assert shape_item.geometry.data["radius_tl_mm"] == 0.0
    assert shape_item.geometry.data["radius_tr_mm"] == 0.0
    assert shape_item.geometry.data["radius_bl_mm"] == 25.4
    assert shape_item.geometry.data["radius_br_mm"] == 25.4

    profile_item = flat.items[1]
    assert profile_item.type == "Polygon"
    assert profile_item.feature is not None
    assert profile_item.feature.type == "profile"
    assert profile_item.geometry is not None
    assert "points" in profile_item.geometry.data
    points = profile_item.geometry.data["points"]
    assert len(points) > 4


def test_rect_profile_uses_domain():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.shape_id == "panel"
    assert shape_item.type == "Rect"

    profile_item = flat.items[1]
    assert profile_item.type == "Polygon"
    assert profile_item.feature is not None
    assert profile_item.feature.type == "profile"
    assert profile_item.geometry is not None
    assert "points" in profile_item.geometry.data
    assert len(profile_item.geometry.data["points"]) == 4


def test_validation_mode_passes_for_correct_resolution():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                RoundedRect(
                    radius_mm=25.0,
                    corners=frozenset({"bl", "br"}),
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast, validate=True)

    assert len(flat.items) == 2
    assert flat.items[1].type == "Polygon"


def _mirrored_geometry(item: Item, working_height_mm: float) -> dict:
    mirrored = mirror_item_about_x(item, working_height_mm)
    assert mirrored.geometry is not None
    return mirrored.geometry.data


def _mirrored_center(item: Item, working_height_mm: float) -> tuple[float, float]:
    mirrored = mirror_item_about_x(item, working_height_mm)
    assert mirrored.placement is not None
    return mirrored.placement.center_xy_mm


class TestMirrorItemAboutX:
    def _item(self, geometry: dict, center=(100.0, 150.0), feature=None) -> Item:
        return Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data=geometry),
            placement=Placement(center_xy_mm=center),
            feature=feature or Feature(type="pocket", depth_mm=6.0, face="back"),
            shape_id="target",
        )

    def test_mirror_polygon_reverses_winding_and_negates_y(self) -> None:
        item = self._item({"points": [[0.0, 0.0], [40.0, 0.0], [40.0, 10.0], [10.0, 10.0], [10.0, 30.0], [0.0, 30.0]]})

        assert _mirrored_center(item, 600.0) == (100.0, 450.0)
        assert _mirrored_geometry(item, 600.0)["points"] == [
            [0.0, -30.0],
            [10.0, -30.0],
            [10.0, -10.0],
            [40.0, -10.0],
            [40.0, 0.0],
            [0.0, 0.0],
        ]

    def test_mirror_rounded_rect_swaps_vertical_radii(self) -> None:
        item = self._item(
            {
                "w_mm": 80.0,
                "h_mm": 40.0,
                "radius_tl_mm": 1.0,
                "radius_tr_mm": 2.0,
                "radius_br_mm": 3.0,
                "radius_bl_mm": 4.0,
            }
        )

        data = _mirrored_geometry(item, 600.0)

        assert data["radius_bl_mm"] == 1.0
        assert data["radius_br_mm"] == 2.0
        assert data["radius_tr_mm"] == 3.0
        assert data["radius_tl_mm"] == 4.0
        assert data["w_mm"] == 80.0
        assert data["h_mm"] == 40.0

    def test_mirror_uniform_corner_radius_unchanged(self) -> None:
        item = self._item({"w_mm": 80.0, "h_mm": 40.0, "radius_mm": 5.0, "corner_radius_mm": 5.0})

        data = _mirrored_geometry(item, 600.0)

        assert data["radius_mm"] == 5.0
        assert data["corner_radius_mm"] == 5.0

    def test_mirror_edge_treatment_unchanged(self) -> None:
        treatment = {"type": "roundover", "radius_mm": 3.0, "finish_allowance_mm": 0.2}
        item = self._item({"w_mm": 80.0, "h_mm": 40.0, "edge_treatment": treatment})

        assert _mirrored_geometry(item, 600.0)["edge_treatment"] == treatment

    def test_mirror_circle_moves_center_only(self) -> None:
        item = self._item({"diameter_mm": 35.0}, center=(80.0, 120.0))

        assert _mirrored_center(item, 640.0) == (80.0, 520.0)
        assert _mirrored_geometry(item, 640.0) == {"diameter_mm": 35.0}

    def test_mirror_polygon_holes_reverse_winding(self) -> None:
        item = self._item(
            {
                "points": [[0.0, 0.0], [40.0, 0.0], [40.0, 40.0], [0.0, 40.0]],
                "holes": [[[10.0, 10.0], [20.0, 10.0], [20.0, 25.0]]],
            }
        )

        holes = _mirrored_geometry(item, 600.0)["holes"]

        assert holes == [[[20.0, -25.0], [20.0, -10.0], [10.0, -10.0]]]

    def test_mirror_line_endpoints_negate_y(self) -> None:
        item = self._item({"start": [-20.0, -5.0], "end": [20.0, 15.0]})

        data = _mirrored_geometry(item, 600.0)

        assert data["start"] == [-20.0, 5.0]
        assert data["end"] == [20.0, -15.0]

    def test_mirror_islands_absolute_bounds(self) -> None:
        item = self._item(
            {
                "w_mm": 200.0,
                "h_mm": 100.0,
                "islands": [{"x_min": 10.0, "x_max": 30.0, "y_min": 100.0, "y_max": 140.0}],
            }
        )

        islands = _mirrored_geometry(item, 600.0)["islands"]

        assert islands == [{"x_min": 10.0, "x_max": 30.0, "y_min": 460.0, "y_max": 500.0}]

    def test_mirror_spline_polyline_metadata_unchanged(self) -> None:
        item = self._item(
            {
                "points": [[0.0, 0.0], [10.0, 20.0], [30.0, 5.0]],
                "spline_source": True,
                "spline_tolerance_mm": 0.1,
                "is_open": True,
                "width_mm": 3.0,
            }
        )

        data = _mirrored_geometry(item, 600.0)

        assert data["spline_source"] is True
        assert data["spline_tolerance_mm"] == 0.1
        assert data["is_open"] is True
        assert data["width_mm"] == 3.0
        assert data["points"] == [[30.0, -5.0], [10.0, -20.0], [0.0, 0.0]]

    def test_mirror_unknown_geometry_key_raises(self) -> None:
        item = self._item({"w_mm": 80.0, "h_mm": 40.0, "image_path": "heights.png"})

        with pytest.raises(ValueError, match="unrecognized geometry key 'image_path'"):
            mirror_item_about_x(item, 600.0)

    def test_mirror_raises_on_absolute_dogbone_fields(self) -> None:
        feature = Feature(type="pocket", depth_mm=6.0, face="back", dogbone_corners=((10.0, 20.0),))
        item = self._item({"w_mm": 80.0, "h_mm": 40.0}, feature=feature)

        with pytest.raises(ValueError, match="dogbone_corners"):
            mirror_item_about_x(item, 600.0)

    def test_mirror_raises_on_dogbone_reference_point(self) -> None:
        feature = Feature(type="pocket", depth_mm=6.0, face="back", dogbone_reference_point=(10.0, 20.0))
        item = self._item({"w_mm": 80.0, "h_mm": 40.0}, feature=feature)

        with pytest.raises(ValueError, match="dogbone_reference_point"):
            mirror_item_about_x(item, 600.0)


def test_pocket_gen_face_threaded_to_generated_item():
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(children=(Rect(children=(PocketGen(depth_mm=6.0, face="back"),), id="panel"),)),
    )

    flat = resolve_layout(ast)

    pockets = [i for i in flat.items if i.feature and i.feature.type == "pocket"]
    assert len(pockets) == 1
    feature = pockets[0].feature
    assert feature is not None
    assert feature.face == "back"


def _beam_ast(beam: BeamDecl, sheet: Sheet | None = None) -> CompositionalLayoutAST:
    return CompositionalLayoutAST(
        sheet=sheet or Sheet(width_mm=800, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(children=(beam,)),
    )


def _geometry_of(item: Item) -> dict:
    assert item.geometry is not None
    return item.geometry.data


def _feature_of(item: Item) -> Feature:
    assert item.feature is not None
    return item.feature


def _center_of(item: Item) -> tuple[float, float]:
    assert item.placement is not None
    return item.placement.center_xy_mm


def _beam_removals(flat, feature_type: str) -> list[Item]:
    return [i for i in flat.items if i.feature and _feature_of(i).type == feature_type]


def test_beam_mortise_emits_pocket_on_reached_layer():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        face_features=(
            BeamFeatureDecl(
                feature_type="SquareMortise",
                params={"x_mm": 250, "y_mm": 38, "width_mm": 38, "height_mm": 50, "depth_mm": 19},
            ),
        ),
    )

    flat = resolve_layout(_beam_ast(beam))

    pockets = _beam_removals(flat, "pocket")
    assert len(pockets) == 1
    assert _geometry_of(pockets[0]) == {"w_mm": 38.0, "h_mm": 50.0}
    assert _feature_of(pockets[0]).is_through is True
    assert _center_of(pockets[0]) == (256.35, 44.35)


def test_beam_face_back_targets_last_layer():
    params = {"x_mm": 250, "y_mm": 38, "width_mm": 38, "height_mm": 50, "depth_mm": 19}
    front = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        face_features=(BeamFeatureDecl(feature_type="SquareMortise", params=params),),
    )
    back = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        face_features=(BeamFeatureDecl(feature_type="SquareMortise", params={**params, "face": "back"}),),
    )

    front_pocket = _beam_removals(resolve_layout(_beam_ast(front)), "pocket")[0]
    back_pocket = _beam_removals(resolve_layout(_beam_ast(back)), "pocket")[0]

    panel_pitch = 76.0 + 10.0
    assert _center_of(back_pocket)[0] == _center_of(front_pocket)[0]
    assert _center_of(back_pocket)[1] - _center_of(front_pocket)[1] == 2 * panel_pitch


def test_beam_partial_depth_splits_across_two_layers():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        face_features=(
            BeamFeatureDecl(
                feature_type="SquareMortise",
                params={"x_mm": 250, "y_mm": 38, "width_mm": 38, "height_mm": 50, "depth_mm": 30},
            ),
        ),
    )

    pockets = _beam_removals(resolve_layout(_beam_ast(beam)), "pocket")

    assert len(pockets) == 2
    assert _feature_of(pockets[0]).is_through is True
    assert _feature_of(pockets[1]).is_through is False
    assert _feature_of(pockets[1]).depth_mm == 11.0


def test_beam_mortise_position_ignores_tenon_extension():
    beam = BeamDecl(
        name="rail",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        end_features=(
            BeamFeatureDecl(
                feature_type="Tenon",
                params={"end": "left", "extension_mm": 38, "width_mm": 76, "height_mm": 19, "layers": "center"},
            ),
        ),
        face_features=(BeamFeatureDecl(feature_type="DrillHole", params={"x_mm": 250, "y_mm": 38, "diameter_mm": 10}),),
    )

    holes = _beam_removals(resolve_layout(_beam_ast(beam)), "hole")

    assert len(holes) == 3
    x_positions = [_center_of(h)[0] for h in holes]
    assert x_positions[0] == x_positions[2]
    assert x_positions[1] - x_positions[0] == 38.0


def test_beam_edge_dado_all_layers():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        edge_features=(
            BeamFeatureDecl(
                feature_type="EdgeDado",
                params={"edge": "top", "position_mm": 250, "width_mm": 19, "depth_mm": 9.5, "layers": "all"},
            ),
        ),
    )

    pockets = _beam_removals(resolve_layout(_beam_ast(beam)), "pocket")

    assert len(pockets) == 3
    assert all(_geometry_of(p) == {"w_mm": 19.0, "h_mm": 9.5} for p in pockets)
    assert all(_feature_of(p).is_through for p in pockets)
    assert _center_of(pockets[0]) == (265.85, 77.6)


def test_beam_rabbet_outer_layers_only():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        edge_features=(
            BeamFeatureDecl(
                feature_type="Rabbet",
                params={"edge": "bottom", "width_mm": 12, "depth_mm": 6},
            ),
        ),
    )

    pockets = _beam_removals(resolve_layout(_beam_ast(beam)), "pocket")

    assert len(pockets) == 2
    assert all(_feature_of(p).depth_mm == 6.0 and not _feature_of(p).is_through for p in pockets)
    panel_pitch = 76.0 + 10.0
    y_positions = [_center_of(p)[1] for p in pockets]
    assert y_positions[1] - y_positions[0] == 2 * panel_pitch


def test_beam_layer_cutout_emits_through_pocket():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=(
            BeamLayerDecl(length_mm=500),
            BeamLayerDecl(
                length_mm=500,
                cutouts=({"start_mm": 100, "length_mm": 60, "width_mm": 40, "offset_from_edge_mm": 18},),
            ),
            BeamLayerDecl(length_mm=500),
        ),
    )

    pockets = _beam_removals(resolve_layout(_beam_ast(beam)), "pocket")

    assert len(pockets) == 1
    assert _geometry_of(pockets[0]) == {"w_mm": 60.0, "h_mm": 40.0}
    assert _feature_of(pockets[0]).is_through is True
    assert _center_of(pockets[0]) == (136.35, 130.35)


def test_beam_explicit_layer_offset_shifts_feature_origin():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=(
            BeamLayerDecl(length_mm=500),
            BeamLayerDecl(length_mm=460, offset_mm=40),
        ),
        face_features=(BeamFeatureDecl(feature_type="DrillHole", params={"x_mm": 250, "y_mm": 38, "diameter_mm": 10}),),
    )

    holes = _beam_removals(resolve_layout(_beam_ast(beam)), "hole")

    assert len(holes) == 2
    assert _center_of(holes[0])[0] - _center_of(holes[1])[0] == pytest.approx(40.0)


def test_spliced_beam_with_face_feature_raises():
    beam = BeamDecl(
        name="rail",
        length_mm=2000,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        face_features=(BeamFeatureDecl(feature_type="DrillHole", params={"x_mm": 250, "y_mm": 38, "diameter_mm": 10}),),
    )

    with pytest.raises(ResolutionAssertionError, match="splices across sheets"):
        resolve_layout(_beam_ast(beam))


def test_spliced_beam_with_tenon_still_resolves():
    beam = BeamDecl(
        name="rail",
        length_mm=2000,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        end_features=(
            BeamFeatureDecl(
                feature_type="Tenon",
                params={"end": "left", "extension_mm": 38, "width_mm": 76, "height_mm": 19, "layers": "center"},
            ),
        ),
    )

    flat = resolve_layout(_beam_ast(beam))

    assert len(flat.items) > 3
    assert all(_feature_of(i).type == "profile" for i in flat.items)


def test_beam_edge_notch_emits_through_pocket():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        edge_features=(
            BeamFeatureDecl(
                feature_type="EdgeNotch",
                params={"edge": "bottom", "position_mm": 100, "width_mm": 25, "depth_mm": 20, "layers": "outer"},
            ),
        ),
    )

    pockets = _beam_removals(resolve_layout(_beam_ast(beam)), "pocket")

    assert len(pockets) == 2
    assert all(_geometry_of(p) == {"w_mm": 25.0, "h_mm": 20.0} for p in pockets)
    assert all(_feature_of(p).is_through for p in pockets)
    assert _center_of(pockets[0]) == (118.85, 16.35)


def test_beam_feature_items_are_machined_from_the_front():
    beam = BeamDecl(
        name="post",
        length_mm=500,
        width_mm=76,
        thickness_mm=19,
        layers=3,
        face_features=(
            BeamFeatureDecl(
                feature_type="SquareMortise",
                params={
                    "x_mm": 250,
                    "y_mm": 38,
                    "width_mm": 38,
                    "height_mm": 50,
                    "depth_mm": 19,
                    "face": "back",
                },
            ),
        ),
        edge_features=(
            BeamFeatureDecl(feature_type="Rabbet", params={"edge": "bottom", "width_mm": 12, "depth_mm": 6}),
        ),
    )

    flat = resolve_layout(_beam_ast(beam))

    assert all(_feature_of(i).face == "front" for i in flat.items)


def test_beam_thickness_must_match_sheet_thickness():
    beam = BeamDecl(name="post", length_mm=500, width_mm=76, thickness_mm=12, layers=3)

    with pytest.raises(ResolutionAssertionError, match="does not match sheet thickness"):
        resolve_layout(_beam_ast(beam))
