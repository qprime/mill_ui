from __future__ import annotations

import re
from typing import Any

from ruamel.yaml import YAML

from core.constants import DepthMode
from layout_ast.compositional import (
    Arch,
    AtPosition,
    Cell,
    ChamferGen,
    Circle,
    ComponentDef,
    CompositionalLayoutAST,
    ConcentricBorderGen,
    Edge,
    Ellipse,
    EngraveTextGen,
    FlutingGen,
    Frame,
    Grid,
    GridLinesGen,
    HeightfieldGen,
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
    RoundoverGen,
    ShellGen,
    SplinePath,
    Split,
    SplitGrid,
    SplitHorizontal,
    SplitHorizontalGaps,
    SplitVertical,
    Subtract,
    SurfaceDecl,
    SvgStampGen,
    TemplateDef,
    Triangle,
    UseComponent,
    WasteCuts,
    WaveGen,
    XPanelGen,
)
from layout_ast.layout import DogboneSpec, Feature, FeedsOverride, RestSpec, Sheet
from pml.measurement_fields import parse_measurement_fields
from pml.nest_parser import HoldingSpec, NestJob, NestParseError, NestPart

_VALID_SHAPE_TYPES = ("Rect", "RoundedRect", "Circle", "Polygon", "Triangle", "Ellipse")


class PMLParseError(Exception):
    def __init__(self, message: str, path: str = ""):
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


def _require(node_data: dict, key: str, path: str) -> Any:
    try:
        return node_data[key]
    except KeyError:
        raise PMLParseError(f"Missing required key '{key}'", path) from None


def parse_dimension(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.match(r"^(-?[\d.]+)\s*mm$", value.strip())
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


def _safe_float(value: Any, field: str, path: str) -> float:
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        raise PMLParseError(f"Invalid {field}: {e}", path) from e


def _safe_int(value: Any, field: str, path: str) -> int:
    try:
        return int(value)
    except (ValueError, TypeError) as e:
        raise PMLParseError(f"Invalid {field}: {e}", path) from e


def _parse_interface_config(data: dict, default_joinery: str = "butt") -> InterfaceConfig:
    dogbone_raw = data.get("dogbone")
    dogbone: DogboneSpec | bool | None = None
    if dogbone_raw is False:
        dogbone = False
    elif dogbone_raw is True:
        dogbone = True
    elif isinstance(dogbone_raw, dict):
        dogbone = DogboneSpec(
            style=dogbone_raw.get("style", "dogbone"),
            diameter_mm=parse_dimension(dogbone_raw["diameter"]) if "diameter" in dogbone_raw else None,
            overcut_mm=parse_dimension(dogbone_raw["overcut"]) if "overcut" in dogbone_raw else 0.0,
        )

    return InterfaceConfig(
        joinery=data.get("joinery", default_joinery),
        finger_width_mm=parse_dimension(data["finger_width"]) if "finger_width" in data else None,
        finger_count=data.get("finger_count"),
        clearance_mm=parse_dimension(data.get("clearance", "0.12mm")),
        dado_depth_mm=parse_dimension(data["dado_depth"]) if "dado_depth" in data else None,
        inset_mm=parse_dimension(data.get("inset", "0mm")),
        receiving=data.get("receiving", "a"),
        dogbone=dogbone,
    )


def parse_children(children_data: list[dict] | None, path: str = "") -> tuple[Any, ...]:
    if not children_data:
        return ()
    return tuple(parse_node(child, f"{path}.children[{i}]") for i, child in enumerate(children_data))


def _parse_feeds_override(data: dict | None, path: str = "") -> FeedsOverride | None:
    if not data:
        return None
    try:
        return FeedsOverride(
            rpm=float(data["rpm"]) if "rpm" in data else None,
            feed_xy=float(data["feed_xy"]) if "feed_xy" in data else None,
            feed_z=float(data["feed_z"]) if "feed_z" in data else None,
            depth_per_pass=float(data["depth_per_pass"]) if "depth_per_pass" in data else None,
            stepover_percent=float(data["stepover_percent"]) if "stepover_percent" in data else None,
        )
    except (ValueError, TypeError) as e:
        raise PMLParseError(f"Invalid feeds_override: {e}", path) from e


def parse_feature(data: dict, path: str = "", sheet_thickness_mm: float = 0.0) -> Feature:
    feature_type = data.get("type")
    if feature_type is None:
        raise PMLParseError("Feature missing 'type'", path)

    depth = data.get("depth", "through")
    is_through = DepthMode.is_through(depth)

    depth_mm = sheet_thickness_mm if is_through else float(parse_dimension(depth))

    dogbone: DogboneSpec | None = None
    dogbone_raw = data.get("dogbone")
    if dogbone_raw is True:
        dogbone = DogboneSpec()
    elif isinstance(dogbone_raw, dict):
        dogbone = DogboneSpec(
            style=dogbone_raw.get("style", "dogbone"),
            diameter_mm=parse_dimension(dogbone_raw["diameter"]) if "diameter" in dogbone_raw else None,
            overcut_mm=parse_dimension(dogbone_raw["overcut"]) if "overcut" in dogbone_raw else 0.0,
        )

    rest: RestSpec | None = None
    rest_raw = data.get("rest")
    rest_tool_raw = data.get("rest_tool")
    if rest_raw is not None and rest_tool_raw is not None:
        raise PMLParseError("Cannot specify both 'rest' and 'rest_tool'", path)
    if isinstance(rest_raw, dict):
        rest = RestSpec(
            tool_diameter_mm=parse_dimension(_require(rest_raw, "tool", path + ".rest")),
            rough_allowance_mm=parse_dimension(rest_raw["rough_allowance"]) if "rough_allowance" in rest_raw else 0.5,
            finish_allowance_mm=parse_dimension(rest_raw["finish_allowance"])
            if "finish_allowance" in rest_raw
            else 0.0,
        )
    elif rest_tool_raw is not None:
        rest = RestSpec(tool_diameter_mm=parse_dimension(rest_tool_raw))

    return Feature(
        type=feature_type,
        depth_mm=depth_mm,
        side=data.get("side"),
        is_through=is_through,
        corner_cleanup_tool_diameter_mm=parse_dimension(data["corner_cleanup"]) if "corner_cleanup" in data else None,
        dogbone=dogbone,
        rest=rest,
        tab_count=data.get("tab_count"),
        tab_height_mm=parse_dimension(data["tab_height"]) if "tab_height" in data else None,
        tab_width_mm=parse_dimension(data["tab_width"]) if "tab_width" in data else None,
        onion_skin_mm=parse_dimension(data["onion_skin_mm"]) if "onion_skin_mm" in data else None,
        feeds_override=_parse_feeds_override(data.get("feeds"), f"{path}.feeds"),
    )


def _parse_joinery_field(raw: Any, default_joinery: str = "butt") -> str | InterfaceConfig | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return _parse_interface_config(raw, default_joinery=default_joinery)
    return None


def _parse_assembly_node(node_data: dict, children: tuple, path: str) -> Any:
    from layout_ast.compositional import AssemblyDecl

    assembly_type = node_data.get("type", "box")

    interfaces_raw = node_data.get("interfaces")
    interfaces: dict[str, str | InterfaceConfig] | None = None
    if interfaces_raw:
        interfaces = {}
        for iface_name, iface_data in interfaces_raw.items():
            if isinstance(iface_data, str):
                interfaces[iface_name] = iface_data
            elif isinstance(iface_data, dict):
                interfaces[iface_name] = _parse_interface_config(iface_data)

    top = _parse_joinery_field(node_data.get("top"))
    bottom = _parse_joinery_field(node_data.get("bottom", "captured"), default_joinery="captured")
    back_raw = node_data.get("back")
    back = _parse_joinery_field(back_raw, default_joinery="captured")

    grid_raw = node_data.get("grid")
    grid = None
    if grid_raw and isinstance(grid_raw, list) and len(grid_raw) == 2:
        try:
            grid = (int(grid_raw[0]), int(grid_raw[1]))
        except (ValueError, TypeError) as e:
            raise PMLParseError(f"Invalid grid values: {e}", path) from e

    shelf_joinery: str | InterfaceConfig = (
        _parse_joinery_field(node_data.get("shelf_joinery", "captured"), default_joinery="captured") or "captured"
    )
    partition_joinery: str | InterfaceConfig = (
        _parse_joinery_field(node_data.get("partition_joinery", "captured"), default_joinery="captured") or "captured"
    )

    dims = node_data.get("dimensions") if isinstance(node_data.get("dimensions"), list) else None

    raw_w = node_data.get("width")
    if raw_w is None:
        raw_w = dims[0] if dims and len(dims) > 0 else _require(node_data, "width", f"{path}.Assembly")

    raw_d = node_data.get("depth")
    if raw_d is None:
        raw_d = dims[1] if dims and len(dims) > 1 else _require(node_data, "depth", f"{path}.Assembly")

    raw_h = node_data.get("height")
    if raw_h is None:
        raw_h = dims[2] if dims and len(dims) > 2 else _require(node_data, "height", f"{path}.Assembly")

    return AssemblyDecl(
        type=assembly_type,
        width_mm=parse_dimension(raw_w),
        depth_mm=parse_dimension(raw_d),
        height_mm=parse_dimension(raw_h),
        thickness_mm=parse_dimension(_require(node_data, "thickness", f"{path}.Assembly")),
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
        back_thickness_mm=parse_dimension(node_data["back_thickness"])
        if "back_thickness" in node_data
        else (
            parse_dimension(back_raw["thickness"]) if isinstance(back_raw, dict) and "thickness" in back_raw else None
        ),
        back_inset_mm=parse_dimension(node_data.get("back_inset", "0mm"))
        if "back_inset" in node_data
        else (parse_dimension(back_raw.get("inset", "0mm")) if isinstance(back_raw, dict) else 0.0),
        back_joinery=node_data.get("back_joinery"),
        back_rabbet_depth_mm=parse_dimension(node_data["back_rabbet_depth"])
        if "back_rabbet_depth" in node_data
        else None,
        back_internal_support=node_data.get("back_internal_support", True),
        fixed_shelves=node_data.get("fixed_shelves", 0),
        shelf_joinery=shelf_joinery,
        shelf_dado_depth_mm=parse_dimension(node_data["shelf_dado_depth"]) if "shelf_dado_depth" in node_data else None,
        shelf_back_support=node_data.get("shelf_back_support", False),
        vertical_partitions=node_data.get("vertical_partitions", 0),
        partition_joinery=partition_joinery,
        partition_dado_depth_mm=parse_dimension(node_data["partition_dado_depth"])
        if "partition_dado_depth" in node_data
        else None,
        grid=grid,
        perimeter_joinery=node_data.get("perimeter_joinery", node_data.get("joinery", "finger")),
        internal_joinery=node_data.get("internal_joinery", "half_lap"),
        toe_kick_height_mm=parse_dimension(node_data["toe_kick_height"]) if "toe_kick_height" in node_data else None,
        toe_kick_depth_mm=parse_dimension(node_data["toe_kick_depth"]) if "toe_kick_depth" in node_data else None,
        toe_kick_style=node_data.get("toe_kick_style", "open"),
        toe_kick_cover=node_data.get("toe_kick_cover", False),
    )


def _parse_beam_feature(feat_data: dict, feat_path: str):
    from layout_ast.compositional import BeamFeatureDecl

    feat_keys = [k for k in feat_data if k[0].isupper()]
    if len(feat_keys) != 1:
        raise PMLParseError(f"Invalid beam feature: {feat_data}", feat_path)
    feat_type = feat_keys[0]
    feat_params = feat_data[feat_type] or {}
    parsed_params: dict[str, Any] = {}
    dimension_keys = {
        "x",
        "y",
        "width",
        "height",
        "depth",
        "diameter",
        "radius",
        "extension",
        "position",
        "start",
        "end",
    }
    literal_values = {"left", "right", "top", "bottom", "front", "back"}
    for key, value in feat_params.items():
        if key in dimension_keys and value is not None:
            if isinstance(value, str) and value in literal_values:
                parsed_params[key] = value
            else:
                parsed_params[f"{key}_mm"] = parse_dimension(value)
        else:
            parsed_params[key] = value
    return BeamFeatureDecl(feature_type=feat_type, params=parsed_params)


def _parse_beam_node(node_data: dict, path: str) -> Any:
    from layout_ast.compositional import BeamDecl, BeamLayerDecl

    layers_raw = node_data.get("layers", 1)
    layers: int | tuple[BeamLayerDecl, ...]
    if isinstance(layers_raw, int):
        layers = layers_raw
    elif isinstance(layers_raw, list):
        parsed_layers = []
        for layer_data in layers_raw:
            cutouts: tuple[()] | tuple[dict, ...] = ()
            if "cutouts" in layer_data:
                cutouts = tuple(
                    {
                        "start_mm": parse_dimension(_require(c, "start", f"{path}.Beam.layer.cutout")),
                        "length_mm": parse_dimension(_require(c, "length", f"{path}.Beam.layer.cutout")),
                        "width_mm": parse_dimension(c["width"]) if "width" in c else None,
                        "offset_from_edge_mm": parse_dimension(c.get("offset", "0mm")),
                    }
                    for c in layer_data["cutouts"]
                )
            parsed_layers.append(
                BeamLayerDecl(
                    length_mm=parse_dimension(_require(layer_data, "length", f"{path}.Beam.layer")),
                    offset_mm=parse_dimension(layer_data.get("offset", "0mm")),
                    cutouts=cutouts,
                )
            )
        layers = tuple(parsed_layers)
    else:
        layers = 1

    face_features = tuple(
        _parse_beam_feature(f, f"{path}.face_features[{i}]") for i, f in enumerate(node_data.get("face_features", []))
    )
    end_features = tuple(
        _parse_beam_feature(f, f"{path}.end_features[{i}]") for i, f in enumerate(node_data.get("end_features", []))
    )
    edge_features = tuple(
        _parse_beam_feature(f, f"{path}.edge_features[{i}]") for i, f in enumerate(node_data.get("edge_features", []))
    )

    return BeamDecl(
        name=node_data.get("name", "beam"),
        length_mm=parse_dimension(_require(node_data, "length", f"{path}.Beam")),
        width_mm=parse_dimension(_require(node_data, "width", f"{path}.Beam")),
        thickness_mm=parse_dimension(_require(node_data, "thickness", f"{path}.Beam")),
        layers=layers,
        role=node_data.get("role"),
        face_features=face_features,
        end_features=end_features,
        edge_features=edge_features,
        show_labels=node_data.get("show_labels", False),
    )


def _parse_radial_node(node_data: dict, path: str) -> Any:
    from layout_ast.compositional import RadialLabelGen, RadialPocketGen, RadialTickGen

    element = node_data.get("element", {})
    element_type = element.get("type", "pocket")
    ctx = f"{path}.Radial"

    rays = _safe_int(_require(node_data, "rays", ctx), "rays", ctx)
    depth_mm = parse_dimension(_require(node_data, "depth", ctx))
    start_angle_deg = _safe_float(node_data.get("start_angle", 0), "start_angle", ctx)
    end_angle_deg = _safe_float(node_data.get("end_angle", 360), "end_angle", ctx)
    radius_mm = parse_dimension(node_data["radius"]) if "radius" in node_data else None

    if element_type == "pocket":
        return RadialPocketGen(
            rays=rays,
            depth_mm=depth_mm,
            bar_width_mm=parse_dimension(element.get("bar_width", "0mm")),
            shape=element.get("shape", "triangle"),
            center_shape=element.get("center_shape"),
            center_size_mm=parse_dimension(element["center_size"]) if "center_size" in element else None,
            start_angle_deg=start_angle_deg,
            end_angle_deg=end_angle_deg,
            radius_mm=radius_mm,
        )

    if element_type == "tick":
        label_list_raw = element.get("label_list")
        label_list = tuple(str(v) for v in label_list_raw) if label_list_raw else None
        return RadialTickGen(
            rays=rays,
            depth_mm=depth_mm,
            minor_subdivisions=_safe_int(node_data.get("minor_subdivisions", 0), "minor_subdivisions", ctx),
            tick_length_mm=parse_dimension(element["tick_length"]) if "tick_length" in element else None,
            minor_tick_length_mm=(
                parse_dimension(element["minor_tick_length"]) if "minor_tick_length" in element else None
            ),
            inward=element.get("inward", False),
            labels=element.get("labels", False),
            label_list=label_list,
            label_height_mm=parse_dimension(element.get("label_height", "3mm")),
            start_angle_deg=start_angle_deg,
            end_angle_deg=end_angle_deg,
            radius_mm=radius_mm,
        )

    if element_type == "label":
        values_raw = element.get("values")
        values = tuple(str(v) for v in values_raw) if values_raw else None
        return RadialLabelGen(
            rays=rays,
            depth_mm=depth_mm,
            values=values,
            label_height_mm=parse_dimension(element.get("height", "3mm")),
            start_angle_deg=start_angle_deg,
            end_angle_deg=end_angle_deg,
            radius_mm=radius_mm,
        )

    if element_type == "svg":
        from layout_ast.compositional import RadialSvgGen

        return RadialSvgGen(
            rays=rays,
            depth_mm=depth_mm,
            svg_path=_require(element, "path", f"{ctx}.element"),
            feature_type=element.get("feature", "engrave"),
            scale_mode=element.get("scale", "fit"),
            svg_unit_mm=_safe_float(element.get("svg_unit", 1.0), "svg_unit", ctx),
            rotate_element=element.get("rotate", True),
            start_angle_deg=start_angle_deg,
            end_angle_deg=end_angle_deg,
            radius_mm=radius_mm,
            stamp_size_mm=parse_dimension(element["size"]) if "size" in element else None,
        )

    raise PMLParseError(f"Unknown Radial element type: '{element_type}'", ctx)


def parse_node(data: dict, path: str = "") -> Any:  # noqa: C901 — PML node-type dispatcher
    if not isinstance(data, dict):
        raise PMLParseError(f"Expected dict, got {type(data).__name__}", path)

    keys = [k for k in data if k not in ("id", "children", "feature")]
    type_keys = [k for k in keys if k[0].isupper()]

    if len(type_keys) == 0:
        raise PMLParseError(f"No node type found in {list(data.keys())}", path)
    if len(type_keys) > 1:
        raise PMLParseError(f"Multiple node types found: {type_keys}", path)

    node_type = type_keys[0]
    node_data = data[node_type]
    if node_data is None:
        node_data = {}

    if node_type == "Radial":
        return _parse_radial_node(node_data, path)

    if node_type == "SvgStamp":
        depth = parse_dimension_or_through(_require(node_data, "depth", f"{path}.SvgStamp"))
        return SvgStampGen(
            svg_path=_require(node_data, "path", f"{path}.SvgStamp"),
            depth=depth,
            feature_type=node_data.get("feature", "engrave"),
            scale_mode=node_data.get("scale", "fit"),
            svg_unit_mm=_safe_float(node_data.get("svg_unit", 1.0), "svg_unit", f"{path}.SvgStamp"),
            center=node_data.get("center", True),
            invert_y=node_data.get("invert_y", True),
        )

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
    node_label = node_data.get("label") if isinstance(node_data, dict) else None

    if node_type == "Panel":
        return Panel(children=children, id=node_id)

    elif node_type == "Rect":
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        rect = Rect(children=children, feature=feature, id=node_id, label=node_label)
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
            label=node_label,
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
        radius_mm = parse_dimension(_require(node_data, "radius", f"{path}.RoundedRect"))
        corners = None
        if "corners" in node_data:
            corners = frozenset(node_data["corners"])
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        rounded_rect = RoundedRect(
            radius_mm=radius_mm,
            children=children,
            feature=feature,
            id=node_id,
            label=node_label,
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
            orientation=_require(node_data, "orientation", f"{path}.Line"),
            feature=feature,
            id=node_id,
            label=node_label,
        )

    elif node_type == "Polyline":
        points = tuple(tuple(p) for p in _require(node_data, "points", f"{path}.Polyline"))
        return Polyline(points=points, feature=feature, id=node_id, label=node_label)

    elif node_type == "Spline":
        points = tuple(tuple(p) for p in _require(node_data, "points", f"{path}.Spline"))
        tolerance_mm = parse_dimension(node_data.get("tolerance", "0.1mm"))
        return SplinePath(points=points, feature=feature, tolerance_mm=tolerance_mm, id=node_id, label=node_label)

    elif node_type == "Keepout":

        def contains_keepout(nodes: tuple) -> bool:
            for node in nodes:
                if isinstance(node, Keepout):
                    return True
                if hasattr(node, "children") and node.children and contains_keepout(node.children):
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
            rough_allowance_mm=parse_dimension(node_data["rough_allowance"])
            if "rough_allowance" in node_data
            else None,
            finish_allowance_mm=parse_dimension(node_data["finish_allowance"])
            if "finish_allowance" in node_data
            else None,
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
            width_mm=parse_dimension(_require(node_data, "width", f"{path}.Frame")),
            children=children,
        )

    elif node_type == "Grid":
        return Grid(
            rows=_require(node_data, "rows", f"{path}.Grid"),
            cols=_require(node_data, "cols", f"{path}.Grid"),
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
            rows=_require(node_data, "rows", f"{path}.Split"),
            cols=_require(node_data, "cols", f"{path}.Split"),
            rail_mm=parse_dimension(node_data.get("rail", "0mm")),
            mullion_mm=parse_dimension(node_data.get("mullion", "0mm")),
            children=children,
        )

    elif node_type == "Profile":
        depth = parse_dimension_or_through(node_data.get("depth", "through"))
        return ProfileGen(
            side=_require(node_data, "side", f"{path}.Profile"),
            depth=depth,
            tab_count=node_data.get("tab_count"),
            tab_height_mm=parse_dimension(node_data["tab_height"]) if "tab_height" in node_data else None,
            tab_width_mm=parse_dimension(node_data["tab_width"]) if "tab_width" in node_data else None,
            onion_skin_mm=parse_dimension(node_data["onion_skin_mm"]) if "onion_skin_mm" in node_data else None,
            feeds_override=_parse_feeds_override(node_data.get("feeds"), f"{path}.Profile.feeds"),
        )

    elif node_type == "Pocket":
        return PocketGen(
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Pocket")),
            feeds_override=_parse_feeds_override(node_data.get("feeds"), f"{path}.Pocket.feeds"),
        )

    elif node_type == "RaisedPanel":
        return RaisedPanelGen(
            border_width_mm=parse_dimension(_require(node_data, "border_width", f"{path}.RaisedPanel")),
            border_depth_mm=parse_dimension(_require(node_data, "border_depth", f"{path}.RaisedPanel")),
            field_depth_mm=parse_dimension(_require(node_data, "field_depth", f"{path}.RaisedPanel")),
        )

    elif node_type == "Chamfer":
        return ChamferGen(
            width_mm=parse_dimension(_require(node_data, "width", f"{path}.Chamfer")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Chamfer")),
        )

    elif node_type == "Roundover":
        return RoundoverGen(
            radius_mm=parse_dimension(_require(node_data, "radius", f"{path}.Roundover")),
        )

    elif node_type == "Wave":
        return WaveGen(
            wave_count=_require(node_data, "count", f"{path}.Wave"),
            amplitude_mm=parse_dimension(_require(node_data, "amplitude", f"{path}.Wave")),
            wavelength_mm=parse_dimension(_require(node_data, "wavelength", f"{path}.Wave")),
            groove_width_mm=parse_dimension(_require(node_data, "groove", f"{path}.Wave")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Wave")),
        )

    elif node_type == "XPanel":
        return XPanelGen(
            bar_width_mm=parse_dimension(_require(node_data, "bar_width", f"{path}.XPanel")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.XPanel")),
        )

    elif node_type == "SplitHorizontal":
        return SplitHorizontal(
            n=_require(node_data, "count", f"{path}.SplitHorizontal"),
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "SplitVertical":
        return SplitVertical(
            n=_require(node_data, "count", f"{path}.SplitVertical"),
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "SplitGrid":
        return SplitGrid(
            rows=_require(node_data, "rows", f"{path}.SplitGrid"),
            cols=_require(node_data, "cols", f"{path}.SplitGrid"),
            gap_mm=parse_dimension(node_data.get("gap", "0mm")),
            children=children,
        )

    elif node_type == "SplitHorizontalGaps":
        return SplitHorizontalGaps(
            n=_require(node_data, "count", f"{path}.SplitHorizontalGaps"),
            gap_mm=parse_dimension(_require(node_data, "gap", f"{path}.SplitHorizontalGaps")),
            children=children,
        )

    elif node_type == "Lines":
        return LinesGen(
            angle_deg=_safe_float(_require(node_data, "angle", f"{path}.Lines"), "angle", f"{path}.Lines"),
            spacing_mm=parse_dimension(_require(node_data, "spacing", f"{path}.Lines")),
            line_width_mm=parse_dimension(_require(node_data, "width", f"{path}.Lines")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Lines")),
        )

    elif node_type == "Heightfield":
        size_data = _require(node_data, "size", f"{path}.Heightfield")
        if not isinstance(size_data, dict) or "width" not in size_data or "height" not in size_data:
            raise PMLParseError("Heightfield 'size' must have 'width' and 'height' keys", path)
        return HeightfieldGen(
            image_path=_require(node_data, "image", f"{path}.Heightfield"),
            width_mm=parse_dimension(size_data["width"]),
            height_mm=parse_dimension(size_data["height"]),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Heightfield")),
            white_is_high=node_data.get("white_is_high", True),
        )

    elif node_type == "Fluting":
        return FlutingGen(
            spacing_mm=parse_dimension(_require(node_data, "spacing", f"{path}.Fluting")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Fluting")),
            ramp_mm=parse_dimension(node_data.get("ramp", "10mm")),
            angle_deg=_safe_float(node_data.get("angle", 0), "angle", f"{path}.Fluting"),
            inset_mm=parse_dimension(node_data.get("inset", "0mm")),
        )

    elif node_type == "ConcentricBorder":
        insets = [parse_dimension(i) for i in _require(node_data, "insets", f"{path}.ConcentricBorder")]
        return ConcentricBorderGen(
            insets_mm=tuple(insets),
            groove_width_mm=parse_dimension(_require(node_data, "groove", f"{path}.ConcentricBorder")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.ConcentricBorder")),
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
            x_mm=parse_dimension(_require(node_data, "x", f"{path}.AtPosition")),
            y_mm=parse_dimension(_require(node_data, "y", f"{path}.AtPosition")),
            width_mm=parse_dimension(node_data["width"]) if "width" in node_data else None,
            height_mm=parse_dimension(node_data["height"]) if "height" in node_data else None,
            child=child,
        )

    elif node_type == "Subtract":
        return Subtract(
            inner_inset_mm=parse_dimension(_require(node_data, "inner_inset", f"{path}.Subtract")),
            children=children,
        )

    elif node_type == "Shell":
        depth_raw = node_data.get("depth", "through")
        depth = parse_dimension_or_through(depth_raw)
        return ShellGen(
            wall_mm=parse_dimension(_require(node_data, "wall", f"{path}.Shell")),
            interior=_require(node_data, "interior", f"{path}.Shell"),
            depth=depth,
            children=children,
        )

    elif node_type == "Arch":
        return Arch(
            width_mm=parse_dimension(_require(node_data, "width", f"{path}.Arch")),
            height_mm=parse_dimension(_require(node_data, "height", f"{path}.Arch")),
            radius_mm=parse_dimension(_require(node_data, "radius", f"{path}.Arch")),
            children=children,
            feature=feature,
            id=node_id,
            label=node_label,
        )

    elif node_type == "Polygon":
        points = tuple(
            (parse_dimension(p[0]), parse_dimension(p[1])) for p in _require(node_data, "points", f"{path}.Polygon")
        )
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        polygon = Polygon(points=points, children=children, feature=feature, id=node_id, label=node_label)
        if at_data:
            return AtPosition(
                x_mm=parse_dimension(at_data.get("x")),
                y_mm=parse_dimension(at_data.get("y")),
                child=polygon,
            )
        return polygon

    elif node_type == "Triangle":
        return Triangle(
            base_mm=parse_dimension(_require(node_data, "base", f"{path}.Triangle")),
            height_mm=parse_dimension(_require(node_data, "height", f"{path}.Triangle")),
            children=children,
            feature=feature,
            id=node_id,
            label=node_label,
        )

    elif node_type == "Ellipse":
        rx_mm = parse_dimension(node_data["rx"]) if "rx" in node_data else None
        ry_mm = parse_dimension(node_data["ry"]) if "ry" in node_data else None
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        ellipse = Ellipse(
            rx_mm=rx_mm,
            ry_mm=ry_mm,
            children=children,
            feature=feature,
            id=node_id,
            label=node_label,
        )
        if at_data:
            return AtPosition(
                x_mm=parse_dimension(at_data.get("x")),
                y_mm=parse_dimension(at_data.get("y")),
                width_mm=parse_dimension(at_data["width"]) if "width" in at_data else None,
                height_mm=parse_dimension(at_data["height"]) if "height" in at_data else None,
                child=ellipse,
            )
        return ellipse

    elif node_type == "HoleGrid":
        depth = parse_dimension_or_through(node_data.get("depth", "through"))
        return HoleGridGen(
            spacing_mm=parse_dimension(_require(node_data, "spacing", f"{path}.HoleGrid")),
            diameter_mm=parse_dimension(_require(node_data, "diameter", f"{path}.HoleGrid")),
            depth=depth,
            pattern=node_data.get("pattern", "rectangular"),
            inset_mm=parse_dimension(node_data.get("inset", "0mm")),
            align=node_data.get("align", "center"),
        )

    elif node_type == "MeasurementGrid":
        fields = parse_measurement_fields(node_data, parse_dimension)
        return MeasurementGridGen(
            depth_mm=parse_dimension(node_data.get("depth", "0.5mm")),
            **fields,
        )

    elif node_type == "MeasurementEdge":
        edges = tuple(_require(node_data, "edges", f"{path}.MeasurementEdge"))
        fields = parse_measurement_fields(node_data, parse_dimension)
        return MeasurementEdgeGen(
            edges=edges,
            depth_mm=parse_dimension(node_data.get("depth", "0.3mm")),
            **fields,
        )

    elif node_type == "GridLines":
        return GridLinesGen(
            unit=node_data.get("unit", "metric"),
            spacing_mm=parse_dimension(node_data["spacing"]) if "spacing" in node_data else None,
            minor_spacing_mm=parse_dimension(node_data["minor_spacing"]) if "minor_spacing" in node_data else None,
            depth_mm=parse_dimension(node_data.get("depth", "0.3mm")),
            minor_lines=node_data.get("minor_lines", False),
        )

    elif node_type == "EngraveText":
        from generators.area.engrave_text import VALID_FONT_NAMES

        font = node_data.get("font", "rowmans")
        if font not in VALID_FONT_NAMES:
            raise PMLParseError(
                f"Unknown font '{font}'; valid fonts: {', '.join(sorted(VALID_FONT_NAMES))}",
                f"{path}.EngraveText",
            )
        return EngraveTextGen(
            text=_require(node_data, "text", f"{path}.EngraveText"),
            height_mm=parse_dimension(node_data.get("height", "4mm")),
            depth_mm=parse_dimension(node_data.get("depth", "0.3mm")),
            font=font,
            alignment=node_data.get("alignment", "left"),
            orientation=node_data.get("orientation", "horizontal"),
        )

    elif node_type == "WasteCuts":
        return WasteCuts(
            min_width_mm=parse_dimension(node_data.get("min_width", "200mm")),
            min_height_mm=parse_dimension(node_data.get("min_height", "200mm")),
            margin_mm=parse_dimension(node_data["margin"]) if "margin" in node_data else None,
            tab_count=_require(node_data, "tab_count", f"{path}.WasteCuts"),
            tab_height_mm=parse_dimension(_require(node_data, "tab_height", f"{path}.WasteCuts")),
            strategy=node_data.get("strategy", "largest"),
        )

    elif node_type == "Assembly":
        return _parse_assembly_node(node_data, children, path)

    elif node_type == "UseComponent":
        return UseComponent(
            component_name=_require(node_data, "name", f"{path}.UseComponent"),
            args=node_data.get("args", {}),
        )

    elif node_type == "Engrave":
        depth_mm = parse_dimension(_require(node_data, "depth", f"{path}.Engrave"))
        return Feature(
            type="engrave",
            depth_mm=depth_mm,
        )

    elif node_type == "Beam":
        return _parse_beam_node(node_data, path)

    else:
        raise PMLParseError(f"Unknown node type: {node_type}", path)


def _parse_surface_block(block: dict | None) -> SurfaceDecl | None:
    if block is None:
        return None
    depth_mm = parse_dimension(_require(block, "depth-per-pass", "Surface"))
    if depth_mm <= 0.0:
        raise PMLParseError("Surface depth-per-pass must be > 0", "Surface")
    passes = _safe_int(block.get("passes", 1), "passes", "Surface")
    if passes < 1:
        raise PMLParseError("Surface passes must be >= 1", "Surface")
    stepover_raw = block.get("stepover", "70%")
    if isinstance(stepover_raw, str) and stepover_raw.endswith("%"):
        stepover_pct = _safe_float(stepover_raw[:-1], "stepover", "Surface")
    else:
        stepover_pct = _safe_float(stepover_raw, "stepover", "Surface")
    if stepover_pct <= 0.0 or stepover_pct > 100.0:
        raise PMLParseError("Surface stepover must be > 0% and <= 100%", "Surface")
    direction = str(block.get("direction", "x"))
    if direction not in ("x", "y"):
        raise PMLParseError(f"Surface direction must be 'x' or 'y', got '{direction}'", "Surface")
    margin_mm = parse_dimension(block.get("margin-overrun", "0mm"))
    if margin_mm < 0.0:
        raise PMLParseError("Surface margin-overrun must be >= 0", "Surface")
    cool_every = _safe_int(block.get("cool_every", 0), "cool_every", "Surface")
    if cool_every < 0:
        raise PMLParseError("Surface cool_every must be >= 0", "Surface")
    cool_dwell_raw = block.get("cool_dwell", "0s")
    if isinstance(cool_dwell_raw, str) and cool_dwell_raw.endswith("s"):
        cool_dwell_s = _safe_float(cool_dwell_raw[:-1], "cool_dwell", "Surface")
    else:
        cool_dwell_s = _safe_float(cool_dwell_raw, "cool_dwell", "Surface")
    if cool_dwell_s < 0.0:
        raise PMLParseError("Surface cool_dwell must be >= 0", "Surface")
    return SurfaceDecl(
        depth_mm=depth_mm,
        passes=passes,
        stepover_pct=stepover_pct,
        direction=direction,
        margin_mm=margin_mm,
        cool_every=cool_every,
        cool_dwell_s=cool_dwell_s,
    )


def parse_pml_yaml(source: str) -> CompositionalLayoutAST:
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(source)
    except Exception as e:
        raise PMLParseError(f"Invalid YAML: {e}") from e

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
        thickness_mm=parse_dimension(_require(sheet_block, "thickness", "Sheet")),
        margin_mm=margin_mm,
        show_dimensions=sheet_block.get("show_dimensions", True),
        material=str(sheet_block.get("material", "mdf")),
        gcode_output=str(sheet_block.get("gcode_output", "per-operation")),
    )

    project = data.get("project")
    kerf_width_mm = parse_dimension(data["kerf"]) if "kerf" in data else None

    surface = _parse_surface_block(data.get("Surface"))

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
        surface=surface,
    )


_VALID_HOLDING_KEYS = {"onion_skin", "tab_count", "tab_height", "tab_width"}


def _parse_holding_block(block: dict[str, Any], path: str) -> HoldingSpec:
    unknown = set(block.keys()) - _VALID_HOLDING_KEYS
    if unknown:
        raise NestParseError(
            f"Unknown key(s) in {path}: {', '.join(sorted(unknown))}. "
            f"Valid keys: {', '.join(sorted(_VALID_HOLDING_KEYS))}"
        )
    kwargs: dict[str, Any] = {}
    if "onion_skin" in block:
        try:
            kwargs["onion_skin_mm"] = parse_dimension(block["onion_skin"])
        except (ValueError, TypeError) as e:
            raise NestParseError(f"Invalid onion_skin in {path}: {e}") from e
    if "tab_count" in block:
        val = block["tab_count"]
        if not isinstance(val, int):
            raise NestParseError(f"Invalid tab_count in {path}: expected integer")
        kwargs["tab_count"] = val
    if "tab_height" in block:
        try:
            kwargs["tab_height_mm"] = parse_dimension(block["tab_height"])
        except (ValueError, TypeError) as e:
            raise NestParseError(f"Invalid tab_height in {path}: {e}") from e
    if "tab_width" in block:
        try:
            kwargs["tab_width_mm"] = parse_dimension(block["tab_width"])
        except (ValueError, TypeError) as e:
            raise NestParseError(f"Invalid tab_width in {path}: {e}") from e
    if not kwargs:
        raise NestParseError(f"Empty holding block in {path}")
    try:
        return HoldingSpec(**kwargs)
    except ValueError as e:
        raise NestParseError(f"Invalid holding in {path}: {e}") from e


def parse_nest_yaml(source: str) -> NestJob:  # noqa: C901 — nest config parser
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(source)
    except Exception as e:
        raise NestParseError(f"Invalid YAML: {e}") from e

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
        raise NestParseError(f"Invalid sheet dimensions: {e}") from e

    kerf_mm = 6.35
    if "kerf" in nest_block:
        try:
            kerf_mm = parse_dimension(nest_block["kerf"])
        except ValueError as e:
            raise NestParseError(f"Invalid kerf: {e}") from e

    margin_mm = 10.0
    if "margin" in nest_block:
        try:
            margin_mm = parse_dimension(nest_block["margin"])
        except ValueError as e:
            raise NestParseError(f"Invalid margin: {e}") from e

    job_holding: HoldingSpec | None = None
    holding_block = nest_block.get("holding")
    if holding_block is not None:
        if not isinstance(holding_block, dict):
            raise NestParseError("Invalid holding: expected a mapping")
        job_holding = _parse_holding_block(holding_block, "Nest.holding")

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
            raise NestParseError(f"Invalid dimensions for part '{name}': {e}") from e

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
                        raise NestParseError(f"Invalid template param '{k}' for part '{name}': {e}") from e
            elif isinstance(template_block, str):
                template = template_block
            else:
                raise NestParseError(f"Invalid template for part '{name}'")

        shape: str | None = None
        shape_params: dict[str, Any] = {}

        shape_block = part_data.get("shape")
        if shape_block is not None:
            if template is not None:
                raise NestParseError(f"Part '{name}' has both 'shape' and 'template' — they are mutually exclusive")
            if not isinstance(shape_block, dict):
                raise NestParseError(f"Invalid shape for part '{name}': expected a mapping")
            shape_type = shape_block.get("type")
            if shape_type not in _VALID_SHAPE_TYPES:
                raise NestParseError(
                    f"Invalid shape type '{shape_type}' for part '{name}'. "
                    f"Must be one of: {', '.join(_VALID_SHAPE_TYPES)}"
                )
            shape = shape_type

            if shape == "RoundedRect":
                radius_raw = shape_block.get("radius")
                if radius_raw is None:
                    raise NestParseError(f"RoundedRect shape for part '{name}' requires 'radius'")
                try:
                    radius_mm = parse_dimension(radius_raw)
                except (ValueError, TypeError) as e:
                    raise NestParseError(f"Invalid radius for part '{name}': {e}") from e
                shape_params["radius_mm"] = radius_mm
                corners_raw = shape_block.get("corners")
                if corners_raw is not None:
                    valid_corners = {"tl", "tr", "bl", "br"}
                    if not isinstance(corners_raw, list):
                        raise NestParseError(f"Invalid corners for part '{name}': expected a list")
                    for c in corners_raw:
                        if c not in valid_corners:
                            raise NestParseError(
                                f"Invalid corner '{c}' for part '{name}'. Must be one of: tl, tr, bl, br"
                            )
                    shape_params["corners"] = tuple(sorted(corners_raw))

            elif shape == "Circle":
                if abs(width - height) > 0.01:
                    raise NestParseError(
                        f"Circle shape for part '{name}' requires width == height, got {width}mm x {height}mm"
                    )

            elif shape == "Polygon":
                points_raw = shape_block.get("points")
                if points_raw is None:
                    raise NestParseError(f"Polygon shape for part '{name}' requires 'points'")
                if not isinstance(points_raw, list) or len(points_raw) < 3:
                    raise NestParseError(f"Polygon shape for part '{name}' requires at least 3 points")
                points = []
                for pt in points_raw:
                    if not isinstance(pt, list) or len(pt) != 2:
                        raise NestParseError(f"Invalid point {pt} for part '{name}': expected [x, y]")
                    try:
                        points.append([float(pt[0]), float(pt[1])])
                    except (ValueError, TypeError) as e:
                        raise NestParseError(f"Invalid point coordinate for part '{name}': {e}") from e
                half_w = width / 2
                half_h = height / 2
                for pt in points:
                    if abs(pt[0]) > half_w + 0.01 or abs(pt[1]) > half_h + 0.01:
                        raise NestParseError(
                            f"Polygon point [{pt[0]}, {pt[1]}] for part '{name}' exceeds "
                            f"bounding box ±{half_w}mm x ±{half_h}mm"
                        )
                shape_params["points"] = points

        part_holding: HoldingSpec | None = None
        part_holding_block = part_data.get("holding")
        if part_holding_block is not None:
            if not isinstance(part_holding_block, dict):
                raise NestParseError(f"Invalid holding for part '{name}': expected a mapping")
            part_holding = _parse_holding_block(part_holding_block, f"parts['{name}'].holding")
        resolved_holding = part_holding if part_holding is not None else job_holding

        parts.append(
            NestPart(
                name=name,
                width_mm=width,
                height_mm=height,
                quantity=quantity,
                template=template,
                template_params=template_params,
                shape=shape,
                shape_params=shape_params,
                holding=resolved_holding,
            )
        )

    return NestJob(
        algorithm=algorithm,
        sheet_width_mm=sheet_width,
        sheet_height_mm=sheet_height,
        sheet_thickness_mm=sheet_thickness,
        kerf_mm=kerf_mm,
        margin_mm=margin_mm,
        holding=job_holding,
        parts=parts,
    )


def substitute_params(text: str, params: dict[str, Any]) -> str:
    def replace_match(m: re.Match[str]) -> str:
        param_name = m.group(1)
        if param_name not in params:
            raise PMLParseError(f"Unknown parameter: ${{{param_name}}}")
        value = params[param_name]
        if isinstance(value, str):
            return value
        return f"{value}mm"

    return re.sub(r"\$\{(\w+)\}", replace_match, text)


def parse_template_yaml(source: str, parse_body: bool = False) -> TemplateDef:
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(source)
    except Exception as e:
        raise PMLParseError(f"Invalid YAML: {e}") from e

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


__all__ = [
    "NestParseError",
    "PMLParseError",
    "parse_dimension",
    "parse_nest_yaml",
    "parse_pml_yaml",
    "parse_template_yaml",
    "substitute_params",
]
