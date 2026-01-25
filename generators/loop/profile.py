"""Profile loop generator.

A profile cut follows the boundary of a domain, cutting through or to a
specified depth. This is the fundamental operation for cutting parts out
of sheet material.

Usage:
    from domains import Domain
    from generators.loop.profile import profile_generator
    from generators.base import ProfileParams

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = ProfileParams(side="outside", depth="through")
    items = profile_generator(domain, params)

    # Items can then be added to a LayoutAST
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    GeneratorResult,
    LoopSelection,
    ProfileParams,
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
                    f"ProfileGenerator: loop index {idx} out of range. "
                    f"Domain has {num_loops} loops (0=outer, 1-{num_loops-1}=inner)"
                )
            result.append((idx, all_loops[idx]))
        return result

    else:
        raise ValueError(f"ProfileGenerator: invalid loop_selection: {selection}")


def _loop_type_suffix(index: int) -> str:
    """Generate suffix for shape ID based on loop index."""
    if index == 0:
        return "outer"
    return f"inner_{index}"


def profile_generator(
    domain: Domain,
    params: ProfileParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "profile",
    sheet_thickness_mm: float | None = None,
) -> GeneratorResult:
    """Generate profile cut items along domain boundaries.

    Creates Polygon items with profile features that follow the specified
    loops of the domain. Each selected loop produces one Item.

    Args:
        domain: The domain defining the cut region
        params: Profile parameters (side, depth, loop selection, tabs)
        allow_empty: If True, return empty list instead of raising when
            the domain has no matching loops
        shape_id_prefix: Prefix for generated shape IDs
        sheet_thickness_mm: Sheet thickness for "through" depth resolution
            (optional, used for metadata only)

    Returns:
        List of Polygon Items with profile features, one per selected loop

    Raises:
        ValueError: If params are invalid or requested loops don't exist
            (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(100, 50, center=(50, 25))
        >>> params = ProfileParams(side="outside", depth="through")
        >>> items = profile_generator(domain, params)
        >>> len(items)
        1
        >>> items[0].feature.type
        'profile'
        >>> items[0].feature.side
        'outside'
    """
    # Validate parameters
    params.validate()

    # Validate domain
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="ProfileGenerator",
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
            f"ProfileGenerator: No loops match selection '{params.loop_selection}'"
        )

    items: list[Item] = []

    for loop_idx, boundary in loops:
        cx = sum(p[0] for p in boundary) / len(boundary)
        cy = sum(p[1] for p in boundary) / len(boundary)

        polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in boundary]

        geometry_data = {
            "points": polygon_points,
        }

        # Resolve depth
        if params.depth == "through":
            depth_str = "through"
            depth_mm = None
        else:
            depth_str = str(params.depth)
            depth_mm = float(params.depth)

        # Build feature
        feature_kwargs = {
            "type": "profile",
            "depth": depth_str,
            "side": params.side,
        }

        if depth_mm is not None:
            feature_kwargs["depth_mm"] = depth_mm

        # Add tabs if specified
        if params.tab_count > 0:
            feature_kwargs["tab_count"] = params.tab_count
            feature_kwargs["tab_width_mm"] = params.tab_width_mm
            feature_kwargs["tab_height_mm"] = params.tab_height_mm

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


__all__ = ["profile_generator"]
