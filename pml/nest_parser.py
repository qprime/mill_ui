from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

_HOLDING_FIELDS = frozenset({"onion_skin_mm", "tab_count", "tab_height_mm", "tab_width_mm"})


class NestParseError(Exception):
    def __init__(self, message: str, path: str = ""):
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class HoldingSpec:
    onion_skin_mm: float | None = None
    tab_count: int | None = None
    tab_height_mm: float | None = None
    tab_width_mm: float | None = None

    def __post_init__(self) -> None:
        has_onion = self.onion_skin_mm is not None
        has_tabs = self.tab_count is not None or self.tab_height_mm is not None or self.tab_width_mm is not None
        if has_onion and has_tabs:
            raise ValueError("onion_skin and tabs are mutually exclusive")
        if self.onion_skin_mm is not None and self.onion_skin_mm <= 0:
            raise ValueError(f"onion_skin must be positive, got {self.onion_skin_mm}")
        if self.tab_count is not None and self.tab_count < 1:
            raise ValueError(f"tab_count must be >= 1, got {self.tab_count}")
        if self.tab_height_mm is not None and self.tab_height_mm <= 0:
            raise ValueError(f"tab_height must be positive, got {self.tab_height_mm}")
        if self.tab_width_mm is not None and self.tab_width_mm <= 0:
            raise ValueError(f"tab_width must be positive, got {self.tab_width_mm}")
        if has_tabs and self.tab_count is None:
            raise ValueError("tab_count is required when using tabs")
        if has_tabs and self.tab_height_mm is None:
            raise ValueError("tab_height is required when using tabs")

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> HoldingSpec:
        filtered = {k: v for k, v in raw.items() if k in _HOLDING_FIELDS}
        return cls(**filtered)


@dataclass(frozen=True)
class NestPart:
    name: str
    width_mm: float
    height_mm: float
    quantity: int = 1
    template: str | None = None
    template_params: dict[str, Any] = field(default_factory=dict)
    shape: str | None = None
    shape_params: dict[str, Any] = field(default_factory=dict)
    holding: HoldingSpec | None = None


@dataclass(frozen=True)
class NestJob:
    algorithm: str
    sheet_width_mm: float
    sheet_height_mm: float
    sheet_thickness_mm: float
    kerf_mm: float = 6.35
    margin_mm: float = 10.0
    holding: HoldingSpec | None = None
    parts: list[NestPart] = field(default_factory=list)


def nest_job_to_api_params(job: NestJob) -> dict[str, Any]:
    parts = []
    for part in job.parts:
        part_dict: dict[str, Any] = {
            "name": part.name,
            "width_mm": part.width_mm,
            "height_mm": part.height_mm,
            "quantity": part.quantity,
        }
        if part.template:
            part_dict["template"] = part.template
            part_dict["template_params"] = part.template_params
        if part.shape:
            part_dict["shape"] = part.shape
            part_dict["shape_params"] = part.shape_params
        if part.holding is not None:
            part_dict["holding"] = part.holding.to_dict()
        parts.append(part_dict)

    return {
        "parts": parts,
        "sheet_width_mm": job.sheet_width_mm,
        "sheet_height_mm": job.sheet_height_mm,
        "sheet_thickness_mm": job.sheet_thickness_mm,
        "kerf_mm": job.kerf_mm,
        "margin_mm": job.margin_mm,
        "algorithm": job.algorithm,
    }


__all__ = [
    "HoldingSpec",
    "NestJob",
    "NestParseError",
    "NestPart",
    "nest_job_to_api_params",
]
