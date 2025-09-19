# path: continuum/system_config.py
# type: system_config
# tags: configuration, continuum, defaults
# owner: cliff
# depends_on: json, pathlib
# description: Loads shared system configuration with project-wide defaults.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "memories/cliff_state/system_config.json"

_DEFAULTS: Dict[str, Any] = {
    "ltp": {
        "whisper": {
            "url": "https://skylink:8001/transcribe",
            "verify": "services/whisper/cert/whisper.crt",
        }
    }
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


@dataclass(frozen=True)
class SystemConfig:
    data: Dict[str, Any]

    def get(self, dotted_key: str, default: Any = None) -> Any:
        parts = dotted_key.split(".")
        cursor: Any = self.data
        for part in parts:
            if not isinstance(cursor, dict) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor


def load(path: Path | None = None) -> SystemConfig:
    cfg_path = path or CONFIG_PATH
    file_data = _load_file(cfg_path)
    data = _deep_merge(_DEFAULTS, file_data)
    return SystemConfig(data)
