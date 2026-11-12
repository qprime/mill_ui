from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry.base import BaseGeometry

from cam.moves import CutMove
from cam.ops.profile import profile_outline
from cam.planner.planner_input import EdgeFeatureInput
from cam.shape import Shape2D
from core.geometry import chamfer_included_angle
from ir.removal_intent import BevelSpec, ChamferSpec, RoundoverSpec
from layout_ast.raised_panel import RaisedPanelSpec

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

_EDGE_DIMENSION_TOLERANCE_MM = 1e-3
_RAISED_PANEL_ARC_TOLERANCE_MM = 5e-4


def vbit_cut_depth(width_mm: float, chamfer_angle_deg: float) -> float:
    if 0.0 < chamfer_angle_deg < 90.0:
        return width_mm * math.tan(math.radians(chamfer_angle_deg))
    return width_mm


def vbit_effective_radius(depth_mm: float, v_angle_deg: float) -> float:
    half_angle = math.radians(v_angle_deg / 2.0)
    return depth_mm * math.tan(half_angle)


@dataclass(frozen=True)
class PocketCutPlan:
    region: BaseGeometry
    tool: ToolSelection
    depth_mm: float


@dataclass(frozen=True)
class EdgeCutPlan:
    shape: Shape2D
    tool: ToolSelection
    depth_mm: float
    pockets: tuple[PocketCutPlan, ...] = ()


def build_edge_cut_plan(entry: EdgeFeatureInput, tool_db: Sequence[ToolSelection]) -> EdgeCutPlan:
    spec = entry.edge_feature
    if isinstance(spec, RaisedPanelSpec):
        from .raised_panel import build_raised_panel_plan

        return build_raised_panel_plan(entry, tool_db)
    return _build_standard_edge_cut_plan(entry, tool_db)


def _build_standard_edge_cut_plan(entry: EdgeFeatureInput, tool_db: Sequence[ToolSelection]) -> EdgeCutPlan:
    spec = entry.edge_feature
    if spec is None:
        raise ValueError(f"Edge feature '{entry.id}': no edge_feature spec")
    if isinstance(spec, (ChamferSpec, BevelSpec)):
        if isinstance(spec, ChamferSpec) and not 0 < spec.angle_deg < 90:
            raise ValueError(
                f"Edge feature '{entry.id}': chamfer angle must be between 0 and 90°, got {spec.angle_deg}"
            )
        desired_angle = (
            chamfer_included_angle(spec.angle_deg) if isinstance(spec, ChamferSpec) else spec.angle_deg * 2.0
        )
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
        if isinstance(spec, ChamferSpec):
            radius = tool.diameter / 2
            if not math.isfinite(radius) or radius <= 0:
                raise ValueError(f"Edge feature '{entry.id}': invalid cutter radius {radius}mm")
            if spec.width_mm > radius + _EDGE_DIMENSION_TOLERANCE_MM:
                raise ValueError(
                    f"Edge feature '{entry.id}': chamfer width {spec.width_mm}mm exceeds cutter radius {radius}mm"
                )
            if not math.isclose(
                vbit_effective_radius(depth, angle), spec.width_mm, rel_tol=0, abs_tol=_EDGE_DIMENSION_TOLERANCE_MM
            ):
                raise ValueError(
                    f"Edge feature '{entry.id}': V-bit '{tool.name}' ({angle}°) cannot cut requested chamfer "
                    f"width {spec.width_mm}mm and depth {depth}mm; requires {desired_angle}°"
                )
            offset = 0.0
        else:
            offset = vbit_effective_radius(depth, angle)
    elif isinstance(spec, RoundoverSpec):
        tool, depth, offset = _roundover_cut_parameters(entry.id, spec, tool_db)
    else:
        raise ValueError(f"Edge feature '{entry.id}': unknown spec type '{type(spec).__name__}'")
    if (entry.side or "outside").lower() == "inside":
        offset = -offset
    shape = _build_offset_shape(entry, offset)
    if shape is None:
        raise ValueError(f"Edge feature '{entry.id}': unsupported shape '{entry.shape}'")
    return EdgeCutPlan(shape, tool, depth + entry.start_depth_mm)


def _roundover_cut_parameters(
    feature_id: str, spec: RoundoverSpec, tool_db: Sequence[ToolSelection]
) -> tuple[ToolSelection, float, float]:
    radius = spec.radius_mm
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError(f"Edge feature '{feature_id}': roundover radius must be finite and positive, got {radius}")
    try:
        tool = pick_tool_for_roundover(tool_db, radius_mm=radius)
    except ValueError as exc:
        raise ValueError(f"Edge feature '{feature_id}': no roundover bit with {radius}mm radius available") from exc
    selected_radius = tool.roundover_radius_mm
    if selected_radius is None or not math.isclose(
        selected_radius, radius, rel_tol=0, abs_tol=_EDGE_DIMENSION_TOLERANCE_MM
    ):
        raise ValueError(
            f"Edge feature '{feature_id}': roundover bit '{tool.name}' has radius {selected_radius}mm; requires {radius}mm"
        )
    nose_radius = tool.diameter / 2 - selected_radius
    if not math.isfinite(nose_radius) or nose_radius < 0:
        raise ValueError(
            f"Edge feature '{feature_id}': roundover diameter {tool.diameter}mm cannot contain radius {selected_radius}mm"
        )
    return tool, radius, nose_radius


def plan_edge_feature_passes(
    edge_features: tuple[EdgeFeatureInput, ...], *, accumulator: PassAccumulator, tool_db: Sequence[ToolSelection]
) -> None:
    for entry in edge_features:
        if isinstance(entry.edge_feature, RaisedPanelSpec) and entry.depth_mm >= accumulator.stock.thickness:
            accumulator.add_error(
                f"RaisedPanel '{entry.id}': border depth {entry.depth_mm}mm must be less than stock thickness {accumulator.stock.thickness}mm"
            )
            continue
        try:
            plan = build_edge_cut_plan(entry, tool_db)
        except ValueError as exc:
            accumulator.add_error(str(exc))
            continue
        from .pocket import _offset_pocket_moves

        for pocket in plan.pockets:
            pocket_record = accumulator.get_record("pocket_offset", pocket.tool)
            pocket_moves = _offset_pocket_moves(
                pocket.region,
                pocket.tool,
                pocket_record.setup,
                depth_mm=pocket.depth_mm,
                wall_allowance_mm=0,
                arc_tolerance_mm=_RAISED_PANEL_ARC_TOLERANCE_MM,
            )
            if not any(isinstance(move, CutMove) for move in pocket_moves):
                accumulator.add_error(f"RaisedPanel '{entry.id}': required pocket produced no cutting moves")
                continue
            pocket_record.add_moves(pocket_moves, increment=1)
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
