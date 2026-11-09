#!/usr/bin/env python3

from dataclasses import replace

import pytest

from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.pipeline import GcodeFile, GcodeNameCollisionError, _claim_gcode_name, gcode_file_groups, run_pipeline
from cam.planner.passes import PassAccumulator
from cam.planner.passes.tools import ToolSelection
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, RestSpec, Sheet
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout

TOOL_DB = [
    {"name": "1/8_endmill", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
    {"name": "1/4_endmill", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    {"name": "3/8_endmill", "diameter": 9.525, "kind": "flat", "rpm": 10000, "feed_xy": 700, "feed_z": 250},
]


def _make_multi_tool_ast(gcode_output: str = "per-operation") -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(
            width_mm=400,
            height_mm=300,
            thickness_mm=19,
            margin_mm=0.0,
            gcode_output=gcode_output,
        ),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 100)),
                feature=Feature(type="pocket", depth_mm=6.0),
                shape_id="pocket_1",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 100)),
                feature=Feature(type="profile", side="outside", depth_mm=0.0, is_through=True),
                shape_id="profile_1",
            ),
        ),
    )


class TestGcodeOutputDefault:
    def test_default_is_per_operation(self):
        sheet = Sheet(width_mm=400, height_mm=300, thickness_mm=19)
        assert sheet.gcode_output == "per-operation"

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="Invalid gcode_output"):
            Sheet(width_mm=400, height_mm=300, thickness_mm=19, gcode_output="bad")


class TestPerOperationOutput:
    def test_per_operation_keys_include_op_name(self):
        ast = _make_multi_tool_ast("per-operation")
        result = run_pipeline(ast, tool_db=TOOL_DB, generate_svg=False)
        assert len(result.gcode) >= 1
        for key in result.gcode:
            assert "-" in key
            parts = key.rsplit("-", 1)
            assert parts[0] in (
                "pocket",
                "profile",
                "pocket_rest",
                "edge",
                "hole",
                "engrave",
                "corner_cleanup",
                "dogbone",
            )


class TestPerToolOutput:
    def test_per_tool_groups_by_diameter(self):
        ast = _make_multi_tool_ast("per-tool")
        result = run_pipeline(ast, tool_db=TOOL_DB, generate_svg=False)
        for key in result.gcode:
            assert key.endswith("mm")
            assert key[0].isdigit()

    def test_per_tool_fewer_files_than_per_operation(self):
        ast_per_op = _make_multi_tool_ast("per-operation")
        ast_per_tool = _make_multi_tool_ast("per-tool")
        result_per_op = run_pipeline(ast_per_op, tool_db=TOOL_DB, generate_svg=False)
        result_per_tool = run_pipeline(ast_per_tool, tool_db=TOOL_DB, generate_svg=False)
        assert len(result_per_tool.gcode) <= len(result_per_op.gcode)

    def test_per_tool_same_total_moves(self):
        ast_per_op = _make_multi_tool_ast("per-operation")
        ast_per_tool = _make_multi_tool_ast("per-tool")
        result_per_op = run_pipeline(ast_per_op, tool_db=TOOL_DB, generate_svg=False)
        result_per_tool = run_pipeline(ast_per_tool, tool_db=TOOL_DB, generate_svg=False)
        assert (
            result_per_tool.metrics["complexity"]["total_moves"] == result_per_op.metrics["complexity"]["total_moves"]
        )


class TestPerToolWithRestPocket:
    def test_rest_pocket_merges_by_tool(self):
        ast = LayoutAST(
            sheet=Sheet(
                width_mm=400,
                height_mm=300,
                thickness_mm=19,
                margin_mm=0.0,
                gcode_output="per-tool",
            ),
            items=(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": 150, "h_mm": 100}),
                    placement=Placement(center_xy_mm=(200, 150)),
                    feature=Feature(
                        type="pocket",
                        depth_mm=12.0,
                        rest=RestSpec(tool_diameter_mm=6.35),
                    ),
                    shape_id="deep_pocket",
                ),
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": 150, "h_mm": 100}),
                    placement=Placement(center_xy_mm=(200, 150)),
                    feature=Feature(type="profile", side="outside", depth_mm=0.0, is_through=True),
                    shape_id="profile",
                ),
            ),
        )
        result = run_pipeline(ast, tool_db=TOOL_DB, generate_svg=False)
        for key in result.gcode:
            assert key.endswith("mm")
            assert key[0].isdigit()
        diameters = {float(k.replace("mm", "")) for k in result.gcode}
        assert len(diameters) >= 2


class TestPMLParsing:
    def test_gcode_output_parsed(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
  gcode_output: per-tool

children:
  - Rect:
      children:
        - Profile: {side: outside, depth: through}
"""
        comp_ast = parse_pml_yaml(pml)
        assert comp_ast.sheet.gcode_output == "per-tool"

    def test_gcode_output_default_when_absent(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      children:
        - Profile: {side: outside, depth: through}
"""
        comp_ast = parse_pml_yaml(pml)
        assert comp_ast.sheet.gcode_output == "per-operation"

    def test_gcode_output_invalid_value(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
  gcode_output: per-shape

children:
  - Rect:
      children:
        - Profile: {side: outside, depth: through}
"""
        with pytest.raises(ValueError, match="Invalid gcode_output"):
            parse_pml_yaml(pml)

    def test_per_tool_end_to_end_via_pml(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
  gcode_output: per-tool

children:
  - Rect:
      id: panel
      children:
        - Profile: {side: outside, depth: through}
        - Frame:
            width: 50mm
            children:
              - Pocket: {depth: 6mm}
"""
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        result = run_pipeline(ast, tool_db=TOOL_DB, generate_svg=False)
        for key in result.gcode:
            assert key.endswith("mm")
            assert key[0].isdigit()


class TestYAMLRoundtrip:
    def test_per_tool_roundtrips(self):
        from pml.yaml_formatter import format_pml_yaml

        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
  gcode_output: per-tool

children:
  - Rect:
      children:
        - Profile: {side: outside, depth: through}
"""
        comp_ast = parse_pml_yaml(pml)
        yaml_out = format_pml_yaml(comp_ast)
        comp_ast2 = parse_pml_yaml(yaml_out)
        assert comp_ast2.sheet.gcode_output == "per-tool"

    def test_default_not_emitted(self):
        from pml.yaml_formatter import format_pml_yaml

        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm

children:
  - Rect:
      children:
        - Profile: {side: outside, depth: through}
"""
        comp_ast = parse_pml_yaml(pml)
        yaml_out = format_pml_yaml(comp_ast)
        assert "gcode_output" not in yaml_out


def _make_two_face_ast(gcode_output: str = "per-operation") -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(
            width_mm=400,
            height_mm=300,
            thickness_mm=19,
            margin_mm=0.0,
            gcode_output=gcode_output,
        ),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 100)),
                feature=Feature(type="pocket", depth_mm=6.0),
                shape_id="front_pocket",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 35.0}),
                placement=Placement(center_xy_mm=(300, 60)),
                feature=Feature(type="pocket", depth_mm=12.5, face="back"),
                shape_id="hinge_cup",
            ),
        ),
    )


class TestTwoFaceOutput:
    def test_back_items_produce_prefixed_gcode(self):
        result = run_pipeline(_make_two_face_ast(), tool_db=TOOL_DB, generate_svg=False)

        assert result.errors == []
        back_keys = [k for k in result.gcode if k.startswith("back-")]
        front_keys = [k for k in result.gcode if not k.startswith("back-")]
        assert back_keys and front_keys
        assert all(not k.startswith("back-back-") for k in back_keys)

    def test_back_programs_precede_front_in_metrics(self):
        result = run_pipeline(_make_two_face_ast(), tool_db=TOOL_DB, generate_svg=False)

        keys = list(result.gcode)
        first_back = next(k for k in keys if k.startswith("back-"))
        first_front = next(k for k in keys if not k.startswith("back-"))
        assert keys.index(first_back) < keys.index(first_front)

    def test_back_pocket_gcode_uses_mirrored_y(self):
        result = run_pipeline(_make_two_face_ast(), tool_db=TOOL_DB, generate_svg=False)

        back_gcode = "".join(gc for name, gc in result.gcode.items() if name.startswith("back-"))
        y_values = [
            float(token[1:]) for line in back_gcode.splitlines() for token in line.split() if token.startswith("Y")
        ]
        cut_y = [y for y in y_values if y != 0.0]
        assert cut_y
        assert all(220.0 < y < 260.0 for y in cut_y)

    def test_single_face_job_names_unchanged(self):
        result = run_pipeline(_make_multi_tool_ast(), tool_db=TOOL_DB, generate_svg=False)

        assert set(result.gcode) == {"pocket-9.53mm", "profile-6.35mm"}

    def test_single_face_job_metrics_unchanged(self):
        result = run_pipeline(_make_multi_tool_ast(), tool_db=TOOL_DB, generate_svg=False)
        metrics = result.metrics

        assert set(metrics["output_size"]["files"]) == set(result.gcode)
        assert metrics["fidelity"]["tool_changes"] == len(result.passes)
        assert [p["name"] for p in metrics["fidelity"]["passes"]] == [p.op for p in result.passes]
        assert metrics["complexity"]["total_moves"] == sum(len(p.moves) for p in result.passes)
        assert result.svg_back is None

    def test_two_face_metrics_merge_across_setups(self):
        result = run_pipeline(_make_two_face_ast(), tool_db=TOOL_DB, generate_svg=False)
        metrics = result.metrics

        assert set(metrics["output_size"]["files"]) == set(result.gcode)
        assert metrics["fidelity"]["tool_changes"] == len(result.passes)
        assert metrics["complexity"]["total_moves"] == sum(len(p.moves) for p in result.passes)

    def test_per_tool_mode_groups_faces_separately(self):
        result = run_pipeline(_make_two_face_ast("per-tool"), tool_db=TOOL_DB, generate_svg=False)

        assert "back-12.70mm" not in result.gcode or "12.70mm" in result.gcode
        for key in result.gcode:
            stem = key[len("back-") :] if key.startswith("back-") else key
            assert stem.endswith("mm")
            assert stem[0].isdigit()

    def test_unmirrorable_back_item_reported_as_error(self):
        ast = _make_two_face_ast()
        dogboned_back = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 40.0, "h_mm": 40.0}),
            placement=Placement(center_xy_mm=(300, 200)),
            feature=Feature(type="pocket", depth_mm=6.0, face="back", dogbone_corners=((10.0, 20.0),)),
            shape_id="notched_back_pocket",
        )
        ast = LayoutAST(sheet=ast.sheet, items=(ast.items[0], dogboned_back))

        result = run_pipeline(ast, tool_db=TOOL_DB, generate_svg=False)

        assert any("Back-face mirror" in e for e in result.errors)
        assert result.gcode == {}

    def test_cross_face_web_breach_reported(self):
        ast = _make_two_face_ast()
        deep_back = Item(
            kind="shape",
            type="Circle",
            geometry=Geometry(data={"diameter_mm": 35.0}),
            placement=Placement(center_xy_mm=(100, 100)),
            feature=Feature(type="pocket", depth_mm=12.5, face="back"),
            shape_id="overlapping_cup",
        )
        ast = LayoutAST(sheet=ast.sheet, items=(ast.items[0], deep_back))

        result = run_pipeline(ast, tool_db=TOOL_DB, generate_svg=False)

        assert any("web breach" in e for e in result.errors)


class TestGcodeFileMap:
    @pytest.mark.parametrize("mode", ["per-operation", "per-tool"])
    def test_every_gcode_file_lists_its_passes(self, mode):
        result = run_pipeline(_make_multi_tool_ast(mode), tool_db=TOOL_DB, generate_svg=False)

        assert set(result.gcode_files) == set(result.gcode)
        mapped = [p for gcode_file in result.gcode_files.values() for p in gcode_file.passes]
        assert sorted(id(p) for p in mapped) == sorted(id(p) for p in result.passes)
        assert {gcode_file.face for gcode_file in result.gcode_files.values()} == {"front"}

    def test_per_tool_file_holds_every_pass_of_its_diameter(self):
        result = run_pipeline(_make_multi_tool_ast("per-tool"), tool_db=TOOL_DB, generate_svg=False)

        for name, gcode_file in result.gcode_files.items():
            assert {f"{p.setup.tool.diameter:.2f}mm" for p in gcode_file.passes} == {name}

    def test_back_face_files_are_marked_back(self):
        ast = _make_multi_tool_ast("per-operation")
        back_pocket = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 40, "h_mm": 30}),
            placement=Placement(center_xy_mm=(300, 200)),
            feature=Feature(type="pocket", depth_mm=4.0, face="back"),
            shape_id="back_pocket",
        )
        result = run_pipeline(
            LayoutAST(sheet=ast.sheet, items=(*ast.items, back_pocket)), tool_db=TOOL_DB, generate_svg=False
        )

        faces = {name: gcode_file.face for name, gcode_file in result.gcode_files.items()}
        assert faces
        assert all(face == ("back" if name.startswith("back-") else "front") for name, face in faces.items())
        assert "back" in faces.values()


TWO_CHAMFER_ANGLES_PML = """Sheet:
  width: 500mm
  height: 300mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: a
    at: {x: 125mm, y: 150mm, width: 150mm, height: 150mm}
    children:
    - Chamfer: {width: 4mm, depth: 4mm}
- Rect:
    id: b
    at: {x: 375mm, y: 150mm, width: 150mm, height: 150mm}
    children:
    - Chamfer: {width: 6.93mm, depth: 4mm}
"""


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("per-operation", {"edge-12.70mm-90deg": 90.0, "edge-12.70mm-60deg": 60.0}),
        ("per-tool", {"12.70mm-90deg": 90.0, "12.70mm-60deg": 60.0}),
    ],
)
def test_same_diameter_vbits_get_one_file_each(mode, expected):
    pml = TWO_CHAMFER_ANGLES_PML.replace("  material: mdf\n", f"  material: mdf\n  gcode_output: {mode}\n")
    result = run_pipeline(resolve_layout(parse_pml_yaml(pml)), kerf_mm=3.175, generate_svg=False)

    assert set(result.gcode) == set(expected)
    for name, gcode_file in result.gcode_files.items():
        assert {p.tool_selection.v_angle_deg for p in gcode_file.passes} == {expected[name]}


def _record(op: str, **tool_fields):
    tool = ToolSelection(name=op, diameter=6.35, kind="flat", rpm=18000, feed_xy=1200.0, feed_z=300.0)
    accumulator = PassAccumulator(
        machine=Machine(), stock=Stock(width=300, height=200, thickness=19), safe_z=3.0, prime_spindle=False
    )
    return accumulator.get_record(op, replace(tool, **tool_fields))


class TestGcodeFileGroups:
    def test_distinct_names_stay_bare(self):
        groups = gcode_file_groups([_record("pocket"), _record("profile")], per_tool=False)

        assert [name for name, _ in groups] == ["pocket-6.35mm", "profile-6.35mm"]

    def test_kind_suffix_when_only_kind_differs(self):
        groups = gcode_file_groups([_record("pocket"), _record("pocket", kind="ball")], per_tool=False)

        assert [name for name, _ in groups] == ["pocket-6.35mm-flat", "pocket-6.35mm-ball"]

    def test_rotation_suffix_when_only_rotation_differs(self):
        records = [_record("profile", rotation="upcut"), _record("profile", rotation="downcut")]

        assert [name for name, _ in gcode_file_groups(records, per_tool=False)] == [
            "profile-6.35mm-upcut",
            "profile-6.35mm-downcut",
        ]

    def test_per_tool_merges_ops_of_one_tool_and_splits_distinct_tools(self):
        records = [_record("pocket"), _record("dogbone"), _record("pocket", kind="ball")]

        groups = gcode_file_groups(records, per_tool=True)

        assert [(name, [p.op for p in group]) for name, group in groups] == [
            ("6.35mm-flat", ["pocket", "dogbone"]),
            ("6.35mm-ball", ["pocket"]),
        ]

    def test_claiming_a_taken_name_raises(self):
        gcode_files: dict = {}
        _claim_gcode_name(gcode_files, "edge-12.70mm", GcodeFile(face="front", passes=(_record("edge"),)))

        with pytest.raises(GcodeNameCollisionError, match=r"edge-12\.70mm\.nc"):
            _claim_gcode_name(gcode_files, "edge-12.70mm", GcodeFile(face="front", passes=(_record("edge"),)))
