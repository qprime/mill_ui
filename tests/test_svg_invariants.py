from __future__ import annotations

import os

import pytest

from validation.core import Verdict
from validation.invariants.svg_invariants import (
    SVG_INVARIANT_IDS,
    check_svg_invariants,
)

RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_svg_path(recipe_num: int, recipe_name: str, filename: str) -> str:
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        filename,
    )


def test_valid_simple_profile_svg():
    """Test that simple profile SVG passes all invariants."""
    svg_path = get_recipe_svg_path(1, "simple_profile", "01_simple_profile.svg")

    if not os.path.exists(svg_path):
        pytest.skip(f"{svg_path} not found")

    with open(svg_path, encoding="utf-8") as f:
        svg_content = f.read()

    results = check_svg_invariants(svg_content)

    result_ids = [r.id for r in results]
    for inv_id in SVG_INVARIANT_IDS:
        assert inv_id in result_ids, f"Missing invariant check: {inv_id}"

    for r in results:
        assert r.status in (Verdict.PASS, Verdict.WARN), f"{r.id} failed: {r.failures}"


def test_valid_shaker_door_svg():
    """Test that shaker door SVG (with pockets) passes all invariants."""
    svg_path = get_recipe_svg_path(3, "shaker_door_template", "03_shaker_door_template.svg")

    if not os.path.exists(svg_path):
        pytest.skip(f"{svg_path} not found")

    with open(svg_path, encoding="utf-8") as f:
        svg_content = f.read()

    results = check_svg_invariants(svg_content)

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert len(failures) == 0, f"Unexpected failures: {[(f.id, f.failures) for f in failures]}"


def test_valid_multiple_depths_svg():
    """Test that multiple depths SVG passes all invariants."""
    svg_path = get_recipe_svg_path(6, "multiple_depths", "06_multiple_depths.svg")

    if not os.path.exists(svg_path):
        pytest.skip(f"{svg_path} not found")

    with open(svg_path, encoding="utf-8") as f:
        svg_content = f.read()

    results = check_svg_invariants(svg_content)

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert len(failures) == 0, f"Unexpected failures: {[(f.id, f.failures) for f in failures]}"


def test_invalid_xml():
    """Test that invalid XML fails SVG_VALID_XML invariant."""
    invalid_svg = "<svg><unclosed"

    results = check_svg_invariants(invalid_svg)

    assert len(results) == 1
    assert results[0].id == "SVG_VALID_XML"
    assert results[0].status == Verdict.FAIL
    assert "parse error" in str(results[0].failures).lower()


def test_empty_content():
    """Test that empty content fails SVG_VALID_XML."""
    results = check_svg_invariants("")

    assert len(results) >= 1
    assert results[0].id == "SVG_VALID_XML"
    assert results[0].status == Verdict.FAIL


def test_missing_viewbox():
    """Test that SVG without viewBox fails SVG_HAS_VIEWBOX."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    viewbox_result = next(r for r in results if r.id == "SVG_HAS_VIEWBOX")
    assert viewbox_result.status == Verdict.FAIL
    assert "viewBox" in str(viewbox_result.failures)


def test_valid_viewbox():
    """Test that SVG with viewBox passes SVG_HAS_VIEWBOX."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    viewbox_result = next(r for r in results if r.id == "SVG_HAS_VIEWBOX")
    assert viewbox_result.status == Verdict.PASS


def test_comma_separated_viewbox():
    """Test that SVG with comma-separated viewBox passes (valid SVG syntax)."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,100,100" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    viewbox_result = next(r for r in results if r.id == "SVG_HAS_VIEWBOX")
    assert viewbox_result.status == Verdict.PASS
    assert viewbox_result.details.get("viewbox") == [0, 0, 100, 100]


def test_zero_dimensions():
    """Test that SVG with zero dimensions fails SVG_POSITIVE_DIMENSIONS."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="0mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    dim_result = next(r for r in results if r.id == "SVG_POSITIVE_DIMENSIONS")
    assert dim_result.status == Verdict.FAIL
    assert "not positive" in str(dim_result.failures).lower()


def test_invalid_path_d():
    """Test that paths with invalid d attribute fail SVG_PATHS_VALID."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="X 0 0 L 100 100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    path_result = next(r for r in results if r.id == "SVG_PATHS_VALID")
    assert path_result.status == Verdict.FAIL
    assert "doesn't start with M" in str(path_result.failures)


def test_empty_path_d():
    """Test that paths with empty d attribute fail SVG_PATHS_VALID."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d=""/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    path_result = next(r for r in results if r.id == "SVG_PATHS_VALID")
    assert path_result.status == Verdict.FAIL
    assert "empty" in str(path_result.failures).lower()


def test_valid_paths():
    """Test that valid paths pass SVG_PATHS_VALID."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="M 0 0 L 100 0 L 100 100 L 0 100 Z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    path_result = next(r for r in results if r.id == "SVG_PATHS_VALID")
    assert path_result.status == Verdict.PASS


def test_unclosed_profile():
    """Test that unclosed profile paths fail SVG_CLOSED_PROFILES."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="M 0 0 L 100 0 L 100 100 L 0 100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.FAIL
    assert "not closed" in str(profile_result.failures).lower()


def test_closed_profile_path():
    """Test that closed profile paths pass SVG_CLOSED_PROFILES."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="M 0 0 L 100 0 L 100 100 L 0 100 Z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS


def test_profile_rect_inherently_closed():
    """Test that rect elements in profile layer count as closed."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS
    assert profile_result.checked == 1
    assert profile_result.passed == 1


def test_profile_polygon_inherently_closed():
    """Test that polygon elements in profile layer count as closed."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <polygon points="10,10 90,10 90,90 10,90"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS
    assert profile_result.checked == 1
    assert profile_result.passed == 1


def test_profile_polyline_closed():
    """Test that closed polyline in profile layer passes."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <polyline points="10,10 90,10 90,90 10,90 10,10"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS
    assert profile_result.checked == 1
    assert profile_result.passed == 1


def test_profile_polyline_unclosed():
    """Test that unclosed polyline in profile layer fails."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <polyline points="10,10 90,10 90,90 10,90"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.FAIL
    assert "not closed" in str(profile_result.failures).lower()


def test_unclosed_pocket():
    """Test that unclosed pocket paths fail SVG_CLOSED_POCKETS."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="POCKET_REGIONS">
            <path d="M 20 20 L 80 20 L 80 80 L 20 80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    pocket_result = next(r for r in results if r.id == "SVG_CLOSED_POCKETS")
    assert pocket_result.status == Verdict.FAIL
    assert "not closed" in str(pocket_result.failures).lower()


def test_closed_pocket():
    """Test that closed pocket paths pass SVG_CLOSED_POCKETS."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="POCKET_REGIONS">
            <path d="M 20 20 L 80 20 L 80 80 L 20 80 z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    pocket_result = next(r for r in results if r.id == "SVG_CLOSED_POCKETS")
    assert pocket_result.status == Verdict.PASS


def test_empty_expected_layer():
    """Test that empty expected layers produce warning."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
        </g>
    </svg>
    """

    results = check_svg_invariants(svg, expected_layers=["SHEET_OUTLINE"])

    layer_result = next(r for r in results if r.id == "SVG_NO_EMPTY_LAYERS")
    assert layer_result.status == Verdict.WARN
    assert "empty" in str(layer_result.failures).lower()


def test_nonempty_expected_layer():
    """Test that non-empty expected layers pass."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="0" y="0" width="100" height="100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg, expected_layers=["SHEET_OUTLINE"])

    layer_result = next(r for r in results if r.id == "SVG_NO_EMPTY_LAYERS")
    assert layer_result.status == Verdict.PASS


def test_missing_expected_layer():
    """Test that missing expected layers produce warning."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <rect x="0" y="0" width="100" height="100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg, expected_layers=["SHEET_OUTLINE", "PROFILE_CUTS"])

    layer_result = next(r for r in results if r.id == "SVG_NO_EMPTY_LAYERS")
    assert layer_result.status == Verdict.WARN
    assert "missing" in str(layer_result.failures).lower()
    assert layer_result.checked == 2
    assert layer_result.passed == 1


def test_no_dimensions():
    """Test that SVG without dimensions produces warning."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    dim_result = next(r for r in results if r.id == "SVG_DIMENSIONS_PRESENT")
    assert dim_result.status == Verdict.WARN


def test_dimensions_in_layer():
    """Test that SVG with DIMENSIONS layer content passes."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="DIMENSIONS">
            <line x1="0" y1="0" x2="100" y2="0"/>
            <text x="50" y="10">100mm</text>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    dim_result = next(r for r in results if r.id == "SVG_DIMENSIONS_PRESENT")
    assert dim_result.status == Verdict.PASS


def test_content_within_viewbox():
    """Test that content within viewBox passes."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    bounds_result = next(r for r in results if r.id == "SVG_BOUNDS_WITHIN_VIEWBOX")
    assert bounds_result.status == Verdict.PASS


def test_content_outside_viewbox():
    """Test that content outside viewBox fails."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="-10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    bounds_result = next(r for r in results if r.id == "SVG_BOUNDS_WITHIN_VIEWBOX")
    assert bounds_result.status == Verdict.FAIL
    assert "x_min" in str(bounds_result.failures)


def test_all_recipe_svgs_pass():
    """Test that all recipe SVGs pass invariants (no false positives)."""
    recipe_svgs = [
        (1, "simple_profile", "01_simple_profile.svg"),
        (2, "pocket_with_cleanup", "02_pocket_with_cleanup.svg"),
        (3, "shaker_door_template", "03_shaker_door_template.svg"),
        (4, "custom_template", "04_custom_template.svg"),
        (5, "validation_workflow", "05_validation_workflow.svg"),
        (6, "multiple_depths", "06_multiple_depths.svg"),
        (7, "json_generation", "07_json_generation.svg"),
        (8, "svg_visualization", "08_svg_visualization.svg"),
        (9, "config_tuning", "09_config_tuning.svg"),
        (10, "hole_patterns_grid", "10_hole_patterns_grid.svg"),
        (11, "keepout_islands", "11_keepout_islands.svg"),
        (12, "edge_treatment_intent", "12_edge_treatment_intent.svg"),
        (13, "split_layout_french_door", "13_split_layout_french_door.svg"),
        (14, "corner_cleanup_multi_tool", "14_corner_cleanup_multi_tool.svg"),
        (15, "profile_with_tabs", "15_profile_with_tabs.svg"),
        (16, "sheet_layout_nesting", "16_sheet_layout_nesting.svg"),
    ]

    passed = 0
    skipped = 0
    failed_svgs = []

    for recipe_num, recipe_name, filename in recipe_svgs:
        svg_path = get_recipe_svg_path(recipe_num, recipe_name, filename)

        if not os.path.exists(svg_path):
            skipped += 1
            continue

        with open(svg_path, encoding="utf-8") as f:
            svg_content = f.read()

        results = check_svg_invariants(svg_content)

        failures = [r for r in results if r.status == Verdict.FAIL]
        if failures:
            failed_svgs.append((filename, [(f.id, f.failures) for f in failures]))
        else:
            passed += 1

    if failed_svgs:
        raise AssertionError(f"{len(failed_svgs)} recipe SVGs failed invariants")


def test_nesting_output_svgs():
    """Test that nesting output SVGs pass invariants."""
    nesting_svgs = []

    for i in range(1, 7):
        nesting_svgs.append((17, "nesting_guillotine", f"sheet_{i}.svg"))

    for i in range(1, 7):
        nesting_svgs.append((18, "nesting_maxrects", f"sheet_{i}.svg"))

    passed = 0
    skipped = 0
    failed_svgs = []

    for recipe_num, recipe_name, filename in nesting_svgs:
        svg_path = get_recipe_svg_path(recipe_num, recipe_name, filename)

        if not os.path.exists(svg_path):
            skipped += 1
            continue

        with open(svg_path, encoding="utf-8") as f:
            svg_content = f.read()

        results = check_svg_invariants(svg_content)

        failures = [r for r in results if r.status == Verdict.FAIL]
        if failures:
            failed_svgs.append((filename, [(f.id, f.failures) for f in failures]))
        else:
            passed += 1

    if failed_svgs:
        raise AssertionError(f"{len(failed_svgs)} nesting SVGs failed invariants")


def test_invariant_result_to_dict():
    """Test that invariant results serialize correctly."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    for r in results:
        d = r.to_dict()
        assert "invariant" in d
        assert "id" in d["invariant"]
        assert "category" in d["invariant"]
        assert "artifact" in d["invariant"]
        assert "description" in d["invariant"]
        assert "status" in d["invariant"]
        assert "details" in d["invariant"]


def test_all_invariant_ids_present():
    """Test that all expected invariant IDs are returned."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="0" y="0" width="100" height="100"/>
        </g>
        <g id="PROFILE_CUTS">
            <path d="M 10 10 L 90 10 L 90 90 L 10 90 Z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)
    result_ids = [r.id for r in results]

    for expected_id in SVG_INVARIANT_IDS:
        assert expected_id in result_ids, f"Missing invariant: {expected_id}"
