from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.planner.passes import PassRecord, plan_passes
from cam.planner.passes.tools import ToolSelection, normalize_tool_entries, pick_tool_for_profile
from cam.planner.planner_input import PlannerInput, SurfaceCooling
from config.machine_loader import Endmill, FeedsEntry, build_tool_db, load_machine_tool_db
from core.constants import PROJECT_KERF_MM
from ir.removal_intent import RemovalIntent
from layout_ast.compositional import CompositionalLayoutAST
from layout_ast.layout import LayoutAST, MachiningClearance, mirror_item_about_x
from pml import parse_pml_yaml
from resolution.layout_resolver import requires_machining_clearance, resolve_layout_multi

COMPILATION_CONFIG_KEY = "compilation"
DEFAULT_SAFE_Z_MM = 6.0
PROFILE_CUT_THROUGH_MM = 0.2


@dataclass(frozen=True)
class CompilationContext:
    material: str
    requested_kerf_mm: float
    tools: tuple[ToolSelection, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.requested_kerf_mm) or self.requested_kerf_mm < 0:
            raise ValueError(
                f"CompilationContext: requested kerf must be finite and nonnegative, got {self.requested_kerf_mm}"
            )
        if not self.tools:
            raise ValueError("CompilationContext: tool snapshot must not be empty")
        for tool in self.tools:
            if not math.isfinite(tool.diameter) or tool.diameter <= 0:
                raise ValueError(f"CompilationContext: tool '{tool.name}' diameter must be finite and positive")

    @property
    def profile_diameter_mm(self) -> float | None:
        if not any(tool.kind == "flat" for tool in self.tools):
            return None
        return pick_tool_for_profile(self.tools, kerf_mm=self.requested_kerf_mm).diameter

    def clearance(self) -> MachiningClearance:
        diameter = self.profile_diameter_mm
        if diameter is None:
            raise ValueError("CompilationContext: packing requires an available flat profile cutter")
        return MachiningClearance(diameter)

    def tool_db(self) -> list[dict[str, Any]]:
        return [asdict(tool) for tool in self.tools]

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": 1,
            "material": self.material,
            "requested_kerf_mm": self.requested_kerf_mm,
            "selected_profile_diameter_mm": self.profile_diameter_mm,
            "tools": self.tool_db(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return {**payload, "fingerprint": hashlib.sha256(encoded).hexdigest()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CompilationContext:
        if data.get("version") != 1 or not isinstance(data.get("tools"), list):
            raise ValueError("CompilationContext: missing or unsupported saved tool context; rebuild the source")
        result = cls(
            str(data["material"]), float(data["requested_kerf_mm"]), tuple(normalize_tool_entries(data["tools"]))
        )
        if result.to_dict() != dict(data):
            raise ValueError(
                "CompilationContext: saved tool context fingerprint or selected cutter disagrees; rebuild the source"
            )
        return result


def compilation_context(
    material: str,
    kerf_mm: float,
    *,
    endmills: list[Endmill] | None = None,
    feeds: list[FeedsEntry] | None = None,
    tool_db: Sequence[Mapping[str, Any]] | None = None,
) -> CompilationContext:
    if tool_db is None:
        tool_db = (
            build_tool_db(endmills, feeds, material)
            if endmills is not None and feeds is not None
            else load_machine_tool_db(material)
        )
    return CompilationContext(material, float(kerf_mm), tuple(normalize_tool_entries(tool_db)))


def saved_compilation_context(ast: LayoutAST) -> CompilationContext | None:
    data = ast.config.get(COMPILATION_CONFIG_KEY)
    return CompilationContext.from_dict(data) if data is not None else None


def load_pml_asts(
    source: Path,
    *,
    kerf_mm: float | None = None,
    default_kerf_mm: float = PROJECT_KERF_MM,
    endmills: list[Endmill] | None = None,
    feeds: list[FeedsEntry] | None = None,
    context: CompilationContext | None = None,
) -> list[LayoutAST]:
    parsed = replace(parse_pml_yaml(source.read_text(encoding="utf-8")), source_dir=str(source.parent.resolve()))
    if context is None:
        requested = kerf_mm if kerf_mm is not None else default_kerf_mm
        context = compilation_context(parsed.sheet.material, requested, endmills=endmills, feeds=feeds)
    elif kerf_mm is not None or endmills is not None or feeds is not None:
        raise ValueError("CompilationContext: saved context and tool overrides cannot be supplied together")
    if parsed.sheet.material != context.material:
        raise ValueError(
            f"CompilationContext: material {context.material!r} does not match source {parsed.sheet.material!r}"
        )
    clearance = context.clearance() if requires_machining_clearance(parsed.root) else None
    return resolve_machining_layout(parsed, context, clearance)


def resolve_machining_layout(
    parsed: CompositionalLayoutAST, context: CompilationContext, clearance: MachiningClearance | None
) -> list[LayoutAST]:
    from adapters.ast_to_removal import ast_to_removal_intents
    from cam.planner.passes.merge_shared_edges import ProfileClearanceError
    from validation.toolpath_checks import (
        verify_layout_cutting_clearance,
        verify_passes_avoid_keepouts,
    )

    attempts: list[dict[str, Any]] = []
    for attempt in range(4):
        resolved = resolve_layout_multi(parsed, machining_clearance=clearance)
        auto = any(ast.config.get("layout_gaps") for ast in resolved)
        if not auto:
            return [replace(ast, config={**ast.config, COMPILATION_CONFIG_KEY: context.to_dict()}) for ast in resolved]
        extra_gap = 0.0
        reasons: list[str] = []
        for ast in resolved:
            for face in ("front", "back"):
                if not ast.face_items(face):
                    continue
                face_ast = back_face_ast(ast) if face == "back" else replace(ast, items=ast.face_items("front"))
                face_intents = ast_to_removal_intents(face_ast)
                planner_input = prepare_face_input(
                    face_ast, face_intents, kerf_mm=context.profile_diameter_mm or context.requested_kerf_mm
                )
                try:
                    passes, _, _, errors = plan_face_passes(
                        planner_input,
                        tools=context.tools,
                        machine=Machine(name="default_grbl"),
                        stock=Stock(ast.sheet.width_mm, ast.sheet.height_mm, ast.sheet.thickness_mm),
                        safe_z=ast.sheet.safe_z_mm if ast.sheet.safe_z_mm is not None else DEFAULT_SAFE_Z_MM,
                    )
                    if errors:
                        raise ValueError("Automatic packing preflight: " + "; ".join(errors))
                    collisions = verify_layout_cutting_clearance(passes, planner_input, face_ast, face_intents)
                    if any(not collision.retriable for collision in collisions):
                        raise ValueError("Automatic packing preflight: " + "; ".join(c.message for c in collisions))
                    keepouts = verify_passes_avoid_keepouts(passes, [k.to_dict() for k in planner_input.keepouts])
                    if keepouts.has_violations():
                        raise ValueError("Automatic packing preflight: " + "; ".join(keepouts.format_errors()))
                    extra_gap = max(extra_gap, max((c.extra_gap_mm for c in collisions), default=0))
                    reasons.extend(c.message for c in collisions)
                except ProfileClearanceError as exc:
                    extra_gap = max(extra_gap, exc.extra_gap_mm)
                    reasons.append(str(exc))
        attempts.append(
            {
                "attempt": attempt + 1,
                "gap_margin_mm": clearance.gap_margin_mm if clearance else 0,
                "reasons": sorted(set(reasons)),
            }
        )
        if extra_gap <= 0:
            return [
                replace(
                    ast, config={**ast.config, COMPILATION_CONFIG_KEY: context.to_dict(), "packing_preflight": attempts}
                )
                for ast in resolved
            ]
        if clearance is None:
            raise ValueError("Automatic packing requires a machining clearance context")
        clearance = replace(clearance, gap_margin_mm=clearance.gap_margin_mm + extra_gap + 0.002)
    raise ValueError(
        "Automatic packing failed after four bounded preflight attempts: " + "; ".join(sorted(set(reasons)))
    )


def attach_surface_cooling(planner_input: PlannerInput, ast: LayoutAST) -> PlannerInput:
    surface_map: dict[str, dict[str, Any]] = {}
    for item in ast.items:
        if item.params and "surface_cooling" in item.params:
            surface_map[item.shape_id or ""] = item.params["surface_cooling"]

    if not surface_map:
        return planner_input

    new_pockets = []
    for pocket in planner_input.pockets:
        sc_data = surface_map.get(pocket.id)
        if sc_data is not None:
            cooling = SurfaceCooling(
                stepover_pct=sc_data["stepover_pct"],
                direction=sc_data["direction"],
                cool_every=sc_data["cool_every"],
                cool_dwell_s=sc_data["cool_dwell_s"],
                start_depth_mm=sc_data.get("start_depth_mm", 0.0),
            )
            new_pockets.append(replace(pocket, surface_cooling=cooling))
        else:
            new_pockets.append(pocket)

    return replace(planner_input, pockets=tuple(new_pockets))


def prepare_face_input(
    ast: LayoutAST, intents: Sequence[RemovalIntent], *, kerf_mm: float, warnings: list[str] | None = None
) -> PlannerInput:
    return attach_surface_cooling(
        removal_intents_to_planner_input(list(intents), kerf_width_mm=kerf_mm, warnings=warnings), ast
    )


def plan_face_passes(
    planner_input: PlannerInput, *, tools: Sequence[ToolSelection], machine: Machine, stock: Stock, safe_z: float
) -> tuple[list[PassRecord], dict[str, Any], list[str], list[str]]:
    return plan_passes(
        planner_input,
        config=Config(),
        tool_db=tuple(tools),
        machine=machine,
        stock=stock,
        safe_z=safe_z,
        profile_opts={"cut_through_mm": PROFILE_CUT_THROUGH_MM},
    )


def back_face_ast(ast: LayoutAST) -> LayoutAST:
    return replace(
        ast, items=tuple(mirror_item_about_x(item, ast.sheet.working_height_mm) for item in ast.face_items("back"))
    )
