"""SVG path string parser.

Parses SVG path data strings (the 'd' attribute of <path> elements) into
sequences of drawing commands, then converts them to polylines.

Supports the standard SVG path command subset needed for CNC engraving:
- M/m: moveto
- L/l: lineto
- H/h: horizontal lineto
- V/v: vertical lineto
- C/c: cubic Bezier
- S/s: smooth cubic Bezier
- Q/q: quadratic Bezier
- T/t: smooth quadratic Bezier
- A/a: elliptical arc
- Z/z: closepath

See: https://www.w3.org/TR/SVG/paths.html
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterator

from generators.svg.curves import (
    flatten_cubic_bezier,
    flatten_quadratic_bezier,
    flatten_arc,
)


# Type alias for 2D points
Point2D = tuple[float, float]

# Type alias for a polyline (sequence of connected points)
Polyline = list[Point2D]


class SVGParseError(ValueError):
    """Error during SVG path parsing."""

    def __init__(self, message: str, position: int | None = None):
        self.position = position
        if position is not None:
            message = f"{message} (at position {position})"
        super().__init__(message)


@dataclass
class ParseState:
    """Mutable state during path parsing."""

    current: Point2D = (0.0, 0.0)
    subpath_start: Point2D = (0.0, 0.0)
    last_control: Point2D | None = None  # For S/s and T/t commands
    last_command: str = ""


def parse_svg_path(
    path_data: str,
    tolerance: float = 0.1,
) -> list[Polyline]:
    """Parse an SVG path string to a list of polylines.

    Each subpath (started by M/m) becomes a separate polyline. Closed paths
    (ending with Z/z) have their last point equal to their first point.

    Args:
        path_data: SVG path data string (the 'd' attribute value)
        tolerance: Maximum deviation for curve flattening in mm

    Returns:
        List of polylines, where each polyline is a list of (x, y) points

    Raises:
        SVGParseError: If the path data is malformed
    """
    if not path_data or not path_data.strip():
        return []

    if tolerance <= 0:
        raise ValueError(f"Tolerance must be positive, got {tolerance}")

    tokens = _tokenize(path_data)
    polylines: list[Polyline] = []
    current_polyline: Polyline = []
    state = ParseState()

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if isinstance(token, str) and token.isalpha():
            command = token
            i += 1
        else:
            # Implicit command - repeat the previous command
            # (except M becomes L, m becomes l)
            if state.last_command in ("M", "m"):
                command = "L" if state.last_command == "M" else "l"
            else:
                command = state.last_command

            if not command:
                raise SVGParseError(f"Unexpected number without command: {token}")

        # Parse command arguments and execute
        try:
            i, new_polylines = _execute_command(
                command, tokens, i, state, current_polyline, tolerance
            )
        except (IndexError, ValueError) as e:
            raise SVGParseError(f"Error parsing command '{command}': {e}") from e

        # Handle new polylines from moveto commands
        if new_polylines:
            # Add any completed polylines (all but the last, which is still being built)
            for poly in new_polylines[:-1]:
                if poly and len(poly) >= 2:
                    polylines.append(poly)
            # The last one becomes the new current polyline
            current_polyline = new_polylines[-1] if new_polylines else []

        state.last_command = command

    # Add final polyline if it has points
    if current_polyline and len(current_polyline) >= 2:
        polylines.append(current_polyline)

    return polylines


def parse_svg_file(
    file_path: str,
    tolerance: float = 0.1,
) -> list[Polyline]:
    """Parse all paths from an SVG file.

    Extracts all <path> elements and concatenates their polylines.

    Args:
        file_path: Path to the SVG file
        tolerance: Maximum deviation for curve flattening in mm

    Returns:
        List of all polylines from all paths in the file

    Raises:
        SVGParseError: If the file cannot be parsed
        FileNotFoundError: If the file does not exist
    """
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as e:
        raise SVGParseError(f"Invalid SVG file: {e}") from e

    root = tree.getroot()

    # Handle SVG namespace
    ns = {"svg": "http://www.w3.org/2000/svg"}

    # Find all path elements (with or without namespace)
    paths = root.findall(".//path") + root.findall(".//svg:path", ns)

    all_polylines: list[Polyline] = []

    for path_elem in paths:
        d = path_elem.get("d")
        if d:
            polylines = parse_svg_path(d, tolerance)
            all_polylines.extend(polylines)

    return all_polylines


# =============================================================================
# Tokenizer
# =============================================================================

# Regex pattern for SVG path numbers (including scientific notation)
_NUMBER_PATTERN = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
)

# Regex pattern for path commands
_COMMAND_PATTERN = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]")


def _tokenize(path_data: str) -> list[str | float]:
    """Tokenize an SVG path string into commands and numbers."""
    tokens: list[str | float] = []
    pos = 0

    while pos < len(path_data):
        # Skip whitespace and commas
        while pos < len(path_data) and path_data[pos] in " \t\n\r,":
            pos += 1

        if pos >= len(path_data):
            break

        char = path_data[pos]

        # Check for command
        if char.isalpha():
            tokens.append(char)
            pos += 1
            continue

        # Check for number (including negative sign)
        match = _NUMBER_PATTERN.match(path_data, pos)
        if match:
            num_str = match.group()
            try:
                tokens.append(float(num_str))
            except ValueError:
                raise SVGParseError(f"Invalid number: {num_str}", pos)
            pos = match.end()
            continue

        # Unknown character
        raise SVGParseError(f"Unexpected character: '{char}'", pos)

    return tokens


def _get_numbers(tokens: list, start: int, count: int) -> tuple[list[float], int]:
    """Extract a fixed number of numeric arguments from tokens."""
    numbers = []
    pos = start

    for _ in range(count):
        if pos >= len(tokens):
            raise ValueError(f"Expected {count} arguments, got {len(numbers)}")
        val = tokens[pos]
        if not isinstance(val, (int, float)):
            raise ValueError(f"Expected number, got {val}")
        numbers.append(float(val))
        pos += 1

    return numbers, pos


# =============================================================================
# Command Execution
# =============================================================================

def _execute_command(
    command: str,
    tokens: list,
    pos: int,
    state: ParseState,
    current_polyline: Polyline,
    tolerance: float,
) -> tuple[int, list[Polyline]]:
    """Execute a path command and return updated position and any new polylines."""
    new_polylines: list[Polyline] = []
    is_relative = command.islower()
    cmd_upper = command.upper()

    if cmd_upper == "M":
        # Moveto - starts a new subpath
        args, pos = _get_numbers(tokens, pos, 2)
        x, y = args[0], args[1]

        if is_relative:
            x += state.current[0]
            y += state.current[1]

        # Save current polyline if it has content
        if current_polyline and len(current_polyline) >= 2:
            new_polylines.append(current_polyline)

        # Start new polyline
        state.current = (x, y)
        state.subpath_start = (x, y)
        state.last_control = None
        new_polylines.append([state.current])

        # Handle implicit lineto commands after moveto
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 2)
            x, y = args[0], args[1]
            if is_relative:
                x += state.current[0]
                y += state.current[1]
            state.current = (x, y)
            new_polylines[-1].append(state.current)
            state.last_control = None

    elif cmd_upper == "L":
        # Lineto
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 2)
            x, y = args[0], args[1]
            if is_relative:
                x += state.current[0]
                y += state.current[1]
            state.current = (x, y)
            current_polyline.append(state.current)
            state.last_control = None

    elif cmd_upper == "H":
        # Horizontal lineto
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 1)
            x = args[0]
            if is_relative:
                x += state.current[0]
            state.current = (x, state.current[1])
            current_polyline.append(state.current)
            state.last_control = None

    elif cmd_upper == "V":
        # Vertical lineto
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 1)
            y = args[0]
            if is_relative:
                y += state.current[1]
            state.current = (state.current[0], y)
            current_polyline.append(state.current)
            state.last_control = None

    elif cmd_upper == "C":
        # Cubic Bezier
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 6)
            x1, y1, x2, y2, x, y = args

            if is_relative:
                cx, cy = state.current
                x1, y1 = x1 + cx, y1 + cy
                x2, y2 = x2 + cx, y2 + cy
                x, y = x + cx, y + cy

            points = flatten_cubic_bezier(
                state.current, (x1, y1), (x2, y2), (x, y), tolerance
            )
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x2, y2)

    elif cmd_upper == "S":
        # Smooth cubic Bezier
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 4)
            x2, y2, x, y = args

            if is_relative:
                cx, cy = state.current
                x2, y2 = x2 + cx, y2 + cy
                x, y = x + cx, y + cy

            # First control point is reflection of previous control point
            if state.last_control and state.last_command.upper() in ("C", "S"):
                x1 = 2 * state.current[0] - state.last_control[0]
                y1 = 2 * state.current[1] - state.last_control[1]
            else:
                x1, y1 = state.current

            points = flatten_cubic_bezier(
                state.current, (x1, y1), (x2, y2), (x, y), tolerance
            )
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x2, y2)

    elif cmd_upper == "Q":
        # Quadratic Bezier
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 4)
            x1, y1, x, y = args

            if is_relative:
                cx, cy = state.current
                x1, y1 = x1 + cx, y1 + cy
                x, y = x + cx, y + cy

            points = flatten_quadratic_bezier(
                state.current, (x1, y1), (x, y), tolerance
            )
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x1, y1)

    elif cmd_upper == "T":
        # Smooth quadratic Bezier
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 2)
            x, y = args

            if is_relative:
                x += state.current[0]
                y += state.current[1]

            # Control point is reflection of previous control point
            if state.last_control and state.last_command.upper() in ("Q", "T"):
                x1 = 2 * state.current[0] - state.last_control[0]
                y1 = 2 * state.current[1] - state.last_control[1]
            else:
                x1, y1 = state.current

            points = flatten_quadratic_bezier(
                state.current, (x1, y1), (x, y), tolerance
            )
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x1, y1)

    elif cmd_upper == "A":
        # Elliptical arc
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 7)
            rx, ry, x_rot, large_arc_flag, sweep_flag, x, y = args

            # Convert flags to booleans
            large_arc = large_arc_flag != 0
            sweep = sweep_flag != 0

            # Convert rotation to radians
            x_rot_rad = math.radians(x_rot)

            if is_relative:
                x += state.current[0]
                y += state.current[1]

            points = flatten_arc(
                state.current, rx, ry, x_rot_rad, large_arc, sweep, (x, y), tolerance
            )
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = None

    elif cmd_upper == "Z":
        # Closepath
        if state.current != state.subpath_start:
            current_polyline.append(state.subpath_start)
        state.current = state.subpath_start
        state.last_control = None

    else:
        raise SVGParseError(f"Unknown command: {command}")

    return pos, new_polylines


# =============================================================================
# Utility Functions
# =============================================================================

def polylines_bounds(polylines: list[Polyline]) -> tuple[float, float, float, float]:
    """Compute the bounding box of a list of polylines.

    Returns:
        Tuple of (x_min, y_min, x_max, y_max)

    Raises:
        ValueError: If polylines is empty
    """
    if not polylines:
        raise ValueError("Cannot compute bounds of empty polylines")

    x_min = float("inf")
    y_min = float("inf")
    x_max = float("-inf")
    y_max = float("-inf")

    for polyline in polylines:
        for x, y in polyline:
            x_min = min(x_min, x)
            y_min = min(y_min, y)
            x_max = max(x_max, x)
            y_max = max(y_max, y)

    return (x_min, y_min, x_max, y_max)


def scale_polylines(
    polylines: list[Polyline],
    scale_x: float,
    scale_y: float | None = None,
) -> list[Polyline]:
    """Scale polylines by the given factors.

    Args:
        polylines: List of polylines to scale
        scale_x: X scale factor
        scale_y: Y scale factor (defaults to scale_x for uniform scaling)

    Returns:
        New list of scaled polylines
    """
    if scale_y is None:
        scale_y = scale_x

    return [
        [(x * scale_x, y * scale_y) for x, y in polyline]
        for polyline in polylines
    ]


def translate_polylines(
    polylines: list[Polyline],
    dx: float,
    dy: float,
) -> list[Polyline]:
    """Translate polylines by the given offsets.

    Args:
        polylines: List of polylines to translate
        dx: X translation
        dy: Y translation

    Returns:
        New list of translated polylines
    """
    return [
        [(x + dx, y + dy) for x, y in polyline]
        for polyline in polylines
    ]


def center_polylines(polylines: list[Polyline]) -> list[Polyline]:
    """Center polylines around the origin.

    Translates polylines so their bounding box center is at (0, 0).

    Args:
        polylines: List of polylines to center

    Returns:
        New list of centered polylines
    """
    if not polylines:
        return []

    x_min, y_min, x_max, y_max = polylines_bounds(polylines)
    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2

    return translate_polylines(polylines, -cx, -cy)


def normalize_polylines(
    polylines: list[Polyline],
    target_width: float | None = None,
    target_height: float | None = None,
    preserve_aspect: bool = True,
) -> list[Polyline]:
    """Normalize polylines to fit within specified dimensions.

    Centers the polylines and scales them to fit within the target dimensions.
    If preserve_aspect is True, uniform scaling is used to fit within the
    bounding box while maintaining aspect ratio.

    Args:
        polylines: List of polylines to normalize
        target_width: Target width (None = use current width)
        target_height: Target height (None = use current height)
        preserve_aspect: If True, maintain aspect ratio

    Returns:
        New list of normalized polylines
    """
    if not polylines:
        return []

    x_min, y_min, x_max, y_max = polylines_bounds(polylines)
    current_width = x_max - x_min
    current_height = y_max - y_min

    if current_width < 1e-10 or current_height < 1e-10:
        # Degenerate geometry
        return center_polylines(polylines)

    # Determine scale factors
    scale_x = 1.0
    scale_y = 1.0

    if target_width is not None:
        scale_x = target_width / current_width
    if target_height is not None:
        scale_y = target_height / current_height

    if preserve_aspect:
        scale = min(scale_x, scale_y)
        scale_x = scale_y = scale

    # Center, then scale
    centered = center_polylines(polylines)
    return scale_polylines(centered, scale_x, scale_y)


__all__ = [
    "parse_svg_path",
    "parse_svg_file",
    "SVGParseError",
    "Polyline",
    "polylines_bounds",
    "scale_polylines",
    "translate_polylines",
    "center_polylines",
    "normalize_polylines",
]
