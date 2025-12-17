"""Layout resolution pass: hierarchical compositional AST → flat positioned shapes.

This pass:
1. Walks the compositional AST tree
2. Propagates "current region" context through the hierarchy
3. Applies inset, frame, grid layout managers
4. Expands components with parameter substitution
5. Replicates subtrees via cell and place
6. Outputs flat LayoutAST with absolute coordinates (compatible with existing pipeline)

Key invariants:
- Children fill their parent region by default
- Layout is order-independent (deterministic, no side effects)
- Regions are never authored, only computed
- Output is compatible with FlatPML / RemovalIntent lowering
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from skills.mill_ui.layout_ast.compositional import (
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
    ResolvedRegion,
    CompositionalLayoutAST,
)
from skills.mill_ui.layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
)


def sample_catmull_rom_spline(control_points: list[tuple[float, float]], tolerance_mm: float) -> list[tuple[float, float]]:
    """Sample Catmull-Rom spline into polyline points.

    Catmull-Rom splines produce smooth curves that pass through all control points.
    The curve is sampled at adaptive intervals to satisfy the tolerance parameter.

    This is a simplified implementation optimized for Studio Mode:
    - Uniform parametric sampling (not adaptive curvature-based)
    - Good enough for decorative/expressive work
    - Deterministic and predictable

    Args:
        control_points: List of (x, y) control points
        tolerance_mm: Target maximum deviation from true curve (lower = more samples)

    Returns:
        List of (x, y) sampled points forming a smooth polyline
    """
    if len(control_points) < 2:
        return list(control_points)

    # For 2 points, just return them (straight line)
    if len(control_points) == 2:
        return list(control_points)

    # Calculate segment count based on tolerance
    # Simple heuristic: more segments for tighter tolerance
    segments_per_span = max(10, int(5.0 / max(tolerance_mm, 0.01)))

    sampled_points = []

    # Catmull-Rom requires 4 points for each segment
    # For endpoints, duplicate first/last points
    extended = [control_points[0]] + control_points + [control_points[-1]]

    # Sample each span between adjacent control points
    for i in range(1, len(extended) - 2):
        p0, p1, p2, p3 = extended[i-1], extended[i], extended[i+1], extended[i+2]

        # Sample this span (from p1 to p2)
        for t_step in range(segments_per_span):
            t = t_step / float(segments_per_span)

            # Catmull-Rom basis functions
            t2 = t * t
            t3 = t2 * t

            # Catmull-Rom matrix coefficients
            q0 = -0.5*t3 + t2 - 0.5*t
            q1 = 1.5*t3 - 2.5*t2 + 1.0
            q2 = -1.5*t3 + 2.0*t2 + 0.5*t
            q3 = 0.5*t3 - 0.5*t2

            x = q0*p0[0] + q1*p1[0] + q2*p2[0] + q3*p3[0]
            y = q0*p0[1] + q1*p1[1] + q2*p2[1] + q3*p3[1]

            sampled_points.append((x, y))

    # Add final control point
    sampled_points.append(control_points[-1])

    return sampled_points


class LayoutResolver:
    """Resolves compositional layout to flat positioned shapes."""

    def __init__(self, ast: CompositionalLayoutAST):
        self.ast = ast
        self.components = ast.components  # Component library

    def _collect_island_bounds(
        self,
        children: tuple[Any, ...],
        region: ResolvedRegion,
        params: dict[str, Any],
    ) -> list[dict[str, float]]:
        """Collect island boundaries from Keepout children.

        Args:
            children: Child nodes to search for Keepouts
            region: Current region for resolving keepout shapes
            params: Component parameter bindings

        Returns:
            List of island bounds dicts with keys: x_min, x_max, y_min, y_max
        """
        islands = []

        for child in children:
            if isinstance(child, Keepout):
                # Resolve keepout children to determine island boundaries
                # Each shape within the keepout defines an island
                keepout_items = []
                for keepout_child in child.children:
                    self._resolve_node(keepout_child, region, keepout_items, params)

                # Extract bounds from resolved keepout items
                for item in keepout_items:
                    if item.kind == "shape" and item.geometry:
                        # Compute bounds from geometry + placement
                        cx, cy = item.placement.center_xy_mm
                        if item.type == "Rect":
                            w = item.geometry.data["w_mm"]
                            h = item.geometry.data["h_mm"]
                            islands.append({
                                "x_min": cx - w / 2,
                                "x_max": cx + w / 2,
                                "y_min": cy - h / 2,
                                "y_max": cy + h / 2,
                            })
                        elif item.type == "Circle":
                            r = item.geometry.data["diameter_mm"] / 2
                            islands.append({
                                "x_min": cx - r,
                                "x_max": cx + r,
                                "y_min": cy - r,
                                "y_max": cy + r,
                            })
                        elif item.type == "RoundedRect":
                            w = item.geometry.data["w_mm"]
                            h = item.geometry.data["h_mm"]
                            islands.append({
                                "x_min": cx - w / 2,
                                "x_max": cx + w / 2,
                                "y_min": cy - h / 2,
                                "y_max": cy + h / 2,
                            })

        return islands

    def _extract_edge_treatment(
        self,
        children: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        """Extract edge treatment from children (if present).

        Args:
            children: Child nodes to search for Edge

        Returns:
            Edge treatment dict or None if no Edge found
        """
        for child in children:
            if isinstance(child, Edge):
                # Found edge treatment - convert to dict for geometry data
                return {
                    "type": child.treatment_type,
                    "rough_allowance_mm": child.rough_allowance_mm,
                    "finish_allowance_mm": child.finish_allowance_mm,
                    "radius_mm": child.radius_mm,
                    "distance_mm": child.distance_mm,
                }
        return None

    def resolve(self) -> LayoutAST:
        """Resolve compositional AST to flat LayoutAST.

        Returns:
            Flat LayoutAST with absolute-positioned shapes
        """
        # Initial region is the full sheet
        sheet_region = ResolvedRegion(
            x_min=0,
            y_min=0,
            x_max=self.ast.sheet.width_mm,
            y_max=self.ast.sheet.height_mm,
        )

        # Resolve root node
        items = []
        self._resolve_node(self.ast.root, sheet_region, items, params={})

        return LayoutAST(
            sheet=self.ast.sheet,
            items=tuple(items),
            project=self.ast.project,
        )

    def _resolve_node(
        self,
        node: Any,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Recursively resolve a node within a region.

        Args:
            node: Compositional node to resolve
            region: Current region bounds
            items: Accumulated list of flat items (mutated)
            params: Component parameter bindings
        """
        if node is None:
            return

        # Panel: establish root region, resolve children
        if isinstance(node, Panel):
            for child in node.children:
                self._resolve_node(child, region, items, params)

        # Inset: shrink region, resolve children within
        elif isinstance(node, Inset):
            inset_region = region.inset(node.amount_mm)
            for child in node.children:
                self._resolve_node(child, inset_region, items, params)

        # Frame: create outer profile, resolve children in inner region
        elif isinstance(node, Frame):
            # Frame creates a profile at current region boundary
            # (For now, we'll emit a rect profile at region bounds)
            # Then shrink by frame width for children

            # Emit outer profile shape
            outer_rect = Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": region.width, "h_mm": region.height}),
                placement=Placement(center_xy_mm=region.center),
                feature=Feature(
                    type="profile",
                    depth=node.profile_depth,
                    side=node.profile_side,
                    depth_mm=None if node.profile_depth == "through" else float(node.profile_depth),
                ),
            )
            items.append(outer_rect)

            # Resolve children in inner region
            inner_region = region.inset(node.width_mm)
            for child in node.children:
                self._resolve_node(child, inner_region, items, params)

        # Grid: subdivide region, resolve children in each cell
        elif isinstance(node, Grid):
            cells = region.subdivide_grid(node.rows, node.cols, node.gap_mm)

            # Find Cell children (content to replicate)
            cell_content = [child for child in node.children if isinstance(child, Cell)]

            if not cell_content:
                # No explicit Cell node; treat all children as cell content
                cell_content = [Cell(children=node.children)]

            # Replicate cell content in each grid cell
            for cell_region in cells:
                for cell_node in cell_content:
                    # Apply cell inset if specified
                    content_region = cell_region.inset(cell_node.inset_mm) if cell_node.inset_mm > 0 else cell_region

                    # Resolve cell children in this grid cell's region
                    for child in cell_node.children:
                        self._resolve_node(child, content_region, items, params)

        # Split: subdivide region with rail/mullion bars, resolve children in each pane
        elif isinstance(node, Split):
            panes = region.subdivide_split(node.rows, node.cols, node.rail_mm, node.mullion_mm)

            # Find Cell children (content to replicate in each pane)
            cell_content = [child for child in node.children if isinstance(child, Cell)]

            if not cell_content:
                # No explicit Cell node; treat all children as cell content
                cell_content = [Cell(children=node.children)]

            # Replicate cell content in each pane
            for pane_region in panes:
                for cell_node in cell_content:
                    # Apply cell inset if specified
                    content_region = pane_region.inset(cell_node.inset_mm) if cell_node.inset_mm > 0 else pane_region

                    # Resolve cell children in this pane's region
                    for child in cell_node.children:
                        self._resolve_node(child, content_region, items, params)

        # Cell: should only appear as Grid/Split child (handled in Grid/Split cases)
        elif isinstance(node, Cell):
            # If encountered outside Grid/Split, treat as passthrough
            for child in node.children:
                self._resolve_node(child, region, items, params)

        # UseComponent: expand component with parameter substitution
        elif isinstance(node, UseComponent):
            if node.component_name not in self.components:
                raise ValueError(f"Unknown component: {node.component_name}")

            comp_def = self.components[node.component_name]

            # Merge component params (defaults) with instantiation args
            resolved_params = {**comp_def.params, **node.args}

            # Resolve component body with parameter bindings
            self._resolve_node(comp_def.body, region, items, resolved_params)

        # Place: sheet-level instance placement
        elif isinstance(node, Place):
            # Place's layout manager subdivides the region
            # Children are instantiated in each slot
            if isinstance(node.layout, Grid):
                # Treat Place+Grid as a grid that places children in cells
                cells = region.subdivide_grid(node.layout.rows, node.layout.cols, node.layout.gap_mm)

                # Place each child in sequence across cells
                # (Simple deterministic layout: fill grid left-to-right, top-to-bottom)
                for idx, child in enumerate(node.children):
                    if idx < len(cells):
                        self._resolve_node(child, cells[idx], items, params)
            else:
                # Unknown layout manager; passthrough
                for child in node.children:
                    self._resolve_node(child, region, items, params)

        # Rect: fill current region with a rectangle shape
        elif isinstance(node, Rect):
            # Collect island bounds from Keepout children
            islands = self._collect_island_bounds(node.children, region, params)

            # Extract edge treatment from Edge children
            edge_treatment = self._extract_edge_treatment(node.children)

            # Rect fills the current region
            geometry_data = {
                "w_mm": region.width,
                "h_mm": region.height,
            }

            # Add islands if present (for pocket features)
            if islands:
                geometry_data["islands"] = islands

            # Add edge treatment if present
            if edge_treatment:
                geometry_data["edge_treatment"] = edge_treatment

            rect_item = Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data=geometry_data),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,  # May be None or a Feature dataclass
                shape_id=node.id,
            )
            items.append(rect_item)

            # Resolve non-Keepout, non-Edge children within same region (for nested features)
            for child in node.children:
                if not isinstance(child, (Keepout, Edge)):
                    self._resolve_node(child, region, items, params)

        # Circle: create circular region
        elif isinstance(node, Circle):
            # Determine diameter: explicit or fit mode
            if node.diameter_mm is not None:
                diameter = node.diameter_mm
            else:
                # Fit mode: largest circle inscribed in region
                diameter = min(region.width, region.height)

            # Collect island bounds from Keepout children
            islands = self._collect_island_bounds(node.children, region, params)

            # Extract edge treatment from Edge children
            edge_treatment = self._extract_edge_treatment(node.children)

            geometry_data = {"diameter_mm": diameter}
            if islands:
                geometry_data["islands"] = islands
            if edge_treatment:
                geometry_data["edge_treatment"] = edge_treatment

            circle_item = Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data=geometry_data),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,
                shape_id=node.id,
            )
            items.append(circle_item)

            # Resolve non-Keepout, non-Edge children within circular region
            # For simplicity, children operate in bounding box region
            for child in node.children:
                if not isinstance(child, (Keepout, Edge)):
                    self._resolve_node(child, region, items, params)

        # RoundedRect: fill current region with rounded corners
        elif isinstance(node, RoundedRect):
            # Collect island bounds from Keepout children
            islands = self._collect_island_bounds(node.children, region, params)

            # Extract edge treatment from Edge children
            edge_treatment = self._extract_edge_treatment(node.children)

            geometry_data = {
                "w_mm": region.width,
                "h_mm": region.height,
                "radius_mm": node.radius_mm,
            }
            if islands:
                geometry_data["islands"] = islands
            if edge_treatment:
                geometry_data["edge_treatment"] = edge_treatment

            rounded_rect_item = Item(
                kind="shape",
                type="RoundedRect",
                geometry=Geometry(data=geometry_data),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,
                shape_id=node.id,
            )
            items.append(rounded_rect_item)

            # Resolve non-Keepout, non-Edge children within same region
            for child in node.children:
                if not isinstance(child, (Keepout, Edge)):
                    self._resolve_node(child, region, items, params)

        # Line: create open path for engraving
        elif isinstance(node, Line):
            # Determine line endpoints based on orientation
            if node.orientation == "horizontal":
                # Horizontal line across center of region
                start_xy = (region.x_min, region.center[1])
                end_xy = (region.x_max, region.center[1])
            elif node.orientation == "vertical":
                # Vertical line down center of region
                start_xy = (region.center[0], region.y_min)
                end_xy = (region.center[0], region.y_max)
            else:
                raise ValueError(f"Unknown line orientation: {node.orientation}")

            line_item = Item(
                kind="path",  # Open path, not closed shape
                type="Line",
                geometry=Geometry(data={
                    "start_xy_mm": start_xy,
                    "end_xy_mm": end_xy,
                }),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,
                shape_id=node.id,
            )
            items.append(line_item)

        # Polyline: map normalized points to absolute coordinates within region
        elif isinstance(node, Polyline):
            # Map normalized points (0..1) to absolute coordinates within region
            # (0, 0) = bottom-left (region.x_min, region.y_min)
            # (1, 1) = top-right (region.x_max, region.y_max)
            absolute_points = []
            for norm_x, norm_y in node.points:
                abs_x = region.x_min + norm_x * region.width
                abs_y = region.y_min + norm_y * region.height
                absolute_points.append((abs_x, abs_y))

            polyline_item = Item(
                kind="path",  # Open path for engraving
                type="Polyline",
                geometry=Geometry(data={
                    "points_mm": absolute_points,
                }),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,
                shape_id=node.id,
            )
            items.append(polyline_item)

        elif isinstance(node, SplinePath):
            # SplinePath: Sample spline to polyline, then convert to absolute coordinates
            # STUDIO MODE: Splines are always lowered to polylines immediately
            # This keeps CAM math simple and deterministic

            # Step 1: Sample spline in normalized space (0..1)
            normalized_samples = sample_catmull_rom_spline(list(node.points), node.tolerance_mm)

            # Step 2: Map sampled points to absolute coordinates within region
            absolute_points = []
            for norm_x, norm_y in normalized_samples:
                abs_x = region.x_min + norm_x * region.width
                abs_y = region.y_min + norm_y * region.height
                absolute_points.append((abs_x, abs_y))

            # Step 3: Create polyline item (spline is now indistinguishable from polyline)
            spline_item = Item(
                kind="path",  # Open path for engraving
                type="Polyline",  # Lowered to polyline (no spline primitives in CAM layer)
                geometry=Geometry(data={
                    "points_mm": absolute_points,
                    "spline_source": True,  # Metadata: originated from spline
                    "spline_tolerance_mm": node.tolerance_mm,
                }),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,
                shape_id=node.id,
            )
            items.append(spline_item)

        # Keepout: handled as children of shapes (Rect/Circle/RoundedRect)
        # If encountered standalone, it's a no-op (should be caught during parse/validation)
        elif isinstance(node, Keepout):
            # Keepout should only appear as child of a shape with pocket feature
            # If encountered here, silently skip (validation happens at parse time)
            pass

        # Legacy Item nodes (from flat LayoutAST): preserve as-is
        elif isinstance(node, Item):
            items.append(node)

        # Unknown node type: skip
        else:
            pass


def resolve_layout(ast: CompositionalLayoutAST) -> LayoutAST:
    """Resolve compositional layout to flat LayoutAST.

    Args:
        ast: Compositional layout with region-relative nodes

    Returns:
        Flat LayoutAST with absolute-positioned shapes
    """
    resolver = LayoutResolver(ast)
    return resolver.resolve()
