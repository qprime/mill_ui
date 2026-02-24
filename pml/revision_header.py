from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path


def get_mill_ui_revision() -> str | None:
    mill_ui_root = Path(__file__).parent.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=mill_ui_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def format_pml_header(revision: str | None = None, gen_date: date | None = None) -> str:
    if revision is None:
        revision = get_mill_ui_revision() or "unknown"
    if gen_date is None:
        gen_date = date.today()
    return f"# mill_ui: {revision}\n# generated: {gen_date.isoformat()}\n"


def has_mill_ui_header(content: str) -> bool:
    lines = content.split("\n")
    return len(lines) >= 2 and lines[0].startswith("# mill_ui:") and lines[1].startswith("# generated:")


def update_pml_header(content: str, revision: str | None = None, gen_date: date | None = None) -> str:
    header = format_pml_header(revision, gen_date)
    if has_mill_ui_header(content):
        lines = content.split("\n")
        return header + "\n".join(lines[2:])
    return header + "\n" + content


def update_file_header(path: Path) -> None:
    content = path.read_text()
    updated = update_pml_header(content)
    path.write_text(updated)
