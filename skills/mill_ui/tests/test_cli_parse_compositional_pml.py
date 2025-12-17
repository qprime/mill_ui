"""Tests for parse-compositional-pml CLI tool."""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_parse_and_format():
    """Test CLI can parse and reformat compositional PML."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        # Test basic parse and format
        result = subprocess.run(
            [sys.executable, "-m", "skills.mill_ui.cli.parse_compositional_pml", input_file],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Parse successful" in result.stderr
        assert "sheet 400.00mm 600.00mm 19.00mm" in result.stdout

    finally:
        Path(input_file).unlink()


def test_cli_resolve_to_flat_pml():
    """Test CLI can resolve compositional PML to flat PML."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        # Test resolve to flat PML
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills.mill_ui.cli.parse_compositional_pml",
                input_file,
                "--resolve",
                "--format",
                "pml",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Parse successful" in result.stderr
        assert "✓ Resolved to" in result.stderr
        assert "sheet 400.00mm 600.00mm 19.00mm" in result.stdout
        # Flat PML should have explicit positions
        assert "at " in result.stdout

    finally:
        Path(input_file).unlink()


def test_cli_resolve_to_json():
    """Test CLI can resolve compositional PML to JSON."""
    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        # Test resolve to JSON
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills.mill_ui.cli.parse_compositional_pml",
                input_file,
                "--resolve",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Parse successful" in result.stderr
        assert "✓ Resolved to" in result.stderr
        assert '"items"' in result.stdout
        assert '"sheet"' in result.stdout

    finally:
        Path(input_file).unlink()


def test_cli_error_on_missing_file():
    """Test CLI reports error for missing input file."""
    result = subprocess.run(
        [sys.executable, "-m", "skills.mill_ui.cli.parse_compositional_pml", "/nonexistent/file.pml"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr


def test_cli_error_on_invalid_pml():
    """Test CLI reports parse error for invalid PML."""
    pml = "invalid pml syntax"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "skills.mill_ui.cli.parse_compositional_pml", input_file],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "Parse Error" in result.stderr

    finally:
        Path(input_file).unlink()


def test_cli_gold_exemplar():
    """Test CLI with Stage 12 gold exemplar."""
    pml = """sheet 1200.00mm 1200.00mm 19.00mm

project acceptance_test_grid_panels

component GridPanel
    rect panel_outer profile through outside
        frame 40.00mm
            grid 2 2 gap 10.00mm
                cell
                    rect pocket 5.00mm

place grid 2 2 gap 100.00mm
    use GridPanel
    use GridPanel
    use GridPanel
    use GridPanel
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        # Test resolution produces 24 items
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills.mill_ui.cli.parse_compositional_pml",
                input_file,
                "--resolve",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Resolved to 24 flat items" in result.stderr

    finally:
        Path(input_file).unlink()
