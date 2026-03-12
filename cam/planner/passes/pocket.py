from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from cam.ops.bore import bore_helical, pocket_circle_concentric
from cam.ops.drill import drill_peck
from cam.ops.engrave import engrave_lines
from cam.ops.pocket_region import pocket_region_rect_raster
from cam.ops.profile import profile_outline
from cam.path.strategies import pocket_then_finish_profile
from cam.path.toolpath import offset_moves_z
from cam.planner.planner_input import CornerCleanupInput, DogboneInput, FeatureInput

from .profile import offset_rect_shape, rect_shape
from .tools import (
    ToolSelection,
    apply_feeds_override,
    pick_tool_by_diameter,
    pick_tool_for_engrave,
    pick_tool_for_hole,
    pick_tool_for_pocket,
    stepdown_for_tool,
    stepover_for_tool,
)

if TYPE_CHECKING:
    from cam.config import Config

    from . import PassAccumulator, PassRecord


def _pocket_with_allowance(
    width: float,
    height: float,
    center: tuple[float, float],
    *,
    record: PassRecord,
    depth: float,
    start_depth: float,
    step_over: float,
    step_down: float,
    cleanup_offset_mm: float,
    rough_allowance_mm: float,
    finish_allowance_mm: float,
    tool: ToolSelection,
    accumulator: PassAccumulator,
) -> None:
    from cam.ops.pocket import pocket_raster

    tool_r = 0.5 * tool.diameter
    cut_depth = depth - start_depth

    rough_shape = offset_rect_shape(width, height, center, -(tool_r + cleanup_offset_mm + rough_allowance_mm))
    if rough_shape is not None:
        rough_moves = pocket_raster(
            rough_shape, record.setup, depth_mm=cut_depth, stepover=step_over, stepdown=step_down
        )
        record.add_moves(offset_moves_z(rough_moves, start_depth), increment=0)

    rough_profile_shape = offset_rect_shape(width, height, center, -(tool_r + rough_allowance_mm))
    if rough_profile_shape is not None:
        rough_profile_moves = profile_outline(
            rough_profile_shape, record.setup, depth_mm=cut_depth, step_down=step_down
        )
        record.add_moves(offset_moves_z(rough_profile_moves, start_depth), increment=1)

    finish_record = accumulator.get_record("finish", tool)
    finish_shape = offset_rect_shape(width, height, center, -(tool_r + finish_allowance_mm))
    if finish_shape is not None:
        finish_moves = profile_outline(finish_shape, finish_record.setup, depth_mm=cut_depth, step_down=step_down)
        finish_record.add_moves(offset_moves_z(finish_moves, start_depth), increment=1)


def _extract_rect_dims(entry: FeatureInput) -> tuple[float, float]:
    sg = entry.geometry.geometry
    shape_name = entry.shape.lower()
    if shape_name == "rect":
        return float(sg.w_mm or 0.0), float(sg.h_mm or 0.0)
    elif shape_name == "polygon":
        pts = sg.points or ()
        if not pts:
            return 0.0, 0.0
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        return max(xs) - min(xs), max(ys) - min(ys)
    raise ValueError(f"Cannot extract rect dims from shape '{shape_name}'")


def _plan_rest_pocket(
    entry: FeatureInput,
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
    config: Config,
) -> None:
    from cam.ops.pocket import pocket_raster

    assert entry.rest is not None
    rest = entry.rest
    shape_name = entry.shape.lower()

    if shape_name not in ("rect", "polygon"):
        raise ValueError(
            f"Rest pocketing only supported for rectangular pockets, got shape '{entry.shape}' on feature '{entry.id}'"
        )

    et = entry.edge_treatment
    if et is not None and et.type == "allowance":
        raise ValueError(
            f"Cannot combine 'rest' and 'edge_treatment: allowance' on feature '{entry.id}'. "
            f"Rest pocketing subsumes edge_treatment allowance — use rest alone."
        )

    width, height = _extract_rect_dims(entry)
    min_dim = min(width, height)

    if rest.tool_diameter_mm >= min_dim:
        raise ValueError(
            f"Rest tool diameter ({rest.tool_diameter_mm}mm) must be less than "
            f"pocket minimum dimension ({min_dim}mm) on feature '{entry.id}'"
        )

    rough_tool = pick_tool_for_pocket(
        tool_db,
        required_width_mm=min_dim,
        cleanup_offset_mm=config.cleanup_offset_mm,
    )
    rough_tool = apply_feeds_override(rough_tool, entry.feeds_override)
    accumulator.set_feature_tool(entry.id, rough_tool)

    finish_tool = pick_tool_by_diameter(tool_db, rest.tool_diameter_mm, kind="flat")
    finish_tool = apply_feeds_override(finish_tool, entry.feeds_override)

    if finish_tool.diameter >= rough_tool.diameter:
        raise ValueError(
            f"Rest finish tool ({finish_tool.diameter}mm) must be smaller than "
            f"rough tool ({rough_tool.diameter}mm) on feature '{entry.id}'"
        )

    center = entry.center_xy_mm
    depth = entry.depth_mm
    start_depth = max(0.0, entry.start_depth_mm)
    cut_depth = depth - start_depth
    if cut_depth <= 0.0:
        return

    rough_tool_r = 0.5 * rough_tool.diameter
    finish_tool_r = 0.5 * finish_tool.diameter
    rough_step_over = stepover_for_tool(rough_tool)
    rough_step_down = stepdown_for_tool(rough_tool)
    finish_step_over = stepover_for_tool(finish_tool)
    finish_step_down = stepdown_for_tool(finish_tool)

    rough_record = accumulator.get_record("pocket", rough_tool)
    rough_wall_offset = rough_tool_r + config.cleanup_offset_mm + rest.rough_allowance_mm
    rough_shape = offset_rect_shape(width, height, center, -rough_wall_offset)
    if rough_shape is not None:
        rough_moves = pocket_raster(
            rough_shape, rough_record.setup, depth_mm=cut_depth, stepover=rough_step_over, stepdown=rough_step_down
        )
        rough_record.add_moves(offset_moves_z(rough_moves, start_depth), increment=0)

    rough_profile_shape = offset_rect_shape(width, height, center, -(rough_tool_r + rest.rough_allowance_mm))
    if rough_profile_shape is not None:
        rough_profile_moves = profile_outline(
            rough_profile_shape, rough_record.setup, depth_mm=cut_depth, step_down=rough_step_down
        )
        rough_record.add_moves(offset_moves_z(rough_profile_moves, start_depth), increment=1)

    rest_record = accumulator.get_record("pocket_rest", finish_tool)

    half_w = 0.5 * width
    half_h = 0.5 * height
    cx, cy = center
    corner_size = rough_tool_r + finish_tool_r
    for corner_cx, corner_cy in [
        (cx - half_w + 0.5 * corner_size, cy - half_h + 0.5 * corner_size),
        (cx + half_w - 0.5 * corner_size, cy - half_h + 0.5 * corner_size),
        (cx + half_w - 0.5 * corner_size, cy + half_h - 0.5 * corner_size),
        (cx - half_w + 0.5 * corner_size, cy + half_h - 0.5 * corner_size),
    ]:
        corner_shape = offset_rect_shape(
            corner_size,
            corner_size,
            (corner_cx, corner_cy),
            -(finish_tool_r + rest.finish_allowance_mm),
        )
        if corner_shape is not None:
            corner_moves = pocket_raster(
                corner_shape,
                rest_record.setup,
                depth_mm=cut_depth,
                stepover=finish_step_over,
                stepdown=finish_step_down,
            )
            rest_record.add_moves(offset_moves_z(corner_moves, start_depth), increment=0)

    finish_profile_shape = offset_rect_shape(width, height, center, -(finish_tool_r + rest.finish_allowance_mm))
    if finish_profile_shape is not None:
        finish_profile_moves = profile_outline(
            finish_profile_shape, rest_record.setup, depth_mm=cut_depth, step_down=finish_step_down
        )
        rest_record.add_moves(offset_moves_z(finish_profile_moves, start_depth), increment=1)


def _plan_surface_pass(
    entry: FeatureInput,
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    from cam.ops.face import face_zigzag

    sc = entry.surface_cooling
    assert sc is not None

    sg = entry.geometry.geometry
    width = float(sg.w_mm or 0.0)
    height = float(sg.h_mm or 0.0)

    tool = pick_tool_for_pocket(tool_db, required_width_mm=min(width, height), cleanup_offset_mm=0.0)
    tool = apply_feeds_override(tool, entry.feeds_override)
    accumulator.set_feature_tool(entry.id, tool)
    record = accumulator.get_record("surface", tool)

    step_mm = tool.diameter * (sc.stepover_pct / 100.0)
    cut_depth = entry.depth_mm - sc.start_depth_mm
    if cut_depth <= 0.0:
        return

    moves = face_zigzag(
        width,
        height,
        record.setup,
        step=step_mm,
        depth_mm=cut_depth,
        direction=sc.direction,
        cool_every=sc.cool_every,
        cool_dwell_s=sc.cool_dwell_s,
    )
    record.add_moves(offset_moves_z(moves, sc.start_depth_mm), increment=1)


def plan_pocket_passes(
    pockets: tuple[FeatureInput, ...],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
    config: Config,
) -> None:
    for entry in pockets:
        if entry.surface_cooling is not None:
            _plan_surface_pass(entry, accumulator=accumulator, tool_db=tool_db)
            continue

        if entry.rest is not None:
            _plan_rest_pocket(entry, accumulator=accumulator, tool_db=tool_db, config=config)
            continue

        sg = entry.geometry.geometry
        shape_name = entry.shape.lower()
        required_width = None
        if shape_name == "rect":
            required_width = min(float(sg.w_mm or 0.0), float(sg.h_mm or 0.0))
        elif shape_name == "circle":
            required_width = float(sg.diameter_mm or 0.0)

        tool = pick_tool_for_pocket(
            tool_db,
            required_width_mm=required_width,
            cleanup_offset_mm=config.cleanup_offset_mm,
        )
        tool = apply_feeds_override(tool, entry.feeds_override)
        accumulator.set_feature_tool(entry.id, tool)
        record = accumulator.get_record("pocket", tool)
        setup = record.setup
        depth = entry.depth_mm
        start_depth = max(0.0, entry.start_depth_mm)
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth
        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        center = entry.center_xy_mm
        et = entry.edge_treatment
        has_allowance = et is not None and et.type == "allowance"

        if shape_name == "rect":
            width = float(sg.w_mm or 0.0)
            height = float(sg.h_mm or 0.0)
            shape = rect_shape(width, height, center)
            if has_allowance:
                assert et is not None
                rough_allow = et.rough_allowance_mm or 0.0
                finish_allow = et.finish_allowance_mm or 0.0
                _pocket_with_allowance(
                    width,
                    height,
                    center,
                    record=record,
                    depth=depth,
                    start_depth=start_depth,
                    step_over=step_over,
                    step_down=step_down,
                    cleanup_offset_mm=config.cleanup_offset_mm,
                    rough_allowance_mm=rough_allow,
                    finish_allowance_mm=finish_allow,
                    tool=tool,
                    accumulator=accumulator,
                )
            else:
                record.add_moves(
                    pocket_then_finish_profile(
                        shape,
                        setup,
                        total_depth_mm=depth,
                        stepover_mm=step_over,
                        step_down_mm=step_down,
                        cleanup_offset_mm=config.cleanup_offset_mm,
                        start_depth_mm=start_depth,
                        finish_perimeter=config.pocket_finish_perimeter,
                    ),
                    increment=1,
                )
        elif shape_name == "circle":
            diameter = float(sg.diameter_mm or 0.0)
            moves = pocket_circle_concentric(
                center,
                diameter,
                setup,
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
                finish=True,
            )
            record.add_moves(offset_moves_z(moves, start_depth), increment=1)
        elif shape_name == "region":
            moves = pocket_region_rect_raster(
                entry.to_dict(),
                setup,
                default_center_xy=center,
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
            )
            record.add_moves(offset_moves_z(moves, start_depth), increment=1)
        elif shape_name == "polygon":
            pts = sg.points or ()
            if not pts:
                continue
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
            shape = rect_shape(width, height, center)
            if has_allowance:
                assert et is not None
                rough_allow = et.rough_allowance_mm or 0.0
                finish_allow = et.finish_allowance_mm or 0.0
                _pocket_with_allowance(
                    width,
                    height,
                    center,
                    record=record,
                    depth=depth,
                    start_depth=start_depth,
                    step_over=step_over,
                    step_down=step_down,
                    cleanup_offset_mm=config.cleanup_offset_mm,
                    rough_allowance_mm=rough_allow,
                    finish_allowance_mm=finish_allow,
                    tool=tool,
                    accumulator=accumulator,
                )
            else:
                record.add_moves(
                    pocket_then_finish_profile(
                        shape,
                        setup,
                        total_depth_mm=depth,
                        stepover_mm=step_over,
                        step_down_mm=step_down,
                        cleanup_offset_mm=config.cleanup_offset_mm,
                        start_depth_mm=start_depth,
                        finish_perimeter=config.pocket_finish_perimeter,
                    ),
                    increment=1,
                )
        else:
            continue


def plan_hole_passes(
    holes: tuple[FeatureInput, ...],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in holes:
        if entry.shape.lower() != "circle":
            continue
        diameter = float(entry.geometry.geometry.diameter_mm or 0.0)
        center = entry.center_xy_mm
        depth = entry.depth_mm

        tool = pick_tool_for_hole(tool_db, hole_diameter_mm=diameter)
        tool = apply_feeds_override(tool, entry.feeds_override)
        tool_diameter = float(tool.diameter)
        eps = 0.05

        if diameter <= tool_diameter + eps:
            record = accumulator.get_record("drill", tool)
            peck = min(stepdown_for_tool(tool), 2.5)
            record.add_moves(
                drill_peck([center], record.setup, depth_mm=depth, peck=peck),
                increment=1,
            )
        elif diameter <= 3.0 * tool_diameter + eps:
            record = accumulator.get_record("bore", tool)
            step_down = stepdown_for_tool(tool)
            record.add_moves(
                bore_helical(center, diameter, record.setup, depth_mm=depth, stepdown_mm=step_down),
                increment=1,
            )
        else:
            record = accumulator.get_record("pocket", tool)
            step_over = stepover_for_tool(tool)
            step_down = stepdown_for_tool(tool)
            record.add_moves(
                pocket_circle_concentric(
                    center,
                    diameter,
                    record.setup,
                    depth_mm=depth,
                    stepover_mm=step_over,
                    stepdown_mm=step_down,
                    finish=True,
                ),
                increment=1,
            )


def plan_engrave_passes(
    engraves: tuple[FeatureInput, ...],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in engraves:
        sg = entry.geometry.geometry
        shape_name = entry.shape.lower()
        lines: list[list[tuple[float, float]]] = []

        if shape_name == "polyline":
            raw_points = sg.points or ()
            cx, cy = entry.center_xy_mm
            line = [(float(pt[0]) + cx, float(pt[1]) + cy) for pt in raw_points]
            if line:
                lines.append(line)
        elif shape_name == "rect":
            width = float(sg.w_mm or 0.0)
            height = float(sg.h_mm or 0.0)
            if width <= 0.0 or height <= 0.0:
                continue
            cx, cy = entry.center_xy_mm
            half_w = 0.5 * width
            half_h = 0.5 * height
            lines.append(
                [
                    (cx - half_w, cy - half_h),
                    (cx + half_w, cy - half_h),
                    (cx + half_w, cy + half_h),
                    (cx - half_w, cy + half_h),
                    (cx - half_w, cy - half_h),
                ]
            )
        elif shape_name == "line":
            start = sg.start or (0.0, 0.0)
            end = sg.end or (0.0, 0.0)
            cx, cy = entry.center_xy_mm
            lines.append(
                [
                    (float(start[0]) + cx, float(start[1]) + cy),
                    (float(end[0]) + cx, float(end[1]) + cy),
                ]
            )
        else:
            continue

        if not lines:
            continue

        tool = pick_tool_for_engrave(tool_db)
        tool = apply_feeds_override(tool, entry.feeds_override)
        record = accumulator.get_record("engrave", tool)
        depth = entry.depth_mm or 0.3
        record.add_moves(
            engrave_lines(lines, record.setup, z=-abs(depth)),
            increment=len(lines),
        )


def plan_corner_cleanup_passes(
    corner_cleanups: tuple[CornerCleanupInput, ...],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in corner_cleanups:
        corner_tool_diameter = entry.corner_tool_diameter_mm
        if corner_tool_diameter <= 0.0:
            continue

        tool = pick_tool_by_diameter(tool_db, corner_tool_diameter)

        record = accumulator.get_record("corner_cleanup", tool)
        setup = record.setup

        depth = entry.depth_mm
        start_depth = entry.start_depth_mm
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth

        corners = entry.corners
        if not corners:
            continue

        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        corner_pocket_diameter = 2.0 * corner_tool_diameter

        for corner_xy in corners:
            moves = pocket_circle_concentric(
                corner_xy,
                corner_pocket_diameter,
                setup,
                depth_mm=effective_depth,
                stepover_mm=step_over,
                stepdown_mm=step_down,
                finish=True,
            )

            moves = offset_moves_z(moves, start_depth)
            record.add_moves(moves, increment=1)


_SQRT2_INV = 1.0 / math.sqrt(2.0)


def _axis_direction(corner_val: float, ref_val: float) -> float:
    if corner_val > ref_val + 1e-9:
        return -1.0
    elif corner_val < ref_val - 1e-9:
        return 1.0
    return 0.0


def _dogbone_center(
    corner: tuple[float, float],
    pocket_center: tuple[float, float],
    style: str,
    tool_radius: float,
) -> tuple[float, float]:
    cx, cy = corner
    px, py = pocket_center

    if style == "dogbone":
        dx = _axis_direction(cx, px)
        dy = _axis_direction(cy, py)
        if dx != 0.0 and dy != 0.0:
            return (cx + dx * tool_radius * _SQRT2_INV, cy + dy * tool_radius * _SQRT2_INV)
        return (cx + dx * tool_radius, cy + dy * tool_radius)
    elif style == "t-bone_x":
        dx = _axis_direction(cx, px)
        return (cx + dx * tool_radius, cy)
    elif style == "t-bone_y":
        dy = _axis_direction(cy, py)
        return (cx, cy + dy * tool_radius)
    else:
        raise ValueError(f"Unknown dogbone style: {style}")


def plan_dogbone_passes(
    dogbones: tuple[DogboneInput, ...],
    *,
    accumulator: PassAccumulator,
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in dogbones:
        if entry.tool_diameter_mm is not None:
            tool = pick_tool_by_diameter(tool_db, entry.tool_diameter_mm)
        else:
            parent_tool = accumulator.get_feature_tool(entry.pocket_id)
            if parent_tool is not None:
                tool = parent_tool
            else:
                flat_tools = [t for t in tool_db if t.kind == "flat"]
                if not flat_tools:
                    raise ValueError("No flat tools available in tool_db for dogbone fillet")
                tool = min(flat_tools, key=lambda t: t.diameter)

        record = accumulator.get_record("dogbone", tool)
        setup = record.setup

        depth = entry.depth_mm
        start_depth = entry.start_depth_mm
        if depth <= start_depth:
            continue
        effective_depth = depth - start_depth

        corners = entry.corners
        if not corners:
            continue

        step_over = stepover_for_tool(tool)
        step_down = stepdown_for_tool(tool)

        tool_radius = 0.5 * tool.diameter
        bore_diameter = tool.diameter + 2.0 * entry.overcut_mm
        pocket_center = (
            entry.reference_point if entry.reference_point is not None else _pocket_center_from_corners(corners)
        )

        fillet_centers = []
        for corner_xy in corners:
            fillet_centers.append(_dogbone_center(corner_xy, pocket_center, entry.style, tool_radius))

        if bore_diameter - tool.diameter < 0.01:
            peck = min(step_down, 2.5)
            moves = drill_peck(fillet_centers, setup, depth_mm=effective_depth, peck=peck)
            moves = offset_moves_z(moves, start_depth)
            record.add_moves(moves, increment=len(fillet_centers))
        else:
            for center in fillet_centers:
                moves = pocket_circle_concentric(
                    center,
                    bore_diameter,
                    setup,
                    depth_mm=effective_depth,
                    stepover_mm=step_over,
                    stepdown_mm=step_down,
                    finish=True,
                )
                moves = offset_moves_z(moves, start_depth)
                record.add_moves(moves, increment=1)


def _pocket_center_from_corners(
    corners: tuple[tuple[float, float], ...],
) -> tuple[float, float]:
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


__all__ = [
    "plan_corner_cleanup_passes",
    "plan_dogbone_passes",
    "plan_engrave_passes",
    "plan_hole_passes",
    "plan_pocket_passes",
]
