class HintKeys:
    ID = "id"
    SHAPE = "shape"
    GEOMETRY = "geometry"
    CENTER_XY_MM = "center_xy_mm"
    DEPTH_MM = "depth_mm"
    START_DEPTH_MM = "start_depth_mm"
    SIDE = "side"
    TABS = "tabs"
    KEEPOUTS = "keepouts"
    CORNER_CLEANUP_TOOL_DIAMETER_MM = "corner_cleanup_tool_diameter_mm"
    CORNERS = "corners"
    CORNER_TOOL_DIAMETER_MM = "corner_tool_diameter_mm"
    POCKET_ID = "pocket_id"


class GeometryKeys:
    W_MM = "w_mm"
    H_MM = "h_mm"
    DIAMETER_MM = "diameter_mm"
    RADIUS_MM = "radius_mm"
    RADIUS_TL_MM = "radius_tl_mm"
    RADIUS_TR_MM = "radius_tr_mm"
    RADIUS_BR_MM = "radius_br_mm"
    RADIUS_BL_MM = "radius_bl_mm"
    ISLANDS = "islands"
    EDGE_TREATMENT = "edge_treatment"

    POINTS = "points"
    HOLES = "holes"

    X_MIN = "x_min"
    X_MAX = "x_max"
    Y_MIN = "y_min"
    Y_MAX = "y_max"

    TYPE = "type"
    DISTANCE_MM = "distance_mm"
    ROUGH_ALLOWANCE_MM = "rough_allowance_mm"
    FINISH_ALLOWANCE_MM = "finish_allowance_mm"


class TabKeys:
    COUNT = "count"
    HEIGHT_MM = "height_mm"
    WIDTH_MM = "width_mm"


class MetadataKeys:
    HINT_TYPE = "hint_type"
    ORIGINAL_ID = "original_id"
    ITEM_TYPE = "item_type"
    FEATURE_TYPE = "feature_type"
    SHAPE_ID = "shape_id"

    BEVEL = "bevel"
    CHAMFER = "chamfer"
    WIDTH_MM = "width_mm"
    ANGLE_DEG = "angle_deg"
    INNER_DEPTH_MM = "inner_depth_mm"


class FeatureType:
    PROFILE = "profile"
    POCKET = "pocket"
    HOLE = "hole"
    ENGRAVE = "engrave"

    BEVEL = "bevel"
    CHAMFER = "chamfer"


class ShapeType:
    RECT = "Rect"
    RECTANGLE = "Rectangle"
    CIRCLE = "Circle"
    ROUNDED_RECT = "RoundedRect"
    POLYGON = "Polygon"
    LINE = "Line"
    POLYLINE = "Polyline"

    RECT_LOWER = "rect"
    RECTANGLE_LOWER = "rectangle"
    CIRCLE_LOWER = "circle"
    POLYGON_LOWER = "polygon"
    LINE_LOWER = "line"
    POLYLINE_LOWER = "polyline"

    @classmethod
    def is_rect(cls, shape: str) -> bool:
        return shape.lower() in (cls.RECT_LOWER, cls.RECTANGLE_LOWER)

    @classmethod
    def is_circle(cls, shape: str) -> bool:
        return shape.lower() == cls.CIRCLE_LOWER

    @classmethod
    def is_polygon(cls, shape: str) -> bool:
        return shape.lower() == cls.POLYGON_LOWER

    @classmethod
    def is_line(cls, shape: str) -> bool:
        return shape.lower() == cls.LINE_LOWER

    @classmethod
    def is_polyline(cls, shape: str) -> bool:
        return shape.lower() == cls.POLYLINE_LOWER


class Side:
    OUTSIDE = "outside"
    INSIDE = "inside"
    ON = "on"


class DepthMode:
    THROUGH = "through"
    HALF = "half"

    @classmethod
    def is_through(cls, depth: str | float | None) -> bool:
        return depth == cls.THROUGH

    @classmethod
    def is_half(cls, depth: str | float | None) -> bool:
        return depth == cls.HALF

    @classmethod
    def resolve(cls, depth: str | float | None, sheet_thickness_mm: float) -> float:
        if depth is None:
            return sheet_thickness_mm
        if cls.is_through(depth):
            return sheet_thickness_mm
        if cls.is_half(depth):
            return sheet_thickness_mm / 2.0
        return float(depth)


class HintCollectionKeys:
    UNITS = "units"
    KERF_WIDTH_MM = "kerf_width_mm"
    MIN_CHANNEL_WIDTH_MM = "min_channel_width_mm"
    PROFILES = "profiles"
    POCKETS = "pockets"
    HOLES = "holes"
    ENGRAVES = "engraves"
    CORNER_CLEANUPS = "corner_cleanups"
    KEEPOUTS = "keepouts"
