from nesting.api import nest_and_generate, nest_parts
from nesting.maxrects import MaxRectsHeuristic, maxrects_pack


def test_maxrects_basic():
    parts = [
        (100, 100, False, "p1"),
        (100, 100, False, "p2"),
        (100, 100, False, "p3"),
        (100, 100, False, "p4"),
    ]

    placements = maxrects_pack(
        parts=parts,  # type: ignore[arg-type]
        bin_width=300,
        bin_height=300,
        gap=0,
    )

    assert len(placements) == 4

    positions = [(p.x, p.y) for p in placements]
    assert len(set(positions)) == 4


def test_maxrects_with_gap():
    parts = [
        (100, 100, False, "p1"),
        (100, 100, False, "p2"),
    ]

    placements = maxrects_pack(
        parts=parts,  # type: ignore[arg-type]
        bin_width=250,
        bin_height=150,
        gap=10,
    )

    assert len(placements) == 2

    for p in placements:
        assert p.x + 100 + 10 <= 250 or p.x == placements[-1].x
        assert p.y + 100 + 10 <= 150 or p.y == placements[-1].y


def test_maxrects_rotation():
    parts = [
        (200, 100, True, "p1"),
    ]

    placements = maxrects_pack(
        parts=parts,  # type: ignore[arg-type]
        bin_width=150,
        bin_height=250,
        gap=0,
    )

    assert len(placements) == 1
    assert placements[0].rotated is True


def test_maxrects_no_rotation():
    parts = [
        (200, 100, False, "p1"),
    ]

    placements = maxrects_pack(
        parts=parts,  # type: ignore[arg-type]
        bin_width=150,
        bin_height=250,
        gap=0,
    )

    assert len(placements) == 0


def test_maxrects_heuristics():
    parts = [
        (100, 150, True, "p1"),
        (80, 120, True, "p2"),
        (60, 90, True, "p3"),
    ]

    for heuristic in MaxRectsHeuristic:
        placements = maxrects_pack(
            parts=parts,  # type: ignore[arg-type]
            bin_width=300,
            bin_height=300,
            gap=5,
            heuristic=heuristic,
        )
        assert len(placements) == 3, f"Heuristic {heuristic.name} failed"


def test_maxrects_contact_point():
    parts = [
        (50, 50, False, "p1"),
        (50, 50, False, "p2"),
        (50, 50, False, "p3"),
        (50, 50, False, "p4"),
    ]

    placements = maxrects_pack(
        parts=parts,  # type: ignore[arg-type]
        bin_width=200,
        bin_height=200,
        gap=0,
        heuristic=MaxRectsHeuristic.CONTACT_POINT,
    )

    assert len(placements) == 4

    for i, p1 in enumerate(placements):
        for j, p2 in enumerate(placements):
            if i >= j:
                continue

            x1_max = p1.x + 50
            x2_max = p2.x + 50
            y1_max = p1.y + 50
            y2_max = p2.y + 50
            overlaps = not (p1.x >= x2_max or p2.x >= x1_max or p1.y >= y2_max or p2.y >= y1_max)
            assert not overlaps, f"Parts {i} and {j} overlap"


def test_maxrects_api_integration():
    parts = [
        {"name": "panel", "width_mm": 400, "height_mm": 300, "quantity": 4},
    ]

    result = nest_parts(
        parts=parts,
        sheet_width_mm=1000,
        sheet_height_mm=1000,
        sheet_thickness_mm=19,
        algorithm="maxrects",
    )

    assert result["total_parts"] == 4
    assert result["total_sheets"] >= 1


def test_maxrects_vs_guillotine():
    parts = [
        {"name": "large_door", "width_mm": 457, "height_mm": 597, "quantity": 20},
        {"name": "small_door", "width_mm": 305, "height_mm": 203, "quantity": 15},
        {"name": "tall_door", "width_mm": 457, "height_mm": 914, "quantity": 2},
    ]

    guillotine_result = nest_parts(
        parts=parts,
        sheet_width_mm=1220,
        sheet_height_mm=2440,
        sheet_thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
        algorithm="guillotine",
    )

    maxrects_result = nest_parts(
        parts=parts,
        sheet_width_mm=1220,
        sheet_height_mm=2440,
        sheet_thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
        algorithm="maxrects",
    )

    assert maxrects_result["utilization_percent"] >= guillotine_result["utilization_percent"] - 5

    assert maxrects_result["total_sheets"] <= guillotine_result["total_sheets"]


def test_maxrects_generate_ast():
    parts = [
        {"name": "panel", "width_mm": 300, "height_mm": 300, "quantity": 2},
    ]

    result = nest_and_generate(
        parts=parts,
        sheet_width_mm=800,
        sheet_height_mm=800,
        sheet_thickness_mm=19,
        output_format="ast",
        algorithm="maxrects",
    )

    assert result["output_format"] == "ast"
    assert len(result["output"]) >= 1

    ast = result["output"][0]
    assert hasattr(ast, "sheet")
    assert hasattr(ast, "items")


def test_maxrects_invalid_algorithm():
    parts = [{"name": "panel", "width_mm": 100, "height_mm": 100}]

    try:
        nest_parts(
            parts=parts,
            sheet_width_mm=500,
            sheet_height_mm=500,
            sheet_thickness_mm=19,
            algorithm="invalid_algo",
        )
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Invalid algorithm" in str(e)
