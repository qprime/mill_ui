"""Pocketing and drilling strategy helpers."""
from __future__ import annotations

from typing import Any, Mapping, Sequence, TYPE_CHECKING

from skills.mill_ui.cam.ops.bore import bore_helical, pocket_circle_concentric
from skills.mill_ui.cam.ops.drill import drill_peck
from skills.mill_ui.cam.ops.engrave import engrave_lines
from skills.mill_ui.cam.ops.pocket_region import pocket_region_rect_raster
from skills.mill_ui.cam.path.strategies import pocket_then_finish_profile

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
    from skills.mill_ui.core.config import Config
    from . import PassAccumulator, PassRecord


def plan_pocket_passes(
    hints: Mapping[str, Any],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[Mapping[str, Any]],
    config: "Config",
) -> None:
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
                ),
                increment=1,
            )
        elif shape_name == "circle":
            diameter = float(geometry.get("diameter_mm", 0.0))
            record.add_moves(
                pocket_circle_concentric(
                    ensure_center(entry),
                    diameter,
                    setup,
                    depth=depth,
                    stepover_mm=step_over,
                    stepdown_mm=step_down,
                    finish=True,
                ),
                increment=1,
            )
        elif shape_name == "region":
            record.add_moves(
                pocket_region_rect_raster(
                    entry,
                    setup,
                    default_center_xy=ensure_center(entry),
                    depth_mm=depth,
                    stepover_mm=step_over,
                    stepdown_mm=step_down,
                ),
                increment=1,
            )
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


__all__ = [
    "plan_engrave_passes",
    "plan_hole_passes",
    "plan_pocket_passes",
]
