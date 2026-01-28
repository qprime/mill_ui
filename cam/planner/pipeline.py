from __future__ import annotations
from typing import Iterable, Dict

from cam.model.tool import Tool
from cam.planner.select import ToolSpec


def _as_tool(spec: ToolSpec) -> Tool:
    return Tool(
        name=spec.name,
        diameter=spec.diameter,
        kind=spec.kind,
        rpm=spec.rpm,
        feed_xy=spec.feed_xy,
        feed_z=spec.feed_z,
    )
