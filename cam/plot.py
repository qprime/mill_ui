from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from shapely.geometry import Polygon

from adapters.ast_to_removal import ast_to_removal_intents
from config.machine_loader import MachineConfig
from core.constants import FeatureType, ShapeType
from domains.domain import Bounds2D
from ir.removal_intent import RemovalIntent
from layout_ast.compositional import AtPosition, Circle, ComponentInstance, ProfileGen, Rect, Triangle
from layout_ast.compositional import Polygon as PmlPolygon
from layout_ast.layout import Feature, LayoutAST, Sheet, item_face
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import ResolutionAssertionError, requires_machining_clearance, resolve_layout
from validation.core import Verdict
from validation.machine_checks import check_job_fits_machine

DEFAULT_STROKE_WIDTH_MM = 1.0
PLOT_FEED_MM_MIN = 300.0
POSITION_PRECISION = 3
BOUNDS_TOLERANCE_MM = 1e-9
PREVIEW_PADDING_MM = 2.0
PREVIEW_LABEL_HEIGHT_MM = 6.0
PREVIEW_LABEL_SIZE_MM = 3.0
PREVIEW_LABEL_MIN_WIDTH_MM = 72.0
Point = tuple[float, float]


class PlotError(ValueError):
    pass


@dataclass(frozen=True)
class PlotOptions:
    stroke_width_mm: float = DEFAULT_STROKE_WIDTH_MM
    y_origin: str = "back"
    show_start_label: bool = True

    def __post_init__(self) -> None:
        if not isfinite(self.stroke_width_mm) or self.stroke_width_mm <= 0:
            raise PlotError("Plot stroke width must be finite and positive")
        if self.y_origin not in ("front", "back"):
            raise PlotError("Plot Y origin must be front or back")


@dataclass(frozen=True)
class PlotArtifacts:
    gcode: str
    svg: str
    start: str


@dataclass(frozen=True)
class _Contour:
    points: tuple[Point, ...]
    radius: float | None = None

    @property
    def bounds(self) -> Bounds2D:
        return Bounds2D.from_points(self.points)


def _without_outline_profiles(node: Any) -> Any:
    if isinstance(node, AtPosition):
        return replace(node, child=_without_outline_profiles(node.child))
    if isinstance(node, ComponentInstance):
        return replace(node, body=_without_outline_profiles(node.body))
    children = getattr(node, "children", ())
    if not children:
        return node
    if isinstance(node, (Rect, Circle, PmlPolygon, Triangle)):
        children = tuple(child for child in children if not isinstance(child, ProfileGen))
    return replace(node, children=tuple(_without_outline_profiles(child) for child in children))


def load_plot_pml(source: Path) -> LayoutAST:
    parsed = parse_pml_yaml(source.read_text(encoding="utf-8"))
    if parsed.surface is not None or requires_machining_clearance(parsed.root):
        raise PlotError("Supply one standalone outline without surfacing, beams, or assemblies")
    try:
        return resolve_layout(
            replace(parsed, root=_without_outline_profiles(parsed.root), source_dir=str(source.parent.resolve()))
        )
    except (ResolutionAssertionError, ValueError) as error:
        raise PlotError(str(error)) from error


def _intent(ast: LayoutAST) -> RemovalIntent:
    shapes = tuple(item for item in ast.items if item.kind == "shape")
    if len(shapes) != 1:
        raise PlotError("Plot output requires exactly one shape")
    shape = shapes[0]
    if item_face(shape) != "front" or shape.type not in (ShapeType.RECT, ShapeType.CIRCLE, ShapeType.POLYGON):
        raise PlotError("Plot output supports a single front-face rectangle, circle, or polygon")
    if shape.geometry is not None:
        geometry = shape.geometry
        if geometry.data.get("islands"):
            raise PlotError("Plot output requires one outline without islands")
        if shape.type == ShapeType.CIRCLE and "diameter_mm" not in geometry.data and "radius_mm" in geometry.data:
            shape = replace(
                shape, geometry=replace(geometry, data={**geometry.data, "diameter_mm": 2 * geometry.data["radius_mm"]})
            )
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


def _machine_bounds(bounds: Bounds2D, sheet: Sheet, y_origin: str) -> Bounds2D:
    x0, y0 = _machine_point((bounds.x_min, bounds.y_min), sheet, y_origin)
    x1, y1 = _machine_point((bounds.x_max, bounds.y_max), sheet, y_origin)
    return Bounds2D(x_min=x0, y_min=min(y0, y1), x_max=x1, y_max=max(y0, y1))


def _validate_bounds(
    bounds: Bounds2D, intent: RemovalIntent, sheet: Sheet, machine: MachineConfig, y_origin: str
) -> None:
    margin = sheet.margin_mm
    if not (
        margin - BOUNDS_TOLERANCE_MM <= bounds.x_min < bounds.x_max <= sheet.width_mm - margin + BOUNDS_TOLERANCE_MM
        and margin - BOUNDS_TOLERANCE_MM
        <= bounds.y_min
        < bounds.y_max
        <= sheet.height_mm - margin + BOUNDS_TOLERANCE_MM
    ):
        raise PlotError("Plot contour must fit the sheet working area, including at 0.001 mm output precision")
    for region in intent.constraints.keepouts:
        other = _machine_bounds(region.bounds, sheet, y_origin)
        if (
            bounds.x_min <= other.x_max
            and other.x_min <= bounds.x_max
            and bounds.y_min <= other.y_max
            and other.y_min <= bounds.y_max
        ):
            raise PlotError(f"Plot bounds overlap keepout {region.reason}")
    result = check_job_fits_machine(bounds, machine)
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


def _quantize(point: Point) -> Point:
    x, y = point
    return round(x, POSITION_PRECISION), round(y, POSITION_PRECISION)


def _xy(point: Point) -> str:
    x, y = point
    return f"X{x:.{POSITION_PRECISION}f} Y{y:.{POSITION_PRECISION}f}"


def _rounded_outline(intent: RemovalIntent, sheet: Sheet, y_origin: str) -> _Contour:
    diameter = intent.shape_geometry.diameter_mm
    if intent.shape == ShapeType.CIRCLE:
        if diameter is None or not isfinite(diameter) or diameter <= 0:
            raise PlotError("Plot circle diameter must be finite and positive")
        cx, cy = _quantize(_machine_point(intent.bounds.center, sheet, y_origin))
        radius = round(diameter / 2, POSITION_PRECISION)
        points = tuple(
            _quantize(point) for point in ((cx - radius, cy), (cx, cy - radius), (cx + radius, cy), (cx, cy + radius))
        )
        return _Contour(points, radius)
    points = tuple(_quantize(_machine_point(point, sheet, y_origin)) for point in _polygon_points(intent))
    if not Polygon(points).is_valid:
        raise PlotError("Plot polygon must remain a simple outline at 0.001 mm output precision")
    return _Contour(points)


def _plot_gcode(contour: _Contour) -> str:
    moves = ["G21", "G90", "G17", "G94", "G54", "G91.1", "M5", f"F{PLOT_FEED_MM_MIN:.1f}"]
    start = contour.points[0]
    if contour.radius is None:
        moves.extend(f"G1 {_xy(point)}" for point in (*contour.points, start))
    else:
        opposite = contour.points[2]
        radius = contour.radius
        moves.extend(
            (
                f"G1 {_xy(start)}",
                f"G3 {_xy(opposite)} I{radius:.{POSITION_PRECISION}f} J0",
                f"G3 {_xy(start)} I{-radius:.{POSITION_PRECISION}f} J0",
            )
        )
    return "\n".join((*moves, "M2", ""))


def _plot_svg(contour: _Contour, sheet: Sheet, options: PlotOptions, start: str) -> str:
    bounds = contour.bounds
    padding = options.stroke_width_mm / 2 + PREVIEW_PADDING_MM
    left = min(0.0, bounds.x_min - padding)
    right = max(sheet.width_mm, bounds.x_max + padding)
    top = min(0.0, sheet.height_mm - bounds.y_max - padding)
    bottom = max(sheet.height_mm, sheet.height_mm - bounds.y_min + padding)
    if options.show_start_label:
        top -= PREVIEW_LABEL_HEIGHT_MM
        right = max(right, left + PREVIEW_LABEL_MIN_WIDTH_MM)
    width, height = right - left, bottom - top
    svg = Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{width}mm",
            "height": f"{height}mm",
            "viewBox": f"{left} {top} {width} {height}",
        },
    )
    SubElement(svg, "title").text = start
    outline = SubElement(
        svg,
        "g",
        {
            "transform": f"translate(0,{sheet.height_mm}) scale(1,-1)",
            "fill": "none",
            "stroke": "black",
            "stroke-width": f"{options.stroke_width_mm:g}",
            "stroke-linejoin": "round",
        },
    )
    if contour.radius is None:
        coordinates = " ".join(f"{x:.{POSITION_PRECISION}f},{y:.{POSITION_PRECISION}f}" for x, y in contour.points)
        SubElement(outline, "polygon", {"points": coordinates})
    else:
        SubElement(
            outline,
            "circle",
            {
                "cx": str(contour.points[1][0]),
                "cy": str(contour.points[0][1]),
                "r": f"{contour.radius:.{POSITION_PRECISION}f}",
            },
        )
    if options.show_start_label:
        SubElement(
            svg,
            "text",
            {
                "x": str(left + PREVIEW_PADDING_MM),
                "y": str(top + 2 * PREVIEW_PADDING_MM),
                "font-size": str(PREVIEW_LABEL_SIZE_MM),
            },
        ).text = start
    return tostring(svg, encoding="unicode") + "\n"


def compile_plot(ast: LayoutAST, machine: MachineConfig, options: PlotOptions) -> PlotArtifacts:
    intent = _intent(ast)
    sheet = ast.sheet
    if not all(isfinite(value) for value in (sheet.width_mm, sheet.height_mm, sheet.margin_mm)) or sheet.margin_mm < 0:
        raise PlotError("Plot output requires finite sheet dimensions and a nonnegative margin")
    _validate_bounds(_machine_bounds(intent.bounds, sheet, options.y_origin), intent, sheet, machine, options.y_origin)
    contour = _rounded_outline(intent, sheet, options.y_origin)
    _validate_bounds(contour.bounds, intent, sheet, machine, options.y_origin)
    start = f"Start G54 {_xy(contour.points[0])} mm"
    return PlotArtifacts(_plot_gcode(contour), _plot_svg(contour, sheet, options, start), start)
