# name: __init__.py
# path: services/__init__.py
# role: Expose services CLI entrypoint
# deps: services.cli
# inputs: args
# outputs: api function

from __future__ import annotations

from services.cli import api

__all__ = ["api"]
