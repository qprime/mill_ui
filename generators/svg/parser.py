from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from domains.domain import Point2D
from generators.svg.curves import (
    flatten_arc,
    flatten_cubic_bezier,
    flatten_quadratic_bezier,
)

Polyline = list[Point2D]


class SVGParseError(ValueError):
    def __init__(self, message: str, position: int | None = None):
        self.position = position
        if position is not None:
            message = f"{message} (at position {position})"
        super().__init__(message)


@dataclass
class ParseState:
    current: Point2D = (0.0, 0.0)
    subpath_start: Point2D = (0.0, 0.0)
    last_control: Point2D | None = None
    last_command: str = ""


def parse_svg_path(
    path_data: str,
    tolerance: float = 0.1,
) -> list[Polyline]:
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
            if state.last_command in ("M", "m"):
                command = "L" if state.last_command == "M" else "l"
            else:
                command = state.last_command

            if not command:
                raise SVGParseError(f"Unexpected number without command: {token}")

        try:
            i, new_polylines = _execute_command(command, tokens, i, state, current_polyline, tolerance)
        except (IndexError, ValueError) as e:
            raise SVGParseError(f"Error parsing command '{command}': {e}") from e

        if new_polylines:
            for poly in new_polylines[:-1]:
                if poly and len(poly) >= 2:
                    polylines.append(poly)

            current_polyline = new_polylines[-1] if new_polylines else []

        state.last_command = command

    if current_polyline and len(current_polyline) >= 2:
        polylines.append(current_polyline)

    return polylines


def parse_svg_file(
    file_path: str,
    tolerance: float = 0.1,
) -> list[Polyline]:
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as e:
        raise SVGParseError(f"Invalid SVG file: {e}") from e

    root = tree.getroot()

    ns = {"svg": "http://www.w3.org/2000/svg"}

    paths = root.findall(".//path") + root.findall(".//svg:path", ns)

    all_polylines: list[Polyline] = []

    for path_elem in paths:
        d = path_elem.get("d")
        if d:
            polylines = parse_svg_path(d, tolerance)
            all_polylines.extend(polylines)

    return all_polylines


_NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


_COMMAND_PATTERN = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]")


def _tokenize(path_data: str) -> list[str | float]:
    tokens: list[str | float] = []
    pos = 0

    while pos < len(path_data):
        while pos < len(path_data) and path_data[pos] in " \t\n\r,":
            pos += 1

        if pos >= len(path_data):
            break

        char = path_data[pos]

        if char.isalpha():
            tokens.append(char)
            pos += 1
            continue

        match = _NUMBER_PATTERN.match(path_data, pos)
        if match:
            num_str = match.group()
            try:
                tokens.append(float(num_str))
            except ValueError as err:
                raise SVGParseError(f"Invalid number: {num_str}", pos) from err
            pos = match.end()
            continue

        raise SVGParseError(f"Unexpected character: '{char}'", pos)

    return tokens


def _get_numbers(tokens: list, start: int, count: int) -> tuple[list[float], int]:
    numbers: list[float] = []
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


def _execute_command(
    command: str,
    tokens: list,
    pos: int,
    state: ParseState,
    current_polyline: Polyline,
    tolerance: float,
) -> tuple[int, list[Polyline]]:
    new_polylines: list[Polyline] = []
    is_relative = command.islower()
    cmd_upper = command.upper()

    if cmd_upper == "M":
        args, pos = _get_numbers(tokens, pos, 2)
        x, y = args[0], args[1]

        if is_relative:
            x += state.current[0]
            y += state.current[1]

        if current_polyline and len(current_polyline) >= 2:
            new_polylines.append(current_polyline)

        state.current = (x, y)
        state.subpath_start = (x, y)
        state.last_control = None
        new_polylines.append([state.current])

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
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 1)
            x = args[0]
            if is_relative:
                x += state.current[0]
            state.current = (x, state.current[1])
            current_polyline.append(state.current)
            state.last_control = None

    elif cmd_upper == "V":
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 1)
            y = args[0]
            if is_relative:
                y += state.current[1]
            state.current = (state.current[0], y)
            current_polyline.append(state.current)
            state.last_control = None

    elif cmd_upper == "C":
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 6)
            x1, y1, x2, y2, x, y = args

            if is_relative:
                cx, cy = state.current
                x1, y1 = x1 + cx, y1 + cy
                x2, y2 = x2 + cx, y2 + cy
                x, y = x + cx, y + cy

            points = flatten_cubic_bezier(state.current, (x1, y1), (x2, y2), (x, y), tolerance)
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x2, y2)

    elif cmd_upper == "S":
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 4)
            x2, y2, x, y = args

            if is_relative:
                cx, cy = state.current
                x2, y2 = x2 + cx, y2 + cy
                x, y = x + cx, y + cy

            if state.last_control and state.last_command.upper() in ("C", "S"):
                x1 = 2 * state.current[0] - state.last_control[0]
                y1 = 2 * state.current[1] - state.last_control[1]
            else:
                x1, y1 = state.current

            points = flatten_cubic_bezier(state.current, (x1, y1), (x2, y2), (x, y), tolerance)
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x2, y2)

    elif cmd_upper == "Q":
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 4)
            x1, y1, x, y = args

            if is_relative:
                cx, cy = state.current
                x1, y1 = x1 + cx, y1 + cy
                x, y = x + cx, y + cy

            points = flatten_quadratic_bezier(state.current, (x1, y1), (x, y), tolerance)
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x1, y1)

    elif cmd_upper == "T":
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 2)
            x, y = args

            if is_relative:
                x += state.current[0]
                y += state.current[1]

            if state.last_control and state.last_command.upper() in ("Q", "T"):
                x1 = 2 * state.current[0] - state.last_control[0]
                y1 = 2 * state.current[1] - state.last_control[1]
            else:
                x1, y1 = state.current

            points = flatten_quadratic_bezier(state.current, (x1, y1), (x, y), tolerance)
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = (x1, y1)

    elif cmd_upper == "A":
        while pos < len(tokens) and isinstance(tokens[pos], (int, float)):
            args, pos = _get_numbers(tokens, pos, 7)
            rx, ry, x_rot, large_arc_flag, sweep_flag, x, y = args

            large_arc = large_arc_flag != 0
            sweep = sweep_flag != 0

            x_rot_rad = math.radians(x_rot)

            if is_relative:
                x += state.current[0]
                y += state.current[1]

            points = flatten_arc(state.current, rx, ry, x_rot_rad, large_arc, sweep, (x, y), tolerance)
            current_polyline.extend(points)
            state.current = (x, y)
            state.last_control = None

    elif cmd_upper == "Z":
        if state.current != state.subpath_start:
            current_polyline.append(state.subpath_start)
        state.current = state.subpath_start
        state.last_control = None

    else:
        raise SVGParseError(f"Unknown command: {command}")

    return pos, new_polylines


def polylines_bounds(polylines: list[Polyline]) -> tuple[float, float, float, float]:
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
    if scale_y is None:
        scale_y = scale_x

    return [[(x * scale_x, y * scale_y) for x, y in polyline] for polyline in polylines]


def translate_polylines(
    polylines: list[Polyline],
    dx: float,
    dy: float,
) -> list[Polyline]:
    return [[(x + dx, y + dy) for x, y in polyline] for polyline in polylines]


def center_polylines(polylines: list[Polyline]) -> list[Polyline]:
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
    if not polylines:
        return []

    x_min, y_min, x_max, y_max = polylines_bounds(polylines)
    current_width = x_max - x_min
    current_height = y_max - y_min

    if current_width < 1e-10 or current_height < 1e-10:
        return center_polylines(polylines)

    scale_x = 1.0
    scale_y = 1.0

    if target_width is not None:
        scale_x = target_width / current_width
    if target_height is not None:
        scale_y = target_height / current_height

    if preserve_aspect:
        scale = min(scale_x, scale_y)
        scale_x = scale_y = scale

    centered = center_polylines(polylines)
    return scale_polylines(centered, scale_x, scale_y)


__all__ = [
    "Polyline",
    "SVGParseError",
    "center_polylines",
    "normalize_polylines",
    "parse_svg_file",
    "parse_svg_path",
    "polylines_bounds",
    "scale_polylines",
    "translate_polylines",
]
