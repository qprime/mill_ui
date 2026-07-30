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


def build_provenance(revision: str | None = None) -> dict[str, str]:
    if revision is None:
        revision = get_mill_ui_revision() or "unknown"
    return {"mill_ui": revision}
