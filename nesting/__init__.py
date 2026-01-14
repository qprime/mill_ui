"""Nesting module for sheet layout optimization.

This module provides tools for packing multiple parts onto stock sheets
with optimal material utilization.
"""

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
    TEMPLATE_REGISTRY,
    register_template,
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

__all__ = [
    # Types
    "PartSpec",
    "SheetSpec",
    "NestedPart",
    "SheetLayout",
    "NestingResult",
    "DEFAULT_KERF_MM",
    # Guillotine packer
    "guillotine_pack",
    "FreeRect",
    "PlacementResult",
    # MaxRects packer
    "maxrects_pack",
    "MaxRectsHeuristic",
    # Multi-sheet packer
    "pack_sheets",
    "PackingAlgorithm",
    # Template expansion
    "TEMPLATE_REGISTRY",
    "register_template",
    "expand_part_to_items",
    "placement_to_items",
    # Layout generation
    "sheet_layout_to_ast",
    "nesting_result_to_asts",
    "sheet_layout_to_pml",
    "nesting_result_to_pml",
    # Validation
    "NestingValidationResult",
    "validate_sheet_layout",
    "validate_nesting_result",
    # High-level API
    "nest_parts",
    "nest_and_generate",
]
