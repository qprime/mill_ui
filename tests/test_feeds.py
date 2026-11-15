from __future__ import annotations

import textwrap
from dataclasses import replace
from pathlib import Path

import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from cam.pipeline import run_pipeline
from cam.planner.passes.tools import (
    ToolSelection,
    apply_feeds_override,
    normalize_tool_entries,
    pick_tool_for_roundover,
)
from config.machine_loader import (
    Endmill,
    FeedsEntry,
    _reset_caches,
    build_tool_db,
    load_endmills,
    load_feeds,
    resolve_tool_selection,
)
from layout_ast.layout import FeedsOverride, Sheet
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout

pytestmark = pytest.mark.usefixtures("machining_config")


def _endmill(name="test_flat_6", diameter=6.35, flutes=2, type_="upcut_spiral", v_angle=None, roundover_radius=None):
    return Endmill(
        name=name,
        diameter_mm=diameter,
        flute_length_mm=25.4,
        shank_diameter_mm=diameter,
        flutes=flutes,
        type=type_,
        v_angle_deg=v_angle,
        roundover_radius_mm=roundover_radius,
    )


def _feeds_entry(endmill="test_flat_6", material="mdf", chipload=0.05, rpm=18000, dpp=3.0, pf=0.33):
    return FeedsEntry(
        endmill=endmill,
        material=material,
        chipload=chipload,
        rpm=rpm,
        depth_per_pass=dpp,
        plunge_factor=pf,
    )


class TestFeedsEntry:
    def test_valid_construction(self):
        entry = _feeds_entry()
        assert entry.endmill == "test_flat_6"
        assert entry.material == "mdf"
        assert entry.chipload == 0.05

    def test_chipload_must_be_positive(self):
        with pytest.raises(ValueError, match="Chipload must be positive"):
            _feeds_entry(chipload=0)

    def test_rpm_must_be_positive(self):
        with pytest.raises(ValueError, match="RPM must be positive"):
            _feeds_entry(rpm=0)

    def test_depth_per_pass_must_be_positive(self):
        with pytest.raises(ValueError, match="depth_per_pass must be positive"):
            _feeds_entry(dpp=0)

    def test_plunge_factor_bounds(self):
        with pytest.raises(ValueError, match="plunge_factor must be in"):
            _feeds_entry(pf=0)
        with pytest.raises(ValueError, match="plunge_factor must be in"):
            _feeds_entry(pf=1.5)

    def test_plunge_factor_at_one(self):
        entry = _feeds_entry(pf=1.0)
        assert entry.plunge_factor == 1.0


class TestResolveToolSelection:
    def test_feed_xy_computation(self):
        em = _endmill(flutes=2)
        feeds = _feeds_entry(chipload=0.05, rpm=18000)
        result = resolve_tool_selection(em, feeds)
        expected_feed_xy = 18000 * 2 * 0.05
        assert result["feed_xy"] == expected_feed_xy

    def test_feed_z_computation(self):
        em = _endmill(flutes=2)
        feeds = _feeds_entry(chipload=0.05, rpm=18000, pf=0.33)
        result = resolve_tool_selection(em, feeds)
        expected_feed_xy = 18000 * 2 * 0.05
        expected_feed_z = expected_feed_xy * 0.33
        assert result["feed_z"] == expected_feed_z

    def test_kind_mapping_flat(self):
        for type_ in ["upcut_spiral", "downcut_spiral", "compression", "straight"]:
            em = _endmill(type_=type_)
            result = resolve_tool_selection(em, _feeds_entry())
            assert result["kind"] == "flat"

    def test_kind_mapping_v(self):
        em = _endmill(type_="v_bit", v_angle=90)
        result = resolve_tool_selection(em, _feeds_entry())
        assert result["kind"] == "v"
        assert result["v_angle_deg"] == 90

    def test_kind_mapping_ball(self):
        for type_ in ["ball", "engraving"]:
            em = _endmill(type_=type_)
            result = resolve_tool_selection(em, _feeds_entry())
            assert result["kind"] == "ball"

    def test_rotation_mapping(self):
        assert resolve_tool_selection(_endmill(type_="upcut_spiral"), _feeds_entry())["rotation"] == "upcut"
        assert resolve_tool_selection(_endmill(type_="downcut_spiral"), _feeds_entry())["rotation"] == "downcut"
        assert resolve_tool_selection(_endmill(type_="compression"), _feeds_entry())["rotation"] == "compression"
        assert resolve_tool_selection(_endmill(type_="straight"), _feeds_entry())["rotation"] is None

    def test_stepover_percent_passed_through(self):
        feeds = FeedsEntry(
            endmill="test",
            material="mdf",
            chipload=0.05,
            rpm=18000,
            depth_per_pass=3.0,
            plunge_factor=0.33,
            stepover_percent=40.0,
        )
        result = resolve_tool_selection(_endmill(), feeds)
        assert result["stepover_percent"] == 40.0

    def test_stepover_percent_absent(self):
        result = resolve_tool_selection(_endmill(), _feeds_entry())
        assert "stepover_percent" not in result


class TestBuildToolDb:
    def test_filters_by_material(self):
        endmills = [_endmill("bit_a"), _endmill("bit_b")]
        feeds = [
            _feeds_entry(endmill="bit_a", material="mdf"),
            _feeds_entry(endmill="bit_b", material="plywood"),
        ]
        result = build_tool_db(endmills, feeds, "mdf")
        assert len(result) == 1
        assert result[0]["name"] == "bit_a"

    def test_material_case_insensitive(self):
        endmills = [_endmill("bit_a")]
        feeds = [_feeds_entry(endmill="bit_a", material="MDF")]
        result = build_tool_db(endmills, feeds, "mdf")
        assert len(result) == 1

    def test_raises_when_no_tools_resolve(self):
        endmills = [_endmill("bit_a")]
        feeds = [_feeds_entry(endmill="bit_a", material="plywood")]
        with pytest.raises(ValueError, match="No endmills have feeds entries for material 'mdf'"):
            build_tool_db(endmills, feeds, "mdf")

    def test_multiple_tools_same_material(self):
        endmills = [_endmill("bit_a"), _endmill("bit_b", diameter=3.175)]
        feeds = [
            _feeds_entry(endmill="bit_a", material="mdf"),
            _feeds_entry(endmill="bit_b", material="mdf", chipload=0.03, rpm=20000),
        ]
        result = build_tool_db(endmills, feeds, "mdf")
        assert len(result) == 2

    def test_endmill_without_feeds_excluded(self):
        endmills = [_endmill("bit_a"), _endmill("bit_b")]
        feeds = [_feeds_entry(endmill="bit_a", material="mdf")]
        result = build_tool_db(endmills, feeds, "mdf")
        assert len(result) == 1
        assert result[0]["name"] == "bit_a"


class TestLoadEndmills:
    def test_roundover_library_preserves_kind_and_radius_for_tool_selection(self, tmp_path):
        yml = tmp_path / "endmills.yml"
        yml.write_text(
            textwrap.dedent("""\
            endmills:
              - name: test roundover
                diameter_mm: 24
                flute_length_mm: 12
                shank_diameter_mm: 6.35
                flutes: 2
                type: roundover
                roundover_radius_mm: 6
        """)
        )
        tools = build_tool_db(load_endmills(yml), [_feeds_entry(endmill="test roundover")], "mdf")
        assert tools[0]["kind"] == "roundover"
        assert tools[0]["roundover_radius_mm"] == 6
        selected = pick_tool_for_roundover(normalize_tool_entries(tools), radius_mm=6)
        assert selected.name == "test roundover"
        assert selected.roundover_radius_mm == 6
        assert selected.as_model().roundover_radius_mm == 6

    @pytest.mark.parametrize("radius", [None, 0, -1, float("nan"), float("inf"), 13])
    def test_roundover_requires_a_valid_radius_that_fits_the_cutter(self, radius):
        with pytest.raises(ValueError, match=r"[Rr]oundover"):
            _endmill(type_="roundover", diameter=24, roundover_radius=radius)

    def test_roundover_radius_cannot_be_ignored_on_another_tool_type(self):
        with pytest.raises(ValueError, match="requires type roundover"):
            _endmill(type_="straight", diameter=24, roundover_radius=6)


class TestLoadFeeds:
    def test_load_feeds_yml(self, tmp_path):
        yml = tmp_path / "feeds.yml"
        yml.write_text(
            textwrap.dedent("""\
            feeds:
              - endmill: "test_flat_6"
                material: mdf
                chipload: 0.05
                rpm: 18000
                depth_per_pass: 3.0
                plunge_factor: 0.33
                stepover_percent: 40
        """)
        )
        entries = load_feeds(yml)
        assert len(entries) == 1
        assert entries[0].endmill == "test_flat_6"
        assert entries[0].stepover_percent == 40.0


class TestLoaderCaching:
    @pytest.fixture(autouse=True)
    def _clear_caches(self):
        _reset_caches()
        yield
        _reset_caches()

    def _write_endmills(self, path: Path, name: str = "bit_a", diameter: float = 6.35) -> None:
        path.write_text(
            textwrap.dedent(f"""\
            endmills:
              - name: "{name}"
                diameter_mm: {diameter}
                flute_length_mm: 25.4
                shank_diameter_mm: {diameter}
                flutes: 2
                type: upcut_spiral
        """)
        )

    def _write_feeds(self, path: Path, endmill: str = "bit_a", material: str = "mdf") -> None:
        path.write_text(
            textwrap.dedent(f"""\
            feeds:
              - endmill: "{endmill}"
                material: {material}
                chipload: 0.05
                rpm: 18000
                depth_per_pass: 3.0
                plunge_factor: 0.33
        """)
        )

    def test_endmills_cache_hit_avoids_reparse(self, tmp_path):
        yml = tmp_path / "endmills.yml"
        self._write_endmills(yml)
        first = load_endmills(yml)
        second = load_endmills(yml)
        assert first is not second
        assert first == second
        assert all(a is b for a, b in zip(first, second, strict=True))

    def test_feeds_cache_hit_avoids_reparse(self, tmp_path):
        yml = tmp_path / "feeds.yml"
        self._write_feeds(yml)
        first = load_feeds(yml)
        second = load_feeds(yml)
        assert first is not second
        assert first == second
        assert all(a is b for a, b in zip(first, second, strict=True))

    def test_mutating_returned_list_does_not_corrupt_cache(self, tmp_path):
        yml = tmp_path / "endmills.yml"
        self._write_endmills(yml, name="bit_a")
        first = load_endmills(yml)
        first.clear()
        first.append(_endmill("bogus"))
        second = load_endmills(yml)
        assert len(second) == 1
        assert second[0].name == "bit_a"

    def test_endmills_mtime_bump_forces_reparse(self, tmp_path):
        import os

        yml = tmp_path / "endmills.yml"
        self._write_endmills(yml, name="bit_a")
        first = load_endmills(yml)
        assert first[0].name == "bit_a"

        self._write_endmills(yml, name="bit_b")
        stat = yml.stat()
        os.utime(yml, (stat.st_atime, stat.st_mtime + 10.0))
        second = load_endmills(yml)
        assert second[0].name == "bit_b"
        assert second is not first

    def test_feeds_mtime_bump_forces_reparse(self, tmp_path):
        import os

        yml = tmp_path / "feeds.yml"
        self._write_feeds(yml, material="mdf")
        first = load_feeds(yml)
        assert first[0].material == "mdf"

        self._write_feeds(yml, material="plywood")
        stat = yml.stat()
        os.utime(yml, (stat.st_atime, stat.st_mtime + 10.0))
        second = load_feeds(yml)
        assert second[0].material == "plywood"
        assert second is not first

    def test_different_paths_cached_independently(self, tmp_path):
        a = tmp_path / "a.yml"
        b = tmp_path / "b.yml"
        self._write_endmills(a, name="bit_a")
        self._write_endmills(b, name="bit_b")
        loaded_a = load_endmills(a)
        loaded_b = load_endmills(b)
        assert loaded_a[0].name == "bit_a"
        assert loaded_b[0].name == "bit_b"
        assert load_endmills(a)[0] is loaded_a[0]
        assert load_endmills(b)[0] is loaded_b[0]

    def test_reset_caches_forces_reparse(self, tmp_path):
        yml = tmp_path / "endmills.yml"
        self._write_endmills(yml)
        first = load_endmills(yml)
        _reset_caches()
        second = load_endmills(yml)
        assert second == first
        assert second[0] is not first[0]


class TestSheetMaterialValidation:
    def test_valid_material_accepted(self):
        Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="mdf")
        Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="plywood")

    def test_material_is_an_authored_name_validated_by_the_selected_preset(self):
        assert Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="oak").material == "oak"

    def test_material_case_insensitive(self):
        Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="MDF")


class TestMaterialInPML:
    def test_sheet_default_material(self):
        sheet = Sheet(width_mm=100, height_mm=100, thickness_mm=19)
        assert sheet.material == "mdf"

    def test_parse_material_from_pml(self):
        pml = textwrap.dedent("""\
            Sheet:
              width: 450mm
              height: 650mm
              thickness: 19mm
              material: plywood
            children: []
        """)
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        assert ast.sheet.material == "plywood"

    def test_parse_material_default(self):
        pml = textwrap.dedent("""\
            Sheet:
              width: 450mm
              height: 650mm
              thickness: 19mm
            children: []
        """)
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        assert ast.sheet.material == "mdf"


class TestFeedsOverrideParsing:
    def test_parse_feeds_on_feature(self):
        pml = textwrap.dedent("""\
            Sheet:
              width: 450mm
              height: 650mm
              thickness: 19mm
            children:
              - Rect:
                  at:
                    x: 225mm
                    y: 325mm
                    width: 200mm
                    height: 150mm
                  feature:
                    type: pocket
                    depth: 6mm
                    feeds:
                      rpm: 14000
                      feed_xy: 600
                      feed_z: 200
        """)
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        item = ast.items[0]
        assert item.feature is not None
        assert item.feature.feeds_override is not None
        assert item.feature.feeds_override.rpm == 14000
        assert item.feature.feeds_override.feed_xy == 600
        assert item.feature.feeds_override.feed_z == 200
        assert item.feature.feeds_override.depth_per_pass is None

    def test_parse_feeds_on_profile_gen(self):
        pml = textwrap.dedent("""\
            Sheet:
              width: 450mm
              height: 650mm
              thickness: 19mm
            children:
              - Rect:
                  at:
                    x: 225mm
                    y: 325mm
                    width: 200mm
                    height: 150mm
                  children:
                    - Profile:
                        side: outside
                        depth: through
                        feeds:
                          rpm: 12000
        """)
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        profile_items = [i for i in ast.items if i.feature and i.feature.type == "profile"]
        assert len(profile_items) == 1
        item = profile_items[0]
        assert item.feature is not None
        assert item.feature.feeds_override is not None
        assert item.feature.feeds_override.rpm == 12000

    def test_parse_feeds_on_pocket_gen(self):
        pml = textwrap.dedent("""\
            Sheet:
              width: 450mm
              height: 650mm
              thickness: 19mm
            children:
              - Rect:
                  at:
                    x: 225mm
                    y: 325mm
                    width: 200mm
                    height: 150mm
                  children:
                    - Pocket:
                        depth: 6mm
                        feeds:
                          feed_xy: 500
                          depth_per_pass: 2.0
        """)
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        pocket_items = [i for i in ast.items if i.feature and i.feature.type == "pocket"]
        assert len(pocket_items) == 1
        item = pocket_items[0]
        assert item.feature is not None
        assert item.feature.feeds_override is not None
        assert item.feature.feeds_override.feed_xy == 500
        assert item.feature.feeds_override.depth_per_pass == 2.0

    def test_no_feeds_returns_none(self):
        pml = textwrap.dedent("""\
            Sheet:
              width: 450mm
              height: 650mm
              thickness: 19mm
            children:
              - Rect:
                  at:
                    x: 225mm
                    y: 325mm
                    width: 200mm
                    height: 150mm
                  feature:
                    type: pocket
                    depth: 6mm
        """)
        comp_ast = parse_pml_yaml(pml)
        ast = resolve_layout(comp_ast)
        item = ast.items[0]
        assert item.feature is not None
        assert item.feature.feeds_override is None


class TestApplyFeedsOverride:
    def _tool(self):
        return ToolSelection(
            name="test",
            diameter=6.35,
            kind="flat",
            rpm=18000,
            feed_xy=1800,
            feed_z=594,
            depth_per_pass=3.0,
        )

    def test_none_override_returns_same(self):
        tool = self._tool()
        result = apply_feeds_override(tool, None)
        assert result is tool

    def test_partial_override(self):
        tool = self._tool()
        override = FeedsOverride(rpm=14000)
        result = apply_feeds_override(tool, override)
        assert result.rpm == 14000
        assert result.feed_xy == 1800
        assert result.feed_z == 594

    def test_full_override(self):
        tool = self._tool()
        override = FeedsOverride(
            rpm=14000,
            feed_xy=600,
            feed_z=200,
            depth_per_pass=2.0,
            stepover_percent=30.0,
        )
        result = apply_feeds_override(tool, override)
        assert result.rpm == 14000
        assert result.feed_xy == 600
        assert result.feed_z == 200
        assert result.depth_per_pass == 2.0
        assert result.stepover_percent == 30.0

    def test_empty_override_returns_same(self):
        tool = self._tool()
        override = FeedsOverride()
        result = apply_feeds_override(tool, override)
        assert result is tool

    def test_override_preserves_other_fields(self):
        tool = ToolSelection(
            name="test",
            diameter=6.35,
            kind="flat",
            rpm=18000,
            feed_xy=1800,
            feed_z=594,
            rotation="upcut",
            v_angle_deg=None,
        )
        override = FeedsOverride(rpm=14000)
        result = apply_feeds_override(tool, override)
        assert result.rotation == "upcut"
        assert result.name == "test"
        assert result.diameter == 6.35


class TestFeedsOverrideIRFlow:
    def test_profile_feeds_override_flows_to_removal_intent(self):
        from adapters.ast_to_removal import item_to_removal_intent
        from layout_ast.layout import Feature, Geometry, Item, Placement

        item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(
                type="profile",
                depth_mm=19.0,
                side="outside",
                is_through=True,
                feeds_override=FeedsOverride(rpm=14000, feed_xy=600),
            ),
            shape_id="test_profile",
        )
        intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
        assert intent.feeds_override is not None
        assert intent.feeds_override.rpm == 14000
        assert intent.feeds_override.feed_xy == 600

    def test_pocket_feeds_override_flows_to_removal_intent(self):
        from adapters.ast_to_removal import item_to_removal_intent
        from layout_ast.layout import Feature, Geometry, Item, Placement

        item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(
                type="pocket",
                depth_mm=6.0,
                feeds_override=FeedsOverride(depth_per_pass=2.0),
            ),
            shape_id="test_pocket",
        )
        intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
        assert intent.feeds_override is not None
        assert intent.feeds_override.depth_per_pass == 2.0

    def test_hole_feeds_override_flows_to_removal_intent(self):
        from adapters.ast_to_removal import item_to_removal_intent
        from layout_ast.layout import Feature, Geometry, Item, Placement

        item = Item(
            kind="shape",
            type="Circle",
            geometry=Geometry(data={"diameter_mm": 10}),
            placement=Placement(center_xy_mm=(100, 100)),
            feature=Feature(
                type="hole",
                depth_mm=19.0,
                is_through=True,
                feeds_override=FeedsOverride(rpm=12000, feed_z=150),
            ),
            shape_id="test_hole",
        )
        intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
        assert intent.feeds_override is not None
        assert intent.feeds_override.rpm == 12000
        assert intent.feeds_override.feed_z == 150

    def test_engrave_feeds_override_flows_to_removal_intent(self):
        from adapters.ast_to_removal import item_to_removal_intent
        from layout_ast.layout import Feature, Geometry, Item, Placement

        item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
            placement=Placement(center_xy_mm=(200, 200)),
            feature=Feature(
                type="engrave",
                depth_mm=0.3,
                feeds_override=FeedsOverride(feed_xy=400),
            ),
            shape_id="test_engrave",
        )
        intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
        assert intent.feeds_override is not None
        assert intent.feeds_override.feed_xy == 400

    def test_no_feeds_override_leaves_none_on_intent(self):
        from adapters.ast_to_removal import item_to_removal_intent
        from layout_ast.layout import Feature, Geometry, Item, Placement

        item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", depth_mm=19.0, side="outside", is_through=True),
            shape_id="test_no_override",
        )
        intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
        assert intent.feeds_override is None


class TestPipelineWithFeeds:
    def test_pipeline_with_endmills_and_feeds(self):
        from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement

        ast = LayoutAST(
            sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
                    placement=Placement(center_xy_mm=(225, 325)),
                    feature=Feature(type="profile", depth_mm=19.0, side="outside", is_through=True),
                    shape_id="test_rect",
                ),
            ),
        )

        endmills = [_endmill("test_flat_6", diameter=6.35, flutes=2, type_="upcut_spiral")]
        feeds = [_feeds_entry(endmill="test_flat_6", material="mdf", chipload=0.05, rpm=18000, dpp=3.0, pf=0.33)]

        result = run_pipeline(ast, kerf_mm=6.35, endmills=endmills, feeds=feeds)
        assert not result.errors
        assert len(result.passes) > 0

    def test_pipeline_loads_machine_library(self):
        from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement

        ast = LayoutAST(
            sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
                    placement=Placement(center_xy_mm=(225, 325)),
                    feature=Feature(type="profile", depth_mm=19.0, side="outside", is_through=True),
                    shape_id="test_rect",
                ),
            ),
        )

        result = run_pipeline(ast, kerf_mm=6.35)
        assert not result.errors
        assert len(result.passes) > 0
        tool = result.passes[0].setup.tool
        assert tool.feed_xy == 3600.0

    def test_pipeline_unknown_material_raises(self):
        from cam.compilation import compilation_context

        with pytest.raises(ValueError, match=r"material 'oak'.*unsupported material"):
            compilation_context("oak")


@pytest.fixture
def preset_inputs(tmp_path):
    from config.machine_loader import load_machine_by_name

    settings = {"rpm": 18000, "feed_xy": 1200, "feed_z": 300, "depth_per_pass": 2, "stepover_percent": 40}
    cutters = [
        Endmill(name, diameter, 25, diameter, 2, kind, v_angle_deg=angle)
        for name, diameter, kind, angle in [
            ("profile", 6, "straight", None),
            ("pcd", 6, "straight", None),
            ("small", 3, "straight", None),
            ("v60", 12, "v_bit", 60),
            ("v90", 12, "v_bit", 90),
        ]
    ]
    data = {
        "name": "test",
        "materials": {
            "mdf": {
                "roles": {
                    "profile": ["profile"],
                    "pocket": ["pcd", "small"],
                    "surface": ["profile"],
                    "vcarve": ["v90", "v60"],
                    "hole": ["small"],
                    "engrave": ["v60"],
                    "specialty": ["small"],
                },
                "parameters": {
                    role: {name: dict(settings, feed_xy=feed) for name, feed in names}
                    for role, names in {
                        "profile": [("profile", 4500), ("small", 900)],
                        "pocket": [("pcd", 2520), ("profile", 1500), ("small", 900)],
                        "hole": [("small", 800)],
                        "surface": [("profile", 2000)],
                        "vcarve": [("v90", 600), ("v60", 500)],
                        "engrave": [("v60", 400)],
                        "specialty": [("small", 900)],
                    }.items()
                },
            }
        },
    }
    path = tmp_path / "preset.yml"
    machine = replace(load_machine_by_name("test_router"), cutting_preset="test")
    return path, data, cutters, machine


def _test_preset_context(inputs, *, material="mdf", machining=None, machine=None):
    from ruamel.yaml import YAML

    from cam.compilation import compilation_context

    path, data, cutters, configured_machine = inputs
    with path.open("w") as handle:
        YAML().dump(data, handle)
    return compilation_context(
        material, endmills=cutters, machine_config=machine or configured_machine, machining=machining, preset_path=path
    )


def test_preset_identity_and_material_are_independent_of_inventory_order(preset_inputs):
    from cam.planner.passes.tools import tools_for_role

    path, data, cutters, machine = preset_inputs
    data["materials"]["plywood"] = {
        "roles": {"profile": ["profile"], "pocket": ["profile"]},
        "parameters": data["materials"]["mdf"]["parameters"],
    }
    mdf = _test_preset_context((path, data, list(reversed(cutters)), machine))
    plywood = _test_preset_context(preset_inputs, material="plywood")
    assert tools_for_role(mdf.tools, "profile")[0].name == "profile"
    assert tools_for_role(mdf.tools, "pocket")[0].name == "pcd"
    assert tools_for_role(plywood.tools, "pocket")[0].name == "profile"
    assert tools_for_role(plywood.tools, "pocket")[0].feed_xy == 1500


def test_job_and_operation_tools_reresolve_parameters_and_precedence(preset_inputs):
    from cam.planner.passes.tools import tools_for_role
    from layout_ast.layout import MachiningSpec

    context = _test_preset_context(
        preset_inputs, machining=MachiningSpec(tools={"pocket": "profile"}, feeds=FeedsOverride(feed_z=200))
    )
    job = tools_for_role(context.tools, "pocket")[0]
    operation = apply_feeds_override(tools_for_role(context.tools, "pocket", "small")[0], FeedsOverride(feed_z=100))
    assert (job.name, job.feed_xy, job.feed_z) == ("profile", 1500, 200)
    assert (operation.name, operation.feed_xy, operation.feed_z) == ("small", 900, 100)
    assert tools_for_role(context.tools, "surface")[0].feed_xy == 2000


def test_approved_alternatives_are_ordered_and_explicit_pocket_is_binding(preset_inputs):
    from cam.planner.passes.tools import pick_tool_for_pocket, tools_for_role

    context = _test_preset_context(preset_inputs)
    approved = tools_for_role(context.tools, "pocket")
    assert pick_tool_for_pocket(approved, required_width_mm=5, cleanup_offset_mm=0).name == "small"
    explicit = tools_for_role(context.tools, "pocket", "pcd")
    with pytest.raises(ValueError, match=r"infeasible.*pcd"):
        pick_tool_for_pocket(explicit, required_width_mm=5, cleanup_offset_mm=0)


@pytest.mark.parametrize(
    "role,tool,error",
    [
        ("pocket", "unknown", "unknown/unavailable"),
        ("pocket", "v90", "missing cutting parameters"),
        ("vcarve", "v60", "required included angle"),
    ],
)
def test_explicit_tools_fail_with_context(preset_inputs, role, tool, error):
    from cam.planner.passes.tools import pick_tool_for_edge, tools_for_role

    context = _test_preset_context(preset_inputs)
    with pytest.raises(ValueError, match=error):
        selected = tools_for_role(context.tools, role, tool)
        pick_tool_for_edge(selected, angle_deg=90)


def test_incompatible_tool_and_missing_feeds_are_actionable(preset_inputs):
    from cam.planner.passes.tools import tools_for_role

    _, data, _, _ = preset_inputs
    parameters = data["materials"]["mdf"]["parameters"]
    parameters["pocket"]["v90"] = dict(parameters["vcarve"]["v90"])
    context = _test_preset_context(preset_inputs)
    with pytest.raises(ValueError, match=r"machine.*preset.*material.*role pocket.*v90.*incompatible"):
        tools_for_role(context.tools, "pocket", "v90")
    del parameters["pocket"]["pcd"]
    context = _test_preset_context(preset_inputs)
    with pytest.raises(ValueError, match=r"machine.*preset.*material.*role pocket.*pcd.*missing cutting"):
        tools_for_role(context.tools, "pocket")


def test_shared_preset_respects_each_machine_limits_after_overrides(preset_inputs):
    from cam.planner.passes.tools import tools_for_role
    from layout_ast.layout import MachiningSpec

    _, _, _, machine = preset_inputs
    second = replace(
        machine, machine=replace(machine.machine, name="Second test router"), capabilities={"max_feed_xy": 1000}
    )
    first = _test_preset_context(preset_inputs)
    context = _test_preset_context(
        preset_inputs, machine=second, machining=MachiningSpec(feeds=FeedsOverride(feed_xy=1500))
    )
    assert first.preset == context.preset
    selected = tools_for_role(context.tools, "pocket")[0]
    with pytest.raises(ValueError, match=r"Second test router.*max_feed_xy.*1000.*1500"):
        selected.validate_cut()
    assert apply_feeds_override(selected, FeedsOverride(feed_xy=800)).feed_xy == 800


def test_tool_reach_and_shank_limits_are_binding(preset_inputs):
    from cam.planner.passes.tools import tools_for_role

    _, _, _, machine = preset_inputs
    context = _test_preset_context(preset_inputs, machine=replace(machine, capabilities={"max_shank_mm": 4}))
    with pytest.raises(ValueError, match="required reach 30mm exceeds flute length 25mm"):
        tools_for_role(context.tools, "pocket", "pcd", 30)
    with pytest.raises(ValueError, match=r"max_shank_mm.*4.*6"):
        tools_for_role(context.tools, "pocket", "pcd")[0].validate_cut()


def test_editing_preset_is_observed_by_next_source_build(preset_inputs, tmp_path):
    from cam.compilation import load_pml_asts
    from validation.runner import resolve_validation_source

    path, data, cutters, machine = preset_inputs
    source = tmp_path / "part.pml.yml"
    source.write_text("Sheet: {width: 200mm, height: 200mm, thickness: 12mm}\nchildren: []\n")
    _test_preset_context(preset_inputs)
    _, first = load_pml_asts(source, machine_config=machine, endmills=cutters, preset_path=path)
    data["materials"]["mdf"]["parameters"]["pocket"]["pcd"]["feed_xy"] = 1111
    _test_preset_context(preset_inputs)
    output = tmp_path / "output"
    output.mkdir()
    (output / "metrics.json").write_text('{"build":{"compilation_contexts":{"part.pml.yml":{"tools":"stale"}}}}')
    asts, second = load_pml_asts(source, machine_config=machine, endmills=cutters, preset_path=path)
    assert resolve_validation_source(source, machine_config=machine, endmills=cutters, preset_path=path) == asts
    from cam.planner.passes.tools import tools_for_role

    assert tools_for_role(first.tools, "pocket")[0].feed_xy == 2520
    assert tools_for_role(second.tools, "pocket")[0].feed_xy == 1111


@pytest.mark.parametrize(
    "settings",
    [
        "machining: {tools: {pockte: small}}",
        "machining: {tools: {pocket: 3}}",
        "machining: {feed: {feed_xy: 1}}",
        "machining: {feeds: {feed_xy: .nan}}",
    ],
)
def test_machining_schema_is_strict(settings):
    with pytest.raises(Exception, match=r"machining|feeds"):
        parse_pml_yaml(settings + "\nSheet: {width: 200mm, height: 200mm, thickness: 12mm}\nchildren: []\n")


def test_named_operation_tools_and_job_settings_survive_source_formatting_and_ir():
    from pml.yaml_formatter import format_pml_yaml

    source = """machining:
  tools: {pocket: 'test_flat_6'}
  feeds: {feed_z: 250}
Sheet: {width: 200mm, height: 200mm, thickness: 12mm}
children:
- Rect:
    at: {x: 100mm, y: 100mm, width: 100mm, height: 100mm}
    children:
    - Pocket: {depth: 3mm, tool: 'test_detail', feeds: {feed_xy: 1000}}
"""
    parsed = parse_pml_yaml(source)
    assert parse_pml_yaml(format_pml_yaml(parsed)) == parsed
    (intent,) = ast_to_removal_intents(resolve_layout(parsed))
    assert intent.tool_name == "test_detail"
    assert intent.feeds_override is not None
    assert intent.feeds_override.feed_xy == 1000


def test_conflicting_profile_overrides_fail_before_packing(tmp_path):
    from cam.compilation import load_pml_asts

    source = tmp_path / "conflict.pml.yml"
    source.write_text("""Sheet: {width: 200mm, height: 200mm, thickness: 12mm}
children:
- Rect:
    children:
    - Profile: {side: outside, tool: 'test_flat_6'}
    - Profile: {side: outside, tool: 'test_detail'}
""")
    with pytest.raises(ValueError, match="Conflicting operation-level profile tools"):
        load_pml_asts(source)


def test_surface_parameters_use_preset_then_operation_settings(preset_inputs):
    from cam.compilation import load_pml_asts, plan_face_passes, prepare_face_input
    from cam.model.stock import Stock
    from cam.moves import CutMove

    path, _, cutters, machine = preset_inputs
    _test_preset_context(preset_inputs)
    source = path.parent / "surface.pml.yml"
    source.write_text("""Sheet: {width: 100mm, height: 100mm, thickness: 12mm}
Surface:
  depth-per-pass: 3mm
  tool: profile
  feeds: {depth_per_pass: 1, feed_xy: 500}
children: []
""")
    (ast,), context = load_pml_asts(source, machine_config=machine, endmills=cutters, preset_path=path)
    assert context is not None
    planner = prepare_face_input(ast, ast_to_removal_intents(ast), kerf_mm=6)
    passes, _, _, errors = plan_face_passes(
        planner, tools=context.tools, machine=context.machine(), stock=Stock(100, 100, 12), safe_z=3
    )
    assert not errors
    (record,) = passes
    assert record.tool_selection.stepover_percent == 40
    assert record.tool_selection.depth_per_pass == 1
    assert record.tool_selection.feed_xy == 500
    assert {m.z for m in record.moves if isinstance(m, CutMove) and m.z is not None and m.z < 0} == {-1, -2, -3}


def test_machine_switch_uses_explicit_independent_preset_inputs(preset_inputs):
    from cam.planner.passes.tools import tools_for_role
    from config.machine_loader import load_machine_by_name

    path, data, cutters, _ = preset_inputs
    first = _test_preset_context(preset_inputs)
    data["materials"]["mdf"]["roles"]["pocket"] = ["small"]
    data["materials"]["mdf"]["parameters"]["pocket"]["small"]["feed_xy"] = 400
    machine = replace(
        load_machine_by_name("test_router"),
        machine=replace(
            load_machine_by_name("test_router").machine,
            name="Small test router",
            envelope_x_max=400,
            envelope_y_max=400,
        ),
        cutting_preset="small_test_cutting",
    )
    second = _test_preset_context((path, data, cutters, machine))
    assert tools_for_role(first.tools, "pocket")[0].name == "pcd"
    assert tools_for_role(second.tools, "pocket")[0].name == "small"
    assert tools_for_role(second.tools, "pocket")[0].feed_xy == 400
    assert second.machine_config.machine.envelope_width < first.machine_config.machine.envelope_width


def test_normalization_does_not_invent_missing_cutting_feeds():
    with pytest.raises(ValueError, match="missing required cutting parameter rpm"):
        normalize_tool_entries([{"name": "unconfigured", "diameter": 6, "kind": "flat"}])


def test_profile_reach_is_resolved_before_packing_with_binding_overrides(tmp_path):
    from cam.compilation import load_pml_asts

    source = tmp_path / "deep.pml.yml"
    source.write_text("""Sheet: {width: 800mm, height: 800mm, thickness: 30mm, margin: 10mm}
children:
- Assembly:
    type: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 30mm
    joinery: butt
    bottom: none
    top: none
    layout_gap: 30mm
""")
    (ast,), context = load_pml_asts(source)
    assert ast.machining_clearance is not None
    assert ast.machining_clearance.profile_diameter_mm == 12.7
    assert context.profile_tool().name == "test_long_flat"
    source.write_text("machining: {tools: {profile: 'test_profile'}}\n" + source.read_text())
    with pytest.raises(ValueError, match=r"required reach 30\.2mm exceeds flute length 25\.4mm"):
        load_pml_asts(source)


def test_unused_profile_role_is_not_required_for_pocket_only_jobs(preset_inputs):
    from cam.planner.passes.tools import tools_for_role

    _, data, _, _ = preset_inputs
    del data["materials"]["mdf"]["roles"]["profile"]
    context = _test_preset_context(preset_inputs)
    assert context.profile_diameter_mm is None
    assert tools_for_role(context.tools, "pocket")[0].name == "pcd"
    with pytest.raises(ValueError, match="role profile: packing requires"):
        context.clearance()


def test_profile_and_vcarve_roles_work_without_matching_specialty_tools(preset_inputs):
    _, data, _, _ = preset_inputs
    material = data["materials"]["mdf"]
    material["parameters"]["specialty"] = {"v90": material["parameters"]["vcarve"]["v90"]}
    material["roles"]["specialty"] = ["v90"]
    context = _test_preset_context(preset_inputs)
    assert context.clearance().profile_diameter_mm == 6
    ast = resolve_layout(
        parse_pml_yaml("""Sheet: {width: 200mm, height: 200mm, thickness: 12mm}
children:
- Rect:
    at: {x: 100mm, y: 100mm, width: 100mm, height: 100mm}
    children:
    - Chamfer: {width: 1mm, depth: 1.7320508075688772mm}
""")
    )
    result = run_pipeline(ast, context=context)
    assert not result.errors
    assert result.svg and result.gcode
    assert {record.tool_selection.name for record in result.passes} == {"v60"}


@pytest.mark.parametrize("role", ["profile", "pocket", "hole"])
def test_legacy_feeds_with_multiple_cutters_require_a_named_role_independent_of_order(role):
    from cam.compilation import compilation_context
    from cam.planner.passes.tools import tools_for_role
    from layout_ast.layout import MachiningSpec

    cutters = [_endmill("large", diameter=6), _endmill("small", diameter=3)]
    feeds = [_feeds_entry(endmill=tool.name) for tool in cutters]
    for ordered in (cutters, list(reversed(cutters))):
        context = compilation_context("mdf", endmills=ordered, feeds=feeds)
        with pytest.raises(ValueError, match=f"role {role}: no configured cutter assignment"):
            tools_for_role(context.tools, role)
        explicit = compilation_context(
            "mdf", endmills=ordered, feeds=feeds, machining=MachiningSpec(tools={role: "small"})
        )
        assert [tool.name for tool in tools_for_role(explicit.tools, role)] == ["small"]


def test_explicit_configuration_root_never_falls_back_to_production(tmp_path, monkeypatch):
    from cam.compilation import default_machine_name

    missing = tmp_path / "unconfigured"
    monkeypatch.setenv("MILL_UI_MACHINES_DIR", str(missing))
    with pytest.raises(FileNotFoundError, match=r"unconfigured/defaults\.yml"):
        default_machine_name()


def test_fresh_configuration_root_reresolves_settings_without_previous_test_state(tmp_path, monkeypatch):
    from ruamel.yaml import YAML

    from cam.compilation import compilation_context
    from cam.planner.passes.tools import tools_for_role
    from tests.machining_fixtures import write_machining_configuration

    first = write_machining_configuration(tmp_path / "first")
    preset = first / "cutting_presets/test_cutting.yml"
    yaml = YAML(typ="safe")
    data = yaml.load(preset.read_text())
    data["materials"]["mdf"]["parameters"]["pocket"]["test_pocket"]["feed_xy"] = 321
    with preset.open("w") as handle:
        yaml.dump(data, handle)
    monkeypatch.setenv("MILL_UI_MACHINES_DIR", str(first))
    assert tools_for_role(compilation_context("mdf").tools, "pocket")[0].feed_xy == 321
    second = write_machining_configuration(tmp_path / "second")
    monkeypatch.setenv("MILL_UI_MACHINES_DIR", str(second))
    assert tools_for_role(compilation_context("mdf").tools, "pocket")[0].feed_xy == 1800
