from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    root: Path
    tests: List[Path]


TOP_LEVEL_MODULES = (
    "vitals",
    "cortex",
    "continuum",
    "interfaces",
    "services",
    "skills",
    "memories",
    "tools",
)


def _collect_tests_for(module_dir: Path) -> List[Path]:
    tests: List[Path] = []
    # Prefer co-located tests directory
    co_located = module_dir / "tests"
    if co_located.is_dir():
        tests.append(co_located)
    # Also include any nested tests/ directories
    for p in module_dir.rglob("tests"):
        if p.is_dir() and p != co_located:
            tests.append(p)
    # Back-compat: existing tests under vitals/unit
    if module_dir.name == "vitals":
        legacy = module_dir / "unit"
        if legacy.is_dir():
            tests.append(legacy)
    # Always include the module root to allow pytest discovery of test_*.py anywhere under it
    tests.append(module_dir)
    return tests


def discover_modules(root: Path | None = None) -> List[ModuleSpec]:
    root = root or Path(__file__).resolve().parent.parent
    specs: List[ModuleSpec] = []
    for name in TOP_LEVEL_MODULES:
        module_dir = root / name
        if not module_dir.is_dir():
            continue
        tests = _collect_tests_for(module_dir)
        specs.append(ModuleSpec(name=name, root=module_dir, tests=tests))
    return specs


def resolve_modules(selected: Iterable[str] | None = None) -> List[ModuleSpec]:
    specs = discover_modules()
    if not selected:
        return specs
    sel = {s.strip() for s in selected}
    return [s for s in specs if s.name in sel]
