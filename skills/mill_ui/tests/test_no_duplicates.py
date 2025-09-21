from __future__ import annotations

from pathlib import Path


def test_no_duplicate_module_stems_between_cad_and_top_level() -> None:
    pkg_root = Path(__file__).resolve().parents[1]
    cad_root = pkg_root / "cad"
    assert cad_root.exists(), "cad package must exist"

    cad_stems = {
        path.stem
        for path in cad_root.rglob("*.py")
        if path.name != "__init__.py"
    }
    top_level_stems = {
        path.stem
        for path in pkg_root.glob("*.py")
        if path.name != "__init__.py"
    }

    duplicates = cad_stems & top_level_stems
    assert not duplicates, f"Duplicate module stems across cad/ and top-level: {sorted(duplicates)}"
