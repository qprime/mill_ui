"""High-level CAM pass planning built from modular helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from skills.mill_ui.cam.config import Config
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.model.stock import Stock

from .merge_shared_edges import merge_rect_profiles
from .pocket import plan_engrave_passes, plan_hole_passes, plan_pocket_passes
from .profile import circle_shape_mm, ensure_center, profile_moves_with_options, rect_shape
from .summary import summarise_passes
from .tools import ToolSelection, pass_key, pick_tool_for_profile, tool_identity


@dataclass
class PassRecord:
    """Mutable representation of a single NC file to be emitted."""

    op: str
    tool_dict: Dict[str, Any]
    tool_selection: ToolSelection
    setup: Setup
    filename: str
    moves: List[Dict[str, Any]] = field(default_factory=list)
    count: int = 0

    def add_moves(self, moves: Iterable[Mapping[str, Any]], *, increment: int = 0) -> None:
        for move in moves:
            self.moves.append(dict(move))
        if increment:
            self.count += int(increment)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op,
            "tool": dict(self.tool_dict),
            "setup": self.setup,
            "moves": list(self.moves),
            "filename": self.filename,
            "count": self.count,
        }


class PassAccumulator:
    """Create or reuse passes grouped by operation/tool identity."""

    def __init__(
        self,
        *,
        material: Material,
        machine: Machine,
        stock: Stock,
        safe_z: float,
        prime_spindle: bool,
    ) -> None:
        self._material = material
        self._machine = machine
        self._stock = stock
        self._safe_z = float(safe_z)
        self._prime_spindle = prime_spindle
        self._records: Dict[tuple[str, float, str, str | None], PassRecord] = {}

    def _make_record(self, operation: str, tool: ToolSelection) -> PassRecord:
        setup = Setup(
            stock=self._stock,
            tool=tool.as_model(),
            material=self._material,
            machine=self._machine,
            safe_z=self._safe_z,
        )
        identity = tool_identity(tool)
        filename = _build_filename(operation, identity)
        moves = []
        if self._prime_spindle:
            moves.append({"kind": "set_rpm", "rpm": 0})
        return PassRecord(
            op=operation,
            tool_dict=identity,
            tool_selection=tool,
            setup=setup,
            filename=filename,
            moves=moves,
        )

    def get_record(self, operation: str, tool: ToolSelection) -> PassRecord:
        key = pass_key(operation, tool)
        if key not in self._records:
            self._records[key] = self._make_record(operation, tool)
        return self._records[key]

    def passes(self) -> List[PassRecord]:
        return list(self._records.values())


def _mm_str(value: float) -> str:
    return f"{value:.2f}mm".replace(".00mm", "mm")


def _build_filename(operation: str, tool_dict: Mapping[str, Any]) -> str:
    bits = [operation, _mm_str(float(tool_dict.get("diameter", 0.0)))]
    rotation = tool_dict.get("rotation")
    if rotation:
        bits.append(str(rotation))
    return "-".join(bits).replace(" ", "_") + ".nc"


def plan_passes(
    hints: Mapping[str, Any],
    *,
    config: Config,
    tool_db: Sequence[Mapping[str, Any]],
    material: Material,
    machine: Machine,
    stock: Stock,
    safe_z: float | None = None,
    prime_spindle: bool = False,
    profile_opts: Optional[Mapping[str, Any]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Plan CAM passes for the provided hints using the configured tolerances."""

    safe_z_value = float(config.safe_z_mm if safe_z is None else safe_z)
    accumulator = PassAccumulator(
        material=material,
        machine=machine,
        stock=stock,
        safe_z=safe_z_value,
        prime_spindle=prime_spindle,
    )

    plan_pocket_passes(hints, accumulator=accumulator, tool_db=tool_db, config=config)
    plan_hole_passes(hints, accumulator=accumulator, tool_db=tool_db)
    plan_engrave_passes(hints, accumulator=accumulator, tool_db=tool_db)

    kerf_mm = float(hints.get("kerf_width_mm", 0.0))

    profile_data = profile_opts or {}
    onion_skin_mm = _extract_positive_float(profile_data.get("onion_skin_mm", 0.0))
    tabs_opts = _normalize_tabs(profile_data.get("tabs"))
    tabs_enabled = bool(tabs_opts)
    cut_through_mm = _extract_positive_float(profile_data.get("cut_through_mm", 0.0))

    merge_enabled = config.merge_epsilon_mm > 0.0 and not (onion_skin_mm > 0.0 or tabs_enabled)

    profiles = hints.get("profiles", []) or []

    def _tabs_for_record(rec: Mapping[str, Any]) -> Optional[Dict[str, float]]:
        value = rec.get("tabs") if isinstance(rec, Mapping) else None
        if isinstance(value, Mapping):
            custom = _normalize_tabs(value)
            return custom if custom is not None else tabs_opts
        if isinstance(value, bool):
            return tabs_opts if value else None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"off", "none", "skip", "false"}:
                return None
            if lowered in {"on", "true", "force"}:
                return tabs_opts
        return tabs_opts

    rect_profiles = [rec for rec in profiles if _shape_name(rec) == "rect"]
    circle_profiles = [rec for rec in profiles if _shape_name(rec) == "circle"]

    merged_seams = 0
    if merge_enabled and rect_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        record = accumulator.get_record("profile", profile_tool)
        merged_seams = merge_rect_profiles(
            rect_profiles,
            record=record,
            tool=profile_tool,
            config=config,
            cut_through_mm=cut_through_mm,
        )
    else:
        for rec in rect_profiles:
            profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
            record = accumulator.get_record("profile", profile_tool)
            geom = rec.get("geometry") or {}
            width = float(geom.get("w_mm", 0.0))
            height = float(geom.get("h_mm", 0.0))
            shape = rect_shape(width + profile_tool.diameter, height + profile_tool.diameter, ensure_center(rec))
            depth = max(0.0, float(rec.get("depth_mm", 0.0))) + cut_through_mm
            record.add_moves(
                profile_moves_with_options(
                    shape,
                    setup=record.setup,
                    depth_mm=depth,
                    tool=profile_tool,
                    onion_skin_mm=onion_skin_mm,
                    tabs_opts=_tabs_for_record(rec),
                ),
                increment=1,
            )

    for rec in circle_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        record = accumulator.get_record("profile", profile_tool)
        geom = rec.get("geometry") or {}
        diameter = float(geom.get("diameter_mm", 0.0))
        radius = 0.5 * diameter
        side = str(rec.get("side", "on")).lower()
        tool_radius = 0.5 * profile_tool.diameter
        if side == "outside":
            radius += tool_radius
        elif side == "inside":
            radius -= tool_radius
        if radius <= 0.0:
            continue
        shape = circle_shape_mm(radius * 2.0, ensure_center(rec))
        depth = max(0.0, float(rec.get("depth_mm", 0.0))) + cut_through_mm
        record.add_moves(
            profile_moves_with_options(
                shape,
                setup=record.setup,
                depth_mm=depth,
                tool=profile_tool,
                onion_skin_mm=onion_skin_mm,
                tabs_opts=_tabs_for_record(rec),
            ),
            increment=1,
        )

    pass_dicts = [record.to_dict() for record in accumulator.passes()]

    profile_options_summary = _build_profile_summary(onion_skin_mm, tabs_opts, cut_through_mm)
    summary = summarise_passes(
        pass_dicts,
        merge_enabled=merge_enabled,
        merged_seams=merged_seams,
        profile_options=profile_options_summary,
    )

    return pass_dicts, summary


def _shape_name(record: Mapping[str, Any]) -> str:
    return str(record.get("shape") or record.get("type") or "").lower()


def _extract_positive_float(value: Any) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return num if num > 0.0 else 0.0


def _normalize_tabs(raw: Any) -> Optional[Dict[str, float]]:
    if not isinstance(raw, Mapping):
        return None
    try:
        count = int(raw.get("count", 0) or 0)
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None
    tabs: Dict[str, float] = {"count": float(count)}
    try:
        tabs["height_mm"] = float(raw.get("height_mm", 3.0))
    except (TypeError, ValueError):
        tabs["height_mm"] = 3.0
    if "width_mm" in raw:
        try:
            tabs["width_mm"] = float(raw.get("width_mm"))
        except (TypeError, ValueError):
            pass
    return tabs


def _build_profile_summary(onion_skin_mm: float, tabs_opts: Optional[Mapping[str, float]], cut_through_mm: float) -> Optional[Dict[str, Any]]:
    summary: Dict[str, Any] = {}
    if onion_skin_mm > 0.0:
        summary["onion_skin_mm"] = onion_skin_mm
    if tabs_opts:
        summary["tabs"] = {
            "count": int(tabs_opts.get("count", 0)),
            "height_mm": float(tabs_opts.get("height_mm", 3.0)),
        }
        if "width_mm" in tabs_opts:
            summary["tabs"]["width_mm"] = float(tabs_opts["width_mm"])
    if cut_through_mm > 0.0:
        summary["cut_through_mm"] = cut_through_mm
    return summary or None


__all__ = ["PassAccumulator", "PassRecord", "plan_passes"]
