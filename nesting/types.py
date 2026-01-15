
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class PartSpec:

    name: str
    width_mm: float
    height_mm: float
    quantity: int = 1
    template: str | None = None
    template_params: dict[str, Any] | None = None
    allow_rotation: bool = True

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(f"width_mm must be positive, got {self.width_mm}")
        if self.height_mm <= 0:
            raise ValueError(f"height_mm must be positive, got {self.height_mm}")
        if self.quantity < 0:
            raise ValueError(f"quantity must be non-negative, got {self.quantity}")

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm

    @property
    def total_area_mm2(self) -> float:
        return self.area_mm2 * self.quantity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartSpec:
        return cls(**data)


DEFAULT_KERF_MM = 6.35


@dataclass(frozen=True)
class SheetSpec:

    width_mm: float
    height_mm: float
    thickness_mm: float
    margin_mm: float = 10.0
    kerf_mm: float | None = None
    gap_margin_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(f"width_mm must be positive, got {self.width_mm}")
        if self.height_mm <= 0:
            raise ValueError(f"height_mm must be positive, got {self.height_mm}")
        if self.thickness_mm <= 0:
            raise ValueError(f"thickness_mm must be positive, got {self.thickness_mm}")
        if self.margin_mm < 0:
            raise ValueError(f"margin_mm must be non-negative, got {self.margin_mm}")
        if self.gap_margin_mm < 0:
            raise ValueError(f"gap_margin_mm must be non-negative, got {self.gap_margin_mm}")


        if self.kerf_mm is None:
            import warnings
            warnings.warn(
                f"kerf_mm not specified, defaulting to {DEFAULT_KERF_MM}mm (1/4\" endmill). "
                "Set kerf_mm explicitly to suppress this warning.",
                UserWarning,
                stacklevel=2,
            )

            object.__setattr__(self, 'kerf_mm', DEFAULT_KERF_MM)
        elif self.kerf_mm < 0:
            raise ValueError(f"kerf_mm must be non-negative, got {self.kerf_mm}")


        usable_w = self.width_mm - 2 * self.margin_mm
        usable_h = self.height_mm - 2 * self.margin_mm
        if usable_w <= 0 or usable_h <= 0:
            raise ValueError(
                f"Margins ({self.margin_mm}mm) leave no usable area on "
                f"{self.width_mm}x{self.height_mm}mm sheet"
            )

    @property
    def gap_mm(self) -> float:
        return self.kerf_mm + self.gap_margin_mm

    @property
    def usable_width_mm(self) -> float:
        return self.width_mm - 2 * self.margin_mm

    @property
    def usable_height_mm(self) -> float:
        return self.height_mm - 2 * self.margin_mm

    @property
    def usable_area_mm2(self) -> float:
        return self.usable_width_mm * self.usable_height_mm

    @property
    def total_area_mm2(self) -> float:
        return self.width_mm * self.height_mm

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "thickness_mm": self.thickness_mm,
            "margin_mm": self.margin_mm,
            "kerf_mm": self.kerf_mm,
            "gap_margin_mm": self.gap_margin_mm,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SheetSpec:
        return cls(**data)


@dataclass(frozen=True)
class NestedPart:

    part_spec: PartSpec
    x_mm: float
    y_mm: float
    rotated: bool = False
    instance_id: int = 0

    @property
    def effective_width_mm(self) -> float:
        if self.rotated:
            return self.part_spec.height_mm
        return self.part_spec.width_mm

    @property
    def effective_height_mm(self) -> float:
        if self.rotated:
            return self.part_spec.width_mm
        return self.part_spec.height_mm

    @property
    def left_mm(self) -> float:
        return self.x_mm - self.effective_width_mm / 2

    @property
    def right_mm(self) -> float:
        return self.x_mm + self.effective_width_mm / 2

    @property
    def bottom_mm(self) -> float:
        return self.y_mm - self.effective_height_mm / 2

    @property
    def top_mm(self) -> float:
        return self.y_mm + self.effective_height_mm / 2

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.left_mm, self.bottom_mm, self.right_mm, self.top_mm)

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_spec": self.part_spec.to_dict(),
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "rotated": self.rotated,
            "instance_id": self.instance_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NestedPart:
        return cls(
            part_spec=PartSpec.from_dict(data["part_spec"]),
            x_mm=data["x_mm"],
            y_mm=data["y_mm"],
            rotated=data.get("rotated", False),
            instance_id=data.get("instance_id", 0),
        )


@dataclass(frozen=True)
class SheetLayout:

    sheet_spec: SheetSpec
    placements: tuple[NestedPart, ...]
    sheet_index: int = 0

    @property
    def part_count(self) -> int:
        return len(self.placements)

    @property
    def parts_area_mm2(self) -> float:
        return sum(
            p.effective_width_mm * p.effective_height_mm for p in self.placements
        )

    @property
    def utilization(self) -> float:
        if self.sheet_spec.usable_area_mm2 == 0:
            return 0.0
        return self.parts_area_mm2 / self.sheet_spec.usable_area_mm2

    @property
    def utilization_percent(self) -> float:
        return self.utilization * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet_spec": self.sheet_spec.to_dict(),
            "placements": [p.to_dict() for p in self.placements],
            "sheet_index": self.sheet_index,
            "utilization": self.utilization,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SheetLayout:
        return cls(
            sheet_spec=SheetSpec.from_dict(data["sheet_spec"]),
            placements=tuple(NestedPart.from_dict(p) for p in data["placements"]),
            sheet_index=data.get("sheet_index", 0),
        )


@dataclass(frozen=True)
class NestingResult:

    sheets: tuple[SheetLayout, ...]
    unplaced_parts: tuple[PartSpec, ...] = ()

    @property
    def total_sheets(self) -> int:
        return len(self.sheets)

    @property
    def total_parts(self) -> int:
        return sum(sheet.part_count for sheet in self.sheets)

    @property
    def total_parts_area_mm2(self) -> float:
        return sum(sheet.parts_area_mm2 for sheet in self.sheets)

    @property
    def total_sheet_area_mm2(self) -> float:
        return sum(sheet.sheet_spec.usable_area_mm2 for sheet in self.sheets)

    @property
    def overall_utilization(self) -> float:
        if self.total_sheet_area_mm2 == 0:
            return 0.0
        return self.total_parts_area_mm2 / self.total_sheet_area_mm2

    @property
    def overall_utilization_percent(self) -> float:
        return self.overall_utilization * 100

    @property
    def waste_area_mm2(self) -> float:
        return self.total_sheet_area_mm2 - self.total_parts_area_mm2

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheets": [s.to_dict() for s in self.sheets],
            "unplaced_parts": [p.to_dict() for p in self.unplaced_parts],
            "total_sheets": self.total_sheets,
            "total_parts": self.total_parts,
            "overall_utilization": self.overall_utilization,
            "waste_area_mm2": self.waste_area_mm2,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NestingResult:
        return cls(
            sheets=tuple(SheetLayout.from_dict(s) for s in data["sheets"]),
            unplaced_parts=tuple(
                PartSpec.from_dict(p) for p in data.get("unplaced_parts", [])
            ),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> NestingResult:
        return cls.from_dict(json.loads(json_str))
