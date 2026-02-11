from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple

from cam.model.tool import Tool
from cam.planner.params import stepdown_for, stepover_for


@dataclass(frozen=True)
class ToolSelection:

    name: str
    diameter: float
    kind: str
    rpm: float
    feed_xy: float
    feed_z: float
    rotation: str | None = None
    depth_per_pass: float | None = None
    stepover_percent: float | None = None

    def as_model(self) -> Tool:
        return Tool(
            name=self.name,
            diameter=self.diameter,
            kind=self.kind,
            rpm=self.rpm,
            feed_xy=self.feed_xy,
            feed_z=self.feed_z,
        )


def _selection_from_dict(data: Mapping[str, Any]) -> ToolSelection:
    return ToolSelection(
        name=str(data.get("name", data.get("tool_id", "tool"))),
        diameter=float(data.get("diameter", data.get("diameter_mm", 0.0))),
        kind=str(data.get("kind", data.get("type", "flat"))).lower(),
        rpm=float(data.get("rpm", 18000.0)),
        feed_xy=float(data.get("feed_xy", data.get("feed_rate_mm_min", 2000.0))),
        feed_z=float(data.get("feed_z", data.get("plunge_rate_mm_min", 300.0))),
        rotation=data.get("rotation"),
        depth_per_pass=(
            float(data["depth_per_pass"])
            if data.get("depth_per_pass") is not None
            else float(data.get("depth_per_pass_mm", 0.0)) if data.get("depth_per_pass_mm") is not None else None
        ),
        stepover_percent=(
            float(data["stepover_percent"])
            if data.get("stepover_percent") is not None
            else float(data.get("step_over_percent", 0.0)) if data.get("step_over_percent") is not None else None
        ),
    )


def _normalize_tool_entries(tool_db: Sequence[Mapping[str, Any]]) -> list[ToolSelection]:
    selections: list[ToolSelection] = []
    for entry in tool_db:
        selections.append(_selection_from_dict(entry))
    return selections


def _flat_tools(tool_db: Sequence[Mapping[str, Any]]) -> list[ToolSelection]:
    return [tool for tool in _normalize_tool_entries(tool_db) if tool.kind != "ball"]


def _ball_or_v_tools(tool_db: Sequence[Mapping[str, Any]]) -> list[ToolSelection]:
    return [tool for tool in _normalize_tool_entries(tool_db) if tool.kind in {"ball", "v"}]


def pick_tool_for_pocket(
    tool_db: Sequence[Mapping[str, Any]],
    *,
    required_width_mm: float | None,
    cleanup_offset_mm: float,
) -> ToolSelection:

    candidates = _flat_tools(tool_db)
    if not candidates:
        raise ValueError("No flat tools available for pocketing")

    candidates.sort(
        key=lambda t: (
            0 if (t.rotation or "").lower() in {"upcut", "compression"} else 1,
            -t.diameter,
        )
    )

    if required_width_mm and required_width_mm > 0.0:
        clearance = max(required_width_mm - 2.0 * cleanup_offset_mm, 0.0)
        within_clearance = [t for t in candidates if t.diameter <= clearance]
        if within_clearance:
            candidates = within_clearance
        else:
            below_width = [t for t in candidates if t.diameter < required_width_mm]
            if below_width:
                candidates = below_width
    return candidates[0]


def pick_tool_for_profile(
    tool_db: Sequence[Mapping[str, Any]],
    *,
    kerf_mm: float | None,
) -> ToolSelection:

    candidates = _flat_tools(tool_db)
    if not candidates:
        raise ValueError("Tool database does not contain a flat tool for profiling")
    if kerf_mm and kerf_mm > 0.0:
        candidates.sort(key=lambda t: abs(t.diameter - kerf_mm))
        return candidates[0]
    candidates.sort(key=lambda t: t.diameter)
    return candidates[0]


def pick_tool_for_hole(
    tool_db: Sequence[Mapping[str, Any]],
    *,
    hole_diameter_mm: float,
) -> ToolSelection:
    candidates = _flat_tools(tool_db)
    if not candidates:
        raise ValueError("Tool database does not contain a flat tool for drilling")
    feasible = [t for t in candidates if t.diameter <= hole_diameter_mm]
    return feasible[-1] if feasible else candidates[0]


def pick_tool_for_engrave(tool_db: Sequence[Mapping[str, Any]]) -> ToolSelection:
    candidates = _ball_or_v_tools(tool_db)
    if candidates:
        candidates.sort(key=lambda t: t.diameter)
        return candidates[0]
    fallback = _normalize_tool_entries(tool_db)
    fallback.sort(key=lambda t: t.diameter)
    return fallback[0]


def stepdown_for_tool(tool: ToolSelection) -> float:
    if tool.depth_per_pass is not None and tool.depth_per_pass > 0.0:
        return float(tool.depth_per_pass)
    return stepdown_for(tool_diameter=tool.diameter, cap_mm=3.0)


def stepover_for_tool(tool: ToolSelection) -> float:
    if tool.stepover_percent is not None and tool.stepover_percent > 0.0:
        return float(tool.diameter) * (float(tool.stepover_percent) / 100.0)
    return stepover_for(tool_diameter=tool.diameter)


def tool_identity(tool: ToolSelection) -> dict[str, Any]:
    return {
        "name": tool.name,
        "diameter": float(tool.diameter),
        "kind": tool.kind,
        "rotation": tool.rotation,
        "rpm": float(tool.rpm),
        "feed_xy": float(tool.feed_xy),
        "feed_z": float(tool.feed_z),
    }


def pass_key(operation: str, tool: ToolSelection) -> Tuple[str, float, str, str | None]:
    return operation, float(tool.diameter), tool.kind, tool.rotation


__all__ = [
    "ToolSelection",
    "pass_key",
    "pick_tool_for_pocket",
    "pick_tool_for_profile",
    "pick_tool_for_hole",
    "pick_tool_for_engrave",
    "stepdown_for_tool",
    "stepover_for_tool",
    "tool_identity",
]
