from __future__ import annotations

from io import StringIO
from typing import Any

from ruamel.yaml import YAML

from core.constants import DepthMode
from layout_ast.compositional import (
    Arch,
    AssemblyDecl,
    AtPosition,
    BeamDecl,
    BeamFeatureDecl,
    Cell,
    ChamferGen,
    Circle,
    CompositionalLayoutAST,
    ConcentricBorderGen,
    Edge,
    Ellipse,
    EngraveTextGen,
    FlutingGen,
    Frame,
    Grid,
    GridLinesGen,
    HoleGridGen,
    Inset,
    InterfaceConfig,
    Keepout,
    Line,
    LinesGen,
    MeasurementEdgeGen,
    MeasurementGridGen,
    Panel,
    Place,
    PocketGen,
    Polygon,
    Polyline,
    ProfileGen,
    RaisedPanelGen,
    Rect,
    RoundedRect,
    SplinePath,
    Split,
    SplitGrid,
    SplitHorizontal,
    SplitHorizontalGaps,
    SplitVertical,
    Subtract,
    Triangle,
    UseComponent,
    WasteCuts,
    WaveGen,
    XPanelGen,
)
from layout_ast.layout import DogboneSpec, Feature, FeedsOverride
from pml.measurement_fields import format_measurement_fields
from pml.nest_parser import HoldingSpec, NestJob


def dim(value: float) -> str:
    if value == int(value):
        return f"{int(value)}mm"
    return f"{value}mm"


def _format_dogbone(dogbone: Any) -> Any:
    if not isinstance(dogbone, DogboneSpec):
        return dogbone
    dogbone_dict: dict[str, Any] = {}
    if dogbone.style != "dogbone":
        dogbone_dict["style"] = dogbone.style
    if dogbone.diameter_mm is not None:
        dogbone_dict["diameter"] = dim(dogbone.diameter_mm)
    if dogbone.overcut_mm != 0.0:
        dogbone_dict["overcut"] = dim(dogbone.overcut_mm)
    return dogbone_dict if dogbone_dict else True


def _format_feeds_override(feeds: Any) -> dict[str, Any] | None:
    if not isinstance(feeds, FeedsOverride):
        return None
    feeds_dict: dict[str, Any] = {}
    if feeds.rpm is not None:
        feeds_dict["rpm"] = feeds.rpm
    if feeds.feed_xy is not None:
        feeds_dict["feed_xy"] = feeds.feed_xy
    if feeds.feed_z is not None:
        feeds_dict["feed_z"] = feeds.feed_z
    if feeds.depth_per_pass is not None:
        feeds_dict["depth_per_pass"] = feeds.depth_per_pass
    if feeds.stepover_percent is not None:
        feeds_dict["stepover_percent"] = feeds.stepover_percent
    return feeds_dict or None


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

    if feature.rest is not None:
        rest_spec = feature.rest
        has_non_defaults = rest_spec.rough_allowance_mm != 0.5 or rest_spec.finish_allowance_mm != 0.0
        if has_non_defaults:
            rest_dict: dict[str, Any] = {"tool": dim(rest_spec.tool_diameter_mm)}
            if rest_spec.rough_allowance_mm != 0.5:
                rest_dict["rough_allowance"] = dim(rest_spec.rough_allowance_mm)
            if rest_spec.finish_allowance_mm != 0.0:
                rest_dict["finish_allowance"] = dim(rest_spec.finish_allowance_mm)
            result["rest"] = rest_dict
        else:
            result["rest_tool"] = dim(rest_spec.tool_diameter_mm)

    if feature.dogbone is not None:
        result["dogbone"] = _format_dogbone(feature.dogbone)

    if feature.tab_count is not None:
        result["tab_count"] = feature.tab_count
    if feature.tab_height_mm is not None:
        result["tab_height"] = dim(feature.tab_height_mm)
    if feature.tab_width_mm is not None:
        result["tab_width"] = dim(feature.tab_width_mm)
    if feature.onion_skin_mm is not None:
        result["onion_skin_mm"] = dim(feature.onion_skin_mm)

    feeds_dict = _format_feeds_override(feature.feeds_override)
    if feeds_dict is not None:
        result["feeds"] = feeds_dict

    return result


def _format_interface_value(val: str | InterfaceConfig | None) -> Any:
    if val is None:
        return None
    if isinstance(val, str):
        return val
    result: dict[str, Any] = {"joinery": val.joinery}
    if val.finger_width_mm is not None:
        result["finger_width"] = dim(val.finger_width_mm)
    if val.finger_count is not None:
        result["finger_count"] = val.finger_count
    if val.clearance_mm != 0.12:
        result["clearance"] = dim(val.clearance_mm)
    if val.dado_depth_mm is not None:
        result["dado_depth"] = dim(val.dado_depth_mm)
    if val.inset_mm != 0.0:
        result["inset"] = dim(val.inset_mm)
    if val.receiving != "a":
        result["receiving"] = val.receiving
    return result


def _format_beam_feature(feat: BeamFeatureDecl) -> dict[str, Any]:
    dimension_keys = {
        "x_mm",
        "y_mm",
        "width_mm",
        "height_mm",
        "depth_mm",
        "diameter_mm",
        "radius_mm",
        "extension_mm",
        "position_mm",
        "start_mm",
        "end_mm",
    }
    params: dict[str, Any] = {}
    for key, value in feat.params.items():
        if key in dimension_keys and isinstance(value, (int, float)):
            bare_key = key.removesuffix("_mm")
            params[bare_key] = dim(value)
        else:
            params[key] = value
    return {feat.feature_type: params if params else None}


def format_node(node: Any) -> dict[str, Any]:  # noqa: C901 — AST node-type dispatcher
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
        elif node.child and isinstance(node.child, Polygon):
            poly_data = format_polygon_node(node.child)
            poly_data["at"] = {"x": dim(node.x_mm), "y": dim(node.y_mm)}
            return {"Polygon": poly_data}
        elif node.child and isinstance(node.child, Ellipse):
            ell_data = format_ellipse_node(node.child)
            ell_data["at"] = {"x": dim(node.x_mm), "y": dim(node.y_mm)}
            if node.width_mm is not None:
                ell_data["at"]["width"] = dim(node.width_mm)
            if node.height_mm is not None:
                ell_data["at"]["height"] = dim(node.height_mm)
            return {"Ellipse": ell_data}
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
        if DepthMode.is_through(node.depth):
            result["depth"] = DepthMode.THROUGH
        else:
            result["depth"] = dim(node.depth) if isinstance(node.depth, (int, float)) else node.depth
        if node.tab_count is not None:
            result["tab_count"] = node.tab_count
        if node.tab_height_mm is not None:
            result["tab_height"] = dim(node.tab_height_mm)
        if node.tab_width_mm is not None:
            result["tab_width"] = dim(node.tab_width_mm)
        if node.onion_skin_mm is not None:
            result["onion_skin_mm"] = dim(node.onion_skin_mm)
        feeds_dict = _format_feeds_override(node.feeds_override)
        if feeds_dict is not None:
            result["feeds"] = feeds_dict
        return {"Profile": result}

    elif isinstance(node, PocketGen):
        result: dict[str, Any] = {"depth": dim(node.depth_mm)}
        feeds_dict = _format_feeds_override(node.feeds_override)
        if feeds_dict is not None:
            result["feeds"] = feeds_dict
        return {"Pocket": result}

    elif isinstance(node, RaisedPanelGen):
        return {
            "RaisedPanel": {
                "border_width": dim(node.border_width_mm),
                "border_depth": dim(node.border_depth_mm),
                "field_depth": dim(node.field_depth_mm),
            }
        }

    elif isinstance(node, ChamferGen):
        return {"Chamfer": {"width": dim(node.width_mm), "depth": dim(node.depth_mm)}}

    elif isinstance(node, WaveGen):
        return {
            "Wave": {
                "count": node.wave_count,
                "amplitude": dim(node.amplitude_mm),
                "wavelength": dim(node.wavelength_mm),
                "groove": dim(node.groove_width_mm),
                "depth": dim(node.depth_mm),
            }
        }

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
        return {
            "Lines": {
                "angle": node.angle_deg,
                "spacing": dim(node.spacing_mm),
                "width": dim(node.line_width_mm),
                "depth": dim(node.depth_mm),
            }
        }

    elif isinstance(node, FlutingGen):
        result: dict[str, Any] = {
            "spacing": dim(node.spacing_mm),
            "depth": dim(node.depth_mm),
        }
        if node.ramp_mm != 10.0:
            result["ramp"] = dim(node.ramp_mm)
        if node.angle_deg != 0.0:
            result["angle"] = node.angle_deg
        if node.inset_mm != 0.0:
            result["inset"] = dim(node.inset_mm)
        return {"Fluting": result}

    elif isinstance(node, ConcentricBorderGen):
        return {
            "ConcentricBorder": {
                "insets": [dim(i) for i in node.insets_mm],
                "groove": dim(node.groove_width_mm),
                "depth": dim(node.depth_mm),
            }
        }

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
        return {"Polygon": format_polygon_node(node)}

    elif isinstance(node, Triangle):
        result: dict[str, Any] = {"base": dim(node.base_mm), "height": dim(node.height_mm)}
        if node.feature:
            result["feature"] = format_feature(node.feature)
        if node.id:
            result["id"] = node.id
        if node.children:
            result["children"] = [format_node(c) for c in node.children]
        return {"Triangle": result}

    elif isinstance(node, Ellipse):
        return {"Ellipse": format_ellipse_node(node)}

    elif isinstance(node, HoleGridGen):
        result: dict[str, Any] = {
            "spacing": dim(node.spacing_mm),
            "diameter": dim(node.diameter_mm),
        }
        if DepthMode.is_through(node.depth):
            result["depth"] = DepthMode.THROUGH
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
        result = format_measurement_fields(node, dim, default_depth=0.5)
        return {"MeasurementGrid": result if result else None}

    elif isinstance(node, MeasurementEdgeGen):
        result: dict[str, Any] = {"edges": list(node.edges)}
        result.update(format_measurement_fields(node, dim, default_depth=0.3))
        return {"MeasurementEdge": result}

    elif isinstance(node, GridLinesGen):
        result: dict[str, Any] = {}
        if node.unit != "metric":
            result["unit"] = node.unit
        if node.spacing_mm is not None:
            result["spacing"] = dim(node.spacing_mm)
        if node.minor_spacing_mm is not None:
            result["minor_spacing"] = dim(node.minor_spacing_mm)
        if node.depth_mm != 0.3:
            result["depth"] = dim(node.depth_mm)
        if node.minor_lines:
            result["minor_lines"] = True
        return {"GridLines": result if result else None}

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

    elif isinstance(node, AssemblyDecl):
        result: dict[str, Any] = {
            "type": node.type,
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
        if node.interfaces is not None:
            result["interfaces"] = {name: _format_interface_value(val) for name, val in node.interfaces.items()}
        if node.top is not None:
            result["top"] = _format_interface_value(node.top)
        if node.bottom != "captured":
            result["bottom"] = _format_interface_value(node.bottom) if node.bottom is not None else None
        if node.layout_gap_mm != 10.0:
            result["layout_gap"] = dim(node.layout_gap_mm)
        if node.show_labels:
            result["show_labels"] = True
        if node.show_edge_colors:
            result["show_edge_colors"] = True
        if not node.show_dimensions:
            result["show_dimensions"] = False
        if node.cap_style != "between_sides":
            result["cap_style"] = node.cap_style
        if node.back is not None:
            result["back"] = _format_interface_value(node.back)
        if node.back_thickness_mm is not None:
            result["back_thickness"] = dim(node.back_thickness_mm)
        if node.back_inset_mm != 0.0:
            result["back_inset"] = dim(node.back_inset_mm)
        if node.back_joinery is not None:
            result["back_joinery"] = node.back_joinery
        if node.back_rabbet_depth_mm is not None:
            result["back_rabbet_depth"] = dim(node.back_rabbet_depth_mm)
        if not node.back_internal_support:
            result["back_internal_support"] = False
        if node.fixed_shelves:
            result["fixed_shelves"] = node.fixed_shelves
        if node.shelf_joinery != "captured":
            result["shelf_joinery"] = _format_interface_value(node.shelf_joinery)
        if node.shelf_dado_depth_mm is not None:
            result["shelf_dado_depth"] = dim(node.shelf_dado_depth_mm)
        if node.shelf_back_support:
            result["shelf_back_support"] = True
        if node.vertical_partitions:
            result["vertical_partitions"] = node.vertical_partitions
        if node.partition_joinery != "captured":
            result["partition_joinery"] = _format_interface_value(node.partition_joinery)
        if node.partition_dado_depth_mm is not None:
            result["partition_dado_depth"] = dim(node.partition_dado_depth_mm)
        if node.grid is not None:
            result["grid"] = list(node.grid)
        if node.perimeter_joinery != "finger":
            result["perimeter_joinery"] = node.perimeter_joinery
        if node.internal_joinery != "half_lap":
            result["internal_joinery"] = node.internal_joinery
        if node.toe_kick_height_mm is not None:
            result["toe_kick_height"] = dim(node.toe_kick_height_mm)
        if node.toe_kick_depth_mm is not None:
            result["toe_kick_depth"] = dim(node.toe_kick_depth_mm)
        if node.toe_kick_style != "open":
            result["toe_kick_style"] = node.toe_kick_style
        if node.toe_kick_cover:
            result["toe_kick_cover"] = True
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

    elif isinstance(node, BeamDecl):
        result: dict[str, Any] = {
            "name": node.name,
            "length": dim(node.length_mm),
            "width": dim(node.width_mm),
            "thickness": dim(node.thickness_mm),
        }
        if isinstance(node.layers, int):
            if node.layers != 1:
                result["layers"] = node.layers
        else:
            layers_list = []
            for layer in node.layers:
                layer_data: dict[str, Any] = {"length": dim(layer.length_mm)}
                if layer.offset_mm != 0.0:
                    layer_data["offset"] = dim(layer.offset_mm)
                if layer.cutouts:
                    cutouts_list = []
                    for c in layer.cutouts:
                        cutout_data: dict[str, Any] = {
                            "start": dim(c["start_mm"]),
                            "length": dim(c["length_mm"]),
                        }
                        if c.get("width_mm") is not None:
                            cutout_data["width"] = dim(c["width_mm"])
                        if c.get("offset_from_edge_mm", 0.0) != 0.0:
                            cutout_data["offset"] = dim(c["offset_from_edge_mm"])
                        cutouts_list.append(cutout_data)
                    layer_data["cutouts"] = cutouts_list
                layers_list.append(layer_data)
            result["layers"] = layers_list
        if node.role is not None:
            result["role"] = node.role
        if node.face_features:
            result["face_features"] = [_format_beam_feature(f) for f in node.face_features]
        if node.end_features:
            result["end_features"] = [_format_beam_feature(f) for f in node.end_features]
        if node.edge_features:
            result["edge_features"] = [_format_beam_feature(f) for f in node.edge_features]
        if node.show_labels:
            result["show_labels"] = True
        return {"Beam": result}

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


def format_polygon_node(node: Polygon) -> dict[str, Any]:
    result: dict[str, Any] = {"points": [[dim(p[0]), dim(p[1])] for p in node.points]}
    if node.id:
        result["id"] = node.id
    if node.feature:
        result["feature"] = format_feature(node.feature)
    if node.children:
        result["children"] = [format_node(c) for c in node.children]
    return result


def format_ellipse_node(node: Ellipse) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if node.rx_mm is not None:
        result["rx"] = dim(node.rx_mm)
    if node.ry_mm is not None:
        result["ry"] = dim(node.ry_mm)
    if node.id:
        result["id"] = node.id
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
    if ast.sheet.gcode_output != "per-operation":
        data["Sheet"]["gcode_output"] = ast.sheet.gcode_output

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


def _holding_to_dict(holding: HoldingSpec) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if holding.onion_skin_mm is not None:
        result["onion_skin"] = dim(holding.onion_skin_mm)
    if holding.tab_count is not None:
        result["tab_count"] = holding.tab_count
    if holding.tab_height_mm is not None:
        result["tab_height"] = dim(holding.tab_height_mm)
    if holding.tab_width_mm is not None:
        result["tab_width"] = dim(holding.tab_width_mm)
    return result


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
    if job.holding is not None:
        data["Nest"]["holding"] = _holding_to_dict(job.holding)

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
        if part.holding is not None and part.holding != job.holding:
            part_data["holding"] = _holding_to_dict(part.holding)
        parts_list.append(part_data)

    data["Nest"]["parts"] = parts_list

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120

    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


__all__ = [
    "format_nest_yaml",
    "format_pml_yaml",
]
