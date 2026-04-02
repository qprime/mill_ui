from __future__ import annotations

from adapters.layoutast_to_ir import (
    FEATURE_HANDLERS,
    FEATURE_LAYER,
    layoutast_to_diagram_ir,
)
from diagram_ir import Circle, DiagramIR, Rect, Text
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet


def _make_sheet(w: float = 200.0, h: float = 150.0, t: float = 12.0, m: float = 0.0) -> Sheet:
    return Sheet(width_mm=w, height_mm=h, thickness_mm=t, margin_mm=m)


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
