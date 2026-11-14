from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, overload

import shapely
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from cam.model.tool import Tool, ToolKind
from cam.planner.params import MIN_STEPDOWN_MM, stepdown_for, stepover_for
from layout_ast.layout import FeedsOverride, MachiningSpec


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
    roundover_radius_mm: float | None = None
    flute_length_mm: float | None = None
    flutes: int | None = None
    shank_diameter_mm: float | None = None
    limits: tuple[tuple[str, float], ...] = ()
    context_label: str = ""

    def __post_init__(self) -> None:
        for name in ("diameter", "rpm", "feed_xy", "feed_z", "depth_per_pass", "stepover_percent"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(
                    f"{self.context_label} cutter {self.name!r}: {name} must be finite and positive, got {value}"
                )
        if self.stepover_percent is not None and self.stepover_percent > 100:
            raise ValueError(f"{self.context_label} cutter {self.name!r}: stepover_percent must be <= 100")

    def validate_cut(self, depth_mm: float = 0) -> ToolSelection:
        if self.flute_length_mm is not None and depth_mm > self.flute_length_mm + 1e-6:
            raise ValueError(
                f"{self.context_label} cutter {self.name!r}: required reach {depth_mm:g}mm exceeds flute length {self.flute_length_mm:g}mm"
            )
        if (
            self.flute_length_mm is not None
            and self.depth_per_pass is not None
            and self.depth_per_pass > self.flute_length_mm
        ):
            raise ValueError(
                f"{self.context_label} cutter {self.name!r}: stepdown {self.depth_per_pass:g}mm exceeds flute length {self.flute_length_mm:g}mm"
            )
        values = {
            "max_feed_xy": self.feed_xy,
            "max_feed_z": self.feed_z,
            "rpm_max": self.rpm,
            "max_shank_mm": self.shank_diameter_mm,
        }
        for name, limit in self.limits:
            actual = values.get(name)
            if actual is not None and actual > limit:
                raise ValueError(
                    f"{self.context_label} cutter {self.name!r}: {name} limit {limit:g}, requested {actual:g}"
                )
            if name == "rpm_min" and self.rpm < limit:
                raise ValueError(f"{self.context_label} cutter {self.name!r}: rpm {self.rpm:g} below minimum {limit:g}")
        return self

    def as_model(self) -> Tool:
        return Tool(
            name=self.name,
            diameter=self.diameter,
            kind=self.kind,
            rpm=self.rpm,
            feed_xy=self.feed_xy,
            feed_z=self.feed_z,
            v_angle_deg=self.v_angle_deg,
            roundover_radius_mm=self.roundover_radius_mm,
        )


_VALID_KINDS: frozenset[ToolKind] = frozenset({"flat", "ball", "v", "roundover"})


def _parse_kind(data: Mapping[str, Any]) -> ToolKind:
    raw = str(data.get("kind", data.get("type", "flat"))).lower()
    if raw not in _VALID_KINDS:
        raise ValueError(f"Unknown tool kind {raw!r}; expected one of {sorted(_VALID_KINDS)}")
    return raw  # type: ignore[return-value]


def _cutting_rate(data: Mapping[str, Any], key: str, alias: str | None = None) -> float:
    value = data.get(key, data.get(alias) if alias is not None else None)
    if value is None:
        raise ValueError(f"Cutter {data.get('name', 'unnamed')!r}: missing required cutting parameter {key}")
    return float(value)


def _selection_from_dict(data: Mapping[str, Any]) -> ToolSelection:
    return ToolSelection(
        name=str(data.get("name", data.get("tool_id", "tool"))),
        diameter=float(data.get("diameter", data.get("diameter_mm", 0.0))),
        kind=_parse_kind(data),
        rpm=_cutting_rate(data, "rpm"),
        feed_xy=_cutting_rate(data, "feed_xy", "feed_rate_mm_min"),
        feed_z=_cutting_rate(data, "feed_z", "plunge_rate_mm_min"),
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
        roundover_radius_mm=float(data["roundover_radius_mm"]) if data.get("roundover_radius_mm") is not None else None,
        flute_length_mm=float(data["flute_length_mm"]) if data.get("flute_length_mm") is not None else None,
        flutes=int(data["flutes"]) if data.get("flutes") is not None else None,
        shank_diameter_mm=float(data["shank_diameter_mm"]) if data.get("shank_diameter_mm") is not None else None,
    )


def normalize_tool_entries(tool_db: Sequence[Mapping[str, Any]]) -> list[ToolSelection]:
    return [_selection_from_dict(entry) for entry in tool_db]


@dataclass(frozen=True)
class ToolCatalog(Sequence[ToolSelection]):
    entries: tuple[ToolSelection, ...]
    parameters: Mapping[str, Mapping[str, ToolSelection]]
    assignments: Mapping[str, tuple[str, ...]]
    machining: MachiningSpec
    label: str
    inventory: tuple[str, ...]

    @overload
    def __getitem__(self, index: int) -> ToolSelection: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[ToolSelection, ...]: ...

    def __getitem__(self, index: int | slice) -> ToolSelection | tuple[ToolSelection, ...]:
        return self.entries[index]

    def __len__(self) -> int:
        return len(self.entries)

    def for_role(self, role: str, name: str | None = None, depth_mm: float = 0) -> list[ToolSelection]:
        explicit = name or self.machining.tools.get(role)
        names = (explicit,) if explicit else self.assignments.get(role, ())
        if not names:
            raise ValueError(
                f"{self.label}, role {role}: no configured cutter assignment; configure the preset or machining.tools.{role}"
            )
        candidates = []
        for selected in names:
            label = f"{self.label}, role {role}, cutter {selected!r}"
            if selected not in self.inventory:
                raise ValueError(f"{label}: unknown/unavailable tool reference; available: {list(self.inventory)}")
            tool = self.parameters.get(role, {}).get(selected)
            if tool is None:
                raise ValueError(
                    f"{label}: missing cutting parameters; configure this exact material/operation/cutter combination"
                )
            allowed = {
                "profile": {"flat"},
                "pocket": {"flat"},
                "hole": {"flat"},
                "surface": {"flat"},
                "vcarve": {"v"},
                "roundover": {"roundover"},
                "engrave": {"flat", "ball", "v"},
            }
            if role in allowed and tool.kind not in allowed[role]:
                raise ValueError(f"{label}: incompatible kind {tool.kind!r}; expected {sorted(allowed[role])}")
            if tool.flute_length_mm is not None and depth_mm > tool.flute_length_mm + 1e-6:
                if explicit:
                    tool.validate_cut(depth_mm)
                continue
            candidates.append(apply_feeds_override(tool, self.machining.feeds, validate=False))
        if not candidates:
            raise ValueError(
                f"{self.label}, role {role}, cutters {list(names)}: no approved cutter has required reach {depth_mm:g}mm"
            )
        return candidates


def tools_for_role(
    tool_db: Sequence[ToolSelection], role: str, name: str | None = None, depth_mm: float = 0
) -> Sequence[ToolSelection]:
    if isinstance(tool_db, ToolCatalog):
        return tool_db.for_role(role, name, depth_mm)
    if name is not None:
        selected = [tool for tool in tool_db if tool.name == name]
        if not selected:
            raise ValueError(f"role {role}: explicit cutter {name!r} not found")
        return [tool.validate_cut(depth_mm) for tool in selected]
    return tool_db


def _flat_tools(tool_db: Sequence[ToolSelection]) -> list[ToolSelection]:
    return [tool for tool in tool_db if tool.kind == "flat"]


def _pocket_candidates(tool_db: Sequence[ToolSelection]) -> list[ToolSelection]:
    candidates = _flat_tools(tool_db)
    if not candidates:
        raise ValueError("No flat tools available for pocketing")
    return candidates


def _topology(geometry: BaseGeometry) -> tuple[int, int]:
    parts = [part for part in shapely.get_parts(geometry) if isinstance(part, Polygon) and not part.is_empty]
    return len(parts), sum(len(part.interiors) for part in parts)


def pick_tool_for_region(
    tool_db: Sequence[ToolSelection],
    region: BaseGeometry,
    *,
    cleanup_offset_mm: float,
) -> ToolSelection | None:
    if region.is_empty:
        return None
    target = _topology(region)
    for tool in _pocket_candidates(tool_db):
        eroded = region.buffer(-(tool.diameter / 2.0 + cleanup_offset_mm), join_style="round")
        if _topology(eroded) == target:
            return tool
    return None


def pick_tool_for_pocket(
    tool_db: Sequence[ToolSelection],
    *,
    required_width_mm: float | None,
    cleanup_offset_mm: float,
) -> ToolSelection:

    candidates = _pocket_candidates(tool_db)

    if required_width_mm and required_width_mm > 0.0:
        clearance = max(required_width_mm - 2.0 * cleanup_offset_mm, 0.0)
        within_clearance = [t for t in candidates if t.diameter <= clearance]
        if not within_clearance:
            within_clearance = [t for t in candidates if t.diameter < required_width_mm]
        if within_clearance:
            candidates = within_clearance
        else:
            raise ValueError(
                f"Pocket width {required_width_mm:g}mm is infeasible for approved/explicit cutters {[t.name for t in candidates]}"
            )
    return candidates[0]


def pick_tool_for_profile(
    tool_db: Sequence[ToolSelection],
    *,
    kerf_mm: float | None,
) -> ToolSelection:

    candidates = _flat_tools(tools_for_role(tool_db, "profile"))
    if not candidates:
        raise ValueError("Tool database does not contain a flat tool for profiling")
    if kerf_mm and kerf_mm > 0.0:
        matches = [t for t in candidates if math.isclose(t.diameter, kerf_mm, abs_tol=0.01)]
        if not matches:
            raise ValueError(
                f"Profile kerf constraint {kerf_mm:g}mm conflicts with configured cutter {candidates[0].name!r} ({candidates[0].diameter:g}mm); choose an exact profile tool or rebuild without a kerf constraint"
            )
        return matches[0]
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
    if not feasible:
        raise ValueError(
            f"Hole diameter {hole_diameter_mm:g}mm: no approved cutter fits; cutters: {[t.name for t in candidates]}"
        )
    return feasible[0]


def pick_tool_for_edge(
    tool_db: Sequence[ToolSelection],
    *,
    angle_deg: float,
) -> ToolSelection:
    candidates = [t for t in tool_db if t.kind == "v" and t.v_angle_deg is not None]
    if not candidates:
        raise ValueError("Tool database does not contain a V-bit for edge features")
    matches = [t for t in candidates if math.isclose(t.v_angle_deg or 0, angle_deg, abs_tol=0.01)]
    if not matches:
        raise ValueError(f"No approved V-bit has required included angle {angle_deg:g} degrees")
    return matches[0]


def pick_tool_for_roundover(
    tool_db: Sequence[ToolSelection],
    *,
    radius_mm: float,
) -> ToolSelection:
    candidates = [t for t in tool_db if t.kind == "roundover" and t.roundover_radius_mm is not None]
    if not candidates:
        raise ValueError("Tool database does not contain a roundover bit")
    candidates.sort(key=lambda t: abs((t.roundover_radius_mm or 0.0) - radius_mm))
    best = candidates[0]
    if abs((best.roundover_radius_mm or 0.0) - radius_mm) > 0.5:
        raise ValueError(
            f"No roundover bit with radius near {radius_mm:.2f}mm (closest: {best.roundover_radius_mm:.2f}mm)"
        )
    return best


def pick_tool_for_surface(tool_db: Sequence[ToolSelection]) -> ToolSelection:
    candidates = _flat_tools(tool_db)
    if not candidates:
        raise ValueError("No flat tools available for surfacing")
    return candidates[0]


def pick_tool_for_engrave(tool_db: Sequence[ToolSelection]) -> ToolSelection:
    candidates = [t for t in tool_db if t.kind in {"ball", "v"}]
    if candidates:
        return candidates[0]
    if not tool_db:
        raise ValueError("No configured engraving cutter")
    return tool_db[0]


def pick_tool_by_diameter(
    tool_db: Sequence[ToolSelection],
    diameter_mm: float,
    *,
    tolerance_mm: float = 0.01,
    kind: str | None = None,
    role: str = "specialty",
) -> ToolSelection:
    if isinstance(tool_db, ToolCatalog):
        names = tool_db.assignments.get(role, ())
        catalog = tool_db
        tool_db = [
            t
            for name in names
            for t in catalog.for_role(role, name)
            if abs(t.diameter - diameter_mm) < tolerance_mm and (kind is None or t.kind == kind)
        ]
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
    return max(MIN_STEPDOWN_MM, stepdown_for(tool_diameter=tool.diameter, cap_mm=3.0))


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
        "depth_per_pass": tool.depth_per_pass,
        "stepover_percent": tool.stepover_percent,
        "flute_length_mm": tool.flute_length_mm,
        "flutes": tool.flutes,
        "shank_diameter_mm": tool.shank_diameter_mm,
        "rpm": float(tool.rpm),
        "feed_xy": float(tool.feed_xy),
        "feed_z": float(tool.feed_z),
    }
    if tool.v_angle_deg is not None:
        result["v_angle_deg"] = tool.v_angle_deg
    if tool.roundover_radius_mm is not None:
        result["roundover_radius_mm"] = tool.roundover_radius_mm
    return result


def pass_key(operation: str, tool: ToolSelection) -> tuple[Any, ...]:
    return (
        operation,
        tool.name,
        tool.rpm,
        tool.feed_xy,
        tool.feed_z,
        tool.depth_per_pass,
        tool.stepover_percent,
        float(tool.diameter),
        tool.kind,
        tool.rotation,
        tool.v_angle_deg,
        tool.roundover_radius_mm,
    )


def apply_feeds_override(
    tool: ToolSelection, override: FeedsOverride | None, *, validate: bool = True
) -> ToolSelection:
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
    result = replace(tool, **kwargs)
    return result.validate_cut() if validate else result


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
    "pick_tool_for_region",
    "pick_tool_for_roundover",
    "pick_tool_for_surface",
    "stepdown_for_tool",
    "stepover_for_tool",
    "tool_identity",
]
