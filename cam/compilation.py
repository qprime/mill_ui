from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.planner.passes import PassRecord, plan_passes
from cam.planner.passes.tools import (
    ToolCatalog,
    ToolSelection,
    normalize_tool_entries,
    pick_tool_for_profile,
    tools_for_role,
)
from cam.planner.planner_input import PlannerInput, SurfaceCooling
from config.machine_loader import (
    Endmill,
    FeedsEntry,
    MachineConfig,
    build_tool_db,
    endmill_geometry,
    get_machines_dir,
    load_endmills,
    load_machine_by_name,
)
from ir.removal_intent import RemovalIntent
from layout_ast.compositional import CompositionalLayoutAST, ProfileGen
from layout_ast.layout import (
    MACHINING_ROLES,
    Feature,
    LayoutAST,
    MachiningClearance,
    MachiningSpec,
    mirror_item_about_x,
)
from pml import parse_pml_yaml
from resolution.layout_resolver import requires_machining_clearance, resolve_layout_multi

PROFILE_CUT_THROUGH_MM = 0.2


def default_machine_name(*, recipe: bool = False) -> str:
    config = YAML(typ="safe").load((get_machines_dir() / "defaults.yml").read_text())
    return str(config["recipe_machine" if recipe else "machine"])


@dataclass(frozen=True)
class CompilationContext:
    material: str
    requested_kerf_mm: float | None
    tools: Sequence[ToolSelection]
    machine_config: MachineConfig
    preset: str
    profile_reach_mm: float = 0.0

    @property
    def profile_diameter_mm(self) -> float | None:
        if (
            isinstance(self.tools, ToolCatalog)
            and not self.tools.assignments.get("profile")
            and not self.tools.machining.tools.get("profile")
        ):
            return None
        return self.profile_tool().diameter

    def profile_tool(self) -> ToolSelection:
        return pick_tool_for_profile(
            tools_for_role(self.tools, "profile", depth_mm=self.profile_reach_mm),
            kerf_mm=self.requested_kerf_mm,
        )

    def clearance(self) -> MachiningClearance:
        diameter = self.profile_diameter_mm
        if diameter is None:
            raise ValueError(
                f"Machine {self.machine_config.machine.name!r}, preset {self.preset!r}, material {self.material!r}, role profile: packing requires a configured flat profile cutter"
            )
        return MachiningClearance(diameter)

    def machine(self) -> Machine:
        caps = self.machine_config.capabilities
        control = self.machine_config.controller
        return Machine(
            name=self.machine_config.machine.name,
            max_feed_xy=caps.get("max_feed_xy", math.inf),
            max_feed_z=caps.get("max_feed_z", math.inf),
            rapid_z=caps.get("rapid_z", 1000),
            work_coord_system=str(control.get("work_coord_system", "G54")),
            spindle_dwell_s=float(control.get("spindle_dwell_s", 5)),
            preamble_codes=tuple(control.get("preamble_codes", ())),
        )

    def setup_summary(self) -> dict[str, Any]:
        return {
            "machine": self.machine_config.machine.name,
            "preset": self.preset,
            "material": self.material,
            "requested_kerf_mm": self.requested_kerf_mm,
            "selected_profile_diameter_mm": self.profile_diameter_mm,
            "selected_profile_tool": self.profile_tool().name if self.profile_diameter_mm is not None else None,
            "job_overrides": {
                "tools": dict(self.tools.machining.tools),
                "feeds": {key: value for key, value in asdict(self.tools.machining.feeds).items() if value is not None}
                if self.tools.machining.feeds
                else {},
            }
            if isinstance(self.tools, ToolCatalog)
            else {},
        }


def _preset_assignments(material_data: dict[str, Any], label: str) -> dict[str, tuple[str, ...]]:
    assignments = {}
    for role, names in material_data.get("roles", {}).items():
        if role not in MACHINING_ROLES:
            raise ValueError(f"{label}: unknown role {role!r}")
        if isinstance(names, str):
            names = [names]
        if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
            raise ValueError(f"{label}, role {role}: expected an ordered list of tool names")
        assignments[role] = tuple(names)
    return assignments


def _preset_catalog(
    machine: MachineConfig,
    material: str,
    machining: MachiningSpec,
    endmills: list[Endmill] | None,
    preset_path: Path | None,
) -> tuple[ToolCatalog, str]:
    preset = machine.cutting_preset
    if preset is None and preset_path is None:
        raise ValueError(f"Machine {machine.machine.name!r}: configure cutting_preset before machining")
    path = preset_path or get_machines_dir() / "cutting_presets" / f"{preset}.yml"
    data = YAML(typ="safe").load(path.read_text())
    label = f"machine {machine.machine.name!r}, preset {str(path)!r}, material {material!r}"
    if not isinstance(data, dict) or set(data) - {"name", "materials"}:
        raise ValueError(f"{label}: expected name/materials cutting preset")
    material_data = data.get("materials", {}).get(material.lower())
    if material_data is None:
        raise ValueError(
            f"{label}: unsupported material; configure explicit roles and cutting parameters for this machine"
        )
    if set(material_data) - {"roles", "parameters"}:
        raise ValueError(f"{label}: unknown material configuration keys")
    inventory = endmills if endmills is not None else load_endmills(get_machines_dir() / "endmills.yml")
    by_name = {em.name: em for em in inventory}
    if len(by_name) != len(inventory):
        raise ValueError(f"{label}: duplicate tool identities in library")
    assignments = _preset_assignments(material_data, label)
    parameters: dict[str, dict[str, ToolSelection]] = {}
    for role, combinations in material_data.get("parameters", {}).items():
        parameters[role] = {}
        for name, values in combinations.items():
            em = by_name.get(name)
            if em is None:
                raise ValueError(f"{label}, role {role}, cutter {name!r}: unknown tool reference")
            required = {"rpm", "feed_xy", "feed_z", "depth_per_pass", "stepover_percent"}
            if set(values) != required:
                raise ValueError(
                    f"{label}, role {role}, cutter {name!r}: cutting parameters require exactly {sorted(required)}"
                )
            limits = tuple((key, val) for key, val in machine.capabilities.items() if key != "rapid_z")
            geometry = endmill_geometry(em)
            try:
                normalized = normalize_tool_entries([{**geometry, **values}])[0]
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{label}, role {role}, cutter {name!r}: {exc}") from exc
            parameters[role][name] = replace(
                normalized,
                limits=limits,
                shank_diameter_mm=em.shank_diameter_mm,
                context_label=f"{label}, role {role}",
            )
    entries = tuple({t.name: t for combinations in parameters.values() for t in combinations.values()}.values())
    catalog = ToolCatalog(entries, parameters, assignments, machining, label, tuple(by_name))
    for role, name in machining.tools.items():
        catalog.for_role(role, name)
    return catalog, str(path if preset_path is not None else preset)


def compilation_context(
    material: str,
    kerf_mm: float | None = None,
    *,
    endmills: list[Endmill] | None = None,
    feeds: list[FeedsEntry] | None = None,
    tool_db: Sequence[Mapping[str, Any]] | None = None,
    machine_config: MachineConfig | None = None,
    machining: MachiningSpec | None = None,
    preset_path: Path | None = None,
    profile_reach_mm: float = 0.0,
) -> CompilationContext:
    machine = machine_config or load_machine_by_name(default_machine_name())
    spec = machining or MachiningSpec()
    if kerf_mm is not None and (not math.isfinite(kerf_mm) or kerf_mm <= 0):
        raise ValueError(f"Profile kerf constraint must be finite and positive, got {kerf_mm}")
    if tool_db is not None or feeds is not None:
        legacy_feeds = tool_db is None
        if tool_db is None:
            if endmills is None:
                raise ValueError("Explicit feeds require an explicit endmill library")
            tool_db = build_tool_db(endmills, feeds or [], material)
        entries = tuple(normalize_tool_entries(tool_db))
        label = f"machine {machine.machine.name!r}, explicit cutting inputs, material {material!r}"
        if len({tool.name for tool in entries}) != len(entries):
            raise ValueError(f"{label}: duplicate cutter identities")
        parameters = {
            role: {
                t.name: replace(t, limits=tuple(machine.capabilities.items()), context_label=f"{label}, role {role}")
                for t in entries
            }
            for role in ("profile", "pocket", "hole", "engrave", "vcarve", "surface", "roundover", "specialty")
        }
        assignments = {
            role: tuple(t.name for t in entries if t.kind in kinds)
            for role, kinds in {
                "profile": {"flat"},
                "pocket": {"flat"},
                "hole": {"flat"},
                "engrave": {"ball", "v"},
                "vcarve": {"v"},
                "surface": {"flat"},
                "roundover": {"roundover"},
                "specialty": {"flat", "ball", "v", "roundover"},
            }.items()
        }
        if legacy_feeds:
            assignments = {
                role: names if len(names) == 1 or role == "specialty" else () for role, names in assignments.items()
            }
        tools: Sequence[ToolSelection] = ToolCatalog(
            entries,
            parameters,
            assignments,
            spec,
            f"machine {machine.machine.name!r}, explicit cutting inputs, material {material!r}",
            tuple(em.name for em in endmills) if endmills is not None else tuple(t.name for t in entries),
        )
        preset = "explicit cutting inputs"
    else:
        tools, preset = _preset_catalog(machine, material, spec, endmills, preset_path)
    return CompilationContext(material, kerf_mm, tools, machine, preset, profile_reach_mm)


def profile_declarations(value: Any) -> tuple[Feature | ProfileGen, ...]:
    if isinstance(value, (Feature, ProfileGen)):
        return (value,) if isinstance(value, ProfileGen) or value.type == "profile" else ()
    children: Iterable[Any]
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, (tuple, list)):
        children = value
    elif is_dataclass(value) and not isinstance(value, type):
        children = (getattr(value, f.name) for f in fields(value))
    else:
        return ()
    return tuple(profile for child in children for profile in profile_declarations(child))


def profile_required_reach(root: Any, thickness_mm: float, *, packing: bool = False) -> float:
    depths = [thickness_mm] if packing else []
    for profile in profile_declarations(root):
        if isinstance(profile, ProfileGen):
            depths.append(thickness_mm if profile.depth == "through" else float(profile.depth))
        else:
            depths.append(thickness_mm if profile.is_through else profile.depth_mm)
    return max(depths) + PROFILE_CUT_THROUGH_MM if depths else 0.0


def profile_machining_spec(spec: MachiningSpec, root: Any) -> MachiningSpec:
    overrides = {profile.tool_name for profile in profile_declarations(root) if profile.tool_name}
    if len(overrides) > 1:
        raise ValueError(
            f"Conflicting operation-level profile tools on one sheet/job: {sorted(overrides)}; use one profile cutter per sheet"
        )
    if overrides:
        return replace(spec, tools={**spec.tools, "profile": next(iter(overrides))})
    return spec


def load_pml_asts(
    source: Path,
    *,
    kerf_mm: float | None = None,
    endmills: list[Endmill] | None = None,
    feeds: list[FeedsEntry] | None = None,
    machine_config: MachineConfig | None = None,
    preset_path: Path | None = None,
) -> tuple[list[LayoutAST], CompilationContext]:
    parsed = replace(parse_pml_yaml(source.read_text(encoding="utf-8")), source_dir=str(source.parent.resolve()))
    spec = profile_machining_spec(parsed.machining, parsed.root)
    context = compilation_context(
        parsed.sheet.material,
        kerf_mm,
        endmills=endmills,
        feeds=feeds,
        machine_config=machine_config,
        machining=spec,
        preset_path=preset_path,
        profile_reach_mm=profile_required_reach(
            parsed.root, parsed.sheet.thickness_mm, packing=requires_machining_clearance(parsed.root)
        ),
    )
    clearance = context.clearance() if requires_machining_clearance(parsed.root) else None
    return resolve_machining_layout(parsed, context, clearance), context


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
            return resolved
        extra_gap = 0.0
        reasons: list[str] = []
        for ast in resolved:
            for face in ("front", "back"):
                if not ast.face_items(face):
                    continue
                face_ast = back_face_ast(ast) if face == "back" else replace(ast, items=ast.face_items("front"))
                face_intents = ast_to_removal_intents(face_ast)
                planner_input = prepare_face_input(
                    face_ast, face_intents, kerf_mm=context.clearance().profile_diameter_mm
                )
                try:
                    passes, _, _, errors = plan_face_passes(
                        planner_input,
                        tools=context.tools,
                        machine=context.machine(),
                        stock=Stock(ast.sheet.width_mm, ast.sheet.height_mm, ast.sheet.thickness_mm),
                        safe_z=ast.sheet.safe_z_mm
                        if ast.sheet.safe_z_mm is not None
                        else context.machine_config.defaults.safe_z_mm,
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
            return [replace(ast, config={**ast.config, "packing_preflight": attempts}) for ast in resolved]
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
        tool_db=tools,
        machine=machine,
        stock=stock,
        safe_z=safe_z,
        profile_opts={"cut_through_mm": PROFILE_CUT_THROUGH_MM},
    )


def back_face_ast(ast: LayoutAST) -> LayoutAST:
    return replace(
        ast, items=tuple(mirror_item_about_x(item, ast.sheet.working_height_mm) for item in ast.face_items("back"))
    )
