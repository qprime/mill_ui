from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence


def _summarise_moves(moves: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    x = y = z = None
    cut_len_xy = 0.0
    cut_len_3d = 0.0
    plunge = 0.0
    min_z = 0.0
    for move in moves:
        kind = move.get("kind")
        nx = move.get("x", x)
        ny = move.get("y", y)
        nz = move.get("z", z)
        if kind in {"rapid", "cut"} and (x is not None or y is not None or z is not None):
            dx = 0.0 if nx is None or x is None else nx - x
            dy = 0.0 if ny is None or y is None else ny - y
            dz = 0.0 if nz is None or z is None else nz - z
            if kind == "cut":
                seg_xy = (dx ** 2 + dy ** 2) ** 0.5
                seg_3d = (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5
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
    passes: Sequence[Mapping[str, Any]],
    *,
    merge_enabled: bool,
    merged_seams: int,
    profile_options: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    summary_passes: list[Dict[str, Any]] = []
    for entry in passes:
        metrics = _summarise_moves(entry.get("moves", []))
        tool = entry.get("tool", {})
        diameter = float(tool.get("diameter", 0.0))
        kind = str(tool.get("kind", "flat"))
        rotation = tool.get("rotation")
        description = f"{entry['op']} with {diameter:.2f}mm {kind}"
        if rotation:
            description += f" ({rotation})"
        summary_passes.append(
            {
                "filename": entry.get("filename"),
                "operation": entry.get("op"),
                "tool": tool,
                "item_count": entry.get("count", 0),
                "metrics": metrics,
                "description": description,
            }
        )

    note = "Shared-edge merge is ON" if merge_enabled else "Shared-edge merge is OFF"
    summary: Dict[str, Any] = {
        "passes": summary_passes,
        "notes": note,
        "merged_seams": merged_seams,
    }
    if profile_options:
        summary["profile_options"] = dict(profile_options)
    return summary


__all__ = ["summarise_passes"]
