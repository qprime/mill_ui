from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from layout_ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    Split,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    Circle,
    RoundedRect,
    Line,
    Polyline,
    SplinePath,
    Keepout,
    Edge,
    CompositionalLayoutAST,
    ProfileGen,
    PocketGen,
    RaisedPanelGen,
    ChamferGen,
    WaveGen,
    SplitHorizontal,
    SplitVertical,
    SplitGrid,
    LinesGen,
    ConcentricBorderGen,
    SplitHorizontalGaps,
    AtPosition,
    Subtract,
    Arch,
    Polygon,
    Triangle,
    XPanelGen,
    HoleGridGen,
    TemplateDef,
    MeasurementGridGen,
    MeasurementEdgeGen,
    EngraveTextGen,
    WasteCuts,
    Assembly,
    InterfaceConfig,
)
from layout_ast.layout import Sheet, Feature
from pml.nest_parser import NestJob, NestPart, NestParseError


class PMLParseError(Exception):
    def __init__(self, message: str, path: str = ""):
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


def parse_dimension(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.match(r'^(-?[\d.]+)\s*mm$', value.strip())
        if match:
            return float(match.group(1))
        try:
            return float(value)
        except ValueError:
            pass
    raise ValueError(f"Invalid dimension: {value}")


def parse_dimension_or_through(value: Any) -> float | str:
    if value == "through":
        return "through"
    return parse_dimension(value)


def parse_children(children_data: list[dict] | None, path: str = "") -> tuple[Any, ...]:
    if not children_data:
        return ()
    return tuple(parse_node(child, f"{path}.children[{i}]") for i, child in enumerate(children_data))


def parse_feature(data: dict, path: str = "") -> Feature:
    feature_type = data.get("type")
    if feature_type is None:
        raise PMLParseError("Feature missing 'type'", path)

    depth = data.get("depth", "through")
    if depth != "through":
        depth = str(parse_dimension(depth))

    depth_mm = None
    if depth != "through":
        depth_mm = float(depth)

    return Feature(
        type=feature_type,
        depth=depth,
        side=data.get("side"),
        depth_mm=depth_mm,
        corner_cleanup_tool_diameter_mm=parse_dimension(data["corner_cleanup"]) if "corner_cleanup" in data else None,
        tab_count=data.get("tab_count"),
        tab_height_mm=parse_dimension(data["tab_height"]) if "tab_height" in data else None,
        tab_width_mm=parse_dimension(data["tab_width"]) if "tab_width" in data else None,
    )


def parse_node(data: dict, path: str = "") -> Any:
    if not isinstance(data, dict):
        raise PMLParseError(f"Expected dict, got {type(data).__name__}", path)

    keys = [k for k in data.keys() if k not in ("id", "children", "feature")]
    type_keys = [k for k in keys if k[0].isupper()]

    if len(type_keys) == 0:
        raise PMLParseError(f"No node type found in {list(data.keys())}", path)
    if len(type_keys) > 1:
        raise PMLParseError(f"Multiple node types found: {type_keys}", path)

    node_type = type_keys[0]
    node_data = data[node_type]
    if node_data is None:
        node_data = {}

    children_data = node_data.get("children") if isinstance(node_data, dict) else None
    children = parse_children(children_data, f"{path}.{node_type}")

    feature = None
    feature_data = node_data.get("feature") if isinstance(node_data, dict) else None
    if feature_data:
        feature = parse_feature(feature_data, f"{path}.{node_type}.feature")

    if children and not feature:
        feature_children = [c for c in children if isinstance(c, Feature)]
        if feature_children:
            feature = feature_children[0]
            children = tuple(c for c in children if not isinstance(c, Feature))

    node_id = node_data.get("id") if isinstance(node_data, dict) else None

    if node_type == "Panel":
        return Panel(children=children, id=node_id)

    elif node_type == "Rect":
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        rect = Rect(children=children, feature=feature, id=node_id)
        if at_data:
            return AtPosition(
                x_mm=parse_dimension(at_data.get("x")),
                y_mm=parse_dimension(at_data.get("y")),
                width_mm=parse_dimension(at_data["width"]) if "width" in at_data else None,
                height_mm=parse_dimension(at_data["height"]) if "height" in at_data else None,
                child=rect,
            )
        return rect

    elif node_type == "Circle":
        diameter_mm = parse_dimension(node_data["diameter"]) if "diameter" in node_data else None
        radius_mm = parse_dimension(node_data["radius"]) if "radius" in node_data else None
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        circle = Circle(
            diameter_mm=diameter_mm,
            radius_mm=radius_mm,
            children=children,
            feature=feature,
            id=node_id,
        )
        if at_data:
            size = diameter_mm if diameter_mm else (radius_mm * 2 if radius_mm else None)
            return AtPosition(
                x_mm=parse_dimension(at_data.get("x")),
                y_mm=parse_dimension(at_data.get("y")),
                width_mm=size,
                height_mm=size,
                child=circle,
            )
        return circle

    elif node_type == "RoundedRect":
        radius_mm = parse_dimension(node_data["radius"])
        corners = None
        if "corners" in node_data:
            corners = frozenset(node_data["corners"])
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        rounded_rect = RoundedRect(
            radius_mm=radius_mm,
            children=children,
            feature=feature,
            id=node_id,
            corners=corners,
        )
        if at_data:
            return AtPosition(
                x_mm=parse_dimension(at_data.get("x")),
                y_mm=parse_dimension(at_data.get("y")),
                width_mm=parse_dimension(at_data["width"]) if "width" in at_data else None,
                height_mm=parse_dimension(at_data["height"]) if "height" in at_data else None,
                child=rounded_rect,
            )
        return rounded_rect

    elif node_type == "Line":
        return Line(
            orientation=node_data["orientation"],
            feature=feature,
            id=node_id,
        )

    elif node_type == "Polyline":
        points = tuple(tuple(p) for p in node_data["points"])
        return Polyline(points=points, feature=feature, id=node_id)

    elif node_type == "Spline":
        points = tuple(tuple(p) for p in node_data["points"])
        tolerance_mm = parse_dimension(node_data.get("tolerance", "0.1mm"))
        return SplinePath(points=points, feature=feature, tolerance_mm=tolerance_mm, id=node_id)

    elif node_type == "Keepout":
        def contains_keepout(nodes: tuple) -> bool:
            for node in nodes:
                if isinstance(node, Keepout):
                    return True
                if hasattr(node, 'children') and node.children:
                    if contains_keepout(node.children):
                        return True
            return False

        if contains_keepout(children):
            raise PMLParseError("Nested Keepout is not allowed", path)
        return Keepout(children=children, id=node_id)

    elif node_type == "Edge":
        treatment = node_data.get("treatment")
        if treatment is None:
            raise PMLParseError("Edge requires 'treatment' key", path)
        return Edge(
            treatment_type=treatment,
            rough_allowance_mm=parse_dimension(node_data["rough_allowance"]) if "rough_allowance" in node_data else None,
            finish_allowance_mm=parse_dimension(node_data["finish_allowance"]) if "finish_allowance" in node_data else None,
            radius_mm=parse_dimension(node_data["radius"]) if "radius" in node_data else None,
            distance_mm=parse_dimension(node_data["distance"]) if "distance" in node_data else None,
            id=node_id,
        )

    elif node_type == "Inset":
        if "distance" not in node_data:
            raise PMLParseError("Inset requires 'distance' key", path)
        return Inset(
            amount_mm=parse_dimension(node_data["distance"]),
            children=children,
        )

    elif node_type == "Frame":
        return Frame(
            width_mm=parse_dimension(node_data["width"]),
            children=children,
        )

    elif node_type == "Grid":
        return Grid(
            rows=node_data["rows"],
            cols=node_data["cols"],
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "Cell":
        return Cell(
            children=children,
            inset_mm=parse_dimension(node_data.get("inset", "0mm")) if isinstance(node_data, dict) else 0.0,
        )

    elif node_type == "Split":
        return Split(
            rows=node_data["rows"],
            cols=node_data["cols"],
            rail_mm=parse_dimension(node_data.get("rail", "0mm")),
            mullion_mm=parse_dimension(node_data.get("mullion", "0mm")),
            children=children,
        )

    elif node_type == "Profile":
        depth = parse_dimension_or_through(node_data.get("depth", "through"))
        return ProfileGen(
            side=node_data["side"],
            depth=depth,
            tab_count=node_data.get("tab_count"),
            tab_height_mm=parse_dimension(node_data["tab_height"]) if "tab_height" in node_data else None,
            tab_width_mm=parse_dimension(node_data["tab_width"]) if "tab_width" in node_data else None,
        )

    elif node_type == "Pocket":
        return PocketGen(depth_mm=parse_dimension(node_data["depth"]))

    elif node_type == "RaisedPanel":
        return RaisedPanelGen(
            border_width_mm=parse_dimension(node_data["border_width"]),
            border_depth_mm=parse_dimension(node_data["border_depth"]),
            field_depth_mm=parse_dimension(node_data["field_depth"]),
        )

    elif node_type == "Chamfer":
        return ChamferGen(
            width_mm=parse_dimension(node_data["width"]),
            depth_mm=parse_dimension(node_data["depth"]),
        )

    elif node_type == "Wave":
        return WaveGen(
            wave_count=node_data["count"],
            amplitude_mm=parse_dimension(node_data["amplitude"]),
            wavelength_mm=parse_dimension(node_data["wavelength"]),
            groove_width_mm=parse_dimension(node_data["groove"]),
            depth_mm=parse_dimension(node_data["depth"]),
        )

    elif node_type == "XPanel":
        return XPanelGen(
            bar_width_mm=parse_dimension(node_data["bar_width"]),
            depth_mm=parse_dimension(node_data["depth"]),
        )

    elif node_type == "SplitHorizontal":
        return SplitHorizontal(
            n=node_data["count"],
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "SplitVertical":
        return SplitVertical(
            n=node_data["count"],
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "SplitGrid":
        return SplitGrid(
            rows=node_data["rows"],
            cols=node_data["cols"],
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "SplitHorizontalGaps":
        return SplitHorizontalGaps(
            n=node_data["count"],
            gap_mm=parse_dimension(node_data["gap"]),
            children=children,
        )

    elif node_type == "Lines":
        return LinesGen(
            angle_deg=float(node_data["angle"]),
            spacing_mm=parse_dimension(node_data["spacing"]),
            line_width_mm=parse_dimension(node_data["width"]),
            depth_mm=parse_dimension(node_data["depth"]),
        )

    elif node_type == "ConcentricBorder":
        insets = [parse_dimension(i) for i in node_data["insets"]]
        return ConcentricBorderGen(
            insets_mm=tuple(insets),
            groove_width_mm=parse_dimension(node_data["groove"]),
            depth_mm=parse_dimension(node_data["depth"]),
        )

    elif node_type == "Place":
        layout_data = node_data.get("layout", {})
        layout = parse_node(layout_data, f"{path}.{node_type}.layout") if layout_data else None
        return Place(
            layout=layout,
            children=children,
        )

    elif node_type == "AtPosition":
        child = parse_node(node_data["child"], f"{path}.{node_type}.child") if "child" in node_data else None
        return AtPosition(
            x_mm=parse_dimension(node_data["x"]),
            y_mm=parse_dimension(node_data["y"]),
            width_mm=parse_dimension(node_data["width"]) if "width" in node_data else None,
            height_mm=parse_dimension(node_data["height"]) if "height" in node_data else None,
            child=child,
        )

    elif node_type == "Subtract":
        return Subtract(
            inner_inset_mm=parse_dimension(node_data["inner_inset"]),
            children=children,
        )

    elif node_type == "Arch":
        return Arch(
            width_mm=parse_dimension(node_data["width"]),
            height_mm=parse_dimension(node_data["height"]),
            radius_mm=parse_dimension(node_data["radius"]),
            children=children,
            feature=feature,
            id=node_id,
        )

    elif node_type == "Polygon":
        points = tuple((parse_dimension(p[0]), parse_dimension(p[1])) for p in node_data["points"])
        return Polygon(points=points, children=children, feature=feature, id=node_id)

    elif node_type == "Triangle":
        return Triangle(
            base_mm=parse_dimension(node_data["base"]),
            height_mm=parse_dimension(node_data["height"]),
            children=children,
            feature=feature,
            id=node_id,
        )

    elif node_type == "HoleGrid":
        depth = parse_dimension_or_through(node_data.get("depth", "through"))
        return HoleGridGen(
            spacing_mm=parse_dimension(node_data["spacing"]),
            diameter_mm=parse_dimension(node_data["diameter"]),
            depth=depth,
            pattern=node_data.get("pattern", "rectangular"),
            inset_mm=parse_dimension(node_data.get("inset", "0mm")),
            align=node_data.get("align", "center"),
        )

    elif node_type == "MeasurementGrid":
        return MeasurementGridGen(
            unit=node_data.get("unit", "metric"),
            minor_spacing_mm=parse_dimension(node_data["minor_spacing"]) if "minor_spacing" in node_data else None,
            major_spacing_mm=parse_dimension(node_data["major_spacing"]) if "major_spacing" in node_data else None,
            minor_length_mm=parse_dimension(node_data.get("minor_length", "3mm")),
            major_length_mm=parse_dimension(node_data.get("major_length", "6mm")),
            depth_mm=parse_dimension(node_data.get("depth", "0.5mm")),
            minor_ticks=node_data.get("minor_ticks", True),
            labels=node_data.get("labels", False),
            label_height_mm=parse_dimension(node_data.get("label_height", "3mm")),
            label_offset_mm=parse_dimension(node_data["label_offset"]) if "label_offset" in node_data else None,
            label_interval=node_data.get("label_interval", 1),
            label_start=node_data.get("label_start", 0),
        )

    elif node_type == "MeasurementEdge":
        edges = tuple(node_data["edges"])
        return MeasurementEdgeGen(
            edges=edges,
            unit=node_data.get("unit", "metric"),
            minor_spacing_mm=parse_dimension(node_data["minor_spacing"]) if "minor_spacing" in node_data else None,
            major_spacing_mm=parse_dimension(node_data["major_spacing"]) if "major_spacing" in node_data else None,
            minor_length_mm=parse_dimension(node_data.get("minor_length", "3mm")),
            major_length_mm=parse_dimension(node_data.get("major_length", "6mm")),
            depth_mm=parse_dimension(node_data.get("depth", "0.3mm")),
            minor_ticks=node_data.get("minor_ticks", True),
            labels=node_data.get("labels", False),
            label_height_mm=parse_dimension(node_data.get("label_height", "3mm")),
            label_offset_mm=parse_dimension(node_data["label_offset"]) if "label_offset" in node_data else None,
            label_interval=node_data.get("label_interval", 1),
            label_start=node_data.get("label_start", 0),
        )

    elif node_type == "EngraveText":
        return EngraveTextGen(
            text=node_data["text"],
            height_mm=parse_dimension(node_data.get("height", "4mm")),
            depth_mm=parse_dimension(node_data.get("depth", "0.3mm")),
            font=node_data.get("font", "rowmans"),
            alignment=node_data.get("alignment", "left"),
            orientation=node_data.get("orientation", "horizontal"),
        )

    elif node_type == "WasteCuts":
        return WasteCuts(
            min_width_mm=parse_dimension(node_data.get("min_width", "200mm")),
            min_height_mm=parse_dimension(node_data.get("min_height", "200mm")),
            margin_mm=parse_dimension(node_data["margin"]) if "margin" in node_data else None,
            tab_count=node_data["tab_count"],
            tab_height_mm=parse_dimension(node_data["tab_height"]),
            strategy=node_data.get("strategy", "largest"),
        )

    elif node_type == "Assembly":
        assembly_type = node_data.get("type", node_data.get("topology", "box"))

        interfaces_raw = node_data.get("interfaces")
        interfaces = None
        if interfaces_raw:
            interfaces = {}
            for iface_name, iface_data in interfaces_raw.items():
                if isinstance(iface_data, str):
                    interfaces[iface_name] = iface_data
                elif isinstance(iface_data, dict):
                    interfaces[iface_name] = InterfaceConfig(
                        joinery=iface_data.get("joinery", "butt"),
                        finger_width_mm=parse_dimension(iface_data["finger_width"]) if "finger_width" in iface_data else None,
                        finger_count=iface_data.get("finger_count"),
                        clearance_mm=parse_dimension(iface_data.get("clearance", "0.12mm")),
                        dado_depth_mm=parse_dimension(iface_data["dado_depth"]) if "dado_depth" in iface_data else None,
                        inset_mm=parse_dimension(iface_data.get("inset", "0mm")),
                        receiving=iface_data.get("receiving", "a"),
                    )

        top_raw = node_data.get("top")
        top = None
        if top_raw is None:
            top = None
        elif isinstance(top_raw, str):
            top = top_raw
        elif isinstance(top_raw, dict):
            top = InterfaceConfig(
                joinery=top_raw.get("joinery", "butt"),
                finger_width_mm=parse_dimension(top_raw["finger_width"]) if "finger_width" in top_raw else None,
                finger_count=top_raw.get("finger_count"),
                clearance_mm=parse_dimension(top_raw.get("clearance", "0.12mm")),
                dado_depth_mm=parse_dimension(top_raw["dado_depth"]) if "dado_depth" in top_raw else None,
                inset_mm=parse_dimension(top_raw.get("inset", "0mm")),
                receiving=top_raw.get("receiving", "a"),
            )

        bottom_raw = node_data.get("bottom", "captured")
        bottom: str | InterfaceConfig | None = "captured"
        if bottom_raw is None:
            bottom = None
        elif isinstance(bottom_raw, str):
            bottom = bottom_raw
        elif isinstance(bottom_raw, dict):
            bottom = InterfaceConfig(
                joinery=bottom_raw.get("joinery", "captured"),
                finger_width_mm=parse_dimension(bottom_raw["finger_width"]) if "finger_width" in bottom_raw else None,
                finger_count=bottom_raw.get("finger_count"),
                clearance_mm=parse_dimension(bottom_raw.get("clearance", "0.12mm")),
                dado_depth_mm=parse_dimension(bottom_raw["dado_depth"]) if "dado_depth" in bottom_raw else None,
                inset_mm=parse_dimension(bottom_raw.get("inset", "0mm")),
                receiving=bottom_raw.get("receiving", "a"),
            )

        back_raw = node_data.get("back")
        back: str | InterfaceConfig | None = None
        if back_raw is None:
            back = None
        elif isinstance(back_raw, str):
            back = back_raw
        elif isinstance(back_raw, dict):
            back = InterfaceConfig(
                joinery=back_raw.get("joinery", "captured"),
                finger_width_mm=parse_dimension(back_raw["finger_width"]) if "finger_width" in back_raw else None,
                finger_count=back_raw.get("finger_count"),
                clearance_mm=parse_dimension(back_raw.get("clearance", "0.12mm")),
                dado_depth_mm=parse_dimension(back_raw["dado_depth"]) if "dado_depth" in back_raw else None,
                inset_mm=parse_dimension(back_raw.get("inset", "0mm")),
                receiving=back_raw.get("receiving", "a"),
            )

        grid_raw = node_data.get("grid")
        grid = None
        if grid_raw:
            if isinstance(grid_raw, list) and len(grid_raw) == 2:
                grid = (int(grid_raw[0]), int(grid_raw[1]))

        shelf_joinery_raw = node_data.get("shelf_joinery", "captured")
        shelf_joinery: str | InterfaceConfig = "captured"
        if isinstance(shelf_joinery_raw, str):
            shelf_joinery = shelf_joinery_raw
        elif isinstance(shelf_joinery_raw, dict):
            shelf_joinery = InterfaceConfig(
                joinery=shelf_joinery_raw.get("joinery", "captured"),
                finger_width_mm=parse_dimension(shelf_joinery_raw["finger_width"]) if "finger_width" in shelf_joinery_raw else None,
                finger_count=shelf_joinery_raw.get("finger_count"),
                clearance_mm=parse_dimension(shelf_joinery_raw.get("clearance", "0.12mm")),
                dado_depth_mm=parse_dimension(shelf_joinery_raw["dado_depth"]) if "dado_depth" in shelf_joinery_raw else None,
                inset_mm=parse_dimension(shelf_joinery_raw.get("inset", "0mm")),
                receiving=shelf_joinery_raw.get("receiving", "a"),
            )

        partition_joinery_raw = node_data.get("partition_joinery", "captured")
        partition_joinery: str | InterfaceConfig = "captured"
        if isinstance(partition_joinery_raw, str):
            partition_joinery = partition_joinery_raw
        elif isinstance(partition_joinery_raw, dict):
            partition_joinery = InterfaceConfig(
                joinery=partition_joinery_raw.get("joinery", "captured"),
                finger_width_mm=parse_dimension(partition_joinery_raw["finger_width"]) if "finger_width" in partition_joinery_raw else None,
                finger_count=partition_joinery_raw.get("finger_count"),
                clearance_mm=parse_dimension(partition_joinery_raw.get("clearance", "0.12mm")),
                dado_depth_mm=parse_dimension(partition_joinery_raw["dado_depth"]) if "dado_depth" in partition_joinery_raw else None,
                inset_mm=parse_dimension(partition_joinery_raw.get("inset", "0mm")),
                receiving=partition_joinery_raw.get("receiving", "a"),
            )

        return Assembly(
            type=assembly_type,
            width_mm=parse_dimension(node_data.get("width") or node_data.get("dimensions", [0])[0] if isinstance(node_data.get("dimensions"), list) else node_data["width"]),
            depth_mm=parse_dimension(node_data.get("depth") or (node_data.get("dimensions", [0, 0])[1] if isinstance(node_data.get("dimensions"), list) and len(node_data.get("dimensions", [])) > 1 else node_data["depth"])),
            height_mm=parse_dimension(node_data.get("height") or (node_data.get("dimensions", [0, 0, 0])[2] if isinstance(node_data.get("dimensions"), list) and len(node_data.get("dimensions", [])) > 2 else node_data["height"])),
            thickness_mm=parse_dimension(node_data["thickness"]),
            joinery=node_data.get("joinery", "finger"),
            finger_width_mm=parse_dimension(node_data["finger_width"]) if "finger_width" in node_data else None,
            finger_count=node_data.get("finger_count"),
            clearance_mm=parse_dimension(node_data.get("clearance", "0.12mm")),
            interfaces=interfaces,
            top=top,
            bottom=bottom,
            children=children,
            layout_gap_mm=parse_dimension(node_data.get("layout_gap", "10mm")),
            show_labels=node_data.get("show_labels", False),
            show_edge_colors=node_data.get("show_edge_colors", False),
            show_dimensions=node_data.get("show_dimensions", True),
            cap_style=node_data.get("cap_style", "between_sides"),
            back=back,
            back_thickness_mm=parse_dimension(node_data["back_thickness"]) if "back_thickness" in node_data else (parse_dimension(back_raw["thickness"]) if isinstance(back_raw, dict) and "thickness" in back_raw else None),
            back_inset_mm=parse_dimension(node_data.get("back_inset", "0mm")) if "back_inset" in node_data else (parse_dimension(back_raw.get("inset", "0mm")) if isinstance(back_raw, dict) else 0.0),
            back_joinery=node_data.get("back_joinery"),
            back_rabbet_depth_mm=parse_dimension(node_data["back_rabbet_depth"]) if "back_rabbet_depth" in node_data else None,
            back_internal_support=node_data.get("back_internal_support", True),
            fixed_shelves=node_data.get("fixed_shelves", 0),
            shelf_joinery=shelf_joinery,
            shelf_dado_depth_mm=parse_dimension(node_data["shelf_dado_depth"]) if "shelf_dado_depth" in node_data else None,
            shelf_back_support=node_data.get("shelf_back_support", False),
            vertical_partitions=node_data.get("vertical_partitions", 0),
            partition_joinery=partition_joinery,
            partition_dado_depth_mm=parse_dimension(node_data["partition_dado_depth"]) if "partition_dado_depth" in node_data else None,
            grid=grid,
            perimeter_joinery=node_data.get("perimeter_joinery", node_data.get("joinery", "finger")),
            internal_joinery=node_data.get("internal_joinery", "half_lap"),
            toe_kick_height_mm=parse_dimension(node_data["toe_kick_height"]) if "toe_kick_height" in node_data else None,
            toe_kick_depth_mm=parse_dimension(node_data["toe_kick_depth"]) if "toe_kick_depth" in node_data else None,
            toe_kick_style=node_data.get("toe_kick_style", "open"),
            toe_kick_cover=node_data.get("toe_kick_cover", False),
        )

    elif node_type == "UseComponent":
        return UseComponent(
            component_name=node_data["name"],
            args=node_data.get("args", {}),
        )

    elif node_type == "Engrave":
        depth_mm = parse_dimension(node_data["depth"])
        return Feature(
            type="engrave",
            depth=str(depth_mm),
            depth_mm=depth_mm,
        )

    else:
        raise PMLParseError(f"Unknown node type: {node_type}", path)


def parse_pml_yaml(source: str) -> CompositionalLayoutAST:
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(source)

    if data is None:
        raise PMLParseError("Empty YAML document")

    sheet_block = data.get("Sheet")
    if sheet_block is None:
        raise PMLParseError("Missing 'Sheet:' root key")

    margin_mm = parse_dimension(sheet_block.get("margin", "0mm"))

    if "working_width" in sheet_block:
        working_width = parse_dimension(sheet_block["working_width"])
        width_mm = working_width + 2 * margin_mm
    elif "physical_width" in sheet_block:
        width_mm = parse_dimension(sheet_block["physical_width"])
    elif "width" in sheet_block:
        width_mm = parse_dimension(sheet_block["width"])
    else:
        raise PMLParseError("Sheet missing 'width', 'physical_width', or 'working_width'")

    if "working_height" in sheet_block:
        working_height = parse_dimension(sheet_block["working_height"])
        height_mm = working_height + 2 * margin_mm
    elif "physical_height" in sheet_block:
        height_mm = parse_dimension(sheet_block["physical_height"])
    elif "height" in sheet_block:
        height_mm = parse_dimension(sheet_block["height"])
    else:
        raise PMLParseError("Sheet missing 'height', 'physical_height', or 'working_height'")

    sheet = Sheet(
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=parse_dimension(sheet_block["thickness"]),
        margin_mm=margin_mm,
        show_dimensions=sheet_block.get("show_dimensions", True),
    )

    project = data.get("project")
    kerf_width_mm = parse_dimension(data["kerf"]) if "kerf" in data else None

    components: dict[str, ComponentDef] = {}
    components_block = data.get("components", {})
    for name, comp_data in components_block.items():
        params = comp_data.get("params", {})
        body_data = comp_data.get("body")
        if body_data:
            if isinstance(body_data, list):
                body = Panel(children=parse_children(body_data, f"components.{name}.body"))
            else:
                body = parse_node(body_data, f"components.{name}.body")
        else:
            body = None
        components[name] = ComponentDef(name=name, params=params, body=body)

    children_data = data.get("children", [])
    children = parse_children(children_data, "root")

    root = Panel(children=children) if children else None

    return CompositionalLayoutAST(
        sheet=sheet,
        components=components,
        root=root,
        project=project,
        kerf_width_mm=kerf_width_mm,
    )


def parse_pml_yaml_file(path: Path | str) -> CompositionalLayoutAST:
    path = Path(path)
    return parse_pml_yaml(path.read_text())


def parse_nest_yaml(source: str) -> NestJob:
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(source)

    if data is None:
        raise NestParseError("Empty YAML document")

    nest_block = data.get("Nest")
    if nest_block is None:
        raise NestParseError("Missing 'Nest:' root key")

    algorithm = nest_block.get("algorithm")
    if algorithm is None:
        raise NestParseError("Missing 'algorithm' in Nest block")

    sheet_block = nest_block.get("Sheet")
    if sheet_block is None:
        raise NestParseError("Missing 'Sheet:' in Nest block")

    try:
        sheet_width = parse_dimension(sheet_block.get("width"))
        sheet_height = parse_dimension(sheet_block.get("height"))
        sheet_thickness = parse_dimension(sheet_block.get("thickness"))
    except (ValueError, TypeError) as e:
        raise NestParseError(f"Invalid sheet dimensions: {e}")

    kerf_mm = 6.35
    if "kerf" in nest_block:
        try:
            kerf_mm = parse_dimension(nest_block["kerf"])
        except ValueError as e:
            raise NestParseError(f"Invalid kerf: {e}")

    margin_mm = 10.0
    if "margin" in nest_block:
        try:
            margin_mm = parse_dimension(nest_block["margin"])
        except ValueError as e:
            raise NestParseError(f"Invalid margin: {e}")

    parts_list = nest_block.get("parts", [])
    if not parts_list:
        raise NestParseError("No parts defined")

    parts: list[NestPart] = []
    for part_data in parts_list:
        if not isinstance(part_data, dict):
            raise NestParseError(f"Invalid part definition: {part_data}")

        name = part_data.get("name")
        if name is None:
            raise NestParseError("Part missing 'name'")

        try:
            width = parse_dimension(part_data.get("width"))
            height = parse_dimension(part_data.get("height"))
        except (ValueError, TypeError) as e:
            raise NestParseError(f"Invalid dimensions for part '{name}': {e}")

        quantity = part_data.get("quantity", 1)
        if not isinstance(quantity, int) or quantity < 1:
            raise NestParseError(f"Invalid quantity for part '{name}': {quantity}")

        template = None
        template_params: dict[str, float] = {}

        template_block = part_data.get("template")
        if template_block is not None:
            if isinstance(template_block, dict):
                template = template_block.get("name")
                params_block = template_block.get("params", {})
                for k, v in params_block.items():
                    try:
                        template_params[k] = parse_dimension(v)
                    except ValueError as e:
                        raise NestParseError(f"Invalid template param '{k}' for part '{name}': {e}")
            elif isinstance(template_block, str):
                template = template_block
            else:
                raise NestParseError(f"Invalid template for part '{name}'")

        parts.append(NestPart(
            name=name,
            width_mm=width,
            height_mm=height,
            quantity=quantity,
            template=template,
            template_params=template_params,
        ))

    return NestJob(
        algorithm=algorithm,
        sheet_width_mm=sheet_width,
        sheet_height_mm=sheet_height,
        sheet_thickness_mm=sheet_thickness,
        kerf_mm=kerf_mm,
        margin_mm=margin_mm,
        parts=parts,
    )


def parse_nest_yaml_file(path: Path | str) -> NestJob:
    path = Path(path)
    return parse_nest_yaml(path.read_text())


def substitute_params(text: str, params: dict[str, Any]) -> str:
    def replace_match(m: re.Match[str]) -> str:
        param_name = m.group(1)
        if param_name not in params:
            raise PMLParseError(f"Unknown parameter: ${{{param_name}}}")
        value = params[param_name]
        if isinstance(value, str):
            if value.endswith("mm"):
                return value
            return value
        return f"{value}mm"

    return re.sub(r'\$\{(\w+)\}', replace_match, text)


def parse_template_yaml(source: str, parse_body: bool = False) -> TemplateDef:
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(source)

    if data is None:
        raise PMLParseError("Empty YAML document")

    template_block = data.get("Template")
    if template_block is None:
        raise PMLParseError("Missing 'Template:' root key")

    name = template_block.get("name")
    if name is None:
        raise PMLParseError("Template missing 'name'")

    params_block = template_block.get("params", {})
    params: dict[str, Any] = {}
    for k, v in params_block.items():
        if isinstance(v, str) and v.endswith("mm"):
            params[k] = parse_dimension(v)
        else:
            params[k] = v

    body = None
    if parse_body and "body" in template_block:
        body = parse_node(template_block["body"], "Template.body")

    return TemplateDef(name=name, params=params, body=body)


def parse_template_yaml_file(path: Path | str, parse_body: bool = False) -> TemplateDef:
    path = Path(path)
    return parse_template_yaml(path.read_text(), parse_body=parse_body)


__all__ = [
    "PMLParseError",
    "parse_dimension",
    "parse_pml_yaml",
    "parse_pml_yaml_file",
    "parse_nest_yaml",
    "parse_nest_yaml_file",
    "parse_template_yaml",
    "parse_template_yaml_file",
    "substitute_params",
]
