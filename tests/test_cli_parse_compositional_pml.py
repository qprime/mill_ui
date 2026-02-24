import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_parse_and_format():
    print("Running test_cli_parse_and_format...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 50mm
            children:
              - Rect:
                  id: inner
                  feature:
                    type: pocket
                    depth: 6mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml.yml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "cli.parse_compositional_pml", input_file],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Parse successful" in result.stderr
        assert "Sheet:" in result.stdout

    finally:
        Path(input_file).unlink()

    print("  ✓ PASS")
    return True


def test_cli_resolve_to_flat_pml():
    print("Running test_cli_resolve_to_flat_pml...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 50mm
            children:
              - Rect:
                  id: inner
                  feature:
                    type: pocket
                    depth: 6mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml.yml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.parse_compositional_pml",
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
        assert "sheet" in result.stdout.lower()

        assert "at " in result.stdout or "placement" in result.stdout.lower()

    finally:
        Path(input_file).unlink()

    print("  ✓ PASS")
    return True


def test_cli_resolve_to_json():
    print("Running test_cli_resolve_to_json...")

    pml = """
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 50mm
            children:
              - Rect:
                  id: inner
                  feature:
                    type: pocket
                    depth: 6mm
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml.yml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.parse_compositional_pml",
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

    print("  ✓ PASS")
    return True


def test_cli_error_on_missing_file():
    print("Running test_cli_error_on_missing_file...")

    result = subprocess.run(
        [sys.executable, "-m", "cli.parse_compositional_pml", "/nonexistent/file.pml.yml"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr

    print("  ✓ PASS")
    return True


def test_cli_error_on_invalid_pml():
    print("Running test_cli_error_on_invalid_pml...")

    pml = "invalid pml syntax"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml.yml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "cli.parse_compositional_pml", input_file],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "Parse Error" in result.stderr or "error" in result.stderr.lower()

    finally:
        Path(input_file).unlink()

    print("  ✓ PASS")
    return True


def test_cli_gold_exemplar():
    print("Running test_cli_gold_exemplar...")

    pml = """
Sheet:
  width: 1200mm
  height: 1200mm
  thickness: 19mm

project: acceptance_test_grid_panels

components:
  GridPanel:
    body:
      - Rect:
          id: panel_outer
          feature:
            type: profile
            side: outside
            depth: through
          children:
            - Frame:
                width: 40mm
                children:
                  - Grid:
                      rows: 2
                      cols: 2
                      gap: 10mm
                      children:
                        - Cell:
                            children:
                              - Rect:
                                  feature:
                                    type: pocket
                                    depth: 5mm

children:
  - Place:
      layout:
        Grid:
          rows: 2
          cols: 2
          gap: 100mm
      children:
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
        - UseComponent:
            name: GridPanel
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pml.yml", delete=False) as f:
        f.write(pml)
        input_file = f.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.parse_compositional_pml",
                input_file,
                "--resolve",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "✓ Resolved to 20 flat items" in result.stderr

    finally:
        Path(input_file).unlink()

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_cli_parse_and_format,
        test_cli_resolve_to_flat_pml,
        test_cli_resolve_to_json,
        test_cli_error_on_missing_file,
        test_cli_error_on_invalid_pml,
        test_cli_gold_exemplar,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{len(tests)} CLI parse tests passed")
    sys.exit(0 if failed == 0 else 1)
