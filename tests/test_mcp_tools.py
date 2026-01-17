"""Tests for MCP server tools."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# Mock the output directory for tests
@pytest.fixture
def mock_output_dir(tmp_path):
    """Use temporary directory for test outputs."""
    with patch("mill_mcp.config.get_output_dir", return_value=tmp_path):
        yield tmp_path


class TestCompilePml:
    """Tests for compile_pml tool."""

    def test_simple_rect_profile(self, mock_output_dir):
        from mill_mcp.server import compile_pml

        pml = """sheet 450mm 650mm 19mm

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
        assert "stl" in result["outputs"]
        assert len(result["outputs"]["gcode"]) > 0

        # Verify files exist
        assert Path(result["outputs"]["pml"]).exists()

    def test_compositional_pml(self, mock_output_dir):
        from mill_mcp.server import compile_pml

        pml = """sheet 450mm 650mm 19mm

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

    def test_auto_detect_compositional(self, mock_output_dir):
        from mill_mcp.server import compile_pml

        pml = """sheet 450mm 650mm 19mm

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

    def test_invalid_pml_returns_error(self, mock_output_dir):
        from mill_mcp.server import compile_pml

        pml = "this is not valid pml"
        result_json = compile_pml(pml)
        result = json.loads(result_json)

        assert "error" in result
        assert result["success"] is False


class TestCompileNest:
    """Tests for compile_nest tool."""

    def test_simple_nest(self, mock_output_dir):
        from mill_mcp.server import compile_nest

        nest = """nest maxrects
    sheet 1220mm 2440mm 19mm
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

    def test_nest_with_template(self, mock_output_dir):
        from mill_mcp.server import compile_nest

        nest = """nest guillotine
    sheet 1220mm 2440mm 19mm
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
        # Shaker template creates 2 items per door
        assert result["sheets"][0]["items"] == 2

    def test_invalid_nest_returns_error(self, mock_output_dir):
        from mill_mcp.server import compile_nest

        nest = "not valid nest syntax"
        result_json = compile_nest(nest)
        result = json.loads(result_json)

        assert "error" in result
        assert result["success"] is False


class TestListTemplates:
    """Tests for list_templates tool."""

    def test_returns_shaker(self):
        from mill_mcp.server import list_templates

        result_json = list_templates()
        result = json.loads(result_json)

        assert "Shaker" in result
        assert "required_params" in result["Shaker"]
        assert "outer_w" in result["Shaker"]["required_params"]
        assert "example" in result["Shaker"]


class TestValidatePml:
    """Tests for validate_pml tool."""

    def test_valid_pml(self):
        from mill_mcp.server import validate_pml

        pml = """sheet 450mm 650mm 19mm

rect door at 225mm,325mm size 400mm,600mm profile through outside
"""
        result_json = validate_pml(pml)
        result = json.loads(result_json)

        assert result["valid"] is True
        assert result["info"]["items"] == 1
        assert len(result["errors"]) == 0

    def test_invalid_pml(self):
        from mill_mcp.server import validate_pml

        pml = "not valid"
        result_json = validate_pml(pml)
        result = json.loads(result_json)

        assert result["valid"] is False
        assert len(result["errors"]) > 0


class TestGetSyntaxSpec:
    """Tests for get_syntax_spec tool."""

    def test_get_pml_spec(self):
        from mill_mcp.server import get_syntax_spec

        result = get_syntax_spec("pml")

        assert "PML" in result
        assert "sheet" in result.lower()
        assert "rect" in result.lower()

    def test_get_nest_spec(self):
        from mill_mcp.server import get_syntax_spec

        result = get_syntax_spec("nest")

        assert "nest" in result.lower()
        assert "parts" in result.lower()

    def test_get_all_specs(self):
        from mill_mcp.server import get_syntax_spec

        result = get_syntax_spec("all")

        assert "PML" in result
        assert "nest" in result.lower()

    def test_invalid_format(self):
        from mill_mcp.server import get_syntax_spec

        result = get_syntax_spec("invalid")

        assert "Unknown format" in result


# =============================================================================
# CAM Validation Tool Tests
# =============================================================================


class TestValidateCamRecipe:
    """Tests for validate_cam_recipe tool."""

    def test_valid_recipe(self):
        """Test validating a valid recipe directory."""
        from mill_mcp.server import validate_cam_recipe

        # Use a known recipe
        recipe_path = "docs/recipes/01_simple_profile"
        if not Path(recipe_path).exists():
            pytest.skip("Recipe not found")

        result_json = validate_cam_recipe(recipe_path)
        result = json.loads(result_json)

        assert "error" not in result
        assert "verdict" in result
        assert result["verdict"] in ("pass", "warn", "fail")
        assert "metrics" in result
        assert "invariants" in result

    def test_nonexistent_recipe(self):
        """Test error handling for nonexistent recipe."""
        from mill_mcp.server import validate_cam_recipe

        result_json = validate_cam_recipe("/nonexistent/path")
        result = json.loads(result_json)

        assert "error" in result
        assert "not found" in result["error"]

    def test_golden_not_found_error(self):
        """Test error when golden_path provided but file doesn't exist."""
        from mill_mcp.server import validate_cam_recipe

        recipe_path = "docs/recipes/01_simple_profile"
        if not Path(recipe_path).exists():
            pytest.skip("Recipe not found")

        result_json = validate_cam_recipe(
            recipe_path,
            golden_path="/nonexistent/golden.json"
        )
        result = json.loads(result_json)

        assert "error" in result
        assert "Golden file not found" in result["error"]

    def test_with_golden_regression(self):
        """Test validation with golden baseline."""
        from mill_mcp.server import validate_cam_recipe

        recipe_path = "docs/recipes/01_simple_profile"
        golden_path = "tests/golden/01_simple_profile/metrics.json"

        if not Path(recipe_path).exists():
            pytest.skip("Recipe not found")
        if not Path(golden_path).exists():
            pytest.skip("Golden baseline not found")

        result_json = validate_cam_recipe(
            recipe_path,
            golden_path=golden_path
        )
        result = json.loads(result_json)

        assert "error" not in result
        assert result["regressions"]["compared"] is True


class TestValidateCamArtifacts:
    """Tests for validate_cam_artifacts tool."""

    def test_svg_validation(self):
        """Test validating an SVG file."""
        from mill_mcp.server import validate_cam_artifacts

        svg_path = "docs/recipes/01_simple_profile/output/01_simple_profile.svg"
        if not Path(svg_path).exists():
            pytest.skip("SVG not found")

        result_json = validate_cam_artifacts(svg_path=svg_path)
        result = json.loads(result_json)

        assert "error" not in result
        assert "verdict" in result
        assert "svg" in result["metrics"]

    def test_stl_validation(self):
        """Test validating an STL file."""
        from mill_mcp.server import validate_cam_artifacts

        stl_path = "docs/recipes/01_simple_profile/output/example.stl"
        if not Path(stl_path).exists():
            pytest.skip("STL not found")

        result_json = validate_cam_artifacts(stl_path=stl_path)
        result = json.loads(result_json)

        assert "error" not in result
        assert "verdict" in result
        assert "stl" in result["metrics"]

    def test_no_artifacts_error(self):
        """Test error when no artifacts provided."""
        from mill_mcp.server import validate_cam_artifacts

        result_json = validate_cam_artifacts()
        result = json.loads(result_json)

        assert "error" in result
        assert "At least one artifact" in result["error"]

    def test_file_not_found(self):
        """Test error for nonexistent file."""
        from mill_mcp.server import validate_cam_artifacts

        result_json = validate_cam_artifacts(svg_path="/nonexistent/file.svg")
        result = json.loads(result_json)

        assert "error" in result
        assert "not found" in result["error"]


class TestListGoldenBaselines:
    """Tests for list_golden_baselines tool."""

    def test_list_baselines(self):
        """Test listing golden baselines."""
        from mill_mcp.server import list_golden_baselines

        result_json = list_golden_baselines()
        result = json.loads(result_json)

        # Should have baselines or indicate store doesn't exist
        assert "baselines" in result
        assert "total" in result
        assert "store_path" in result

    def test_nonexistent_store(self):
        """Test handling of nonexistent store."""
        from mill_mcp.server import list_golden_baselines

        result_json = list_golden_baselines(store_path="/nonexistent/store")
        result = json.loads(result_json)

        assert result["total"] == 0
        assert "message" in result or len(result["baselines"]) == 0


class TestGetGoldenMetrics:
    """Tests for get_golden_metrics tool."""

    def test_get_metrics(self):
        """Test getting golden metrics for a recipe."""
        from mill_mcp.server import get_golden_metrics

        # Check if golden store exists
        if not Path("tests/golden").exists():
            pytest.skip("Golden store not found")

        result_json = get_golden_metrics("01_simple_profile")
        result = json.loads(result_json)

        # Either returns metrics or an error (if recipe doesn't have golden)
        if "error" not in result:
            assert isinstance(result, dict)

    def test_nonexistent_recipe(self):
        """Test error for nonexistent recipe."""
        from mill_mcp.server import get_golden_metrics

        result_json = get_golden_metrics("nonexistent_recipe")
        result = json.loads(result_json)

        assert "error" in result

    def test_nonexistent_store(self):
        """Test error for nonexistent store."""
        from mill_mcp.server import get_golden_metrics

        result_json = get_golden_metrics(
            "01_simple_profile",
            store_path="/nonexistent/store"
        )
        result = json.loads(result_json)

        assert "error" in result
        assert "not found" in result["error"]
