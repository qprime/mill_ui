"""Flat pocket area generator.

A flat pocket removes material uniformly within the domain boundary,
creating a recessed area at the specified depth. This is the simplest
area generator and serves as the foundation for more complex patterns.

Usage:
    from domains import Domain
    from generators.area.flat import flat_pocket_generator
    from generators.base import FlatPocketParams

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = FlatPocketParams(depth_mm=6.0)
    items = flat_pocket_generator(domain, params)

    # Items can then be added to a LayoutAST
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    FlatPocketParams,
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def flat_pocket_generator(
    domain: Domain,
    params: FlatPocketParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "pocket",
) -> GeneratorResult:
    """Generate a flat pocket item that fills the domain interior.

    The pocket is created as a Polygon item matching the domain's outer boundary.
    If the domain has inner boundaries (holes), they become keepout regions that
    the CAM planner will respect.

    Args:
        domain: The domain defining the pocket region
        params: Pocket parameters (depth, allowance)
        allow_empty: If True, return empty list instead of raising when
            the domain is too small after applying allowance
        shape_id_prefix: Prefix for generated shape IDs

    Returns:
        List containing one Polygon Item with pocket feature, or empty list
        if allow_empty=True and domain is unsuitable

    Raises:
        ValueError: If params are invalid or domain too small (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(100, 50, center=(50, 25))
        >>> params = FlatPocketParams(depth_mm=6.0)
        >>> items = flat_pocket_generator(domain, params)
        >>> len(items)
        1
        >>> items[0].feature.type
        'pocket'
    """
    # Validate parameters
    params.validate()

    # Apply allowance if specified (contracts the domain)
    if params.allowance_mm > 0:
        inset_result = domain.inset(params.allowance_mm)
        if inset_result.is_empty:
            if allow_empty:
                return []
            raise ValueError(
                f"FlatPocketGenerator: allowance {params.allowance_mm}mm exceeds domain size. "
                f"Domain bounds: {domain.bounds.width}mm x {domain.bounds.height}mm"
            )
        # Use first domain from inset result (typically single for convex shapes)
        effective_domain = inset_result.domains[0]
    else:
        effective_domain = domain

    # Validate domain is large enough
    if not validate_domain_for_generation(
        effective_domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="FlatPocketGenerator",
    ):
        return []

    cx, cy = effective_domain.centroid

    polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in effective_domain.outer_boundary]

    geometry_data = {
        "points": polygon_points,
    }

    if effective_domain.inner_boundaries:
        geometry_data["holes"] = [
            [[pt[0] - cx, pt[1] - cy] for pt in hole]
            for hole in effective_domain.inner_boundaries
        ]

    # Create the Item
    item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(
            type="pocket",
            depth=str(params.depth_mm),
            depth_mm=params.depth_mm,
        ),
        shape_id=generate_shape_id(shape_id_prefix, 0, "flat"),
    )

    return [item]


__all__ = ["flat_pocket_generator"]
