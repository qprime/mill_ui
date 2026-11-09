from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from cam.moves import CutMove, DwellMove, Move, RapidMove, RetractMove, SetFeedMove
from cam.planner.passes.tools import ToolSelection, tool_identity
from core.constants import RAPID_XY_MM_MIN, RAPID_Z_MM_MIN

if TYPE_CHECKING:
    from cam.planner.passes import PassRecord


def _summarise_moves(moves: Sequence[Move], tool: ToolSelection | None = None) -> dict[str, float]:
    x = y = z = None
    feed: float | None = None
    cut_len_xy = 0.0
    cut_len_3d = 0.0
    plunge = 0.0
    min_z = 0.0
    rapid_xy = 0.0
    rapid_z = 0.0
    cut_time_s = 0.0
    dwell_time_s = 0.0
    for move in moves:
        if isinstance(move, SetFeedMove):
            feed = move.feed
            continue
        if isinstance(move, DwellMove):
            dwell_time_s += move.seconds
            continue
        if isinstance(move, RetractMove):
            if z is not None:
                rapid_z += abs(move.z - z)
            z = move.z
            continue
        if not isinstance(move, (RapidMove, CutMove)):
            continue

        nx = move.x if move.x is not None else x
        ny = move.y if move.y is not None else y
        nz = move.z if move.z is not None else z
        dx = 0.0 if nx is None or x is None else nx - x
        dy = 0.0 if ny is None or y is None else ny - y
        dz = 0.0 if nz is None or z is None else nz - z
        seg_xy = math.hypot(dx, dy)

        if isinstance(move, CutMove):
            seg_3d = math.sqrt(dx**2 + dy**2 + dz**2)
            cut_len_xy += seg_xy
            cut_len_3d += seg_3d
            is_plunge = abs(dx) < 1e-9 and abs(dy) < 1e-9
            if is_plunge and nz is not None and z is not None:
                plunge += abs(nz - z)
            if nz is not None:
                min_z = min(min_z, nz)
            if move.feed is not None:
                feed = move.feed
            segment_feed = feed if feed is not None else _fallback_feed(tool, is_plunge)
            if segment_feed:
                cut_time_s += seg_3d / segment_feed * 60.0
        else:
            rapid_xy += seg_xy
            rapid_z += abs(dz)
        x, y, z = nx, ny, nz
    return {
        "cut_length_xy_mm": cut_len_xy,
        "cut_length_3d_mm": cut_len_3d,
        "plunge_travel_mm": plunge,
        "max_depth_mm": abs(min_z),
        "rapid_distance_xy_mm": rapid_xy,
        "rapid_distance_z_mm": rapid_z,
        "cut_time_s": cut_time_s,
        "dwell_time_s": dwell_time_s,
    }


def _fallback_feed(tool: ToolSelection | None, is_plunge: bool) -> float | None:
    if tool is None:
        return None
    return tool.feed_z if is_plunge else tool.feed_xy


def estimated_runtime_min(move_metrics: Mapping[str, float]) -> float:
    rapid_time_s = (
        move_metrics["rapid_distance_xy_mm"] / RAPID_XY_MM_MIN + move_metrics["rapid_distance_z_mm"] / RAPID_Z_MM_MIN
    ) * 60.0
    total_s = move_metrics["cut_time_s"] + rapid_time_s + move_metrics["dwell_time_s"]
    return round(total_s / 60.0, 1)


def summarise_gcode_file(filename: str, passes: Sequence[PassRecord]) -> dict[str, Any]:
    tool = passes[0].tool_selection
    moves = [move for entry in passes for move in entry.moves]
    return {
        "filename": filename,
        "operation": ", ".join(dict.fromkeys(entry.op for entry in passes)),
        "tool_diameter_mm": float(tool.diameter),
        "estimated_runtime_min": estimated_runtime_min(_summarise_moves(moves, tool)),
    }


def summarise_passes(
    passes: Sequence[PassRecord],
    *,
    merge_enabled: bool,
    merged_seams: int,
    profile_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary_passes: list[dict[str, Any]] = []
    for entry in passes:
        metrics = _summarise_moves(entry.moves, entry.tool_selection)
        tool = entry.tool_selection
        diameter = float(tool.diameter)
        kind = str(tool.kind)
        rotation = tool.rotation
        description = f"{entry.op} with {diameter:.2f}mm {kind}"
        if rotation:
            description += f" ({rotation})"
        summary_passes.append(
            {
                "filename": entry.filename,
                "operation": entry.op,
                "tool": tool_identity(tool),
                "item_count": entry.count,
                "metrics": metrics,
                "description": description,
            }
        )

    note = "Shared-edge merge is ON" if merge_enabled else "Shared-edge merge is OFF"
    summary: dict[str, Any] = {
        "passes": summary_passes,
        "notes": note,
        "merged_seams": merged_seams,
    }
    if profile_options:
        summary["profile_options"] = dict(profile_options)
    return summary


__all__ = ["estimated_runtime_min", "summarise_gcode_file", "summarise_passes"]
