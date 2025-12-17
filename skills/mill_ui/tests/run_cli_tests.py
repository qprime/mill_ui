"""Standalone test runner for CLI tools (without pytest)."""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_parse_and_format():
    """Test CLI can parse and reformat compositional PML."""
    print("Running test_cli_parse_and_format...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "skills.mill_ui.cli.parse_compositional_pml", input_file],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Parse successful" in result.stderr
        assert "sheet 400.00mm 600.00mm 19.00mm" in result.stdout

        print("  ✓ PASS")
        return True

    finally:
        Path(input_file).unlink()


def test_cli_resolve_to_flat_pml():
    """Test CLI can resolve compositional PML to flat PML."""
    print("Running test_cli_resolve_to_flat_pml...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
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
        assert "at " in result.stdout  # Flat PML has explicit positions

        print("  ✓ PASS")
        return True

    finally:
        Path(input_file).unlink()


def test_cli_resolve_to_json():
    """Test CLI can resolve compositional PML to JSON."""
    print("Running test_cli_resolve_to_json...")

    pml = """sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        rect inner pocket 6.00mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
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

        print("  ✓ PASS")
        return True

    finally:
        Path(input_file).unlink()


def test_cli_error_on_missing_file():
    """Test CLI reports error for missing input file."""
    print("Running test_cli_error_on_missing_file...")

    result = subprocess.run(
        [sys.executable, "-m", "skills.mill_ui.cli.parse_compositional_pml", "/nonexistent/file.pml"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr

    print("  ✓ PASS")
    return True


def test_cli_error_on_invalid_pml():
    """Test CLI reports parse error for invalid PML."""
    print("Running test_cli_error_on_invalid_pml...")

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

        print("  ✓ PASS")
        return True

    finally:
        Path(input_file).unlink()


def test_cli_gold_exemplar():
    """Test CLI with Stage 12 gold exemplar (24 items)."""
    print("Running test_cli_gold_exemplar...")

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

        print("  ✓ PASS")
        return True

    finally:
        Path(input_file).unlink()


if __name__ == "__main__":
    tests = [
        test_cli_parse_and_format,
        test_cli_resolve_to_flat_pml,
        test_cli_resolve_to_json,
        test_cli_error_on_missing_file,
        test_cli_error_on_invalid_pml,
        test_cli_gold_exemplar,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} CLI tests passed")

    sys.exit(0 if all(results) else 1)
