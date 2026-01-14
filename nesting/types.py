"""Data structures for sheet nesting optimization.

These dataclasses define the input/output format for the nesting system.
All are frozen (immutable) for safety and hashability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class PartSpec:
    """Specification for a part to be nested.

    Attributes:
        name: Human-readable identifier for the part
        width_mm: Bounding box width in millimeters
        height_mm: Bounding box height in millimeters
        quantity: Number of this part to cut
        template: Optional template name (e.g., "Shaker") for expansion
        template_params: Parameters to pass to the template
        allow_rotation: Whether 90-degree rotation is permitted
    """

    name: str
    width_mm: float
    height_mm: float
    quantity: int = 1
    template: str | None = None
    template_params: dict[str, Any] | None = None
    allow_rotation: bool = True

    def __post_init__(self) -> None:
        """Validate part specification."""
        if self.width_mm <= 0:
            raise ValueError(f"width_mm must be positive, got {self.width_mm}")
        if self.height_mm <= 0:
            raise ValueError(f"height_mm must be positive, got {self.height_mm}")
        if self.quantity < 0:
            raise ValueError(f"quantity must be non-negative, got {self.quantity}")

    @property
    def area_mm2(self) -> float:
        """Bounding box area in square millimeters."""
        return self.width_mm * self.height_mm

    @property
    def total_area_mm2(self) -> float:
        """Total area for all instances (area * quantity)."""
        return self.area_mm2 * self.quantity

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartSpec:
        """Create from dictionary."""
        return cls(**data)


# Default kerf width (1/4" endmill)
DEFAULT_KERF_MM = 6.35


@dataclass(frozen=True)
class SheetSpec:
    """Specification for stock sheets.

    Attributes:
        width_mm: Sheet width in millimeters
        height_mm: Sheet height in millimeters
        thickness_mm: Material thickness in millimeters
        margin_mm: No-cut zone on all edges for workholding
        kerf_mm: Cutter diameter/kerf width (should come from PML/tooling config)
        gap_margin_mm: Extra margin beyond kerf for part spacing (default: 0)
    """

    width_mm: float
    height_mm: float
    thickness_mm: float
    margin_mm: float = 10.0
    kerf_mm: float | None = None  # None triggers warning and default
    gap_margin_mm: float = 0.0

    def __post_init__(self) -> None:
        """Validate sheet specification."""
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

        # Handle kerf_mm default with warning
        if self.kerf_mm is None:
            import warnings
            warnings.warn(
                f"kerf_mm not specified, defaulting to {DEFAULT_KERF_MM}mm (1/4\" endmill). "
                "Set kerf_mm explicitly to suppress this warning.",
                UserWarning,
                stacklevel=2,
            )
            # Use object.__setattr__ to bypass frozen
            object.__setattr__(self, 'kerf_mm', DEFAULT_KERF_MM)
        elif self.kerf_mm < 0:
            raise ValueError(f"kerf_mm must be non-negative, got {self.kerf_mm}")

        # Ensure usable area is positive (margins don't consume entire sheet)
        usable_w = self.width_mm - 2 * self.margin_mm
        usable_h = self.height_mm - 2 * self.margin_mm
        if usable_w <= 0 or usable_h <= 0:
            raise ValueError(
                f"Margins ({self.margin_mm}mm) leave no usable area on "
                f"{self.width_mm}x{self.height_mm}mm sheet"
            )

    @property
    def gap_mm(self) -> float:
        """Total gap between parts (kerf + margin)."""
        return self.kerf_mm + self.gap_margin_mm

    @property
    def usable_width_mm(self) -> float:
        """Width available for parts after margins."""
        return self.width_mm - 2 * self.margin_mm

    @property
    def usable_height_mm(self) -> float:
        """Height available for parts after margins."""
        return self.height_mm - 2 * self.margin_mm

    @property
    def usable_area_mm2(self) -> float:
        """Area available for parts after margins."""
        return self.usable_width_mm * self.usable_height_mm

    @property
    def total_area_mm2(self) -> float:
        """Total sheet area."""
        return self.width_mm * self.height_mm

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        """Create from dictionary."""
        return cls(**data)


@dataclass(frozen=True)
class NestedPart:
    """A part placed on a sheet during nesting.

    Named NestedPart (not Placement) to avoid collision with
    layout_ast.layout.Placement which has different semantics.

    Coordinates are center-based to match LayoutAST conventions.

    Attributes:
        part_spec: The part specification being placed
        x_mm: Center X position on the sheet
        y_mm: Center Y position on the sheet
        rotated: Whether the part is rotated 90 degrees
        instance_id: Which instance of this part (0-indexed)
    """

    part_spec: PartSpec
    x_mm: float
    y_mm: float
    rotated: bool = False
    instance_id: int = 0

    @property
    def effective_width_mm(self) -> float:
        """Width after rotation."""
        if self.rotated:
            return self.part_spec.height_mm
        return self.part_spec.width_mm

    @property
    def effective_height_mm(self) -> float:
        """Height after rotation."""
        if self.rotated:
            return self.part_spec.width_mm
        return self.part_spec.height_mm

    @property
    def left_mm(self) -> float:
        """Left edge X coordinate."""
        return self.x_mm - self.effective_width_mm / 2

    @property
    def right_mm(self) -> float:
        """Right edge X coordinate."""
        return self.x_mm + self.effective_width_mm / 2

    @property
    def bottom_mm(self) -> float:
        """Bottom edge Y coordinate."""
        return self.y_mm - self.effective_height_mm / 2

    @property
    def top_mm(self) -> float:
        """Top edge Y coordinate."""
        return self.y_mm + self.effective_height_mm / 2

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Bounding box as (left, bottom, right, top)."""
        return (self.left_mm, self.bottom_mm, self.right_mm, self.top_mm)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "part_spec": self.part_spec.to_dict(),
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "rotated": self.rotated,
            "instance_id": self.instance_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NestedPart:
        """Create from dictionary."""
        return cls(
            part_spec=PartSpec.from_dict(data["part_spec"]),
            x_mm=data["x_mm"],
            y_mm=data["y_mm"],
            rotated=data.get("rotated", False),
            instance_id=data.get("instance_id", 0),
        )


@dataclass(frozen=True)
class SheetLayout:
    """Complete layout for one sheet.

    Attributes:
        sheet_spec: The sheet being used
        placements: All parts placed on this sheet (NestedPart instances)
        sheet_index: 0-based index in multi-sheet job
    """

    sheet_spec: SheetSpec
    placements: tuple[NestedPart, ...]
    sheet_index: int = 0

    @property
    def part_count(self) -> int:
        """Number of parts on this sheet."""
        return len(self.placements)

    @property
    def parts_area_mm2(self) -> float:
        """Total area of all placed parts."""
        return sum(
            p.effective_width_mm * p.effective_height_mm for p in self.placements
        )

    @property
    def utilization(self) -> float:
        """Material utilization ratio (0.0 to 1.0)."""
        if self.sheet_spec.usable_area_mm2 == 0:
            return 0.0
        return self.parts_area_mm2 / self.sheet_spec.usable_area_mm2

    @property
    def utilization_percent(self) -> float:
        """Material utilization as percentage."""
        return self.utilization * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sheet_spec": self.sheet_spec.to_dict(),
            "placements": [p.to_dict() for p in self.placements],
            "sheet_index": self.sheet_index,
            "utilization": self.utilization,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SheetLayout:
        """Create from dictionary."""
        return cls(
            sheet_spec=SheetSpec.from_dict(data["sheet_spec"]),
            placements=tuple(NestedPart.from_dict(p) for p in data["placements"]),
            sheet_index=data.get("sheet_index", 0),
        )


@dataclass(frozen=True)
class NestingResult:
    """Complete nesting solution across multiple sheets.

    Attributes:
        sheets: All sheet layouts in the solution
        unplaced_parts: Parts that could not be placed (too large, etc.)
    """

    sheets: tuple[SheetLayout, ...]
    unplaced_parts: tuple[PartSpec, ...] = ()

    @property
    def total_sheets(self) -> int:
        """Number of sheets in the solution."""
        return len(self.sheets)

    @property
    def total_parts(self) -> int:
        """Total number of parts placed."""
        return sum(sheet.part_count for sheet in self.sheets)

    @property
    def total_parts_area_mm2(self) -> float:
        """Total area of all placed parts."""
        return sum(sheet.parts_area_mm2 for sheet in self.sheets)

    @property
    def total_sheet_area_mm2(self) -> float:
        """Total usable area across all sheets."""
        return sum(sheet.sheet_spec.usable_area_mm2 for sheet in self.sheets)

    @property
    def overall_utilization(self) -> float:
        """Overall material utilization ratio."""
        if self.total_sheet_area_mm2 == 0:
            return 0.0
        return self.total_parts_area_mm2 / self.total_sheet_area_mm2

    @property
    def overall_utilization_percent(self) -> float:
        """Overall utilization as percentage."""
        return self.overall_utilization * 100

    @property
    def waste_area_mm2(self) -> float:
        """Total waste area across all sheets."""
        return self.total_sheet_area_mm2 - self.total_parts_area_mm2

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        """Create from dictionary."""
        return cls(
            sheets=tuple(SheetLayout.from_dict(s) for s in data["sheets"]),
            unplaced_parts=tuple(
                PartSpec.from_dict(p) for p in data.get("unplaced_parts", [])
            ),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> NestingResult:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
