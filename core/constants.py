"""String constants for mill_ui to prevent typos and enable autocomplete.

These constants define the canonical string keys used throughout the adapter layer
for hint dictionaries, geometry data, feature types, and shape types.

Usage:
    from core.constants import HintKeys, FeatureType

    hint = {
        HintKeys.ID: "door_outer",
        HintKeys.SHAPE: ShapeType.RECT,
        HintKeys.DEPTH_MM: 19.0,
    }

    if feature.type == FeatureType.PROFILE:
        ...
"""


class HintKeys:
    """Keys for v1 hint dictionaries passed to the planner."""

    ID = "id"
    SHAPE = "shape"
    GEOMETRY = "geometry"
    CENTER_XY_MM = "center_xy_mm"
    DEPTH_MM = "depth_mm"
    START_DEPTH_MM = "start_depth_mm"
    SIDE = "side"
    TABS = "tabs"
    CORNER_CLEANUP_TOOL_DIAMETER_MM = "corner_cleanup_tool_diameter_mm"
    CORNERS = "corners"
    CORNER_TOOL_DIAMETER_MM = "corner_tool_diameter_mm"
    POCKET_ID = "pocket_id"


class GeometryKeys:
    """Keys for geometry data dictionaries."""

    W_MM = "w_mm"
    H_MM = "h_mm"
    DIAMETER_MM = "diameter_mm"
    RADIUS_MM = "radius_mm"
    ISLANDS = "islands"
    EDGE_TREATMENT = "edge_treatment"

    # Bounds keys (used in island data)
    X_MIN = "x_min"
    X_MAX = "x_max"
    Y_MIN = "y_min"
    Y_MAX = "y_max"

    # Edge treatment sub-keys
    TYPE = "type"
    DISTANCE_MM = "distance_mm"
    ROUGH_ALLOWANCE_MM = "rough_allowance_mm"
    FINISH_ALLOWANCE_MM = "finish_allowance_mm"


class TabKeys:
    """Keys for tab constraint dictionaries."""

    COUNT = "count"
    HEIGHT = "height"  # Legacy key
    HEIGHT_MM = "height_mm"
    WIDTH = "width"  # Legacy key
    WIDTH_MM = "width_mm"


class MetadataKeys:
    """Keys for RemovalIntent metadata dictionaries."""

    HINT_TYPE = "hint_type"
    ORIGINAL_ID = "original_id"
    ITEM_TYPE = "item_type"
    FEATURE_TYPE = "feature_type"
    SHAPE_ID = "shape_id"


class FeatureType:
    """Feature type values for machining operations."""

    PROFILE = "profile"
    POCKET = "pocket"
    HOLE = "hole"
    ENGRAVE = "engrave"


class ShapeType:
    """Shape type values for geometry primitives."""

    RECT = "Rect"
    RECTANGLE = "Rectangle"  # Alias for Rect
    CIRCLE = "Circle"
    ROUNDED_RECT = "RoundedRect"

    # Lowercase variants (used in some comparisons)
    RECT_LOWER = "rect"
    RECTANGLE_LOWER = "rectangle"
    CIRCLE_LOWER = "circle"

    @classmethod
    def is_rect(cls, shape: str) -> bool:
        """Check if shape is a rectangle type (case-insensitive)."""
        return shape.lower() in (cls.RECT_LOWER, cls.RECTANGLE_LOWER)

    @classmethod
    def is_circle(cls, shape: str) -> bool:
        """Check if shape is a circle type (case-insensitive)."""
        return shape.lower() == cls.CIRCLE_LOWER


class Side:
    """Side values for profile operations."""

    OUTSIDE = "outside"
    INSIDE = "inside"
    ON = "on"


class DepthMode:
    """Depth mode string values.

    Note: Feature.depth can be either a string mode (like "through")
    or a numeric float. This class only defines the string constants.
    """

    THROUGH = "through"
    HALF = "half"

    @classmethod
    def is_through(cls, depth: str | float | None) -> bool:
        """Check if depth represents full sheet thickness."""
        return depth == cls.THROUGH

    @classmethod
    def is_half(cls, depth: str | float | None) -> bool:
        """Check if depth represents half sheet thickness."""
        return depth == cls.HALF

    @classmethod
    def resolve(cls, depth: str | float | None, sheet_thickness_mm: float) -> float:
        """Resolve a depth value to millimeters.

        Args:
            depth: Either a string mode ("through", "half") or numeric mm value
            sheet_thickness_mm: Sheet thickness for relative depth modes

        Returns:
            Depth in millimeters
        """
        if depth is None:
            return sheet_thickness_mm
        if cls.is_through(depth):
            return sheet_thickness_mm
        if cls.is_half(depth):
            return sheet_thickness_mm / 2.0
        return float(depth)


class HintCollectionKeys:
    """Keys for the top-level hint collection dictionary."""

    UNITS = "units"
    KERF_WIDTH_MM = "kerf_width_mm"
    MIN_CHANNEL_WIDTH_MM = "min_channel_width_mm"
    PROFILES = "profiles"
    POCKETS = "pockets"
    HOLES = "holes"
    ENGRAVES = "engraves"
    CORNER_CLEANUPS = "corner_cleanups"
