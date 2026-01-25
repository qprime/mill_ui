
from .types import (
    PartSpec,
    SheetSpec,
    NestedPart,
    SheetLayout,
    NestingResult,
    DEFAULT_KERF_MM,
)
from .guillotine import (
    guillotine_pack,
    FreeRect,
    PlacementResult,
)
from .maxrects import (
    maxrects_pack,
    MaxRectsHeuristic,
)
from .sheet_packer import pack_sheets, PackingAlgorithm
from .template_expander import (
    expand_part_to_items,
    placement_to_items,
)
from .layout_generator import (
    sheet_layout_to_ast,
    nesting_result_to_asts,
    sheet_layout_to_pml,
    nesting_result_to_pml,
)
from .validation import (
    NestingValidationResult,
    validate_sheet_layout,
    validate_nesting_result,
)
from .api import nest_parts, nest_and_generate
from .waste_decomposition import (
    WasteStrategy,
    WasteRect,
    PartBounds,
    compute_waste_rectangles,
)

__all__ = [

    "PartSpec",
    "SheetSpec",
    "NestedPart",
    "SheetLayout",
    "NestingResult",
    "DEFAULT_KERF_MM",

    "guillotine_pack",
    "FreeRect",
    "PlacementResult",

    "maxrects_pack",
    "MaxRectsHeuristic",

    "pack_sheets",
    "PackingAlgorithm",

    "expand_part_to_items",
    "placement_to_items",

    "sheet_layout_to_ast",
    "nesting_result_to_asts",
    "sheet_layout_to_pml",
    "nesting_result_to_pml",

    "NestingValidationResult",
    "validate_sheet_layout",
    "validate_nesting_result",

    "nest_parts",
    "nest_and_generate",

    "WasteStrategy",
    "WasteRect",
    "PartBounds",
    "compute_waste_rectangles",
]
