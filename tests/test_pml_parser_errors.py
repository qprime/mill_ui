from __future__ import annotations

import pytest

from pml.nest_parser import NestParseError
from pml.yaml_parser import PMLParseError, parse_node, parse_pml_yaml

MINIMAL_SHEET = "Sheet:\n  width: 200\n  height: 200\n  thickness: 19\n"


class TestRequireMissingKey:
    def test_missing_required_key_raises(self) -> None:
        with pytest.raises(PMLParseError, match="Missing required key 'width'"):
            parse_node({"Frame": {"height": 10}}, "test")


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
            "Panel": {
                "width": 100,
                "height": 100,
                "feature": {
                    "type": "profile",
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


class TestGridCoercion:
    def test_invalid_grid_values_raises_pml_error(self) -> None:
        with pytest.raises(PMLParseError, match="grid"):
            parse_node(
                {
                    "Assembly": {
                        "type": "box",
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
        with pytest.raises(NestParseError, match="Unknown key"):
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
