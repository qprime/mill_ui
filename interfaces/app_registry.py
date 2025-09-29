from __future__ import annotations
from typing import Callable, Iterable

from flask import Flask

from .apps.chat.manifest import register as register_chat
from .apps.ctx.manifest import register as register_ctx
from .apps.ltp.manifest import register as register_ltp
from .apps.system.manifest import register as register_system
from .apps.tasks.manifest import register as register_tasks


def _manifests() -> Iterable[Callable[[Flask], None]]:
    yield register_chat
    yield register_tasks
    yield register_ltp
    yield register_ctx
    yield register_system


def register_all_apps(app: Flask) -> None:
    for manifest in _manifests():
        manifest(app)
