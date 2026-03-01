from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from cam.model.tool import Tool, ToolKind
from cam.planner.params import stepdown_for, stepover_for
from layout_ast.layout import FeedsOverride


@dataclass(frozen=True)
class ToolSelection:
    name: str
    diameter: float
    kind: ToolKind
    rpm: float
    feed_xy: float
    feed_z: float
    rotation: str | None = None
    depth_per_pass: float | None = None
    stepover_percent: float | None = None
    v_angle_deg: float | None = None

    def as_model(self) -> Tool:
        return Tool(
            name=self.name,
            diameter=self.diameter,
            kind=self.kind,
            rpm=self.rpm,
            feed_xy=self.feed_xy,
            feed_z=self.feed_z,
            v_angle_deg=self.v_angle_deg,
        )


_VALID_KINDS: frozenset[ToolKind] = frozenset({"flat", "ball", "v"})


def _parse_kind(data: Mapping[str, Any]) -> ToolKind:
    raw = str(data.get("kind", data.get("type", "flat"))).lower()
    if raw not in _VALID_KINDS:
        raise ValueError(f"Unknown tool kind {raw!r}; expected one of {sorted(_VALID_KINDS)}")
    return raw  # type: ignore[return-value]


def _selection_from_dict(data: Mapping[str, Any]) -> ToolSelection:
    return ToolSelection(
        name=str(data.get("name", data.get("tool_id", "tool"))),
        diameter=float(data.get("diameter", data.get("diameter_mm", 0.0))),
        kind=_parse_kind(data),
        rpm=float(data.get("rpm", 18000.0)),
        feed_xy=float(data.get("feed_xy", data.get("feed_rate_mm_min", 2000.0))),
        feed_z=float(data.get("feed_z", data.get("plunge_rate_mm_min", 300.0))),
        rotation=data.get("rotation"),
        depth_per_pass=(
            float(data["depth_per_pass"])
            if data.get("depth_per_pass") is not None
            else float(data.get("depth_per_pass_mm", 0.0))
            if data.get("depth_per_pass_mm") is not None
            else None
        ),
        stepover_percent=(
            float(data["stepover_percent"])
            if data.get("stepover_percent") is not None
            else float(data.get("step_over_percent", 0.0))
            if data.get("step_over_percent") is not None
            else None
        ),
        v_angle_deg=float(data["v_angle_deg"]) if data.get("v_angle_deg") is not None else None,
    )


def normalize_tool_entries(tool_db: Sequence[Mapping[str, Any]]) -> list[ToolSelection]:
    return [_selection_from_dict(entry) for entry in tool_db]


def _flat_tools(tool_db: Sequence[ToolSelection]) -> list[ToolSelection]:
    return [tool for tool in tool_db if tool.kind == "flat"]


def _ball_or_v_tools(tool_db: Sequence[ToolSelection]) -> list[ToolSelection]:
    return [tool for tool in tool_db if tool.kind in {"ball", "v"}]


def pick_tool_for_pocket(
    tool_db: Sequence[ToolSelection],
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
    tool_db: Sequence[ToolSelection],
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
    tool_db: Sequence[ToolSelection],
    *,
    hole_diameter_mm: float,
) -> ToolSelection:
    candidates = _flat_tools(tool_db)
    if not candidates:
        raise ValueError("Tool database does not contain a flat tool for drilling")
    feasible = [t for t in candidates if t.diameter <= hole_diameter_mm]
    return feasible[-1] if feasible else candidates[0]


def pick_tool_for_edge(
    tool_db: Sequence[ToolSelection],
    *,
    angle_deg: float,
) -> ToolSelection:
    candidates = [t for t in tool_db if t.kind == "v" and t.v_angle_deg is not None]
    if not candidates:
        raise ValueError("Tool database does not contain a V-bit for edge features")
    candidates.sort(key=lambda t: abs((t.v_angle_deg or 0.0) - angle_deg))
    return candidates[0]


def pick_tool_for_engrave(tool_db: Sequence[ToolSelection]) -> ToolSelection:
    candidates = _ball_or_v_tools(tool_db)
    if candidates:
        candidates.sort(key=lambda t: t.diameter)
        return candidates[0]
    fallback = sorted(tool_db, key=lambda t: t.diameter)
    return fallback[0]


def pick_tool_by_diameter(
    tool_db: Sequence[ToolSelection],
    diameter_mm: float,
    *,
    tolerance_mm: float = 0.01,
    kind: str | None = None,
) -> ToolSelection:
    for t in tool_db:
        if kind is not None and t.kind != kind:
            continue
        if abs(t.diameter - diameter_mm) < tolerance_mm:
            return t
    kind_msg = f" of kind '{kind}'" if kind else ""
    raise ValueError(
        f"Tool with diameter {diameter_mm}mm{kind_msg} not found in tool_db. "
        f"Available tools: {[t.diameter for t in tool_db]}"
    )


def stepdown_for_tool(tool: ToolSelection) -> float:
    if tool.depth_per_pass is not None and tool.depth_per_pass > 0.0:
        return float(tool.depth_per_pass)
    return stepdown_for(tool_diameter=tool.diameter, cap_mm=3.0)


def stepover_for_tool(tool: ToolSelection) -> float:
    if tool.stepover_percent is not None and tool.stepover_percent > 0.0:
        return float(tool.diameter) * (float(tool.stepover_percent) / 100.0)
    return stepover_for(tool_diameter=tool.diameter)


def tool_identity(tool: ToolSelection) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": tool.name,
        "diameter": float(tool.diameter),
        "kind": tool.kind,
        "rotation": tool.rotation,
        "rpm": float(tool.rpm),
        "feed_xy": float(tool.feed_xy),
        "feed_z": float(tool.feed_z),
    }
    if tool.v_angle_deg is not None:
        result["v_angle_deg"] = tool.v_angle_deg
    return result


def pass_key(operation: str, tool: ToolSelection) -> tuple[str, float, str, str | None, float | None]:
    return operation, float(tool.diameter), tool.kind, tool.rotation, tool.v_angle_deg


def apply_feeds_override(tool: ToolSelection, override: FeedsOverride | None) -> ToolSelection:
    if override is None:
        return tool
    kwargs: dict[str, Any] = {}
    if override.rpm is not None:
        kwargs["rpm"] = override.rpm
    if override.feed_xy is not None:
        kwargs["feed_xy"] = override.feed_xy
    if override.feed_z is not None:
        kwargs["feed_z"] = override.feed_z
    if override.depth_per_pass is not None:
        kwargs["depth_per_pass"] = override.depth_per_pass
    if override.stepover_percent is not None:
        kwargs["stepover_percent"] = override.stepover_percent
    if not kwargs:
        return tool
    return replace(tool, **kwargs)


__all__ = [
    "ToolSelection",
    "apply_feeds_override",
    "normalize_tool_entries",
    "pass_key",
    "pick_tool_by_diameter",
    "pick_tool_for_edge",
    "pick_tool_for_engrave",
    "pick_tool_for_hole",
    "pick_tool_for_pocket",
    "pick_tool_for_profile",
    "stepdown_for_tool",
    "stepover_for_tool",
    "tool_identity",
]
