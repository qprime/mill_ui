from __future__ import annotations
from typing import Iterable, Callable
from flask import Flask

# Explicit manifests
from .apps.chat.manifest import register as register_chat
from .apps.tasks.manifest import register as register_tasks

def _manifests() -> Iterable[Callable[[Flask], None]]:
    yield register_chat
    yield register_tasks

def register_all_apps(app: Flask) -> None:
    for reg in _manifests():
        reg(app)
