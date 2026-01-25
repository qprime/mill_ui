"""Grid pattern area generator.

A grid generator creates a crosshatch pattern of perpendicular lines
across the domain interior at the specified depth. The pattern consists
of vertical and horizontal lines that form a regular grid.

The grid pattern is computed in domain-local coordinates, ensuring consistent
output regardless of where the domain is placed on the sheet. The final
geometry is then transformed to sheet coordinates.

Usage:
    from domains import Domain
    from generators.area.grid import grid_generator
    from generators.base import GridParams

    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    params = GridParams(
        spacing_x_mm=25.0,
        spacing_y_mm=25.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )
    items = grid_generator(domain, params)

    # Items can then be added to a LayoutAST
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch, sheet_to_local
from generators.base import (
    GeneratorResult,
    GridParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def _clip_line_to_domain(
    line_start: tuple[float, float],
    line_end: tuple[float, float],
    domain: Domain,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Clip a line segment to stay within the domain boundary.

    Uses Shapely to intersect the line with the domain polygon.

    Args:
        line_start: Start point of the line in sheet coordinates
        line_end: End point of the line in sheet coordinates
        domain: The domain to clip against

    Returns:
        List of (start, end) tuples representing the clipped segments.
        May be empty if line is fully outside, or contain multiple
        segments if the domain has holes.
    """
    from shapely.geometry import LineString

    line = LineString([line_start, line_end])
    polygon = domain.polygon

    intersection = line.intersection(polygon)

    if intersection.is_empty:
        return []

    segments = []

    if intersection.geom_type == "LineString":
        coords = list(intersection.coords)
        if len(coords) >= 2:
            segments.append(
                ((coords[0][0], coords[0][1]), (coords[-1][0], coords[-1][1]))
            )
    elif intersection.geom_type == "MultiLineString":
        for geom in intersection.geoms:
            coords = list(geom.coords)
            if len(coords) >= 2:
                segments.append(
                    ((coords[0][0], coords[0][1]), (coords[-1][0], coords[-1][1]))
                )
    # Ignore points or other geometry types

    return segments


def grid_generator(
    domain: Domain,
    params: GridParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "grid",
) -> GeneratorResult:
    """Generate grid pattern items that cover the domain interior.

    Creates a crosshatch of perpendicular lines at the specified spacing.
    Lines are clipped to stay within the domain boundary, including
    handling of holes in the domain.

    The pattern is computed in domain-local coordinates (centered at domain
    centroid, aligned with domain rotation), then transformed to sheet
    coordinates for the output Items.

    Args:
        domain: The domain defining the pattern region
        params: Grid parameters (spacing, line width, depth, offset)
        allow_empty: If True, return empty list instead of raising when
            the domain is too small for the grid parameters
        shape_id_prefix: Prefix for generated shape IDs

    Returns:
        List of Line Items with engrave features representing grid lines,
        or empty list if allow_empty=True and generation cannot proceed

    Raises:
        ValueError: If params are invalid or domain too small (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(200, 100, center=(100, 50))
        >>> params = GridParams(spacing_x_mm=25.0, spacing_y_mm=25.0,
        ...                     line_width_mm=3.0, depth_mm=2.0)
        >>> items = grid_generator(domain, params)
        >>> len(items) > 0
        True
    """
    # Validate parameters
    params.validate()

    # Validate domain
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,  # Need reasonable area for grid pattern
        allow_empty=allow_empty,
        generator_name="GridGenerator",
    ):
        return []

    # Get domain bounds in local coordinates
    local_bounds = _get_local_bounds(domain)
    local_x_min = local_bounds["x_min"]
    local_x_max = local_bounds["x_max"]
    local_y_min = local_bounds["y_min"]
    local_y_max = local_bounds["y_max"]

    # Check if domain is large enough for at least one grid cell
    domain_width = local_x_max - local_x_min
    domain_height = local_y_max - local_y_min

    if domain_width < params.spacing_x_mm and domain_height < params.spacing_y_mm:
        if allow_empty:
            return []
        raise ValueError(
            f"GridGenerator: Domain size ({domain_width:.1f}mm x {domain_height:.1f}mm) "
            f"is smaller than grid spacing ({params.spacing_x_mm}mm x {params.spacing_y_mm}mm). "
            f"Reduce spacing or use a larger domain."
        )

    items: list[Item] = []
    item_index = 0

    # Generate vertical lines (parallel to Y axis)
    # Start from offset, extend both directions to cover domain
    x_start = params.offset_x_mm
    # Find the first grid line position less than local_x_min
    while x_start > local_x_min:
        x_start -= params.spacing_x_mm
    # Now generate lines from x_start to beyond local_x_max
    x = x_start
    while x <= local_x_max:
        # Line goes from bottom to top of domain (with margin)
        local_start = (x, local_y_min - 10)
        local_end = (x, local_y_max + 10)

        # Transform to sheet coordinates
        sheet_points = local_to_sheet_batch([local_start, local_end], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]

        # Clip to domain
        clipped = _clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            item = _create_line_item(
                start=seg_start,
                end=seg_end,
                depth_mm=params.depth_mm,
                line_width_mm=params.line_width_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index, "v"),
            )
            items.append(item)
            item_index += 1

        x += params.spacing_x_mm

    # Generate horizontal lines (parallel to X axis)
    y_start = params.offset_y_mm
    while y_start > local_y_min:
        y_start -= params.spacing_y_mm

    y = y_start
    while y <= local_y_max:
        # Line goes from left to right of domain (with margin)
        local_start = (local_x_min - 10, y)
        local_end = (local_x_max + 10, y)

        # Transform to sheet coordinates
        sheet_points = local_to_sheet_batch([local_start, local_end], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]

        # Clip to domain
        clipped = _clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            item = _create_line_item(
                start=seg_start,
                end=seg_end,
                depth_mm=params.depth_mm,
                line_width_mm=params.line_width_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index, "h"),
            )
            items.append(item)
            item_index += 1

        y += params.spacing_y_mm

    if not items and not allow_empty:
        raise ValueError(
            f"GridGenerator: Could not generate any grid lines for domain. "
            f"Domain may be too small or grid parameters incompatible."
        )

    return items


def _create_line_item(
    start: tuple[float, float],
    end: tuple[float, float],
    depth_mm: float,
    line_width_mm: float,
    shape_id: str,
) -> Item:
    """Create a Line Item for a grid line segment.

    Args:
        start: Start point in sheet coordinates
        end: End point in sheet coordinates
        depth_mm: Engraving depth
        line_width_mm: Width of the line (for toolpath planning)
        shape_id: Unique shape identifier

    Returns:
        A Line Item with engrave feature
    """
    # Compute center for placement
    cx = (start[0] + end[0]) / 2
    cy = (start[1] + end[1]) / 2

    geometry_data = {
        "start": [start[0] - cx, start[1] - cy],
        "end": [end[0] - cx, end[1] - cy],
        "width_mm": line_width_mm,
    }

    return Item(
        kind="shape",
        type="Line",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(
            type="engrave",
            depth=str(depth_mm),
            depth_mm=depth_mm,
        ),
        shape_id=shape_id,
    )


def _get_local_bounds(domain: Domain) -> dict[str, float]:
    """Get domain bounds in domain-local coordinates.

    Transforms the domain's corner points to local coordinates and
    computes the axis-aligned bounding box.

    Args:
        domain: The domain to analyze

    Returns:
        Dict with x_min, x_max, y_min, y_max in local coordinates
    """
    # Transform outer boundary to local coordinates
    local_points = [
        sheet_to_local(pt, domain)
        for pt in domain.outer_boundary
    ]

    xs = [p[0] for p in local_points]
    ys = [p[1] for p in local_points]

    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


__all__ = ["grid_generator"]
