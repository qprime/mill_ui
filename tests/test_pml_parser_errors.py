from __future__ import annotations

import json
from typing import Any

import pytest

from pml.nest_parser import NestParseError
from pml.yaml_parser import PMLParseError, parse_node, parse_pml_yaml

MINIMAL_SHEET = "Sheet:\n  width: 200\n  height: 200\n  thickness: 19\n"


class TestRequireMissingKey:
    def test_missing_required_key_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Missing required key 'width'"):
            parse_node({"Frame": {}}, "test")


class TestParseNodeTypeChecks:
    def test_no_type_found(self) -> None:
        with pytest.raises(PMLParseError, match="No node type found"):
            parse_node({}, "test")

    def test_multiple_types_found(self) -> None:
        with pytest.raises(PMLParseError, match="Multiple node types"):
            parse_node({"Panel": {}, "Frame": {}}, "test")

    def test_non_dict_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Expected dict"):
            parse_node("not a dict", "test")  # type: ignore[arg-type]

    def test_unknown_node_type_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Unknown node type"):
            parse_node({"ZzUnknown": {}}, "test")


class TestRestAndRestToolConflict:
    def test_both_rest_and_rest_tool_raises(self) -> None:
        node = {
            "Rect": {
                "feature": {
                    "type": "pocket",
                    "rest": {"tool": 6},
                    "rest_tool": 3,
                },
            }
        }
        with pytest.raises(PMLParseError, match="Cannot specify both 'rest' and 'rest_tool'"):
            parse_node(node, "test")


class TestEdgeParsing:
    def test_missing_treatment_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Edge requires 'treatment' key"):
            parse_node({"Edge": {"radius": 5}}, "test")


class TestInsetParsing:
    def test_missing_distance_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Inset requires 'distance' key"):
            parse_node({"Inset": {}}, "test")


class TestEngraveTextFontValidation:
    def test_unknown_font_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Unknown font 'bogus'"):
            parse_node({"EngraveText": {"text": "X", "font": "bogus"}}, "test")

    def test_default_font_accepted(self) -> None:
        parse_node({"EngraveText": {"text": "X"}}, "test")

    def test_bundled_font_accepted(self) -> None:
        parse_node({"EngraveText": {"text": "X", "font": "futural"}}, "test")


class TestSurfaceBlockValidation:
    @pytest.mark.parametrize(
        ("override", "match"),
        [
            ({"depth-per-pass": -1}, "depth-per-pass must be > 0"),
            ({"depth-per-pass": 0}, "depth-per-pass must be > 0"),
            ({"depth-per-pass": 1, "passes": 0}, "passes must be >= 1"),
            ({"depth-per-pass": 1, "stepover": "0%"}, "stepover must be > 0"),
            ({"depth-per-pass": 1, "stepover": "101%"}, "stepover must be > 0"),
            ({"depth-per-pass": 1, "direction": "z"}, "direction must be 'x' or 'y'"),
            ({"depth-per-pass": 1, "margin-overrun": "-1mm"}, "margin-overrun must be >= 0"),
            ({"depth-per-pass": 1, "cool_every": -1}, "cool_every must be >= 0"),
            ({"depth-per-pass": 1, "cool_dwell": "-1s"}, "cool_dwell must be >= 0"),
        ],
    )
    def test_surface_constraint(self, override: dict, match: str) -> None:
        source = MINIMAL_SHEET + "Surface:\n"
        for k, v in override.items():
            source += f"  {k}: {v}\n"
        with pytest.raises(PMLParseError, match=match):
            parse_pml_yaml(source)


class TestSurfaceCoercions:
    @pytest.mark.parametrize(
        ("field", "value", "field_name"),
        [
            ("passes", "many", "passes"),
            ("stepover", "wide", "stepover"),
            ("cool_every", "often", "cool_every"),
            ("cool_dwell", "long", "cool_dwell"),
        ],
    )
    def test_invalid_type_raises_pml_error(self, field: str, value: str, field_name: str) -> None:
        source = MINIMAL_SHEET + f"Surface:\n  depth-per-pass: 1\n  {field}: {value}\n"
        with pytest.raises(PMLParseError, match=field_name):
            parse_pml_yaml(source)


class TestSvgStampCoercion:
    def test_invalid_svg_unit_raises_pml_error(self) -> None:
        with pytest.raises(PMLParseError, match="svg_unit"):
            parse_node(
                {"SvgStamp": {"path": "M0 0 L10 10", "depth": 3, "svg_unit": "big"}},
                "test",
            )


class TestLinesAngleCoercion:
    def test_invalid_angle_raises_pml_error(self) -> None:
        with pytest.raises(PMLParseError, match="angle"):
            parse_node(
                {"Lines": {"angle": "steep", "spacing": 10, "width": 2, "depth": 3}},
                "test",
            )


class TestAssemblyDimensionFalsyValues:
    @pytest.mark.parametrize("field", ["width", "depth", "height"])
    def test_explicit_zero_not_overridden_by_dimensions(self, field: str) -> None:
        base = {"type": "box", "width": 200, "depth": 300, "height": 100, "thickness": 19}
        base[field] = 0
        base["dimensions"] = [999, 999, 999]
        node = {"Assembly": base}
        result = parse_node(node, "test")
        assert getattr(result, f"{field}_mm") == 0.0

    def test_dimensions_fallback_still_works(self) -> None:
        node = {
            "Assembly": {
                "type": "box",
                "dimensions": [200, 300, 100],
                "thickness": 19,
            }
        }
        result = parse_node(node, "test")
        assert result.width_mm == 200.0
        assert result.depth_mm == 300.0
        assert result.height_mm == 100.0


class TestGridCoercion:
    def test_invalid_grid_values_raises_pml_error(self) -> None:
        with pytest.raises(PMLParseError, match="grid"):
            parse_node(
                {
                    "Assembly": {
                        "type": "cubby",
                        "width": 200,
                        "height": 100,
                        "depth": 300,
                        "thickness": 19,
                        "grid": ["a", "b"],
                    }
                },
                "test",
            )


class TestParseEmptyYaml:
    def test_empty_string_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Empty YAML document"):
            parse_pml_yaml("")

    def test_missing_sheet_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Missing 'Sheet:' root key"):
            parse_pml_yaml("project: test\n")


class TestSheetDimensionValidation:
    def test_missing_width_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Sheet missing 'width'"):
            parse_pml_yaml("Sheet:\n  height: 200\n  thickness: 19\n")

    def test_missing_height_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Sheet missing 'height'"):
            parse_pml_yaml("Sheet:\n  width: 200\n  thickness: 19\n")


class TestNestParserErrors:
    def test_empty_yaml(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        with pytest.raises(NestParseError, match="Empty YAML document"):
            parse_nest_yaml("")

    def test_missing_nest_key(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        with pytest.raises(NestParseError, match="Missing 'Nest:' root key"):
            parse_nest_yaml("project: test\n")

    def test_missing_algorithm(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n  parts:\n    - name: a\n      width: 100\n      height: 100\n"
        with pytest.raises(NestParseError, match="Missing 'algorithm'"):
            parse_nest_yaml(source)

    def test_invalid_sheet_dimensions(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: big\n    height: 1000\n    thickness: 19\n  parts:\n    - name: a\n      width: 100\n      height: 100\n"
        with pytest.raises(NestParseError, match="Invalid sheet dimensions"):
            parse_nest_yaml(source)

    def test_no_parts_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
        with pytest.raises(NestParseError, match="No parts defined"):
            parse_nest_yaml(source)

    def test_non_dict_part_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n  parts:\n    - not_a_dict\n"
        with pytest.raises(NestParseError, match="Invalid part definition"):
            parse_nest_yaml(source)

    def test_part_missing_name(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n  parts:\n    - width: 100\n      height: 100\n"
        with pytest.raises(NestParseError, match="Part missing 'name'"):
            parse_nest_yaml(source)

    def test_invalid_part_dimensions(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n  parts:\n    - name: a\n      width: big\n      height: 100\n"
        with pytest.raises(NestParseError, match="Invalid dimensions"):
            parse_nest_yaml(source)

    def test_invalid_quantity(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n  parts:\n    - name: a\n      width: 100\n      height: 100\n      quantity: 0\n"
        with pytest.raises(NestParseError, match="Invalid quantity"):
            parse_nest_yaml(source)


class TestNestPolygonValidation:
    def test_missing_points_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n      shape:\n        type: Polygon\n"
        )
        with pytest.raises(NestParseError, match="requires 'points'"):
            parse_nest_yaml(source)

    def test_fewer_than_3_points_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n      shape:\n        type: Polygon\n"
            "        points:\n          - [0, 0]\n          - [50, 0]\n"
        )
        with pytest.raises(NestParseError, match="at least 3 points"):
            parse_nest_yaml(source)

    def test_invalid_point_format_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n      shape:\n        type: Polygon\n"
            "        points:\n          - [0, 0, 0]\n          - [50, 0]\n          - [50, 50]\n"
        )
        with pytest.raises(NestParseError, match=r"expected \[x, y\]"):
            parse_nest_yaml(source)

    def test_non_numeric_point_coordinate_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n      shape:\n        type: Polygon\n"
            "        points:\n          - [x, y]\n          - [50, 0]\n          - [50, 50]\n"
        )
        with pytest.raises(NestParseError, match="Invalid point coordinate"):
            parse_nest_yaml(source)


class TestNestHoldingValidation:
    def test_unknown_holding_key_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  holding:\n    bogus_key: 5\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n"
        )
        with pytest.raises(NestParseError, match="Unknown holding key"):
            parse_nest_yaml(source)

    def test_invalid_onion_skin_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  holding:\n    onion_skin: big\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n"
        )
        with pytest.raises(NestParseError, match="Invalid onion_skin"):
            parse_nest_yaml(source)

    def test_mutually_exclusive_holding_raises(self) -> None:
        from pml.yaml_parser import parse_nest_yaml

        source = (
            "Nest:\n  algorithm: maxrects\n  Sheet:\n    width: 1000\n    height: 1000\n    thickness: 19\n"
            "  holding:\n    onion_skin: 0.5mm\n    tab_count: 4\n    tab_height: 3mm\n"
            "  parts:\n    - name: a\n      width: 100\n      height: 100\n"
        )
        with pytest.raises(NestParseError, match="Invalid holding"):
            parse_nest_yaml(source)


class TestFaceAttribute:
    def _pml(self, feature_block: str, sheet_extra: str = "") -> str:
        return (
            f"Sheet:\n  width: 400mm\n  height: 300mm\n  thickness: 19mm\n{sheet_extra}"
            f"children:\n- Circle:\n    id: anchor\n    diameter: 35mm\n"
            f"    feature:\n{feature_block}"
            f"    at:\n      x: 100mm\n      y: 100mm\n"
        )

    def test_face_back_with_through_depth_rejected(self) -> None:
        source = self._pml("      type: pocket\n      depth: through\n      face: back\n")
        with pytest.raises(PMLParseError, match="cannot be combined with depth: through"):
            parse_pml_yaml(source)

    def test_face_back_hole_without_depth_rejected(self) -> None:
        source = self._pml("      type: hole\n      face: back\n")
        with pytest.raises(PMLParseError, match="cannot be combined with depth: through"):
            parse_pml_yaml(source)

    def test_face_on_profile_feature_rejected(self) -> None:
        source = self._pml("      type: profile\n      depth: 6mm\n      side: outside\n      face: back\n")
        with pytest.raises(PMLParseError, match="only valid on"):
            parse_pml_yaml(source)

    def test_face_invalid_value_rejected(self) -> None:
        source = self._pml("      type: pocket\n      depth: 6mm\n      face: top\n")
        with pytest.raises(PMLParseError, match="Invalid face 'top'"):
            parse_pml_yaml(source)

    def test_non_positive_safe_z_rejected(self) -> None:
        source = self._pml("      type: pocket\n      depth: 6mm\n", sheet_extra="  safe_z: 0mm\n")
        with pytest.raises(PMLParseError, match="safe_z must be > 0"):
            parse_pml_yaml(source)

    def test_negative_min_web_rejected(self) -> None:
        source = self._pml("      type: pocket\n      depth: 6mm\n", sheet_extra="  min_web: -1mm\n")
        with pytest.raises(PMLParseError, match="min_web must be >= 0"):
            parse_pml_yaml(source)

    def test_pocket_generator_rejects_invalid_face(self) -> None:
        source = (
            "Sheet:\n  width: 400mm\n  height: 300mm\n  thickness: 19mm\n"
            "children:\n- Rect:\n    children:\n    - Pocket:\n        depth: 6mm\n        face: sideways\n"
        )
        with pytest.raises(PMLParseError, match="Invalid face 'sideways'"):
            parse_pml_yaml(source)


MINIMAL_NODE_DATA: dict[str, dict[str, Any]] = {
    "Panel": {},
    "Rect": {},
    "Circle": {},
    "RoundedRect": {"radius": 5},
    "Line": {"orientation": "horizontal"},
    "Polyline": {"points": [[0, 0], [1, 1]]},
    "Spline": {"points": [[0, 0], [1, 1]]},
    "Island": {},
    "Keepout": {},
    "Edge": {"treatment": "roundover", "radius": 2},
    "Inset": {"distance": 5},
    "Frame": {"width": 5},
    "Grid": {"rows": 2, "cols": 2},
    "Cell": {},
    "Split": {"rows": 2, "cols": 2},
    "Profile": {"side": "outside"},
    "Pocket": {"depth": 2},
    "RaisedPanel": {"border_depth": 4, "field_depth": 2},
    "Chamfer": {"width": 2, "depth": 2},
    "Roundover": {"radius": 2},
    "Wave": {"count": 2, "amplitude": 2, "spacing": 5, "depth": 1},
    "XPanel": {"bar_width": 5, "depth": 2},
    "SplitHorizontal": {"count": 2},
    "SplitVertical": {"count": 2},
    "SplitGrid": {"rows": 2, "cols": 2},
    "SplitHorizontalGaps": {"count": 2, "gap": 5},
    "Lines": {"angle": 45, "spacing": 10, "width": 2, "depth": 2},
    "Heightfield": {"image": "relief.png", "size": {"width": 50, "height": 40}, "depth": 2},
    "Fluting": {"spacing": 10, "depth": 2},
    "ConcentricBorder": {"insets": [10], "groove": 2, "depth": 1},
    "Place": {},
    "AtPosition": {"x": 50, "y": 50},
    "Subtract": {"inner_inset": 5},
    "Shell": {"wall": 5, "interior": "pocket"},
    "Arch": {"width": 50, "height": 40, "radius": 25},
    "Polygon": {"points": [[0, 0], [50, 0], [0, 40]]},
    "Triangle": {"base": 50, "height": 40},
    "Ellipse": {},
    "HoleGrid": {"spacing": 10, "diameter": 3},
    "MeasurementGrid": {},
    "MeasurementEdge": {"edges": ["bottom"]},
    "GridLines": {},
    "EngraveText": {"text": "test"},
    "WasteCuts": {"tab_count": 2, "tab_height": 2},
    "Assembly": {"width": 100, "height": 100, "depth": 100, "thickness": 19},
    "UseComponent": {"name": "test"},
    "Engrave": {"depth": 1},
    "Beam": {"length": 100, "width": 50, "thickness": 19},
    "Radial": {"rays": 8, "depth": 2},
    "Curve": {"type": "rose", "lobes": 5, "depth": 1},
    "Phyllotaxis": {"count": 10, "spacing": 5, "element": {"type": "hole", "diameter": 2}},
    "Voronoi": {"seed_count": 5, "depth": 1},
    "StringArt": {"anchors": 10, "rule": "multiply", "factor": 2, "depth": 1},
    "SvgStamp": {"path": "M0 0 L10 10", "depth": 1},
}

_FEATURE_NODES = {
    "Rect",
    "Circle",
    "RoundedRect",
    "Line",
    "Polyline",
    "Spline",
    "Arch",
    "Polygon",
    "Triangle",
    "Ellipse",
}
_CHILDREN_NODES = {
    "Panel",
    "Rect",
    "Circle",
    "RoundedRect",
    "Island",
    "Keepout",
    "Inset",
    "Frame",
    "Grid",
    "Cell",
    "Split",
    "SplitHorizontal",
    "SplitVertical",
    "SplitGrid",
    "SplitHorizontalGaps",
    "Place",
    "Subtract",
    "Shell",
    "Arch",
    "Polygon",
    "Triangle",
    "Ellipse",
}


class TestClosedNodeKeys:
    def test_minimal_node_data_covers_every_node_type(self):
        from pml.yaml_parser import _NODE_KEYS

        assert MINIMAL_NODE_DATA.keys() == _NODE_KEYS.keys()

    @pytest.mark.parametrize("node_type", MINIMAL_NODE_DATA)
    def test_unknown_key_rejected_for_every_node_type(self, node_type):
        data = MINIMAL_NODE_DATA[node_type]
        parse_node({node_type: data}, "test")
        with pytest.raises(PMLParseError, match=r"zz_unknown.*PM-18") as exc:
            parse_node({node_type: {**data, "zz_unknown": 1}}, "test")
        assert exc.value.path == f"test.{node_type}"
        assert "Allowed keys:" in str(exc.value)

    @pytest.mark.parametrize("node_type", MINIMAL_NODE_DATA)
    @pytest.mark.parametrize("key", ["feature", "children", "id", "label"])
    def test_generic_keys_admitted_only_where_kept(self, node_type, key):
        if key == "feature" and node_type == "SvgStamp":
            result = parse_node({node_type: {**MINIMAL_NODE_DATA[node_type], "feature": "pocket"}})
            assert result.feature_type == "pocket"
            return
        values = {"feature": {"type": "engrave", "depth": 1}, "children": [{"Rect": {}}], "id": "part", "label": "part"}
        allowed = {
            "feature": _FEATURE_NODES,
            "label": _FEATURE_NODES,
            "id": _FEATURE_NODES | {"Panel", "Island", "Keepout", "Edge"},
            "children": _CHILDREN_NODES,
        }
        data = {node_type: {**MINIMAL_NODE_DATA[node_type], key: values[key]}}
        if node_type not in allowed[key]:
            with pytest.raises(PMLParseError, match=f"{key}.*PM-18"):
                parse_node(data)
            return
        result = parse_node(data)
        if key == "feature":
            assert result.feature.type == "engrave"
            assert result.feature.depth_mm == 1
        elif key == "children":
            assert len(result.children) == 1
        else:
            assert getattr(result, key) == "part"

    @pytest.mark.parametrize("key", ["at", "feature", "id", "children", "typo"])
    def test_sibling_keys_rejected(self, key):
        with pytest.raises(PMLParseError, match=f"'{key}' must be inside the Rect mapping.*PM-18"):
            parse_node({"Rect": {}, key: {}})

    def test_unknown_key_checked_before_required_key(self):
        with pytest.raises(PMLParseError, match=r"widht.*Allowed keys:.*width.*PM-18"):
            parse_node({"Frame": {"widht": 10}})


class TestRectPlacementKeys:
    @pytest.mark.parametrize("node_type", ["Rect", "RoundedRect", "Ellipse"])
    @pytest.mark.parametrize(
        "keys",
        [{"w": 50, "h": 40, "x": 100, "y": 100}, {"width": 50, "height": 40}, {"at": {"x": 100, "y": 100}, "w": 50}],
    )
    def test_shape_shorthand_rejected_with_at_hint(self, node_type, keys):
        with pytest.raises(PMLParseError, match=r"placement and size go in at: \{x, y, width, height\}.*PM-18"):
            parse_node({node_type: keys})

    def test_rect_at_w_h_rejected(self):
        with pytest.raises(PMLParseError, match=r"w, h.*PM-18"):
            parse_node({"Rect": {"at": {"x": 100, "y": 100, "w": 50, "h": 40}}})

    def test_rect_at_pocket_intent_bounds(self):
        from adapters.ast_to_removal import ast_to_removal_intents
        from resolution.layout_resolver import resolve_layout

        ast = parse_pml_yaml(
            "Sheet: {width: 400mm, height: 300mm, thickness: 19mm}\n"
            "children:\n- Rect:\n    at: {x: 100mm, y: 100mm, width: 50mm, height: 40mm}\n"
            "    feature: {type: pocket, depth: 2mm}\n"
        )
        (intent,) = ast_to_removal_intents(resolve_layout(ast))
        assert (intent.bounds.x_min, intent.bounds.x_max, intent.bounds.y_min, intent.bounds.y_max) == (
            75,
            125,
            80,
            120,
        )
        assert intent.depth_profile.z_bottom == -2


class TestAtKeys:
    @pytest.mark.parametrize("node_type", ["Circle", "Polygon"])
    def test_at_size_rejected(self, node_type):
        with pytest.raises(PMLParseError, match=r"width.*PM-18"):
            parse_node({node_type: {**MINIMAL_NODE_DATA[node_type], "at": {"x": 100, "y": 100, "width": 50}}})

    @pytest.mark.parametrize("node_type", ["Rect", "RoundedRect", "Ellipse", "Circle", "Polygon"])
    @pytest.mark.parametrize("at", [{}, {"x": 100}, {"y": 100}])
    def test_at_requires_xy(self, node_type, at):
        with pytest.raises(PMLParseError, match="Missing required key"):
            parse_node({node_type: {**MINIMAL_NODE_DATA[node_type], "at": at}})


class TestFeatureChildren:
    @pytest.mark.parametrize("node_type", sorted(_CHILDREN_NODES - _FEATURE_NODES))
    def test_feature_child_rejected_on_container(self, node_type):
        with pytest.raises(PMLParseError, match=r"does not accept Feature children.*PM-18"):
            parse_node({node_type: {**MINIMAL_NODE_DATA[node_type], "children": [{"Engrave": {"depth": 1}}]}})

    @pytest.mark.parametrize("explicit", [False, True])
    def test_multiple_features_rejected(self, explicit):
        data: dict[str, Any] = {"children": [{"Engrave": {"depth": 1}}]}
        if explicit:
            data["feature"] = {"type": "pocket", "depth": 2}
        else:
            data["children"].append({"Engrave": {"depth": 3}})
        with pytest.raises(PMLParseError, match=r"at most one feature.*PM-18"):
            parse_node({"Rect": data})

    @pytest.mark.parametrize("node_type", ["Rect", "Line", "Polyline", "Spline"])
    def test_single_engrave_child_still_hoisted(self, node_type):
        node = parse_node({node_type: {**MINIMAL_NODE_DATA[node_type], "children": [{"Engrave": {"depth": 1}}]}})
        assert node.feature.type == "engrave"
        assert node.feature.depth_mm == 1
        assert getattr(node, "children", ()) == ()


class TestFeatureKeys:
    @pytest.mark.parametrize(
        "feature",
        [
            {"type": "pocket", "depht": 2},
            {"type": "pockett"},
            {"type": "profile", "dogbone": True},
            {"type": "pocket", "tab_count": 4},
            {"type": "pocket", "feeds": {"feedxy": 500}},
            {"type": "pocket", "dogbone": {"diamter": 3}},
            {"type": "pocket", "rest": {"rough_allowence": 1}},
        ],
    )
    def test_invalid_feature_keys_rejected(self, feature):
        with pytest.raises(PMLParseError, match="PM-18"):
            parse_node({"Rect": {"feature": feature}})

    def test_empty_feature_rejected(self):
        with pytest.raises(PMLParseError, match="Feature missing 'type'"):
            parse_node({"Rect": {"feature": {}}})

    def test_empty_feeds_accepted(self):
        node = parse_node({"Rect": {"feature": {"type": "pocket", "depth": 2, "feeds": {}}}})
        assert node.feature.feeds_override is None


class TestDocumentKeys:
    @pytest.mark.parametrize(
        "source, context, key",
        [
            (MINIMAL_SHEET + "zz_unknown: 1", "root", "zz_unknown"),
            ("Sheet: {width: 200, height: 200, thickness: 19, cut_through_mm: 1}", "Sheet", "cut_through_mm"),
            (MINIMAL_SHEET + "Surface: {zz_unknown: 1}", "Surface", "zz_unknown"),
            (MINIMAL_SHEET + "components: {part: {zz_unknown: 1}}", "components.part", "zz_unknown"),
        ],
    )
    def test_document_unknown_keys_rejected(self, source, context, key):
        with pytest.raises(PMLParseError, match=f"{key}.*PM-18") as exc:
            parse_pml_yaml(source)
        assert exc.value.path == context

    def test_templated_component_checks_keys_at_instantiation(self):
        source = MINIMAL_SHEET + "components: {part: {params: {d: 2}, body: {Rect: {zz_unknown: '${d}'}}}}\n"
        parse_pml_yaml(source)
        with pytest.raises(PMLParseError, match=r"zz_unknown.*PM-18"):
            parse_pml_yaml(source + "children: [{UseComponent: {name: part}}]")


class TestBeamKeys:
    @pytest.mark.parametrize(
        "field, value",
        [
            ("end_features", [{"Tenon": {"center_offset": 5}}]),
            ("face_features", [{"DrillHole": {"diamter": 3}}]),
            ("layers", [{"length": 100, "offest": 5}]),
            ("layers", [{"length": 100, "cutouts": [{"start": 5, "length": 10, "widht": 2}]}]),
        ],
    )
    def test_discarded_beam_keys_rejected(self, field, value):
        with pytest.raises(PMLParseError, match="PM-18"):
            parse_node({"Beam": {**MINIMAL_NODE_DATA["Beam"], field: value}})


class TestAssemblyKeys:
    @pytest.mark.parametrize(
        "field, value",
        [
            ("widht", 10),
            ("interfaces", {"left": {"clearence": 1}}),
            ("interfaces", {"left": 1}),
            ("top", {"widht": 5}),
            ("back", {"thikness": 5}),
            *[
                (field, value)
                for field in ("top", "bottom", "back", "shelf_joinery", "partition_joinery")
                for value in (1, ["invalid"], None)
            ],
            *[("grid", value) for value in ([1], [1, 2, 3], [], 2, None)],
        ],
    )
    def test_discarded_assembly_input_rejected(self, field, value):
        with pytest.raises(PMLParseError, match="PM-18"):
            assembly_type = "cubby" if field in ("grid", "partition_joinery") else "carcass"
            parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "type": assembly_type, field: value}})

    def test_back_mapping_keeps_thickness(self):
        result = parse_node(
            {
                "Assembly": {
                    **MINIMAL_NODE_DATA["Assembly"],
                    "type": "carcass",
                    "back": {"thickness": 6, "joinery": "captured", "inset": 2},
                }
            }
        )
        assert result.back_thickness_mm == 6
        assert result.back.inset_mm == 2


class TestGeneratorSubKeys:
    @pytest.mark.parametrize(
        "node_type, overrides",
        [
            ("Radial", {"minor_subdivisions": 2}),
            ("Radial", {"element": {"type": "tick", "bar_width": 2}}),
            ("Phyllotaxis", {"element": {"type": "hole", "diameter": 2, "diamter": 3}}),
            ("Heightfield", {"tools": [{"tool": "flat", "step_over": 0.5}]}),
            ("Heightfield", {"size": {"width": 50, "heigth": 40}}),
        ],
    )
    def test_discarded_generator_keys_rejected(self, node_type, overrides):
        with pytest.raises(PMLParseError, match="PM-18"):
            parse_node({node_type: {**MINIMAL_NODE_DATA[node_type], **overrides}})


class TestStandaloneFeatures:
    @pytest.mark.parametrize(
        "document, error_path",
        [
            ("children: [{Engrave: {depth: 1mm}}]", "root.children[0]"),
            (
                "children: [{Rect: {feature: {type: pocket, depth: 2mm}}}, {Engrave: {depth: 1mm}}]",
                "root.children[1]",
            ),
            (
                "components: {part: {body: [{Engrave: {depth: 1mm}}]}}",
                "components.part.body.children[0]",
            ),
            ("components: {part: {body: {Engrave: {depth: 1mm}}}}", "components.part.body"),
            (
                "children: [{AtPosition: {x: 100mm, y: 100mm, child: {Engrave: {depth: 1mm}}}}]",
                "root.children[0].child",
            ),
            (
                "children: [{Place: {layout: {Engrave: {depth: 1mm}}}}]",
                "root.children[0].layout",
            ),
        ],
    )
    def test_standalone_feature_rejected_at_document_boundary(self, document, error_path):
        with pytest.raises(PMLParseError, match=r"Standalone Feature.*attach it to a shape.*PM-18") as exc:
            parse_pml_yaml(MINIMAL_SHEET + document)
        assert exc.value.path == error_path

    @pytest.mark.parametrize(
        "body, error_path",
        [
            ("[{Engrave: {depth: '${d}'}}]", "root.children[0].body.children[0]"),
            ("{Engrave: {depth: '${d}'}}", "root.children[0].body"),
            (
                "{AtPosition: {x: 50mm, y: 50mm, child: {Engrave: {depth: '${d}'}}}}",
                "root.children[0].body.child",
            ),
            ("{Place: {layout: {Engrave: {depth: '${d}'}}}}", "root.children[0].body.layout"),
        ],
    )
    def test_parameterized_component_feature_checked_when_instantiated(self, body, error_path):
        source = MINIMAL_SHEET + "components:\n  part:\n    params: {d: 1mm}\n    body: " + body + "\n"
        parse_pml_yaml(source)
        with pytest.raises(PMLParseError, match=r"Standalone Feature.*PM-18") as exc:
            parse_pml_yaml(source + "children: [{UseComponent: {name: part}}]")
        assert exc.value.path == error_path

    @pytest.mark.parametrize(
        "document",
        [
            "children: [{AtPosition: {x: 100mm, y: 100mm, width: 50mm, height: 40mm, child: {Rect: {children: [{Engrave: {depth: 1mm}}]}}}}]",
            "children: [{Place: {layout: {Grid: {rows: 1, cols: 1}}, children: [{Rect: {children: [{Engrave: {depth: 1mm}}]}}]}}]",
            "components: {part: {params: {d: 1mm}, body: [{Rect: {children: [{Engrave: {depth: '${d}'}}]}}]}}\nchildren: [{UseComponent: {name: part}}]",
        ],
    )
    def test_attached_feature_survives_nested_structure(self, document):
        from adapters.ast_to_removal import ast_to_removal_intents
        from resolution.layout_resolver import resolve_layout

        ast = parse_pml_yaml(MINIMAL_SHEET + document)
        (intent,) = ast_to_removal_intents(resolve_layout(ast))
        assert intent.hint_type == "engrave"
        assert intent.depth_profile.z_bottom == -1


class TestDogboneValueShapes:
    @staticmethod
    def _parse_dogbone(target: str, value: Any) -> Any:
        if target == "feature":
            return parse_node(
                {"Rect": {"feature": {"type": "pocket", "depth": 2, "dogbone": value}}}, "test"
            ).feature.dogbone
        config = {"dogbone": value}
        override = {target: config}
        node = parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "type": "carcass", **override}}, "test")
        return getattr(node, target).dogbone

    @pytest.mark.parametrize("target", ["feature", "top", "shelf_joinery"])
    @pytest.mark.parametrize("value", ["3mm", "true", "false", 3, 0, 1, 0.0, 1.0, [], [True], None])
    def test_invalid_dogbone_value_rejected(self, target, value):
        with pytest.raises(PMLParseError, match=r"dogbone must be true, false or a mapping.*PM-18") as exc:
            self._parse_dogbone(target, value)
        expected_path = {
            "feature": "test.Rect.feature.dogbone",
            "top": "test.Assembly.top.dogbone",
            "shelf_joinery": "test.Assembly.shelf_joinery.dogbone",
        }
        assert exc.value.path == expected_path[target]

    @pytest.mark.parametrize("target", ["feature", "top", "shelf_joinery"])
    @pytest.mark.parametrize(
        "value", [True, False, {}, {"style": "t-bone_x", "diameter": "3.175mm", "overcut": "0.5mm"}]
    )
    def test_supported_dogbone_values_retained(self, target, value):
        from layout_ast.layout import DogboneSpec

        dogbone = self._parse_dogbone(target, value)
        if value is False:
            assert dogbone is (None if target == "feature" else False)
        elif value is True:
            if target == "feature":
                assert dogbone == DogboneSpec()
            else:
                assert dogbone is True
        elif not value:
            assert dogbone == DogboneSpec()
        else:
            assert dogbone == DogboneSpec(style="t-bone_x", diameter_mm=3.175, overcut_mm=0.5)

    def test_omitted_dogbone_retains_defaults(self):
        node = parse_node({"Rect": {"feature": {"type": "pocket", "depth": 2}}})
        assert node.feature.dogbone is None
        node = parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "top": {"joinery": "captured"}}})
        assert node.top.dogbone is None


class TestEffectiveAssemblyOptions:
    @pytest.mark.parametrize("assembly_type", ["box", "carcass", "cubby"])
    @pytest.mark.parametrize(
        "options",
        [
            {"interfaces": {}},
            {"interfaces": {"left": "butt"}},
            {"children": [{"Rect": {"feature": {"type": "pocket", "depth": 2}}}]},
            {"show_dimensions": False},
        ],
    )
    def test_unimplemented_assembly_requests_rejected(self, assembly_type, options):
        with pytest.raises(PMLParseError, match="PM-18"):
            parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "type": assembly_type, **options}})

    @pytest.mark.parametrize(
        "assembly_type, options",
        [
            ("box", {"fixed_shelves": 2}),
            ("box", {"toe_kick_height": 50}),
            ("box", {"toe_kick_depth": 20}),
            ("box", {"toe_kick_style": "open"}),
            ("box", {"toe_kick_cover": True}),
            ("box", {"back": "captured"}),
            ("box", {"grid": [2, 2]}),
            ("box", {"cap_style": "over_sides"}),
            ("carcass", {"grid": [2, 2]}),
            ("carcass", {"back_joinery": "butt"}),
            ("carcass", {"back_rabbet_depth": 6}),
            ("carcass", {"back_internal_support": False}),
            ("carcass", {"internal_joinery": "half_lap"}),
            ("carcass", {"partition_joinery": "captured"}),
            ("carcass", {"partition_dado_depth": 5}),
            ("cubby", {"top": "none"}),
            ("cubby", {"bottom": "butt"}),
            ("cubby", {"fixed_shelves": 2}),
            ("cubby", {"toe_kick_height": 50}),
            ("cubby", {"cap_style": "over_sides"}),
        ],
    )
    def test_option_for_another_assembly_type_rejected(self, assembly_type, options):
        key = next(iter(options))
        with pytest.raises(PMLParseError, match=rf"Assembly {assembly_type} key.*{key}.*Allowed keys:.*PM-18"):
            parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "type": assembly_type, **options}})

    def test_unknown_assembly_type_rejected(self):
        with pytest.raises(PMLParseError, match=r"Unknown Assembly type.*Allowed types:.*PM-18"):
            parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "type": "cabient"}})

    @pytest.mark.parametrize(
        "assembly_type, config, variant, counts",
        [
            (
                "box",
                {"width": 160, "depth": 110, "height": 70, "thickness": 6, "finger_width": 12, "top": "none"},
                {"top": "finger"},
                (5, 6),
            ),
            (
                "carcass",
                {
                    "width": 600,
                    "depth": 300,
                    "height": 600,
                    "thickness": 18,
                    "joinery": "butt",
                    "top": "butt",
                    "bottom": "butt",
                },
                {"fixed_shelves": 1},
                (4, 5),
            ),
            (
                "cubby",
                {"width": 900, "depth": 300, "height": 600, "thickness": 18, "grid": [1, 1], "finger_width": 15},
                {"grid": [2, 2]},
                (4, 6),
            ),
        ],
    )
    def test_supported_type_options_change_machining_intents_and_round_trip(
        self, assembly_type, config, variant, counts
    ):
        from adapters.ast_to_removal import ast_to_removal_intents
        from pml.yaml_formatter import format_pml_yaml
        from resolution.layout_resolver import resolve_layout_multi

        for extra, count in zip(({}, variant), counts, strict=True):
            source = json.dumps(
                {
                    "Sheet": {"width": 2000, "height": 2000, "thickness": config["thickness"]},
                    "children": [{"Assembly": {"type": assembly_type, **config, **extra}}],
                }
            )
            ast = parse_pml_yaml(source)
            assert parse_pml_yaml(format_pml_yaml(ast)) == ast
            intents = [intent for sheet in resolve_layout_multi(ast) for intent in ast_to_removal_intents(sheet)]
            assert sum(intent.hint_type == "profile" for intent in intents) == count


class TestPlaceLayouts:
    @pytest.mark.parametrize("layout", [{"Rect": {}}, {"Frame": {"width": 5}}, {"Split": {"rows": 1, "cols": 2}}])
    def test_ignored_layout_node_rejected(self, layout):
        source = json.dumps(
            {"Sheet": {"width": 400, "height": 300, "thickness": 19}, "children": [{"Place": {"layout": layout}}]}
        )
        with pytest.raises(PMLParseError, match=r"Place.layout must be a Grid.*PM-18"):
            parse_pml_yaml(source)

    @pytest.mark.parametrize("layout", [{}, [], None, False])
    def test_supplied_empty_or_invalid_layout_rejected(self, layout):
        with pytest.raises(PMLParseError):
            parse_node({"Place": {"layout": layout}})

    def test_layout_grid_children_rejected(self):
        source = (
            MINIMAL_SHEET
            + "children: [{Place: {layout: {Grid: {rows: 1, cols: 1, children: [{Rect: {feature: {type: pocket, depth: 2}}}]}}}}]"
        )
        with pytest.raises(PMLParseError, match=r"put them in Place.children.*PM-18"):
            parse_pml_yaml(source)

    @pytest.mark.parametrize(
        "layout, bounds",
        [
            ({"Grid": {"rows": 1, "cols": 2, "gap": 20}}, [(0, 240), (260, 500)]),
            (None, [(0, 500), (0, 500)]),
        ],
    )
    def test_supported_layout_controls_resolved_pockets(self, layout, bounds):
        from adapters.ast_to_removal import ast_to_removal_intents
        from pml.yaml_formatter import format_pml_yaml
        from resolution.layout_resolver import resolve_layout

        place = {"children": [{"Rect": {"feature": {"type": "pocket", "depth": 2}}}] * 2}
        if layout is not None:
            place["layout"] = layout
        ast = parse_pml_yaml(
            json.dumps({"Sheet": {"width": 500, "height": 200, "thickness": 19}, "children": [{"Place": place}]})
        )
        assert parse_pml_yaml(format_pml_yaml(ast)) == ast
        intents = ast_to_removal_intents(resolve_layout(ast))
        assert [(intent.bounds.x_min, intent.bounds.x_max) for intent in intents] == bounds
        assert all(intent.depth_profile.z_bottom == -2 for intent in intents)


class TestDimensionConflicts:
    @pytest.mark.parametrize("axis", ["width", "height"])
    @pytest.mark.parametrize("margin", [0, 10])
    @pytest.mark.parametrize("keys", [("", "physical_"), ("", "working_"), ("physical_", "working_")])
    def test_conflicting_sheet_dimensions_rejected(self, axis, margin, keys):
        sheet = {"width": 500, "height": 400, "thickness": 19, "margin": margin}
        del sheet[axis]
        sheet[keys[0] + axis] = 500 - (2 * margin if keys[0] == "working_" else 0)
        sheet[keys[1] + axis] = 501 - (2 * margin if keys[1] == "working_" else 0)
        with pytest.raises(PMLParseError, match=rf"Conflicting Sheet {axis}.*expected matching dimensions.*PM-18"):
            parse_pml_yaml(json.dumps({"Sheet": sheet}))

    @pytest.mark.parametrize("margin", [0, 10])
    def test_equivalent_sheet_dimensions_resolve_identically(self, margin):
        from pml.yaml_formatter import format_pml_yaml

        base = {"width": 500, "height": 400, "thickness": 19, "margin": margin}
        expected = parse_pml_yaml(json.dumps({"Sheet": base}))
        redundant = {
            **base,
            "physical_width": 500,
            "physical_height": 400,
            "working_width": 500 - 2 * margin,
            "working_height": 400 - 2 * margin,
        }
        actual = parse_pml_yaml(json.dumps({"Sheet": redundant}))
        assert actual == expected
        assert parse_pml_yaml(format_pml_yaml(actual)) == actual

    @pytest.mark.parametrize("key, primary, nested", [("thickness", 18, 6), ("inset", 10, 5), ("inset", 0, 5)])
    @pytest.mark.parametrize("assembly_type", ["carcass", "cubby"])
    def test_conflicting_back_dimensions_rejected(self, key, primary, nested, assembly_type):
        data = {
            **MINIMAL_NODE_DATA["Assembly"],
            "type": assembly_type,
            f"back_{key}": primary,
            "back": {"joinery": "captured", key: nested},
        }
        with pytest.raises(PMLParseError, match=rf"Conflicting back_{key}.*back.{key}.*PM-18"):
            parse_node({"Assembly": data})

    @pytest.mark.parametrize("assembly_type", ["carcass", "cubby"])
    @pytest.mark.parametrize("flat, nested", [(12, 0), (12, 12), (0, 0)])
    def test_back_inset_default_and_equivalent_forms_preserved(self, assembly_type, flat, nested):
        data = {
            **MINIMAL_NODE_DATA["Assembly"],
            "type": assembly_type,
            "back_inset": flat,
            "back": {"joinery": "captured", "inset": nested},
        }
        node = parse_node({"Assembly": data})
        assert node.back_inset_mm == flat
        assert node.back.inset_mm == nested

    @pytest.mark.parametrize("dimensions", [[], [1, 2, 3, 4], 123, "100mm", None, ["wrong", 200, 300]])
    def test_discarded_dimension_vector_input_rejected(self, dimensions):
        with pytest.raises(PMLParseError, match=r"dimensions.*PM-18"):
            parse_node({"Assembly": {**MINIMAL_NODE_DATA["Assembly"], "dimensions": dimensions}})

    def test_partial_dimension_vector_supplies_only_missing_named_dimensions(self):
        node = parse_node({"Assembly": {"dimensions": [200, 300], "width": 0, "height": 100, "thickness": 19}})
        assert (node.width_mm, node.depth_mm, node.height_mm) == (0, 300, 100)


@pytest.mark.parametrize("assembly_type", ["carcass", "cubby"])
def test_equivalent_back_thickness_forms_round_trip(assembly_type):
    from pml.yaml_formatter import format_pml_yaml

    base = {
        "type": assembly_type,
        "width": 600,
        "depth": 300,
        "height": 600,
        "thickness": 18,
        "back": {"joinery": "captured"},
        "back_thickness": 18,
    }
    sheet = {"width": 2000, "height": 2000, "thickness": 18}
    expected = parse_pml_yaml(json.dumps({"Sheet": sheet, "children": [{"Assembly": base}]}))
    duplicate = {**base, "back": {"joinery": "captured", "thickness": "18mm"}}
    actual = parse_pml_yaml(json.dumps({"Sheet": sheet, "children": [{"Assembly": duplicate}]}))
    assert actual == expected
    assert parse_pml_yaml(format_pml_yaml(actual)) == actual
