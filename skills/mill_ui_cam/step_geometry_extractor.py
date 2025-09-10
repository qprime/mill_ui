"""STEP helpers used by the CAM generator (bounds + XY circle detection)."""

from __future__ import annotations
from pathlib import Path
from typing import Tuple, List, Dict

import cadquery as cq


def _load_shape(step_path: Path):
    """Import STEP and return a top-level CadQuery Shape."""
    result = cq.importers.importStep(str(step_path))
    if hasattr(result, "val"):
        return result.val()  # Workplane -> Shape
    return result


def get_step_bounds(step_path: Path) -> Tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return ((min_x,min_y,min_z),(max_x,max_y,max_z)) for the combined shape."""
    shape = _load_shape(step_path)
    bb = shape.BoundingBox()
    return (
        (float(bb.xmin), float(bb.ymin), float(bb.zmin)),
        (float(bb.xmax), float(bb.ymax), float(bb.zmax)),
    )


def find_circles_xy(step_path: Path) -> List[Dict[str, float]]:
    """
    Find circular edges that are (approximately) planar in XY.
    We detect circles by edge geomType() and take center/radius from the edge's bbox.
    Returns a list of dicts: {center_x, center_y, z, radius_mm}
    """
    shape = _load_shape(step_path)
    circles: List[Dict[str, float]] = []

    # scan edges for circular geometry
    for edge in shape.Edges():
        try:
            if edge.geomType() != "CIRCLE":
                continue
        except Exception:
            continue

        bb = edge.BoundingBox()
        xmin, ymin, zmin = float(bb.xmin), float(bb.ymin), float(bb.zmin)
        xmax, ymax, zmax = float(bb.xmax), float(bb.ymax), float(bb.zmax)

        # treat as XY circle if it is effectively flat in Z
        if abs(zmax - zmin) > 1e-4:
            continue

        cx = (xmin + xmax) * 0.5
        cy = (ymin + ymax) * 0.5
        r = max((xmax - xmin), (ymax - ymin)) * 0.5

        if r <= 0:
            continue

        circles.append(
            {
                "center_x": float(cx),
                "center_y": float(cy),
                "z": float(zmin),
                "radius_mm": float(r),
            }
        )

    return circles
