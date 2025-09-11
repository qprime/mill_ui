# path: skills/mill_ui/cam/planner/select.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional, Literal

ToolKind = Literal["flat", "ball", "v"]

@dataclass(frozen=True)
class ToolSpec:
    name: str
    diameter: float
    kind: ToolKind = "flat"
    rpm: float = 12000.0
    feed_xy: float = 800.0
    feed_z: float = 300.0

def _to_toolspecs(tool_db: Iterable[dict]) -> list[ToolSpec]:
    out: list[ToolSpec] = []
    for t in tool_db:
        out.append(ToolSpec(
            name=str(t.get("name", "")),
            diameter=float(t.get("diameter", 0.0)),
            kind=(t.get("kind") or "flat"),
            rpm=float(t.get("rpm", 12000.0)),
            feed_xy=float(t.get("feed_xy", 800.0)),
            feed_z=float(t.get("feed_z", 300.0)),
        ))
    return sorted(out, key=lambda x: x.diameter)

def pick_for_profile(tool_db: Iterable[dict]) -> ToolSpec:
    """Profiles prefer largest tool (fastest perimeter time)."""
    tools = _to_toolspecs(tool_db)
    return tools[-1]

def pick_for_pocket(tool_db: Iterable[dict], *, min_channel_width_mm: float) -> ToolSpec:
    """Pocketing must fit channels → pick the largest tool ≤ channel width."""
    tools = _to_toolspecs(tool_db)
    feasible = [t for t in tools if t.diameter <= float(min_channel_width_mm)]
    return feasible[-1] if feasible else tools[0]

def pick_for_hole(tool_db: Iterable[dict], *, hole_diameter_mm: float) -> ToolSpec:
    """Drilling/boring: pick the largest tool ≤ hole diameter."""
    tools = _to_toolspecs(tool_db)
    feasible = [t for t in tools if t.diameter <= float(hole_diameter_mm)]
    return feasible[-1] if feasible else tools[0]

def pick_for_engrave(tool_db: Iterable[dict]) -> ToolSpec:
    """Engrave defaults to the smallest available flat/V bit."""
    tools = _to_toolspecs(tool_db)
    return tools[0]
