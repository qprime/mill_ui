from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import fields, is_dataclass, replace
from typing import Any, Literal

from ruamel.yaml import YAML

from core.constants import BACK_FACE_FEATURE_TYPES, GOLDEN_ANGLE_DEG, DepthMode
from layout_ast.compositional import (
    Arch,
    AtPosition,
    Cell,
    ChamferGen,
    Circle,
    ComponentDef,
    ComponentInstance,
    ComponentTemplate,
    CompositionalLayoutAST,
    ConcentricBorderGen,
    Edge,
    Ellipse,
    EngraveTextGen,
    FlutingGen,
    Frame,
    Grid,
    GridLinesGen,
    HarmonographCurveGen,
    HarmonographPendulum,
    HeightfieldGen,
    HeightfieldToolEntry,
    HoleGridGen,
    Inset,
    InterfaceConfig,
    Island,
    Keepout,
    Line,
    LinesGen,
    LissajousCurveGen,
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
    RoseCurveGen,
    RoundedRect,
    RoundoverGen,
    ShellGen,
    SpirographCurveGen,
    SpirographLayer,
    SplinePath,
    Split,
    SplitGrid,
    SplitHorizontal,
    SplitHorizontalGaps,
    SplitVertical,
    StringArtGen,
    Subtract,
    SuperformulaCurveGen,
    SurfaceDecl,
    SvgStampGen,
    TemplateDef,
    Triangle,
    UseComponent,
    VoronoiGen,
    WasteCuts,
    WaveGen,
    XPanelGen,
)
from layout_ast.layout import (
    DEFAULT_MIN_WEB_MM,
    VALID_FACES,
    DogboneSpec,
    Feature,
    FeedsOverride,
    MachiningSpec,
    RestSpec,
    Sheet,
)
from pml.measurement_fields import MEASUREMENT_KEYS, parse_measurement_fields
from pml.nest_parser import HoldingSpec, NestJob, NestParseError, NestPart

_DIMENSION_MATCH_TOLERANCE_MM = 1e-9

_VALID_SHAPE_TYPES = ("Rect", "RoundedRect", "Circle", "Polygon", "Triangle", "Ellipse")


_NODE_KEYS: dict[str, tuple[str, ...]] = {
    "Radial": ("depth", "element", "end_angle", "minor_subdivisions", "radius", "rays", "start_angle"),
    "Curve": (
        "a",
        "b",
        "cycles",
        "depth",
        "frequency_x",
        "frequency_y",
        "height",
        "layers",
        "lobes",
        "m",
        "max_cut_length",
        "min_length",
        "n1",
        "n2",
        "n3",
        "pendulums",
        "phase",
        "rotation",
        "size",
        "tolerance",
        "type",
        "width",
    ),
    "Phyllotaxis": ("angle", "count", "depth", "element", "min_size", "scale_with_radius", "spacing"),
    "Voronoi": (
        "cell_inset",
        "depth",
        "line_width",
        "margin",
        "min_length",
        "min_spacing",
        "mode",
        "points",
        "rest",
        "rest_tool",
        "seed",
        "seed_count",
    ),
    "StringArt": ("anchors", "depth", "factor", "min_length", "phase", "rule", "step"),
    "SvgStamp": ("center", "depth", "feature", "invert_y", "path", "scale", "svg_unit"),
    "Panel": ("children", "id"),
    "Rect": ("at", "children", "feature", "id", "label"),
    "Circle": ("at", "children", "diameter", "feature", "id", "label", "radius"),
    "RoundedRect": ("at", "children", "corners", "feature", "id", "label", "radius"),
    "Line": ("children", "feature", "id", "label", "orientation"),
    "Polyline": ("children", "feature", "id", "label", "points"),
    "Spline": ("children", "feature", "id", "label", "points", "tolerance"),
    "Island": ("children", "id"),
    "Keepout": ("children", "id"),
    "Edge": ("distance", "finish_allowance", "id", "radius", "rough_allowance", "treatment"),
    "Inset": ("children", "distance"),
    "Frame": ("children", "width"),
    "Grid": ("children", "cols", "gap", "rows"),
    "Cell": ("children", "inset"),
    "Split": ("children", "cols", "mullion", "rail", "rows"),
    "Profile": ("tool", "depth", "feeds", "onion_skin_mm", "side", "tab_count", "tab_height", "tab_width"),
    "Pocket": ("tool", "depth", "face", "feeds"),
    "RaisedPanel": ("tool", "feeds", "border_depth", "border_width", "field_depth", "profile", "v_angle"),
    "Chamfer": ("tool", "feeds", "depth", "width"),
    "Roundover": (
        "tool",
        "feeds",
        "radius",
    ),
    "Wave": ("amplitude", "count", "depth", "direction", "phase", "spacing", "wavelength"),
    "XPanel": ("bar_width", "depth"),
    "SplitHorizontal": ("children", "count", "gap"),
    "SplitVertical": ("children", "count", "gap"),
    "SplitGrid": ("children", "cols", "gap", "rows"),
    "SplitHorizontalGaps": ("children", "count", "gap"),
    "Lines": ("angle", "depth", "spacing", "width"),
    "Heightfield": ("depth", "image", "size", "tools", "white_is_high"),
    "Fluting": ("angle", "depth", "inset", "ramp", "spacing"),
    "ConcentricBorder": ("count", "depth", "groove", "insets", "join", "mode", "start", "step"),
    "Place": ("children", "layout"),
    "AtPosition": ("child", "height", "part_id", "width", "x", "y"),
    "Subtract": ("children", "inner_inset"),
    "Shell": ("children", "depth", "interior", "wall"),
    "Arch": ("children", "feature", "height", "id", "label", "radius", "width"),
    "Polygon": ("at", "children", "feature", "id", "label", "points"),
    "Triangle": ("base", "children", "feature", "height", "id", "label"),
    "Ellipse": ("at", "children", "feature", "id", "label", "rx", "ry"),
    "HoleGrid": ("align", "depth", "diameter", "inset", "pattern", "spacing"),
    "MeasurementGrid": (
        *MEASUREMENT_KEYS,
        "depth",
    ),
    "MeasurementEdge": (
        *MEASUREMENT_KEYS,
        "depth",
        "edges",
    ),
    "GridLines": ("depth", "minor_lines", "minor_spacing", "spacing", "unit"),
    "EngraveText": ("alignment", "depth", "font", "height", "orientation", "text"),
    "WasteCuts": ("margin", "min_height", "min_width", "strategy", "tab_count", "tab_height"),
    "Assembly": (
        "type",
        "width",
        "depth",
        "height",
        "dimensions",
        "thickness",
        "joinery",
        "finger_width",
        "finger_count",
        "clearance",
        "perimeter_joinery",
        "layout_gap",
        "show_labels",
        "show_edge_colors",
        "top",
        "bottom",
        "cap_style",
        "back",
        "back_thickness",
        "back_inset",
        "fixed_shelves",
        "shelf_joinery",
        "shelf_dado_depth",
        "shelf_back_support",
        "vertical_partitions",
        "toe_kick_height",
        "toe_kick_depth",
        "toe_kick_style",
        "toe_kick_cover",
        "grid",
        "back_joinery",
        "back_rabbet_depth",
        "back_internal_support",
        "partition_joinery",
        "partition_dado_depth",
        "internal_joinery",
    ),
    "UseComponent": ("args", "name"),
    "Engrave": (
        "tool",
        "feeds",
        "depth",
    ),
    "Beam": (
        "edge_features",
        "end_features",
        "face_features",
        "layers",
        "layout_gap",
        "length",
        "name",
        "role",
        "show_labels",
        "thickness",
        "width",
    ),
}

_ASSEMBLY_COMMON_KEYS = (
    "type",
    "width",
    "depth",
    "height",
    "dimensions",
    "thickness",
    "joinery",
    "finger_width",
    "finger_count",
    "clearance",
    "perimeter_joinery",
    "layout_gap",
    "show_labels",
    "show_edge_colors",
)
_ASSEMBLY_TYPE_KEYS: dict[str, tuple[str, ...]] = {
    "box": (*_ASSEMBLY_COMMON_KEYS, "top", "bottom"),
    "carcass": (
        *_ASSEMBLY_COMMON_KEYS,
        "top",
        "bottom",
        "cap_style",
        "back",
        "back_thickness",
        "back_inset",
        "fixed_shelves",
        "shelf_joinery",
        "shelf_dado_depth",
        "shelf_back_support",
        "vertical_partitions",
        "toe_kick_height",
        "toe_kick_depth",
        "toe_kick_style",
        "toe_kick_cover",
    ),
    "cubby": (
        *_ASSEMBLY_COMMON_KEYS,
        "grid",
        "back",
        "back_thickness",
        "back_inset",
        "back_joinery",
        "back_rabbet_depth",
        "back_internal_support",
        "shelf_joinery",
        "shelf_dado_depth",
        "partition_joinery",
        "partition_dado_depth",
        "internal_joinery",
    ),
}

_AT_KEYS: dict[str, tuple[str, ...]] = {
    "Rect": ("x", "y", "width", "height"),
    "RoundedRect": ("x", "y", "width", "height"),
    "Ellipse": ("x", "y", "width", "height"),
    "Circle": ("x", "y"),
    "Polygon": ("x", "y"),
}

_FEATURE_KEYS: dict[str, tuple[str, ...]] = {
    "profile": (
        "tool",
        "type",
        "depth",
        "face",
        "side",
        "tab_count",
        "tab_height",
        "tab_width",
        "onion_skin_mm",
        "feeds",
    ),
    "pocket": ("tool", "type", "depth", "face", "corner_cleanup", "dogbone", "rest", "rest_tool", "feeds"),
    "hole": ("tool", "type", "depth", "face", "feeds"),
    "engrave": ("tool", "type", "depth", "face", "feeds"),
}

_DOGBONE_KEYS = ("style", "diameter", "overcut")
_INTERFACE_KEYS = (
    "joinery",
    "finger_width",
    "finger_count",
    "clearance",
    "dado_depth",
    "inset",
    "receiving",
    "dogbone",
)
_BEAM_FEATURE_KEYS = {
    "DrillHole": ("x", "y", "diameter", "depth", "face", "stage"),
    "SquareMortise": ("x", "y", "width", "height", "depth", "face", "stage"),
    "Tenon": ("end", "extension", "width", "height", "layers"),
    "Rabbet": ("edge", "width", "depth", "start", "end", "layers", "stage"),
    "EdgeDado": ("edge", "position", "width", "depth", "layers", "stage"),
    "EdgeNotch": ("edge", "position", "width", "depth", "layers", "stage"),
}

_RADIAL_ELEMENT_KEYS = {
    "pocket": ("tool", "type", "bar_width", "shape", "center_shape", "center_size"),
    "tick": ("type", "tick_length", "minor_tick_length", "inward", "labels", "label_list", "label_height"),
    "label": ("type", "values", "height"),
    "svg": ("type", "path", "feature", "scale", "svg_unit", "rotate", "size"),
}

_PHYLLOTAXIS_ELEMENT_KEYS = {
    "hole": ("tool", "type", "diameter"),
    "pocket": ("tool", "type", "diameter"),
    "svg": ("type", "path", "size", "feature", "rotate"),
}

_SHEET_KEYS = (
    "width",
    "height",
    "physical_width",
    "physical_height",
    "working_width",
    "working_height",
    "thickness",
    "margin",
    "min_web",
    "safe_z",
    "show_dimensions",
    "material",
    "gcode_output",
)


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


def _reject_unknown_keys(
    data: dict[str, Any],
    known: Sequence[str],
    label: str,
    ctx: str,
    *,
    hint: str = "",
    error_type: type[Exception] = PMLParseError,
) -> None:
    if not isinstance(data, dict):
        raise error_type(f"Expected {label} mapping, got {type(data).__name__} (PM-18 violation)", ctx)
    unknown = [str(key) for key in data if key not in known]
    if unknown:
        message = f"Unknown {label} key(s): {', '.join(unknown)}. Allowed keys: {', '.join(known)}."
        if hint:
            message += f" {hint}"
        raise error_type(f"{message} (PM-18 violation)", ctx)


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


def _parse_concentric_border_node(node_data: dict, path: str) -> ConcentricBorderGen:
    ctx = f"{path}.ConcentricBorder"
    has_insets = "insets" in node_data
    has_count = "count" in node_data
    has_step = "step" in node_data
    if has_insets and (has_count or has_step):
        raise PMLParseError("ConcentricBorder takes either 'insets' or 'count' + 'step', not both", ctx)
    if not has_insets and not (has_count and has_step):
        raise PMLParseError("ConcentricBorder requires either 'insets' or both 'count' and 'step'", ctx)
    if "start" in node_data and not has_count:
        raise PMLParseError("ConcentricBorder 'start' is only valid with 'count' and 'step'", ctx)

    mode = node_data.get("mode", "pocket")
    if mode == "engrave" and "groove" in node_data:
        raise PMLParseError("ConcentricBorder 'groove' is not valid with 'mode: engrave'", ctx)
    groove_width_mm = parse_dimension(node_data["groove"]) if "groove" in node_data else None
    if mode == "pocket" and groove_width_mm is None:
        raise PMLParseError("ConcentricBorder 'mode: pocket' requires 'groove'", ctx)

    insets_mm = None
    count = step_mm = start_mm = None
    if has_insets:
        insets_mm = tuple(parse_dimension(i) for i in node_data["insets"])
    else:
        count = _safe_int(node_data["count"], "count", ctx)
        step_mm = parse_dimension(node_data["step"])
        start_mm = parse_dimension(node_data["start"]) if "start" in node_data else None
        if count < 1:
            raise PMLParseError(f"ConcentricBorder 'count' must be at least 1, got {count}", ctx)
        if step_mm <= 0:
            raise PMLParseError(f"ConcentricBorder 'step' must be positive, got {step_mm}mm", ctx)
        if start_mm is not None and start_mm <= 0:
            raise PMLParseError(f"ConcentricBorder 'start' must be positive, got {start_mm}mm", ctx)
        if groove_width_mm is not None and step_mm < groove_width_mm:
            raise PMLParseError(
                f"ConcentricBorder 'step' ({step_mm}mm) is less than 'groove' ({groove_width_mm}mm); the rings would overlap",
                ctx,
            )

    return ConcentricBorderGen(
        depth_mm=parse_dimension(_require(node_data, "depth", ctx)),
        insets_mm=insets_mm,
        count=count,
        step_mm=step_mm,
        start_mm=start_mm,
        groove_width_mm=groove_width_mm,
        join=node_data.get("join", "mitre"),
        mode=mode,
    )


def _parse_heightfield_tool_entry(entry: Any, path: str) -> HeightfieldToolEntry:
    import math

    if not isinstance(entry, dict):
        raise PMLParseError(f"Heightfield tool entry must be a mapping, got {type(entry).__name__}", path)
    _reject_unknown_keys(entry, ("tool", "role", "stepover", "stepdown", "angle"), "Heightfield tool", path)
    if "tool" not in entry:
        raise PMLParseError("Heightfield tool entry requires 'tool' (endmill name)", path)
    role = str(entry.get("role", "rough")).lower()
    if role not in ("rough", "finish"):
        raise PMLParseError(f"Heightfield tool role must be 'rough' or 'finish', got {role!r}", path)
    if role == "finish" and "stepover" not in entry:
        raise PMLParseError(
            "Heightfield finish entry requires explicit 'stepover' (no role-appropriate default)",
            path,
        )
    stepover_raw = entry.get("stepover", "60%")
    if isinstance(stepover_raw, str) and stepover_raw.strip().endswith("%"):
        stepover_frac = float(stepover_raw.strip().rstrip("%")) / 100.0
    else:
        stepover_frac = float(stepover_raw)
    stepdown_raw = entry.get("stepdown")
    stepdown_mm = parse_dimension(stepdown_raw) if stepdown_raw is not None else None
    angle_raw = entry.get("angle")
    angle_deg: float | None = None

    if role == "finish":
        if stepdown_mm is not None:
            raise PMLParseError("Heightfield finish entry must not specify 'stepdown' (finish is single-pass)", path)
        raw_angle = 0.0 if angle_raw is None else float(angle_raw)
        if not math.isfinite(raw_angle):
            raise PMLParseError(f"Heightfield finish 'angle' must be finite, got {raw_angle}", path)
        angle_deg = raw_angle % 180.0
    else:
        if angle_raw is not None:
            raise PMLParseError("Heightfield 'angle' only valid on finish entries", path)

    return HeightfieldToolEntry(
        tool=str(entry["tool"]),
        role=role,
        stepover_frac=stepover_frac,
        stepdown_mm=stepdown_mm,
        angle_deg=angle_deg,
    )


def _parse_interface_config(
    data: dict, default_joinery: str = "butt", *, path: str = "", back: bool = False
) -> InterfaceConfig:
    known = (*_INTERFACE_KEYS, "thickness") if back else _INTERFACE_KEYS
    _reject_unknown_keys(data, known, "interface config", path)
    dogbone_raw = data.get("dogbone")
    dogbone: DogboneSpec | bool | None = None
    if dogbone_raw is False:
        dogbone = False
    elif dogbone_raw is True:
        dogbone = True
    elif isinstance(dogbone_raw, dict):
        _reject_unknown_keys(dogbone_raw, _DOGBONE_KEYS, "dogbone", f"{path}.dogbone")
        dogbone = DogboneSpec(
            style=dogbone_raw.get("style", "dogbone"),
            diameter_mm=parse_dimension(dogbone_raw["diameter"]) if "diameter" in dogbone_raw else None,
            overcut_mm=parse_dimension(dogbone_raw["overcut"]) if "overcut" in dogbone_raw else 0.0,
        )
    elif "dogbone" in data:
        raise PMLParseError(
            f"dogbone must be true, false or a mapping, got {dogbone_raw!r} (PM-18 violation)", f"{path}.dogbone"
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
    if children_data is None:
        return ()
    if not isinstance(children_data, list):
        raise PMLParseError("children must be a list (PM-18 violation)", path)
    return tuple(parse_node(child, f"{path}.children[{i}]") for i, child in enumerate(children_data))


def _parse_tool_name(value: Any, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PMLParseError("tool must be a nonempty library name", path)
    return value


def _parse_machining(data: Any, path: str = "machining") -> MachiningSpec:
    if data is None:
        return MachiningSpec()
    _reject_unknown_keys(data, ("tools", "feeds"), "machining", path)
    tools = data.get("tools", {})
    if not isinstance(tools, dict):
        raise PMLParseError("machining.tools must be a mapping of roles to exact tool names", path)
    try:
        return MachiningSpec(tools=dict(tools), feeds=_parse_feeds_override(data.get("feeds"), path + ".feeds"))
    except ValueError as exc:
        raise PMLParseError(str(exc), path) from exc


def _parse_feeds_override(data: dict | None, path: str = "") -> FeedsOverride | None:
    if data is None:
        return None
    _reject_unknown_keys(data, ("rpm", "feed_xy", "feed_z", "depth_per_pass", "stepover_percent"), "feeds", path)
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


def _parse_face(raw: Any, path: str) -> str:
    if raw is None:
        return "front"
    face = str(raw)
    if face not in VALID_FACES:
        raise PMLParseError(f"Invalid face '{face}'. Must be one of: {VALID_FACES}", path)
    return face


def _parse_rest(data: dict, path: str) -> RestSpec | None:
    rest_raw = data.get("rest")
    rest_tool_raw = data.get("rest_tool")
    if rest_raw is not None and rest_tool_raw is not None:
        raise PMLParseError("Cannot specify both 'rest' and 'rest_tool'", path)
    if rest_raw is not None and not isinstance(rest_raw, dict):
        raise PMLParseError(
            f"'rest' must be a mapping such as 'rest: {{tool: 3.175mm}}', got {rest_raw!r}; "
            "use 'rest_tool' for the diameter-only form",
            path,
        )
    if isinstance(rest_raw, dict):
        _reject_unknown_keys(rest_raw, ("tool", "rough_allowance", "finish_allowance"), "rest", path + ".rest")
        return RestSpec(
            tool_diameter_mm=parse_dimension(_require(rest_raw, "tool", path + ".rest")),
            rough_allowance_mm=parse_dimension(rest_raw["rough_allowance"]) if "rough_allowance" in rest_raw else 0.5,
            finish_allowance_mm=parse_dimension(rest_raw["finish_allowance"])
            if "finish_allowance" in rest_raw
            else 0.0,
        )
    if rest_tool_raw is not None:
        return RestSpec(tool_diameter_mm=parse_dimension(rest_tool_raw))
    return None


def parse_feature(data: dict, path: str = "", sheet_thickness_mm: float = 0.0) -> Feature:
    if not isinstance(data, dict):
        raise PMLParseError("Feature must be a mapping (PM-18 violation)", path)
    feature_type = data.get("type")
    if feature_type is None:
        raise PMLParseError("Feature missing 'type'", path)

    if feature_type not in _FEATURE_KEYS:
        raise PMLParseError(
            f"Unknown feature type: {feature_type!r}. Valid types: {', '.join(_FEATURE_KEYS)} (PM-18 violation)", path
        )
    _reject_unknown_keys(data, _FEATURE_KEYS[feature_type], "feature", path)
    depth = data.get("depth", "through")
    is_through = DepthMode.is_through(depth)

    depth_mm = sheet_thickness_mm if is_through else float(parse_dimension(depth))

    face = _parse_face(data.get("face"), path)
    if face == "back":
        if feature_type not in BACK_FACE_FEATURE_TYPES:
            raise PMLParseError(
                f"face: back is only valid on {BACK_FACE_FEATURE_TYPES} features, got '{feature_type}'",
                path,
            )
        if is_through:
            raise PMLParseError(
                "face: back cannot be combined with depth: through — back features must "
                "specify a finite depth (through cuts belong to the front setup)",
                path,
            )

    dogbone: DogboneSpec | None = None
    dogbone_raw = data.get("dogbone")
    if dogbone_raw is True:
        dogbone = DogboneSpec()
    elif isinstance(dogbone_raw, dict):
        _reject_unknown_keys(dogbone_raw, _DOGBONE_KEYS, "dogbone", f"{path}.dogbone")
        dogbone = DogboneSpec(
            style=dogbone_raw.get("style", "dogbone"),
            diameter_mm=parse_dimension(dogbone_raw["diameter"]) if "diameter" in dogbone_raw else None,
            overcut_mm=parse_dimension(dogbone_raw["overcut"]) if "overcut" in dogbone_raw else 0.0,
        )
    elif "dogbone" in data and dogbone_raw is not False:
        raise PMLParseError(
            f"dogbone must be true, false or a mapping, got {dogbone_raw!r} (PM-18 violation)", f"{path}.dogbone"
        )

    return Feature(
        type=feature_type,
        depth_mm=depth_mm,
        side=data.get("side"),
        face=face,
        is_through=is_through,
        corner_cleanup_tool_diameter_mm=parse_dimension(data["corner_cleanup"]) if "corner_cleanup" in data else None,
        dogbone=dogbone,
        rest=_parse_rest(data, path),
        tab_count=data.get("tab_count"),
        tab_height_mm=parse_dimension(data["tab_height"]) if "tab_height" in data else None,
        tab_width_mm=parse_dimension(data["tab_width"]) if "tab_width" in data else None,
        onion_skin_mm=parse_dimension(data["onion_skin_mm"]) if "onion_skin_mm" in data else None,
        feeds_override=_parse_feeds_override(data.get("feeds"), f"{path}.feeds"),
        tool_name=_parse_tool_name(data.get("tool"), path),
    )


def _parse_joinery_field(
    raw: Any, default_joinery: str = "butt", *, path: str = "", back: bool = False
) -> str | InterfaceConfig | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return _parse_interface_config(raw, default_joinery=default_joinery, path=path, back=back)
    raise PMLParseError("Joinery must be a string or mapping (PM-18 violation)", path)


def _parse_assembly_dimensions(node_data: dict, ctx: str) -> tuple[float, float, float]:
    dims = node_data.get("dimensions")
    if "dimensions" in node_data:
        if not isinstance(dims, list) or not 1 <= len(dims) <= 3:
            raise PMLParseError("Assembly dimensions must be a list of one to three dimensions (PM-18 violation)", ctx)
        for index, value in enumerate(dims):
            try:
                parse_dimension(value)
            except (ValueError, TypeError) as exc:
                raise PMLParseError(f"Invalid dimensions[{index}]: {value!r} (PM-18 violation)", ctx) from exc

    resolved = []
    for index, key in enumerate(("width", "depth", "height")):
        value = node_data.get(key)
        if value is None:
            value = dims[index] if dims and index < len(dims) else _require(node_data, key, ctx)
        resolved.append(parse_dimension(value))
    return resolved[0], resolved[1], resolved[2]


def _validate_back_dimensions(node_data: dict, back_raw: Any, ctx: str) -> None:
    if isinstance(back_raw, dict):
        for key in ("thickness", "inset"):
            flat_key = f"back_{key}"
            if flat_key not in node_data or key not in back_raw:
                continue
            flat_value = parse_dimension(node_data[flat_key])
            nested_value = parse_dimension(back_raw[key])
            if key == "inset" and nested_value == 0.0:
                continue
            if not math.isclose(flat_value, nested_value, rel_tol=0.0, abs_tol=_DIMENSION_MATCH_TOLERANCE_MM):
                raise PMLParseError(
                    f"Conflicting {flat_key} ({flat_value}mm) and back.{key} ({nested_value}mm); expected matching dimensions (PM-18 violation)",
                    ctx,
                )


def _parse_assembly_node(node_data: dict, path: str) -> Any:
    from layout_ast.compositional import AssemblyDecl

    assembly_type = node_data.get("type", "box")
    ctx = f"{path}.Assembly"
    if assembly_type not in _ASSEMBLY_TYPE_KEYS:
        raise PMLParseError(
            f"Unknown Assembly type: {assembly_type!r}. Allowed types: {', '.join(_ASSEMBLY_TYPE_KEYS)} (PM-18 violation)",
            ctx,
        )
    _reject_unknown_keys(node_data, _ASSEMBLY_TYPE_KEYS[assembly_type], f"Assembly {assembly_type}", ctx)
    for key in ("top", "bottom", "back", "shelf_joinery", "partition_joinery"):
        if key in node_data and not isinstance(node_data[key], (str, dict)):
            raise PMLParseError("Joinery must be a string or mapping (PM-18 violation)", f"{path}.Assembly.{key}")

    top = _parse_joinery_field(node_data.get("top"), path=f"{path}.Assembly.top")
    bottom = _parse_joinery_field(
        node_data.get("bottom", "captured"), default_joinery="captured", path=f"{path}.Assembly.bottom"
    )
    back_raw = node_data.get("back")
    back = _parse_joinery_field(back_raw, default_joinery="captured", path=f"{path}.Assembly.back", back=True)

    grid_raw = node_data.get("grid")
    grid = None
    if "grid" in node_data:
        if not isinstance(grid_raw, list) or len(grid_raw) != 2:
            raise PMLParseError("grid must be a 2-element list (PM-18 violation)", f"{path}.Assembly.grid")
        try:
            grid = (int(grid_raw[0]), int(grid_raw[1]))
        except (ValueError, TypeError) as e:
            raise PMLParseError(f"Invalid grid values: {e}", path) from e

    shelf_joinery: str | InterfaceConfig = (
        _parse_joinery_field(
            node_data.get("shelf_joinery", "captured"),
            default_joinery="captured",
            path=f"{path}.Assembly.shelf_joinery",
        )
        or "captured"
    )
    partition_joinery: str | InterfaceConfig = (
        _parse_joinery_field(
            node_data.get("partition_joinery", "captured"),
            default_joinery="captured",
            path=f"{path}.Assembly.partition_joinery",
        )
        or "captured"
    )

    width_mm, depth_mm, height_mm = _parse_assembly_dimensions(node_data, ctx)
    _validate_back_dimensions(node_data, back_raw, ctx)

    return AssemblyDecl(
        type=assembly_type,
        width_mm=width_mm,
        depth_mm=depth_mm,
        height_mm=height_mm,
        thickness_mm=parse_dimension(_require(node_data, "thickness", f"{path}.Assembly")),
        joinery=node_data.get("joinery", "finger"),
        finger_width_mm=parse_dimension(node_data["finger_width"]) if "finger_width" in node_data else None,
        finger_count=node_data.get("finger_count"),
        clearance_mm=parse_dimension(node_data.get("clearance", "0.12mm")),
        top=top,
        bottom=bottom,
        layout_gap_mm=_parse_layout_gap(node_data.get("layout_gap", "10mm")),
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


_UNBACKED_BEAM_FEATURES = {
    "CarvedDesign": "no design-template registry exists",
    "GeometricPattern": "no pattern generator exists",
    "EndCap": "no end-cap profile registry exists",
    "EndProfile": "requires a polygon layer outline",
    "EdgeContour": "requires a polygon layer outline",
    "Fillet": "requires per-edge ranged edge treatment",
    "Chamfer": "requires per-edge ranged edge treatment",
}


def _parse_beam_feature(feat_data: dict, feat_path: str):
    from layout_ast.compositional import BeamFeatureDecl

    feat_keys = [k for k in feat_data if k[0].isupper()]
    if len(feat_keys) != 1:
        raise PMLParseError(f"Invalid beam feature: {feat_data}", feat_path)
    feat_type = feat_keys[0]
    _reject_unknown_keys(feat_data, (feat_type,), "beam feature wrapper", feat_path)
    if feat_type in _UNBACKED_BEAM_FEATURES:
        raise PMLParseError(
            f"Beam feature '{feat_type}' is not supported: {_UNBACKED_BEAM_FEATURES[feat_type]}",
            feat_path,
        )
    feat_params = feat_data[feat_type] or {}
    if feat_type not in _BEAM_FEATURE_KEYS:
        raise PMLParseError(f"Unknown beam feature type: {feat_type!r} (PM-18 violation)", feat_path)
    _reject_unknown_keys(feat_params, _BEAM_FEATURE_KEYS[feat_type], feat_type, feat_path)
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
            _reject_unknown_keys(layer_data, ("length", "offset", "cutouts"), "Beam layer", f"{path}.Beam.layer")
            cutouts: tuple[()] | tuple[dict, ...] = ()
            if "cutouts" in layer_data:
                for cutout in layer_data["cutouts"]:
                    _reject_unknown_keys(
                        cutout, ("start", "length", "width", "offset"), "Beam cutout", f"{path}.Beam.layer.cutout"
                    )
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
        raise PMLParseError("Beam layers must be an integer or list (PM-18 violation)", f"{path}.Beam.layers")

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
        layout_gap_mm=_parse_layout_gap(node_data.get("layout_gap", "10mm")),
        show_labels=node_data.get("show_labels", False),
    )


def _parse_layout_gap(value: Any) -> float | Literal["auto"]:
    if value == "auto":
        return "auto"
    gap = parse_dimension(value)
    if not math.isfinite(gap) or gap < 0:
        raise PMLParseError(f"layout_gap must be auto or a finite nonnegative dimension, got {value!r}")
    return gap


def _parse_radial_node(node_data: dict, path: str) -> Any:
    from layout_ast.compositional import RadialLabelGen, RadialPocketGen, RadialTickGen

    element = node_data.get("element", {})
    element_type = element.get("type", "pocket")
    ctx = f"{path}.Radial"
    if element_type not in _RADIAL_ELEMENT_KEYS:
        raise PMLParseError(f"Unknown Radial element type: {element_type!r}", ctx)
    _reject_unknown_keys(element, _RADIAL_ELEMENT_KEYS[element_type], "Radial element", f"{ctx}.element")
    if "minor_subdivisions" in node_data and element_type != "tick":
        raise PMLParseError("Radial minor_subdivisions is only valid with element.type: tick (PM-18 violation)", ctx)

    rays = _safe_int(_require(node_data, "rays", ctx), "rays", ctx)
    depth_mm = parse_dimension(_require(node_data, "depth", ctx))
    start_angle_deg = _safe_float(node_data.get("start_angle", 0), "start_angle", ctx)
    end_angle_deg = _safe_float(node_data.get("end_angle", 360), "end_angle", ctx)
    radius_mm = parse_dimension(node_data["radius"]) if "radius" in node_data else None

    if element_type == "pocket":
        return RadialPocketGen(
            tool_name=_parse_tool_name(element.get("tool"), f"{ctx}.element"),
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


_PHYLLOTAXIS_ELEMENT_TYPES = ("hole", "pocket", "svg")


def _parse_phyllotaxis_node(node_data: dict, path: str) -> Any:
    from layout_ast.compositional import PhyllotaxisHoleGen, PhyllotaxisPocketGen, PhyllotaxisSvgGen

    ctx = f"{path}.Phyllotaxis"

    element = _require(node_data, "element", ctx)
    element_ctx = f"{ctx}.element"
    element_type = _require(element, "type", element_ctx)
    if element_type not in _PHYLLOTAXIS_ELEMENT_TYPES:
        raise PMLParseError(
            f"Unknown Phyllotaxis element type: '{element_type}'. Known types: {', '.join(_PHYLLOTAXIS_ELEMENT_TYPES)}",
            ctx,
        )
    hint = ""
    if element_type == "svg" and any(key in element for key in ("scale", "svg_unit")):
        hint = "Phyllotaxis svg elements are always fitted to 'size'; omit 'scale' and 'svg_unit'"
    _reject_unknown_keys(
        element, _PHYLLOTAXIS_ELEMENT_KEYS[element_type], "Phyllotaxis element", element_ctx, hint=hint
    )

    count = _safe_int(_require(node_data, "count", ctx), "count", ctx)
    spacing_mm = parse_dimension(_require(node_data, "spacing", ctx))
    angle_deg = _safe_float(node_data.get("angle", GOLDEN_ANGLE_DEG), "angle", ctx)
    scale_with_radius = node_data.get("scale_with_radius", False)
    min_size_mm = parse_dimension(node_data["min_size"]) if "min_size" in node_data else None

    if element_type == "hole":
        for key in ("scale_with_radius", "min_size"):
            if key in node_data:
                raise PMLParseError(f"Phyllotaxis '{key}' is not supported for hole elements", ctx)
        return PhyllotaxisHoleGen(
            tool_name=_parse_tool_name(element.get("tool"), f"{ctx}.element"),
            count=count,
            spacing_mm=spacing_mm,
            diameter_mm=parse_dimension(_require(element, "diameter", element_ctx)),
            depth_mm=parse_dimension_or_through(node_data.get("depth", "through")),
            angle_deg=angle_deg,
        )

    if scale_with_radius and min_size_mm is None:
        raise PMLParseError("Phyllotaxis 'scale_with_radius' requires 'min_size'", ctx)
    if min_size_mm is not None and not scale_with_radius:
        raise PMLParseError("Phyllotaxis 'min_size' requires 'scale_with_radius: true'", ctx)
    depth_mm = parse_dimension(_require(node_data, "depth", ctx))

    if element_type == "pocket":
        return PhyllotaxisPocketGen(
            tool_name=_parse_tool_name(element.get("tool"), f"{ctx}.element"),
            count=count,
            spacing_mm=spacing_mm,
            diameter_mm=parse_dimension(_require(element, "diameter", element_ctx)),
            depth_mm=depth_mm,
            angle_deg=angle_deg,
            scale_with_radius=scale_with_radius,
            min_size_mm=min_size_mm,
        )

    return PhyllotaxisSvgGen(
        count=count,
        spacing_mm=spacing_mm,
        svg_path=_require(element, "path", element_ctx),
        size_mm=parse_dimension(_require(element, "size", element_ctx)),
        depth_mm=depth_mm,
        angle_deg=angle_deg,
        scale_with_radius=scale_with_radius,
        min_size_mm=min_size_mm,
        feature_type=element.get("feature", "engrave"),
        rotate_element=element.get("rotate", True),
    )


_CURVE_SHARED_KEYS = ("type", "depth", "size", "rotation", "tolerance", "min_length")
_CURVE_TYPE_KEYS: dict[str, tuple[str, ...]] = {
    "rose": ("lobes",),
    "spirograph": ("layers", "max_cut_length"),
    "lissajous": ("frequency_x", "frequency_y", "phase", "width", "height"),
    "superformula": ("m", "n1", "n2", "n3", "a", "b"),
    "harmonograph": ("cycles", "pendulums"),
}
_CURVE_TYPES = tuple(_CURVE_TYPE_KEYS)
_HARMONOGRAPH_AXES = ("x", "y")
_HARMONOGRAPH_PENDULUM_KEYS = ("axis", "amplitude", "frequency", "phase", "damping")


def _parse_harmonograph_pendulums(raw: Any, ctx: str) -> tuple[HarmonographPendulum, ...]:
    if not isinstance(raw, list):
        raise PMLParseError(f"Curve harmonograph 'pendulums' must be a list, got {type(raw).__name__}", ctx)
    pendulums: list[HarmonographPendulum] = []
    for index, entry in enumerate(raw):
        entry_ctx = f"{ctx}.pendulums[{index}]"
        if not isinstance(entry, dict):
            raise PMLParseError(f"Curve harmonograph pendulum must be a mapping, got {type(entry).__name__}", entry_ctx)
        _reject_unknown_keys(entry, _HARMONOGRAPH_PENDULUM_KEYS, "harmonograph pendulum", entry_ctx)
        axis = _require(entry, "axis", entry_ctx)
        if axis not in _HARMONOGRAPH_AXES:
            raise PMLParseError(f"Curve harmonograph pendulum 'axis' must be x or y, got {axis!r}", entry_ctx)
        pendulums.append(
            HarmonographPendulum(
                axis=axis,
                amplitude_mm=parse_dimension(_require(entry, "amplitude", entry_ctx)),
                frequency=_safe_float(_require(entry, "frequency", entry_ctx), "frequency", entry_ctx),
                phase_deg=_safe_float(entry.get("phase", 0.0), "phase", entry_ctx),
                damping=_safe_float(entry.get("damping", 0.0), "damping", entry_ctx),
            )
        )
    missing = [axis for axis in _HARMONOGRAPH_AXES if all(p.axis != axis for p in pendulums)]
    if missing:
        raise PMLParseError(
            f"Curve harmonograph 'pendulums' needs at least one pendulum on each axis; none on {', '.join(missing)}",
            ctx,
        )
    return tuple(pendulums)


_SPIROGRAPH_LAYER_KEYS = ("points", "step", "pen", "mode", "rotation", "rotation_step", "depth")
_SPIROGRAPH_PEN_SWEEP_KEYS = ("from", "to", "count")


def _parse_spirograph_pen(raw: Any, ctx: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        _reject_unknown_keys(raw, _SPIROGRAPH_PEN_SWEEP_KEYS, "spirograph pen sweep", ctx)
        return {
            "pen_from": _safe_float(_require(raw, "from", ctx), "pen from", ctx),
            "pen_to": _safe_float(_require(raw, "to", ctx), "pen to", ctx),
            "pen_count": _safe_int(_require(raw, "count", ctx), "pen count", ctx),
        }
    if isinstance(raw, list):
        return {"pens": tuple(_safe_float(value, "pen", ctx) for value in raw)}
    return {"pens": (_safe_float(raw, "pen", ctx),)}


def _parse_spirograph_layers(raw: Any, ctx: str) -> tuple[SpirographLayer, ...]:
    if not isinstance(raw, list) or not raw:
        raise PMLParseError("Curve spirograph 'layers' must be a non-empty list", ctx)
    layers: list[SpirographLayer] = []
    for index, entry in enumerate(raw):
        entry_ctx = f"{ctx}.layers[{index}]"
        if not isinstance(entry, dict):
            raise PMLParseError(f"Curve spirograph layer must be a mapping, got {type(entry).__name__}", entry_ctx)
        _reject_unknown_keys(entry, _SPIROGRAPH_LAYER_KEYS, "spirograph layer", entry_ctx)
        layers.append(
            SpirographLayer(
                points=_safe_int(_require(entry, "points", entry_ctx), "points", entry_ctx),
                step=_safe_int(_require(entry, "step", entry_ctx), "step", entry_ctx),
                **_parse_spirograph_pen(_require(entry, "pen", entry_ctx), entry_ctx),
                mode=entry.get("mode", "inside"),
                rotation_deg=_safe_float(entry.get("rotation", 0.0), "rotation", entry_ctx),
                rotation_step_deg=_safe_float(entry.get("rotation_step", 0.0), "rotation_step", entry_ctx),
                depth_mm=parse_dimension(entry["depth"]) if "depth" in entry else None,
            )
        )
    return tuple(layers)


def _parse_curve_node(node_data: dict, path: str) -> Any:
    ctx = f"{path}.Curve"

    curve_type = _require(node_data, "type", ctx)
    if curve_type not in _CURVE_TYPES:
        raise PMLParseError(f"Unknown Curve type: '{curve_type}'. Known types: {', '.join(_CURVE_TYPES)}", ctx)
    _reject_unknown_keys(node_data, _CURVE_SHARED_KEYS + _CURVE_TYPE_KEYS[curve_type], curve_type, ctx)
    depth_mm = parse_dimension(_require(node_data, "depth", ctx))
    size_mm = parse_dimension(node_data["size"]) if "size" in node_data else None
    rotation_deg = _safe_float(node_data.get("rotation", 0.0), "rotation", ctx)
    tolerance_mm = parse_dimension(node_data.get("tolerance", "0.05mm"))
    min_length_mm = parse_dimension(node_data.get("min_length", "0mm"))

    if curve_type == "rose":
        return RoseCurveGen(
            lobes=_safe_int(_require(node_data, "lobes", ctx), "lobes", ctx),
            depth_mm=depth_mm,
            size_mm=size_mm,
            rotation_deg=rotation_deg,
            tolerance_mm=tolerance_mm,
            min_length_mm=min_length_mm,
        )

    if curve_type == "spirograph":
        return SpirographCurveGen(
            layers=_parse_spirograph_layers(_require(node_data, "layers", ctx), ctx),
            depth_mm=depth_mm,
            size_mm=size_mm,
            rotation_deg=rotation_deg,
            tolerance_mm=tolerance_mm,
            min_length_mm=min_length_mm,
            max_cut_length_mm=parse_dimension(node_data.get("max_cut_length", "50000mm")),
        )

    if curve_type == "lissajous":
        return LissajousCurveGen(
            frequency_x=_safe_int(_require(node_data, "frequency_x", ctx), "frequency_x", ctx),
            frequency_y=_safe_int(_require(node_data, "frequency_y", ctx), "frequency_y", ctx),
            depth_mm=depth_mm,
            phase_deg=_safe_float(node_data.get("phase", 90.0), "phase", ctx),
            width_mm=parse_dimension(node_data["width"]) if "width" in node_data else None,
            height_mm=parse_dimension(node_data["height"]) if "height" in node_data else None,
            size_mm=size_mm,
            rotation_deg=rotation_deg,
            tolerance_mm=tolerance_mm,
            min_length_mm=min_length_mm,
        )

    if curve_type == "superformula":
        m = _safe_float(_require(node_data, "m", ctx), "m", ctx)
        if not m.is_integer():
            raise PMLParseError(f"Curve superformula 'm' must be a whole number, got {m}", ctx)
        return SuperformulaCurveGen(
            m=int(m),
            n1=_safe_float(_require(node_data, "n1", ctx), "n1", ctx),
            n2=_safe_float(_require(node_data, "n2", ctx), "n2", ctx),
            n3=_safe_float(_require(node_data, "n3", ctx), "n3", ctx),
            depth_mm=depth_mm,
            a=_safe_float(node_data.get("a", 1.0), "a", ctx),
            b=_safe_float(node_data.get("b", 1.0), "b", ctx),
            size_mm=size_mm,
            rotation_deg=rotation_deg,
            tolerance_mm=tolerance_mm,
            min_length_mm=min_length_mm,
        )

    if curve_type == "harmonograph":
        return HarmonographCurveGen(
            cycles=_safe_float(_require(node_data, "cycles", ctx), "cycles", ctx),
            pendulums=_parse_harmonograph_pendulums(_require(node_data, "pendulums", ctx), ctx),
            depth_mm=depth_mm,
            size_mm=size_mm,
            rotation_deg=rotation_deg,
            tolerance_mm=tolerance_mm,
            min_length_mm=min_length_mm,
        )

    raise TypeError(f"Unhandled Curve type: {curve_type!r}")


_VORONOI_MODES = ("engrave", "pocket")


def _parse_voronoi_points(raw: Any, ctx: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw, list):
        raise PMLParseError("Voronoi 'points' must be a list of [x, y] pairs", ctx)
    points: list[tuple[float, float]] = []
    for index, point in enumerate(raw):
        if not isinstance(point, list) or len(point) != 2:
            raise PMLParseError(f"Voronoi point {index} must be an [x, y] pair, got {point!r}", ctx)
        points.append((parse_dimension(point[0]), parse_dimension(point[1])))
    if len(set(points)) < 2:
        raise PMLParseError("Voronoi 'points' must include at least 2 distinct locations", ctx)
    return tuple(points)


def _check_voronoi_keys(node_data: dict, ctx: str) -> Literal["engrave", "pocket"]:
    if ("seed_count" in node_data) == ("points" in node_data):
        raise PMLParseError("Voronoi takes exactly one of 'seed_count' or 'points'", ctx)
    if "points" in node_data:
        for key in ("seed", "min_spacing", "margin"):
            if key in node_data:
                raise PMLParseError(
                    f"Voronoi '{key}' applies only to 'seed_count' and would be ignored with 'points'", ctx
                )

    mode = node_data.get("mode", "engrave")
    if mode == "engrave":
        for key in ("line_width", "cell_inset", "rest", "rest_tool"):
            if key in node_data:
                raise PMLParseError(f"Voronoi '{key}' is only valid with 'mode: pocket'", ctx)
        return "engrave"
    if mode != "pocket":
        raise PMLParseError(f"Unknown Voronoi mode: '{mode}'. Known modes: {', '.join(_VORONOI_MODES)}", ctx)
    if "line_width" not in node_data:
        raise PMLParseError("Voronoi 'mode: pocket' requires 'line_width'", ctx)
    if "min_length" in node_data:
        raise PMLParseError("Voronoi 'min_length' is only valid with 'mode: engrave'", ctx)
    return "pocket"


def _parse_voronoi_node(node_data: dict, path: str) -> VoronoiGen:
    ctx = f"{path}.Voronoi"
    mode = _check_voronoi_keys(node_data, ctx)

    seed_count = _safe_int(node_data["seed_count"], "seed_count", ctx) if "seed_count" in node_data else None
    if seed_count is not None and seed_count < 2:
        raise PMLParseError(f"Voronoi 'seed_count' must be at least 2, got {seed_count}", ctx)
    seed = _safe_int(node_data.get("seed", 0), "seed", ctx)
    if seed < 0:
        raise PMLParseError(f"Voronoi 'seed' must be a non-negative integer, got {seed}", ctx)
    min_spacing_mm = parse_dimension(node_data["min_spacing"]) if "min_spacing" in node_data else None
    if min_spacing_mm is not None and min_spacing_mm <= 0:
        raise PMLParseError(
            f"Voronoi 'min_spacing' must be positive, got {min_spacing_mm}mm; omit it for plain uniform sampling", ctx
        )

    return VoronoiGen(
        depth_mm=parse_dimension(_require(node_data, "depth", ctx)),
        seed_count=seed_count,
        points=_parse_voronoi_points(node_data["points"], ctx) if "points" in node_data else None,
        seed=seed,
        min_spacing_mm=min_spacing_mm,
        margin_mm=parse_dimension(node_data.get("margin", "0mm")),
        mode=mode,
        line_width_mm=parse_dimension(node_data["line_width"]) if "line_width" in node_data else None,
        cell_inset_mm=parse_dimension(node_data.get("cell_inset", "0mm")),
        min_length_mm=parse_dimension(node_data.get("min_length", "0mm")),
        rest=_parse_rest(node_data, ctx),
    )


_STRING_ART_RULES = ("multiply", "skip", "mirror")
_STRING_ART_RULE_KEYS = {"multiply": "factor", "skip": "step"}


def _parse_string_art_node(node_data: dict, path: str) -> StringArtGen:
    ctx = f"{path}.StringArt"
    rule = _require(node_data, "rule", ctx)
    if rule not in _STRING_ART_RULES:
        raise PMLParseError(f"Unknown StringArt rule: '{rule}'. Known rules: {', '.join(_STRING_ART_RULES)}", ctx)
    for key_rule, key in _STRING_ART_RULE_KEYS.items():
        if key in node_data and rule != key_rule:
            raise PMLParseError(f"StringArt '{key}' is only valid with 'rule: {key_rule}', not '{rule}'", ctx)

    return StringArtGen(
        anchors=_safe_int(_require(node_data, "anchors", ctx), "anchors", ctx),
        rule=rule,
        depth_mm=parse_dimension(_require(node_data, "depth", ctx)),
        factor=_safe_int(_require(node_data, "factor", ctx), "factor", ctx) if rule == "multiply" else None,
        step=_safe_int(_require(node_data, "step", ctx), "step", ctx) if rule == "skip" else None,
        phase_deg=_safe_float(node_data.get("phase", 0.0), "phase", ctx),
        min_length_mm=parse_dimension(node_data.get("min_length", "0mm")),
    )


def _validate_node_structure(node: Any, path: str, parent: Any = None, in_zone: bool = False) -> None:
    if isinstance(node, Feature):
        raise PMLParseError(
            "Standalone Feature is not allowed here; attach it to a shape with feature: or one Feature child (PM-18 violation)",
            path,
        )
    if isinstance(node, ComponentInstance):
        _validate_node_structure(node.body, f"{path}.body", parent, in_zone)
        return
    is_zone = isinstance(node, (Island, Keepout))
    if is_zone:
        if in_zone:
            raise PMLParseError("Nested Island/Keepout zones are not allowed", path)
        if not node.children:
            raise PMLParseError(f"{type(node).__name__} requires nonempty children", path)
        parent_feature = getattr(parent, "feature", None)
        pocket_parent = parent_feature is not None and parent_feature.type == "pocket"
        if isinstance(node, Island) and not (isinstance(parent, Rect) and pocket_parent):
            raise PMLParseError("Island must be a direct child of a Rect with a pocket feature", path)
        if isinstance(node, Keepout) and pocket_parent:
            raise PMLParseError(
                "Keepout marks a clamp or fixture zone no cut may enter; use Island for material a pocket preserves",
                path,
            )
    for index, child in enumerate(getattr(node, "children", ())):
        _validate_node_structure(child, f"{path}.children[{index}]", node, in_zone or is_zone)
    for field in ("child", "layout"):
        child = getattr(node, field, None)
        if child is not None:
            _validate_node_structure(child, f"{path}.{field}", node, in_zone or is_zone)
    if isinstance(node, Place) and node.layout is not None:
        if not isinstance(node.layout, Grid):
            raise PMLParseError(
                "Place.layout must be a Grid; omit layout to use the parent region (PM-18 violation)", f"{path}.layout"
            )
        if node.layout.children:
            raise PMLParseError(
                "Place.layout Grid cannot contain children; put them in Place.children (PM-18 violation)",
                f"{path}.layout.children",
            )


def parse_node(data: dict, path: str = "") -> Any:  # noqa: C901 — PML node-type dispatcher
    if not isinstance(data, dict):
        raise PMLParseError(f"Expected dict, got {type(data).__name__}", path)

    type_keys = [k for k in data if isinstance(k, str) and k[:1].isupper()]

    if len(type_keys) == 0:
        raise PMLParseError(f"No node type found in {list(data.keys())}", path)
    if len(type_keys) > 1:
        raise PMLParseError(f"Multiple node types found: {type_keys}", path)

    node_type = type_keys[0]
    siblings = [str(key) for key in data if key != node_type]
    if siblings:
        raise PMLParseError(
            f"{', '.join(repr(key) for key in siblings)} must be inside the {node_type} mapping (PM-18 violation)", path
        )
    if node_type not in _NODE_KEYS:
        raise PMLParseError(f"Unknown node type: {node_type}", path)
    node_data = data[node_type]
    if node_data is None:
        node_data = {}

    ctx = f"{path}.{node_type}"
    hint = ""
    if (
        node_type in ("Rect", "RoundedRect", "Ellipse")
        and isinstance(node_data, dict)
        and any(key in node_data for key in ("w", "h", "x", "y", "width", "height"))
    ):
        hint = "placement and size go in at: {x, y, width, height}"
    if node_type == "Wave" and isinstance(node_data, dict) and "groove" in node_data:
        hint = "Wave 'groove' was renamed to 'spacing'; engraving width comes from the selected tool"
    _reject_unknown_keys(node_data, _NODE_KEYS[node_type], node_type, ctx, hint=hint)
    if node_type in _AT_KEYS and "at" in node_data:
        at = node_data["at"]
        _reject_unknown_keys(at, _AT_KEYS[node_type], "at", f"{ctx}.at")
        _require(at, "x", f"{ctx}.at")
        _require(at, "y", f"{ctx}.at")

    if node_type == "Radial":
        return _parse_radial_node(node_data, path)

    if node_type == "Curve":
        return _parse_curve_node(node_data, path)

    if node_type == "Phyllotaxis":
        return _parse_phyllotaxis_node(node_data, path)

    if node_type == "Voronoi":
        return _parse_voronoi_node(node_data, path)

    if node_type == "StringArt":
        return _parse_string_art_node(node_data, path)

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
    if "feature" in node_data:
        feature = parse_feature(node_data["feature"], f"{path}.{node_type}.feature")

    feature_children = [child for child in children if isinstance(child, Feature)]
    if feature_children:
        if "feature" not in _NODE_KEYS[node_type]:
            raise PMLParseError(f"{node_type} does not accept Feature children (PM-18 violation)", ctx)
        if feature is not None or len(feature_children) > 1:
            raise PMLParseError(
                "A node carries at most one feature, from feature: or one Feature child (PM-18 violation)", ctx
            )
        feature = feature_children[0]
        children = tuple(child for child in children if not isinstance(child, Feature))
    if node_type in ("Line", "Polyline", "Spline") and children:
        raise PMLParseError(f"{node_type} children may contain only one Feature child (PM-18 violation)", ctx)

    node_id = node_data.get("id") if isinstance(node_data, dict) else None
    node_label = node_data.get("label") if isinstance(node_data, dict) else None

    if node_type == "Panel":
        return Panel(children=children, id=node_id)

    elif node_type == "Rect":
        at_data = node_data.get("at") if isinstance(node_data, dict) else None
        rect = Rect(children=children, feature=feature, id=node_id, label=node_label)
        if at_data is not None:
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
        if at_data is not None:
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
        if at_data is not None:
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

    elif node_type == "Island":
        return Island(children=children, id=node_id)

    elif node_type == "Keepout":
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
            tool_name=_parse_tool_name(node_data.get("tool"), path),
        )

    elif node_type == "Pocket":
        return PocketGen(
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Pocket")),
            face=_parse_face(node_data.get("face"), f"{path}.Pocket"),
            feeds_override=_parse_feeds_override(node_data.get("feeds"), f"{path}.Pocket.feeds"),
            tool_name=_parse_tool_name(node_data.get("tool"), path),
        )

    elif node_type == "RaisedPanel":
        return RaisedPanelGen(
            tool_name=_parse_tool_name(node_data.get("tool"), path),
            feeds_override=_parse_feeds_override(node_data.get("feeds"), path + ".feeds"),
            border_width_mm=parse_dimension(node_data["border_width"]) if "border_width" in node_data else None,
            border_depth_mm=parse_dimension(_require(node_data, "border_depth", f"{path}.RaisedPanel")),
            field_depth_mm=parse_dimension(_require(node_data, "field_depth", f"{path}.RaisedPanel")),
            profile=node_data.get("profile", "gutter"),
            v_angle_deg=_safe_float(node_data.get("v_angle", 90), "v_angle", f"{path}.RaisedPanel"),
        )

    elif node_type == "Chamfer":
        return ChamferGen(
            tool_name=_parse_tool_name(node_data.get("tool"), path),
            feeds_override=_parse_feeds_override(node_data.get("feeds"), path + ".feeds"),
            width_mm=parse_dimension(_require(node_data, "width", f"{path}.Chamfer")),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Chamfer")),
        )

    elif node_type == "Roundover":
        return RoundoverGen(
            tool_name=_parse_tool_name(node_data.get("tool"), path),
            feeds_override=_parse_feeds_override(node_data.get("feeds"), path + ".feeds"),
            radius_mm=parse_dimension(_require(node_data, "radius", f"{path}.Roundover")),
        )

    elif node_type == "Wave":
        ctx = f"{path}.Wave"
        if ("count" in node_data) == ("wavelength" in node_data):
            raise PMLParseError("Wave requires exactly one of 'count' or 'wavelength'", ctx)
        count = node_data.get("count")
        if "count" in node_data and (isinstance(count, bool) or not isinstance(count, int) or count <= 0):
            raise PMLParseError(f"Wave 'count' must be a positive integer, got {count}", ctx)
        angles = {key: _safe_float(node_data.get(key, 0.0), key, ctx) for key in ("direction", "phase")}
        if not all(math.isfinite(value) for value in angles.values()):
            raise PMLParseError(f"Wave direction and phase must be finite, got {angles}", ctx)
        return WaveGen(
            wave_count=count,
            amplitude_mm=parse_dimension(_require(node_data, "amplitude", ctx)),
            wavelength_mm=parse_dimension(node_data["wavelength"]) if "wavelength" in node_data else None,
            spacing_mm=parse_dimension(_require(node_data, "spacing", ctx)),
            depth_mm=parse_dimension(_require(node_data, "depth", ctx)),
            direction_deg=angles["direction"],
            phase_deg=angles["phase"],
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
        _reject_unknown_keys(size_data, ("width", "height"), "Heightfield size", f"{path}.Heightfield.size")
        if "width" not in size_data or "height" not in size_data:
            raise PMLParseError("Heightfield 'size' must have 'width' and 'height' keys", path)
        tools_raw = node_data.get("tools")
        tools: tuple[HeightfieldToolEntry, ...] = ()
        if tools_raw is not None:
            if not isinstance(tools_raw, list) or not tools_raw:
                raise PMLParseError("Heightfield 'tools' must be a non-empty list", path)
            tools = tuple(_parse_heightfield_tool_entry(t, path) for t in tools_raw)
        return HeightfieldGen(
            image_path=_require(node_data, "image", f"{path}.Heightfield"),
            width_mm=parse_dimension(size_data["width"]),
            height_mm=parse_dimension(size_data["height"]),
            depth_mm=parse_dimension(_require(node_data, "depth", f"{path}.Heightfield")),
            white_is_high=node_data.get("white_is_high", True),
            tools=tools,
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
        return _parse_concentric_border_node(node_data, path)

    elif node_type == "Place":
        layout = parse_node(node_data["layout"], f"{path}.{node_type}.layout") if "layout" in node_data else None
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
            part_id=node_data.get("part_id"),
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
        if at_data is not None:
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
        if at_data is not None:
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
        return _parse_assembly_node(node_data, path)

    elif node_type == "UseComponent":
        args = node_data.get("args", {})
        if not isinstance(args, dict):
            raise PMLParseError("UseComponent args must be a mapping", f"{path}.UseComponent")
        return UseComponent(
            component_name=_require(node_data, "name", f"{path}.UseComponent"),
            args=args,
        )

    elif node_type == "Engrave":
        depth_mm = parse_dimension(_require(node_data, "depth", f"{path}.Engrave"))
        return Feature(
            type="engrave",
            depth_mm=depth_mm,
            tool_name=_parse_tool_name(node_data.get("tool"), path),
            feeds_override=_parse_feeds_override(node_data.get("feeds"), path + ".feeds"),
        )

    elif node_type == "Beam":
        return _parse_beam_node(node_data, path)

    else:
        raise PMLParseError(f"Unknown node type: {node_type}", path)


def _parse_surface_block(block: dict | None) -> SurfaceDecl | None:
    if block is None:
        return None
    _reject_unknown_keys(
        block,
        (
            "depth-per-pass",
            "passes",
            "stepover",
            "direction",
            "margin-overrun",
            "cool_every",
            "cool_dwell",
            "tool",
            "feeds",
        ),
        "Surface",
        "Surface",
    )
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
        tool_name=_parse_tool_name(block.get("tool"), "Surface"),
        feeds_override=_parse_feeds_override(block.get("feeds"), "Surface.feeds"),
        depth_mm=depth_mm,
        passes=passes,
        stepover_pct=stepover_pct if "stepover" in block else None,
        direction=direction,
        margin_mm=margin_mm,
        cool_every=cool_every,
        cool_dwell_s=cool_dwell_s,
    )


def _substitute_component_values(value: Any, params: dict[str, Any], path: str) -> Any:
    if isinstance(value, dict):
        mapping = {}
        for key, item in value.items():
            mapping[key] = _substitute_component_values(item, params, f"{path}.{key}")
        return mapping
    if isinstance(value, list):
        sequence = []
        for index, item in enumerate(value):
            sequence.append(_substitute_component_values(item, params, f"{path}[{index}]"))
        return sequence
    if not isinstance(value, str):
        return value

    def parameter(name: str) -> Any:
        if name not in params:
            raise PMLParseError(f"Unknown component parameter: ${{{name}}}", path)
        result = params[name]
        if not isinstance(result, (str, int, float, bool)):
            raise PMLParseError(f"Component parameter '{name}' must be a scalar, got {result!r}", path)
        if isinstance(result, str) and "${" in result:
            raise PMLParseError(f"Component parameter '{name}' must have a concrete value, got {result!r}", path)
        return result

    match = re.fullmatch(r"\$\{(\w+)\}", value)
    if match:
        return parameter(match.group(1))
    result = re.sub(r"\$\{(\w+)\}", lambda match: str(parameter(match.group(1))), value)
    if "${" in result:
        raise PMLParseError(f"Invalid component parameter reference: {value!r}", path)
    return result


def _contains_component_reference(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_component_reference(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_component_reference(item) for item in value)
    return isinstance(value, str) and "${" in value


def _bind_component_uses(value: Any, components: dict[str, ComponentDef], stack: tuple[str, ...] = ()) -> Any:
    if isinstance(value, UseComponent):
        name = value.component_name
        path = " -> ".join((*stack, name))
        if name not in components:
            raise PMLParseError(f"Unknown component: {name}", path)
        if name in stack:
            raise PMLParseError(f"Recursive component use: {path}")
        definition = components[name]
        unknown = set(value.args) - set(definition.params)
        if unknown:
            raise PMLParseError(f"Unknown arguments for component '{name}': {', '.join(sorted(unknown))}", path)
        body = definition.body
        if isinstance(body, ComponentTemplate):
            params = {**definition.params, **value.args}
            bound_source = _substitute_component_values(body.source, params, f"components.{name}.body")
            try:
                body = (
                    Panel(children=parse_children(bound_source, path))
                    if isinstance(bound_source, list)
                    else parse_node(bound_source, path)
                )
            except ValueError as exc:
                raise PMLParseError(f"Component '{name}' has invalid bound values: {exc}", path) from exc
        return ComponentInstance(use=value, body=_bind_component_uses(body, components, (*stack, name)))
    if isinstance(value, tuple):
        bound_items = []
        for item in value:
            bound_items.append(_bind_component_uses(item, components, stack))
        return tuple(bound_items)
    if is_dataclass(value) and not isinstance(value, type):
        updates = {}
        for field in fields(value):
            current = getattr(value, field.name)
            if is_dataclass(current) or isinstance(current, tuple):
                updates[field.name] = _bind_component_uses(current, components, stack)
        return replace(value, **updates)
    return value


def _parse_components(data: dict[str, Any]) -> dict[str, ComponentDef]:
    components: dict[str, ComponentDef] = {}
    for name, comp_data in data.items():
        path = f"components.{name}"
        if not isinstance(comp_data, dict):
            raise PMLParseError("Component definition must be a mapping", path)
        _reject_unknown_keys(comp_data, ("params", "body"), "component definition", path)
        params = comp_data.get("params", {})
        if not isinstance(params, dict):
            raise PMLParseError("Component params must be a mapping", path)
        body_data = comp_data.get("body")
        body: Any = None
        if body_data:
            if _contains_component_reference(body_data):
                body = ComponentTemplate(source=body_data)
            elif isinstance(body_data, list):
                body = Panel(children=parse_children(body_data, f"{path}.body"))
            else:
                body = parse_node(body_data, f"{path}.body")
        _validate_node_structure(body, f"{path}.body")
        components[name] = ComponentDef(name=name, params=params, body=body)
    return components


def _parse_sheet_dimension(sheet: dict, axis: str, margin_mm: float) -> float:
    candidates = []
    for key in (f"working_{axis}", f"physical_{axis}", axis):
        if key in sheet:
            value = parse_dimension(sheet[key])
            if key == f"working_{axis}":
                value += 2 * margin_mm
            candidates.append((key, value))
    if not candidates:
        raise PMLParseError(f"Sheet missing '{axis}', 'physical_{axis}', or 'working_{axis}'")
    first_key, physical = candidates[0]
    for key, value in candidates[1:]:
        if not math.isclose(physical, value, rel_tol=0.0, abs_tol=_DIMENSION_MATCH_TOLERANCE_MM):
            raise PMLParseError(
                f"Conflicting Sheet {axis}: {first_key} implies {physical}mm physical size, {key} implies {value}mm; expected matching dimensions (PM-18 violation)",
                "Sheet",
            )
    return physical


def parse_pml_yaml(source: str) -> CompositionalLayoutAST:
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(source)
    except Exception as e:
        raise PMLParseError(f"Invalid YAML: {e}") from e

    if data is None:
        raise PMLParseError("Empty YAML document")

    _reject_unknown_keys(
        data, ("Sheet", "project", "kerf", "Surface", "components", "children", "machining"), "PML root", "root"
    )
    sheet_block = data.get("Sheet")
    if sheet_block is None:
        raise PMLParseError("Missing 'Sheet:' root key")

    _reject_unknown_keys(sheet_block, _SHEET_KEYS, "Sheet", "Sheet")
    margin_mm = parse_dimension(sheet_block.get("margin", "0mm"))

    width_mm = _parse_sheet_dimension(sheet_block, "width", margin_mm)
    height_mm = _parse_sheet_dimension(sheet_block, "height", margin_mm)

    min_web_mm = parse_dimension(sheet_block["min_web"]) if "min_web" in sheet_block else DEFAULT_MIN_WEB_MM
    if min_web_mm < 0.0:
        raise PMLParseError(f"Sheet min_web must be >= 0, got {min_web_mm}", "Sheet")

    safe_z_mm = parse_dimension(sheet_block["safe_z"]) if "safe_z" in sheet_block else None
    if safe_z_mm is not None and safe_z_mm <= 0.0:
        raise PMLParseError(f"Sheet safe_z must be > 0, got {safe_z_mm}", "Sheet")

    sheet = Sheet(
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=parse_dimension(_require(sheet_block, "thickness", "Sheet")),
        margin_mm=margin_mm,
        show_dimensions=sheet_block.get("show_dimensions", True),
        material=str(sheet_block.get("material", "mdf")),
        gcode_output=str(sheet_block.get("gcode_output", "per-operation")),
        min_web_mm=min_web_mm,
        safe_z_mm=safe_z_mm,
    )

    project = data.get("project")
    kerf_width_mm = parse_dimension(data["kerf"]) if "kerf" in data else None

    surface = _parse_surface_block(data.get("Surface"))

    components_block = data.get("components", {})
    if not isinstance(components_block, dict):
        raise PMLParseError("Components must be a mapping", "components")
    components = _parse_components(components_block)

    children_data = data.get("children", [])
    children = parse_children(children_data, "root")

    root = Panel(children=children) if children else None
    root = _bind_component_uses(root, components)
    _validate_node_structure(root, "root")

    return CompositionalLayoutAST(
        sheet=sheet,
        components=components,
        root=root,
        project=project,
        kerf_width_mm=kerf_width_mm,
        surface=surface,
        machining=_parse_machining(data.get("machining")),
    )


_VALID_HOLDING_KEYS = {"onion_skin", "tab_count", "tab_height", "tab_width"}


def _parse_holding_block(block: dict[str, Any], path: str) -> HoldingSpec:
    _reject_unknown_keys(block, sorted(_VALID_HOLDING_KEYS), "holding", path, error_type=NestParseError)
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

    if not isinstance(data, dict):
        raise NestParseError("Nest document must be a mapping (PM-18 violation)")
    nest_block = data.get("Nest")
    if nest_block is None:
        raise NestParseError("Missing 'Nest:' root key")

    _reject_unknown_keys(data, ("Nest",), "nest root", "root", error_type=NestParseError)
    _reject_unknown_keys(
        nest_block,
        ("algorithm", "Sheet", "kerf", "margin", "gap_margin", "holding", "parts", "machining"),
        "Nest",
        "Nest",
        error_type=NestParseError,
    )
    algorithm = nest_block.get("algorithm")
    if algorithm is None:
        raise NestParseError("Missing 'algorithm' in Nest block")

    sheet_block = nest_block.get("Sheet")
    if sheet_block is None:
        raise NestParseError("Missing 'Sheet:' in Nest block")

    _reject_unknown_keys(
        sheet_block, ("width", "height", "thickness", "material"), "nest Sheet", "Nest.Sheet", error_type=NestParseError
    )
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

        _reject_unknown_keys(
            part_data,
            ("name", "width", "height", "quantity", "template", "shape", "holding"),
            "nest part",
            "Nest.parts",
            error_type=NestParseError,
        )
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
                _reject_unknown_keys(
                    template_block,
                    ("name", "params"),
                    "part template",
                    f"Nest.parts.{name}.template",
                    error_type=NestParseError,
                )
                template = template_block.get("name")
                if template is None:
                    raise NestParseError("Part template requires name (PM-18 violation)", f"Nest.parts.{name}.template")
                params_block = template_block.get("params", {})
                if not isinstance(params_block, dict):
                    raise NestParseError(
                        "Template params must be a mapping (PM-18 violation)", f"Nest.parts.{name}.template.params"
                    )
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
            shape_keys: tuple[str, ...] = ("type",)
            if shape_type == "RoundedRect":
                shape_keys += ("radius", "corners")
            elif shape_type == "Polygon":
                shape_keys += ("points",)
            _reject_unknown_keys(
                shape_block, shape_keys, "part shape", f"Nest.parts.{name}.shape", error_type=NestParseError
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

    try:
        machining = _parse_machining(nest_block.get("machining"), "Nest.machining")
    except PMLParseError as exc:
        raise NestParseError(exc.message, exc.path) from exc

    return NestJob(
        algorithm=algorithm,
        sheet_width_mm=sheet_width,
        sheet_height_mm=sheet_height,
        sheet_thickness_mm=sheet_thickness,
        kerf_mm=kerf_mm,
        margin_mm=margin_mm,
        gap_margin_mm=parse_dimension(nest_block.get("gap_margin", "0mm")),
        holding=job_holding,
        parts=parts,
        material=str(sheet_block.get("material", "mdf")),
        machining=machining,
        kerf_explicit="kerf" in nest_block,
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

    _reject_unknown_keys(data, ("Template",), "template root", "root")
    template_block = data.get("Template")
    if template_block is None:
        raise PMLParseError("Missing 'Template:' root key")

    _reject_unknown_keys(template_block, ("name", "params", "body"), "Template", "Template")
    name = template_block.get("name")
    if name is None:
        raise PMLParseError("Template missing 'name'")

    params_block = template_block.get("params", {})
    if not isinstance(params_block, dict):
        raise PMLParseError("Template params must be a mapping (PM-18 violation)", "Template.params")
    params: dict[str, Any] = {}
    for k, v in params_block.items():
        if isinstance(v, str) and v.endswith("mm"):
            params[k] = parse_dimension(v)
        else:
            params[k] = v

    body = None
    if parse_body and "body" in template_block:
        body = parse_node(template_block["body"], "Template.body")
        _validate_node_structure(body, "Template.body")

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
