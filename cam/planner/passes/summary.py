from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from cam.moves import CutMove, Move, RapidMove, XYMove
from cam.planner.passes.tools import tool_identity

if TYPE_CHECKING:
    from cam.planner.passes import PassRecord


def _summarise_moves(moves: Sequence[Move]) -> dict[str, float]:
    x = y = z = None
    cut_len_xy = 0.0
    cut_len_3d = 0.0
    plunge = 0.0
    min_z = 0.0
    for move in moves:
        if isinstance(move, XYMove):
            nx = move.x if move.x is not None else x
            ny = move.y if move.y is not None else y
            nz = move.z if move.z is not None else z
        else:
            nx, ny, nz = x, y, z

        if isinstance(move, (RapidMove, CutMove)) and (x is not None or y is not None or z is not None):
            dx = 0.0 if nx is None or x is None else nx - x
            dy = 0.0 if ny is None or y is None else ny - y
            dz = 0.0 if nz is None or z is None else nz - z
            if isinstance(move, CutMove):
                seg_xy = (dx**2 + dy**2) ** 0.5
                seg_3d = (dx**2 + dy**2 + dz**2) ** 0.5
                cut_len_xy += max(0.0, seg_xy)
                cut_len_3d += max(0.0, seg_3d)
                if abs(dx) < 1e-9 and abs(dy) < 1e-9 and nz is not None and z is not None:
                    plunge += abs(nz - z)
                if nz is not None:
                    min_z = min(min_z, nz)
        x, y, z = nx, ny, nz
    return {
        "cut_length_xy_mm": cut_len_xy,
        "cut_length_3d_mm": cut_len_3d,
        "plunge_travel_mm": plunge,
        "max_depth_mm": abs(min_z),
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
        metrics = _summarise_moves(entry.moves)
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


__all__ = ["summarise_passes"]
