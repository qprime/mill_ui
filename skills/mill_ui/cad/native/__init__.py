"""Native CAD bindings facade."""

from pathlib import Path
from pkgutil import extend_path
import sys

__path__ = extend_path(__path__, __name__)

_THIS_DIR = Path(__file__).resolve().parent
for _entry in list(sys.path):
    candidate = Path(_entry) / "skills" / "mill_ui" / "cad" / "native"
    if candidate.exists() and candidate != _THIS_DIR:
        candidate_str = str(candidate)
        if candidate_str not in __path__:
            __path__.append(candidate_str)

from .core import (
    is_native_available,
    build_model,
    export_stl,
    export_step,
)

__all__ = [
    "is_native_available",
    "build_model",
    "export_stl",
    "export_step",
]
