"""Operate command policy management for ACE."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "ace_control" / "operate_policy.json"
ALLOWED_VALUES = {"accept", "verify", "escalate"}
DEFAULT_VALUE = "accept"
DEFAULT_KNOWN_TYPES = (
    "operate_action.freeform",
    "command.shell",
    "command.git",
    "command.docker",
    "command.systemctl",
    "command.curl",
)


@dataclass(frozen=True)
class PolicyDecision:
    value: str
    command_types: Tuple[str, ...]

    @property
    def is_accept(self) -> bool:
        return self.value == "accept"

    @property
    def is_verify(self) -> bool:
        return self.value == "verify"

    @property
    def is_escalate(self) -> bool:
        return self.value == "escalate"


def _load() -> Dict[str, str]:
    if POLICY_PATH.exists():
        try:
            data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if str(v) in ALLOWED_VALUES}
        except json.JSONDecodeError:
            pass
    return {}


def _save(policy: Dict[str, str]) -> None:
    POLICY_PATH.write_text(json.dumps(policy, indent=2, sort_keys=True), encoding="utf-8")


def get_policy() -> Dict[str, str]:
    return _load()


def set_policy(policy: Dict[str, str]) -> Dict[str, str]:
    cleaned = {
        str(k): (str(v) if str(v) in ALLOWED_VALUES else DEFAULT_VALUE)
        for k, v in policy.items()
    }
    _save(cleaned)
    return cleaned


def update_policy(updates: Dict[str, str]) -> Dict[str, str]:
    policy = _load()
    for key, value in updates.items():
        value_str = str(value)
        if value_str not in ALLOWED_VALUES:
            continue
        policy[str(key)] = value_str
    _save(policy)
    return policy


def ensure_command_type(command_type: str, *, default: str = DEFAULT_VALUE) -> None:
    policy = _load()
    if command_type not in policy:
        policy[command_type] = default if default in ALLOWED_VALUES else DEFAULT_VALUE
        _save(policy)


def evaluate_command_types(command_types: Iterable[str]) -> PolicyDecision:
    policy = _load()
    seen = []
    highest = DEFAULT_VALUE
    for command_type in command_types:
        if command_type not in policy:
            policy[command_type] = DEFAULT_VALUE
            seen.append(command_type)
        else:
            seen.append(command_type)
        value = policy.get(command_type, DEFAULT_VALUE)
        if value == "escalate":
            highest = "escalate"
            break
        if value == "verify" and highest != "escalate":
            highest = "verify"
    if seen:
        _save(policy)
    return PolicyDecision(value=highest, command_types=tuple(seen))


def known_types() -> Tuple[str, ...]:
    policy = _load()
    combined = set(DEFAULT_KNOWN_TYPES)
    combined.update(policy.keys())
    return tuple(sorted(combined))


def reset() -> None:  # pragma: no cover - helper for tests
    if POLICY_PATH.exists():
        POLICY_PATH.unlink()
