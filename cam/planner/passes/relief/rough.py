from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from cam.moves import CutMove, Move, RapidMove, SetFeedMove, SetRpmMove
from cam.planner.planner_input import HeightfieldFeatureInput
from ir.removal_intent import HeightfieldToolAssignment

from ..tools import ToolSelection
from .bands import ToolSpec, compute_barriers
from .common import load_surface, sample_barrier_at
from .finish import _emit_finish_moves
from .kernels import compute_center_z_ball

if TYPE_CHECKING:
    from cam.config import Config

    from .. import PassAccumulator


def _barrier_for_tool(
    barriers: dict[str, np.ndarray],
    assignment: HeightfieldToolAssignment,
) -> np.ndarray:
    return barriers[assignment.tool_name]


def _stepdown_for(assignment: HeightfieldToolAssignment, tool: ToolSelection) -> float:
    if assignment.stepdown_mm is not None:
        return assignment.stepdown_mm
    if tool.depth_per_pass is not None and tool.depth_per_pass > 0.0:
        return float(tool.depth_per_pass)
    return max(0.5, 0.25 * tool.diameter)


def _stepover_for(assignment: HeightfieldToolAssignment, tool: ToolSelection) -> float:
    return assignment.stepover_frac * tool.diameter


def _emit_rough_moves(
    feature: HeightfieldFeatureInput,
    tool: ToolSelection,
    assignment: HeightfieldToolAssignment,
    barrier: np.ndarray,
    safe_z: float,
) -> list[Move]:
    moves: list[Move] = []
    cx, cy = feature.center_xy_mm
    half_w = feature.width_mm * 0.5
    half_h = feature.height_mm * 0.5
    x_min = cx - half_w
    x_max = cx + half_w
    y_min = cy - half_h
    y_max = cy + half_h

    z_top = feature.z_top
    z_bottom = z_top - feature.depth_mm
    stepdown = _stepdown_for(assignment, tool)
    stepover = _stepover_for(assignment, tool)
    if stepover <= 0.0:
        raise ValueError(f"Heightfield pass '{feature.id}': stepover must be positive, got {stepover}")

    sample_pitch = 0.5 * tool.diameter
    if sample_pitch <= 0.0:
        sample_pitch = 0.5

    min_barrier = float(np.min(barrier))
    start_z = z_top
    slice_levels: list[float] = []
    z_level = start_z - stepdown
    while z_level > max(min_barrier, z_bottom):
        slice_levels.append(z_level)
        z_level -= stepdown
    final_z = max(min_barrier, z_bottom)
    if not slice_levels or slice_levels[-1] > final_z + 1e-6:
        slice_levels.append(final_z)

    moves.append(SetRpmMove(rpm=tool.rpm))
    moves.append(SetFeedMove(feed=tool.feed_xy))

    width = x_max - x_min
    height = y_max - y_min
    y_steps = max(2, int(np.ceil(height / stepover)) + 1)
    x_sample_steps = max(2, int(np.ceil(width / sample_pitch)) + 1)
    ys = np.linspace(y_min, y_max, y_steps)
    xs = np.linspace(x_min, x_max, x_sample_steps)

    for slice_z in slice_levels:
        moves.append(RapidMove(z=safe_z))
        for j, y in enumerate(ys):
            sweep_xs = xs if (j % 2 == 0) else xs[::-1]
            first_x = float(sweep_xs[0])
            barrier_at_start = sample_barrier_at(barrier, first_x, float(y), x_min, y_min, width, height)
            entry_z = max(slice_z, barrier_at_start)
            moves.append(RapidMove(x=first_x, y=float(y)))
            moves.append(CutMove(z=entry_z, feed=tool.feed_z))
            for x in sweep_xs[1:]:
                xf = float(x)
                b = sample_barrier_at(barrier, xf, float(y), x_min, y_min, width, height)
                z = max(slice_z, b)
                moves.append(CutMove(x=xf, y=float(y), z=z, feed=tool.feed_xy))
            moves.append(RapidMove(z=safe_z))

    return moves


def plan_heightfield_passes(
    heightfields: Sequence[HeightfieldFeatureInput],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
    config: Config,
) -> None:
    if not heightfields:
        return

    safe_z = accumulator._safe_z

    for feature in heightfields:
        _plan_one_heightfield(feature, accumulator=accumulator, tool_db=tool_db, safe_z=safe_z)


def _resolve_tool(
    assignment: HeightfieldToolAssignment, tool_db: Sequence[ToolSelection], feature_id: str
) -> ToolSelection:
    matching = [t for t in tool_db if t.name == assignment.tool_name]
    if not matching:
        raise ValueError(f"Heightfield '{feature_id}': tool {assignment.tool_name!r} not found in machine tool_db")
    tool = matching[0]
    if assignment.role == "finish" and tool.kind != "ball":
        raise ValueError(
            f"Heightfield '{feature_id}': finish role requires kind='ball' tool, got kind={tool.kind!r} "
            f"for tool {assignment.tool_name!r}"
        )
    return tool


def _plan_one_heightfield(
    feature: HeightfieldFeatureInput,
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
    safe_z: float,
) -> None:
    surface, pixel_pitch_mm = load_surface(
        image_path=feature.image_path,
        width_mm=feature.width_mm,
        height_mm=feature.height_mm,
        depth_mm=feature.depth_mm,
        z_top=feature.z_top,
        white_is_high=feature.white_is_high,
    )

    resolved_tools: list[tuple[HeightfieldToolAssignment, ToolSelection]] = [
        (a, _resolve_tool(a, tool_db, feature.id)) for a in feature.tools
    ]

    rough_pairs = [(a, t) for a, t in resolved_tools if a.role == "rough"]
    finish_pairs = [(a, t) for a, t in resolved_tools if a.role == "finish"]

    barriers: dict[str, np.ndarray] = {}
    if rough_pairs:
        tool_specs = [ToolSpec(name=t.name, diameter_mm=t.diameter, kind=t.kind) for _, t in rough_pairs]
        barriers = compute_barriers(surface, tool_specs, pixel_pitch_mm=pixel_pitch_mm)

    rough_pairs_sorted = sorted(rough_pairs, key=lambda pair: -pair[1].diameter)
    for assignment, tool in rough_pairs_sorted:
        barrier = _barrier_for_tool(barriers, assignment)
        record = accumulator.get_record("heightfield-rough", tool)
        moves = _emit_rough_moves(feature, tool, assignment, barrier, safe_z)
        record.add_moves(moves, increment=1)

    if not finish_pairs:
        return

    finest_rough_barrier: np.ndarray | None = None
    if rough_pairs:
        finest_pair = min(rough_pairs, key=lambda pair: pair[1].diameter)
        finest_rough_barrier = barriers[finest_pair[0].tool_name]

    prev_safe_surface: np.ndarray | None = None
    for assignment, tool in finish_pairs:
        radius_mm = 0.5 * tool.diameter
        safe_surface = compute_center_z_ball(surface, pixel_pitch_mm, radius_mm)
        if finest_rough_barrier is not None:
            safe_surface = np.maximum(safe_surface, finest_rough_barrier)
        if prev_safe_surface is not None:
            safe_surface = np.maximum(safe_surface, prev_safe_surface)
        record = accumulator.get_record("heightfield-finish", tool)
        moves = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z)
        record.add_moves(moves, increment=1)
        prev_safe_surface = safe_surface


__all__ = ["plan_heightfield_passes"]
