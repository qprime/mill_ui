"""Raised panel area generator.

Creates the traditional "raised panel" look used in cabinet doors and architectural
millwork. The raised panel effect is created by:

1. A beveled border region that transitions from deep at the outer edge to shallow
   at the inner edge, creating an angled surface.
2. A center field region at a uniform shallow depth, appearing "raised" relative
   to the surrounding border.

The border region is represented as a polygon with a hole (the inner domain boundary).
The field region is represented as a separate polygon for the center area.

Usage:
    from domains import Domain
    from generators.area.raised_panel import raised_panel_generator
    from generators.base import RaisedPanelParams

    domain = Domain.from_rectangle(300, 400, center=(150, 200))
    params = RaisedPanelParams(
        border_width_mm=25.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )
    items = raised_panel_generator(domain, params)

    # Returns 2 items: border (beveled pocket) and field (flat pocket)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    GeneratorResult,
    RaisedPanelParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def raised_panel_generator(
    domain: Domain,
    params: RaisedPanelParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "raised_panel",
) -> GeneratorResult:
    """Generate raised panel items within the domain.

    Creates two items:
    1. A border pocket with 'bevel' feature type at border_depth_mm, representing
       the angled transition zone.
    2. A field pocket at field_depth_mm for the raised center area.

    The border is created by insetting the domain by border_width_mm. The resulting
    inner domain becomes the field, and the original domain minus the field becomes
    the border region.

    Args:
        domain: The domain defining the panel region
        params: Raised panel parameters (border width, depths, angle)
        allow_empty: If True, return empty list instead of raising when
            the domain is too small for the specified border width
        shape_id_prefix: Prefix for generated shape IDs

    Returns:
        List containing two Polygon Items (border and field), or empty list
        if allow_empty=True and domain is unsuitable

    Raises:
        ValueError: If params are invalid or domain too small (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(200, 300, center=(100, 150))
        >>> params = RaisedPanelParams(
        ...     border_width_mm=20.0,
        ...     border_depth_mm=6.0,
        ...     field_depth_mm=2.0,
        ... )
        >>> items = raised_panel_generator(domain, params)
        >>> len(items)
        2
        >>> items[0].feature.type  # border
        'bevel'
        >>> items[1].feature.type  # field
        'pocket'
    """
    # Validate parameters
    params.validate()

    # Validate domain is large enough
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,  # Raised panels need reasonable size
        allow_empty=allow_empty,
        generator_name="RaisedPanelGenerator",
    ):
        return []

    # Inset to create the field domain
    field_result = domain.inset(params.border_width_mm)

    if field_result.is_empty:
        if allow_empty:
            return []
        raise ValueError(
            f"RaisedPanelGenerator: border_width {params.border_width_mm}mm exceeds "
            f"half of domain minimum dimension. Domain bounds: "
            f"{domain.bounds.width}mm x {domain.bounds.height}mm"
        )

    # Use first domain from inset (typically single for convex shapes)
    field_domain = field_result.domains[0]

    items: list[Item] = []

    # -------------------------------------------------------------------------
    # 1. Create border item (bevel pocket)
    # -------------------------------------------------------------------------
    # Compute border centroid (approximate: use original domain centroid)
    bcx, bcy = domain.centroid

    # Convert absolute domain coordinates to relative coordinates (centered on placement)
    border_points = [[pt[0] - bcx, pt[1] - bcy] for pt in domain.outer_boundary]
    field_hole = [[pt[0] - bcx, pt[1] - bcy] for pt in field_domain.outer_boundary]

    # Include any existing holes from the original domain
    holes = [field_hole]
    if domain.inner_boundaries:
        for inner in domain.inner_boundaries:
            holes.append([[pt[0] - bcx, pt[1] - bcy] for pt in inner])

    border_geometry_data = {
        "points": border_points,
        "holes": holes,
    }

    border_item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=border_geometry_data),
        placement=Placement(center_xy_mm=(bcx, bcy)),
        feature=Feature(
            type="bevel",
            depth=str(params.border_depth_mm),
            depth_mm=params.border_depth_mm,
            bevel_width_mm=params.border_width_mm,
            bevel_angle_deg=params.angle_degrees,
            bevel_inner_depth_mm=params.field_depth_mm,
        ),
        shape_id=generate_shape_id(shape_id_prefix, 0, "border"),
    )
    items.append(border_item)

    # -------------------------------------------------------------------------
    # 2. Create field item (flat pocket)
    # -------------------------------------------------------------------------
    fcx, fcy = field_domain.centroid

    # Convert absolute domain coordinates to relative coordinates (centered on placement)
    field_points = [[pt[0] - fcx, pt[1] - fcy] for pt in field_domain.outer_boundary]

    field_geometry_data = {
        "points": field_points,
    }

    # Include any holes that ended up in the field domain
    if field_domain.inner_boundaries:
        field_geometry_data["holes"] = [
            [[pt[0] - fcx, pt[1] - fcy] for pt in hole]
            for hole in field_domain.inner_boundaries
        ]

    field_item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=field_geometry_data),
        placement=Placement(center_xy_mm=(fcx, fcy)),
        feature=Feature(
            type="pocket",
            depth=str(params.field_depth_mm),
            depth_mm=params.field_depth_mm,
        ),
        shape_id=generate_shape_id(shape_id_prefix, 1, "field"),
    )
    items.append(field_item)

    return items


__all__ = ["raised_panel_generator"]
