from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import MultiDomain

from layout_ast.layout import Item

GeneratorResult = list[Item]


class GeneratorSkipError(ValueError):
    pass


LoopSelection = Literal["outer_only", "inner_only", "all_loops"] | list[int]


@runtime_checkable
class Generator(Protocol):
    def __call__(
        self,
        domain: Domain,
        params: Any,
        *,
        allow_empty: bool = False,
    ) -> GeneratorResult: ...


@dataclass(frozen=True)
class BaseParams:
    pass


def generate_shape_id(prefix: str, index: int = 0, suffix: str = "") -> str:
    parts = ["generated", prefix]
    if suffix:
        parts.append(suffix)
    else:
        parts.append(f"{index:03d}")
    return "_".join(parts)


def validate_domain_for_generation(
    domain: Domain,
    min_area_mm2: float = 0.01,
    *,
    allow_empty: bool = False,
    generator_name: str = "Generator",
) -> bool:
    if domain.area_mm2 < min_area_mm2:
        if allow_empty:
            return False
        raise GeneratorSkipError(
            f"{generator_name}: Domain area {domain.area_mm2:.4f}mm^2 is below minimum {min_area_mm2}mm^2"
        )
    return True


def require_single_inset_domain(
    inset_result: MultiDomain,
    *,
    allow_empty: bool,
    generator_name: str,
    empty_message: str = "",
) -> Domain | None:
    if inset_result.is_empty:
        if allow_empty:
            return None
        raise GeneratorSkipError(empty_message or f"{generator_name}: inset collapsed domain to empty")
    if len(inset_result.domains) != 1:
        if allow_empty:
            return None
        raise GeneratorSkipError(
            f"{generator_name}: inset produced {len(inset_result.domains)} disjoint regions, "
            f"expected exactly 1. Domain may have complex geometry."
        )
    return inset_result.domains[0]


def resolve_minor_spacing(unit: str, minor_spacing_mm: float | None) -> float:
    if unit == "metric":
        return 1.0
    elif unit == "imperial":
        return 25.4 / 16
    else:
        return minor_spacing_mm or 1.0


def resolve_major_spacing(unit: str, major_spacing_mm: float | None) -> float:
    if unit == "metric":
        return 10.0
    elif unit == "imperial":
        return 25.4
    else:
        return major_spacing_mm or 10.0


__all__ = [
    "BaseParams",
    "Generator",
    "GeneratorResult",
    "GeneratorSkipError",
    "LoopSelection",
    "generate_shape_id",
    "require_single_inset_domain",
    "resolve_major_spacing",
    "resolve_minor_spacing",
    "validate_domain_for_generation",
]
