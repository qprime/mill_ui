from __future__ import annotations

from typing import Callable, Dict, Tuple

from ..models import Action, Capsule, Memory
from ..registry import MemoryRegistry

ExecutorFn = Callable[[Action, Capsule, MemoryRegistry], Tuple[Memory, list[Memory], dict]]

_EXECUTORS: Dict[str, ExecutorFn] = {}


def register_executor(name: str, fn: ExecutorFn) -> None:
    _EXECUTORS[name] = fn


def get_executor(name: str) -> ExecutorFn:
    if name not in _EXECUTORS:
        raise KeyError(f"Unknown executor {name}")
    return _EXECUTORS[name]


# Import side effects to register executors
from . import codex_cli  # noqa: E402,F401
from . import ops_shell  # noqa: E402,F401
from . import prose_llm  # noqa: E402,F401
