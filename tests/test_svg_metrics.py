# tests/test_svg_metrics.py - Unit tests for SVG metric extraction
#
# Tests verify:
# 1. Correct metric extraction from known SVG files
# 2. Determinism (same input -> same output)
# 3. JSON serialization
# 4. Edge cases and error handling

from __future__ import annotations

import json
import os

import pytest

from validation.core import CAMValidationResult
from validation.metrics.svg_metrics import (
    extract_svg_metrics,
    extract_svg_metrics_from_file,
)

# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_svg_path(recipe_num: int, recipe_name: str) -> str:
    """Get path to a recipe's SVG output."""
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        f"{recipe_num:02d}_{recipe_name}.svg",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Basic SVG Parsing
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_svg_metrics_simple_profile():
    """Test metric extraction from simple profile recipe."""
    svg_path = get_recipe_svg_path(1, "simple_profile")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    metrics = extract_svg_metrics_from_file(svg_path)

    assert metrics.document.width_mm > 0, f"Width: {metrics.document.width_mm}"
    assert metrics.document.height_mm > 0, f"Height: {metrics.document.height_mm}"
    assert len(metrics.document.viewbox) == 4, "ViewBox should have 4 components"

    assert metrics.layer_count >= 3, f"Layer count: {metrics.layer_count}"
    assert "SHEET_OUTLINE" in metrics.layer_names
    assert "PROFILE_CUTS" in metrics.layer_names

    assert metrics.paths.total_count >= 1, f"Path count: {metrics.paths.total_count}"
    assert metrics.paths.closed_count >= 1, f"Closed count: {metrics.paths.closed_count}"


def test_extract_svg_metrics_shaker_door():
    """Test metric extraction from shaker door recipe."""
    svg_path = get_recipe_svg_path(3, "shaker_door_template")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    metrics = extract_svg_metrics_from_file(svg_path)

    assert metrics.document.width_mm > 0
    assert metrics.document.height_mm > 0

    assert "POCKET_REGIONS" in metrics.layer_names
    pocket_layer = metrics.layers.get("POCKET_REGIONS")
    assert pocket_layer is not None
    assert pocket_layer.rect_count >= 1, f"Pocket rects: {pocket_layer.rect_count}"

    # Should have profile layer with content
    assert "PROFILE_CUTS" in metrics.layer_names
    profile_layer = metrics.layers.get("PROFILE_CUTS")
    assert profile_layer is not None
    assert profile_layer.rect_count >= 1, f"Profile rects: {profile_layer.rect_count}"

    # Text elements should include dimensions
    assert metrics.text.count >= 1, f"Text count: {metrics.text.count}"
    assert len(metrics.text.dimension_labels) >= 1, f"Dimensions: {metrics.text.dimension_labels}"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Determinism
# ─────────────────────────────────────────────────────────────────────────────


def test_svg_metrics_deterministic():
    """Verify same input produces identical metrics."""
    svg_path = get_recipe_svg_path(1, "simple_profile")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    # Extract twice
    metrics1 = extract_svg_metrics_from_file(svg_path)
    metrics2 = extract_svg_metrics_from_file(svg_path)

    # Convert to dict (excluding timing)
    dict1 = metrics1.to_dict()
    dict2 = metrics2.to_dict()

    # Remove extraction time (will differ)
    dict1["svg"]["extraction_time_ms"] = 0
    dict2["svg"]["extraction_time_ms"] = 0

    # Compare
    assert dict1 == dict2, "Metrics should be deterministic"


def test_svg_metrics_deterministic_from_string():
    """Verify string input produces same metrics as file."""
    svg_path = get_recipe_svg_path(1, "simple_profile")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    # Read file content
    with open(svg_path) as f:
        svg_content = f.read()

    # Extract from file and string
    metrics_file = extract_svg_metrics_from_file(svg_path)
    metrics_string = extract_svg_metrics(svg_content)

    # Convert to dict (excluding timing)
    dict1 = metrics_file.to_dict()
    dict2 = metrics_string.to_dict()
    dict1["svg"]["extraction_time_ms"] = 0
    dict2["svg"]["extraction_time_ms"] = 0

    assert dict1 == dict2, "File and string extraction should match"


# ─────────────────────────────────────────────────────────────────────────────
# Test: JSON Serialization
# ─────────────────────────────────────────────────────────────────────────────


def test_svg_metrics_json_serializable():
    """Verify metrics can be serialized to JSON."""
    svg_path = get_recipe_svg_path(1, "simple_profile")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    metrics = extract_svg_metrics_from_file(svg_path)
    metrics_dict = metrics.to_dict()

    # Should serialize without error
    json_str = json.dumps(metrics_dict, indent=2)
    assert len(json_str) > 0

    # Should deserialize back
    parsed = json.loads(json_str)
    assert "svg" in parsed
    assert "document" in parsed["svg"]
    assert "layers" in parsed["svg"]


def test_svg_metrics_schema_compliance():
    """Verify output matches expected schema structure."""
    svg_path = get_recipe_svg_path(3, "shaker_door_template")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    metrics = extract_svg_metrics_from_file(svg_path)
    d = metrics.to_dict()

    # Top level
    assert "svg" in d
    svg = d["svg"]

    # Required fields
    assert "version" in svg
    assert "extraction_time_ms" in svg
    assert "document" in svg
    assert "layers" in svg
    assert "paths" in svg
    assert "bounds" in svg
    assert "text_elements" in svg
    assert "circles" in svg
    assert "rects" in svg

    # Document fields
    doc = svg["document"]
    assert "width_mm" in doc
    assert "height_mm" in doc
    assert "viewbox" in doc
    assert len(doc["viewbox"]) == 4

    # Layers fields
    layers = svg["layers"]
    assert "count" in layers
    assert "names" in layers
    assert "by_layer" in layers

    # Paths fields
    paths = svg["paths"]
    assert "total_count" in paths
    assert "closed_count" in paths
    assert "open_count" in paths


# ─────────────────────────────────────────────────────────────────────────────
# Test: Edge Cases
# ─────────────────────────────────────────────────────────────────────────────


def test_svg_metrics_empty_layers():
    """Test handling of empty layers."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="EMPTY_LAYER"></g>
        <g id="WITH_CONTENT">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert "EMPTY_LAYER" in metrics.layer_names
    assert "WITH_CONTENT" in metrics.layer_names
    assert metrics.layers["EMPTY_LAYER"].element_count == 0
    assert metrics.layers["WITH_CONTENT"].element_count == 1


def test_svg_metrics_invalid_svg():
    """Test error handling for invalid SVG."""
    invalid_svg = "not valid xml"

    try:
        extract_svg_metrics(invalid_svg)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Invalid SVG" in str(e)


def test_svg_metrics_minimal_svg():
    """Test handling of minimal valid SVG."""
    minimal_svg = """<svg xmlns="http://www.w3.org/2000/svg"></svg>"""

    metrics = extract_svg_metrics(minimal_svg)

    assert metrics.document.width_mm == 0.0
    assert metrics.document.height_mm == 0.0
    assert metrics.layer_count == 0


def test_svg_metrics_with_circles():
    """Test circle metric extraction."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="HOLES">
            <circle cx="25" cy="25" r="5"/>
            <circle cx="75" cy="25" r="5"/>
            <circle cx="50" cy="75" r="10"/>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert metrics.circles.count == 3
    assert sorted(metrics.circles.radii_mm) == [5.0, 5.0, 10.0]


def test_svg_metrics_bounds_exclude_background():
    """Test that bounds exclude background rect (Codex review feedback)."""
    # SVG with background rect covering full viewBox and content rect inside
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 730 930" width="730mm" height="930mm">
        <rect x="0" y="0" width="730" height="930" fill="#1a1a1a"/>
        <g id="SHEET_OUTLINE">
            <rect x="140" y="140" width="450" height="650"/>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    # Bounds should be from SHEET_OUTLINE, not background
    assert metrics.bounds.x_min == 140.0, f"x_min should be 140, got {metrics.bounds.x_min}"
    assert metrics.bounds.y_min == 140.0, f"y_min should be 140, got {metrics.bounds.y_min}"
    assert metrics.bounds.x_max == 590.0, f"x_max should be 590, got {metrics.bounds.x_max}"
    assert metrics.bounds.y_max == 790.0, f"y_max should be 790, got {metrics.bounds.y_max}"

    # Rects count should also exclude background
    assert metrics.rects.count == 1, f"Should have 1 rect (excluding bg), got {metrics.rects.count}"


def test_svg_metrics_dimension_text():
    """Test dimension label extraction."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="DIMENSIONS">
            <text x="50" y="10">200.0mm</text>
            <text x="90" y="50">150.0mm</text>
        </g>
        <g id="NOTES">
            <text x="10" y="90">Sheet: 450 x 650mm</text>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert metrics.text.count == 3
    assert "200.0mm" in metrics.text.dimension_labels
    assert "150.0mm" in metrics.text.dimension_labels


# ─────────────────────────────────────────────────────────────────────────────
# Test: All Recipes (Smoke Test)
# ─────────────────────────────────────────────────────────────────────────────


def test_svg_metrics_all_recipes():
    """Smoke test: extract metrics from all recipe SVGs without error."""
    import glob

    # Single-SVG recipes (output/NN_name.svg)
    single_svg_recipes = [
        (1, "simple_profile"),
        (2, "pocket_with_cleanup"),
        (3, "shaker_door_template"),
        (4, "custom_template"),
        (5, "validation_workflow"),
        (6, "multiple_depths"),
        (7, "json_generation"),
        (8, "svg_visualization"),
        (9, "config_tuning"),
        (10, "hole_patterns_grid"),
        (11, "keepout_islands"),
        (12, "edge_treatment_intent"),
        (13, "split_layout_french_door"),
        (14, "corner_cleanup_multi_tool"),
        (15, "profile_with_tabs"),
        (16, "sheet_layout_nesting"),
    ]

    # Multi-sheet recipes (output/sheet_*.svg)
    multi_sheet_recipes = [
        (17, "nesting_guillotine"),
        (18, "nesting_maxrects"),
    ]

    passed = 0
    skipped = 0
    failed = 0

    # Test single-SVG recipes
    for num, name in single_svg_recipes:
        svg_path = get_recipe_svg_path(num, name)
        if not os.path.exists(svg_path):
            skipped += 1
            continue

        try:
            metrics = extract_svg_metrics_from_file(svg_path)
            assert metrics.document.width_mm > 0
            assert metrics.document.height_mm > 0
            assert metrics.layer_count > 0
            passed += 1
        except Exception as e:
            print(f"FAIL: Recipe {num:02d}_{name}: {e}")
            failed += 1

    # Test multi-sheet recipes
    for num, name in multi_sheet_recipes:
        recipe_dir = os.path.join(RECIPE_DIR, f"{num:02d}_{name}", "output")
        if not os.path.exists(recipe_dir):
            skipped += 1
            continue

        # Find all sheet_*.svg files (exclude macOS ._ files)
        sheet_svgs = sorted(
            f for f in glob.glob(os.path.join(recipe_dir, "sheet_*.svg")) if not os.path.basename(f).startswith("._")
        )

        if not sheet_svgs:
            skipped += 1
            continue

        for svg_path in sheet_svgs:
            try:
                metrics = extract_svg_metrics_from_file(svg_path)
                assert metrics.document.width_mm > 0
                assert metrics.document.height_mm > 0
                assert metrics.layer_count > 0
                passed += 1
            except Exception as e:
                print(f"FAIL: {os.path.basename(svg_path)} in {num:02d}_{name}: {e}")
                failed += 1

    assert failed == 0, f"{failed} recipes failed"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Core Types Integration
# ─────────────────────────────────────────────────────────────────────────────


def test_cam_validation_result_with_svg_metrics():
    """Test integration of SVG metrics into CAMValidationResult."""
    svg_path = get_recipe_svg_path(1, "simple_profile")

    if not os.path.exists(svg_path):
        pytest.skip("{svg_path} not found")

    metrics = extract_svg_metrics_from_file(svg_path)

    # Create validation result with metrics
    result = CAMValidationResult(input_file="simple_profile.pml.yml")
    result.metrics["svg"] = metrics.to_dict()["svg"]

    # Should serialize
    json_str = result.to_json()
    assert len(json_str) > 0

    # Parse and verify
    parsed = json.loads(json_str)
    assert "validation_result" in parsed
    assert "metrics" in parsed["validation_result"]
    assert "svg" in parsed["validation_result"]["metrics"]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
