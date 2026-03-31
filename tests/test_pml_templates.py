import pytest

from layout_ast.compositional import TemplateDef
from pml.yaml_parser import (
    PMLParseError as ParseError,
)
from pml.yaml_parser import (
    parse_template_yaml,
    substitute_params,
)
from templates.loader import (
    clear_template_cache,
    expand_template,
    find_template_file,
    load_pml_template,
)


class TestParseTemplateDef:
    def test_parse_simple_template(self):
        text = """
Template:
  name: test
  params:
    my_width: 100mm
    my_depth: 5mm

children:
  - Rect:
      id: panel
      children:
        - Pocket:
            depth: ${my_depth}
"""
        result = parse_template_yaml(text)
        assert isinstance(result, TemplateDef)
        assert result.name == "test"
        assert result.params == {"my_width": 100.0, "my_depth": 5.0}
        assert result.body is None

    def test_parse_template_without_params(self):
        text = """
Template:
  name: simple

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
"""
        result = parse_template_yaml(text)
        assert result.name == "simple"
        assert result.params == {}
        assert result.body is None

    def test_parse_shaker_template(self):
        text = """
Template:
  name: shaker
  params:
    stile_w: 57mm
    rail_h: 57mm
    panel_recess: 6mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: ${stile_w}
            children:
              - Pocket:
                  depth: ${panel_recess}
"""
        result = parse_template_yaml(text)
        assert result.name == "shaker"
        assert result.params == {
            "stile_w": 57.0,
            "rail_h": 57.0,
            "panel_recess": 6.0,
        }
        assert result.body is None


class TestParameterSubstitution:
    def test_substitute_single_param(self):
        text = "width: ${width}"
        result = substitute_params(text, {"width": 50.0})
        assert result == "width: 50.0mm"

    def test_substitute_multiple_params(self):
        text = "width: ${width}\ndepth: ${depth}"
        result = substitute_params(text, {"width": 50.0, "depth": 6.0})
        assert result == "width: 50.0mm\ndepth: 6.0mm"

    def test_substitute_same_param_twice(self):
        text = "${size} ${size}"
        result = substitute_params(text, {"size": 100.0})
        assert result == "100.0mm 100.0mm"

    def test_unknown_param_raises(self):
        text = "width: ${unknown}"
        with pytest.raises(ParseError) as exc_info:
            substitute_params(text, {"width": 50.0})
        assert "Unknown parameter" in str(exc_info.value)

    def test_substitute_string_param(self):
        text = "${style}: ${depth}"
        result = substitute_params(text, {"style": "pocket", "depth": 6.0})
        assert result == "pocket: 6.0mm"

    def test_substitute_string_param_keyword(self):
        text = "width: 50mm\ntype: ${generator}"
        result = substitute_params(text, {"generator": "concentric_border"})
        assert result == "width: 50mm\ntype: concentric_border"


class TestStringParameters:
    def test_parse_template_with_string_param(self):
        text = """
Template:
  name: test
  params:
    width: 100mm
    style: pocket

children:
  - Rect:
      id: panel
"""
        result = parse_template_yaml(text)
        assert result.params == {"width": 100.0, "style": "pocket"}

    def test_parse_template_with_keyword_string_param(self):
        text = """
Template:
  name: test
  params:
    depth: 6mm
    generator: concentric_border

children:
  - Rect:
      id: panel
"""
        result = parse_template_yaml(text)
        assert result.params == {"depth": 6.0, "generator": "concentric_border"}


class TestTemplateLoader:
    def setup_method(self):
        clear_template_cache()

    def test_find_template_file_shaker(self):
        path = find_template_file("shaker")
        assert path is not None
        assert path.name == "shaker.pml.yml"
        assert path.exists()

    def test_find_template_file_case_insensitive(self):
        path = find_template_file("Shaker")
        assert path is not None
        assert path.name == "shaker.pml.yml"

    def test_find_template_file_nonexistent(self):
        path = find_template_file("nonexistent")
        assert path is None

    def test_load_pml_template_shaker(self):
        template_def, _raw_text = load_pml_template("shaker")
        assert template_def.name == "shaker"
        assert "stile_w" in template_def.params
        assert "rail_h" in template_def.params
        assert "panel_recess" in template_def.params

    def test_load_pml_template_caches(self):
        clear_template_cache()
        result1 = load_pml_template("shaker")
        result2 = load_pml_template("shaker")
        assert result1[0].name == result2[0].name
        assert result1[0].params == result2[0].params


class TestExpandTemplate:
    def setup_method(self):
        clear_template_cache()

    def test_expand_shaker_basic(self):
        items = expand_template(
            template_name="shaker",
            params={},
            region_width=400.0,
            region_height=600.0,
            sheet_thickness=19.0,
        )
        assert len(items) >= 2

        profile_items = [i for i in items if i.feature and i.feature.type == "profile"]
        assert len(profile_items) >= 1

        pocket_items = [i for i in items if i.feature and i.feature.type == "pocket"]
        assert len(pocket_items) >= 1

    def test_expand_shaker_with_overrides(self):
        items = expand_template(
            template_name="shaker",
            params={"stile_w": 100.0, "panel_recess": 10.0},
            region_width=500.0,
            region_height=700.0,
            sheet_thickness=19.0,
        )
        assert len(items) >= 2

        pocket_item = next(i for i in items if i.feature and i.feature.type == "pocket")
        assert pocket_item.feature is not None
        assert pocket_item.feature.depth_mm == 10.0

    def test_expand_template_nonexistent_raises(self):
        with pytest.raises(ValueError) as exc_info:
            expand_template(
                template_name="nonexistent",
                params={},
                region_width=100.0,
                region_height=100.0,
                sheet_thickness=19.0,
            )
        assert "Template not found" in str(exc_info.value)


class TestShakerTemplate:
    def setup_method(self):
        clear_template_cache()

    def test_shaker_produces_profile_and_pocket(self):
        items = expand_template(
            template_name="shaker",
            params={},
            region_width=400.0,
            region_height=600.0,
            sheet_thickness=19.0,
        )

        feature_types = {i.feature.type for i in items if i.feature}
        assert "profile" in feature_types
        assert "pocket" in feature_types

    def test_shaker_geometry_centered(self):
        items = expand_template(
            template_name="shaker",
            params={"stile_w": 50.0},
            region_width=400.0,
            region_height=600.0,
            sheet_thickness=19.0,
        )

        profile_item = next(i for i in items if i.feature and i.feature.type == "profile")
        assert profile_item.placement is not None
        cx, cy = profile_item.placement.center_xy_mm
        assert cx == pytest.approx(200.0, rel=0.01)
        assert cy == pytest.approx(300.0, rel=0.01)

    def test_shaker_pocket_inset_correct(self):
        stile_w = 50.0
        items = expand_template(
            template_name="shaker",
            params={"stile_w": stile_w},
            region_width=400.0,
            region_height=600.0,
            sheet_thickness=19.0,
        )

        pocket_item = next(i for i in items if i.feature and i.feature.type == "pocket")
        assert pocket_item.geometry is not None
        pocket_w = pocket_item.geometry.data.get("w_mm")
        pocket_h = pocket_item.geometry.data.get("h_mm")

        expected_pocket_w = 400.0 - 2 * stile_w
        expected_pocket_h = 600.0 - 2 * stile_w

        assert pocket_w == pytest.approx(expected_pocket_w, rel=0.01)
        assert pocket_h == pytest.approx(expected_pocket_h, rel=0.01)
