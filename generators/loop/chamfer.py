"""Chamfer loop generator.

A chamfer creates an angled edge cut along domain boundaries, removing material
at an angle from the top surface. This is commonly used for:

- Presentation edges on cabinet panels
- Breaking sharp edges for safety
- Decorative edge treatments

The chamfer is defined by its horizontal width and vertical depth, which
together determine the cut angle. The generator creates Polygon items with
chamfer features that the CAM planner can convert to appropriate V-bit or
chamfer mill toolpaths.

Usage:
    from domains import Domain
    from generators.loop.chamfer import chamfer_generator
    from generators.base import ChamferParams

    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    params = ChamferParams(width_mm=5.0, depth_mm=3.0)
    items = chamfer_generator(domain, params)

    # Items can then be added to a LayoutAST
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    ChamferParams,
    GeneratorResult,
    LoopSelection,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def _extract_loops(
    domain: Domain,
    selection: LoopSelection,
) -> list[tuple[int, tuple[tuple[float, float], ...]]]:
    """Extract loops from domain based on selection.

    Args:
        domain: The domain to extract loops from
        selection: Which loops to extract

    Returns:
        List of (index, boundary_points) tuples

    Raises:
        ValueError: If selection references invalid loop indices
    """
    all_loops = [domain.outer_boundary] + list(domain.inner_boundaries)
    num_loops = len(all_loops)

    if selection == "outer_only":
        return [(0, domain.outer_boundary)]

    elif selection == "inner_only":
        return [
            (i + 1, inner)
            for i, inner in enumerate(domain.inner_boundaries)
        ]

    elif selection == "all_loops":
        return [(i, loop) for i, loop in enumerate(all_loops)]

    elif isinstance(selection, list):
        result = []
        for idx in selection:
            if idx < 0 or idx >= num_loops:
                raise ValueError(
                    f"ChamferGenerator: loop index {idx} out of range. "
                    f"Domain has {num_loops} loops (0=outer, 1-{num_loops-1}=inner)"
                )
            result.append((idx, all_loops[idx]))
        return result

    else:
        raise ValueError(f"ChamferGenerator: invalid loop_selection: {selection}")


def _loop_type_suffix(index: int) -> str:
    """Generate suffix for shape ID based on loop index."""
    if index == 0:
        return "outer"
    return f"inner_{index}"


def chamfer_generator(
    domain: Domain,
    params: ChamferParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "chamfer",
) -> GeneratorResult:
    """Generate chamfer items along domain boundaries.

    Creates Polygon items with chamfer features that follow the specified
    loops of the domain. Each selected loop produces one Item with chamfer
    geometry that represents the angled edge cut.

    The chamfer creates a band along the edge where material is removed at
    an angle. The band width equals params.width_mm, and the depth at the
    inner edge of the band equals params.depth_mm.

    Args:
        domain: The domain defining the edge region
        params: Chamfer parameters (width, depth, loop selection)
        allow_empty: If True, return empty list instead of raising when
            the domain has no matching loops
        shape_id_prefix: Prefix for generated shape IDs

    Returns:
        List of Polygon Items with chamfer features, one per selected loop

    Raises:
        ValueError: If params are invalid or requested loops don't exist
            (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(100, 50, center=(50, 25))
        >>> params = ChamferParams(width_mm=3.0, depth_mm=2.0)
        >>> items = chamfer_generator(domain, params)
        >>> len(items)
        1
        >>> items[0].feature.type
        'chamfer'
    """
    # Validate parameters
    params.validate()

    # Validate domain
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="ChamferGenerator",
    ):
        return []

    # Extract the loops to process
    try:
        loops = _extract_loops(domain, params.loop_selection)
    except ValueError:
        if allow_empty:
            return []
        raise

    if not loops:
        if allow_empty:
            return []
        raise ValueError(
            f"ChamferGenerator: No loops match selection '{params.loop_selection}'"
        )

    items: list[Item] = []

    for loop_idx, boundary in loops:
        cx = sum(p[0] for p in boundary) / len(boundary)
        cy = sum(p[1] for p in boundary) / len(boundary)

        polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in boundary]

        geometry_data = {
            "points": polygon_points,
        }

        # Build feature with chamfer-specific attributes
        feature_kwargs = {
            "type": "chamfer",
            "depth": str(params.depth_mm),
            "depth_mm": params.depth_mm,
            "chamfer_width_mm": params.width_mm,
            "chamfer_angle_deg": params.angle_degrees,
        }

        # Determine side based on loop type
        # Outer loop: chamfer on outside
        # Inner loops (holes): chamfer on inside of hole
        if loop_idx == 0:
            feature_kwargs["side"] = "outside"
        else:
            feature_kwargs["side"] = "inside"

        # Create the Item
        item = Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=Feature(**feature_kwargs),
            shape_id=generate_shape_id(
                shape_id_prefix,
                loop_idx,
                _loop_type_suffix(loop_idx),
            ),
        )

        items.append(item)

    return items


__all__ = ["chamfer_generator"]
