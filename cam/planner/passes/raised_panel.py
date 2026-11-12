from __future__ import annotations

import math
from collections.abc import Sequence

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from cam.planner.planner_input import EdgeFeatureInput
from core.geometry import pocket_region
from layout_ast.raised_panel import RaisedPanelSpec

from .edge import EdgeCutPlan, PocketCutPlan
from .profile import polygon_shape
from .tools import ToolSelection, pick_tool_for_edge, pick_tool_for_region


def build_raised_panel_plan(entry: EdgeFeatureInput, tools: Sequence[ToolSelection]) -> EdgeCutPlan:
    spec = entry.edge_feature
    if not isinstance(spec, RaisedPanelSpec):
        raise ValueError("RaisedPanel requires its profile specification")
    if entry.start_depth_mm != 0:
        raise ValueError(f"RaisedPanel '{entry.id}': nonzero starting surfaces are not supported")
    if not math.isclose(entry.depth_mm, spec.border_depth_mm, rel_tol=0, abs_tol=1e-9):
        raise ValueError(
            f"RaisedPanel '{entry.id}': depth {entry.depth_mm}mm disagrees with profile depth {spec.border_depth_mm}mm"
        )
    region = pocket_region(entry.shape, entry.geometry.geometry, entry.center_xy_mm, ())
    if not isinstance(region, Polygon) or not region.is_valid or region.interiors:
        raise ValueError(f"RaisedPanel '{entry.id}': requires a valid single outline without holes")
    field = region.buffer(-spec.field_inset_mm, join_style="mitre")
    groove = region.buffer(-spec.groove_inset_mm, join_style="mitre")
    if any(not isinstance(p, Polygon) or p.is_empty or not p.is_valid or p.interiors for p in (field, groove)):
        raise ValueError(f"RaisedPanel '{entry.id}': profile insets leave no single connected field or groove")
    if groove.boundary.distance(field) < spec.slope_run_mm - 1e-6:
        raise ValueError(f"RaisedPanel '{entry.id}': V-bit slope would gouge the declared center field")
    try:
        tool = pick_tool_for_edge(tools, angle_deg=spec.v_angle_deg)
    except ValueError as exc:
        raise ValueError(f"RaisedPanel '{entry.id}': {exc}") from exc
    if tool.v_angle_deg is None or not math.isclose(tool.v_angle_deg, spec.v_angle_deg, rel_tol=0, abs_tol=1e-6):
        raise ValueError(
            f"RaisedPanel '{entry.id}': requires a {spec.v_angle_deg:g}° V-bit; nearest is {tool.v_angle_deg}°"
        )
    if (
        not math.isfinite(tool.diameter)
        or tool.diameter <= 0
        or spec.cutter_radius_at_depth_mm > tool.diameter / 2 + 1e-6
    ):
        raise ValueError(
            f"RaisedPanel '{entry.id}': V-bit diameter {tool.diameter}mm cannot reach depth {spec.border_depth_mm}mm at {spec.v_angle_deg}°"
        )
    swept = groove.boundary.buffer(spec.cutter_radius_at_depth_mm, quad_segs=64)
    if not region.buffer(1e-6).covers(swept):
        raise ValueError(f"RaisedPanel '{entry.id}': V-bit cutting footprint would leave the cell")
    pockets: list[PocketCutPlan] = []
    if spec.profile == "gutter":
        pockets.append(_pocket_plan(region.difference(groove), tools, spec.border_depth_mm, entry.id))
    if spec.field_depth_mm > 0:
        pockets.append(_pocket_plan(field, tools, spec.field_depth_mm, entry.id))
    shape = polygon_shape([[float(x), float(y)] for x, y in groove.exterior.coords[:-1]], (0, 0))
    return EdgeCutPlan(shape, tool, spec.border_depth_mm, tuple(pockets))


def _pocket_plan(region: BaseGeometry, tools: Sequence[ToolSelection], depth: float, feature_id: str) -> PocketCutPlan:
    try:
        tool = pick_tool_for_region(tools, region, cleanup_offset_mm=0)
    except ValueError as exc:
        raise ValueError(f"RaisedPanel '{feature_id}': {exc}") from exc
    if tool is None:
        raise ValueError(f"RaisedPanel '{feature_id}': no flat tool fits the required pocket")
    return PocketCutPlan(region, tool, depth)
