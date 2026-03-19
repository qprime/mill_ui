from __future__ import annotations

from layout_ast.compositional import (
    AtPosition,
    Circle,
    CompositionalLayoutAST,
    Panel,
    Polygon,
    Rect,
    RoundedRect,
)
from layout_ast.layout import Item, LayoutAST, Sheet


def _lift_item(item: Item) -> AtPosition | None:
    if item.kind != "shape" or not item.geometry or not item.placement or not item.feature:
        return None

    cx, cy = item.placement.center_xy_mm
    data = item.geometry.data

    if item.type == "Rect":
        w = data["w_mm"]
        h = data["h_mm"]
        rect = Rect(feature=item.feature, id=item.shape_id, label=item.label)
        return AtPosition(x_mm=cx, y_mm=cy, width_mm=w, height_mm=h, child=rect)

    elif item.type == "Circle":
        diameter = data.get("diameter_mm")
        radius = data.get("radius_mm")
        circle = Circle(
            diameter_mm=diameter,
            radius_mm=radius,
            feature=item.feature,
            id=item.shape_id,
            label=item.label,
        )
        size = diameter if diameter else (radius * 2 if radius else None)
        return AtPosition(x_mm=cx, y_mm=cy, width_mm=size, height_mm=size, child=circle)

    elif item.type == "RoundedRect":
        w = data["w_mm"]
        h = data["h_mm"]
        has_per_corner = "radius_tl_mm" in data
        if has_per_corner:
            rtl = data["radius_tl_mm"]
            rtr = data["radius_tr_mm"]
            rbl = data["radius_bl_mm"]
            rbr = data["radius_br_mm"]
            if rtl == rtr == rbl == rbr:
                rr_radius = rtl
                corners = None
            else:
                rr_radius = max(rtl, rtr, rbl, rbr)
                corners = frozenset(c for c, r in [("tl", rtl), ("tr", rtr), ("bl", rbl), ("br", rbr)] if r > 0)
        else:
            rr_radius = data.get("corner_radius_mm", data.get("radius_mm", 0.0))
            corners = None
        rounded_rect = RoundedRect(
            radius_mm=rr_radius,
            feature=item.feature,
            id=item.shape_id,
            label=item.label,
            corners=corners,
        )
        return AtPosition(x_mm=cx, y_mm=cy, width_mm=w, height_mm=h, child=rounded_rect)

    elif item.type == "Polygon":
        points = tuple(tuple(p) for p in data.get("points", []))
        polygon = Polygon(
            points=points,
            feature=item.feature,
            id=item.shape_id,
            label=item.label,
        )
        return AtPosition(x_mm=cx, y_mm=cy, child=polygon)

    return None


def lift_layout_ast(ast: LayoutAST) -> CompositionalLayoutAST:
    sheet = Sheet(
        width_mm=ast.sheet.width_mm,
        height_mm=ast.sheet.height_mm,
        thickness_mm=ast.sheet.thickness_mm,
        margin_mm=ast.sheet.margin_mm,
        gcode_output=ast.sheet.gcode_output,
    )

    children = []
    for item in ast.items:
        node = _lift_item(item)
        if node is not None:
            children.append(node)

    root = Panel(children=tuple(children)) if children else None

    return CompositionalLayoutAST(
        sheet=sheet,
        root=root,
        project=ast.project,
        kerf_width_mm=ast.kerf_width_mm,
    )
