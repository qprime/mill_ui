from __future__ import annotations

import contextlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from cam.config import Config
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.moves import Move, SetRpmMove
from cam.ops.profile import profile_outline
from cam.planner.planner_input import FeatureInput, PlannerInput, TabsInput
from cam.shape import Shape2D

from .edge import plan_edge_feature_passes
from .merge_shared_edges import merge_rect_profiles
from .pocket import plan_corner_cleanup_passes, plan_engrave_passes, plan_hole_passes, plan_pocket_passes
from .profile import (
    circle_shape_mm,
    offset_polygon_shape,
    offset_rect_shape,
    offset_rounded_rect_shape,
    polygon_shape,
    profile_moves_with_options,
    rect_shape,
    rounded_rect_shape,
)
from .summary import summarise_passes
from .tools import ToolSelection, normalize_tool_entries, pass_key, pick_tool_for_profile, stepdown_for_tool


@dataclass
class PassRecord:
    op: str
    tool_selection: ToolSelection
    setup: Setup
    filename: str
    moves: list[Move] = field(default_factory=list)
    count: int = 0

    def add_moves(self, moves: Iterable[Move], *, increment: int = 0) -> None:
        for move in moves:
            self.moves.append(move)
        if increment:
            self.count += int(increment)


class PassAccumulator:
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
        self._records: dict[tuple[str, float, str, str | None, float | None], PassRecord] = {}

    def _make_record(self, operation: str, tool: ToolSelection) -> PassRecord:
        setup = Setup(
            stock=self._stock,
            tool=tool.as_model(),
            material=self._material,
            machine=self._machine,
            safe_z=self._safe_z,
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

    def passes(self) -> list[PassRecord]:
        return list(self._records.values())


def _mm_str(value: float) -> str:
    return f"{value:.2f}mm".replace(".00mm", "mm")


def _build_filename(operation: str, tool: ToolSelection) -> str:
    bits = [operation, _mm_str(float(tool.diameter))]
    if tool.rotation:
        bits.append(str(tool.rotation))
    return "-".join(bits).replace(" ", "_") + ".nc"


def plan_passes(
    planner_input: PlannerInput,
    *,
    config: Config,
    tool_db: Sequence[ToolSelection],
    material: Material,
    machine: Machine,
    stock: Stock,
    safe_z: float | None = None,
    prime_spindle: bool = False,
    profile_opts: Mapping[str, Any] | None = None,
) -> tuple[list[PassRecord], dict[str, Any]]:

    safe_z_value = float(config.safe_z_mm if safe_z is None else safe_z)
    accumulator = PassAccumulator(
        material=material,
        machine=machine,
        stock=stock,
        safe_z=safe_z_value,
        prime_spindle=prime_spindle,
    )

    plan_pocket_passes(planner_input.pockets, accumulator=accumulator, tool_db=tool_db, config=config)
    plan_hole_passes(planner_input.holes, accumulator=accumulator, tool_db=tool_db)
    plan_engrave_passes(planner_input.engraves, accumulator=accumulator, tool_db=tool_db)
    plan_corner_cleanup_passes(planner_input.corner_cleanups, accumulator=accumulator, tool_db=tool_db)

    plan_edge_feature_passes(planner_input.edge_features, accumulator=accumulator, tool_db=tool_db)

    kerf_mm = planner_input.kerf_width_mm

    profile_data = profile_opts or {}
    onion_skin_mm = _extract_positive_float(profile_data.get("onion_skin_mm", 0.0))
    tabs_opts = _normalize_tabs(profile_data.get("tabs"))
    tabs_enabled = bool(tabs_opts)
    cut_through_mm = _extract_positive_float(profile_data.get("cut_through_mm", 0.0))

    profiles = planner_input.profiles

    any_profile_has_tabs = tabs_enabled or any(rec.tabs is not None for rec in profiles)

    merge_enabled = config.merge_epsilon_mm > 0.0 and not (onion_skin_mm > 0.0 or any_profile_has_tabs)

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

    rect_profiles = [rec for rec in profiles if rec.shape.lower() == "rect"]
    circle_profiles = [rec for rec in profiles if rec.shape.lower() == "circle"]
    polygon_profiles = [rec for rec in profiles if rec.shape.lower() == "polygon"]
    rounded_rect_profiles = [rec for rec in profiles if rec.shape.lower() == "roundedrect"]

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
            width = float(rec.geometry.geometry.w_mm or 0.0)
            height = float(rec.geometry.geometry.h_mm or 0.0)
            depth = max(0.0, rec.depth_mm) + cut_through_mm
            et = rec.edge_treatment
            if et is not None and et.type == "allowance":
                rough_allow = et.rough_allowance_mm or 0.0
                finish_allow = et.finish_allowance_mm or 0.0
                tool_r = 0.5 * profile_tool.diameter
                rough_record = accumulator.get_record("profile", profile_tool)
                rough_shape = offset_rect_shape(width, height, rec.center_xy_mm, tool_r + rough_allow)
                if rough_shape is not None:
                    step_down = stepdown_for_tool(profile_tool)
                    rough_moves = profile_outline(rough_shape, rough_record.setup, depth, step_down=step_down)
                    rough_record.add_moves(rough_moves, increment=1)
                finish_record = accumulator.get_record("finish", profile_tool)
                finish_shape = offset_rect_shape(width, height, rec.center_xy_mm, tool_r + finish_allow)
                if finish_shape is not None:
                    step_down = stepdown_for_tool(profile_tool)
                    finish_moves = profile_outline(finish_shape, finish_record.setup, depth, step_down=step_down)
                    finish_record.add_moves(finish_moves, increment=1)
            else:
                record = accumulator.get_record("profile", profile_tool)
                shape = rect_shape(width + profile_tool.diameter, height + profile_tool.diameter, rec.center_xy_mm)
                record.add_moves(
                    profile_moves_with_options(
                        shape,
                        setup=record.setup,
                        depth_mm=depth,
                        tool=profile_tool,
                        onion_skin_mm=onion_skin_mm,
                        tabs_opts=_tabs_for_feature(rec),
                    ),
                    increment=1,
                )

    for rec in circle_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        diameter = float(rec.geometry.geometry.diameter_mm or 0.0)
        radius = 0.5 * diameter
        side = (rec.side or "on").lower()
        tool_radius = 0.5 * profile_tool.diameter
        depth = max(0.0, rec.depth_mm) + cut_through_mm
        et = rec.edge_treatment
        if et is not None and et.type == "allowance":
            rough_allow = et.rough_allowance_mm or 0.0
            finish_allow = et.finish_allowance_mm or 0.0
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            step_down = stepdown_for_tool(profile_tool)
            for label, allow in [("profile", rough_allow), ("finish", finish_allow)]:
                r = radius + sign * (tool_radius + allow)
                if r <= 0.0:
                    continue
                s = circle_shape_mm(r * 2.0, rec.center_xy_mm)
                rec_pass = accumulator.get_record(label, profile_tool)
                rec_pass.add_moves(profile_outline(s, rec_pass.setup, depth, step_down=step_down), increment=1)
        else:
            if side == "outside":
                radius += tool_radius
            elif side == "inside":
                radius -= tool_radius
            if radius <= 0.0:
                continue
            record = accumulator.get_record("profile", profile_tool)
            shape = circle_shape_mm(radius * 2.0, rec.center_xy_mm)
            record.add_moves(
                profile_moves_with_options(
                    shape,
                    setup=record.setup,
                    depth_mm=depth,
                    tool=profile_tool,
                    onion_skin_mm=onion_skin_mm,
                    tabs_opts=_tabs_for_feature(rec),
                ),
                increment=1,
            )

    for rec in polygon_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
        raw_points = rec.geometry.geometry.points
        points = [list(p) for p in raw_points] if raw_points is not None else []
        if not points:
            continue
        side = (rec.side or "on").lower()
        tool_radius = 0.5 * profile_tool.diameter
        depth = max(0.0, rec.depth_mm) + cut_through_mm
        et = rec.edge_treatment
        if et is not None and et.type == "allowance":
            rough_allow = et.rough_allowance_mm or 0.0
            finish_allow = et.finish_allowance_mm or 0.0
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            step_down = stepdown_for_tool(profile_tool)
            for label, allow in [("profile", rough_allow), ("finish", finish_allow)]:
                off = sign * (tool_radius + allow)
                s: Shape2D | None = (
                    offset_polygon_shape(points, rec.center_xy_mm, off)
                    if abs(off) > 1e-9
                    else polygon_shape(points, rec.center_xy_mm)
                )
                if s is None:
                    continue
                rec_pass = accumulator.get_record(label, profile_tool)
                rec_pass.add_moves(profile_outline(s, rec_pass.setup, depth, step_down=step_down), increment=1)
        else:
            record = accumulator.get_record("profile", profile_tool)
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
            record.add_moves(
                profile_moves_with_options(
                    shape_poly,
                    setup=record.setup,
                    depth_mm=depth,
                    tool=profile_tool,
                    onion_skin_mm=onion_skin_mm,
                    tabs_opts=_tabs_for_feature(rec),
                ),
                increment=1,
            )

    for rec in rounded_rect_profiles:
        profile_tool = pick_tool_for_profile(tool_db, kerf_mm=kerf_mm)
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
        depth = max(0.0, rec.depth_mm) + cut_through_mm
        et = rec.edge_treatment
        if et is not None and et.type == "allowance":
            rough_allow = et.rough_allowance_mm or 0.0
            finish_allow = et.finish_allowance_mm or 0.0
            sign = 1.0 if side == "outside" else (-1.0 if side == "inside" else 0.0)
            step_down = stepdown_for_tool(profile_tool)
            for label, allow in [("profile", rough_allow), ("finish", finish_allow)]:
                off = sign * (tool_radius + allow)
                s: Shape2D | None = (
                    offset_rounded_rect_shape(width, height, radii, rec.center_xy_mm, off)
                    if abs(off) > 1e-9
                    else rounded_rect_shape(width, height, radii, rec.center_xy_mm)
                )
                if s is None:
                    continue
                rec_pass = accumulator.get_record(label, profile_tool)
                rec_pass.add_moves(profile_outline(s, rec_pass.setup, depth, step_down=step_down), increment=1)
        else:
            record = accumulator.get_record("profile", profile_tool)
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
            record.add_moves(
                profile_moves_with_options(
                    shape_rr,
                    setup=record.setup,
                    depth_mm=depth,
                    tool=profile_tool,
                    onion_skin_mm=onion_skin_mm,
                    tabs_opts=_tabs_for_feature(rec),
                ),
                increment=1,
            )

    pass_records = accumulator.passes()

    profile_options_summary = _build_profile_summary(onion_skin_mm, tabs_opts, cut_through_mm)
    summary = summarise_passes(
        pass_records,
        merge_enabled=merge_enabled,
        merged_seams=merged_seams,
        profile_options=profile_options_summary,
    )

    return pass_records, summary


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
