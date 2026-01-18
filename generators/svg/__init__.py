"""SVG path parsing and conversion for the generator system.

This module provides utilities to parse SVG path strings and convert them to
polylines suitable for use with generators. It enables area generators to use
SVG-derived geometry as stamps, fills, or engraving patterns.

Supported SVG path commands (subset):
- M/m: Move to (absolute/relative)
- L/l: Line to (absolute/relative)
- H/h: Horizontal line to (absolute/relative)
- V/v: Vertical line to (absolute/relative)
- C/c: Cubic Bezier curve (absolute/relative)
- S/s: Smooth cubic Bezier (absolute/relative)
- Q/q: Quadratic Bezier curve (absolute/relative)
- T/t: Smooth quadratic Bezier (absolute/relative)
- A/a: Elliptical arc (absolute/relative)
- Z/z: Close path

Limitations:
    - Fill rules (even-odd, nonzero) are not interpreted; all closed paths
      are treated as solid polygons
    - Nested paths (holes) are not supported; SVGs with holes like fonts
      should be pre-processed to separate inner/outer contours
    - SVG coordinates are unitless; use scale_mode="fit" or "fill" for
      automatic scaling, or scale_mode="none" with svg_unit_mm for exact sizes

Usage:
    from generators.svg import parse_svg_path, SVGPathParams
    from generators.svg.stamp import svg_stamp_generator

    # Parse an SVG path to polylines
    polylines = parse_svg_path("M0,0 L100,0 L100,100 L0,100 Z", tolerance=0.1)

    # Use with a generator
    params = SVGPathParams(
        svg_path="M0,0 C50,50 100,0 100,100",
        depth_mm=2.0,
        tolerance=0.1,
    )
    items = svg_stamp_generator(domain, params)

See Also:
    - docs/domain_generator_design.md Stage 6 for design specification
    - generators/svg/parser.py for parsing implementation
    - generators/svg/curves.py for curve flattening algorithms
"""

from generators.svg.parser import (
    parse_svg_path,
    SVGParseError,
)
from generators.svg.params import SVGPathParams
from generators.svg.stamp import svg_stamp_generator

__all__ = [
    # Parsing
    "parse_svg_path",
    "SVGParseError",
    # Parameters
    "SVGPathParams",
    # Generators
    "svg_stamp_generator",
]
