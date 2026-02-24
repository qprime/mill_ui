from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class NestParseError(Exception):
    def __init__(self, message: str, path: str = ""):
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class NestPart:
    name: str
    width_mm: float
    height_mm: float
    quantity: int = 1
    template: str | None = None
    template_params: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class NestJob:
    algorithm: str
    sheet_width_mm: float
    sheet_height_mm: float
    sheet_thickness_mm: float
    kerf_mm: float = 6.35
    margin_mm: float = 10.0
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
    "NestJob",
    "NestParseError",
    "NestPart",
    "nest_job_to_api_params",
]
