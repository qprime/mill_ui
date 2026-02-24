from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from cam.ops.bore import bore_helical, pocket_circle_concentric
from cam.ops.drill import drill_peck
from cam.ops.engrave import engrave_lines
from cam.ops.pocket_region import pocket_region_rect_raster
from cam.path.strategies import pocket_then_finish_profile
from cam.path.toolpath import offset_moves_z
from cam.planner.planner_input import FeatureInput, CornerCleanupInput
from .profile import circle_shape_mm, rect_shape
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
    pockets: tuple[FeatureInput, ...],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[ToolSelection],
    config: "Config",
) -> None:
    for entry in pockets:
        sg = entry.geometry.geometry
        shape_name = entry.shape.lower()
        required_width = None
        if shape_name == "rect":
            required_width = min(float(sg.w_mm or 0.0), float(sg.h_mm or 0.0))
        elif shape_name == "circle":
            required_width = float(sg.diameter_mm or 0.0)

        tool = pick_tool_for_pocket(
            tool_db,
            required_width_mm=required_width,
            cleanup_offset_mm=config.cleanup_offset_mm,
        )
        record = accumulator.get_record("pocket", tool)
        setup = record.setup
        depth = entry.depth_mm
        start_depth = max(0.0, entry.start_depth_mm)
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth
        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        center = entry.center_xy_mm

        if shape_name == "rect":
            width = float(sg.w_mm or 0.0)
            height = float(sg.h_mm or 0.0)
            shape = rect_shape(width, height, center)
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
            diameter = float(sg.diameter_mm or 0.0)
            moves = pocket_circle_concentric(
                center,
                diameter,
                setup,
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
                finish=True,
            )
            record.add_moves(offset_moves_z(moves, start_depth), increment=1)
        elif shape_name == "region":
            moves = pocket_region_rect_raster(
                entry.to_dict(),
                setup,
                default_center_xy=center,
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
            )
            record.add_moves(offset_moves_z(moves, start_depth), increment=1)
        else:
            continue


def plan_hole_passes(
    holes: tuple[FeatureInput, ...],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in holes:
        if entry.shape.lower() != "circle":
            continue
        diameter = float(entry.geometry.geometry.diameter_mm or 0.0)
        center = entry.center_xy_mm
        depth = entry.depth_mm

        tool = pick_tool_for_hole(tool_db, hole_diameter_mm=diameter)
        tool_diameter = float(tool.diameter)
        eps = 0.05

        if diameter <= tool_diameter + eps:
            record = accumulator.get_record("drill", tool)
            peck = min(stepdown_for_tool(tool), 2.5)
            record.add_moves(
                drill_peck([center], record.setup, depth_mm=depth, peck=peck),
                increment=1,
            )
        elif diameter <= 3.0 * tool_diameter + eps:
            record = accumulator.get_record("bore", tool)
            step_down = stepdown_for_tool(tool)
            record.add_moves(
                bore_helical(center, diameter, record.setup, depth_mm=depth, stepdown_mm=step_down),
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
                    depth_mm=depth,
                    stepover_mm=step_over,
                    stepdown_mm=step_down,
                    finish=True,
                ),
                increment=1,
            )


def plan_engrave_passes(
    engraves: tuple[FeatureInput, ...],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in engraves:
        sg = entry.geometry.geometry
        shape_name = entry.shape.lower()
        lines: list[list[tuple[float, float]]] = []

        if shape_name == "polyline":
            raw_points = sg.points or ()
            cx, cy = entry.center_xy_mm
            line = [(float(pt[0]) + cx, float(pt[1]) + cy) for pt in raw_points]
            if line:
                lines.append(line)
        elif shape_name == "rect":
            width = float(sg.w_mm or 0.0)
            height = float(sg.h_mm or 0.0)
            if width <= 0.0 or height <= 0.0:
                continue
            cx, cy = entry.center_xy_mm
            half_w = 0.5 * width
            half_h = 0.5 * height
            lines.append([
                (cx - half_w, cy - half_h),
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy + half_h),
                (cx - half_w, cy - half_h),
            ])
        elif shape_name == "line":
            start = sg.start or (0.0, 0.0)
            end = sg.end or (0.0, 0.0)
            cx, cy = entry.center_xy_mm
            lines.append([
                (float(start[0]) + cx, float(start[1]) + cy),
                (float(end[0]) + cx, float(end[1]) + cy),
            ])
        else:
            continue

        if not lines:
            continue

        tool = pick_tool_for_engrave(tool_db)
        record = accumulator.get_record("engrave", tool)
        depth = entry.depth_mm or 0.3
        record.add_moves(
            engrave_lines(lines, record.setup, z=-abs(depth)),
            increment=len(lines),
        )


def plan_corner_cleanup_passes(
    corner_cleanups: tuple[CornerCleanupInput, ...],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in corner_cleanups:
        corner_tool_diameter = entry.corner_tool_diameter_mm
        if corner_tool_diameter <= 0.0:
            continue

        tool = None
        for t in tool_db:
            if abs(t.diameter - corner_tool_diameter) < 0.01:
                tool = t
                break

        if tool is None:
            raise ValueError(
                f"Corner cleanup tool with diameter {corner_tool_diameter}mm not found in tool_db. "
                f"Available tools: {[t.diameter for t in tool_db]}"
            )

        record = accumulator.get_record("corner_cleanup", tool)
        setup = record.setup

        depth = entry.depth_mm
        start_depth = entry.start_depth_mm
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth

        corners = entry.corners
        if not corners:
            continue

        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        corner_pocket_diameter = 2.0 * corner_tool_diameter

        for corner_xy in corners:
            moves = pocket_circle_concentric(
                corner_xy,
                corner_pocket_diameter,
                setup,
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
                finish=True,
            )

            moves = offset_moves_z(moves, start_depth)
            record.add_moves(moves, increment=1)


__all__ = [
    "plan_engrave_passes",
    "plan_hole_passes",
    "plan_pocket_passes",
    "plan_corner_cleanup_passes",
]
