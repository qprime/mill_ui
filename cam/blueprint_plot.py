from __future__ import annotations

from math import isclose, isfinite
from pathlib import Path
from xml.etree.ElementTree import Element, ParseError, parse

from cam.plot import PlotError
from core.constants import ShapeType
from generators.svg.parser import SVGParseError, parse_svg_path
from layout_ast.layout import Geometry, Item, LayoutAST, Placement, Sheet

SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
PATH_TOLERANCE_MM = 0.05


def _length_mm(value: str) -> float:
    if not value.endswith("mm"):
        raise PlotError("Blueprint width and height must be in millimeters")
    try:
        length = float(value[:-2])
    except ValueError as error:
        raise PlotError("Blueprint width and height must be numeric") from error
    if not isfinite(length) or length <= 0:
        raise PlotError("Blueprint width and height must be finite and positive")
    return length


def _scale(root: Element) -> float:
    try:
        box = tuple(float(value) for value in root.get("viewBox", "").replace(",", " ").split())
    except ValueError as error:
        raise PlotError("Blueprint requires a numeric viewBox") from error
    if len(box) != 4 or not all(isfinite(value) for value in box):
        raise PlotError("Blueprint requires a finite viewBox")
    _, _, width, height = box
    if width <= 0 or height <= 0:
        raise PlotError("Blueprint viewBox dimensions must be positive")
    scale = _length_mm(root.get("width", "")) / width
    y_scale = _length_mm(root.get("height", "")) / height
    if not isfinite(scale) or scale <= 0 or not isclose(scale, y_scale):
        raise PlotError("Blueprint requires the same physical scale on both axes")
    return scale


def _path_by_id(root: Element, stroke_id: str) -> Element:
    candidates = [item for item in root.iter() if item.get("id") == stroke_id]
    if not stroke_id or len(candidates) != 1:
        raise PlotError(f"Select exactly one blueprint stroke ID: {stroke_id!r}")
    path = candidates[0]
    if path.tag != f"{SVG_NAMESPACE}path":
        raise PlotError(f"Blueprint stroke {stroke_id!r} must be a path")
    parents = {child: item for item in root.iter() for child in item}
    item = path
    while True:
        if item.get("transform") or (item is not root and item.tag == f"{SVG_NAMESPACE}svg"):
            raise PlotError("The selected blueprint stroke uses an unsupported transform")
        if item is root:
            return path
        item = parents[item]


def load_blueprint_outline(source: Path, stroke_id: str) -> LayoutAST:
    try:
        root = parse(source).getroot()
    except ParseError as error:
        raise PlotError(f"Invalid blueprint SVG: {error}") from error
    if root.tag != f"{SVG_NAMESPACE}svg":
        raise PlotError("Blueprint requires an SVG root")
    path = _path_by_id(root, stroke_id)
    scale = _scale(root)
    try:
        outlines = parse_svg_path(path.get("d", ""), tolerance=PATH_TOLERANCE_MM / scale)
    except SVGParseError as error:
        raise PlotError(f"Invalid blueprint stroke: {error}") from error
    if len(outlines) != 1 or outlines[0][0] != outlines[0][-1]:
        raise PlotError("The selected blueprint stroke must be one closed outline")
    points = outlines[0][:-1]
    if len(points) < 3 or not all(isfinite(value) for point in points for value in point):
        raise PlotError("The selected outline requires at least three finite points")
    x_min, x_max = min(p[0] for p in points), max(p[0] for p in points)
    y_min, y_max = min(p[1] for p in points), max(p[1] for p in points)
    width, height = (x_max - x_min) * scale, (y_max - y_min) * scale
    if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0:
        raise PlotError("The selected outline has invalid physical dimensions")
    center = width / 2, height / 2
    local = tuple(((x - x_min) * scale - center[0], (y_max - y) * scale - center[1]) for x, y in points)
    shape = Item("shape", ShapeType.POLYGON, Geometry({"points": local}), Placement(center), shape_id=stroke_id)
    return LayoutAST(Sheet(width, height, 1.0), (shape,))
