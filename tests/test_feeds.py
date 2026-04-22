from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cam.pipeline import run_pipeline
from cam.planner.passes.tools import ToolSelection, apply_feeds_override
from config.machine_loader import (
    Endmill,
    FeedsEntry,
    _reset_caches,
    build_tool_db,
    load_endmills,
    load_feeds,
    load_machine_tool_db,
    resolve_tool_selection,
)
from layout_ast.layout import FeedsOverride, Sheet
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def _endmill(name="1/4 upcut spiral", diameter=6.35, flutes=2, type_="upcut_spiral", v_angle=None):
    return Endmill(
        name=name,
        diameter_mm=diameter,
        flute_length_mm=25.4,
        shank_diameter_mm=diameter,
        flutes=flutes,
        type=type_,
        v_angle_deg=v_angle,
    )


def _feeds_entry(endmill="1/4 upcut spiral", material="mdf", chipload=0.05, rpm=18000, dpp=3.0, pf=0.33):
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
        assert entry.endmill == "1/4 upcut spiral"
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

    def test_plywood_tools_resolve(self):
        endmills = load_endmills("machines/endmills.yml")
        feeds = load_feeds("machines/feeds.yml")
        result = build_tool_db(endmills, feeds, "plywood")
        assert len(result) == 6


class TestLoadFeeds:
    def test_load_feeds_yml(self, tmp_path):
        yml = tmp_path / "feeds.yml"
        yml.write_text(
            textwrap.dedent("""\
            feeds:
              - endmill: "1/4 upcut spiral"
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
        assert entries[0].endmill == "1/4 upcut spiral"
        assert entries[0].stepover_percent == 40.0

    def test_load_real_feeds_yml(self):
        feeds_path = Path("machines/feeds.yml")
        if not feeds_path.exists():
            pytest.skip("machines/feeds.yml not present")
        entries = load_feeds(feeds_path)
        assert len(entries) > 0
        for entry in entries:
            assert entry.chipload > 0
            assert entry.rpm > 0


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

    def test_endmills_cache_hit_returns_same_instance(self, tmp_path):
        yml = tmp_path / "endmills.yml"
        self._write_endmills(yml)
        first = load_endmills(yml)
        second = load_endmills(yml)
        assert first is second

    def test_feeds_cache_hit_returns_same_instance(self, tmp_path):
        yml = tmp_path / "feeds.yml"
        self._write_feeds(yml)
        first = load_feeds(yml)
        second = load_feeds(yml)
        assert first is second

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
        assert load_endmills(a) is loaded_a
        assert load_endmills(b) is loaded_b

    def test_reset_caches_forces_reparse(self, tmp_path):
        yml = tmp_path / "endmills.yml"
        self._write_endmills(yml)
        first = load_endmills(yml)
        _reset_caches()
        second = load_endmills(yml)
        assert second is not first
        assert second == first

    def test_machine_tool_db_correct_across_materials(self):
        mdf_tools = load_machine_tool_db("mdf")
        plywood_tools = load_machine_tool_db("plywood")
        assert len(mdf_tools) > 0
        assert len(plywood_tools) > 0
        mdf_again = load_machine_tool_db("mdf")
        assert {t["name"] for t in mdf_tools} == {t["name"] for t in mdf_again}
        for tool in mdf_tools:
            assert "rpm" in tool and "feed_xy" in tool


class TestAvailableMaterials:
    def test_returns_materials_from_feeds(self):
        from config.machine_loader import available_materials

        feeds = [
            _feeds_entry(endmill="bit_a", material="mdf"),
            _feeds_entry(endmill="bit_b", material="plywood"),
        ]
        result = available_materials(feeds)
        assert result == frozenset({"mdf", "plywood"})

    def test_case_normalized(self):
        from config.machine_loader import available_materials

        feeds = [_feeds_entry(endmill="bit_a", material="MDF")]
        result = available_materials(feeds)
        assert "mdf" in result

    def test_loads_real_feeds_yml(self):
        from config.machine_loader import available_materials

        result = available_materials()
        assert "mdf" in result
        assert "plywood" in result


class TestSheetMaterialValidation:
    def test_valid_material_accepted(self):
        Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="mdf")
        Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="plywood")

    def test_invalid_material_raises(self):
        with pytest.raises(ValueError, match="Unknown material 'oak'"):
            Sheet(width_mm=100, height_mm=100, thickness_mm=19, material="oak")

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

        endmills = [_endmill("1/4 upcut spiral", diameter=6.35, flutes=2, type_="upcut_spiral")]
        feeds = [_feeds_entry(endmill="1/4 upcut spiral", material="mdf", chipload=0.05, rpm=18000, dpp=3.0, pf=0.33)]

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
        assert tool.feed_xy == 1800.0

    def test_pipeline_unknown_material_raises(self):
        with pytest.raises(ValueError, match="Unknown material 'oak'"):
            Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0, material="oak")
