from __future__ import annotations

import pytest

from domains.domain import Domain
from generators.area.concentric_border import concentric_border_generator
from generators.core import GeneratorSkipError, require_single_inset_domain, validate_domain_for_generation
from generators.params.area import ConcentricBorderParams
from generators.svg.params import SVGPathParams
from generators.svg.stamp import svg_stamp_generator
from generators.utils import extract_loops
from layout_ast.compositional import (
    ChamferGen,
    CompositionalLayoutAST,
    PocketGen,
    ProfileGen,
    ResolvedRegion,
    RoundoverGen,
    ShellGen,
)
from layout_ast.layout import Sheet
from resolution.layout_resolver import LayoutResolver


def _make_resolver(width: float = 200.0, height: float = 200.0, thickness: float = 19.0) -> LayoutResolver:
    sheet = Sheet(width_mm=width, height_mm=height, thickness_mm=thickness)
    ast = CompositionalLayoutAST(sheet=sheet)
    return LayoutResolver(ast)


def _make_region(w: float = 100.0, h: float = 100.0) -> ResolvedRegion:
    return ResolvedRegion(x_min=0.0, y_min=0.0, x_max=w, y_max=h)


def _make_domain(w: float = 100.0, h: float = 100.0) -> Domain:
    return Domain.from_rectangle(w, h, center=(w / 2, h / 2))


class TestValidateDomainForGeneration:
    def test_returns_false_when_allow_empty_and_area_too_small(self) -> None:
        tiny = Domain.from_rectangle(0.001, 0.001)
        assert validate_domain_for_generation(tiny, allow_empty=True) is False

    def test_raises_when_not_allow_empty_and_area_too_small(self) -> None:
        tiny = Domain.from_rectangle(0.001, 0.001)
        with pytest.raises(GeneratorSkipError, match="below minimum"):
            validate_domain_for_generation(tiny, allow_empty=False)

    def test_returns_true_for_adequate_domain(self) -> None:
        d = _make_domain()
        assert validate_domain_for_generation(d, allow_empty=True) is True


class TestRequireSingleInsetDomain:
    def test_returns_none_when_empty_and_allow_empty(self) -> None:
        d = _make_domain(2.0, 2.0)
        result = d.inset(10.0)
        assert result.is_empty
        assert require_single_inset_domain(result, allow_empty=True, generator_name="test") is None

    def test_raises_when_empty_and_not_allow_empty(self) -> None:
        d = _make_domain(2.0, 2.0)
        result = d.inset(10.0)
        with pytest.raises(GeneratorSkipError, match="collapsed domain"):
            require_single_inset_domain(result, allow_empty=False, generator_name="test")

    def test_returns_domain_for_single_result(self) -> None:
        d = _make_domain(100.0, 100.0)
        result = d.inset(5.0)
        inset_domain = require_single_inset_domain(result, allow_empty=True, generator_name="test")
        assert inset_domain is not None
        assert inset_domain.area_mm2 > 0


class TestConcentricBorderGeneratorSkip:
    def test_returns_empty_when_inset_exceeds_domain_and_allow_empty(self) -> None:
        d = _make_domain(10.0, 10.0)
        params = ConcentricBorderParams(insets_mm=(100.0,), groove_width_mm=2.0, depth_mm=3.0)
        result = concentric_border_generator(d, params, allow_empty=True)
        assert result == []

    def test_raises_when_inset_exceeds_domain_and_not_allow_empty(self) -> None:
        d = _make_domain(10.0, 10.0)
        params = ConcentricBorderParams(insets_mm=(100.0,), groove_width_mm=2.0, depth_mm=3.0)
        with pytest.raises(GeneratorSkipError, match="exceeds domain size"):
            concentric_border_generator(d, params, allow_empty=False)

    def test_non_generator_skip_error_propagates(self) -> None:
        from unittest.mock import patch

        d = _make_domain(100.0, 100.0)
        params = ConcentricBorderParams(insets_mm=(5.0,), groove_width_mm=2.0, depth_mm=3.0)
        with (
            patch.object(Domain, "inset", side_effect=RuntimeError("shapely internal error")),
            pytest.raises(RuntimeError, match="shapely internal error"),
        ):
            concentric_border_generator(d, params, allow_empty=True)


class TestSvgStampGeneratorSkip:
    def test_returns_empty_on_degenerate_svg_allow_empty(self) -> None:
        d = _make_domain(100.0, 100.0)
        params = SVGPathParams(svg_path="M0 0", depth_mm=3.0)
        result = svg_stamp_generator(d, params, allow_empty=True)
        assert result == []

    def test_raises_on_degenerate_svg_not_allow_empty(self) -> None:
        d = _make_domain(100.0, 100.0)
        params = SVGPathParams(svg_path="M0 0", depth_mm=3.0)
        with pytest.raises(GeneratorSkipError, match=r"no geometry|no valid polylines"):
            svg_stamp_generator(d, params, allow_empty=False)

    def test_returns_empty_on_tiny_domain_allow_empty(self) -> None:
        tiny = Domain.from_rectangle(0.001, 0.001)
        params = SVGPathParams(svg_path="M0 0 L10 0 L10 10 Z", depth_mm=3.0)
        result = svg_stamp_generator(tiny, params, allow_empty=True)
        assert result == []


class TestExtractLoopsErrors:
    def test_out_of_range_index_raises_skip(self) -> None:
        d = _make_domain(100.0, 100.0)
        with pytest.raises(GeneratorSkipError, match="out of range"):
            extract_loops(d, [5], "test_gen")

    def test_invalid_selection_raises_value_error(self) -> None:
        d = _make_domain(100.0, 100.0)
        with pytest.raises(ValueError, match="invalid loop_selection"):
            extract_loops(d, "bogus", "test_gen")  # type: ignore[arg-type]


class TestProfileGenDirectConstruction:
    def test_emits_rect_item_when_no_domain(self) -> None:
        resolver = _make_resolver()
        region = _make_region(100.0, 100.0)
        node = ProfileGen(side="outside", depth="through")
        items: list = []
        resolver._handle_profile_gen(node, region, items, {})
        assert len(items) == 1
        assert items[0].type == "Rect"
        assert items[0].feature.type == "profile"

    def test_emits_polygon_item_when_domain_provided(self) -> None:
        resolver = _make_resolver()
        region = _make_region(100.0, 100.0)
        domain = _make_domain(100.0, 100.0)
        node = ProfileGen(side="inside", depth=5.0)
        items: list = []
        params = {"domain": domain, "domain_center": domain.centroid}
        resolver._handle_profile_gen(node, region, items, params)
        assert len(items) == 1
        assert items[0].type == "Polygon"

    def test_edge_treatment_propagated(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ProfileGen(side="outside", depth="through")
        items: list = []
        params = {"edge_treatment": {"type": "chamfer", "width_mm": 2.0}}
        resolver._handle_profile_gen(node, region, items, params)
        assert items[0].geometry.data.get("edge_treatment") is not None


class TestPocketGenDirectConstruction:
    def test_emits_rect_item_when_no_domain(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = PocketGen(depth_mm=5.0)
        items: list = []
        resolver._handle_pocket_gen(node, region, items, {})
        assert len(items) == 1
        assert items[0].type == "Rect"
        assert items[0].feature.type == "pocket"

    def test_edge_treatment_propagated(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = PocketGen(depth_mm=5.0)
        items: list = []
        params = {"edge_treatment": {"type": "roundover", "radius_mm": 3.0}}
        resolver._handle_pocket_gen(node, region, items, params)
        assert items[0].geometry.data.get("edge_treatment") is not None


class TestChamferGenDirectConstruction:
    def test_emits_rect_item_when_no_domain(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ChamferGen(width_mm=5.0, depth_mm=3.0)
        items: list = []
        resolver._handle_chamfer_gen(node, region, items, {})
        assert len(items) == 1
        assert items[0].type == "Rect"
        assert items[0].feature.type == "chamfer"

    def test_no_edge_treatment_propagated(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ChamferGen(width_mm=5.0, depth_mm=3.0)
        items: list = []
        params = {"edge_treatment": {"type": "roundover", "radius_mm": 3.0}}
        resolver._handle_chamfer_gen(node, region, items, params)
        assert "edge_treatment" not in items[0].geometry.data


class TestRoundoverGenDirectConstruction:
    def test_emits_rect_item_when_no_domain(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = RoundoverGen(radius_mm=5.0)
        items: list = []
        resolver._handle_roundover_gen(node, region, items, {})
        assert len(items) == 1
        assert items[0].type == "Rect"
        assert items[0].feature.type == "roundover"

    def test_no_edge_treatment_propagated(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = RoundoverGen(radius_mm=5.0)
        items: list = []
        params = {"edge_treatment": {"type": "chamfer", "width_mm": 2.0}}
        resolver._handle_roundover_gen(node, region, items, params)
        assert "edge_treatment" not in items[0].geometry.data


class TestShellGenErrorPaths:
    def test_wall_not_positive_raises(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ShellGen(wall_mm=0, interior="profile", depth="through")
        with pytest.raises(ValueError, match="wall must be positive"):
            resolver._handle_shell_gen(node, region, [], {})

    def test_invalid_interior_raises(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ShellGen(wall_mm=5.0, interior="invalid", depth="through")
        with pytest.raises(ValueError, match="interior must be"):
            resolver._handle_shell_gen(node, region, [], {})

    def test_pocket_through_raises(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ShellGen(wall_mm=5.0, interior="pocket", depth="through")
        with pytest.raises(ValueError, match="numeric depth"):
            resolver._handle_shell_gen(node, region, [], {})

    def test_pocket_negative_depth_raises(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        node = ShellGen(wall_mm=5.0, interior="pocket", depth=-1.0)
        with pytest.raises(ValueError, match="pocket depth must be positive"):
            resolver._handle_shell_gen(node, region, [], {})

    def test_nested_shell_raises(self) -> None:
        resolver = _make_resolver()
        region = _make_region()
        inner = ShellGen(wall_mm=2.0, interior="profile", depth="through")
        node = ShellGen(wall_mm=5.0, interior="profile", depth="through", children=(inner,))
        with pytest.raises(ValueError, match="nested Shell"):
            resolver._handle_shell_gen(node, region, [], {})

    def test_wall_exceeds_capacity_raises_skip_error(self) -> None:
        resolver = _make_resolver()
        region = _make_region(20.0, 20.0)
        node = ShellGen(wall_mm=50.0, interior="profile", depth="through")
        with pytest.raises(GeneratorSkipError, match="exceeds shape capacity"):
            resolver._handle_shell_gen(node, region, [], {})

    def test_disjoint_inset_raises_skip_error(self) -> None:
        u_domain = Domain.from_polygon(
            [
                (0, 0),
                (200, 0),
                (200, 100),
                (110, 100),
                (110, 15),
                (90, 15),
                (90, 100),
                (0, 100),
            ]
        )
        resolver = _make_resolver(width=300.0, height=200.0)
        region = _make_region(200.0, 100.0)
        node = ShellGen(wall_mm=10.0, interior="profile", depth="through")
        params = {"domain": u_domain, "domain_center": u_domain.centroid}
        with pytest.raises(GeneratorSkipError, match="disjoint regions"):
            resolver._handle_shell_gen(node, region, [], params)

    def test_valid_shell_produces_items(self) -> None:
        resolver = _make_resolver()
        region = _make_region(100.0, 100.0)
        node = ShellGen(wall_mm=10.0, interior="profile", depth="through")
        items: list = []
        resolver._handle_shell_gen(node, region, items, {})
        assert len(items) >= 1
        assert items[0].feature.type == "profile"


class TestEngraveTextCharacterization:
    def test_empty_text_returns_empty_silently(self) -> None:
        from generators.area.engrave_text import engrave_text_at_position

        result = engrave_text_at_position(
            text="",
            position=(50.0, 50.0),
            height_mm=10.0,
            depth_mm=1.0,
        )
        assert result == []
