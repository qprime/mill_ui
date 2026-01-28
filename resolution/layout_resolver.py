
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

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
    ResolvedRegion,
    CompositionalLayoutAST,
    # Generator AST nodes (Stage 12)
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
    # Stage 14 additions
    SplitHorizontalGaps,
    AtPosition,
    Subtract,
    Arch,
    # Stage 15 additions (polygon/triangle)
    Polygon,
    Triangle,
    # Stage 16 additions (x_panel generator)
    XPanelGen,
    # Stage 18 additions (hole_grid generator)
    HoleGridGen,
    # Stage 20 additions (measurement_grid generator)
    MeasurementGridGen,
    # Stage 21 additions (measurement_edge generator)
    MeasurementEdgeGen,
    # Stage 22 additions (engrave_text generator)
    EngraveTextGen,
    # Waste cuts directive
    WasteCuts,
    # Assembly
    Assembly,
)
from layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
)
from core.constants import DepthMode
from core.geometry import compute_shape_bounds_dict

# Import generators and Domain for Stage 12 integration
from domains import Domain
from generators.area.raised_panel import raised_panel_generator
from generators.area.wave import wave_generator
from generators.area.line_pattern import line_pattern_generator
from generators.area.concentric_border import concentric_border_generator
from generators.area.x_panel import x_panel_generator
from generators.area.hole_grid import hole_grid_generator
from generators.area.measurement_grid import measurement_grid_generator
from generators.loop.measurement_edge import measurement_edge_generator
from generators.area.engrave_text import engrave_text_at_position
from generators.base import RaisedPanelParams, WaveParams, LinePatternParams, ConcentricBorderParams, XPanelParams, HoleGridParams, MeasurementGridParams, MeasurementEdgeParams
from assembly import (
    AssemblyParams,
    AssemblyTopology,
    ButtJoineryStrategy,
    FingerJoineryStrategy,
    box_topology,
    pyramid_topology,
    generate_assembly_panels,
)
from generators.panels import JointedPanelParams, jointed_panel_generator


# Type alias for node handlers
NodeHandler = Callable[["LayoutResolver", Any, ResolvedRegion, list[Item], dict[str, Any]], None]


def _feature_from_profile_gen(node: ProfileGen) -> Feature:
    depth_value = node.depth
    depth_mm = None if depth_value == "through" else float(depth_value)
    return Feature(
        type="profile",
        depth=str(depth_value),
        side=node.side,
        depth_mm=depth_mm,
        tab_count=node.tab_count,
        tab_height_mm=node.tab_height_mm,
        tab_width_mm=node.tab_width_mm,
    )


def sample_catmull_rom_spline(control_points: list[tuple[float, float]], tolerance_mm: float) -> list[tuple[float, float]]:
    if len(control_points) < 2:
        return list(control_points)


    if len(control_points) == 2:
        return list(control_points)


    segments_per_span = max(10, int(5.0 / max(tolerance_mm, 0.01)))

    sampled_points = []


    extended = [control_points[0]] + control_points + [control_points[-1]]


    for i in range(1, len(extended) - 2):
        p0, p1, p2, p3 = extended[i-1], extended[i], extended[i+1], extended[i+2]


        for t_step in range(segments_per_span):
            t = t_step / float(segments_per_span)


            t2 = t * t
            t3 = t2 * t


            q0 = -0.5*t3 + t2 - 0.5*t
            q1 = 1.5*t3 - 2.5*t2 + 1.0
            q2 = -1.5*t3 + 2.0*t2 + 0.5*t
            q3 = 0.5*t3 - 0.5*t2

            x = q0*p0[0] + q1*p1[0] + q2*p2[0] + q3*p3[0]
            y = q0*p0[1] + q1*p1[1] + q2*p2[1] + q3*p3[1]

            sampled_points.append((x, y))


    sampled_points.append(control_points[-1])

    return sampled_points


class ResolutionAssertionError(Exception):
    """Raised when a geometry assertion fails during resolution."""
    pass


class LayoutResolver:

    def __init__(self, ast: CompositionalLayoutAST, validate: bool = False):
        self.ast = ast
        self.components = ast.components
        self._shape_counter = 0
        self._validate = validate

    def _assert_shape_context(
        self,
        parent_type: str,
        child_item: Item,
        context_desc: str,
    ) -> None:
        """Assert that child item preserves parent shape type when expected."""
        if not self._validate:
            return

        if child_item.feature and child_item.feature.type == "profile":
            if child_item.type != parent_type:
                raise ResolutionAssertionError(
                    f"Shape context mismatch in {context_desc}: "
                    f"parent is {parent_type} but profile item is {child_item.type}"
                )

    def _assert_geometry_preserved(
        self,
        parent_geometry: dict[str, Any],
        child_geometry: dict[str, Any],
        keys: list[str],
        context_desc: str,
    ) -> None:
        """Assert that specific geometry keys are preserved from parent to child."""
        if not self._validate:
            return

        for key in keys:
            if key in parent_geometry:
                parent_val = parent_geometry[key]
                child_val = child_geometry.get(key)
                if child_val != parent_val:
                    raise ResolutionAssertionError(
                        f"Geometry mismatch in {context_desc}: "
                        f"{key} was {parent_val} in parent but {child_val} in child"
                    )

    def _next_shape_id(self, prefix: str) -> str:
        """Generate a deterministic shape ID using a counter."""
        shape_id = f"{prefix}_{self._shape_counter}"
        self._shape_counter += 1
        return shape_id

    def _collect_island_bounds(
        self,
        children: tuple[Any, ...],
        region: ResolvedRegion,
        params: dict[str, Any],
    ) -> list[dict[str, float]]:
        islands = []

        for child in children:
            if isinstance(child, Keepout):


                keepout_items = []
                for keepout_child in child.children:
                    self._resolve_node(keepout_child, region, keepout_items, params)


                for item in keepout_items:
                    if item.kind == "shape" and item.geometry:
                        # Use unified bounds calculation
                        bounds_dict = compute_shape_bounds_dict(
                            item.type,
                            item.geometry.data,
                            item.placement.center_xy_mm,
                        )
                        islands.append(bounds_dict)

        return islands

    def _extract_edge_treatment(
        self,
        children: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        for child in children:
            if isinstance(child, Edge):

                return {
                    "type": child.treatment_type,
                    "rough_allowance_mm": child.rough_allowance_mm,
                    "finish_allowance_mm": child.finish_allowance_mm,
                    "radius_mm": child.radius_mm,
                    "distance_mm": child.distance_mm,
                }
        return None

    # =========================================================================
    # Node Handlers - Each handles one node type from the AST
    # =========================================================================

    def _handle_panel(
        self,
        node: Panel,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        for child in node.children:
            self._resolve_node(child, region, items, params)

    def _handle_inset(
        self,
        node: Inset,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        inset_region = region.inset(node.amount_mm)
        for child in node.children:
            self._resolve_node(child, inset_region, items, params)

    def _handle_frame(
        self,
        node: Frame,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        inner_region = region.inset(node.width_mm)
        for child in node.children:
            self._resolve_node(child, inner_region, items, params)

    def _handle_grid(
        self,
        node: Grid,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        cells = region.subdivide_grid(node.rows, node.cols, node.gap_mm)

        cell_content = [child for child in node.children if isinstance(child, Cell)]

        if not cell_content:
            cell_content = [Cell(children=node.children)]

        for cell_region in cells:
            for cell_node in cell_content:
                content_region = cell_region.inset(cell_node.inset_mm) if cell_node.inset_mm > 0 else cell_region

                for child in cell_node.children:
                    self._resolve_node(child, content_region, items, params)

    def _handle_split(
        self,
        node: Split,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        panes = region.subdivide_split(node.rows, node.cols, node.rail_mm, node.mullion_mm)

        cell_content = [child for child in node.children if isinstance(child, Cell)]

        if not cell_content:
            cell_content = [Cell(children=node.children)]

        for pane_region in panes:
            for cell_node in cell_content:
                content_region = pane_region.inset(cell_node.inset_mm) if cell_node.inset_mm > 0 else pane_region

                for child in cell_node.children:
                    self._resolve_node(child, content_region, items, params)

    def _handle_cell(
        self,
        node: Cell,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        for child in node.children:
            self._resolve_node(child, region, items, params)

    def _handle_use_component(
        self,
        node: UseComponent,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        if node.component_name not in self.components:
            raise ValueError(f"Unknown component: {node.component_name}")

        comp_def = self.components[node.component_name]

        resolved_params = {**comp_def.params, **node.args}

        self._resolve_node(comp_def.body, region, items, resolved_params)

    def _handle_place(
        self,
        node: Place,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        if isinstance(node.layout, Grid):
            cells = region.subdivide_grid(node.layout.rows, node.layout.cols, node.layout.gap_mm)

            for idx, child in enumerate(node.children):
                if idx < len(cells):
                    self._resolve_node(child, cells[idx], items, params)
        else:
            for child in node.children:
                self._resolve_node(child, region, items, params)

    def _handle_rect(
        self,
        node: Rect,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        islands = self._collect_island_bounds(node.children, region, params)

        edge_treatment = self._extract_edge_treatment(node.children)

        geometry_data = {
            "w_mm": region.width,
            "h_mm": region.height,
        }

        if islands:
            geometry_data["islands"] = islands

        if edge_treatment:
            geometry_data["edge_treatment"] = edge_treatment

        rect_item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=region.center),
            feature=node.feature,
            shape_id=node.id,
        )
        items.append(rect_item)

        child_params = {**params}
        if edge_treatment:
            child_params["edge_treatment"] = edge_treatment

        for child in node.children:
            if not isinstance(child, (Keepout, Edge)):
                self._resolve_node(child, region, items, child_params)

    def _handle_circle(
        self,
        node: Circle,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        if node.diameter_mm is not None:
            geometry_data = {"diameter_mm": node.diameter_mm}
        elif node.radius_mm is not None:
            geometry_data = {"radius_mm": node.radius_mm}
        else:
            diameter = min(region.width, region.height)
            geometry_data = {"diameter_mm": diameter}

        islands = self._collect_island_bounds(node.children, region, params)

        edge_treatment = self._extract_edge_treatment(node.children)

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

        for child in node.children:
            if not isinstance(child, (Keepout, Edge)):
                self._resolve_node(child, region, items, params)

    def _handle_rounded_rect(
        self,
        node: RoundedRect,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        islands = self._collect_island_bounds(node.children, region, params)

        edge_treatment = self._extract_edge_treatment(node.children)

        all_corners = {'tl', 'tr', 'bl', 'br'}
        if node.corners is not None:
            radius_tl = node.radius_mm if 'tl' in node.corners else 0.0
            radius_tr = node.radius_mm if 'tr' in node.corners else 0.0
            radius_bl = node.radius_mm if 'bl' in node.corners else 0.0
            radius_br = node.radius_mm if 'br' in node.corners else 0.0
        else:
            radius_tl = radius_tr = radius_bl = radius_br = node.radius_mm

        geometry_data = {
            "w_mm": region.width,
            "h_mm": region.height,
            "radius_tl_mm": radius_tl,
            "radius_tr_mm": radius_tr,
            "radius_bl_mm": radius_bl,
            "radius_br_mm": radius_br,
        }
        if radius_tl == radius_tr == radius_bl == radius_br:
            geometry_data["radius_mm"] = radius_tl
            geometry_data["corner_radius_mm"] = radius_tl
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

        items_before = len(items)
        child_params = {**params, "shape_context": {"type": "RoundedRect", "geometry_data": geometry_data}}
        for child in node.children:
            if not isinstance(child, (Keepout, Edge)):
                self._resolve_node(child, region, items, child_params)

        for child_item in items[items_before:]:
            self._assert_shape_context("RoundedRect", child_item, f"RoundedRect({node.id})")
            if child_item.type == "RoundedRect" and child_item.feature:
                self._assert_geometry_preserved(
                    geometry_data,
                    child_item.geometry.data,
                    ["radius_tl_mm", "radius_tr_mm", "radius_bl_mm", "radius_br_mm"],
                    f"RoundedRect({node.id}) -> {child_item.feature.type}",
                )

    def _handle_line(
        self,
        node: Line,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        if node.orientation == "horizontal":
            start_xy = (region.x_min, region.center[1])
            end_xy = (region.x_max, region.center[1])
        elif node.orientation == "vertical":
            start_xy = (region.center[0], region.y_min)
            end_xy = (region.center[0], region.y_max)
        else:
            raise ValueError(f"Unknown line orientation: {node.orientation}")

        cx = (start_xy[0] + end_xy[0]) / 2
        cy = (start_xy[1] + end_xy[1]) / 2

        line_item = Item(
            kind="shape",
            type="Line",
            geometry=Geometry(data={
                "start": [start_xy[0] - cx, start_xy[1] - cy],
                "end": [end_xy[0] - cx, end_xy[1] - cy],
            }),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=node.feature,
            shape_id=node.id,
        )
        items.append(line_item)

    def _handle_polyline(
        self,
        node: Polyline,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        absolute_points = []
        for norm_x, norm_y in node.points:
            abs_x = region.x_min + norm_x * region.width
            abs_y = region.y_min + norm_y * region.height
            absolute_points.append((abs_x, abs_y))

        xs = [p[0] for p in absolute_points]
        ys = [p[1] for p in absolute_points]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2

        relative_points = [[p[0] - cx, p[1] - cy] for p in absolute_points]

        polyline_item = Item(
            kind="shape",
            type="Polyline",
            geometry=Geometry(data={
                "points": relative_points,
            }),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=node.feature,
            shape_id=node.id,
        )
        items.append(polyline_item)

    def _handle_spline_path(
        self,
        node: SplinePath,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        normalized_samples = sample_catmull_rom_spline(list(node.points), node.tolerance_mm)

        absolute_points = []
        for norm_x, norm_y in normalized_samples:
            abs_x = region.x_min + norm_x * region.width
            abs_y = region.y_min + norm_y * region.height
            absolute_points.append((abs_x, abs_y))

        xs = [p[0] for p in absolute_points]
        ys = [p[1] for p in absolute_points]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2

        relative_points = [[p[0] - cx, p[1] - cy] for p in absolute_points]

        spline_item = Item(
            kind="shape",
            type="Polyline",
            geometry=Geometry(data={
                "points": relative_points,
                "spline_source": True,
                "spline_tolerance_mm": node.tolerance_mm,
            }),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=node.feature,
            shape_id=node.id,
        )
        items.append(spline_item)

    def _handle_keepout(
        self,
        node: Keepout,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        # Keepout nodes are processed by _collect_island_bounds, not here
        pass

    def _handle_item(
        self,
        node: Item,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        items.append(node)

    # =========================================================================
    # Generator Handlers (Stage 12: PML Generator Syntax)
    # =========================================================================
    #
    # KNOWN LIMITATION: Generator handlers emit Rect geometry and operate on
    # axis-aligned ResolvedRegion. Generators nested under circle/rounded_rect
    # shapes will NOT be clipped to the parent shape boundary. The parent
    # shape's profile cut handles the actual boundary in the final output.
    # This is by design - the compositional system uses rectangular regions
    # for layout calculations, and non-rectangular clipping would require
    # passing shape context through the resolution process.
    # =========================================================================

    def _handle_profile_gen(
        self,
        node: ProfileGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        shape_context = params.get("shape_context")
        if shape_context:
            shape_type = shape_context["type"]
            geometry_data = {**shape_context["geometry_data"]}
            geometry_data["w_mm"] = region.width
            geometry_data["h_mm"] = region.height
        else:
            shape_type = "Rect"
            geometry_data = {"w_mm": region.width, "h_mm": region.height}

        edge_treatment = params.get("edge_treatment")
        if edge_treatment:
            geometry_data["edge_treatment"] = edge_treatment

        profile_item = Item(
            kind="shape",
            type=shape_type,
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=region.center),
            feature=_feature_from_profile_gen(node),
            shape_id=self._next_shape_id("generated_profile"),
        )
        items.append(profile_item)

    def _handle_pocket_gen(
        self,
        node: PocketGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle PocketGen: Generate flat pocket item for region."""
        geometry_data = {"w_mm": region.width, "h_mm": region.height}

        edge_treatment = params.get("edge_treatment")
        if edge_treatment:
            geometry_data["edge_treatment"] = edge_treatment

        pocket_item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=region.center),
            feature=Feature(
                type="pocket",
                depth=str(node.depth_mm),
                depth_mm=node.depth_mm,
            ),
            shape_id=self._next_shape_id("generated_pocket"),
        )
        items.append(pocket_item)

    def _handle_raised_panel_gen(
        self,
        node: RaisedPanelGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle RaisedPanelGen: Generate raised panel items for region.

        Creates proper bevel and field items using the raised_panel_generator,
        which emits correct 'bevel' feature type for the border and 'pocket'
        for the field, preserving the angled border intent for CAM processing.
        """
        # Create a Domain from the ResolvedRegion
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        # Create parameters for the generator
        generator_params = RaisedPanelParams(
            border_width_mm=node.border_width_mm,
            border_depth_mm=node.border_depth_mm,
            field_depth_mm=node.field_depth_mm,
        )

        # Call the actual generator - it will produce proper bevel/pocket items
        shape_id_prefix = self._next_shape_id("raised_panel")
        try:
            generated_items = raised_panel_generator(
                domain,
                generator_params,
                allow_empty=True,  # Handle too-small regions gracefully
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            # Region too small for raised panel - skip silently
            pass

    def _handle_chamfer_gen(
        self,
        node: ChamferGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle ChamferGen: Generate chamfer item for region boundary.

        The chamfer is represented with proper chamfer metadata on the Feature,
        which ast_to_removal.py uses to compute the chamfer angle and create
        appropriate RemovalIntent metadata for CAM processing.
        """
        import math
        # Calculate chamfer angle from width and depth
        chamfer_angle = math.degrees(math.atan2(node.depth_mm, node.width_mm))

        chamfer_item = Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={
                "w_mm": region.width,
                "h_mm": region.height,
            }),
            placement=Placement(center_xy_mm=region.center),
            feature=Feature(
                type="chamfer",
                depth=str(node.depth_mm),
                depth_mm=node.depth_mm,
                chamfer_width_mm=node.width_mm,
                chamfer_angle_deg=chamfer_angle,
            ),
            shape_id=self._next_shape_id("generated_chamfer"),
        )
        items.append(chamfer_item)

    def _handle_x_panel_gen(
        self,
        node: XPanelGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle XPanelGen: Generate X-panel items for region.

        Creates 4 triangular pockets forming an X pattern using the
        x_panel_generator, which computes the correct geometry based
        on bar width and region dimensions.
        """
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = XPanelParams(
            bar_width_mm=node.bar_width_mm,
            depth_mm=node.depth_mm,
        )

        shape_id_prefix = self._next_shape_id("x_panel")
        try:
            generated_items = x_panel_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_hole_grid_gen(
        self,
        node: HoleGridGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle HoleGridGen: Generate hole grid items for region.

        Creates a grid of circular holes using the hole_grid_generator,
        which places holes at regular intervals within the domain boundary.
        """
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = HoleGridParams(
            spacing_mm=node.spacing_mm,
            diameter_mm=node.diameter_mm,
            depth_mm=node.depth,
            pattern=node.pattern,
            inset_mm=node.inset_mm,
            align=node.align,
        )

        shape_id_prefix = self._next_shape_id("hole")
        try:
            generated_items = hole_grid_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_waste_cuts(
        self,
        node: WasteCuts,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        from nesting.waste_decomposition import compute_waste_rectangles, PartBounds, WasteStrategy

        sheet_width = self.ast.sheet.width_mm
        sheet_height = self.ast.sheet.height_mm

        if node.margin_mm is not None:
            margin = node.margin_mm
        else:
            margin = self.ast.sheet.margin_mm

        part_bounds = []
        for item in items:
            if item.kind == "shape" and item.geometry:
                bounds = compute_shape_bounds_dict(
                    item.type,
                    item.geometry.data,
                    item.placement.center_xy_mm,
                )
                part_bounds.append(PartBounds(
                    x=bounds["x_min"],
                    y=bounds["y_min"],
                    width=bounds["x_max"] - bounds["x_min"],
                    height=bounds["y_max"] - bounds["y_min"],
                ))

        strategy = WasteStrategy.LARGEST if node.strategy == "largest" else WasteStrategy.SIMPLE

        waste_rects = compute_waste_rectangles(
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            margin=margin,
            parts=part_bounds,
            min_width=node.min_width_mm,
            min_height=node.min_height_mm,
            strategy=strategy,
        )

        for i, wrect in enumerate(waste_rects):
            waste_item = Item(
                kind="shape",
                type="Rectangle",
                geometry=Geometry(data={
                    "width": wrect.width,
                    "height": wrect.height,
                }),
                placement=Placement(center_xy_mm=(wrect.center_x, wrect.center_y)),
                feature=Feature(
                    type="profile",
                    depth="through",
                    side="outside",
                    depth_mm=None,
                    tab_count=node.tab_count,
                    tab_height_mm=node.tab_height_mm,
                ),
                shape_id=self._next_shape_id(f"waste_{i}"),
            )
            items.append(waste_item)

    def _handle_wave_gen(
        self,
        node: WaveGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle WaveGen: Generate wave pattern items for region.

        Calls the wave_generator to produce actual engrave polylines,
        which correctly map to the engraves bucket in hint export.
        """
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = WaveParams(
            amplitude_mm=node.amplitude_mm,
            wavelength_mm=node.wavelength_mm,
            depth_mm=node.depth_mm,
            tool_width_mm=node.groove_width_mm,
            wave_count=node.wave_count,
        )

        shape_id_prefix = self._next_shape_id("wave")
        try:
            generated_items = wave_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_lines_gen(
        self,
        node: LinesGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle LinesGen: Generate line pattern items for region.

        Calls the line_pattern_generator to produce parallel groove lines
        at the specified angle.
        """
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = LinePatternParams(
            angle_deg=node.angle_deg,
            spacing_mm=node.spacing_mm,
            line_width_mm=node.line_width_mm,
            depth_mm=node.depth_mm,
        )

        shape_id_prefix = self._next_shape_id("lines")
        try:
            generated_items = line_pattern_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_concentric_border_gen(
        self,
        node: ConcentricBorderGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle ConcentricBorderGen: Generate concentric border items for region.

        Calls the concentric_border_generator to produce nested ring grooves
        at the specified inset distances.
        """
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = ConcentricBorderParams(
            insets_mm=node.insets_mm,
            groove_width_mm=node.groove_width_mm,
            depth_mm=node.depth_mm,
        )

        shape_id_prefix = self._next_shape_id("border")
        try:
            generated_items = concentric_border_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_measurement_grid_gen(
        self,
        node: MeasurementGridGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle MeasurementGridGen: Generate ruler-style tick marks for region."""
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = MeasurementGridParams(
            unit=node.unit,
            minor_spacing_mm=node.minor_spacing_mm,
            major_spacing_mm=node.major_spacing_mm,
            minor_length_mm=node.minor_length_mm,
            major_length_mm=node.major_length_mm,
            depth_mm=node.depth_mm,
            minor_ticks=node.minor_ticks,
            labels=node.labels,
            label_height_mm=node.label_height_mm,
            label_offset_mm=node.label_offset_mm,
            label_interval=node.label_interval,
            label_start=node.label_start,
        )

        shape_id_prefix = self._next_shape_id("measurement_grid")
        try:
            generated_items = measurement_grid_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_measurement_edge_gen(
        self,
        node: MeasurementEdgeGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle MeasurementEdgeGen: Generate ruler tick marks along specified edges."""
        domain = Domain.from_rectangle(
            width_mm=region.width,
            height_mm=region.height,
            center=region.center,
        )

        generator_params = MeasurementEdgeParams(
            edges=node.edges,
            unit=node.unit,
            minor_spacing_mm=node.minor_spacing_mm,
            major_spacing_mm=node.major_spacing_mm,
            minor_length_mm=node.minor_length_mm,
            major_length_mm=node.major_length_mm,
            depth_mm=node.depth_mm,
            minor_ticks=node.minor_ticks,
            labels=node.labels,
            label_height_mm=node.label_height_mm,
            label_offset_mm=node.label_offset_mm,
            label_interval=node.label_interval,
            label_start=node.label_start,
        )

        shape_id_prefix = self._next_shape_id("measurement_edge")
        try:
            generated_items = measurement_edge_generator(
                domain,
                generator_params,
                allow_empty=True,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_engrave_text_gen(
        self,
        node: EngraveTextGen,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle EngraveTextGen: Generate engraved text at region center."""
        shape_id_prefix = self._next_shape_id("engrave_text")
        try:
            generated_items = engrave_text_at_position(
                text=node.text,
                position=region.center,
                height_mm=node.height_mm,
                depth_mm=node.depth_mm,
                font=node.font,
                alignment=node.alignment,
                orientation=node.orientation,
                shape_id_prefix=shape_id_prefix,
            )
            items.extend(generated_items)
        except ValueError:
            pass

    def _handle_split_horizontal(
        self,
        node: SplitHorizontal,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle SplitHorizontal: Split region into n rows and apply children to each."""
        n = node.n
        gap_mm = node.gap_mm

        # Validate inputs
        if n < 1:
            raise ValueError(f"split_horizontal: n must be at least 1, got {n}")
        if gap_mm < 0:
            raise ValueError(f"split_horizontal: gap cannot be negative, got {gap_mm}mm")

        # Calculate cell height
        total_gap = gap_mm * (n - 1)
        available_height = region.height - total_gap
        if available_height <= 0:
            raise ValueError(
                f"split_horizontal: gap {gap_mm}mm × {n-1} = {total_gap}mm exceeds "
                f"region height {region.height}mm"
            )
        cell_height = available_height / n

        # Create sub-regions from bottom to top
        num_children = len(node.children)
        for i in range(n):
            y_min = region.y_min + i * (cell_height + gap_mm)
            y_max = y_min + cell_height
            cell_region = ResolvedRegion(
                x_min=region.x_min,
                y_min=y_min,
                x_max=region.x_max,
                y_max=y_max,
            )

            if num_children == n:
                self._resolve_node(node.children[i], cell_region, items, params)
            else:
                for child in node.children:
                    self._resolve_node(child, cell_region, items, params)

    def _handle_split_vertical(
        self,
        node: SplitVertical,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle SplitVertical: Split region into n columns and apply children to each."""
        n = node.n
        gap_mm = node.gap_mm

        # Validate inputs
        if n < 1:
            raise ValueError(f"split_vertical: n must be at least 1, got {n}")
        if gap_mm < 0:
            raise ValueError(f"split_vertical: gap cannot be negative, got {gap_mm}mm")

        # Calculate cell width
        total_gap = gap_mm * (n - 1)
        available_width = region.width - total_gap
        if available_width <= 0:
            raise ValueError(
                f"split_vertical: gap {gap_mm}mm × {n-1} = {total_gap}mm exceeds "
                f"region width {region.width}mm"
            )
        cell_width = available_width / n

        # Create sub-regions from left to right
        num_children = len(node.children)
        for i in range(n):
            x_min = region.x_min + i * (cell_width + gap_mm)
            x_max = x_min + cell_width
            cell_region = ResolvedRegion(
                x_min=x_min,
                y_min=region.y_min,
                x_max=x_max,
                y_max=region.y_max,
            )

            if num_children == n:
                self._resolve_node(node.children[i], cell_region, items, params)
            else:
                for child in node.children:
                    self._resolve_node(child, cell_region, items, params)

    def _handle_split_grid(
        self,
        node: SplitGrid,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle SplitGrid: Split region into rows x cols grid and apply children to each."""
        rows = node.rows
        cols = node.cols
        gap_mm = node.gap_mm

        # Validate inputs
        if rows < 1:
            raise ValueError(f"split_grid: rows must be at least 1, got {rows}")
        if cols < 1:
            raise ValueError(f"split_grid: cols must be at least 1, got {cols}")
        if gap_mm < 0:
            raise ValueError(f"split_grid: gap cannot be negative, got {gap_mm}mm")

        # Calculate cell dimensions
        total_h_gap = gap_mm * (cols - 1)
        total_v_gap = gap_mm * (rows - 1)
        available_width = region.width - total_h_gap
        available_height = region.height - total_v_gap

        if available_width <= 0:
            raise ValueError(
                f"split_grid: horizontal gap {gap_mm}mm × {cols-1} = {total_h_gap}mm exceeds "
                f"region width {region.width}mm"
            )
        if available_height <= 0:
            raise ValueError(
                f"split_grid: vertical gap {gap_mm}mm × {rows-1} = {total_v_gap}mm exceeds "
                f"region height {region.height}mm"
            )

        cell_width = available_width / cols
        cell_height = available_height / rows

        # Create sub-regions (row-major from bottom-left)
        for row in range(rows):
            for col in range(cols):
                x_min = region.x_min + col * (cell_width + gap_mm)
                y_min = region.y_min + row * (cell_height + gap_mm)
                cell_region = ResolvedRegion(
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_min + cell_width,
                    y_max=y_min + cell_height,
                )

                # Apply children to this cell
                for child in node.children:
                    self._resolve_node(child, cell_region, items, params)

    # =========================================================================
    # Stage 14 Handlers: Additional PML features for remaining recipes
    # =========================================================================

    def _handle_split_horizontal_gaps(
        self,
        node: SplitHorizontalGaps,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle SplitHorizontalGaps: Apply children to gap regions between n+1 slats."""
        n = node.n
        gap_mm = node.gap_mm

        if n < 1:
            raise ValueError(f"split_horizontal_gaps: n must be at least 1, got {n}")
        if gap_mm <= 0:
            raise ValueError(f"split_horizontal_gaps: gap must be positive, got {gap_mm}mm")

        total_gap_space = n * gap_mm
        if total_gap_space >= region.height:
            raise ValueError(
                f"split_horizontal_gaps: {n} gaps × {gap_mm}mm = {total_gap_space}mm "
                f"exceeds region height {region.height}mm"
            )

        remaining_height = region.height - total_gap_space
        slat_height = remaining_height / (n + 1)

        for i in range(n):
            gap_y_min = region.y_min + (i + 1) * slat_height + i * gap_mm
            gap_y_max = gap_y_min + gap_mm

            gap_region = ResolvedRegion(
                x_min=region.x_min,
                y_min=gap_y_min,
                x_max=region.x_max,
                y_max=gap_y_max,
            )

            for child in node.children:
                self._resolve_node(child, gap_region, items, params)

    def _handle_at_position(
        self,
        node: AtPosition,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle AtPosition: Position child at explicit coordinates with explicit size."""
        if node.child is None:
            return

        width = node.width_mm if node.width_mm is not None else region.width
        height = node.height_mm if node.height_mm is not None else region.height

        child_region = ResolvedRegion(
            x_min=node.x_mm - width / 2,
            y_min=node.y_mm - height / 2,
            x_max=node.x_mm + width / 2,
            y_max=node.y_mm + height / 2,
        )

        self._resolve_node(node.child, child_region, items, params)

    def _handle_subtract(
        self,
        node: Subtract,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle Subtract: Create ring domain by subtracting inner from outer.

        Uses the Domain.subtract() operation to create a proper ring,
        then applies children to the resulting polygon domain.
        """
        inner_inset = node.inner_inset_mm

        outer = Domain.from_rectangle(region.width, region.height, center=region.center)
        inner = outer.inset(inner_inset).domains[0]
        ring_domains = outer.subtract(inner)

        for ring_domain in ring_domains:
            ring_bounds = ring_domain.bounds
            ring_region = ResolvedRegion(
                x_min=ring_bounds.x_min,
                y_min=ring_bounds.y_min,
                x_max=ring_bounds.x_max,
                y_max=ring_bounds.y_max,
            )

            cx, cy = ring_region.center
            polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in ring_domain.outer_boundary]
            holes = [[[pt[0] - cx, pt[1] - cy] for pt in hole] for hole in ring_domain.inner_boundaries]

            for child in node.children:
                if isinstance(child, PocketGen):
                    pocket_item = Item(
                        kind="shape",
                        type="Polygon",
                        geometry=Geometry(data={"points": polygon_points, "holes": holes}),
                        placement=Placement(center_xy_mm=(cx, cy)),
                        feature=Feature(
                            type="pocket",
                            depth=str(child.depth_mm),
                            depth_mm=child.depth_mm,
                        ),
                        shape_id=self._next_shape_id("subtract_pocket"),
                    )
                    items.append(pocket_item)
                elif isinstance(child, ChamferGen):
                    import math
                    chamfer_angle = math.degrees(math.atan2(child.depth_mm, child.width_mm))
                    chamfer_item = Item(
                        kind="shape",
                        type="Polygon",
                        geometry=Geometry(data={"points": polygon_points, "holes": holes}),
                        placement=Placement(center_xy_mm=(cx, cy)),
                        feature=Feature(
                            type="chamfer",
                            depth=str(child.depth_mm),
                            depth_mm=child.depth_mm,
                            chamfer_width_mm=child.width_mm,
                            chamfer_angle_deg=chamfer_angle,
                        ),
                        shape_id=self._next_shape_id("subtract_chamfer"),
                    )
                    items.append(chamfer_item)
                else:
                    self._resolve_node(child, ring_region, items, params)

    def _handle_arch(
        self,
        node: Arch,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle Arch: Create arch shape using Domain.from_arch().

        Creates the arch polygon geometry and processes children
        within the arch's bounding region.
        """
        arch_domain = Domain.from_arch(node.width_mm, node.height_mm, node.radius_mm)

        arch_region = ResolvedRegion(
            x_min=0,
            y_min=0,
            x_max=node.width_mm,
            y_max=node.height_mm,
        )

        cx, cy = arch_region.center
        relative_points = [[pt[0] - cx, pt[1] - cy] for pt in arch_domain.outer_boundary]

        if node.feature is not None:
            arch_item = Item(
                kind="shape",
                type="Polygon",
                geometry=Geometry(data={"points": relative_points, "holes": []}),
                placement=Placement(center_xy_mm=arch_region.center),
                feature=node.feature,
                shape_id=node.id or self._next_shape_id("arch"),
            )
            items.append(arch_item)

        for child in node.children:
            if isinstance(child, ProfileGen):
                profile_item = Item(
                    kind="shape",
                    type="Polygon",
                    geometry=Geometry(data={"points": relative_points, "holes": []}),
                    placement=Placement(center_xy_mm=arch_region.center),
                    feature=_feature_from_profile_gen(child),
                    shape_id=self._next_shape_id("arch_profile"),
                )
                items.append(profile_item)
            elif isinstance(child, Frame):
                inset_domain = arch_domain.inset(child.width_mm).domains[0]
                inset_bounds = inset_domain.bounds
                inset_region = ResolvedRegion(
                    x_min=inset_bounds.x_min,
                    y_min=inset_bounds.y_min,
                    x_max=inset_bounds.x_max,
                    y_max=inset_bounds.y_max,
                )

                for frame_child in child.children:
                    if isinstance(frame_child, RaisedPanelGen):
                        generator_params = RaisedPanelParams(
                            border_width_mm=frame_child.border_width_mm,
                            border_depth_mm=frame_child.border_depth_mm,
                            field_depth_mm=frame_child.field_depth_mm,
                        )
                        shape_id_prefix = self._next_shape_id("arch_raised_panel")
                        try:
                            from generators.area.raised_panel import raised_panel_generator
                            generated_items = raised_panel_generator(
                                inset_domain,
                                generator_params,
                                allow_empty=True,
                                shape_id_prefix=shape_id_prefix,
                            )
                            items.extend(generated_items)
                        except ValueError:
                            pass
                    else:
                        self._resolve_node(frame_child, inset_region, items, params)
            else:
                self._resolve_node(child, arch_region, items, params)

    def _handle_polygon(
        self,
        node: Polygon,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        abs_points = list(node.points)

        xs = [p[0] for p in abs_points]
        ys = [p[1] for p in abs_points]
        bounds_center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

        cx, cy = bounds_center
        relative_points = [[pt[0] - cx, pt[1] - cy] for pt in abs_points]

        if node.feature is not None:
            polygon_item = Item(
                kind="shape",
                type="Polygon",
                geometry=Geometry(data={"points": relative_points, "holes": []}),
                placement=Placement(center_xy_mm=bounds_center),
                feature=node.feature,
                shape_id=node.id or self._next_shape_id("polygon"),
            )
            items.append(polygon_item)

        polygon_region = ResolvedRegion(
            x_min=min(xs),
            y_min=min(ys),
            x_max=max(xs),
            y_max=max(ys),
        )

        for child in node.children:
            if isinstance(child, ProfileGen):
                profile_item = Item(
                    kind="shape",
                    type="Polygon",
                    geometry=Geometry(data={"points": relative_points, "holes": []}),
                    placement=Placement(center_xy_mm=bounds_center),
                    feature=_feature_from_profile_gen(child),
                    shape_id=self._next_shape_id("polygon_profile"),
                )
                items.append(profile_item)
            elif isinstance(child, PocketGen):
                pocket_item = Item(
                    kind="shape",
                    type="Polygon",
                    geometry=Geometry(data={"points": relative_points, "holes": []}),
                    placement=Placement(center_xy_mm=bounds_center),
                    feature=Feature(
                        type="pocket",
                        depth=str(child.depth_mm),
                        depth_mm=child.depth_mm,
                    ),
                    shape_id=self._next_shape_id("polygon_pocket"),
                )
                items.append(pocket_item)
            else:
                self._resolve_node(child, polygon_region, items, params)

    def _handle_triangle(
        self,
        node: Triangle,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        cx, cy = region.center
        half_base = node.base_mm / 2
        half_height = node.height_mm / 2

        triangle_center = (cx, cy)

        relative_points = [
            (-half_base, -half_height),
            (half_base, -half_height),
            (0, half_height),
        ]

        if node.feature is not None:
            triangle_item = Item(
                kind="shape",
                type="Polygon",
                geometry=Geometry(data={"points": relative_points, "holes": []}),
                placement=Placement(center_xy_mm=triangle_center),
                feature=node.feature,
                shape_id=node.id or self._next_shape_id("triangle"),
            )
            items.append(triangle_item)

        triangle_region = ResolvedRegion(
            x_min=cx - half_base,
            y_min=cy - half_height,
            x_max=cx + half_base,
            y_max=cy + half_height,
        )

        for child in node.children:
            if isinstance(child, ProfileGen):
                profile_item = Item(
                    kind="shape",
                    type="Polygon",
                    geometry=Geometry(data={"points": relative_points, "holes": []}),
                    placement=Placement(center_xy_mm=triangle_center),
                    feature=_feature_from_profile_gen(child),
                    shape_id=self._next_shape_id("triangle_profile"),
                )
                items.append(profile_item)
            elif isinstance(child, PocketGen):
                pocket_item = Item(
                    kind="shape",
                    type="Polygon",
                    geometry=Geometry(data={"points": relative_points, "holes": []}),
                    placement=Placement(center_xy_mm=triangle_center),
                    feature=Feature(
                        type="pocket",
                        depth=str(child.depth_mm),
                        depth_mm=child.depth_mm,
                    ),
                    shape_id=self._next_shape_id("triangle_pocket"),
                )
                items.append(pocket_item)
            else:
                self._resolve_node(child, triangle_region, items, params)

    def _handle_assembly(
        self,
        node: Assembly,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Handle Assembly: Generate all panels for a multi-panel assembly.

        Creates topology using the appropriate factory (box_topology, pyramid_topology),
        then generates panel specifications using the new assembly system. Panels are
        laid out in a grid within the region.
        """
        topology_type = node.topology

        if topology_type == "box":
            topology = box_topology(
                width_mm=node.width_mm,
                depth_mm=node.depth_mm,
                height_mm=node.height_mm,
                thickness_mm=node.thickness_mm,
                joinery=node.joinery,
                include_top=node.include_top,
                include_bottom=node.include_bottom,
                bottom_style=node.bottom_style,
                top_style=node.top_style,
                dado_inset_mm=node.dado_inset_mm,
                dado_drop_mm=node.dado_drop_mm,
            )
        elif topology_type == "pyramid":
            if node.base_mm is None or node.slant_height_mm is None:
                raise ValueError("Pyramid topology requires base and slant_height parameters")
            topology = pyramid_topology(
                base_mm=node.base_mm,
                slant_height_mm=node.slant_height_mm,
                thickness_mm=node.thickness_mm,
            )
        else:
            raise ValueError(f"Unsupported topology type: {topology_type}")

        if node.joinery == "finger":
            if node.finger_count is not None:
                joinery_strategy = FingerJoineryStrategy(
                    finger_count=node.finger_count,
                    clearance_mm=node.clearance_mm,
                )
            elif node.finger_width_mm is not None:
                joinery_strategy = FingerJoineryStrategy(
                    finger_width_mm=node.finger_width_mm,
                    clearance_mm=node.clearance_mm,
                )
            else:
                joinery_strategy = FingerJoineryStrategy(
                    finger_width_mm=12.0,
                    clearance_mm=node.clearance_mm,
                )
        else:
            joinery_strategy = ButtJoineryStrategy()

        assembly_params = AssemblyParams(
            topology=topology,
            joinery_strategy=joinery_strategy,
        )

        panel_specs = generate_assembly_panels(assembly_params)

        edge_name_map = {0: "bottom", 1: "right", 2: "top", 3: "left"}

        gap = node.layout_gap_mm
        x_cursor = region.x_min
        y_cursor = region.y_min
        row_height = 0.0

        for spec in panel_specs:
            polygon = spec.polygon
            min_x = min(p[0] for p in polygon)
            max_x = max(p[0] for p in polygon)
            min_y = min(p[1] for p in polygon)
            max_y = max(p[1] for p in polygon)
            panel_width = max_x - min_x
            panel_height = max_y - min_y

            if x_cursor + panel_width > region.x_max:
                x_cursor = region.x_min
                y_cursor += row_height + gap
                row_height = 0.0

            panel_center = (
                x_cursor + panel_width / 2,
                y_cursor + panel_height / 2,
            )

            filtered_edge_joints = {
                edge_name_map.get(idx, f"edge_{idx}"): profile
                for idx, profile in spec.edge_joints.items()
                if profile is not None
            }

            panel_params = JointedPanelParams(
                width_mm=panel_width,
                height_mm=panel_height,
                edge_joints=filtered_edge_joints,
                part_name=spec.name,
            )

            panel_label = spec.name.upper().replace("_", " ") if node.show_labels else None
            panel_items = jointed_panel_generator(
                panel_params,
                center=panel_center,
                shape_id_prefix=self._next_shape_id(f"assembly_{spec.name}"),
                label=panel_label,
            )

            if node.show_edge_colors and panel_items:
                edge_colors = {
                    "top": "#5ab9ea",
                    "bottom": "#ff9500",
                    "left": "#4cd964",
                    "right": "#ffcc00",
                }
                edge_lines = []
                x_min = x_cursor
                x_max = x_cursor + panel_width
                y_min = y_cursor
                y_max = y_cursor + panel_height

                for edge_idx in spec.edge_joints.keys():
                    edge_name = edge_name_map.get(edge_idx, f"edge_{edge_idx}")
                    color = edge_colors.get(edge_name, "#ffffff")
                    if edge_name == "top":
                        edge_lines.append({
                            "x1": x_min, "y1": y_max, "x2": x_max, "y2": y_max, "color": color
                        })
                    elif edge_name == "bottom":
                        edge_lines.append({
                            "x1": x_min, "y1": y_min, "x2": x_max, "y2": y_min, "color": color
                        })
                    elif edge_name == "left":
                        edge_lines.append({
                            "x1": x_min, "y1": y_min, "x2": x_min, "y2": y_max, "color": color
                        })
                    elif edge_name == "right":
                        edge_lines.append({
                            "x1": x_max, "y1": y_min, "x2": x_max, "y2": y_max, "color": color
                        })

                updated_item = replace(
                    panel_items[0],
                    params={"edge_lines": edge_lines} if panel_items[0].params is None
                    else {**panel_items[0].params, "edge_lines": edge_lines}
                )
                panel_items = [updated_item] + panel_items[1:]

            items.extend(panel_items)

            for dado in spec.dados:
                if dado.edge == "bottom":
                    dado_y = y_cursor + dado.position_from_edge_mm + dado.width_mm / 2
                else:
                    dado_y = y_cursor + panel_height - dado.position_from_edge_mm - dado.width_mm / 2

                dado_center = (x_cursor + panel_width / 2, dado_y)
                dado_item = Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(
                        data={
                            "w_mm": panel_width,
                            "h_mm": dado.width_mm,
                        }
                    ),
                    placement=Placement(center_xy_mm=dado_center),
                    feature=Feature(
                        type="pocket",
                        depth=str(dado.depth_mm),
                        depth_mm=dado.depth_mm,
                    ),
                    shape_id=self._next_shape_id(f"assembly_{spec.name}_dado"),
                )
                items.append(dado_item)

            x_cursor += panel_width + gap
            row_height = max(row_height, panel_height)

    def resolve(self) -> LayoutAST:
        margin = self.ast.sheet.margin_mm

        sheet_region = ResolvedRegion(
            x_min=margin,
            y_min=margin,
            x_max=self.ast.sheet.width_mm - margin,
            y_max=self.ast.sheet.height_mm - margin,
        )


        items = []
        self._resolve_node(self.ast.root, sheet_region, items, params={})

        return LayoutAST(
            sheet=self.ast.sheet,
            items=tuple(items),
            project=self.ast.project,
            kerf_width_mm=self.ast.kerf_width_mm,
        )

    # Handler map: maps node type to handler method
    # Initialized in __init__ to allow self references
    _NODE_HANDLERS: dict[type, NodeHandler] | None = None

    def _get_handler_map(self) -> dict[type, NodeHandler]:
        """Return the handler map, initializing lazily if needed."""
        if LayoutResolver._NODE_HANDLERS is None:
            LayoutResolver._NODE_HANDLERS = {
                Panel: LayoutResolver._handle_panel,
                Inset: LayoutResolver._handle_inset,
                Frame: LayoutResolver._handle_frame,
                Grid: LayoutResolver._handle_grid,
                Split: LayoutResolver._handle_split,
                Cell: LayoutResolver._handle_cell,
                UseComponent: LayoutResolver._handle_use_component,
                Place: LayoutResolver._handle_place,
                Rect: LayoutResolver._handle_rect,
                Circle: LayoutResolver._handle_circle,
                RoundedRect: LayoutResolver._handle_rounded_rect,
                Line: LayoutResolver._handle_line,
                Polyline: LayoutResolver._handle_polyline,
                SplinePath: LayoutResolver._handle_spline_path,
                Keepout: LayoutResolver._handle_keepout,
                Item: LayoutResolver._handle_item,
                # Generator handlers (Stage 12)
                ProfileGen: LayoutResolver._handle_profile_gen,
                PocketGen: LayoutResolver._handle_pocket_gen,
                RaisedPanelGen: LayoutResolver._handle_raised_panel_gen,
                ChamferGen: LayoutResolver._handle_chamfer_gen,
                WaveGen: LayoutResolver._handle_wave_gen,
                SplitHorizontal: LayoutResolver._handle_split_horizontal,
                SplitVertical: LayoutResolver._handle_split_vertical,
                SplitGrid: LayoutResolver._handle_split_grid,
                # Stage 13 generator handlers
                LinesGen: LayoutResolver._handle_lines_gen,
                ConcentricBorderGen: LayoutResolver._handle_concentric_border_gen,
                # Stage 14 handlers
                SplitHorizontalGaps: LayoutResolver._handle_split_horizontal_gaps,
                AtPosition: LayoutResolver._handle_at_position,
                Subtract: LayoutResolver._handle_subtract,
                Arch: LayoutResolver._handle_arch,
                # Stage 15 handlers (polygon/triangle)
                Polygon: LayoutResolver._handle_polygon,
                Triangle: LayoutResolver._handle_triangle,
                # Stage 16 handlers (x_panel generator)
                XPanelGen: LayoutResolver._handle_x_panel_gen,
                # Stage 18 handlers (hole_grid generator)
                HoleGridGen: LayoutResolver._handle_hole_grid_gen,
                # Stage 20 handlers (measurement_grid generator)
                MeasurementGridGen: LayoutResolver._handle_measurement_grid_gen,
                # Stage 21 handlers (measurement_edge generator)
                MeasurementEdgeGen: LayoutResolver._handle_measurement_edge_gen,
                # Stage 22 handlers (engrave_text generator)
                EngraveTextGen: LayoutResolver._handle_engrave_text_gen,
                # Waste cuts handler
                WasteCuts: LayoutResolver._handle_waste_cuts,
                # Assembly handler
                Assembly: LayoutResolver._handle_assembly,
            }
        return LayoutResolver._NODE_HANDLERS

    def _resolve_node(
        self,
        node: Any,
        region: ResolvedRegion,
        items: list[Item],
        params: dict[str, Any],
    ) -> None:
        """Dispatch to the appropriate handler based on node type."""
        if node is None:
            return

        handler_map = self._get_handler_map()
        node_type = type(node)

        if node_type in handler_map:
            handler_map[node_type](self, node, region, items, params)
        # Unknown node types are silently ignored (preserves original behavior)


def resolve_layout(ast: CompositionalLayoutAST, validate: bool = True) -> LayoutAST:
    """Resolve a compositional layout AST to a flat LayoutAST.

    Args:
        ast: The compositional layout AST to resolve
        validate: Run geometry assertions during resolution (default True)

    Returns:
        Flat LayoutAST with absolute coordinates

    Raises:
        ResolutionAssertionError: If a geometry assertion fails
    """
    resolver = LayoutResolver(ast, validate=validate)
    return resolver.resolve()
