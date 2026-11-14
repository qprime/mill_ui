from __future__ import annotations

import contextlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from cam.config import Config
from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.moves import CutMove, Move, SetRpmMove
from cam.ops.profile import profile_outline
from cam.planner.planner_input import FeatureInput, PlannerInput, TabsInput
from cam.shape import Shape2D

from .edge import plan_edge_feature_passes
from .merge_shared_edges import merge_rect_profiles, plan_shared_rect_profiles, validate_rect_profile_clearance
from .pocket import (
    plan_corner_cleanup_passes,
    plan_dogbone_passes,
    plan_engrave_passes,
    plan_hole_passes,
    plan_pocket_passes,
)
from .profile import (
    circle_shape_mm,
    offset_polygon_shape,
    offset_rect_shape,
    offset_rounded_rect_shape,
    onion_skin_finish_moves,
    onion_skin_rough_moves,
    polygon_shape,
    profile_moves_with_options,
    rounded_rect_shape,
)
from .relief.rough import plan_heightfield_passes
from .summary import summarise_passes
from .tools import (
    ToolSelection,
    apply_feeds_override,
    normalize_tool_entries,
    pass_key,
    pick_tool_for_profile,
    stepdown_for_tool,
)


@dataclass
class PassRecord:
    op: str
    tool_selection: ToolSelection
    setup: Setup
    filename: str
    moves: list[Move] = field(default_factory=list)
    count: int = 0
    _cut_moves: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._cut_moves = sum(isinstance(move, CutMove) for move in self.moves)

    @property
    def cut_move_count(self) -> int:
        return self._cut_moves

    def setup_for(self, tool: ToolSelection) -> Setup:
        return replace(self.setup, tool=tool.as_model())

    def add_moves(self, moves: Iterable[Move], *, increment: int = 0) -> None:
        for move in moves:
            self.moves.append(move)
            self._cut_moves += isinstance(move, CutMove)
        if increment:
            self.count += int(increment)


class PassAccumulator:
    def __init__(
        self,
        *,
        machine: Machine,
        stock: Stock,
        safe_z: float,
        prime_spindle: bool,
        ramp_angle_deg: float = 3.0,
    ) -> None:
        self._machine = machine
        self._stock = stock
        self._safe_z = float(safe_z)
        self._prime_spindle = prime_spindle
        self._ramp_angle_deg = float(ramp_angle_deg)
        self._records: dict[tuple[str, float, str, str | None, float | None, float | None], PassRecord] = {}
        self._feature_tools: dict[str, ToolSelection] = {}
        self._warnings: list[str] = []
        self._errors: list[str] = []

    def _make_record(self, operation: str, tool: ToolSelection) -> PassRecord:
        setup = Setup(
            stock=self._stock,
            tool=tool.as_model(),
            machine=self._machine,
            safe_z=self._safe_z,
            ramp_angle_deg=self._ramp_angle_deg,
        )
        filename = _build_filename(operation, tool)
        moves: list[Move] = []
        if self._prime_spindle:
            moves.append(SetRpmMove(rpm=0))
        return PassRecord(
            op=operation,
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

    def set_feature_tool(self, feature_id: str, tool: ToolSelection) -> None:
        self._feature_tools[feature_id] = tool

    def get_feature_tool(self, feature_id: str) -> ToolSelection | None:
        return self._feature_tools.get(feature_id)

    def add_warning(self, message: str) -> None:
        self._warnings.append(message)

    def add_error(self, message: str) -> None:
        self._errors.append(message)

    @property
    def stock(self) -> Stock:
        return self._stock

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def cut_move_count(self) -> int:
        return sum(record.cut_move_count for record in self._records.values())

    def passes(self) -> list[PassRecord]:
        return list(self._records.values())


def _mm_str(value: float) -> str:
    return f"{value:.2f}mm".replace(".00mm", "mm")


def _build_filename(operation: str, tool: ToolSelection) -> str:
    bits = [operation, _mm_str(float(tool.diameter))]
    if tool.rotation:
        bits.append(str(tool.rotation))
    return "-".join(bits).replace(" ", "_") + ".nc"


def plan_passes(  # noqa: C901 — feature-type dispatcher (defer refactor)
    planner_input: PlannerInput,
    *,
    config: Config,
    tool_db: Sequence[ToolSelection],
    machine: Machine,
    stock: Stock,
    safe_z: float | None = None,
    prime_spindle: bool = False,
    profile_opts: Mapping[str, Any] | None = None,
) -> tuple[list[PassRecord], dict[str, Any], list[str], list[str]]:

    safe_z_value = float(config.safe_z_mm if safe_z is None else safe_z)
    accumulator = PassAccumulator(
        machine=machine,
        stock=stock,
        safe_z=safe_z_value,
        prime_spindle=prime_spindle,
        ramp_angle_deg=float(config.ramp_angle_deg),
    )

    plan_pocket_passes(planner_input.pockets, accumulator=accumulator, tool_db=tool_db, config=config)
    plan_hole_passes(planner_input.holes, accumulator=accumulator, tool_db=tool_db)
    plan_engrave_passes(planner_input.engraves, accumulator=accumulator, tool_db=tool_db)
    plan_corner_cleanup_passes(planner_input.corner_cleanups, accumulator=accumulator, tool_db=tool_db)
    plan_dogbone_passes(planner_input.dogbones, accumulator=accumulator, tool_db=tool_db)
    plan_heightfield_passes(planner_input.heightfields, accumulator=accumulator, tool_db=tool_db, config=config)

    plan_edge_feature_passes(planner_input.edge_features, accumulator=accumulator, tool_db=tool_db)

    kerf_mm = planner_input.kerf_width_mm

    profile_data = profile_opts or {}
    onion_skin_mm = _extract_positive_float(profile_data.get("onion_skin_mm", 0.0))
    tabs_opts = _normalize_tabs(profile_data.get("tabs"))
    tabs_enabled = bool(tabs_opts)
    cut_through_mm = _extract_positive_float(profile_data.get("cut_through_mm", 0.0))

    profiles = planner_input.profiles

    any_profile_has_tabs = tabs_enabled or any(rec.tabs is not None for rec in profiles)
    any_profile_has_onion_skin = onion_skin_mm > 0.0 or any(
        rec.onion_skin_mm is not None and rec.onion_skin_mm > 0.0 for rec in profiles
    )

    merge_enabled = config.merge_epsilon_mm > 0.0 and not (any_profile_has_onion_skin or any_profile_has_tabs)

    def _tabs_for_feature(rec: FeatureInput) -> dict[str, float] | None:
        if rec.tabs is not None:
            custom = _normalize_tabs(
                {
                    "count": rec.tabs.count,
                    "height_mm": rec.tabs.height_mm,
                    "width_mm": rec.tabs.width_mm,
                }
            )
            return custom if custom is not None else tabs_opts
        return tabs_opts

    def _onion_skin_for_feature(rec: FeatureInput) -> float:
        if rec.onion_skin_mm is not None:
            return rec.onion_skin_mm
        return onion_skin_mm

    for rec in profiles:
        if _tabs_for_feature(rec) and _onion_skin_for_feature(rec) > 0.0:
            raise ValueError(f"Profile '{rec.id}': onion skin and tabs cannot be combined")

    rect_profiles = [rec for rec in profiles if rec.shape.lower() == "rect"]
    circle_profiles = [rec for rec in profiles if rec.shape.lower() == "circle"]
    polygon_profiles = [rec for rec in profiles if rec.shape.lower() == "polygon"]
    rounded_rect_profiles = [rec for rec in profiles if rec.shape.lower() == "roundedrect"]

    deferred_finishes: list[tuple[FeatureInput, Shape2D, ToolSelection]] = []
    deferred_releases: list[tuple[Shape2D, Setup, ToolSelection, float]] = []

    def _add_profile_moves(rec: FeatureInput, shape: Shape2D, tool: ToolSelection, *, finishing: bool = False) -> None:
        skin = _onion_skin_for_feature(rec)
        tabs = _tabs_for_feature(rec)
        nominal_depth = max(0.0, rec.depth_mm)
        held = skin > 0.0 or bool(tabs)
        allowance = rec.edge_treatment is not None and rec.edge_treatment.type == "allowance"
        operation = ("profile_finish" if held else "finish") if finishing else "profile"
        record = accumulator.get_record(operation, tool)
        setup = record.setup_for(tool)
        if allowance and not finishing and held:
            web = float(tabs["height_mm"]) if tabs else skin
            rough_depth = max(0.0, nominal_depth - web)
            if rough_depth > 0.0:
                record.add_moves(
                    profile_outline(shape, setup, rough_depth, step_down=stepdown_for_tool(tool)), increment=1
                )
        elif skin > 0.0:
            rough_moves, finish_depth = onion_skin_rough_moves(
                shape,
                setup=setup,
                depth_mm=nominal_depth,
                tool=tool,
                onion_skin_mm=skin,
                cut_through_mm=cut_through_mm,
            )
            record.add_moves(rough_moves, increment=1)
            deferred_releases.append((shape, setup, tool, finish_depth))
        else:
            adjusted_tabs = {**tabs, "height_mm": tabs["height_mm"] + cut_through_mm} if tabs else None
            record.add_moves(
                profile_moves_with_options(
                    shape,
                    setup=setup,
                    depth_mm=nominal_depth + cut_through_mm,
                    tool=tool,
                    onion_skin_mm=0.0,
                    tabs_opts=adjusted_tabs,
                ),
                increment=1,
            )

    def _plan_profile_stage(rec: FeatureInput, shape: Shape2D, tool: ToolSelection, label: str = "profile") -> None:
        if label == "finish" and (_tabs_for_feature(rec) or _onion_skin_for_feature(rec) > 0.0):
            deferred_finishes.append((rec, shape, tool))
        else:
            _add_profile_moves(rec, shape, tool, finishing=label == "finish")

    merged_seams = 0
    merged_indices: set[int] = set()
    if rect_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        validate_rect_profile_clearance(rect_profiles, profile_tool.diameter)
        groups = (
            merge_rect_profiles(rect_profiles, tool_diameter_mm=profile_tool.diameter, config=config)
            if merge_enabled
            else ()
        )
        if groups:
            record = accumulator.get_record("profile", profile_tool)
            merged_seams = plan_shared_rect_profiles(
                groups, record=record, tool=profile_tool, cut_through_mm=cut_through_mm
            )
            merged_indices = {index for group in groups for index in group.profile_indices}
    for index, rec in enumerate(rect_profiles):
        if index not in merged_indices:
            profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
            profile_tool = apply_feeds_override(profile_tool, rec.feeds_override)
            width = float(rec.geometry.geometry.w_mm or 0.0)
            height = float(rec.geometry.geometry.h_mm or 0.0)
            side = (rec.side or "on").lower()
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            tool_radius = profile_tool.diameter / 2.0
            et = rec.edge_treatment
            has_allowance = et is not None and et.type == "allowance"
            stages = (
                [("profile", et.rough_allowance_mm or 0.0), ("finish", et.finish_allowance_mm or 0.0)]
                if has_allowance and et is not None
                else [("profile", 0.0)]
            )
            for label, allowance in stages:
                offset = sign * (tool_radius + allowance)
                shape = offset_rect_shape(width, height, rec.center_xy_mm, offset)
                if shape is None:
                    raise ValueError(
                        f"Rectangle profile '{rec.id}' ({label}): {width}x{height}mm boundary "
                        f"has no positive centerline dimensions at offset {offset}mm "
                        f"with selected cutter diameter {profile_tool.diameter}mm"
                    )
                _plan_profile_stage(rec, shape, profile_tool, label)

    for rec in circle_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        profile_tool = apply_feeds_override(profile_tool, rec.feeds_override)
        diameter = float(rec.geometry.geometry.diameter_mm or 0.0)
        radius = 0.5 * diameter
        side = (rec.side or "on").lower()
        tool_radius = 0.5 * profile_tool.diameter
        et = rec.edge_treatment
        if et is not None and et.type == "allowance":
            rough_allow = et.rough_allowance_mm or 0.0
            finish_allow = et.finish_allowance_mm or 0.0
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            for label, allow in [("profile", rough_allow), ("finish", finish_allow)]:
                r = radius + sign * (tool_radius + allow)
                if r <= 0.0:
                    continue
                s = circle_shape_mm(r * 2.0, rec.center_xy_mm)
                _plan_profile_stage(rec, s, profile_tool, label)
        else:
            if side == "outside":
                radius += tool_radius
            elif side == "inside":
                radius -= tool_radius
            if radius <= 0.0:
                continue
            shape = circle_shape_mm(radius * 2.0, rec.center_xy_mm)
            _plan_profile_stage(rec, shape, profile_tool)

    for rec in polygon_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        profile_tool = apply_feeds_override(profile_tool, rec.feeds_override)
        raw_points = rec.geometry.geometry.points
        points = [list(p) for p in raw_points] if raw_points is not None else []
        if not points:
            continue
        side = (rec.side or "on").lower()
        tool_radius = 0.5 * profile_tool.diameter
        et = rec.edge_treatment
        if et is not None and et.type == "allowance":
            rough_allow = et.rough_allowance_mm or 0.0
            finish_allow = et.finish_allowance_mm or 0.0
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            for label, allow in [("profile", rough_allow), ("finish", finish_allow)]:
                off = sign * (tool_radius + allow)
                s: Shape2D | None = (
                    offset_polygon_shape(points, rec.center_xy_mm, off)
                    if abs(off) > 1e-9
                    else polygon_shape(points, rec.center_xy_mm)
                )
                if s is None:
                    continue
                _plan_profile_stage(rec, s, profile_tool, label)
        else:
            offset = 0.0
            if side == "outside":
                offset = tool_radius
            elif side == "inside":
                offset = -tool_radius
            shape_poly: Shape2D | None
            if offset != 0.0:
                shape_poly = offset_polygon_shape(points, rec.center_xy_mm, offset)
            else:
                shape_poly = polygon_shape(points, rec.center_xy_mm)
            if shape_poly is None:
                continue
            _plan_profile_stage(rec, shape_poly, profile_tool)

    for rec in rounded_rect_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        profile_tool = apply_feeds_override(profile_tool, rec.feeds_override)
        sg = rec.geometry.geometry
        width = float(sg.w_mm or 0.0)
        height = float(sg.h_mm or 0.0)
        fallback_r = float(sg.radius_mm or 0.0)
        radii = {
            "tl": float(sg.radius_tl_mm if sg.radius_tl_mm is not None else fallback_r),
            "tr": float(sg.radius_tr_mm if sg.radius_tr_mm is not None else fallback_r),
            "br": float(sg.radius_br_mm if sg.radius_br_mm is not None else fallback_r),
            "bl": float(sg.radius_bl_mm if sg.radius_bl_mm is not None else fallback_r),
        }
        side = (rec.side or "on").lower()
        tool_radius = 0.5 * profile_tool.diameter
        et = rec.edge_treatment
        if et is not None and et.type == "allowance":
            rough_allow = et.rough_allowance_mm or 0.0
            finish_allow = et.finish_allowance_mm or 0.0
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            for label, allow in [("profile", rough_allow), ("finish", finish_allow)]:
                off = sign * (tool_radius + allow)
                s: Shape2D | None = (
                    offset_rounded_rect_shape(width, height, radii, rec.center_xy_mm, off)
                    if abs(off) > 1e-9
                    else rounded_rect_shape(width, height, radii, rec.center_xy_mm)
                )
                if s is None:
                    continue
                _plan_profile_stage(rec, s, profile_tool, label)
        else:
            offset = 0.0
            if side == "outside":
                offset = tool_radius
            elif side == "inside":
                offset = -tool_radius
            shape_rr: Shape2D | None
            if offset != 0.0:
                shape_rr = offset_rounded_rect_shape(width, height, radii, rec.center_xy_mm, offset)
            else:
                shape_rr = rounded_rect_shape(width, height, radii, rec.center_xy_mm)
            if shape_rr is None:
                continue
            _plan_profile_stage(rec, shape_rr, profile_tool)

    for feature, finish_shape, finish_tool in deferred_finishes:
        _add_profile_moves(feature, finish_shape, finish_tool, finishing=True)

    for shape_def, deferred_setup, release_tool, finish_depth in deferred_releases:
        release_record = accumulator.get_record("release", release_tool)
        release_record.add_moves(
            onion_skin_finish_moves(shape_def, setup=deferred_setup, finish_depth=finish_depth), increment=1
        )

    pass_records = accumulator.passes()

    profile_options_summary = _build_profile_summary(onion_skin_mm, tabs_opts, cut_through_mm)
    summary = summarise_passes(
        pass_records,
        merge_enabled=merge_enabled,
        merged_seams=merged_seams,
        profile_options=profile_options_summary,
    )

    return pass_records, summary, accumulator.warnings, accumulator.errors


def _extract_positive_float(value: Any) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return num if num > 0.0 else 0.0


def _normalize_tabs(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, Mapping):
        return None
    try:
        count = int(raw.get("count", 0) or 0)
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None
    tabs: dict[str, float] = {"count": float(count)}
    try:
        tabs["height_mm"] = float(raw.get("height_mm", 3.0))
    except (TypeError, ValueError):
        tabs["height_mm"] = 3.0
    if "width_mm" in raw:
        with contextlib.suppress(TypeError, ValueError):
            tabs["width_mm"] = float(raw.get("width_mm", 0.0))
    return tabs


def _build_profile_summary(
    onion_skin_mm: float, tabs_opts: Mapping[str, float] | None, cut_through_mm: float
) -> dict[str, Any] | None:
    summary: dict[str, Any] = {}
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


__all__ = ["PassAccumulator", "PassRecord", "TabsInput", "normalize_tool_entries", "plan_passes"]
