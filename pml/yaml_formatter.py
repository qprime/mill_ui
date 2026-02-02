from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

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
)
from layout_ast.layout import Sheet, Feature
from pml.nest_parser import NestJob, NestPart


def dim(value: float) -> str:
    if value == int(value):
        return f"{int(value)}mm"
    return f"{value}mm"


def format_feature(feature: Feature) -> dict[str, Any]:
    result: dict[str, Any] = {"type": feature.type}

    if feature.is_through:
        result["depth"] = "through"
    else:
        result["depth"] = dim(feature.depth_mm)

    if feature.side:
        result["side"] = feature.side

    if feature.corner_cleanup_tool_diameter_mm is not None:
        result["corner_cleanup"] = dim(feature.corner_cleanup_tool_diameter_mm)

    if feature.tab_count is not None:
        result["tab_count"] = feature.tab_count
    if feature.tab_height_mm is not None:
        result["tab_height"] = dim(feature.tab_height_mm)
    if feature.tab_width_mm is not None:
        result["tab_width"] = dim(feature.tab_width_mm)

    return result


def format_node(node: Any) -> dict[str, Any]:
    if isinstance(node, Panel):
        result: dict[str, Any] = {}
        if node.id:
            result["id"] = node.id
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Panel": result if result else None}

    elif isinstance(node, AtPosition):
        if node.child and isinstance(node.child, Rect):
            rect_data = format_rect_node(node.child)
            rect_data["at"] = {"x": dim(node.x_mm), "y": dim(node.y_mm)}
            if node.width_mm is not None:
                rect_data["at"]["width"] = dim(node.width_mm)
            if node.height_mm is not None:
                rect_data["at"]["height"] = dim(node.height_mm)
            return {"Rect": rect_data}
        elif node.child and isinstance(node.child, Circle):
            circle_data = format_circle_node(node.child)
            circle_data["at"] = {"x": dim(node.x_mm), "y": dim(node.y_mm)}
            return {"Circle": circle_data}
        elif node.child and isinstance(node.child, RoundedRect):
            rr_data = format_rounded_rect_node(node.child)
            rr_data["at"] = {"x": dim(node.x_mm), "y": dim(node.y_mm)}
            if node.width_mm is not None:
                rr_data["at"]["width"] = dim(node.width_mm)
            if node.height_mm is not None:
                rr_data["at"]["height"] = dim(node.height_mm)
            return {"RoundedRect": rr_data}
        else:
            result = {"x": dim(node.x_mm), "y": dim(node.y_mm)}
            if node.width_mm is not None:
                result["width"] = dim(node.width_mm)
            if node.height_mm is not None:
                result["height"] = dim(node.height_mm)
            if node.child:
                result["child"] = format_node(node.child)
            return {"AtPosition": result}

    elif isinstance(node, Rect):
        return {"Rect": format_rect_node(node)}

    elif isinstance(node, Circle):
        return {"Circle": format_circle_node(node)}

    elif isinstance(node, RoundedRect):
        return {"RoundedRect": format_rounded_rect_node(node)}

    elif isinstance(node, Line):
        result = {"orientation": node.orientation}
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        return {"Line": result}

    elif isinstance(node, Polyline):
        result: dict[str, Any] = {"points": [list(p) for p in node.points]}
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        return {"Polyline": result}

    elif isinstance(node, SplinePath):
        result: dict[str, Any] = {"points": [list(p) for p in node.points]}
        if node.tolerance_mm != 0.1:
            result["tolerance"] = dim(node.tolerance_mm)
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        return {"Spline": result}

    elif isinstance(node, Keepout):
        result: dict[str, Any] = {}
        if node.id:
            result["id"] = node.id
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Keepout": result if result else None}

    elif isinstance(node, Edge):
        result: dict[str, Any] = {"treatment": node.treatment_type}
        if node.rough_allowance_mm is not None:
            result["rough_allowance"] = dim(node.rough_allowance_mm)
        if node.finish_allowance_mm is not None:
            result["finish_allowance"] = dim(node.finish_allowance_mm)
        if node.radius_mm is not None:
            result["radius"] = dim(node.radius_mm)
        if node.distance_mm is not None:
            result["distance"] = dim(node.distance_mm)
        if node.id:
            result["id"] = node.id
        return {"Edge": result}

    elif isinstance(node, Inset):
        result: dict[str, Any] = {"distance": dim(node.amount_mm)}
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Inset": result}

    elif isinstance(node, Frame):
        result: dict[str, Any] = {"width": dim(node.width_mm)}
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Frame": result}

    elif isinstance(node, Grid):
        result: dict[str, Any] = {"rows": node.rows, "cols": node.cols}
        if node.gap_mm:
            result["gap"] = dim(node.gap_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Grid": result}

    elif isinstance(node, Cell):
        result: dict[str, Any] = {}
        if node.inset_mm:
            result["inset"] = dim(node.inset_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Cell": result if result else None}

    elif isinstance(node, Split):
        result: dict[str, Any] = {"rows": node.rows, "cols": node.cols}
        if node.rail_mm:
            result["rail"] = dim(node.rail_mm)
        if node.mullion_mm:
            result["mullion"] = dim(node.mullion_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Split": result}

    elif isinstance(node, ProfileGen):
        result: dict[str, Any] = {"side": node.side}
        if node.depth == "through":
            result["depth"] = "through"
        else:
            result["depth"] = dim(node.depth) if isinstance(node.depth, (int, float)) else node.depth
        if node.tab_count is not None:
            result["tab_count"] = node.tab_count
        if node.tab_height_mm is not None:
            result["tab_height"] = dim(node.tab_height_mm)
        if node.tab_width_mm is not None:
            result["tab_width"] = dim(node.tab_width_mm)
        return {"Profile": result}

    elif isinstance(node, PocketGen):
        return {"Pocket": {"depth": dim(node.depth_mm)}}

    elif isinstance(node, RaisedPanelGen):
        return {"RaisedPanel": {
            "border_width": dim(node.border_width_mm),
            "border_depth": dim(node.border_depth_mm),
            "field_depth": dim(node.field_depth_mm),
        }}

    elif isinstance(node, ChamferGen):
        return {"Chamfer": {"width": dim(node.width_mm), "depth": dim(node.depth_mm)}}

    elif isinstance(node, WaveGen):
        return {"Wave": {
            "count": node.wave_count,
            "amplitude": dim(node.amplitude_mm),
            "wavelength": dim(node.wavelength_mm),
            "groove": dim(node.groove_width_mm),
            "depth": dim(node.depth_mm),
        }}

    elif isinstance(node, XPanelGen):
        return {"XPanel": {"bar_width": dim(node.bar_width_mm), "depth": dim(node.depth_mm)}}

    elif isinstance(node, SplitHorizontal):
        result: dict[str, Any] = {"count": node.n}
        if node.gap_mm:
            result["gap"] = dim(node.gap_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"SplitHorizontal": result}

    elif isinstance(node, SplitVertical):
        result: dict[str, Any] = {"count": node.n}
        if node.gap_mm:
            result["gap"] = dim(node.gap_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"SplitVertical": result}

    elif isinstance(node, SplitGrid):
        result: dict[str, Any] = {"rows": node.rows, "cols": node.cols}
        if node.gap_mm:
            result["gap"] = dim(node.gap_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"SplitGrid": result}

    elif isinstance(node, SplitHorizontalGaps):
        result: dict[str, Any] = {"count": node.n, "gap": dim(node.gap_mm)}
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"SplitHorizontalGaps": result}

    elif isinstance(node, LinesGen):
        return {"Lines": {
            "angle": node.angle_deg,
            "spacing": dim(node.spacing_mm),
            "width": dim(node.line_width_mm),
            "depth": dim(node.depth_mm),
        }}

    elif isinstance(node, ConcentricBorderGen):
        return {"ConcentricBorder": {
            "insets": [dim(i) for i in node.insets_mm],
            "groove": dim(node.groove_width_mm),
            "depth": dim(node.depth_mm),
        }}

    elif isinstance(node, Subtract):
        result: dict[str, Any] = {"inner_inset": dim(node.inner_inset_mm)}
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Subtract": result}

    elif isinstance(node, Arch):
        result: dict[str, Any] = {
            "width": dim(node.width_mm),
            "height": dim(node.height_mm),
            "radius": dim(node.radius_mm),
        }
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Arch": result}

    elif isinstance(node, Polygon):
        result: dict[str, Any] = {"points": [[dim(p[0]), dim(p[1])] for p in node.points]}
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Polygon": result}

    elif isinstance(node, Triangle):
        result: dict[str, Any] = {"base": dim(node.base_mm), "height": dim(node.height_mm)}
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Triangle": result}

    elif isinstance(node, HoleGridGen):
        result: dict[str, Any] = {
            "spacing": dim(node.spacing_mm),
            "diameter": dim(node.diameter_mm),
        }
        if node.depth == "through":
            result["depth"] = "through"
        else:
            result["depth"] = dim(node.depth) if isinstance(node.depth, (int, float)) else node.depth
        if node.pattern != "rectangular":
            result["pattern"] = node.pattern
        if node.inset_mm:
            result["inset"] = dim(node.inset_mm)
        if node.align != "center":
            result["align"] = node.align
        return {"HoleGrid": result}

    elif isinstance(node, MeasurementGridGen):
        result: dict[str, Any] = {}
        if node.unit != "metric":
            result["unit"] = node.unit
        if node.minor_spacing_mm is not None:
            result["minor_spacing"] = dim(node.minor_spacing_mm)
        if node.major_spacing_mm is not None:
            result["major_spacing"] = dim(node.major_spacing_mm)
        if node.minor_length_mm != 3.0:
            result["minor_length"] = dim(node.minor_length_mm)
        if node.major_length_mm != 6.0:
            result["major_length"] = dim(node.major_length_mm)
        if node.depth_mm != 0.5:
            result["depth"] = dim(node.depth_mm)
        if not node.minor_ticks:
            result["minor_ticks"] = False
        if node.labels:
            result["labels"] = True
        if node.label_height_mm != 3.0:
            result["label_height"] = dim(node.label_height_mm)
        if node.label_offset_mm is not None:
            result["label_offset"] = dim(node.label_offset_mm)
        if node.label_interval != 1:
            result["label_interval"] = node.label_interval
        if node.label_start != 0:
            result["label_start"] = node.label_start
        return {"MeasurementGrid": result if result else None}

    elif isinstance(node, MeasurementEdgeGen):
        result: dict[str, Any] = {"edges": list(node.edges)}
        if node.unit != "metric":
            result["unit"] = node.unit
        if node.minor_spacing_mm is not None:
            result["minor_spacing"] = dim(node.minor_spacing_mm)
        if node.major_spacing_mm is not None:
            result["major_spacing"] = dim(node.major_spacing_mm)
        if node.minor_length_mm != 3.0:
            result["minor_length"] = dim(node.minor_length_mm)
        if node.major_length_mm != 6.0:
            result["major_length"] = dim(node.major_length_mm)
        if node.depth_mm != 0.3:
            result["depth"] = dim(node.depth_mm)
        if not node.minor_ticks:
            result["minor_ticks"] = False
        if node.labels:
            result["labels"] = True
        if node.label_height_mm != 3.0:
            result["label_height"] = dim(node.label_height_mm)
        if node.label_offset_mm is not None:
            result["label_offset"] = dim(node.label_offset_mm)
        if node.label_interval != 1:
            result["label_interval"] = node.label_interval
        if node.label_start != 0:
            result["label_start"] = node.label_start
        return {"MeasurementEdge": result}

    elif isinstance(node, EngraveTextGen):
        result: dict[str, Any] = {"text": node.text}
        if node.height_mm != 4.0:
            result["height"] = dim(node.height_mm)
        if node.depth_mm != 0.3:
            result["depth"] = dim(node.depth_mm)
        if node.font != "rowmans":
            result["font"] = node.font
        if node.alignment != "left":
            result["alignment"] = node.alignment
        if node.orientation != "horizontal":
            result["orientation"] = node.orientation
        return {"EngraveText": result}

    elif isinstance(node, WasteCuts):
        result: dict[str, Any] = {
            "tab_count": node.tab_count,
            "tab_height": dim(node.tab_height_mm),
        }
        if node.min_width_mm != 200.0:
            result["min_width"] = dim(node.min_width_mm)
        if node.min_height_mm != 200.0:
            result["min_height"] = dim(node.min_height_mm)
        if node.margin_mm is not None:
            result["margin"] = dim(node.margin_mm)
        if node.strategy != "largest":
            result["strategy"] = node.strategy
        return {"WasteCuts": result}

    elif isinstance(node, Assembly):
        result: dict[str, Any] = {
            "topology": node.topology,
            "width": dim(node.width_mm),
            "depth": dim(node.depth_mm),
            "height": dim(node.height_mm),
            "thickness": dim(node.thickness_mm),
        }
        if node.joinery != "finger":
            result["joinery"] = node.joinery
        if node.finger_width_mm is not None:
            result["finger_width"] = dim(node.finger_width_mm)
        if node.finger_count is not None:
            result["finger_count"] = node.finger_count
        if node.clearance_mm != 0.12:
            result["clearance"] = dim(node.clearance_mm)
        if node.include_top:
            result["include_top"] = True
        if not node.include_bottom:
            result["include_bottom"] = False
        if node.layout_gap_mm != 10.0:
            result["layout_gap"] = dim(node.layout_gap_mm)
        if node.bottom_style != "captured":
            result["bottom_style"] = node.bottom_style
        if node.top_style != "captured":
            result["top_style"] = node.top_style
        if node.dado_inset_mm:
            result["dado_inset"] = dim(node.dado_inset_mm)
        if node.dado_drop_mm:
            result["dado_drop"] = dim(node.dado_drop_mm)
        if node.show_labels:
            result["show_labels"] = True
        if node.show_edge_colors:
            result["show_edge_colors"] = True
        if node.base_mm is not None:
            result["base"] = dim(node.base_mm)
        if node.slant_height_mm is not None:
            result["slant_height"] = dim(node.slant_height_mm)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Assembly": result}

    elif isinstance(node, UseComponent):
        result: dict[str, Any] = {"name": node.component_name}
        if node.args:
            result["args"] = node.args
        return {"UseComponent": result}

    elif isinstance(node, Place):
        result: dict[str, Any] = {}
        if node.layout:
            result["layout"] = format_node(node.layout)
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Place": result}

    else:
        raise ValueError(f"Unknown node type: {type(node).__name__}")


def format_rect_node(node: Rect) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if node.id:
        result["id"] = node.id
    if node.feature:
        result["feature"] = format_feature(node.feature)
    if node.children:
        result["children"] = [format_node(c) for c in node.children]
    return result


def format_circle_node(node: Circle) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if node.id:
        result["id"] = node.id
    if node.diameter_mm is not None:
        result["diameter"] = dim(node.diameter_mm)
    if node.radius_mm is not None:
        result["radius"] = dim(node.radius_mm)
    if node.feature:
        result["feature"] = format_feature(node.feature)
    if node.children:
        result["children"] = [format_node(c) for c in node.children]
    return result


def format_rounded_rect_node(node: RoundedRect) -> dict[str, Any]:
    result: dict[str, Any] = {"radius": dim(node.radius_mm)}
    if node.id:
        result["id"] = node.id
    if node.corners:
        result["corners"] = list(node.corners)
    if node.feature:
        result["feature"] = format_feature(node.feature)
    if node.children:
        result["children"] = [format_node(c) for c in node.children]
    return result


def format_pml_yaml(ast: CompositionalLayoutAST) -> str:
    data: dict[str, Any] = {}

    if ast.project:
        data["project"] = ast.project

    if ast.kerf_width_mm is not None:
        data["kerf"] = dim(ast.kerf_width_mm)

    data["Sheet"] = {
        "width": dim(ast.sheet.width_mm),
        "height": dim(ast.sheet.height_mm),
        "thickness": dim(ast.sheet.thickness_mm),
    }
    if ast.sheet.margin_mm:
        data["Sheet"]["margin"] = dim(ast.sheet.margin_mm)

    if ast.components:
        data["components"] = {}
        for name, comp in ast.components.items():
            comp_data: dict[str, Any] = {}
            if comp.params:
                comp_data["params"] = comp.params
            if comp.body:
                comp_data["body"] = format_node(comp.body)
            data["components"][name] = comp_data

    if ast.root and ast.root.children:
        data["children"] = [format_node(c) for c in ast.root.children]

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120

    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def format_pml_yaml_file(ast: CompositionalLayoutAST, path: Path | str) -> None:
    path = Path(path)
    path.write_text(format_pml_yaml(ast))


def format_nest_yaml(job: NestJob) -> str:
    data: dict[str, Any] = {
        "Nest": {
            "algorithm": job.algorithm,
            "Sheet": {
                "width": dim(job.sheet_width_mm),
                "height": dim(job.sheet_height_mm),
                "thickness": dim(job.sheet_thickness_mm),
            },
        }
    }

    if job.kerf_mm != 6.35:
        data["Nest"]["kerf"] = dim(job.kerf_mm)
    if job.margin_mm != 10.0:
        data["Nest"]["margin"] = dim(job.margin_mm)

    parts_list: list[dict[str, Any]] = []
    for part in job.parts:
        part_data: dict[str, Any] = {
            "name": part.name,
            "width": dim(part.width_mm),
            "height": dim(part.height_mm),
        }
        if part.quantity != 1:
            part_data["quantity"] = part.quantity
        if part.template:
            if part.template_params:
                part_data["template"] = {
                    "name": part.template,
                    "params": {k: dim(v) for k, v in part.template_params.items()},
                }
            else:
                part_data["template"] = part.template
        parts_list.append(part_data)

    data["Nest"]["parts"] = parts_list

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120

    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def format_nest_yaml_file(job: NestJob, path: Path | str) -> None:
    path = Path(path)
    path.write_text(format_nest_yaml(job))


__all__ = [
    "format_pml_yaml",
    "format_pml_yaml_file",
    "format_nest_yaml",
    "format_nest_yaml_file",
]
