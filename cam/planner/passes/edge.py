from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
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


def vbit_cut_depth(width_mm: float, chamfer_angle_deg: float) -> float:
    if 0.0 < chamfer_angle_deg < 90.0:
        return width_mm * math.tan(math.radians(chamfer_angle_deg))
    return width_mm


def vbit_effective_radius(depth_mm: float, v_angle_deg: float) -> float:
    half_angle = math.radians(v_angle_deg / 2.0)
    return depth_mm * math.tan(half_angle)


@dataclass(frozen=True)
class EdgeCutPlan:
    shape: Shape2D
    tool: ToolSelection
    depth_mm: float


def build_edge_cut_plan(entry: EdgeFeatureInput, tool_db: Sequence[ToolSelection]) -> EdgeCutPlan:
    spec = entry.edge_feature
    if spec is None:
        raise ValueError(f"Edge feature '{entry.id}': no edge_feature spec")
    if isinstance(spec, (ChamferSpec, BevelSpec)):
        desired_angle = spec.angle_deg * 2.0
        try:
            tool = pick_tool_for_edge(tool_db, angle_deg=desired_angle)
        except ValueError as exc:
            raise ValueError(f"Edge feature '{entry.id}': no V-bit with {desired_angle}° angle available") from exc
        depth = vbit_cut_depth(spec.width_mm, spec.angle_deg)
        if depth <= 0.0:
            raise ValueError(f"Edge feature '{entry.id}': cut depth must be positive, got {depth}mm")
        angle = tool.v_angle_deg
        if angle is None or angle <= 0.0:
            raise ValueError(
                f"Edge feature '{entry.id}': V-bit '{tool.name}': v_angle_deg must be positive, got {angle}"
            )
        offset = vbit_effective_radius(depth, angle)
    elif isinstance(spec, RoundoverSpec):
        try:
            tool = pick_tool_for_roundover(tool_db, radius_mm=spec.radius_mm)
        except ValueError as exc:
            raise ValueError(
                f"Edge feature '{entry.id}': no roundover bit with {spec.radius_mm}mm radius available"
            ) from exc
        depth = offset = spec.radius_mm
    else:
        raise ValueError(f"Edge feature '{entry.id}': unknown spec type '{type(spec).__name__}'")
    if (entry.side or "outside").lower() == "inside":
        offset = -offset
    shape = _build_offset_shape(entry, offset)
    if shape is None:
        raise ValueError(f"Edge feature '{entry.id}': unsupported shape '{entry.shape}'")
    return EdgeCutPlan(shape, tool, depth + entry.start_depth_mm)


def plan_edge_feature_passes(
    edge_features: tuple[EdgeFeatureInput, ...], *, accumulator: PassAccumulator, tool_db: Sequence[ToolSelection]
) -> None:
    for entry in edge_features:
        try:
            plan = build_edge_cut_plan(entry, tool_db)
        except ValueError as exc:
            accumulator.add_error(str(exc))
            continue
        record = accumulator.get_record("edge", plan.tool)
        moves = profile_outline(plan.shape, record.setup, plan.depth_mm, step_down=stepdown_for_tool(plan.tool))
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

    return None


__all__ = [
    "EdgeCutPlan",
    "build_edge_cut_plan",
    "plan_edge_feature_passes",
    "vbit_cut_depth",
    "vbit_effective_radius",
]
