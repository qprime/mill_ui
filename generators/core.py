
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from domains import Domain

from layout_ast.layout import Item


GeneratorResult = list[Item]


LoopSelection = Literal["outer_only", "inner_only", "all_loops"] | list[int]


@runtime_checkable
class Generator(Protocol):

    def __call__(
        self,
        domain: Domain,
        params: Any,
        *,
        allow_empty: bool = False,
    ) -> GeneratorResult:
        ...


@dataclass(frozen=True)
class BaseParams(ABC):

    @abstractmethod
    def validate(self) -> None:
        ...


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
        raise ValueError(
            f"{generator_name}: Domain area {domain.area_mm2:.4f}mm^2 is below "
            f"minimum {min_area_mm2}mm^2"
        )
    return True


__all__ = [
    "Generator",
    "GeneratorResult",
    "BaseParams",
    "LoopSelection",
    "generate_shape_id",
    "validate_domain_for_generation",
]
