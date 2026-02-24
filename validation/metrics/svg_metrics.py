from __future__ import annotations

import contextlib
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, cast

from validation.core import round_metric

SVG_NS = "{http://www.w3.org/2000/svg}"


SEMANTIC_LAYERS = [
    "SHEET_OUTLINE",
    "PROFILE_CUTS",
    "POCKET_REGIONS",
    "ENGRAVE_PATHS",
    "HOLES",
    "CONSTRUCTION",
    "DIMENSIONS",
    "NOTES",
    "TITLE_BLOCK",
    "LEGEND",
]


@dataclass
class DocumentMetrics:
    width_mm: float = 0.0
    height_mm: float = 0.0
    viewbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_mm": round_metric(self.width_mm),
            "height_mm": round_metric(self.height_mm),
            "viewbox": [round_metric(v) for v in self.viewbox],
        }


@dataclass
class ElementGeometry:
    element_type: str
    bounds: tuple[float, float, float, float]
    center: tuple[float, float]

    width: float | None = None
    height: float | None = None

    radius: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "element_type": self.element_type,
            "bounds": [round_metric(v) for v in self.bounds],
            "center": [round_metric(v) for v in self.center],
        }
        if self.width is not None:
            d["width"] = round_metric(self.width)
        if self.height is not None:
            d["height"] = round_metric(self.height)
        if self.radius is not None:
            d["radius"] = round_metric(self.radius)
        return d


@dataclass
class LayerMetrics:
    name: str = ""
    element_count: int = 0
    rect_count: int = 0
    circle_count: int = 0
    path_count: int = 0
    line_count: int = 0
    polygon_count: int = 0
    text_count: int = 0

    elements: list[ElementGeometry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_count": self.element_count,
            "rect_count": self.rect_count,
            "circle_count": self.circle_count,
            "path_count": self.path_count,
            "line_count": self.line_count,
            "polygon_count": self.polygon_count,
            "text_count": self.text_count,
            "elements": [e.to_dict() for e in self.elements],
        }


@dataclass
class PathMetrics:
    total_count: int = 0
    closed_count: int = 0
    open_count: int = 0
    total_length_mm: float = 0.0
    by_layer: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "closed_count": self.closed_count,
            "open_count": self.open_count,
            "total_length_mm": round_metric(self.total_length_mm),
            "by_layer": self.by_layer,
        }


@dataclass
class BoundsMetrics:
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_min": round_metric(self.x_min),
            "x_max": round_metric(self.x_max),
            "y_min": round_metric(self.y_min),
            "y_max": round_metric(self.y_max),
        }


@dataclass
class TextMetrics:
    count: int = 0
    dimension_labels: list[str] = field(default_factory=list)
    depth_annotations: list[str] = field(default_factory=list)
    notes_text: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "dimension_labels": sorted(self.dimension_labels),
            "depth_annotations": sorted(self.depth_annotations),
            "notes_text": self.notes_text,
        }


@dataclass
class CircleMetrics:
    count: int = 0
    radii_mm: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "radii_mm": sorted([round_metric(r) for r in self.radii_mm]),
        }


@dataclass
class RectMetrics:
    count: int = 0
    dimensions: list[tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "dimensions": sorted([(round_metric(w), round_metric(h)) for w, h in self.dimensions]),
        }


@dataclass
class SVGMetrics:
    version: str = "1.0.0"
    extraction_time_ms: float = 0.0

    document: DocumentMetrics = field(default_factory=DocumentMetrics)
    layers: dict[str, LayerMetrics] = field(default_factory=dict)
    paths: PathMetrics = field(default_factory=PathMetrics)
    bounds: BoundsMetrics = field(default_factory=BoundsMetrics)
    text: TextMetrics = field(default_factory=TextMetrics)
    circles: CircleMetrics = field(default_factory=CircleMetrics)
    rects: RectMetrics = field(default_factory=RectMetrics)

    layer_count: int = 0
    layer_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "svg": {
                "version": self.version,
                "extraction_time_ms": round_metric(self.extraction_time_ms, 2),
                "document": self.document.to_dict(),
                "layers": {
                    "count": self.layer_count,
                    "names": sorted(self.layer_names),
                    "by_layer": {name: metrics.to_dict() for name, metrics in sorted(self.layers.items())},
                },
                "paths": self.paths.to_dict(),
                "bounds": self.bounds.to_dict(),
                "text_elements": self.text.to_dict(),
                "circles": self.circles.to_dict(),
                "rects": self.rects.to_dict(),
            }
        }


def extract_svg_metrics(svg_content: str | bytes) -> SVGMetrics:
    start_time = time.perf_counter()

    if isinstance(svg_content, bytes):
        svg_content = svg_content.decode("utf-8")

    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError as e:
        raise ValueError(f"Invalid SVG: {e}") from e

    metrics = SVGMetrics()

    metrics.document = _extract_document_metrics(root)

    metrics.layers, metrics.layer_names = _extract_layer_metrics(root)
    metrics.layer_count = len(metrics.layer_names)

    metrics.paths = _extract_path_metrics(root, metrics.layers)

    metrics.bounds = _extract_bounds(root)

    metrics.text = _extract_text_metrics(root)

    metrics.circles = _extract_circle_metrics(root)

    metrics.rects = _extract_rect_metrics(root)

    metrics.extraction_time_ms = (time.perf_counter() - start_time) * 1000

    return metrics


def extract_svg_metrics_from_file(file_path: str) -> SVGMetrics:
    with open(file_path, encoding="utf-8") as f:
        return extract_svg_metrics(f.read())


def _extract_document_metrics(root: ET.Element) -> DocumentMetrics:
    metrics = DocumentMetrics()

    width_str = root.get("width", "0")
    height_str = root.get("height", "0")
    metrics.width_mm = _parse_dimension(width_str)
    metrics.height_mm = _parse_dimension(height_str)

    viewbox_str = root.get("viewBox", "0 0 0 0")

    parts = re.split(r"[\s,]+", viewbox_str.strip())
    if len(parts) == 4:
        with contextlib.suppress(ValueError):
            metrics.viewbox = cast(tuple[float, float, float, float], tuple(float(p) for p in parts))

    return metrics


def _extract_layer_metrics(
    root: ET.Element,
) -> tuple[dict[str, LayerMetrics], list[str]]:
    layers: dict[str, LayerMetrics] = {}
    layer_names: list[str] = []

    geometry_layers = {
        "PROFILE_CUTS",
        "POCKET_REGIONS",
        "HOLES",
        "ENGRAVE_PATHS",
        "SHEET_OUTLINE",
    }

    for group in root.iter(f"{SVG_NS}g"):
        layer_id = group.get("id")
        if not layer_id:
            continue

        layer_names.append(layer_id)
        layer = LayerMetrics(name=layer_id)
        extract_geometry = layer_id in geometry_layers

        for child in group:
            tag = child.tag.replace(SVG_NS, "")
            layer.element_count += 1

            if tag == "rect":
                layer.rect_count += 1
                if extract_geometry:
                    geom = _extract_rect_geometry(child)
                    if geom:
                        layer.elements.append(geom)
            elif tag == "circle":
                layer.circle_count += 1
                if extract_geometry:
                    geom = _extract_circle_geometry(child)
                    if geom:
                        layer.elements.append(geom)
            elif tag == "path":
                layer.path_count += 1
                if extract_geometry:
                    geom = _extract_path_geometry(child)
                    if geom:
                        layer.elements.append(geom)
            elif tag == "line":
                layer.line_count += 1
            elif tag == "polygon":
                layer.polygon_count += 1
            elif tag == "text":
                layer.text_count += 1

        layers[layer_id] = layer

    return layers, layer_names


def _extract_rect_geometry(elem: ET.Element) -> ElementGeometry | None:
    try:
        x = float(elem.get("x", 0))
        y = float(elem.get("y", 0))
        w = float(elem.get("width", 0))
        h = float(elem.get("height", 0))
        if w <= 0 or h <= 0:
            return None
        return ElementGeometry(
            element_type="rect",
            bounds=(x, y, x + w, y + h),
            center=(x + w / 2, y + h / 2),
            width=w,
            height=h,
        )
    except (ValueError, TypeError):
        return None


def _extract_circle_geometry(elem: ET.Element) -> ElementGeometry | None:
    try:
        cx = float(elem.get("cx", 0))
        cy = float(elem.get("cy", 0))
        r = float(elem.get("r", 0))
        if r <= 0:
            return None
        return ElementGeometry(
            element_type="circle",
            bounds=(cx - r, cy - r, cx + r, cy + r),
            center=(cx, cy),
            radius=r,
        )
    except (ValueError, TypeError):
        return None


def _extract_path_geometry(elem: ET.Element) -> ElementGeometry | None:
    d = elem.get("d", "")
    if not d:
        return None

    numbers = re.findall(r"-?\d+\.?\d*", d)
    if len(numbers) < 4:
        return None
    try:
        coords = [float(n) for n in numbers]

        x_coords = [coords[i] for i in range(0, len(coords), 2)]
        y_coords = [coords[i] for i in range(1, len(coords), 2)]
        if not x_coords or not y_coords:
            return None
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        return ElementGeometry(
            element_type="path",
            bounds=(x_min, y_min, x_max, y_max),
            center=((x_min + x_max) / 2, (y_min + y_max) / 2),
        )
    except (ValueError, TypeError):
        return None


def _extract_path_metrics(root: ET.Element, layers: dict[str, LayerMetrics]) -> PathMetrics:
    metrics = PathMetrics()

    for group in root.iter(f"{SVG_NS}g"):
        layer_id = group.get("id")
        if not layer_id:
            continue

        layer_paths = {
            "count": 0,
            "closed": 0,
            "length_mm": 0.0,
        }

        for path in group.iter(f"{SVG_NS}path"):
            d = path.get("d", "")
            metrics.total_count += 1
            layer_paths["count"] += 1

            if d.strip().upper().endswith("Z"):
                metrics.closed_count += 1
                layer_paths["closed"] += 1
            else:
                metrics.open_count += 1

            length = _estimate_path_length(d)
            metrics.total_length_mm += length
            layer_paths["length_mm"] += length

        if layer_paths["count"] > 0:
            metrics.by_layer[layer_id] = {
                "count": layer_paths["count"],
                "closed": layer_paths["closed"],
                "length_mm": round_metric(layer_paths["length_mm"]),
            }

    for layer_id in ["PROFILE_CUTS", "POCKET_REGIONS", "SHEET_OUTLINE"]:
        if layer_id in layers:
            rect_count = layers[layer_id].rect_count
            if rect_count > 0:
                metrics.total_count += rect_count
                metrics.closed_count += rect_count
                if layer_id not in metrics.by_layer:
                    metrics.by_layer[layer_id] = {
                        "count": 0,
                        "closed": 0,
                        "length_mm": 0.0,
                    }
                metrics.by_layer[layer_id]["count"] += rect_count
                metrics.by_layer[layer_id]["closed"] += rect_count

    return metrics


def _extract_bounds(root: ET.Element) -> BoundsMetrics:
    x_values: list[float] = []
    y_values: list[float] = []

    for rect in root.iter(f"{SVG_NS}rect"):
        parent = _find_parent_group(root, rect)
        if parent is None:
            fill = rect.get("fill", "")

            if fill.startswith("#") and fill != "none":
                continue

        x = float(rect.get("x", 0))
        y = float(rect.get("y", 0))
        w = float(rect.get("width", 0))
        h = float(rect.get("height", 0))
        x_values.extend([x, x + w])
        y_values.extend([y, y + h])

    for circle in root.iter(f"{SVG_NS}circle"):
        cx = float(circle.get("cx", 0))
        cy = float(circle.get("cy", 0))
        r = float(circle.get("r", 0))
        x_values.extend([cx - r, cx + r])
        y_values.extend([cy - r, cy + r])

    for line in root.iter(f"{SVG_NS}line"):
        x1 = float(line.get("x1", 0))
        y1 = float(line.get("y1", 0))
        x2 = float(line.get("x2", 0))
        y2 = float(line.get("y2", 0))
        x_values.extend([x1, x2])
        y_values.extend([y1, y2])

    if not x_values or not y_values:
        return BoundsMetrics()

    return BoundsMetrics(
        x_min=min(x_values),
        x_max=max(x_values),
        y_min=min(y_values),
        y_max=max(y_values),
    )


def _extract_text_metrics(root: ET.Element) -> TextMetrics:
    metrics = TextMetrics()

    dimension_pattern = re.compile(r"(\d+\.?\d*)\s*mm")
    depth_pattern = re.compile(r"(pocket|hole|engrave).*?(\d+\.?\d*)", re.IGNORECASE)

    for text in root.iter(f"{SVG_NS}text"):
        metrics.count += 1
        content = _get_text_content(text)

        if not content:
            continue

        dim_match = dimension_pattern.search(content)
        if dim_match and "mm" in content:
            metrics.dimension_labels.append(content.strip())

        depth_match = depth_pattern.search(content)
        if depth_match:
            metrics.depth_annotations.append(content.strip())

        parent = _find_parent_group(root, text)
        if parent is not None and parent.get("id") == "NOTES":
            metrics.notes_text.append(content.strip())

    return metrics


def _extract_circle_metrics(root: ET.Element) -> CircleMetrics:
    metrics = CircleMetrics()

    for circle in root.iter(f"{SVG_NS}circle"):
        metrics.count += 1
        r = float(circle.get("r", 0))
        metrics.radii_mm.append(r)

    return metrics


def _extract_rect_metrics(root: ET.Element) -> RectMetrics:
    metrics = RectMetrics()

    for rect in root.iter(f"{SVG_NS}rect"):
        parent = _find_parent_group(root, rect)
        if parent is None:
            fill = rect.get("fill", "")
            if fill.startswith("#") and fill != "none":
                continue

        w = float(rect.get("width", 0))
        h = float(rect.get("height", 0))
        if w > 0 and h > 0:
            metrics.count += 1
            metrics.dimensions.append((w, h))

    return metrics


def _parse_dimension(value: str) -> float:
    if not value:
        return 0.0

    value = value.strip()
    for unit in ["mm", "px", "pt", "in", "cm"]:
        if value.endswith(unit):
            value = value[: -len(unit)]
            break
    try:
        return float(value)
    except ValueError:
        return 0.0


def _estimate_path_length(d: str) -> float:

    numbers = re.findall(r"-?\d+\.?\d*", d)
    if len(numbers) < 4:
        return 0.0

    total_length = 0.0
    coords = [float(n) for n in numbers]

    for i in range(0, len(coords) - 1, 2):
        if i + 3 < len(coords):
            dx = abs(coords[i + 2] - coords[i])
            dy = abs(coords[i + 3] - coords[i + 1])
            total_length += (dx**2 + dy**2) ** 0.5

    return total_length


def _get_text_content(text_elem: ET.Element) -> str:
    content = text_elem.text or ""
    for child in text_elem:
        if child.text:
            content += child.text
        if child.tail:
            content += child.tail
    if text_elem.tail:
        content += text_elem.tail
    return content.strip()


def _find_parent_group(root: ET.Element, target: ET.Element) -> ET.Element | None:
    for group in root.iter(f"{SVG_NS}g"):
        for child in group:
            if child is target:
                return group

            for nested in child.iter():
                if nested is target:
                    return group
    return None
