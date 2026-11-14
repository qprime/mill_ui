import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from nesting.api import nest_and_generate, nest_parts
from validation.removal_checks import check_working_area_bounds


def test_basic_nesting_api():
    parts = [
        {"name": "panel", "width_mm": 400, "height_mm": 300, "quantity": 4},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=1000,
        sheet_thickness_mm=19,
    )

    assert "sheets" in result
    assert result["total_parts"] == 4
    assert result["total_sheets"] >= 1
    assert "utilization" in result


def test_api_with_template():
    parts = [
        {
            "name": "door",
            "width_mm": 400,
            "height_mm": 600,
            "quantity": 2,
            "template": "Shaker",
            "template_params": {
                "stile_w": 50,
                "rail_h": 50,
                "panel_recess": 6,
            },
        },
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=1000,
        sheet_thickness_mm=19,
    )

    assert result["total_parts"] == 2


def test_api_validation():
    parts = [
        {"name": "panel", "width_mm": 200, "height_mm": 200, "quantity": 1},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        validate=True,
    )

    assert "validation" in result
    assert result["validation"] is not None
    assert "is_valid" in result["validation"]


def test_api_no_validation():
    parts = [
        {"name": "panel", "width_mm": 200, "height_mm": 200, "quantity": 1},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        validate=False,
    )

    assert result["validation"] is None


def test_api_unplaced_parts():
    parts = [
        {"name": "huge", "width_mm": 2000, "height_mm": 2000, "quantity": 1},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
    )

    assert result["total_parts"] == 0
    assert len(result["unplaced"]) == 1
    assert result["unplaced"][0]["name"] == "huge"


def test_api_max_sheets():
    parts = [
        {"name": "panel", "width_mm": 400, "height_mm": 400, "quantity": 10},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=500,
        sheet_height_mm=500,
        sheet_thickness_mm=19,
        margin_mm=10,
        max_sheets=2,
    )

    assert result["total_sheets"] <= 2


def test_nest_and_generate_ast():
    parts = [
        {"name": "panel", "width_mm": 300, "height_mm": 300, "quantity": 2},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=800,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        output_format="ast",
    )

    assert result["output_format"] == "ast"
    assert len(result["output"]) >= 1

    ast = result["output"][0]
    assert hasattr(ast, "sheet")
    assert hasattr(ast, "items")


def test_user_example():
    parts = [
        {"name": "large_door", "width_mm": 457, "height_mm": 597, "quantity": 20},
        {"name": "small_door", "width_mm": 305, "height_mm": 203, "quantity": 15},
        {"name": "tall_door", "width_mm": 457, "height_mm": 914, "quantity": 2},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1220,
        sheet_height_mm=2440,
        sheet_thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
    )

    print(f"  Total sheets: {result['total_sheets']}")
    print(f"  Total parts placed: {result['total_parts']}")
    print(f"  Utilization: {result['utilization_percent']:.1f}%")

    assert result["total_parts"] >= 35
    assert result["total_sheets"] >= 3


def test_invalid_output_format():
    parts = [{"name": "panel", "width_mm": 100, "height_mm": 100}]

    try:
        nest_and_generate(
            parts=parts,
            sheet_width_mm=500,
            sheet_height_mm=500,
            sheet_thickness_mm=19,
            kerf_mm=6,
            output_format="invalid",
        )
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Invalid output_format" in str(e)
        assert "invalid" in str(e)


@pytest.mark.parametrize("algorithm", ["guillotine", "maxrects"])
@pytest.mark.parametrize("margin", [0, 10, 25])
@pytest.mark.parametrize("padding", [0, 0.1])
def test_nested_machining_reserves_cutter_clearance_in_working_coordinates(algorithm, margin, padding):
    kerf = 6.35
    width, height = 200, 100
    params = {
        "parts": [{"name": "panel", "width_mm": width, "height_mm": height, "allow_rotation": False}],
        "sheet_width_mm": width + 2 * (margin + kerf) + padding,
        "sheet_height_mm": height + 2 * (margin + kerf) + padding,
        "sheet_thickness_mm": 19,
        "margin_mm": margin,
        "kerf_mm": kerf,
        "algorithm": algorithm,
    }

    result = nest_and_generate(**params)
    packed = nest_parts(**params)

    assert result["total_sheets"] == packed["total_sheets"] == 1
    assert packed["validation"]["is_valid"]
    placement = result["nesting_result"].sheets[0].placements[0]
    assert placement.left_mm == pytest.approx(margin + kerf)
    assert placement.bottom_mm == pytest.approx(margin + kerf)
    ast = result["output"][0]
    (intent,) = ast_to_removal_intents(ast)
    assert intent.bounds.x_min == pytest.approx(kerf)
    assert intent.bounds.y_min == pytest.approx(kerf)
    assert intent.bounds.x_max - intent.bounds.x_min == width
    assert intent.bounds.y_max - intent.bounds.y_min == height
    assert not check_working_area_bounds(
        [intent], ast.sheet.working_width_mm, ast.sheet.working_height_mm, tool_radius_mm=kerf / 2
    ).has_issues()


@pytest.mark.parametrize("algorithm", ["guillotine", "maxrects"])
def test_actual_nesting_cutter_contract_and_holding_margin(algorithm):
    from layout_ast.layout import MachiningClearance

    parts = [
        {"name": "p", "width_mm": 100, "height_mm": 60, "quantity": 2, "holding": {"tab_count": 3, "tab_height_mm": 2}}
    ]
    result = nest_and_generate(
        parts,
        223,
        90,
        6,
        margin_mm=10,
        kerf_mm=3,
        gap_margin_mm=3,
        algorithm=algorithm,
        machining_clearance=MachiningClearance(3),
    )
    asts = result["output"]
    assert all(a.machining_clearance == MachiningClearance(3) for a in asts)
    intents = [i for a in asts for i in ast_to_removal_intents(a)]
    assert len({i.part_id for i in intents}) == 2
    with pytest.raises(ValueError, match="smaller than selected profile cutter"):
        nest_and_generate(
            parts, 300, 200, 6, margin_mm=10, kerf_mm=3, algorithm=algorithm, machining_clearance=MachiningClearance(6)
        )
