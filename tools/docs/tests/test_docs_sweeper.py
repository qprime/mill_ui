from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.docs.sweep_readmes import (
    GUIDE_CONTENT,
    README_SPECS,
    ReadmeSpec,
    ReadmeSweeper,
    archive_document,
    render_readme,
    validate_readme_text,
)


@pytest.mark.parametrize("key", ["README.md", "tools/README.md"])
def test_render_and_validate_round_trip(key: str) -> None:
    spec: ReadmeSpec = README_SPECS[key]
    text = render_readme(spec)
    issues = validate_readme_text(text, spec)
    assert not issues, f"Expected zero issues, got: {[issue.reason for issue in issues]}"
    assert text.splitlines()[0].startswith("# ")
    owner_line = f"Owner path: {spec.owner}"
    assert owner_line in text.splitlines(), "Owner line missing from rendered README"


def test_validate_detects_missing_owner() -> None:
    spec = README_SPECS["README.md"]
    text = render_readme(spec)
    owner_line = f"Owner path: {spec.owner}"
    lines = [line for line in text.splitlines() if line != owner_line]
    mutated = "\n".join(lines) + "\n"
    issues = validate_readme_text(mutated, spec)
    assert any("owner line" in issue.reason for issue in issues)


def test_archive_document_adds_header(tmp_path: Path) -> None:
    src = tmp_path / "memories" / "README_memories.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Sample\n", encoding="utf-8")
    dst = tmp_path / "docs" / "_archive" / "memories" / "README_memories.md"
    archive_document(src, dst, "Superseded by AI_README_GUIDE.md")
    content = dst.read_text(encoding="utf-8")
    assert content.startswith("---\narchived: true")
    assert "Superseded by AI_README_GUIDE.md" in content


def test_apply_creates_readmes_and_report(tmp_path: Path) -> None:
    spec_subset = {
        "README.md": README_SPECS["README.md"],
        "tools/README.md": README_SPECS["tools/README.md"],
    }
    sweeper = ReadmeSweeper(tmp_path, spec_subset, {}, GUIDE_CONTENT)
    issues, generated, archived = sweeper.apply()
    assert not issues
    assert "README.md" in generated
    assert "docs/AI_README_GUIDE.md" in generated
    assert not archived
    report_path = tmp_path / "docs/_reports/readme_sweep.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["issues"] == []
    assert "README.md" in report["generated"]


def test_dry_run_reports_issues(tmp_path: Path) -> None:
    spec = README_SPECS["README.md"]
    bad_readme = tmp_path / "README.md"
    bad_readme.write_text("# cliff_ai\nOwner path: .\n", encoding="utf-8")
    sweeper = ReadmeSweeper(tmp_path, {"README.md": spec}, {}, GUIDE_CONTENT)
    issues, _, _ = sweeper.dry_run()
    assert issues
    assert any("missing or empty section" in issue.reason for issue in issues)
