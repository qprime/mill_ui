"""Generator system for producing LayoutAST Items from Domains.

Generators are deterministic functions that produce geometry within a domain.
This module provides:

1. Generator protocol and base parameter classes
2. Area generators (flat pocket, patterns)
3. Loop generators (profile cuts, beads)
4. SVG generators (SVG path parsing and stamping)

Usage:
    from domains import Domain
    from generators import (
        flat_pocket_generator,
        profile_generator,
        FlatPocketParams,
        ProfileParams,
    )

    # Create a door with profile and pocket
    outer_domain = Domain.from_rectangle(400, 600, center=(200, 300))
    panel_domain = outer_domain.inset(50).domains[0]

    # Generate profile for outer cut
    profile_items = profile_generator(
        outer_domain,
        ProfileParams(side="outside", depth="through"),
    )

    # Generate pocket for panel recess
    pocket_items = flat_pocket_generator(
        panel_domain,
        FlatPocketParams(depth_mm=6.0),
    )

    # Combine into LayoutAST
    all_items = profile_items + pocket_items

SVG Support (Stage 6):
    from generators.svg import parse_svg_path, svg_stamp_generator, SVGPathParams

    # Parse SVG path and generate engravings
    params = SVGPathParams(
        svg_path="M0,0 C50,50 100,0 100,100",
        depth_mm=2.0,
    )
    svg_items = svg_stamp_generator(domain, params)

Architecture:
    Generators receive a Domain and typed parameters, and emit LayoutAST Items.
    They operate in domain-local coordinates internally but output Items in
    sheet coordinates. This enables:

    - Determinism: same domain + params = same output
    - Composability: generators can be combined on different domains
    - Testability: output can be validated at IR level without CAM

See Also:
    - docs/domain_generator_design.md for the full architecture spec
    - generators/base.py for protocol and parameter definitions
    - generators/area/ for area generator implementations
    - generators/loop/ for loop generator implementations
    - generators/svg/ for SVG path parsing and generators
"""

# Base classes and utilities
from generators.base import (
    # Protocol
    Generator,
    GeneratorResult,
    # Parameter classes
    BaseParams,
    FlatPocketParams,
    ProfileParams,
    WaveParams,
    GridParams,
    BeadParams,
    RaisedPanelParams,
    ChamferParams,
    LinePatternParams,
    ConcentricBorderParams,
    XPanelParams,
    # Type aliases
    LoopSelection,
    # Utilities
    generate_shape_id,
    validate_domain_for_generation,
)

# Area generators
from generators.area import (
    flat_pocket_generator,
    wave_generator,
    grid_generator,
    raised_panel_generator,
    line_pattern_generator,
    concentric_border_generator,
    x_panel_generator,
)

# Utilities
from generators.utils import shapely_to_item, iter_polygons

# Loop generators
from generators.loop import profile_generator, bead_generator, chamfer_generator

# SVG generators (Stage 6)
from generators.svg import (
    parse_svg_path,
    SVGParseError,
    SVGPathParams,
    svg_stamp_generator,
)

__all__ = [
    # Protocol and types
    "Generator",
    "GeneratorResult",
    "LoopSelection",
    # Parameter classes
    "BaseParams",
    "FlatPocketParams",
    "ProfileParams",
    "WaveParams",
    "GridParams",
    "BeadParams",
    "RaisedPanelParams",
    "ChamferParams",
    "LinePatternParams",
    "ConcentricBorderParams",
    "XPanelParams",
    "SVGPathParams",
    # Generators
    "flat_pocket_generator",
    "wave_generator",
    "grid_generator",
    "raised_panel_generator",
    "line_pattern_generator",
    "concentric_border_generator",
    "x_panel_generator",
    "profile_generator",
    "bead_generator",
    "chamfer_generator",
    "svg_stamp_generator",
    # SVG utilities
    "parse_svg_path",
    "SVGParseError",
    # Utilities
    "generate_shape_id",
    "validate_domain_for_generation",
    "shapely_to_item",
    "iter_polygons",
]
