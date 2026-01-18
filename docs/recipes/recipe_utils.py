from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from adapters.ast_to_removal import ast_to_removal_intents
from layout_ast.layout import LayoutAST, Item


_FEATURE_STYLES = {
    "profile": {
        "stroke": "#111111",
        "fill": "none",
        "stroke-width": "1.5",
    },
    "pocket": {
        "stroke": "#1d70b8",
        "fill": "#1d70b8",
        "fill-opacity": "0.2",
        "stroke-width": "1.0",
    },
    "engrave": {
        "stroke": "#777777",
        "fill": "none",
        "stroke-width": "1.0",
        "stroke-dasharray": "4,3",
    },
    "bevel": {
        "stroke": "#b84a1b",
        "fill": "#b84a1b",
        "fill-opacity": "0.2",
        "stroke-width": "1.0",
    },
    "chamfer": {
        "stroke": "#2b8a3e",
        "fill": "none",
        "stroke-width": "1.0",
    },
}


def write_recipe_outputs(ast: LayoutAST, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    ast_path = output_dir / "ast.json"
    intents_path = output_dir / "intents.json"
    svg_path = output_dir / "preview.svg"

    ast.to_json(str(ast_path))

    warnings: list[str] = []
    intents = ast_to_removal_intents(ast, warnings=warnings)
    intent_payload = [intent.to_dict() for intent in intents]
    intents_path.write_text(
        json.dumps(intent_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    svg_path.write_text(render_preview_svg(ast), encoding="utf-8")

    print(f"Wrote {ast_path.name}, {intents_path.name}, {svg_path.name} in {output_dir}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")


def render_preview_svg(ast: LayoutAST) -> str:
    sheet = ast.sheet
    margin = 10.0
    viewbox_width = sheet.width_mm + 2 * margin
    viewbox_height = sheet.height_mm + 2 * margin

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {viewbox_width} {viewbox_height}",
            "width": f"{viewbox_width}mm",
            "height": f"{viewbox_height}mm",
        },
    )

    ET.SubElement(
        svg,
        "rect",
        {
            "x": "0",
            "y": "0",
            "width": str(viewbox_width),
            "height": str(viewbox_height),
            "fill": "#ffffff",
        },
    )

    ET.SubElement(
        svg,
        "rect",
        {
            "x": str(margin),
            "y": str(margin),
            "width": str(sheet.width_mm),
            "height": str(sheet.height_mm),
            "stroke": "#cccccc",
            "fill": "none",
            "stroke-width": "1",
        },
    )

    groups: dict[str, ET.Element] = {}

    for item in ast.items:
        if not _is_drawable_item(item):
            continue

        feature_type = item.feature.type
        group = groups.get(feature_type)
        if group is None:
            group = ET.SubElement(svg, "g", {"id": feature_type})
            groups[feature_type] = group

        style = _FEATURE_STYLES.get(feature_type, _FEATURE_STYLES["profile"])
        _render_item(group, item, margin, style)

    ET.indent(svg, space="  ")
    return ET.tostring(svg, encoding="unicode")


def _is_drawable_item(item: Item) -> bool:
    return item.kind == "shape" and item.geometry is not None and item.feature is not None


def _render_item(
    group: ET.Element,
    item: Item,
    offset: float,
    style: dict[str, str],
) -> None:
    shape_type = item.type
    geom = item.geometry.data

    if shape_type == "Polygon":
        points = geom.get("points", [])
        holes = geom.get("holes", [])
        path = _polygon_path(points, holes, offset)
        if not path:
            return
        elem = ET.SubElement(
            group,
            "path",
            {"d": path, "fill-rule": "evenodd"},
        )
        _apply_style(elem, style)
        return

    if shape_type == "Polyline":
        points = geom.get("points", [])
        if not points:
            return
        elem = ET.SubElement(
            group,
            "polyline",
            {"points": _points_attr(points, offset)},
        )
        _apply_style(elem, style)
        return

    if shape_type == "Line":
        start = geom.get("start")
        end = geom.get("end")
        if not start or not end:
            return
        elem = ET.SubElement(
            group,
            "line",
            {
                "x1": _fmt(start[0] + offset),
                "y1": _fmt(start[1] + offset),
                "x2": _fmt(end[0] + offset),
                "y2": _fmt(end[1] + offset),
            },
        )
        _apply_style(elem, style)
        return

    if shape_type == "Rect":
        if item.placement is None:
            return
        w = geom.get("w_mm", 0.0)
        h = geom.get("h_mm", 0.0)
        cx, cy = item.placement.center_xy_mm
        x = offset + cx - w / 2
        y = offset + cy - h / 2
        elem = ET.SubElement(
            group,
            "rect",
            {
                "x": _fmt(x),
                "y": _fmt(y),
                "width": _fmt(w),
                "height": _fmt(h),
            },
        )
        _apply_style(elem, style)
        return

    if shape_type == "Circle":
        if item.placement is None:
            return
        r = geom.get("radius_mm", geom.get("diameter_mm", 0.0) / 2)
        cx, cy = item.placement.center_xy_mm
        elem = ET.SubElement(
            group,
            "circle",
            {
                "cx": _fmt(cx + offset),
                "cy": _fmt(cy + offset),
                "r": _fmt(r),
            },
        )
        _apply_style(elem, style)
        return


def _apply_style(element: ET.Element, style: dict[str, str]) -> None:
    style_str = ";".join(f"{key}:{value}" for key, value in style.items())
    element.set("style", style_str)


def _polygon_path(
    outer: list[list[float]] | list[tuple[float, float]],
    holes: list[list[list[float]]] | list[list[tuple[float, float]]],
    offset: float,
) -> str:
    if not outer:
        return ""

    segments = [_loop_to_path(outer, offset)]
    for hole in holes:
        if hole:
            segments.append(_loop_to_path(hole, offset))
    return " ".join(segments)


def _loop_to_path(loop: list[list[float]] | list[tuple[float, float]], offset: float) -> str:
    first = loop[0]
    parts = [f"M {_fmt(first[0] + offset)} {_fmt(first[1] + offset)}"]
    for x, y in loop[1:]:
        parts.append(f"L {_fmt(x + offset)} {_fmt(y + offset)}")
    parts.append("Z")
    return " ".join(parts)


def _points_attr(points: list[list[float]] | list[tuple[float, float]], offset: float) -> str:
    return " ".join(f"{_fmt(x + offset)},{_fmt(y + offset)}" for x, y in points)


def _fmt(value: float) -> str:
    return f"{value:.3f}"
