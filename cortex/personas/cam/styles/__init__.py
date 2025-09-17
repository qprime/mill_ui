"""Utilities for loading CAM style metadata from JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

# Root of the personas tree (…/cortex/personas)
PERSONA_ROOT = Path(__file__).resolve().parents[2]
# Default directory containing style JSON definitions
DEFAULT_STYLES_DIR = Path(__file__).resolve().parent


def _category_dir(category: Optional[str]) -> Path:
    """Return the directory to scan for style definitions."""
    if category:
        return PERSONA_ROOT / Path(category)
    return DEFAULT_STYLES_DIR


def load_styles(category: Optional[str] = None) -> Dict[str, Dict]:
    """Load all styles for the given category into a name->payload map."""
    directory = _category_dir(category)
    styles: Dict[str, Dict] = {}

    if not directory.exists():
        raise ValueError(f"Unknown style category: {category!r}")

    for json_path in sorted(directory.rglob("*.json")):
        try:
            with json_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:  # pragma: no cover - log and continue
            print(f"WARNING: Could not parse style file {json_path}: {exc}")
            continue

        if isinstance(data, dict) and data.get("name"):
            styles[data["name"]] = data
        else:
            print(f"WARNING: Style file missing 'name': {json_path}")

    return styles


def get_style(style_name: str, category: Optional[str] = None) -> Dict:
    """Fetch a single style definition by name."""
    styles = load_styles(category)
    if style_name in styles:
        return styles[style_name]
    raise ValueError(f"Unknown style: {style_name} (category: {category!r})")


def list_styles(category: Optional[str] = None) -> list[str]:
    """Return the alphabetized list of available style names."""
    return sorted(load_styles(category).keys())
