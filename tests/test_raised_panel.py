from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.moves import CutMove, RapidMove, RetractMove
from cam.pipeline import run_pipeline
from cam.planner.passes.edge import build_edge_cut_plan
from cam.planner.passes.tools import ToolSelection
from cam.planner.planner_input import PlannerInput
from core.geometry import pocket_region
from ir.removal_intent import DepthProfile
from layout_ast.layout import LayoutAST
from layout_ast.raised_panel import RaisedPanelSpec
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import PMLParseError, parse_pml_yaml
from resolution.layout_resolver import resolve_layout
from validation import check_overlap
from validation.removal_checks import check_cross_face_web, check_edge_feature


def _source(profile="gutter", field=2, angle=90, shape="Rect"):
    width = "border_width: 25mm" if profile == "gutter" else ""
    dimensions = "width: 200mm\n          height: 300mm\n          radius: 80mm" if shape == "Arch" else ""
    return f"""Sheet: {{width: 800mm, height: 700mm, thickness: 19mm, margin: 10mm}}
children:
- AtPosition:
    x: 410mm
    y: 350mm
    width: 200mm
    height: 300mm
    child:
      {shape}:
          {dimensions}
          children:
          - Profile: {{side: outside, depth: through}}
          - Frame:
              width: 20mm
              children:
              - RaisedPanel:
                  profile: {profile}
                  {width}
                  border_depth: 6mm
                  field_depth: {field}mm
                  v_angle: {angle}
"""


def _tools(angle=90):
    return [
        ToolSelection("flat", 12.7, "flat", 14000, 1400, 350, depth_per_pass=3.5),
        ToolSelection("small flat", 3.175, "flat", 18000, 900, 250, depth_per_pass=1.5),
        ToolSelection("V", 12.7, "v", 18000, 540, 180, depth_per_pass=1, v_angle_deg=angle),
    ]


def _entry(source):
    ast = resolve_layout(parse_pml_yaml(source))
    intents = ast_to_removal_intents(ast)
    raised = next(i for i in intents if i.hint_type == "raised_panel")
    entry = removal_intents_to_planner_input([raised]).edge_features[0]
    return ast, intents, raised, entry


@pytest.mark.parametrize("component_part", ["milling", "frame"])
@pytest.mark.parametrize("body_list", [False, True])
def test_arch_frame_components_preserve_the_same_machining_intents(component_part, body_list):
    from io import StringIO

    from ruamel.yaml import YAML

    source = _source(shape="Arch")
    yaml = YAML()
    data = yaml.load(source)
    children = data["children"][0]["AtPosition"]["child"]["Arch"]["children"]
    if component_part == "milling":
        children = children[1]["Frame"]["children"]
        index = 0
    else:
        index = 1
    body = children[index]
    data["components"] = {
        "cut": {"body": [body] if body_list else body},
        "nested": {"body": {"UseComponent": {"name": "cut"}}},
    }
    children[index] = {"UseComponent": {"name": "nested"}}
    stream = StringIO()
    yaml.dump(data, stream)
    component = parse_pml_yaml(stream.getvalue())

    actual = ast_to_removal_intents(resolve_layout(component))
    expected = ast_to_removal_intents(resolve_layout(parse_pml_yaml(source)))

    assert actual == expected
    assert check_overlap(actual).is_valid()
    assert parse_pml_yaml(format_pml_yaml(component)) == component


@pytest.mark.parametrize("shape", ["Rect", "Arch"])
@pytest.mark.parametrize("angle", [60, 90])
@pytest.mark.parametrize("profile, field, pocket_count", [("gutter", 2, 2), ("v_groove", 2, 1), ("v_groove", 0, 0)])
def test_profiles_preserve_depths_and_keep_the_complete_cutter_in_the_cell(shape, angle, profile, field, pocket_count):
    _, intents, raised, entry = _entry(_source(profile, field, angle, shape))
    assert check_overlap(intents).is_valid()
    assert raised.depth_mm() == 6
    assert isinstance(raised.edge_feature, RaisedPanelSpec)
    assert raised.edge_feature.field_depth_mm == field
    plan = build_edge_cut_plan(entry, _tools(angle))
    assert plan.depth_mm == 6
    assert len(plan.pockets) == pocket_count
    cell = pocket_region(raised.shape, raised.shape_geometry, raised.bounds.center)
    assert cell is not None
    centerline = Polygon([(p.x, p.y) for p in plan.shape.points]).boundary
    footprint = centerline.buffer(raised.edge_feature.cutter_radius_at_depth_mm, quad_segs=64)
    assert cell.buffer(1e-6).covers(footprint)
    for pocket in plan.pockets:
        assert cell.covers(pocket.region)
    assert [p.depth_mm for p in plan.pockets] == ([6, 2] if profile == "gutter" else [field] if field else [])


@pytest.mark.parametrize("profile, field, angle", [("gutter", 2, 90), ("v_groove", 2, 60), ("v_groove", 0, 90)])
def test_profile_survives_pml_flat_ast_ir_and_planner_serialization(tmp_path, profile, field, angle):
    parsed = parse_pml_yaml(_source(profile, field, angle))
    assert parse_pml_yaml(format_pml_yaml(parsed)) == parsed
    ast, _, raised, entry = _entry(_source(profile, field, angle))
    path = tmp_path / "layout.json"
    subset = replace(ast, items=tuple(i for i in ast.items if i.feature and i.feature.type == "raised_panel"))
    path.write_text(subset.to_json())
    assert LayoutAST.from_json(str(path)).items == subset.items
    planner = removal_intents_to_planner_input([raised])
    restored = PlannerInput.from_hints_dict(json.loads(json.dumps(planner.to_hints_dict())))
    assert restored.edge_features[0] == entry
    assert raised.to_dict()["edge_feature"] == raised.edge_feature.to_dict()


@pytest.mark.parametrize("angle", [30, 60, 90, 120])
def test_v_groove_width_is_derived_from_its_included_angle(angle):
    spec = RaisedPanelSpec(6, 2, profile="v_groove", v_angle_deg=angle)
    expected = {30: 2.6794919243, 60: 5.7735026919, 90: 10, 120: 17.3205080757}[angle]
    assert spec.field_inset_mm == pytest.approx(expected)


def test_wide_gutter_retains_its_width_and_has_a_tool_matched_inner_bevel():
    spec = RaisedPanelSpec(6, 2, 25, v_angle_deg=90)
    assert spec.field_inset_mm == 25
    assert spec.groove_inset_mm == 21
    assert spec.slope_run_mm == pytest.approx(4)


@pytest.mark.parametrize(
    "changes, error",
    [
        ({"border_depth_mm": 0}, "border_depth"),
        ({"field_depth_mm": 6}, "field_depth"),
        ({"field_depth_mm": -1}, "field_depth"),
        ({"v_angle_deg": 180}, "v_angle"),
        ({"border_width_mm": 8}, "at least"),
        ({"border_width_mm": None}, "border_width"),
        ({"profile": "unknown"}, "unknown profile"),
        ({"profile": "v_groove"}, "omit border_width"),
    ],
)
def test_invalid_profiles_raise_instead_of_becoming_another_shape(changes, error):
    with pytest.raises(ValueError, match=error):
        replace(RaisedPanelSpec(6, 2, 25), **changes)


@pytest.mark.parametrize(
    "tools, error", [(_tools(60), "requires a 90"), ([_tools()[0]], "V-bit"), ([_tools()[-1]], "flat tool")]
)
def test_missing_required_cutting_capability_is_an_error(tools, error):
    _, _, _, entry = _entry(_source())
    with pytest.raises(ValueError, match=error):
        build_edge_cut_plan(entry, tools)


def test_tool_diameter_limits_the_depth_of_a_wide_angle_bit():
    _, _, _, entry = _entry(_source(angle=120))
    with pytest.raises(ValueError, match="cannot reach depth"):
        build_edge_cut_plan(entry, _tools(120))


def test_plain_v_groove_needs_no_flat_tool():
    _, _, _, entry = _entry(_source("v_groove", 0))
    plan = build_edge_cut_plan(entry, [_tools()[-1]])
    assert not plan.pockets


def test_required_profile_does_not_disappear_when_its_field_collapses():
    with pytest.raises(ValueError, match="field inset"):
        resolve_layout(parse_pml_yaml(_source().replace("border_width: 25mm", "border_width: 200mm")))


def test_missing_v_bit_blocks_the_setup_but_retains_a_diagnostic_blueprint():
    ast, _, _, _ = _entry(_source())
    tools = [{"name": "flat", "diameter_mm": 3.175, "kind": "flat", "rpm": 18000, "feed_xy": 900, "feed_z": 250}]
    result = run_pipeline(ast, tool_db=tools, generate_svg=True)
    assert result.gcode == {}
    assert any("V-bit" in str(error) for error in result.errors)
    assert result.svg is not None


def test_arced_shoulder_pocket_moves_keep_the_full_flat_cutter_inside_the_cell():
    ast, _, raised, _ = _entry(_source(shape="Arch"))
    result = run_pipeline(ast, tool_db=[asdict(t) for t in _tools()], generate_svg=False)
    assert not result.errors
    cell = pocket_region(raised.shape, raised.shape_geometry, raised.bounds.center)
    assert cell is not None
    records = [p for p in result.passes if p.op == "pocket_offset"]
    assert len(records) == 1
    record = records[0]
    x = y = z = None
    parts: list[BaseGeometry] = []
    for move in record.moves:
        if isinstance(move, RetractMove):
            z = move.z
        elif isinstance(move, (RapidMove, CutMove)):
            previous = x, y, z
            x = move.x if move.x is not None else x
            y = move.y if move.y is not None else y
            z = move.z if move.z is not None else z
            if isinstance(move, CutMove) and z == -6 and x is not None and y is not None:
                parts.append(Point(x, y))
                if previous[2] == -6 and previous[0] is not None and previous[1] is not None:
                    parts.append(LineString([(previous[0], previous[1]), (x, y)]))
    footprint = unary_union(parts).buffer(record.tool_selection.diameter / 2, quad_segs=96)
    assert cell.buffer(0.001).covers(footprint)
    assert record.count == 2


@pytest.mark.parametrize("changes", [{"depth_mm": 5}, {"start_depth_mm": 1}])
def test_inconsistent_depth_coordinates_are_rejected(changes):
    _, _, _, entry = _entry(_source())
    with pytest.raises(ValueError, match=r"depth|starting"):
        build_edge_cut_plan(replace(entry, **changes), _tools())


def test_unknown_profile_options_are_not_silently_ignored():
    with pytest.raises(PMLParseError, match="Unknown RaisedPanel"):
        parse_pml_yaml(_source().replace("v_angle: 90", "angle: 90"))


def test_minimum_width_gutter_can_use_a_smaller_flat_cutter():
    source = _source().replace("border_width: 25mm", "border_width: 10mm")
    _, _, _, entry = _entry(source)
    plan = build_edge_cut_plan(entry, _tools())
    assert len(plan.pockets) == 2
    assert plan.pockets[0].tool.diameter == 3.175


def test_gutter_with_original_height_field_has_no_field_pocket():
    _, _, _, entry = _entry(_source(field=0))
    plan = build_edge_cut_plan(entry, _tools())
    assert len(plan.pockets) == 1
    assert plan.pockets[0].depth_mm == 6


@pytest.mark.parametrize("thickness", [5, 6])
def test_raised_panel_cannot_cut_through_its_stock(thickness):
    _, _, raised, _ = _entry(_source())
    result = check_edge_feature(raised, thickness)
    assert any("must be less than sheet thickness" in error.message for error in result.errors)


def test_back_pocket_cannot_break_through_the_raised_panel_gutter():
    _, _, raised, _ = _entry(_source())
    back = replace(
        raised,
        region_id="back_pocket",
        feature_type="pocket",
        edge_feature=None,
        face="back",
        depth_profile=DepthProfile.constant(z_top=0, z_bottom=-12),
    )
    assert not check_cross_face_web([raised, back], 19, 2).is_valid()


@pytest.mark.parametrize("side, depth", [("inside", 19), ("outside", 6)])
def test_containment_does_not_waive_an_incompatible_parent_profile(side, depth):
    _, intents, raised, _ = _entry(_source())
    profile = next(i for i in intents if i.hint_type == "profile")
    profile = replace(profile, side=side, depth_profile=DepthProfile.constant(z_top=0, z_bottom=-depth))
    assert not check_overlap([profile, raised]).is_valid()


def test_through_recess_blocks_gcode_instead_of_only_reporting_a_depth_error():
    ast, _, _, _ = _entry(_source().replace("thickness: 19mm", "thickness: 6mm"))
    result = run_pipeline(ast, tool_db=[asdict(t) for t in _tools()], generate_svg=False)
    assert any("stock thickness" in str(error) for error in result.errors)
    assert result.gcode == {}


def test_missing_profile_spec_is_retained_as_a_required_unplannable_feature():
    ast, _, _, _ = _entry(_source())
    items = tuple(
        replace(item, feature=replace(item.feature, raised_panel=None))
        if item.feature and item.feature.type == "raised_panel"
        else item
        for item in ast.items
    )
    result = run_pipeline(replace(ast, items=items), tool_db=[asdict(t) for t in _tools()], generate_svg=False)
    assert any("no edge_feature spec" in str(error) for error in result.errors)
    assert result.gcode == {}
