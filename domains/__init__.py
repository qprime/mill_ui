"""Domain and generator system for math-based 2D region composition.

This module provides the Domain and MultiDomain types that define bounded 2D
regions for CAM operations. Domains support algebraic operations (inset, offset,
subtract, intersect) that derive new regions from existing ones.

Usage:
    from domains import Domain, MultiDomain

    # Create a rectangular domain
    domain = Domain.from_rectangle(width_mm=100, height_mm=50, center=(200, 150))

    # Apply operations
    inset_result = domain.inset(10)  # Returns MultiDomain
    for d in inset_result:
        # Process each resulting domain
        pass

    # Create domain with a hole
    outer = Domain.from_rectangle(100, 100, (50, 50))
    inner = Domain.from_rectangle(40, 40, (50, 50))
    frame = outer.subtract(inner)

Coordinate Transforms:
    from domains import Domain
    from domains.transforms import local_to_sheet, sheet_to_local

    domain = Domain.from_rectangle(100, 100, center=(200, 150), rotation_rad=0.5)

    # Transform from domain-local to sheet space
    sheet_point = local_to_sheet((10, 20), domain)

    # Transform from sheet space to domain-local
    local_point = sheet_to_local(sheet_point, domain)

See Also:
    - docs/domain_generator_design.md for the full architecture spec
    - domains/domain.py for Domain implementation details
    - domains/transforms.py for coordinate transform functions
"""

from domains.domain import (
    Domain,
    MultiDomain,
    Bounds2D,
    Point2D,
    Boundary,
    JoinStyle,
)

from domains.transforms import (
    local_to_sheet,
    sheet_to_local,
    local_to_sheet_batch,
    sheet_to_local_batch,
    transform_boundary,
    compose_transforms,
    get_rotation_between,
    get_translation_between,
)

__all__ = [
    # Domain types
    "Domain",
    "MultiDomain",
    "Bounds2D",
    "Point2D",
    "Boundary",
    "JoinStyle",
    # Transform functions
    "local_to_sheet",
    "sheet_to_local",
    "local_to_sheet_batch",
    "sheet_to_local_batch",
    "transform_boundary",
    "compose_transforms",
    "get_rotation_between",
    "get_translation_between",
]
