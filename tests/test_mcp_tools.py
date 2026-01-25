"""Tests for MCP server tools."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    import mcp
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

pytestmark = pytest.mark.skipif(not MCP_AVAILABLE, reason="mcp package not installed")


def test_simple_rect_profile():
    print("Running test_simple_rect_profile...")
    from mill_mcp.server import compile_pml

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            pml = """sheet 450mm 650mm 19mm margin 0mm

rect door at 225mm,325mm size 400mm,600mm profile through outside
"""
            result_json = compile_pml(pml, job_name="test_door")
            result = json.loads(result_json)

            assert "error" not in result
            assert result["job_name"] == "test_door"
            assert result["items"] == 1
            assert result["intents"] == 1
            assert "pml" in result["outputs"]
            assert "svg" in result["outputs"]
            assert len(result["outputs"]["gcode"]) > 0

            # Verify files exist
            assert Path(result["outputs"]["pml"]).exists()
    print("  PASS")
    return True


def test_compositional_pml():
    print("Running test_compositional_pml...")
    from mill_mcp.server import compile_pml

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            pml = """sheet 450mm 650mm 19mm margin 0mm

component Door
    rect outer profile through outside
        inset 50mm
            rect panel pocket 6mm

place grid 1 1 gap 0mm
    use Door
"""
            result_json = compile_pml(pml, job_name="test_comp", compositional=True)
            result = json.loads(result_json)

            assert "error" not in result
            assert result["items"] == 2  # outer + panel
    print("  PASS")
    return True


def test_auto_detect_compositional():
    print("Running test_auto_detect_compositional...")
    from mill_mcp.server import compile_pml

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            pml = """sheet 450mm 650mm 19mm margin 0mm

component Door
    rect outer profile through outside
        frame 50mm
            rect panel pocket 6mm

place grid 1 1 gap 0mm
    use Door
"""
            # Should auto-detect compositional syntax
            result_json = compile_pml(pml, job_name="test_auto")
            result = json.loads(result_json)

            assert "error" not in result
    print("  PASS")
    return True


def test_invalid_pml_returns_error():
    print("Running test_invalid_pml_returns_error...")
    from mill_mcp.server import compile_pml

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            pml = "this is not valid pml"
            result_json = compile_pml(pml)
            result = json.loads(result_json)

            assert "error" in result
            assert result["success"] is False
    print("  PASS")
    return True


def test_simple_nest():
    print("Running test_simple_nest...")
    from mill_mcp.server import compile_nest

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            nest = """nest maxrects
    sheet 1220mm 2440mm 19mm margin 0mm
    kerf 6.35mm
    margin 10mm

    parts
        door 400mm 600mm x2
"""
            result_json = compile_nest(nest, job_name="test_nest")
            result = json.loads(result_json)

            assert "error" not in result
            assert result["nesting"]["algorithm"] == "maxrects"
            assert result["nesting"]["total_sheets"] >= 1
            assert len(result["sheets"]) >= 1
    print("  PASS")
    return True


def test_nest_with_template():
    print("Running test_nest_with_template...")
    from mill_mcp.server import compile_nest

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            nest = """nest guillotine
    sheet 1220mm 2440mm 19mm margin 0mm
    kerf 6.35mm

    parts
        door 400mm 600mm x1
            template Shaker
                stile_w 50mm
                rail_h 50mm
                panel_recess 6mm
"""
            result_json = compile_nest(nest, job_name="test_nest_template")
            result = json.loads(result_json)

            assert "error" not in result
            assert result["sheets"][0]["items"] == 3
    print("  PASS")
    return True


def test_invalid_nest_returns_error():
    print("Running test_invalid_nest_returns_error...")
    from mill_mcp.server import compile_nest

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
            nest = "not valid nest syntax"
            result_json = compile_nest(nest)
            result = json.loads(result_json)

            assert "error" in result
            assert result["success"] is False
    print("  PASS")
    return True


def test_returns_shaker():
    print("Running test_returns_shaker...")
    from mill_mcp.server import list_templates

    result_json = list_templates()
    result = json.loads(result_json)

    assert "Shaker" in result
    assert "required_params" in result["Shaker"]
    assert "outer_w" in result["Shaker"]["required_params"]
    assert "example" in result["Shaker"]
    print("  PASS")
    return True


def test_valid_pml():
    print("Running test_valid_pml...")
    from mill_mcp.server import validate_pml

    pml = """sheet 450mm 650mm 19mm margin 0mm

rect door at 225mm,325mm size 400mm,600mm profile through outside
"""
    result_json = validate_pml(pml)
    result = json.loads(result_json)

    assert result["valid"] is True
    assert result["info"]["items"] == 1
    assert len(result["errors"]) == 0
    print("  PASS")
    return True


def test_invalid_pml():
    print("Running test_invalid_pml...")
    from mill_mcp.server import validate_pml

    pml = "not valid"
    result_json = validate_pml(pml)
    result = json.loads(result_json)

    assert result["valid"] is False
    assert len(result["errors"]) > 0
    print("  PASS")
    return True


def test_get_pml_spec():
    print("Running test_get_pml_spec...")
    from mill_mcp.server import get_syntax_spec

    result = get_syntax_spec("pml")

    assert "PML" in result
    assert "sheet" in result.lower()
    assert "rect" in result.lower()
    print("  PASS")
    return True


def test_get_nest_spec():
    print("Running test_get_nest_spec...")
    from mill_mcp.server import get_syntax_spec

    result = get_syntax_spec("nest")

    assert "nest" in result.lower()
    assert "parts" in result.lower()
    print("  PASS")
    return True


def test_get_all_specs():
    print("Running test_get_all_specs...")
    from mill_mcp.server import get_syntax_spec

    result = get_syntax_spec("all")

    assert "PML" in result
    assert "nest" in result.lower()
    print("  PASS")
    return True


def test_invalid_format():
    print("Running test_invalid_format...")
    from mill_mcp.server import get_syntax_spec

    result = get_syntax_spec("invalid")

    assert "Unknown format" in result
    print("  PASS")
    return True


def test_valid_recipe():
    print("Running test_valid_recipe...")
    from mill_mcp.server import validate_cam_recipe

    # Use a known recipe
    recipe_path = "docs/recipes/01_simple_profile"
    if not Path(recipe_path).exists():
        print("  SKIP: Recipe not found")
        return True

    result_json = validate_cam_recipe(recipe_path)
    result = json.loads(result_json)

    assert "error" not in result
    assert "verdict" in result
    assert result["verdict"] in ("pass", "warn", "fail")
    assert "metrics" in result
    assert "invariants" in result
    print("  PASS")
    return True


def test_nonexistent_recipe():
    print("Running test_nonexistent_recipe...")
    from mill_mcp.server import validate_cam_recipe

    result_json = validate_cam_recipe("/nonexistent/path")
    result = json.loads(result_json)

    assert "error" in result
    assert "not found" in result["error"]
    print("  PASS")
    return True


def test_golden_not_found_error():
    print("Running test_golden_not_found_error...")
    from mill_mcp.server import validate_cam_recipe

    recipe_path = "docs/recipes/01_simple_profile"
    if not Path(recipe_path).exists():
        print("  SKIP: Recipe not found")
        return True

    result_json = validate_cam_recipe(
        recipe_path,
        golden_path="/nonexistent/golden.json"
    )
    result = json.loads(result_json)

    assert "error" in result
    assert "Golden file not found" in result["error"]
    print("  PASS")
    return True


def test_with_golden_regression():
    print("Running test_with_golden_regression...")
    from mill_mcp.server import validate_cam_recipe

    recipe_path = "docs/recipes/01_simple_profile"
    golden_path = "tests/golden/01_simple_profile/metrics.json"

    if not Path(recipe_path).exists():
        print("  SKIP: Recipe not found")
        return True
    if not Path(golden_path).exists():
        print("  SKIP: Golden baseline not found")
        return True

    result_json = validate_cam_recipe(
        recipe_path,
        golden_path=golden_path
    )
    result = json.loads(result_json)

    assert "error" not in result
    assert result["regressions"]["compared"] is True
    print("  PASS")
    return True


def test_svg_validation():
    print("Running test_svg_validation...")
    from mill_mcp.server import validate_cam_artifacts

    svg_path = "docs/recipes/01_simple_profile/output/01_simple_profile.svg"
    if not Path(svg_path).exists():
        print("  SKIP: SVG not found")
        return True

    result_json = validate_cam_artifacts(svg_path=svg_path)
    result = json.loads(result_json)

    assert "error" not in result
    assert "verdict" in result
    assert "svg" in result["metrics"]
    print("  PASS")
    return True


def test_no_artifacts_error():
    print("Running test_no_artifacts_error...")
    from mill_mcp.server import validate_cam_artifacts

    result_json = validate_cam_artifacts()
    result = json.loads(result_json)

    assert "error" in result
    assert "At least one artifact" in result["error"]
    print("  PASS")
    return True


def test_file_not_found():
    print("Running test_file_not_found...")
    from mill_mcp.server import validate_cam_artifacts

    result_json = validate_cam_artifacts(svg_path="/nonexistent/file.svg")
    result = json.loads(result_json)

    assert "error" in result
    assert "not found" in result["error"]
    print("  PASS")
    return True


def test_list_baselines():
    print("Running test_list_baselines...")
    from mill_mcp.server import list_golden_baselines

    result_json = list_golden_baselines()
    result = json.loads(result_json)

    # Should have baselines or indicate store doesn't exist
    assert "baselines" in result
    assert "total" in result
    assert "store_path" in result
    print("  PASS")
    return True


def test_nonexistent_store():
    print("Running test_nonexistent_store...")
    from mill_mcp.server import list_golden_baselines

    result_json = list_golden_baselines(store_path="/nonexistent/store")
    result = json.loads(result_json)

    assert result["total"] == 0
    assert "message" in result or len(result["baselines"]) == 0
    print("  PASS")
    return True


def test_get_metrics():
    print("Running test_get_metrics...")
    from mill_mcp.server import get_golden_metrics

    # Check if golden store exists
    if not Path("tests/golden").exists():
        print("  SKIP: Golden store not found")
        return True

    result_json = get_golden_metrics("01_simple_profile")
    result = json.loads(result_json)

    # Either returns metrics or an error (if recipe doesn't have golden)
    if "error" not in result:
        assert isinstance(result, dict)
    print("  PASS")
    return True


def test_nonexistent_recipe_metrics():
    print("Running test_nonexistent_recipe_metrics...")
    from mill_mcp.server import get_golden_metrics

    result_json = get_golden_metrics("nonexistent_recipe")
    result = json.loads(result_json)

    assert "error" in result
    print("  PASS")
    return True


def test_nonexistent_store_metrics():
    print("Running test_nonexistent_store_metrics...")
    from mill_mcp.server import get_golden_metrics

    result_json = get_golden_metrics(
        "01_simple_profile",
        store_path="/nonexistent/store"
    )
    result = json.loads(result_json)

    assert "error" in result
    assert "not found" in result["error"]
    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_simple_rect_profile,
        test_compositional_pml,
        test_auto_detect_compositional,
        test_invalid_pml_returns_error,
        test_simple_nest,
        test_nest_with_template,
        test_invalid_nest_returns_error,
        test_returns_shaker,
        test_valid_pml,
        test_invalid_pml,
        test_get_pml_spec,
        test_get_nest_spec,
        test_get_all_specs,
        test_invalid_format,
        test_valid_recipe,
        test_nonexistent_recipe,
        test_golden_not_found_error,
        test_with_golden_regression,
        test_svg_validation,
        test_no_artifacts_error,
        test_file_not_found,
        test_list_baselines,
        test_nonexistent_store,
        test_get_metrics,
        test_nonexistent_recipe_metrics,
        test_nonexistent_store_metrics,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
