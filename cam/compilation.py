from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from cam.planner.passes.tools import ToolSelection, normalize_tool_entries, pick_tool_for_profile
from config.machine_loader import Endmill, FeedsEntry, build_tool_db, load_machine_tool_db
from core.constants import PROJECT_KERF_MM
from layout_ast.layout import LayoutAST, MachiningClearance
from pml import parse_pml_yaml
from resolution.layout_resolver import requires_machining_clearance, resolve_layout_multi

COMPILATION_CONFIG_KEY = "compilation"


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
    return [
        replace(ast, config={**ast.config, COMPILATION_CONFIG_KEY: context.to_dict()})
        for ast in resolve_layout_multi(parsed, machining_clearance=clearance)
    ]
