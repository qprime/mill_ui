from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from pml.nest_parser import HoldingSpec


@dataclass(frozen=True)
class FreeRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height

    def can_fit(self, part_w: float, part_h: float, gap: float = 0.0) -> bool:
        needed_w = part_w + gap
        needed_h = part_h + gap
        return self.width >= needed_w and self.height >= needed_h

    def can_fit_rotated(self, part_w: float, part_h: float, gap: float = 0.0) -> bool:
        return self.can_fit(part_h, part_w, gap)

    def intersects(self, other: FreeRect) -> bool:
        return not (self.right <= other.x or other.right <= self.x or self.top <= other.y or other.top <= self.y)

    def contains(self, other: FreeRect) -> bool:
        return self.x <= other.x and self.y <= other.y and self.right >= other.right and self.top >= other.top


@dataclass(frozen=True)
class PlacementResult:
    x: float
    y: float
    rotated: bool
    metadata: Any


@dataclass(frozen=True)
class WasteRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


def _shoelace_area(points: tuple[tuple[float, float], ...]) -> float:
    n = len(points)
    area = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2


@dataclass(frozen=True)
class PartSpec:
    name: str
    width_mm: float
    height_mm: float
    quantity: int = 1
    template: str | None = None
    template_params: dict[str, Any] | None = None
    allow_rotation: bool = True
    geometry_points: tuple[tuple[float, float], ...] | None = None
    shape: str | None = None
    shape_params: dict[str, Any] | None = None
    holding: HoldingSpec | None = None

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(f"width_mm must be positive, got {self.width_mm}")
        if self.height_mm <= 0:
            raise ValueError(f"height_mm must be positive, got {self.height_mm}")
        if self.quantity < 0:
            raise ValueError(f"quantity must be non-negative, got {self.quantity}")

    @property
    def area_mm2(self) -> float:
        import math

        shape = self.shape or "Rect"
        if shape == "Circle":
            diameter = min(self.width_mm, self.height_mm)
            return math.pi / 4 * diameter * diameter
        if shape in ("Polygon", "Triangle") and self.geometry_points:
            return _shoelace_area(self.geometry_points)
        return self.width_mm * self.height_mm

    @property
    def total_area_mm2(self) -> float:
        return self.area_mm2 * self.quantity

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("geometry_points"):
            d["geometry_points"] = [list(p) for p in d["geometry_points"]]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartSpec:
        data = dict(data)
        if data.get("geometry_points"):
            data["geometry_points"] = tuple(tuple(p) for p in data["geometry_points"])
        sp = data.get("shape_params")
        if sp and "corners" in sp:
            data["shape_params"] = {**sp, "corners": tuple(sorted(sp["corners"]))}
        holding = data.get("holding")
        if isinstance(holding, dict):
            data["holding"] = HoldingSpec.from_dict(holding)
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
                f'kerf_mm not specified, defaulting to {DEFAULT_KERF_MM}mm (1/4" endmill). '
                "Set kerf_mm explicitly to suppress this warning.",
                UserWarning,
                stacklevel=2,
            )

            object.__setattr__(self, "kerf_mm", DEFAULT_KERF_MM)
        elif self.kerf_mm < 0:
            raise ValueError(f"kerf_mm must be non-negative, got {self.kerf_mm}")

        usable_w = self.width_mm - 2 * self.margin_mm
        usable_h = self.height_mm - 2 * self.margin_mm
        if usable_w <= 0 or usable_h <= 0:
            raise ValueError(
                f"Margins ({self.margin_mm}mm) leave no usable area on {self.width_mm}x{self.height_mm}mm sheet"
            )

    @property
    def gap_mm(self) -> float:
        if self.kerf_mm is None:
            raise ValueError("kerf_mm must be set before computing gap_mm")
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

    def get_geometry_points(self) -> tuple[tuple[float, float], ...]:
        if self.part_spec.geometry_points:
            points = []
            for px, py in self.part_spec.geometry_points:
                if self.rotated:
                    rx, ry = -py, px
                else:
                    rx, ry = px, py
                points.append((self.x_mm + rx, self.y_mm + ry))
            return tuple(points)
        half_w = self.effective_width_mm / 2
        half_h = self.effective_height_mm / 2
        return (
            (self.x_mm - half_w, self.y_mm - half_h),
            (self.x_mm + half_w, self.y_mm - half_h),
            (self.x_mm + half_w, self.y_mm + half_h),
            (self.x_mm - half_w, self.y_mm + half_h),
        )

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
        return sum(p.part_spec.area_mm2 for p in self.placements)

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
            unplaced_parts=tuple(PartSpec.from_dict(p) for p in data.get("unplaced_parts", [])),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> NestingResult:
        return cls.from_dict(json.loads(json_str))
