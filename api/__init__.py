"""Public API re-exports for the CAM toolkit."""
from __future__ import annotations

from . import cad as _cad
from . import cam as _cam
from . import io as _io

__all__ = []  # populated below

for module in (_cad, _cam, _io):
    names = getattr(module, "__all__", [])
    for name in names:
        globals()[name] = getattr(module, name)
    __all__.extend(names)

__all__ = sorted(set(__all__))
