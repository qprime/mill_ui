from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from xml.etree.ElementTree import Element, SubElement, tostring

from shapely.geometry import Polygon

from adapters.ast_to_removal import ast_to_removal_intents
from config.machine_loader import MachineConfig
from core.constants import FeatureType, ShapeType
from domains.domain import Bounds2D
from ir.removal_intent import RemovalIntent
from layout_ast.layout import Feature, LayoutAST, Sheet, item_face
from validation.core import Verdict
from validation.machine_checks import check_job_fits_machine

DEFAULT_STROKE_WIDTH_MM = 1.0
PLOT_FEED_MM_MIN = 300.0
Point = tuple[float, float]


class PlotError(ValueError):
    pass


@dataclass(frozen=True)
class PlotOptions:
    stroke_width_mm: float = DEFAULT_STROKE_WIDTH_MM
    y_origin: str = "back"

    def __post_init__(self) -> None:
        if not isfinite(self.stroke_width_mm) or self.stroke_width_mm <= 0:
            raise PlotError("Plot stroke width must be finite and positive")
        if self.y_origin not in ("front", "back"):
            raise PlotError("Plot Y origin must be front or back")


@dataclass(frozen=True)
class PlotArtifacts:
    gcode: str
    svg: str


def _intent(ast: LayoutAST) -> RemovalIntent:
    shapes = tuple(item for item in ast.items if item.kind == "shape")
    if len(shapes) != 1:
        raise PlotError("Plot output requires exactly one shape")
    shape = shapes[0]
    if item_face(shape) != "front" or shape.type not in (ShapeType.RECT, ShapeType.CIRCLE, ShapeType.POLYGON):
        raise PlotError("Plot output supports a single front-face rectangle, circle, or polygon")
    nominal = replace(shape, feature=Feature(type=FeatureType.PROFILE, side="on", depth_mm=0.0))
    items = (nominal, *(item for item in ast.items if item.kind == "keepout"))
    warnings: list[str] = []
    intents = ast_to_removal_intents(replace(ast, items=items), warnings=warnings)
    if len(intents) != 1 or warnings:
        raise PlotError("; ".join(warnings) or "Unable to resolve the plot contour")
    return intents[0]


def _machine_point(point: Point, sheet: Sheet, y_origin: str) -> Point:
    x, y = point
    y += sheet.margin_mm
    return x + sheet.margin_mm, sheet.height_mm - y if y_origin == "front" else y


def _validate_bounds(intent: RemovalIntent, ast: LayoutAST, machine: MachineConfig, options: PlotOptions) -> None:
    bounds, sheet = intent.bounds, ast.sheet
    if not (
        0 <= bounds.x_min < bounds.x_max <= sheet.working_width_mm
        and 0 <= bounds.y_min < bounds.y_max <= sheet.working_height_mm
    ):
        raise PlotError("Plot contour must fit the sheet working area")
    for region in intent.constraints.keepouts:
        other = region.bounds
        if (
            bounds.x_min <= other.x_max
            and other.x_min <= bounds.x_max
            and bounds.y_min <= other.y_max
            and other.y_min <= bounds.y_max
        ):
            raise PlotError(f"Plot bounds overlap keepout {region.reason}")
    x0, y0 = _machine_point((bounds.x_min, bounds.y_min), sheet, options.y_origin)
    x1, y1 = _machine_point((bounds.x_max, bounds.y_max), sheet, options.y_origin)
    physical = Bounds2D(x_min=x0, y_min=min(y0, y1), x_max=x1, y_max=max(y0, y1))
    result = check_job_fits_machine(physical, machine)
    if result.status is Verdict.FAIL:
        raise PlotError(". ".join(result.failures))


def _polygon_points(intent: RemovalIntent) -> tuple[Point, ...]:
    bounds = intent.bounds
    if intent.shape == ShapeType.RECT:
        return (
            (bounds.x_min, bounds.y_min),
            (bounds.x_max, bounds.y_min),
            (bounds.x_max, bounds.y_max),
            (bounds.x_min, bounds.y_max),
        )
    geometry = intent.shape_geometry
    if not geometry.points or len(geometry.points) < 3 or geometry.holes:
        raise PlotError("A plot polygon requires one simple outline")
    cx, cy = bounds.center
    points = tuple((x + cx, y + cy) for x, y in geometry.points)
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise PlotError("A plot polygon requires one simple outline")
    return points


def _xy(point: Point) -> str:
    x, y = point
    return f"X{x:.3f} Y{y:.3f}"


def _polygon_plot(moves: list[str], svg: Element, points: tuple[Point, ...], sheet: Sheet) -> None:
    for point in (*points, points[0]):
        moves.append(f"G1 {_xy(point)}")
    coordinates = " ".join(f"{x:.3f},{sheet.height_mm - y:.3f}" for x, y in points)
    SubElement(svg, "polygon", {"points": coordinates})


def _circle_plot(moves: list[str], svg: Element, center: Point, diameter: float, sheet: Sheet) -> None:
    cx, cy = center
    radius = diameter / 2
    if not isfinite(radius) or radius <= 0:
        raise PlotError("Plot circle radius must be finite and positive")
    left, right = (cx - radius, cy), (cx + radius, cy)
    moves.extend((f"G1 {_xy(left)}", f"G3 {_xy(right)} I{radius:.3f} J0", f"G3 {_xy(left)} I{-radius:.3f} J0"))
    SubElement(svg, "circle", {"cx": f"{cx:.3f}", "cy": f"{sheet.height_mm - cy:.3f}", "r": f"{radius:.3f}"})


def compile_plot(ast: LayoutAST, machine: MachineConfig, options: PlotOptions) -> PlotArtifacts:
    intent = _intent(ast)
    _validate_bounds(intent, ast, machine, options)
    sheet = ast.sheet
    moves = ["G21", "G90", "G17", "G94", "G54", "G91.1", "M5", f"F{PLOT_FEED_MM_MIN:.1f}"]
    svg = Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{sheet.width_mm:g}mm",
            "height": f"{sheet.height_mm:g}mm",
            "viewBox": f"0 0 {sheet.width_mm:g} {sheet.height_mm:g}",
            "fill": "none",
            "stroke": "black",
            "stroke-width": f"{options.stroke_width_mm:g}",
        },
    )
    diameter = intent.shape_geometry.diameter_mm
    if intent.shape == ShapeType.CIRCLE and diameter is not None:
        center = _machine_point(intent.bounds.center, sheet, options.y_origin)
        _circle_plot(moves, svg, center, diameter, sheet)
    else:
        points = tuple(_machine_point(p, sheet, options.y_origin) for p in _polygon_points(intent))
        _polygon_plot(moves, svg, points, sheet)
    moves.append("M2")
    return PlotArtifacts("\n".join(moves) + "\n", tostring(svg, encoding="unicode") + "\n")
