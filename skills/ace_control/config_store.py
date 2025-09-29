"""Configuration store for ACE routing and budgeting settings."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]


CONFIG_ENV_VAR = "ACE_CONFIG_DIR"
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "docs" / "_reports"

ROUTER_FILENAME = "router_config.json"
BUDGET_FILENAME = "ace_budgets.json"


DEFAULT_ROUTER_CONFIG: Dict[str, object] = {
    "task_types": {
        "build_large": {"provider": "codex_cli", "stream": True},
        "refactor_multi": {"provider": "codex_cli", "stream": True},
        "repo_plan": {"provider": "codex_cli", "stream": True},
        "chat": {"provider": "gpt_api", "stream": True},
        "patch_small": {"provider": "gpt_api", "stream": True},
        "analyze": {"provider": "gpt_api", "stream": True},
        "report": {"provider": "gpt_api", "stream": True},
        "tests": {"provider": "gpt_api", "stream": True},
    },
    "providers": {
        "codex_cli": {
            "temperature": 0.2,
            "fallback": True,
        },
        "gpt_api": {
            "model": "gpt-5",
            "temperature": 0.2,
            "max_prompt_tokens": 500000,
            "max_output_tokens": 16000,
        },
        "gpt_api_mini": {
            "model": "gpt-5-mini",
            "temperature": 0.2,
            "max_prompt_tokens": 120000,
            "max_output_tokens": 8000,
        },
        "gpt_api_nano": {
            "model": "gpt-5-nano",
            "temperature": 0.2,
            "max_prompt_tokens": 60000,
            "max_output_tokens": 4000,
        },
    },
    "fallback": {
        "attempts": 1,
        "order": ["gpt_api", "gpt_api_mini", "gpt_api_nano", "codex_cli"],
    },
}


DEFAULT_BUDGET_CONFIG: Dict[str, object] = {
    "focus_history": 5,
    "direct_files_max": 12,
    "neighbors_depth": 2,
    "neighbors_per_file": 3,
    "neighbor_signature_budget": 500,
    "docs_tests_budget": 2000,
    "gpt_api": {
        "max_prompt_tokens": 60000,
        "max_output_tokens": 4000,
    },
    "codex_cli": {
        "max_prompt_tokens": None,
        "max_output_tokens": None,
    },
}


def _config_dir() -> Path:
    override = os.getenv(CONFIG_ENV_VAR)
    if override:
        path = Path(override).expanduser()
    else:
        path = DEFAULT_CONFIG_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path(filename: str) -> Path:
    return _config_dir() / filename


def _load_config(path: Path, defaults: Dict[str, object]) -> Tuple[Dict[str, object], str]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            merged = _merge_with_defaults(data, defaults)
            return merged, "file"
        except json.JSONDecodeError:
            pass
    return defaults.copy(), "default"


def _save_config(path: Path, payload: Dict[str, object], defaults: Dict[str, object]) -> Dict[str, object]:
    merged = _merge_with_defaults(payload, defaults)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    return merged


def _merge_with_defaults(payload: Dict[str, object], defaults: Dict[str, object]) -> Dict[str, object]:
    """Merge payload onto defaults, preserving default keys and types."""
    merged = {}
    for key, default_value in defaults.items():
        if key not in payload:
            merged[key] = default_value
            continue
        value = payload[key]
        if isinstance(default_value, dict) and isinstance(value, dict):
            merged[key] = _merge_with_defaults(value, default_value)
        else:
            merged[key] = value
    # include any additional keys present in payload
    for key, value in payload.items():
        if key not in merged:
            merged[key] = value
    return merged


def load_router_config() -> Tuple[Dict[str, object], str]:
    path = _config_path(ROUTER_FILENAME)
    return _load_config(path, DEFAULT_ROUTER_CONFIG)


def save_router_config(payload: Dict[str, object]) -> Dict[str, object]:
    path = _config_path(ROUTER_FILENAME)
    return _save_config(path, payload, DEFAULT_ROUTER_CONFIG)


def load_budget_config() -> Tuple[Dict[str, object], str]:
    path = _config_path(BUDGET_FILENAME)
    return _load_config(path, DEFAULT_BUDGET_CONFIG)


def save_budget_config(payload: Dict[str, object]) -> Dict[str, object]:
    path = _config_path(BUDGET_FILENAME)
    return _save_config(path, payload, DEFAULT_BUDGET_CONFIG)
