from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shapely.geometry import LineString, Point, box

from cam.moves import CutMove, Move, XYMove
from ir.removal_intent import Bounds2D
from validation.core import InvariantResult, Verdict

if TYPE_CHECKING:
    from cam.planner.passes import PassRecord
    from cam.planner.planner_input import PlannerInput
    from ir.removal_intent import RemovalIntent
    from layout_ast.layout import LayoutAST


@dataclass(frozen=True)
class KeepoutViolation:
    move_index: int
    x: float
    y: float
    keepout_reason: str
    keepout_bounds: Bounds2D


@dataclass(frozen=True)
class ToolpathVerificationResult:
    keepout_violations: tuple[KeepoutViolation, ...]
    rapid_crossings: tuple[KeepoutViolation, ...] = ()
    final_xy: tuple[float | None, float | None] = (None, None)

    def has_violations(self) -> bool:
        return len(self.keepout_violations) > 0

    def format_errors(self) -> list[str]:
        errors = []
        for v in self.keepout_violations:
            errors.append(
                f"Toolpath enters keepout region '{v.keepout_reason}' at "
                f"({v.x:.2f}, {v.y:.2f}). Keepout bounds: "
                f"X[{v.keepout_bounds.x_min:.2f}, {v.keepout_bounds.x_max:.2f}], "
                f"Y[{v.keepout_bounds.y_min:.2f}, {v.keepout_bounds.y_max:.2f}]"
            )
        return errors

    def format_warnings(self, safe_z_mm: float) -> list[str]:
        counts = Counter(v.keepout_reason for v in self.rapid_crossings)
        return [
            f"{count} rapid moves cross keepout '{reason}' at safe Z {safe_z_mm} mm; "
            "confirm the clamp is lower than safe Z"
            for reason, count in counts.items()
        ]

    def to_invariant_result(self) -> InvariantResult:
        n = len(self.keepout_violations)
        return InvariantResult(
            id="KEEPOUT-001",
            category="toolpath",
            artifact="gcode",
            description="Toolpath must not enter keepout regions",
            status=Verdict.FAIL if n > 0 else Verdict.PASS,
            checked=max(n, 1),
            passed=0 if n > 0 else 1,
            failed=n,
            failures=tuple(self.format_errors()),
        )


def _keepout_dict_to_region(keepout: Mapping[str, Any]) -> tuple[Bounds2D, str]:
    bounds = Bounds2D(
        x_min=float(keepout.get("x_min", 0.0)),
        x_max=float(keepout.get("x_max", 0.0)),
        y_min=float(keepout.get("y_min", 0.0)),
        y_max=float(keepout.get("y_max", 0.0)),
    )
    reason = str(keepout.get("reason", "keepout"))
    return bounds, reason


def verify_toolpath_avoids_keepouts(
    moves: Sequence[Move],
    keepouts: Sequence[Mapping[str, Any]],
    tool_radius_mm: float = 0.0,
    *,
    initial_xy: tuple[float | None, float | None] = (None, None),
) -> ToolpathVerificationResult:
    if not keepouts:
        return ToolpathVerificationResult(keepout_violations=())

    keepout_regions = [_keepout_dict_to_region(k) for k in keepouts]

    expanded_regions = []
    for bounds, reason in keepout_regions:
        expanded = box(
            bounds.x_min - tool_radius_mm,
            bounds.y_min - tool_radius_mm,
            bounds.x_max + tool_radius_mm,
            bounds.y_max + tool_radius_mm,
        )
        expanded_regions.append((expanded, bounds, reason))

    violations: list[KeepoutViolation] = []
    rapid_crossings: list[KeepoutViolation] = []
    x, y = initial_xy

    for i, move in enumerate(moves):
        if not isinstance(move, XYMove):
            continue

        next_x = move.x if move.x is not None else x
        next_y = move.y if move.y is not None else y
        if next_x is None or next_y is None:
            if isinstance(move, CutMove):
                raise ValueError(f"Keepout verification: cutting move {i} has unknown XY position")
            x, y = next_x, next_y
            continue
        target = (next_x, next_y)
        segment = Point(target) if x is None or y is None or (x, y) == target else LineString([(x, y), target])

        for expanded, original, reason in expanded_regions:
            if segment.intersects(expanded):
                crossing = segment.intersection(expanded).representative_point()
                collection = violations if isinstance(move, CutMove) else rapid_crossings
                collection.append(
                    KeepoutViolation(
                        move_index=i,
                        x=crossing.x,
                        y=crossing.y,
                        keepout_reason=reason,
                        keepout_bounds=original,
                    )
                )
        x, y = target

    return ToolpathVerificationResult(tuple(violations), tuple(rapid_crossings), (x, y))


def verify_passes_avoid_keepouts(
    passes: Sequence[PassRecord],
    keepouts: Sequence[Mapping[str, Any]],
) -> ToolpathVerificationResult:
    if not keepouts:
        return ToolpathVerificationResult(keepout_violations=())

    all_violations: list[KeepoutViolation] = []
    all_rapid_crossings: list[KeepoutViolation] = []
    xy: tuple[float | None, float | None] = (None, None)

    for p in passes:
        tool_radius = p.setup.tool.diameter / 2.0
        result = verify_toolpath_avoids_keepouts(p.moves, keepouts, tool_radius, initial_xy=xy)
        all_violations.extend(result.keepout_violations)
        all_rapid_crossings.extend(result.rapid_crossings)
        xy = result.final_xy

    return ToolpathVerificationResult(tuple(all_violations), tuple(all_rapid_crossings), xy)


@dataclass(frozen=True)
class PartCollision:
    feature_ids: tuple[str, ...]
    part_id: str
    extra_gap_mm: float
    message: str


def _cutting_segments(
    passes: Sequence[PassRecord],
) -> Iterator[tuple[PassRecord, tuple[str, ...], Point | LineString]]:
    from cam.moves import RetractMove

    for record in passes:
        x: float | None = None
        y: float | None = None
        z = record.setup.safe_z
        range_index = 0
        for index, move in enumerate(record.moves):
            if isinstance(move, RetractMove):
                z = move.z
                continue
            if not isinstance(move, XYMove):
                continue
            next_x = move.x if move.x is not None else x
            next_y = move.y if move.y is not None else y
            next_z = move.z if move.z is not None else z
            while range_index < len(record.move_ranges) and index >= record.move_ranges[range_index][1]:
                range_index += 1
            ids = record.move_ranges[range_index][2] if range_index < len(record.move_ranges) else ()
            if isinstance(move, CutMove) and min(z, next_z) < -1e-9:
                if next_x is None or next_y is None:
                    raise ValueError("Cutter sweep verification: cutting move has unknown XY")
                target = (next_x, next_y)
                segment = Point(target) if x is None or y is None or (x, y) == target else LineString([(x, y), target])
                yield record, ids, segment
            x, y, z = next_x, next_y, next_z


def verify_passes_preserve_parts(
    passes: Sequence[PassRecord],
    planner_input: PlannerInput,
    owners: Mapping[str, str],
) -> tuple[PartCollision, ...]:
    from shapely.strtree import STRtree

    from cam.planner.passes.merge_shared_edges import profile_material_region
    from cam.planner.passes.tools import pick_tool_for_profile

    retained = [
        (p, profile_material_region(p))
        for p in planner_input.profiles
        if p.side == "outside" and p.depth_mm > 0 and p.shape.lower() in {"rect", "polygon", "circle", "roundedrect"}
    ]
    if not retained or not passes:
        return ()
    diameter = pick_tool_for_profile(
        [record.tool_selection for record in passes], kerf_mm=planner_input.kerf_width_mm
    ).diameter
    regions = [
        region.buffer(diameter) if p.tabs is not None or (p.onion_skin_mm or 0) > 0 else region
        for p, region in retained
    ]
    profile_ids = {p.id for p, _ in retained}
    tree = STRtree(regions)
    by_owner = {owners.get(p.id, p.id): region for p, region in retained}
    collisions: dict[tuple[tuple[str, ...], str], PartCollision] = {}
    for record, ids, segment in _cutting_segments(passes):
        radius = record.setup.tool.diameter / 2
        bounds = segment.bounds
        query = box(bounds[0] - radius, bounds[1] - radius, bounds[2] + radius, bounds[3] + radius)
        own_parts = {owners.get(feature_id, feature_id) for feature_id in ids}
        if len(retained) == 1 and not any(feature_id in owners or feature_id in profile_ids for feature_id in ids):
            own_parts.add(owners.get(retained[0][0].id, retained[0][0].id))
        for candidate in tree.query(query):
            profile, _ = retained[int(candidate)]
            part_id = owners.get(profile.id, profile.id)
            if part_id in own_parts or (ids, part_id) in collisions:
                continue
            region = regions[int(candidate)]
            tolerance = 0.002 if profile.tabs is not None else 0.001
            if segment.distance(region) >= radius - tolerance:
                continue
            reach = record.setup.tool.diameter
            for owner in own_parts:
                source = by_owner.get(owner)
                if source is not None:
                    sx0, sy0, sx1, sy1 = source.bounds
                    reach = max(
                        reach,
                        sx0 - bounds[0] + radius,
                        sy0 - bounds[1] + radius,
                        bounds[2] - sx1 + radius,
                        bounds[3] - sy1 + radius,
                    )
            message = (
                f"Cutter sweep for {', '.join(ids) or 'unowned feature'} enters retained part "
                f"'{part_id}' or its protected holding stock; increase part spacing"
            )
            collisions[ids, part_id] = PartCollision(ids, part_id, reach, message)
    return tuple(collisions.values())


def verify_passes_within_working_area(
    passes: Sequence[PassRecord],
    width_mm: float,
    height_mm: float,
    *,
    surface_ids: frozenset[str] = frozenset(),
) -> tuple[PartCollision, ...]:
    collisions: dict[tuple[str, ...], PartCollision] = {}
    for record, ids, segment in _cutting_segments(passes):
        if ids and all(feature_id in surface_ids for feature_id in ids):
            continue
        radius = record.setup.tool.diameter / 2
        x0, y0, x1, y1 = segment.bounds
        overrun = max(radius - x0, radius - y0, x1 + radius - width_mm, y1 + radius - height_mm)
        if overrun > 0.001 and ids not in collisions:
            collisions[ids] = PartCollision(
                ids,
                "working_area",
                overrun,
                f"Cutter sweep for {', '.join(ids) or 'unowned feature'} exceeds working area by {overrun:.6f}mm",
            )
    return tuple(collisions.values())


def verify_layout_cutting_clearance(
    passes: Sequence[PassRecord],
    planner_input: PlannerInput,
    ast: LayoutAST,
    intents: Sequence[RemovalIntent],
) -> tuple[PartCollision, ...]:
    owners = {
        (intent.original_id if intent.original_id is not None else intent.region_id): intent.part_id
        for intent in intents
        if intent.part_id is not None
    }
    collisions = verify_passes_preserve_parts(passes, planner_input, owners)
    return collisions + verify_passes_within_working_area(
        passes,
        ast.sheet.working_width_mm,
        ast.sheet.working_height_mm,
        surface_ids=frozenset(
            item.shape_id
            for item in ast.items
            if item.shape_id is not None and item.feature is not None and item.feature.type == "surface"
        ),
    )
