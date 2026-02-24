import sys
from pathlib import Path
from pkgutil import extend_path

from .core import (
    bore_helical,
    create_stock,
    detect_holes,
    detect_planar,
    drill_peck,
    fit_arcs,
    is_native_available,
    link_keepdown,
    load_step,
    make_setup,
    offset_inset,
    offset_outset,
    pocket_raster,
    post_gcode,
    profile_outline,
)

__path__ = extend_path(__path__, __name__)

_THIS_DIR = Path(__file__).resolve().parent
for _entry in list(sys.path):
    candidate = Path(_entry) / "skills" / "mill_ui" / "cam" / "native"
    if candidate.exists() and candidate != _THIS_DIR:
        candidate_str = str(candidate)
        if candidate_str not in __path__:
            __path__.append(candidate_str)

__all__ = [
    "bore_helical",
    "create_stock",
    "detect_holes",
    "detect_planar",
    "drill_peck",
    "fit_arcs",
    "is_native_available",
    "link_keepdown",
    "load_step",
    "make_setup",
    "offset_inset",
    "offset_outset",
    "pocket_raster",
    "post_gcode",
    "profile_outline",
]
