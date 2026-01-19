"""Concentric border area generator.

Creates nested contour-following borders (inset loops) as groove patterns.
Each border is created by subtracting an inner inset from an outer inset,
producing a ring-shaped groove that follows the domain's contour.

Usage:
    from domains import Domain
    from generators.area.concentric_border import concentric_border_generator
    from generators.base import ConcentricBorderParams

    domain = Domain.from_rectangle(350, 450, center=(175, 225))
    params = ConcentricBorderParams(
        insets_mm=(15.0, 30.0, 45.0),
        groove_width_mm=3.0,
        depth_mm=2.0,
    )
    items = concentric_border_generator(domain, params)

This generator is useful for creating:
- Decorative nested rectangular borders
- Concentric contour grooves on any shape
- Multi-ring border patterns
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    ConcentricBorderParams,
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.utils import shapely_to_item, iter_polygons

if TYPE_CHECKING:
    from domains import Domain


def concentric_border_generator(
    domain: Domain,
    params: ConcentricBorderParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "border",
) -> GeneratorResult:
    """Generate concentric groove borders following domain contour.

    For each inset distance in params.insets_mm, creates a ring-shaped
    groove by:
    1. Computing an outer boundary at the inset distance
    2. Computing an inner boundary at inset + groove_width
    3. Subtracting inner from outer to get the ring

    Args:
        domain: The domain defining the border region
        params: Concentric border parameters (insets, groove width, depth)
        allow_empty: If True, return empty list instead of raising when
            borders don't fit within the domain
        shape_id_prefix: Prefix for generated shape IDs

    Returns:
        List of Polygon Items for each border groove, or empty list
        if allow_empty=True and domain is unsuitable

    Raises:
        ValueError: If params are invalid or domain too small (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(200, 200, center=(100, 100))
        >>> params = ConcentricBorderParams(insets_mm=(10.0, 20.0), groove_width_mm=3.0, depth_mm=2.0)
        >>> items = concentric_border_generator(domain, params)
        >>> len(items) >= 2
        True
    """
    # Validate parameters
    params.validate()

    # Validate domain
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="ConcentricBorderGenerator",
    ):
        return []

    items = []
    ring_idx = 0

    for inset in params.insets_mm:
        # Create outer boundary of the ring
        outer_result = domain.inset(inset)
        if outer_result.is_empty:
            if allow_empty:
                continue
            raise ValueError(
                f"ConcentricBorderGenerator: inset {inset}mm exceeds domain size. "
                f"Domain bounds: {domain.bounds.width:.1f}mm x {domain.bounds.height:.1f}mm"
            )

        # Create inner boundary of the ring
        inner_inset = inset + params.groove_width_mm
        inner_result = domain.inset(inner_inset)

        # For each outer domain, subtract the corresponding inner domain
        for outer_domain in outer_result:
            # Get the ring by subtracting inner from outer
            if inner_result.is_empty:
                continue

            ring_polygon = outer_domain.polygon
            for inner_domain in inner_result:
                ring_polygon = ring_polygon.difference(inner_domain.polygon)

            # Convert resulting polygons to items
            for poly in iter_polygons(ring_polygon):
                if poly.area < 0.01:  # Skip tiny fragments
                    continue

                item = shapely_to_item(
                    poly,
                    feature_type="pocket",
                    depth_mm=params.depth_mm,
                    shape_id=generate_shape_id(shape_id_prefix, ring_idx),
                )
                items.append(item)
                ring_idx += 1

    if not items and not allow_empty:
        raise ValueError(
            f"ConcentricBorderGenerator: No borders fit within domain. "
            f"Domain bounds: {domain.bounds.width:.1f}mm x {domain.bounds.height:.1f}mm, "
            f"smallest inset: {min(params.insets_mm)}mm"
        )

    return items


__all__ = ["concentric_border_generator"]
