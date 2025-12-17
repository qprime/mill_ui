"""Compositional LayoutAST extensions for hierarchical, region-relative layouts.

These nodes support:
- Region-relative composition (no explicit XY coordinates required)
- Layout managers (frame, grid)
- Reusable components
- Sheet-level multi-instance placement

Regions are computed during layout resolution, not authored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Panel:
    """Root panel node - defines the workpiece region.

    Panel establishes the initial region from sheet bounds.
    Children are placed within this region.

    Attributes:
        children: Nested layout nodes
        id: Optional identifier
    """
    children: tuple[Any, ...] = ()  # Tuple of compositional nodes or leaf shapes
    id: str | None = None


@dataclass(frozen=True)
class Inset:
    """Shrinks current region inward by specified amount on all sides.

    Operates on the current region context, reducing available space
    for children by the inset amount on each edge.

    Attributes:
        amount_mm: Inset distance (positive shrinks inward)
        children: Nodes to place within inset region
    """
    amount_mm: float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Frame:
    """Produces inner field region from current region.

    Frame works on ANY closed region:
    - Creates a profile at the boundary
    - Produces an inner region (shrunk by frame width)
    - Children operate within the inner region

    Attributes:
        width_mm: Frame width (distance from edge to inner field)
        children: Nodes to place within inner field region
        profile_depth: Depth for frame profile (default "through")
        profile_side: Profile side (default "outside")
    """
    width_mm: float
    children: tuple[Any, ...] = ()
    profile_depth: str | float = "through"
    profile_side: str = "outside"


@dataclass(frozen=True)
class Grid:
    """Subdivides current region into rows × cols cells.

    Creates a regular grid layout within the current region.
    Gap is the spacing between cells (not inset from edges).

    Attributes:
        rows: Number of rows
        cols: Number of columns
        gap_mm: Spacing between cells (default 0)
        children: Nodes to replicate in each cell (via Cell node)
    """
    rows: int
    cols: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Cell:
    """Content template for grid cells.

    Cell nodes are direct children of Grid.
    Each Cell subtree is replicated once per grid cell.

    Attributes:
        children: Nodes to replicate in each grid cell
        inset_mm: Optional inset applied to each cell before placing children
    """
    children: tuple[Any, ...] = ()
    inset_mm: float = 0.0


@dataclass(frozen=True)
class Split:
    """Subdivides current region into panes with rail/mullion bars.

    Similar to Grid but reserves material for the bars themselves.
    Rails are horizontal bars, mullions are vertical bars.
    Use case: French doors, drawer faces with decorative mullions.

    Pane sizes account for rail/mullion material:
    - Pane width = (region_width - (cols-1)*mullion_mm) / cols
    - Pane height = (region_height - (rows-1)*rail_mm) / rows

    When rail_mm=0 and mullion_mm=0, behaves like Grid.

    Attributes:
        rows: Number of rows (panes stacked vertically)
        cols: Number of columns (panes side by side)
        rail_mm: Horizontal bar width (default 0)
        mullion_mm: Vertical bar width (default 0)
        children: Nodes to replicate in each pane (via Cell node)
    """
    rows: int
    cols: int
    rail_mm: float = 0.0
    mullion_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ComponentDef:
    """Reusable component definition (named, parameterized subtree).

    Components are region-relative: they operate within the current region
    when instantiated, not at absolute coordinates.

    Attributes:
        name: Component identifier
        params: Parameter names with optional defaults
        body: Root node of component subtree
    """
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    body: Any = None  # Root compositional node or leaf shape


@dataclass(frozen=True)
class UseComponent:
    """Component instantiation - expands component with parameter substitution.

    Attributes:
        component_name: Name of component to instantiate
        args: Argument values for component parameters
    """
    component_name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Place:
    """Sheet-level multi-instance placement.

    Place subdivides the sheet (or current region) and instantiates
    content in each slot. Simple deterministic layout first;
    irregular nesting optimization deferred.

    Attributes:
        layout: Layout manager (Grid for v1)
        children: Nodes to place (typically UseComponent instances)
    """
    layout: Any  # Grid or other layout manager
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Rect:
    """Rectangle node - fills current region by default.

    Unlike legacy Item(kind="shape", type="Rect"), this is a compositional
    node that participates in region-relative layout.

    Attributes:
        children: Nested layout nodes (e.g., Frame, Grid)
        feature: Optional CAM feature (profile, pocket)
        id: Optional identifier
    """
    children: tuple[Any, ...] = ()
    feature: Any = None  # Feature dataclass from layout.py
    id: str | None = None


@dataclass(frozen=True)
class Circle:
    """Circle node - creates circular region.

    Circle can either specify explicit diameter or use 'fit' mode to inscribe
    within current region (largest circle that fits).

    Attributes:
        diameter_mm: Explicit diameter (None for fit mode)
        children: Nested layout nodes (e.g., Frame, Grid)
        feature: Optional CAM feature (profile, pocket, hole)
        id: Optional identifier
    """
    diameter_mm: float | None = None  # None means 'fit' mode
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None


@dataclass(frozen=True)
class RoundedRect:
    """Rounded rectangle node - fills current region with rounded corners.

    Attributes:
        radius_mm: Corner radius in millimeters
        children: Nested layout nodes (e.g., Frame, Grid)
        feature: Optional CAM feature (profile, pocket)
        id: Optional identifier
    """
    radius_mm: float
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None


@dataclass(frozen=True)
class Line:
    """Line node - creates open path for engraving.

    Simple canned forms: horizontal or vertical line spanning current region.
    For v1, we use deterministic orientation rather than explicit point lists.

    Attributes:
        orientation: 'horizontal' or 'vertical'
        feature: Optional CAM feature (typically engrave)
        id: Optional identifier
    """
    orientation: str  # 'horizontal' or 'vertical'
    feature: Any = None
    id: str | None = None


@dataclass(frozen=True)
class Polyline:
    """Polyline node - creates arbitrary open path for engraving.

    Uses normalized coordinates (0..1, 0..1) relative to current region.
    The resolver maps these to absolute coordinates within the region bounds.

    Use case: Arbitrary engraving paths, decorative patterns, custom shapes.

    Attributes:
        points: List of (x, y) tuples with normalized coordinates in [0, 1]
                Minimum 2 points required
                (0, 0) = bottom-left of region
                (1, 1) = top-right of region
        feature: Optional CAM feature (typically engrave)
        id: Optional identifier

    Example:
        # Diagonal line from bottom-left to top-right
        Polyline(points=[(0.0, 0.0), (1.0, 1.0)], feature=engrave_feature)

        # Zigzag pattern
        Polyline(points=[(0.1, 0.1), (0.9, 0.5), (0.1, 0.9)])
    """
    points: tuple[tuple[float, float], ...]
    feature: Any = None
    id: str | None = None

    def __post_init__(self):
        """Validate polyline constraints."""
        if len(self.points) < 2:
            raise ValueError(f"Polyline requires at least 2 points, got {len(self.points)}")

        for i, (x, y) in enumerate(self.points):
            if not (0.0 <= x <= 1.0):
                raise ValueError(f"Point {i} x-coordinate {x} out of range [0, 1]")
            if not (0.0 <= y <= 1.0):
                raise ValueError(f"Point {i} y-coordinate {y} out of range [0, 1]")


@dataclass(frozen=True)
class Keepout:
    """Keepout node - marks regions where material should be preserved (islands).

    Keepout defines subregions within a parent shape that should NOT be removed
    during milling. This creates "islands" or "raised panels" within pockets.

    Keepout must be a child of a shape with a pocket feature. During resolution,
    the keepout boundaries are computed and added to the RemovalIntent as islands.

    Nesting constraint: Keepouts cannot contain nested keepouts (validated at parse time).

    Attributes:
        children: Shape nodes defining the island boundaries (e.g., Rect, Circle)
        id: Optional identifier

    Example:
        # Faux raised panel - pocket with rectangular island
        Rect(feature=pocket_feature, children=(
            Keepout(children=(
                Inset(amount_mm=10.0, children=(
                    Rect(id="island"),
                )),
            )),
        ))
    """
    children: tuple[Any, ...] = ()
    id: str | None = None


@dataclass(frozen=True)
class Edge:
    """Edge node - specifies edge treatment intent for profiles/pockets.

    Edge defines either:
    1. Allowance semantics (rough/finish multi-pass operations)
    2. Decorative edges (fillet/chamfer hints for specialized toolpaths)

    Edge nodes are children of shapes with features and influence RemovalIntent
    constraints/annotations for downstream toolpath planning.

    Attributes:
        treatment_type: "allowance", "fillet", or "chamfer"
        rough_allowance_mm: Stock to leave for rough pass (allowance type only)
        finish_allowance_mm: Final allowance after finish pass (allowance type only)
        radius_mm: Fillet radius (fillet type only)
        distance_mm: Chamfer distance (chamfer type only)
        id: Optional identifier

    Examples:
        # Multi-pass allowance
        Rect(feature=profile_feature, children=(
            Edge(treatment_type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.1),
        ))

        # Decorative fillet
        Rect(feature=profile_feature, children=(
            Edge(treatment_type="fillet", radius_mm=3.0),
        ))
    """
    treatment_type: str  # "allowance", "fillet", "chamfer"
    rough_allowance_mm: float | None = None
    finish_allowance_mm: float | None = None
    radius_mm: float | None = None
    distance_mm: float | None = None
    id: str | None = None


@dataclass(frozen=True)
class SplinePath:
    """Spline path node - smooth, expressive centerline curves for Studio Mode.

    SplinePath represents smooth curves for decorative, artistic, and expressive CNC work.
    This is a Studio Mode primitive: tool center follows this path exactly (centerline intent).

    KEY BEHAVIORS:
    - Always treated as centerline (tool follows path, not boundary)
    - Immediately lowered to polyline during resolution (no spline math in CAM)
    - Normalized coordinates (0.0-1.0) relative to current region
    - Open paths only (closed splines optional in future)

    STUDIO MODE POLICY:
    - Visual outcome takes precedence over dimensional accuracy
    - No errors for tight curvature, self-intersection, or tool coupling
    - Designers iterate via test cuts
    - Warnings are informational only (never blocking)

    NOT FOR:
    - Pocket/profile boundaries (use Circle/Rect/RoundedRect)
    - Fit-critical geometry (use explicit boundary shapes)
    - Production CAM (use explicit polylines or boundary shapes)

    Attributes:
        points: Control points as normalized (x, y) tuples (0.0-1.0)
        feature: CAM feature (typically engrave)
        tolerance_mm: Sampling tolerance for polyline conversion (default 0.1mm)
        id: Optional identifier

    Examples:
        # Decorative wave
        SplinePath(
            points=((0.0, 0.5), (0.25, 0.6), (0.5, 0.4), (0.75, 0.6), (1.0, 0.5)),
            feature=Feature(type="engrave", depth_mm=0.8),
            id="wave"
        )

        # High-resolution curve
        SplinePath(
            points=((0.1, 0.1), (0.3, 0.2), (0.5, 0.5), (0.7, 0.8), (0.9, 0.9)),
            feature=Feature(type="engrave", depth_mm=1.0),
            tolerance_mm=0.05,
            id="flourish"
        )
    """
    points: tuple[tuple[float, float], ...]  # Normalized (x, y) control points
    feature: Any = None  # Feature dataclass from layout.py
    tolerance_mm: float = 0.1  # Sampling tolerance for polyline conversion
    id: str | None = None

    def __post_init__(self):
        """Validate spline path."""
        if len(self.points) < 2:
            raise ValueError(f"SplinePath requires at least 2 control points, got {len(self.points)}")

        # Validate normalized coordinates
        for i, (x, y) in enumerate(self.points):
            if not (0.0 <= x <= 1.0):
                raise ValueError(f"SplinePath point {i} x-coordinate {x} out of range [0, 1]")
            if not (0.0 <= y <= 1.0):
                raise ValueError(f"SplinePath point {i} y-coordinate {y} out of range [0, 1]")

        if self.tolerance_mm <= 0:
            raise ValueError(f"SplinePath tolerance_mm must be positive, got {self.tolerance_mm}")


# Computed during resolution (not authored)
@dataclass(frozen=True)
class ResolvedRegion:
    """Computed region bounds - output of layout resolution.

    This is NOT part of the authored AST. It's attached during
    the resolve_layout() pass as internal metadata.

    Attributes:
        x_min: Left edge in sheet coordinates
        y_min: Bottom edge in sheet coordinates
        x_max: Right edge in sheet coordinates
        y_max: Top edge in sheet coordinates
    """
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2,
        )

    def inset(self, amount: float) -> ResolvedRegion:
        """Shrink region inward by amount on all sides."""
        return ResolvedRegion(
            x_min=self.x_min + amount,
            y_min=self.y_min + amount,
            x_max=self.x_max - amount,
            y_max=self.y_max - amount,
        )

    def subdivide_grid(self, rows: int, cols: int, gap: float) -> list[ResolvedRegion]:
        """Subdivide region into grid cells with gap spacing."""
        # Calculate cell dimensions
        total_gap_x = gap * (cols - 1) if cols > 1 else 0
        total_gap_y = gap * (rows - 1) if rows > 1 else 0

        cell_width = (self.width - total_gap_x) / cols
        cell_height = (self.height - total_gap_y) / rows

        cells = []
        for row in range(rows):
            for col in range(cols):
                x_offset = col * (cell_width + gap)
                y_offset = row * (cell_height + gap)

                cells.append(ResolvedRegion(
                    x_min=self.x_min + x_offset,
                    y_min=self.y_min + y_offset,
                    x_max=self.x_min + x_offset + cell_width,
                    y_max=self.y_min + y_offset + cell_height,
                ))

        return cells

    def subdivide_split(self, rows: int, cols: int, rail_mm: float, mullion_mm: float) -> list[ResolvedRegion]:
        """Subdivide region into panes with rail/mullion bars.

        Rails are horizontal bars (between rows), mullions are vertical bars (between cols).
        Pane sizes account for material reserved by the bars.

        When rail_mm=0 and mullion_mm=0, behaves identically to subdivide_grid(gap=0).

        Args:
            rows: Number of rows (panes stacked vertically)
            cols: Number of columns (panes side by side)
            rail_mm: Horizontal bar width (material reserved between rows)
            mullion_mm: Vertical bar width (material reserved between columns)

        Returns:
            List of pane regions (left-to-right, bottom-to-top)
        """
        # Calculate pane dimensions accounting for rail/mullion material
        total_mullion = mullion_mm * (cols - 1) if cols > 1 else 0
        total_rail = rail_mm * (rows - 1) if rows > 1 else 0

        pane_width = (self.width - total_mullion) / cols
        pane_height = (self.height - total_rail) / rows

        panes = []
        for row in range(rows):
            for col in range(cols):
                # Offset includes pane sizes + bar material
                x_offset = col * (pane_width + mullion_mm)
                y_offset = row * (pane_height + rail_mm)

                panes.append(ResolvedRegion(
                    x_min=self.x_min + x_offset,
                    y_min=self.y_min + y_offset,
                    x_max=self.x_min + x_offset + pane_width,
                    y_max=self.y_min + y_offset + pane_height,
                ))

        return panes


@dataclass(frozen=True)
class CompositionalLayoutAST:
    """Top-level compositional layout (before resolution).

    This extends LayoutAST with compositional nodes.
    After resolve_layout(), this lowers to flat LayoutAST.

    Attributes:
        sheet: Sheet stock specification
        components: Component definitions (library)
        root: Root layout node (Panel or Place)
        project: Optional project name
    """
    sheet: Any  # Sheet dataclass from layout.py
    components: dict[str, ComponentDef] = field(default_factory=dict)
    root: Any = None  # Panel or Place node
    project: str | None = None
