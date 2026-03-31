from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RECIPE_DIR = Path(__file__).parent.parent / "docs" / "recipes" / "01_simple_profile"
PML_FILE = RECIPE_DIR / "example.pml.yml"


def _check_optional_deps() -> dict[str, bool]:
    import importlib.util

    return {
        "shapely": importlib.util.find_spec("shapely") is not None,
        "numpy": importlib.util.find_spec("numpy") is not None,
    }


OPTIONAL_DEPS = _check_optional_deps()


def _skip_if_missing(dep: str) -> None:
    if not OPTIONAL_DEPS.get(dep, False):
        pytest.skip(f"missing {dep}")


def _run_cli(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"CLI failed with code {result.returncode}:\n{result.stderr}")
    return result


def test_export_blueprint_produces_svg():

    _skip_if_missing("shapely")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run_cli(
            [
                "-m",
                "cli.mill",
                "--input",
                str(PML_FILE),
                "--out",
                tmpdir,
                "--theme",
                "dark",
            ]
        )

        output_path = Path(tmpdir)
        svg_files = list(output_path.glob("*.svg"))
        assert len(svg_files) > 0, f"No SVG files generated. stderr: {result.stderr}"

        expected_svg = output_path / "example.pml.svg"
        assert expected_svg.exists(), f"Expected SVG not found. Files: {list(output_path.iterdir())}"

        svg_content = expected_svg.read_text()
        assert "<svg" in svg_content, "SVG file missing <svg> tag"
        assert "</svg>" in svg_content, "SVG file missing closing </svg> tag"


def test_convert_layout_pml_to_json():

    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = Path(tmpdir) / "output.json"

        result = _run_cli(
            [
                "-m",
                "cli.convert_layout",
                "--from",
                "pml",
                "--to",
                "json",
                str(PML_FILE),
                str(json_file),
            ]
        )

        assert json_file.exists(), f"JSON file not created. stderr: {result.stderr}"

        with open(json_file) as f:
            data = json.load(f)

        assert "sheet" in data, "JSON missing 'sheet' key"
        assert "items" in data, "JSON missing 'items' key"
        assert data["sheet"]["width_mm"] == 450, f"Unexpected sheet width: {data['sheet']}"
        assert data["sheet"]["height_mm"] == 650, f"Unexpected sheet height: {data['sheet']}"


def test_convert_layout_json_to_pml():

    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = Path(tmpdir) / "intermediate.json"
        pml_file = Path(tmpdir) / "roundtrip.pml.yml"

        _run_cli(
            [
                "-m",
                "cli.convert_layout",
                "--from",
                "pml",
                "--to",
                "json",
                str(PML_FILE),
                str(json_file),
            ]
        )

        _run_cli(
            [
                "-m",
                "cli.convert_layout",
                "--from",
                "json",
                "--to",
                "pml",
                str(json_file),
                str(pml_file),
            ]
        )

        assert pml_file.exists(), "PML roundtrip file not created"

        pml_content = pml_file.read_text()
        assert "Sheet" in pml_content, "PML missing 'Sheet' declaration"
        assert "450" in pml_content, "PML missing sheet width"
        assert "650" in pml_content, "PML missing sheet height"


def test_cli_missing_input_fails():

    result = _run_cli(
        [
            "-m",
            "cli.mill",
            "--input",
            "/nonexistent/path/to/file.pml.yml",
            "--out",
            "/tmp",
        ],
        check=False,
    )

    assert result.returncode != 0, "CLI should fail with missing input"
    assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


def test_cli_invalid_format_fails():

    with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
        f.write("invalid content")
        invalid_file = f.name

    try:
        result = _run_cli(
            [
                "-m",
                "cli.mill",
                "--input",
                invalid_file,
                "--out",
                "/tmp",
            ],
            check=False,
        )

        assert result.returncode != 0, "CLI should fail with unsupported format"
        assert "unsupported" in result.stderr.lower() or "error" in result.stderr.lower()
    finally:
        Path(invalid_file).unlink()
