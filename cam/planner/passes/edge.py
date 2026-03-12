from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from cam.ops.profile import profile_outline
from cam.planner.planner_input import EdgeFeatureInput
from cam.shape import Shape2D
from ir.removal_intent import BevelSpec, ChamferSpec, RoundoverSpec

from .profile import (
    offset_circle_shape,
    offset_polygon_shape,
    offset_rect_shape,
    offset_rounded_rect_shape,
    polygon_shape,
)
from .tools import ToolSelection, pick_tool_for_edge, pick_tool_for_roundover, stepdown_for_tool

if TYPE_CHECKING:
    from cam.planner.passes import PassAccumulator

_logger = logging.getLogger(__name__)


def vbit_cut_depth(width_mm: float, chamfer_angle_deg: float) -> float:
    if 0.0 < chamfer_angle_deg < 90.0:
        return width_mm * math.tan(math.radians(chamfer_angle_deg))
    return width_mm


def vbit_effective_radius(depth_mm: float, v_angle_deg: float) -> float:
    half_angle = math.radians(v_angle_deg / 2.0)
    return depth_mm * math.tan(half_angle)


def plan_edge_feature_passes(
    edge_features: tuple[EdgeFeatureInput, ...],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in edge_features:
        spec = entry.edge_feature
        if spec is None:
            _logger.warning("Edge feature '%s' has no edge_feature spec — skipping", entry.id)
            continue

        if isinstance(spec, (ChamferSpec, BevelSpec)):
            _plan_vbit_pass(entry, spec, accumulator, tool_db)
        elif isinstance(spec, RoundoverSpec):
            _plan_roundover_pass(entry, spec, accumulator, tool_db)
        else:
            _logger.warning("Edge feature '%s' has unknown spec type — skipping", entry.id)


def _plan_vbit_pass(
    entry: EdgeFeatureInput,
    spec: ChamferSpec | BevelSpec,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    desired_angle = spec.angle_deg * 2.0

    try:
        tool = pick_tool_for_edge(tool_db, angle_deg=desired_angle)
    except ValueError:
        _logger.warning("Edge feature '%s': no V-bit available — skipping", entry.id)
        return

    cut_depth = vbit_cut_depth(spec.width_mm, spec.angle_deg)
    if cut_depth <= 0.0:
        return

    v_angle = tool.v_angle_deg
    if v_angle is None or v_angle <= 0.0:
        _logger.warning("Edge feature '%s': V-bit has no v_angle_deg — skipping", entry.id)
        return

    offset = vbit_effective_radius(cut_depth, v_angle)

    side = (entry.side or "outside").lower()
    if side == "inside":
        offset = -offset

    shape = _build_offset_shape(entry, offset)
    if shape is None:
        return

    record = accumulator.get_record("edge", tool)
    step_down = stepdown_for_tool(tool)
    total_depth = cut_depth + entry.start_depth_mm
    moves = profile_outline(shape, record.setup, total_depth, step_down=step_down)
    record.add_moves(moves, increment=1)


def _plan_roundover_pass(
    entry: EdgeFeatureInput,
    spec: RoundoverSpec,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    try:
        tool = pick_tool_for_roundover(tool_db, radius_mm=spec.radius_mm)
    except ValueError:
        _logger.warning("Edge feature '%s': no roundover bit available — skipping", entry.id)
        return

    offset = spec.radius_mm

    side = (entry.side or "outside").lower()
    if side == "inside":
        offset = -offset

    shape = _build_offset_shape(entry, offset)
    if shape is None:
        return

    record = accumulator.get_record("edge", tool)
    step_down = stepdown_for_tool(tool)
    total_depth = spec.radius_mm + entry.start_depth_mm
    moves = profile_outline(shape, record.setup, total_depth, step_down=step_down)
    record.add_moves(moves, increment=1)


def _build_offset_shape(entry: EdgeFeatureInput, offset: float) -> Shape2D | None:
    shape_type = entry.shape.lower()
    geom = entry.geometry.geometry

    if shape_type == "rect":
        w = float(geom.w_mm or 0.0)
        h = float(geom.h_mm or 0.0)
        return offset_rect_shape(w, h, entry.center_xy_mm, offset)

    if shape_type == "circle":
        d = float(geom.diameter_mm or 0.0)
        return offset_circle_shape(d, entry.center_xy_mm, offset)

    if shape_type == "polygon":
        raw_points = geom.points
        points = [list(p) for p in raw_points] if raw_points is not None else []
        if not points:
            return None
        if abs(offset) < 1e-9:
            return polygon_shape(points, entry.center_xy_mm)
        return offset_polygon_shape(points, entry.center_xy_mm, offset)

    if shape_type == "roundedrect":
        w = float(geom.w_mm or 0.0)
        h = float(geom.h_mm or 0.0)
        fallback_r = float(geom.radius_mm or 0.0)
        radii = {
            "tl": float(geom.radius_tl_mm if geom.radius_tl_mm is not None else fallback_r),
            "tr": float(geom.radius_tr_mm if geom.radius_tr_mm is not None else fallback_r),
            "br": float(geom.radius_br_mm if geom.radius_br_mm is not None else fallback_r),
            "bl": float(geom.radius_bl_mm if geom.radius_bl_mm is not None else fallback_r),
        }
        return offset_rounded_rect_shape(w, h, radii, entry.center_xy_mm, offset)

    _logger.warning("Edge feature shape '%s' not supported — skipping", entry.shape)
    return None


__all__ = [
    "plan_edge_feature_passes",
    "vbit_cut_depth",
    "vbit_effective_radius",
]
