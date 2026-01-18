"""SVG stamp generator for area fills.

This generator takes an SVG path, parses it to polylines, and produces
LayoutAST Items that can be used for engraving, pockets, or profiles.

The SVG geometry is scaled and positioned to fit within the target domain,
making it suitable for decorative patterns, logos, or custom engravings.

Usage:
    from domains import Domain
    from generators.svg import svg_stamp_generator, SVGPathParams

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = SVGPathParams(
        svg_path="M0,0 C50,50 100,0 100,100 L0,100 Z",
        depth_mm=2.0,
        tolerance=0.1,
    )
    items = svg_stamp_generator(domain, params)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch
from generators.base import (
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.svg.parser import (
    parse_svg_path,
    polylines_bounds,
    Polyline,
)
from generators.svg.params import SVGPathParams
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def svg_stamp_generator(
    domain: Domain,
    params: SVGPathParams,
    *,
    allow_empty: bool = False,
) -> GeneratorResult:
    """Generate Items from an SVG path within a domain.

    Parses the SVG path, flattens curves to polylines, scales/positions
    the geometry within the domain bounds, and produces LayoutAST Items.

    Args:
        domain: The domain defining the target region
        params: SVGPathParams with path string and settings
        allow_empty: If True, return empty list when SVG produces no geometry

    Returns:
        List of LayoutAST Items representing the SVG geometry

    Raises:
        ValueError: If SVG parsing fails or domain is unsuitable

    Note:
        File-based SVG loading is not supported at the generator level to
        maintain determinism. Load SVG content at a higher layer (template
        or orchestration) and pass the path string via SVGPathParams.svg_path.
    """
    params.validate()

    if not validate_domain_for_generation(
        domain, allow_empty=allow_empty, generator_name="svg_stamp_generator"
    ):
        return []

    # Parse SVG to polylines
    polylines = parse_svg_path(params.svg_path, tolerance=params.tolerance)

    if not polylines:
        if allow_empty:
            return []
        raise ValueError("svg_stamp_generator: SVG path produced no geometry")

    # Filter out single-point polylines
    polylines = [p for p in polylines if len(p) >= 2]

    if not polylines:
        if allow_empty:
            return []
        raise ValueError("svg_stamp_generator: SVG path produced no valid polylines")

    # Get SVG bounds
    x_min, y_min, x_max, y_max = polylines_bounds(polylines)
    svg_width = x_max - x_min
    svg_height = y_max - y_min

    if svg_width < 1e-10 or svg_height < 1e-10:
        if allow_empty:
            return []
        raise ValueError("svg_stamp_generator: SVG has degenerate dimensions")

    # Get domain bounds in local coordinates
    domain_bounds = domain.bounds
    domain_width = domain_bounds.width
    domain_height = domain_bounds.height

    # Calculate transform from SVG coordinates to domain-local coordinates
    # SVG origin is typically top-left, domain-local is centered at local_origin
    transform = _calculate_transform(
        svg_bounds=(x_min, y_min, x_max, y_max),
        domain_bounds=domain_bounds,
        scale_mode=params.scale_mode,
        svg_unit_mm=params.svg_unit_mm,
        center=params.center,
        invert_y=params.invert_y,
    )

    # Transform polylines to domain-local coordinates
    transformed_polylines = _transform_polylines(polylines, transform)

    # Clip polylines to domain (optional, for safety)
    # For now, skip clipping - trust that SVG fits after scaling

    # Convert to sheet coordinates using domain transforms
    sheet_polylines = _to_sheet_coordinates(transformed_polylines, domain)

    # Generate Items
    items: GeneratorResult = []

    for i, polyline in enumerate(sheet_polylines):
        if len(polyline) < 2:
            continue

        # Determine if this is a closed path
        is_closed = _is_closed_polyline(polyline)

        # Calculate center for placement
        px_min = min(p[0] for p in polyline)
        px_max = max(p[0] for p in polyline)
        py_min = min(p[1] for p in polyline)
        py_max = max(p[1] for p in polyline)
        center_x = (px_min + px_max) / 2
        center_y = (py_min + py_max) / 2

        # Build geometry
        if is_closed and params.feature_type == "pocket":
            # Closed path as polygon for pocket
            shape_type = "Polygon"
            geometry_data = {
                "points": [[p[0], p[1]] for p in polyline],
            }
        elif is_closed and params.feature_type == "profile":
            # Closed path for profile cut
            shape_type = "Polygon"
            geometry_data = {
                "points": [[p[0], p[1]] for p in polyline],
            }
        else:
            # Open path or engrave - use Polyline
            shape_type = "Polyline"
            geometry_data = {
                "points": [[p[0], p[1]] for p in polyline],
            }

        # Determine feature side for profile
        feature_side = None
        if params.feature_type == "profile":
            feature_side = "on"  # Default to on-line for SVG profiles

        item = Item(
            kind="shape",
            type=shape_type,
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=(center_x, center_y)),
            feature=Feature(
                type=params.feature_type,
                depth=params.depth_mm,
                side=feature_side,
            ),
            shape_id=generate_shape_id("svg", i),
        )
        items.append(item)

    if not items and not allow_empty:
        raise ValueError("svg_stamp_generator: No valid Items produced from SVG")

    return items


def _calculate_transform(
    svg_bounds: tuple[float, float, float, float],
    domain_bounds,
    scale_mode: str,
    svg_unit_mm: float,
    center: bool,
    invert_y: bool,
) -> dict:
    """Calculate transform parameters from SVG to domain-local coordinates.

    Args:
        svg_bounds: (x_min, y_min, x_max, y_max) of the SVG content
        domain_bounds: Domain bounds object with width/height
        scale_mode: "fit", "fill", or "none"
        svg_unit_mm: Conversion factor from SVG units to mm (used when scale_mode="none")
        center: Whether to center the SVG in the domain
        invert_y: Whether to flip Y coordinates (SVG Y-down to CAM Y-up)

    Returns a dict with scale_x, scale_y, offset_x, offset_y.
    """
    x_min, y_min, x_max, y_max = svg_bounds
    svg_width = x_max - x_min
    svg_height = y_max - y_min

    domain_width = domain_bounds.width
    domain_height = domain_bounds.height

    # Calculate scale based on mode
    if scale_mode == "fit":
        # Uniform scale to fit within domain
        scale = min(domain_width / svg_width, domain_height / svg_height)
        scale_x = scale
        scale_y = scale
    elif scale_mode == "fill":
        # Uniform scale to fill domain (may crop)
        scale = max(domain_width / svg_width, domain_height / svg_height)
        scale_x = scale
        scale_y = scale
    else:  # "none"
        # Use svg_unit_mm to convert SVG units to mm
        scale_x = svg_unit_mm
        scale_y = svg_unit_mm

    # Apply Y inversion
    if invert_y:
        scale_y = -scale_y

    # Calculate offset to center or position
    if center:
        # Center SVG within domain bounds
        # Domain local coords: center at local_origin, extends ±width/2, ±height/2
        scaled_width = svg_width * abs(scale_x)
        scaled_height = svg_height * abs(scale_y)

        # Offset to center the scaled SVG at domain center (0, 0 in local coords)
        # First translate SVG to origin (subtract SVG center), then scale
        svg_cx = (x_min + x_max) / 2
        svg_cy = (y_min + y_max) / 2

        offset_x = -svg_cx * scale_x
        offset_y = -svg_cy * scale_y
    else:
        # Position at domain origin
        offset_x = -x_min * scale_x
        offset_y = -y_min * scale_y

    return {
        "scale_x": scale_x,
        "scale_y": scale_y,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }


def _transform_polylines(
    polylines: list[Polyline],
    transform: dict,
) -> list[Polyline]:
    """Apply transform to polylines."""
    scale_x = transform["scale_x"]
    scale_y = transform["scale_y"]
    offset_x = transform["offset_x"]
    offset_y = transform["offset_y"]

    return [
        [(x * scale_x + offset_x, y * scale_y + offset_y) for x, y in polyline]
        for polyline in polylines
    ]


def _to_sheet_coordinates(
    local_polylines: list[Polyline],
    domain: Domain,
) -> list[Polyline]:
    """Transform polylines from domain-local to sheet coordinates."""
    return [
        local_to_sheet_batch(polyline, domain)
        for polyline in local_polylines
    ]


def _is_closed_polyline(polyline: Polyline, tolerance: float = 0.01) -> bool:
    """Check if a polyline forms a closed path."""
    if len(polyline) < 3:
        return False

    first = polyline[0]
    last = polyline[-1]

    dx = abs(first[0] - last[0])
    dy = abs(first[1] - last[1])

    return dx <= tolerance and dy <= tolerance


__all__ = [
    "svg_stamp_generator",
]
