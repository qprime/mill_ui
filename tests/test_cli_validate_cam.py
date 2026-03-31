from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.validate_cam import EXIT_FAIL, EXIT_PASS, EXIT_WARN, main

RECIPE_DIR = Path(__file__).parent.parent / "docs" / "recipes"


def run_cli(*args: str) -> tuple[int, str, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with (
        patch.object(sys, "argv", ["validate_cam", *args]),
        redirect_stdout(stdout_capture),
        redirect_stderr(stderr_capture),
    ):
        try:
            exit_code = main()
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0

    return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()


def test_cli_no_args_fails():
    """CLI with no arguments exits with error."""
    exit_code, _stdout, stderr = run_cli()
    assert exit_code != EXIT_PASS
    assert "error" in stderr.lower() or "required" in stderr.lower()


def test_cli_help():
    """CLI --help shows usage."""
    exit_code, stdout, stderr = run_cli("--help")
    assert exit_code == 0
    assert "validate" in stdout.lower() or "validate" in stderr.lower()


def test_cli_missing_file_fails():
    """CLI with nonexistent file exits with FAIL."""
    exit_code, _stdout, stderr = run_cli("--svg", "/nonexistent/file.svg")
    assert exit_code == EXIT_FAIL
    assert "not found" in stderr.lower() or "error" in stderr.lower()


def test_cli_recipe_simple_profile():
    """CLI validates recipe 01_simple_profile."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"

    if not recipe_dir.exists():
        pytest.skip("recipe not found")

    exit_code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit code {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "verdict" in result
    assert "metrics" in result
    assert result["verdict"] in ("pass", "warn")


def test_cli_recipe_with_summary():
    """CLI --summary outputs human-readable text."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"

    if not recipe_dir.exists():
        pytest.skip("recipe not found")

    exit_code, stdout, _stderr = run_cli("--recipe", str(recipe_dir), "--summary")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    assert "Validation Result:" in stdout
    assert "Metrics extracted:" in stdout or "Invariants:" in stdout


def test_cli_recipe_with_output_file():
    """CLI --output writes to file."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"

    if not recipe_dir.exists():
        pytest.skip("recipe not found")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        output_path = f.name

    try:
        exit_code, _stdout, _stderr = run_cli(
            "--recipe",
            str(recipe_dir),
            "--output",
            output_path,
        )
        assert exit_code in (EXIT_PASS, EXIT_WARN)

        assert os.path.exists(output_path)
        with open(output_path) as f:
            data = json.load(f)
        result = data.get("validation_result", data)
        assert "verdict" in result
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_cli_svg_only():
    """CLI validates single SVG file."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    exit_code, stdout, _stderr = run_cli("--svg", str(svg_path), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "svg" in result["metrics"]


def test_cli_gcode_only():
    """CLI validates single G-code file."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    output_dir = recipe_dir / "output"

    nc_files = [f for f in output_dir.glob("*.nc") if not f.name.startswith("._")] if output_dir.exists() else []
    if not nc_files:
        pytest.skip("G-code not found")

    exit_code, stdout, stderr = run_cli("--gcode", str(nc_files[0]), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "gcode" in result["metrics"]


def test_cli_multiple_gcode():
    """CLI validates multiple G-code files."""
    recipe_dir = RECIPE_DIR / "02_simple_pocket"
    output_dir = recipe_dir / "output"

    nc_files = [f for f in output_dir.glob("*.nc") if not f.name.startswith("._")] if output_dir.exists() else []
    if len(nc_files) < 2:
        pytest.skip("not enough G-code files")

    exit_code, stdout, stderr = run_cli("--gcode", str(nc_files[0]), str(nc_files[1]), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "gcode" in result["metrics"]
    assert result["metrics"]["gcode"].get("file_count", 1) >= 2


def test_cli_metrics_only():
    """CLI --metrics-only skips invariant/assertion checks."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    exit_code, stdout, _stderr = run_cli("--svg", str(svg_path), "--metrics-only", "--quiet")
    assert exit_code == EXIT_PASS

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "svg" in result["metrics"]
    assert result["invariants"]["total"] == 0


def test_cli_metrics_only_with_golden():
    """CLI --metrics-only disables regression even with --golden."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    golden_metrics = {"svg": {"document": {"width_mm": 9999.0}}}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(golden_metrics, f)
        golden_path = f.name

    try:
        exit_code, stdout, stderr = run_cli(
            "--svg", str(svg_path), "--metrics-only", "--golden", golden_path, "--quiet"
        )
        assert exit_code == EXIT_PASS, f"Expected PASS, got {exit_code}: {stderr}"

        data = json.loads(stdout)
        result = data.get("validation_result", data)
        assert result["regressions"]["compared"] is False
        assert result["regressions"]["total"] == 0
    finally:
        if os.path.exists(golden_path):
            os.unlink(golden_path)


def test_cli_compact_json():
    """CLI --compact outputs single-line JSON."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    exit_code, stdout, _stderr = run_cli("--svg", str(svg_path), "--compact", "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    lines = [line for line in stdout.strip().split("\n") if line.strip()]
    assert len(lines) <= 2, f"Expected compact JSON, got {len(lines)} lines"
    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "verdict" in result


def test_cli_with_pml_assertions():
    """CLI --pml enables intent assertions."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    pml_path = recipe_dir / "example.pml.yml"
    output_dir = recipe_dir / "output"

    if not pml_path.exists() or not output_dir.exists():
        pytest.skip("recipe not found")

    svg_path = output_dir / "01_simple_profile.svg"
    if not svg_path.exists():
        pytest.skip("SVG not found")

    exit_code, stdout, _stderr = run_cli("--svg", str(svg_path), "--pml", str(pml_path), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN, EXIT_FAIL)

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert result["assertions"]["total"] > 0


def test_cli_with_golden_regression():
    """CLI --golden enables regression comparison."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    from validation.metrics.svg_metrics import extract_svg_metrics_from_file

    golden_metrics = extract_svg_metrics_from_file(str(svg_path)).to_dict()

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(golden_metrics, f)
        golden_path = f.name

    try:
        exit_code, stdout, stderr = run_cli(
            "--svg", str(svg_path), "--golden", golden_path, "--no-assertions", "--quiet"
        )
        assert exit_code == EXIT_PASS, f"Unexpected exit {exit_code}: {stderr}"

        data = json.loads(stdout)
        result = data.get("validation_result", data)
        assert result["regressions"]["compared"] is True
        assert result["regressions"]["total"] > 0
    finally:
        if os.path.exists(golden_path):
            os.unlink(golden_path)


def test_cli_golden_not_found():
    """CLI with nonexistent golden file fails."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    exit_code, _stdout, stderr = run_cli(
        "--svg",
        str(svg_path),
        "--golden",
        "/nonexistent/golden.json",
    )
    assert exit_code == EXIT_FAIL
    assert "not found" in stderr.lower()


def test_cli_tolerance_override():
    """CLI --tolerance overrides default comparison tolerance."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        pytest.skip("SVG not found")

    from validation.metrics.svg_metrics import extract_svg_metrics_from_file

    golden_metrics = extract_svg_metrics_from_file(str(svg_path)).to_dict()

    if (
        "svg" in golden_metrics
        and "document" in golden_metrics["svg"]
        and "width_mm" in golden_metrics["svg"]["document"]
    ):
        golden_metrics["svg"]["document"]["width_mm"] *= 0.9995

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(golden_metrics, f)
        golden_path = f.name

    try:
        exit_code1, _stdout1, _stderr1 = run_cli(
            "--svg", str(svg_path), "--golden", golden_path, "--tolerance", "0.01", "--quiet"
        )

        exit_code2, _stdout2, _stderr2 = run_cli(
            "--svg", str(svg_path), "--golden", golden_path, "--tolerance", "1.0", "--quiet"
        )

        assert exit_code1 >= exit_code2
    finally:
        if os.path.exists(golden_path):
            os.unlink(golden_path)


def test_cli_exit_codes():
    """Verify exit code constants match plan."""
    assert EXIT_PASS == 0
    assert EXIT_WARN == 1
    assert EXIT_FAIL == 2
