from __future__ import annotations

from dataclasses import replace

import pytest

from adapters.layoutast_to_ir import (
    FEATURE_HANDLERS,
    FEATURE_LAYER,
    layoutast_to_diagram_ir,
)
from diagram_ir import Circle, DiagramIR, Path, Polyline, Rect, Text
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet


def _make_sheet(w: float = 200.0, h: float = 150.0, t: float = 12.0, m: float = 0.0) -> Sheet:
    return Sheet(width_mm=w, height_mm=h, thickness_mm=t, margin_mm=m)


@pytest.mark.parametrize("y_origin", ["back", "front"])
@pytest.mark.parametrize("margin", [0, 10])
@pytest.mark.parametrize("shape", ["Rect", "Polygon"])
def test_pocket_label_avoids_preserved_island(shape, margin, y_origin):
    geometry = (
        {"w_mm": 100, "h_mm": 80, "islands": [{"x_min": 80, "x_max": 120, "y_min": 60, "y_max": 100}]}
        if shape == "Rect"
        else {
            "points": [(-50, -40), (50, -40), (50, 40), (-50, 40)],
            "holes": [[(-20, -20), (20, -20), (20, 20), (-20, 20)]],
        }
    )
    item = Item(
        kind="shape",
        type=shape,
        geometry=Geometry(data=geometry),
        placement=Placement(center_xy_mm=(100, 80)),
        feature=Feature(type="pocket", depth_mm=6),
        label="Recess",
        shape_id="recess",
    )
    sheet = _make_sheet(w=240, h=200, m=margin)
    ir = layoutast_to_diagram_ir(LayoutAST(sheet=sheet, items=(item,)), y_origin=y_origin)
    layer = next(layer for layer in ir.layers if layer.name == "LABELS")
    (label,) = layer.items
    assert isinstance(label, Text) and label.content == "Recess"
    x = label.x - margin
    y = sheet.working_height_mm - (label.y - margin) if y_origin == "back" else label.y - margin
    assert 50 < x < 150 and 40 < y < 120
    assert not (80 <= x <= 120 and 60 <= y <= 100)


def _make_profile_item(shape_id: str, w: float, h: float, cx: float, cy: float) -> Item:
    return Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": w, "h_mm": h}),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
        shape_id=shape_id,
    )


def _make_pocket_item(shape_id: str, w: float, h: float, cx: float, cy: float, depth: float = 5.0) -> Item:
    return Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": w, "h_mm": h}),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(type="pocket", depth_mm=depth),
        shape_id=shape_id,
    )


def _make_hole_item(shape_id: str, diameter: float, cx: float, cy: float) -> Item:
    return Item(
        kind="shape",
        type="Circle",
        geometry=Geometry(data={"diameter_mm": diameter}),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(type="hole", depth_mm=0.0, is_through=True),
        shape_id=shape_id,
    )


def test_feature_handlers_registered():
    assert "profile" in FEATURE_HANDLERS
    assert "pocket" in FEATURE_HANDLERS
    assert "hole" in FEATURE_HANDLERS
    assert "engrave" in FEATURE_HANDLERS
    assert "notch" in FEATURE_HANDLERS


def test_keepout_has_own_layer_and_label():
    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
children:
- Keepout:
    id: clamp_left
    children:
    - Rect: {at: {x: 30mm, y: 40mm, width: 20mm, height: 30mm}}
"""
    ir = layoutast_to_diagram_ir(resolve_layout(parse_pml_yaml(pml)))

    layers = {layer.name: layer for layer in ir.layers}
    assert "KEEPOUT_ZONES" in layers
    assert len(layers["KEEPOUT_ZONES"].items) == 1
    assert layers["KEEPOUT_ZONES"].items[0].style_token == "keepout"
    assert any(isinstance(item, Text) and item.content == "clamp_left" for item in layers["LABELS"].items)
    assert "POCKET_REGIONS" not in layers


def test_keepout_outside_sheet_can_be_drawn_without_relaxing_cut_bounds():
    from dataclasses import replace

    item = _make_profile_item("fixture", 20, 20, 300, 300)
    item = replace(item, kind="keepout", feature=None, label="fixture")
    ir = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(), items=(item,)))

    assert ir.bounds.x_max >= 310
    assert ir.bounds.y_min <= -160
    assert any(layer.name == "KEEPOUT_ZONES" for layer in ir.layers)


def test_feature_layer_covers_shape_producing_handlers():
    shape_producing = {ft for ft in FEATURE_HANDLERS if ft != "surface"}
    assert shape_producing == set(FEATURE_LAYER.keys())


def test_no_empty_layer_when_handler_returns_empty():
    item = Item(
        kind="shape",
        type="Rect",
        geometry=None,
        placement=None,
        feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
        shape_id="no_geom",
    )
    ast = LayoutAST(sheet=_make_sheet(), items=(item,))
    ir = layoutast_to_diagram_ir(ast)
    layer_names = {layer.name for layer in ir.layers}
    assert "PROFILE_CUTS" not in layer_names


def test_basic_diagram_ir_structure():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
    )

    ir = layoutast_to_diagram_ir(ast)

    assert isinstance(ir, DiagramIR)
    assert ir.bounds is not None
    assert len(ir.layers) >= 1


def test_sheet_outline_layer():
    ast = LayoutAST(sheet=_make_sheet(), items=())

    ir = layoutast_to_diagram_ir(ast)

    sheet_layer = next((layer for layer in ir.layers if layer.name == "SHEET_OUTLINE"), None)
    assert sheet_layer is not None
    assert len(sheet_layer.items) >= 1
    assert any(isinstance(s, Rect) for s in sheet_layer.items)


def test_profile_layer():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
    )

    ir = layoutast_to_diagram_ir(ast)

    profile_layer = next((layer for layer in ir.layers if layer.name == "PROFILE_CUTS"), None)
    assert profile_layer is not None
    assert len(profile_layer.items) >= 1

    rect_shapes = [s for s in profile_layer.items if isinstance(s, Rect)]
    assert len(rect_shapes) == 1
    assert rect_shapes[0].style_token == "profile"


def test_pocket_layer():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_pocket_item("pocket1", 60.0, 40.0, 100.0, 75.0),),
    )

    ir = layoutast_to_diagram_ir(ast)

    pocket_layer = next((layer for layer in ir.layers if layer.name == "POCKET_REGIONS"), None)
    assert pocket_layer is not None
    assert len(pocket_layer.items) >= 1

    rect_shapes = [s for s in pocket_layer.items if isinstance(s, Rect)]
    assert len(rect_shapes) == 1
    assert rect_shapes[0].style_token == "pocket"


@pytest.mark.parametrize("origin", ["front", "back"])
def test_polygon_pocket_preserves_local_holes_and_margin(origin):
    item = Item(
        kind="shape",
        type="Polygon",
        shape_id="ring",
        geometry=Geometry(
            data={
                "points": [(-40, -25), (40, -25), (40, 25), (-40, 25)],
                "holes": [[(-20, -10), (5, -10), (5, 10), (-20, 10)], [(15, -5), (25, -5), (25, 5), (15, 5)]],
            }
        ),
        placement=Placement(center_xy_mm=(70, 50)),
        feature=Feature(type="pocket", depth_mm=5),
    )
    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(220, 180, m=10), items=(item,)), y_origin=origin)
    (path,) = next(layer.items for layer in diagram.layers if layer.name == "POCKET_REGIONS")

    assert isinstance(path, Path)
    assert path.fill_rule == "evenodd" and path.id == "ring" and path.style_token == "pocket"
    assert path.d.count("M ") == path.d.count("Z") == 3
    assert ("40.000 35.000" if origin == "front" else "40.000 145.000") in path.d
    assert ("60.000 50.000" if origin == "front" else "60.000 130.000") in path.d


def test_rect_pocket_islands_use_absolute_bounds_and_union():
    item = _make_pocket_item("island_pocket", 100, 60, 80, 70)
    item = replace(
        item,
        geometry=Geometry(
            data={
                "w_mm": 100,
                "h_mm": 60,
                "islands": [
                    {"x_min": 60, "x_max": 80, "y_min": 60, "y_max": 80},
                    {"x_min": 70, "x_max": 90, "y_min": 60, "y_max": 80},
                ],
            }
        ),
    )
    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(220, 180, m=10), items=(item,)))
    (path,) = next(layer.items for layer in diagram.layers if layer.name == "POCKET_REGIONS")

    assert isinstance(path, Path) and path.fill_rule == "evenodd"
    assert path.d.count("M ") == path.d.count("Z") == 2
    assert "70.000 90.000" in path.d and "100.000 110.000" in path.d


@pytest.mark.parametrize("covered", [False, True])
def test_edge_touching_islands_split_or_empty_the_pocket(covered):
    item = _make_pocket_item("split", 100, 60, 80, 70)
    island = {"x_min": 20 if covered else 70, "x_max": 140 if covered else 90, "y_min": 30, "y_max": 110}
    item = replace(item, geometry=Geometry(data={"w_mm": 100, "h_mm": 60, "islands": [island]}))

    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(220, 180), items=(item,)))

    pockets = [shape for layer in diagram.layers if layer.name == "POCKET_REGIONS" for shape in layer.items]
    if covered:
        assert not pockets
    else:
        (path,) = pockets
        assert isinstance(path, Path) and path.d.count("M ") == path.d.count("Z") == 2


@pytest.mark.parametrize("origin,top", [("front", 40), ("back", 110)])
def test_plain_rect_pocket_uses_same_sheet_coordinates_as_holed_pocket(origin, top):
    item = _make_pocket_item("plain", 50, 30, 65, 45)
    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(220, 180, m=10), items=(item,)), y_origin=origin)
    (rect,) = next(layer.items for layer in diagram.layers if layer.name == "POCKET_REGIONS")

    assert isinstance(rect, Rect)
    assert rect.x == 50 and rect.y == top


def test_hole_layer():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_hole_item("hole1", 10.0, 100.0, 75.0),),
    )

    ir = layoutast_to_diagram_ir(ast)

    hole_layer = next((layer for layer in ir.layers if layer.name == "HOLES"), None)
    assert hole_layer is not None
    assert len(hole_layer.items) >= 1

    circle_shapes = [s for s in hole_layer.items if isinstance(s, Circle)]
    assert len(circle_shapes) >= 1


def test_label_layer():
    item = _make_profile_item("labeled_rect", 100.0, 80.0, 100.0, 75.0)
    item = Item(
        kind=item.kind,
        type=item.type,
        geometry=item.geometry,
        placement=item.placement,
        feature=item.feature,
        shape_id=item.shape_id,
        label="TEST LABEL",
    )

    ast = LayoutAST(sheet=_make_sheet(), items=(item,))
    ir = layoutast_to_diagram_ir(ast)

    label_layer = next((layer for layer in ir.layers if layer.name == "LABELS"), None)
    assert label_layer is not None
    assert len(label_layer.items) >= 1

    text_shapes = [s for s in label_layer.items if isinstance(s, Text)]
    assert len(text_shapes) == 1
    assert text_shapes[0].content == "TEST LABEL"


def test_y_origin_back():
    ast = LayoutAST(
        sheet=_make_sheet(200.0, 200.0),
        items=(_make_profile_item("rect1", 60.0, 60.0, 100.0, 100.0),),
    )

    ir_back = layoutast_to_diagram_ir(ast, y_origin="back")

    profile_layer = next((layer for layer in ir_back.layers if layer.name == "PROFILE_CUTS"), None)
    assert profile_layer is not None

    rect = next(s for s in profile_layer.items if isinstance(s, Rect))
    assert rect.y == 70.0


def test_margin_zones():
    ast = LayoutAST(sheet=_make_sheet(200.0, 150.0, 12.0, 10.0), items=())

    ir = layoutast_to_diagram_ir(ast)

    sheet_layer = next((layer for layer in ir.layers if layer.name == "SHEET_OUTLINE"), None)
    assert sheet_layer is not None

    margin_shapes = [s for s in sheet_layer.items if isinstance(s, Rect) and s.style_token == "margin-zone"]
    assert len(margin_shapes) == 4


def test_dimensions_present():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
    )

    ir = layoutast_to_diagram_ir(ast, show_dimensions=True)

    assert len(ir.dims) > 0


def test_dimensions_disabled():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
    )

    ir = layoutast_to_diagram_ir(ast, show_dimensions=False)

    assert len(ir.dims) == 0


def test_metadata():
    ast = LayoutAST(sheet=_make_sheet(250.0, 180.0, 19.0), items=())

    ir = layoutast_to_diagram_ir(ast, y_origin="back")

    assert ir.metadata["sheet_width"] == "250.0"
    assert ir.metadata["sheet_height"] == "180.0"
    assert ir.metadata["sheet_thickness"] == "19.0"
    assert ir.metadata["y_origin"] == "back"


def test_waste_shapes_separated():
    waste_item = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 50.0, "h_mm": 30.0}),
        placement=Placement(center_xy_mm=(150.0, 100.0)),
        feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
        shape_id="waste_cut_1",
    )

    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(
            _make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),
            waste_item,
        ),
    )

    ir = layoutast_to_diagram_ir(ast)

    profile_layer = next((layer for layer in ir.layers if layer.name == "PROFILE_CUTS"), None)
    waste_layer = next((layer for layer in ir.layers if layer.name == "WASTE_CUTS"), None)

    assert profile_layer is not None
    assert waste_layer is not None

    assert any(s.id == "rect1" for s in profile_layer.items if isinstance(s, Rect))
    assert any(s.id == "waste_cut_1" for s in waste_layer.items if isinstance(s, Rect))


def test_bounds_calculation():
    ast = LayoutAST(sheet=_make_sheet(200.0, 150.0, 12.0, 10.0), items=())

    ir = layoutast_to_diagram_ir(ast)

    assert ir.bounds.x_min == -10.0
    assert ir.bounds.x_max == 210.0
    assert ir.bounds.y_min == -10.0
    assert ir.bounds.y_max == 160.0


def _make_item_with_edge(shape_id: str, edge_treatment: dict, feature_type: str = "pocket") -> Item:
    return Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 60.0, "h_mm": 40.0, "edge_treatment": edge_treatment}),
        placement=Placement(center_xy_mm=(100.0, 75.0)),
        feature=Feature(type=feature_type, depth_mm=5.0),
        shape_id=shape_id,
    )


def test_edge_profiles_collected_for_chamfer():
    item = _make_item_with_edge("panel_a", {"type": "chamfer", "distance_mm": 3.0})
    ast = LayoutAST(sheet=_make_sheet(), items=(item,))
    ir = layoutast_to_diagram_ir(ast)

    profiles = ir.metadata["edge_profiles"]
    assert len(profiles) == 1
    assert profiles[0]["type"] == "chamfer"
    assert profiles[0]["distance_mm"] == 3.0
    assert "panel_a" in profiles[0]["items"]


def test_edge_profiles_collected_for_fillet():
    item = _make_item_with_edge("panel_b", {"type": "fillet", "radius_mm": 5.0})
    ast = LayoutAST(sheet=_make_sheet(), items=(item,))
    ir = layoutast_to_diagram_ir(ast)

    profiles = ir.metadata["edge_profiles"]
    assert len(profiles) == 1
    assert profiles[0]["type"] == "fillet"
    assert profiles[0]["radius_mm"] == 5.0
    assert "panel_b" in profiles[0]["items"]


def test_edge_profiles_skip_allowance():
    item = _make_item_with_edge(
        "panel_c",
        {"type": "allowance", "rough_allowance_mm": 0.5, "finish_allowance_mm": 0.1},
    )
    ast = LayoutAST(sheet=_make_sheet(), items=(item,))
    ir = layoutast_to_diagram_ir(ast)

    profiles = ir.metadata["edge_profiles"]
    assert len(profiles) == 0


def test_edge_allowances_collected():
    item = _make_item_with_edge(
        "panel_c",
        {"type": "allowance", "rough_allowance_mm": 0.5, "finish_allowance_mm": 0.1},
    )
    ast = LayoutAST(sheet=_make_sheet(), items=(item,))
    ir = layoutast_to_diagram_ir(ast)

    allowances = ir.metadata["edge_allowances"]
    assert len(allowances) == 1
    assert allowances[0]["rough_allowance_mm"] == 0.5
    assert allowances[0]["finish_allowance_mm"] == 0.1


def test_edge_profiles_deduplicated():
    item_a = _make_item_with_edge("panel_a", {"type": "chamfer", "distance_mm": 3.0})
    item_b = _make_item_with_edge("panel_b", {"type": "chamfer", "distance_mm": 3.0})
    ast = LayoutAST(sheet=_make_sheet(), items=(item_a, item_b))
    ir = layoutast_to_diagram_ir(ast)

    profiles = ir.metadata["edge_profiles"]
    assert len(profiles) == 1
    assert set(profiles[0]["items"]) == {"panel_a", "panel_b"}


def test_edge_profiles_empty_when_none():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
    )
    ir = layoutast_to_diagram_ir(ast)

    assert ir.metadata["edge_profiles"] == []
    assert ir.metadata["edge_allowances"] == []


def test_beam_structures_empty_by_default():
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
    )
    ir = layoutast_to_diagram_ir(ast)
    assert ir.metadata["beam_structures"] == []


def test_beam_structures_passed_through_config():
    beam_data = [
        {
            "name": "test_beam",
            "length_mm": 1000.0,
            "width_mm": 100.0,
            "thickness_mm": 19.0,
            "layer_count": 3,
            "total_thickness_mm": 57.0,
            "role": "RAIL",
            "layers": [
                {"layer_index": 0, "segments": [{"index": 0, "start_mm": 0.0, "end_mm": 1000.0, "length_mm": 1000.0}]},
                {"layer_index": 1, "segments": [{"index": 0, "start_mm": 0.0, "end_mm": 1000.0, "length_mm": 1000.0}]},
                {"layer_index": 2, "segments": [{"index": 0, "start_mm": 0.0, "end_mm": 1000.0, "length_mm": 1000.0}]},
            ],
        }
    ]
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(_make_profile_item("rect1", 100.0, 80.0, 100.0, 75.0),),
        config={"beam_structures": beam_data},
    )
    ir = layoutast_to_diagram_ir(ast)
    assert ir.metadata["beam_structures"] == beam_data
    assert ir.metadata["beam_structures"][0]["name"] == "test_beam"
    assert ir.metadata["beam_structures"][0]["layer_count"] == 3


def test_beam_labels_on_items():
    item_with_label = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 50.0, "h_mm": 30.0}),
        placement=Placement(center_xy_mm=(50.0, 50.0)),
        feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
        shape_id="beam_test_L0",
        label="TEST L0",
    )
    ast = LayoutAST(
        sheet=_make_sheet(),
        items=(item_with_label,),
    )
    ir = layoutast_to_diagram_ir(ast)
    label_layers = [layer for layer in ir.layers if layer.name == "LABELS"]
    assert len(label_layers) == 1
    labels = label_layers[0].items
    assert len(labels) == 1
    label = labels[0]
    assert isinstance(label, Text)
    assert label.content == "TEST L0"


@pytest.mark.parametrize(
    "kind,fields,depth,left_x",
    [
        ("chamfer", {"chamfer_width_mm": 2.0, "chamfer_angle_deg": 45.0}, 2.0, 85),
        ("bevel", {"bevel_width_mm": 2.0, "bevel_angle_deg": 45.0, "bevel_inner_depth_mm": 1.0}, 2.0, 83),
        ("roundover", {"roundover_radius_mm": 6.0}, 6.0, 78.3),
    ],
)
def test_edge_features_draw_planner_contours_and_actual_depth(kind, fields, depth, left_x):
    from cam.planner.passes.tools import normalize_tool_entries

    item = replace(_make_profile_item("edge", 50, 30, 100, 80), feature=Feature(type=kind, depth_mm=9, **fields))
    tools = normalize_tool_entries(
        [
            {"name": "v90", "kind": "v", "diameter": 12.7, "v_angle_deg": 90},
            {"name": "r6", "kind": "roundover", "diameter": 25.4, "roundover_radius_mm": 6},
        ]
    )

    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(240, 200, m=10), items=(item,)), edge_tools=tools)

    layer = next(layer for layer in diagram.layers if layer.name == f"{kind.upper()}_CUTS")
    path = next(shape for shape in layer.items if isinstance(shape, Polyline))
    assert min(p.x for p in path.points) == pytest.approx(left_x)
    assert path.style_token == kind and path.closed
    assert f"{kind}: {depth:.3f}mm" in diagram.metadata["depth_info"]
    assert any(isinstance(s, Text) and f"{depth:.3f}mm" in s.content for s in layer.items)


@pytest.mark.parametrize("origin", ["front", "back"])
@pytest.mark.parametrize("inside", [False, True])
def test_chamfer_drawing_follows_nominal_edge_for_both_sides(origin, inside):
    from cam.planner.passes.tools import normalize_tool_entries

    item = replace(
        _make_profile_item("edge", 50, 30, 100, 80),
        feature=Feature(
            type="chamfer", depth_mm=2, side="inside" if inside else "outside", chamfer_width_mm=2, chamfer_angle_deg=45
        ),
    )
    tools = normalize_tool_entries([{"name": "v90", "kind": "v", "diameter": 12.7, "v_angle_deg": 90}])
    diagram = layoutast_to_diagram_ir(
        LayoutAST(sheet=_make_sheet(240, 200, m=10), items=(item,)), edge_tools=tools, y_origin=origin
    )
    layer = next(layer for layer in diagram.layers if layer.name == "CHAMFER_CUTS")
    path = next(shape for shape in layer.items if isinstance(shape, Polyline))
    assert min(p.x for p in path.points) == pytest.approx(85)
    expected_min_y = 75 if origin == "front" else 95
    assert min(p.y for p in path.points) == pytest.approx(expected_min_y)


def test_bevel_drawing_retains_selected_angle_offset():
    from cam.planner.passes.tools import normalize_tool_entries

    item = replace(
        _make_profile_item("edge", 50, 30, 100, 80),
        feature=Feature(type="bevel", depth_mm=2, bevel_width_mm=2, bevel_angle_deg=30, bevel_inner_depth_mm=1),
    )
    tools = normalize_tool_entries([{"name": "v90", "kind": "v", "diameter": 12.7, "v_angle_deg": 90}])
    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(240, 200, m=10), items=(item,)), edge_tools=tools)
    layer = next(layer for layer in diagram.layers if layer.name == "BEVEL_CUTS")
    path = next(shape for shape in layer.items if isinstance(shape, Polyline))
    assert min(p.x for p in path.points) == pytest.approx(85 - 2 / 3**0.5)


def test_missing_edge_tool_is_drawn_as_unplanned_reference():
    item = replace(
        _make_profile_item("round", 50, 30, 100, 80),
        feature=Feature(type="roundover", depth_mm=6, roundover_radius_mm=6),
    )

    diagram = layoutast_to_diagram_ir(LayoutAST(sheet=_make_sheet(240, 200, m=10), items=(item,)), edge_tools=[])

    assert not any(layer.name == "ROUNDOVER_CUTS" for layer in diagram.layers)
    layer = next(layer for layer in diagram.layers if layer.name == "UNPLANNED_EDGES")
    assert any(s.style_token == "edge-unplanned" for s in layer.items)
    assert any(isinstance(s, Text) and "unplanned" in s.content.lower() for s in layer.items)
    assert any("roundover:" in d and "unplanned" in d for d in diagram.metadata["depth_info"])


@pytest.mark.parametrize("other_face", [False, True])
def test_edge_drawing_honors_supplied_removal_intent_and_start_depth(other_face):
    from adapters.ast_to_removal import item_to_removal_intent
    from cam.planner.passes.tools import normalize_tool_entries
    from ir.removal_intent import DepthProfile

    item = replace(
        _make_profile_item("edge", 50, 30, 100, 80),
        feature=Feature(type="chamfer", depth_mm=2, side="outside", chamfer_width_mm=2, chamfer_angle_deg=45),
    )
    intent = replace(
        item_to_removal_intent(item, 19), side="inside", depth_profile=DepthProfile.constant(z_top=-3, z_bottom=-5)
    )
    tools = normalize_tool_entries([{"name": "v90", "kind": "v", "diameter": 12.7, "v_angle_deg": 90}])

    intents = [replace(intent, face="back"), intent] if other_face else [intent]
    diagram = layoutast_to_diagram_ir(
        LayoutAST(sheet=_make_sheet(240, 200, m=10), items=(item,)), edge_tools=tools, removal_intents=intents
    )

    layer = next(layer for layer in diagram.layers if layer.name == "CHAMFER_CUTS")
    path = next(s for s in layer.items if isinstance(s, Polyline))
    assert min(p.x for p in path.points) == pytest.approx(85)
    assert "chamfer: 5.000mm" in diagram.metadata["depth_info"]
