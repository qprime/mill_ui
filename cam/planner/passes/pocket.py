"""Pocketing and drilling strategy helpers."""
from __future__ import annotations

from typing import Any, Mapping, Sequence, TYPE_CHECKING, List

from cam.ops.bore import bore_helical, pocket_circle_concentric
from cam.ops.drill import drill_peck
from cam.ops.engrave import engrave_lines
from cam.ops.pocket_region import pocket_region_rect_raster
from cam.path.strategies import pocket_then_finish_profile
from cam.planner.registry import register_strategy

from .profile import circle_shape_mm, ensure_center, rect_shape
from .tools import (
    ToolSelection,
    pick_tool_for_engrave,
    pick_tool_for_hole,
    pick_tool_for_pocket,
    stepdown_for_tool,
    stepover_for_tool,
)

if TYPE_CHECKING:
    from cam.config import Config
    from . import PassAccumulator, PassRecord


def plan_pocket_passes(
    hints: Mapping[str, Any],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[Mapping[str, Any]],
    config: "Config",
) -> None:
    def _offset_moves_z(moves: List[dict], offset: float) -> List[dict]:
        if offset <= 0.0:
            return moves
        adj: List[dict] = []
        for mv in moves:
            clone = dict(mv)
            if "z" in clone and clone["z"] is not None:
                z_val = float(clone["z"])
                if z_val <= 0.0:
                    clone["z"] = z_val - offset
            adj.append(clone)
        return adj

    pockets = hints.get("pockets", []) or []
    for entry in pockets:
        geometry = entry.get("geometry") or {}
        shape_name = str(entry.get("shape") or entry.get("type") or "").lower()
        required_width = None
        if shape_name == "rect":
            required_width = min(float(geometry.get("w_mm", 0.0)), float(geometry.get("h_mm", 0.0)))
        elif shape_name == "circle":
            required_width = float(geometry.get("diameter_mm", 0.0))

        tool = pick_tool_for_pocket(
            tool_db,
            required_width_mm=required_width,
            cleanup_offset_mm=config.cleanup_offset_mm,
        )
        record = accumulator.get_record("pocket", tool)
        setup = record.setup
        depth = float(entry.get("depth_mm", 0.0))
        start_depth = max(0.0, float(entry.get("start_depth_mm", 0.0)))
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth
        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        if shape_name == "rect":
            width = float(geometry.get("w_mm", 0.0))
            height = float(geometry.get("h_mm", 0.0))
            shape = rect_shape(width, height, ensure_center(entry))
            record.add_moves(
                pocket_then_finish_profile(
                    shape,
                    setup,
                    total_depth_mm=depth,
                    stepover_mm=step_over,
                    step_down_mm=step_down,
                    cleanup_offset_mm=config.cleanup_offset_mm,
                    start_depth_mm=start_depth,
                    finish_perimeter=config.pocket_finish_perimeter,
                ),
                increment=1,
            )
        elif shape_name == "circle":
            diameter = float(geometry.get("diameter_mm", 0.0))
            moves = pocket_circle_concentric(
                ensure_center(entry),
                diameter,
                setup,
                depth=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
                finish=True,
            )
            record.add_moves(_offset_moves_z(moves, start_depth), increment=1)
        elif shape_name == "region":
            moves = pocket_region_rect_raster(
                entry,
                setup,
                default_center_xy=ensure_center(entry),
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
            )
            record.add_moves(_offset_moves_z(moves, start_depth), increment=1)
        else:
            continue


def plan_hole_passes(
    hints: Mapping[str, Any],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[Mapping[str, Any]],
) -> None:
    holes = hints.get("holes", []) or []
    for entry in holes:
        if str(entry.get("shape") or entry.get("type") or "").lower() != "circle":
            continue
        geometry = entry.get("geometry") or {}
        diameter = float(geometry.get("diameter_mm", 0.0))
        center = ensure_center(entry)
        depth = float(entry.get("depth_mm", 0.0))

        tool = pick_tool_for_hole(tool_db, hole_diameter_mm=diameter)
        tool_diameter = float(tool.diameter)
        eps = 0.05

        if diameter <= tool_diameter + eps:
            record = accumulator.get_record("drill", tool)
            peck = min(stepdown_for_tool(tool), 2.5)
            record.add_moves(
                drill_peck([center], record.setup, depth=depth, peck=peck),
                increment=1,
            )
        elif diameter <= 3.0 * tool_diameter + eps:
            record = accumulator.get_record("bore", tool)
            step_down = stepdown_for_tool(tool)
            record.add_moves(
                bore_helical(center, diameter, record.setup, depth=depth, stepdown_mm=step_down),
                increment=1,
            )
        else:
            record = accumulator.get_record("pocket", tool)
            step_over = stepover_for_tool(tool)
            step_down = stepdown_for_tool(tool)
            record.add_moves(
                pocket_circle_concentric(
                    center,
                    diameter,
                    record.setup,
                    depth=depth,
                    stepover_mm=step_over,
                    stepdown_mm=step_down,
                    finish=True,
                ),
                increment=1,
            )


def plan_engrave_passes(
    hints: Mapping[str, Any],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[Mapping[str, Any]],
) -> None:
    engraves = hints.get("engraves", []) or []
    for entry in engraves:
        geometry = entry.get("geometry") or {}
        shape_name = str(entry.get("shape") or entry.get("type") or "").lower()
        lines: list[list[tuple[float, float]]] = []

        if shape_name == "polyline":
            points = geometry.get("points") or []
            cx, cy = ensure_center(entry)
            line = []
            for pt in points:
                if isinstance(pt, (list, tuple)) and len(pt) == 2:
                    line.append((float(pt[0]) + cx, float(pt[1]) + cy))
            if line:
                lines.append(line)
        elif shape_name == "rect":
            width = float(geometry.get("w_mm", 0.0))
            height = float(geometry.get("h_mm", 0.0))
            if width <= 0.0 or height <= 0.0:
                continue
            cx, cy = ensure_center(entry)
            half_w = 0.5 * width
            half_h = 0.5 * height
            lines.append([
                (cx - half_w, cy - half_h),
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy + half_h),
                (cx - half_w, cy - half_h),
            ])
        else:
            continue

        if not lines:
            continue

        tool = pick_tool_for_engrave(tool_db)
        record = accumulator.get_record("engrave", tool)
        depth = float(entry.get("depth_mm", 0.0)) or 0.3
        record.add_moves(
            engrave_lines(lines, record.setup, z=-abs(depth)),
            increment=len(lines),
        )


def plan_corner_cleanup_passes(
    hints: Mapping[str, Any],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[Mapping[str, Any]],
) -> None:
    """Plan corner cleanup passes for rectangular pockets.

    Generates small circular pockets at each corner to remove material
    left by larger tools with radiused corners.

    Args:
        hints: Hints dict containing "corner_cleanups" list
        accumulator: PassAccumulator for grouping operations by tool
        tool_db: Available tools
    """
    corner_cleanups = hints.get("corner_cleanups", []) or []

    for entry in corner_cleanups:
        corner_tool_diameter = float(entry.get("corner_tool_diameter_mm", 0.0))
        if corner_tool_diameter <= 0.0:
            continue

        # Find tool matching the specified diameter
        tool = None
        for t in tool_db:
            if abs(float(t.get("diameter", 0.0)) - corner_tool_diameter) < 0.01:
                tool = ToolSelection(
                    diameter=float(t.get("diameter", corner_tool_diameter)),
                    kind=t.get("kind", "flat"),
                    name=t.get("name", "corner_tool"),
                    rpm=float(t.get("rpm", 18000)),
                    feed_xy=float(t.get("feed_xy", 1000)),
                    feed_z=float(t.get("feed_z", 300)),
                    depth_per_pass=float(t.get("depth_per_pass", 3.0)),
                    stepover_percent=float(t.get("stepover_percent", 40)),
                )
                break

        if tool is None:
            raise ValueError(
                f"Corner cleanup tool with diameter {corner_tool_diameter}mm not found in tool_db. "
                f"Available tools: {[t.get('diameter') for t in tool_db]}"
            )

        record = accumulator.get_record("corner_cleanup", tool)
        setup = record.setup

        depth = float(entry.get("depth_mm", 0.0))
        start_depth = float(entry.get("start_depth_mm", 0.0))
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth

        corners = entry.get("corners", [])
        if not corners:
            continue

        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        # Generate small circular pocket at each corner
        # The diameter should be just enough to clear the radiused corner
        # Calculate from parent pocket's primary tool radius
        geometry = entry.get("geometry", {})
        # We don't have primary tool info here, so use a heuristic:
        # Corner pocket diameter = 2x corner tool diameter (conservative)
        corner_pocket_diameter = 2.0 * corner_tool_diameter

        for corner_xy in corners:
            moves = pocket_circle_concentric(
                corner_xy,
                corner_pocket_diameter,
                setup,
                depth=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
                finish=True,
            )
            # Offset moves if start_depth is non-zero
            if start_depth > 0.0:
                adjusted_moves: List[dict] = []
                for mv in moves:
                    clone = dict(mv)
                    if "z" in clone and clone["z"] is not None:
                        z_val = float(clone["z"])
                        if z_val <= 0.0:
                            clone["z"] = z_val - start_depth
                    adjusted_moves.append(clone)
                moves = adjusted_moves

            record.add_moves(moves, increment=1)


register_strategy("pocket", "rect_raster", pocket_then_finish_profile)
register_strategy("pocket", "circle_concentric", pocket_circle_concentric)
register_strategy("pocket", "region_rect_raster", pocket_region_rect_raster)


__all__ = [
    "plan_engrave_passes",
    "plan_hole_passes",
    "plan_pocket_passes",
    "plan_corner_cleanup_passes",
]
