
from __future__ import annotations

from dataclasses import replace
from typing import Any

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
)
from layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
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


class LayoutResolver:

    def __init__(self, ast: CompositionalLayoutAST):
        self.ast = ast
        self.components = ast.components

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

    def resolve(self) -> LayoutAST:

        sheet_region = ResolvedRegion(
            x_min=0,
            y_min=0,
            x_max=self.ast.sheet.width_mm,
            y_max=self.ast.sheet.height_mm,
        )


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
        if node is None:
            return


        if isinstance(node, Panel):
            for child in node.children:
                self._resolve_node(child, region, items, params)


        elif isinstance(node, Inset):
            inset_region = region.inset(node.amount_mm)
            for child in node.children:
                self._resolve_node(child, inset_region, items, params)


        elif isinstance(node, Frame):


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


            inner_region = region.inset(node.width_mm)
            for child in node.children:
                self._resolve_node(child, inner_region, items, params)


        elif isinstance(node, Grid):
            cells = region.subdivide_grid(node.rows, node.cols, node.gap_mm)


            cell_content = [child for child in node.children if isinstance(child, Cell)]

            if not cell_content:

                cell_content = [Cell(children=node.children)]


            for cell_region in cells:
                for cell_node in cell_content:

                    content_region = cell_region.inset(cell_node.inset_mm) if cell_node.inset_mm > 0 else cell_region


                    for child in cell_node.children:
                        self._resolve_node(child, content_region, items, params)


        elif isinstance(node, Split):
            panes = region.subdivide_split(node.rows, node.cols, node.rail_mm, node.mullion_mm)


            cell_content = [child for child in node.children if isinstance(child, Cell)]

            if not cell_content:

                cell_content = [Cell(children=node.children)]


            for pane_region in panes:
                for cell_node in cell_content:

                    content_region = pane_region.inset(cell_node.inset_mm) if cell_node.inset_mm > 0 else pane_region


                    for child in cell_node.children:
                        self._resolve_node(child, content_region, items, params)


        elif isinstance(node, Cell):

            for child in node.children:
                self._resolve_node(child, region, items, params)


        elif isinstance(node, UseComponent):
            if node.component_name not in self.components:
                raise ValueError(f"Unknown component: {node.component_name}")

            comp_def = self.components[node.component_name]


            resolved_params = {**comp_def.params, **node.args}


            self._resolve_node(comp_def.body, region, items, resolved_params)


        elif isinstance(node, Place):


            if isinstance(node.layout, Grid):

                cells = region.subdivide_grid(node.layout.rows, node.layout.cols, node.layout.gap_mm)


                for idx, child in enumerate(node.children):
                    if idx < len(cells):
                        self._resolve_node(child, cells[idx], items, params)
            else:

                for child in node.children:
                    self._resolve_node(child, region, items, params)


        elif isinstance(node, Rect):

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


            for child in node.children:
                if not isinstance(child, (Keepout, Edge)):
                    self._resolve_node(child, region, items, params)


        elif isinstance(node, Circle):

            if node.diameter_mm is not None:
                diameter = node.diameter_mm
            else:

                diameter = min(region.width, region.height)


            islands = self._collect_island_bounds(node.children, region, params)


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


            for child in node.children:
                if not isinstance(child, (Keepout, Edge)):
                    self._resolve_node(child, region, items, params)


        elif isinstance(node, RoundedRect):

            islands = self._collect_island_bounds(node.children, region, params)


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


            for child in node.children:
                if not isinstance(child, (Keepout, Edge)):
                    self._resolve_node(child, region, items, params)


        elif isinstance(node, Line):

            if node.orientation == "horizontal":

                start_xy = (region.x_min, region.center[1])
                end_xy = (region.x_max, region.center[1])
            elif node.orientation == "vertical":

                start_xy = (region.center[0], region.y_min)
                end_xy = (region.center[0], region.y_max)
            else:
                raise ValueError(f"Unknown line orientation: {node.orientation}")

            line_item = Item(
                kind="path",
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


        elif isinstance(node, Polyline):


            absolute_points = []
            for norm_x, norm_y in node.points:
                abs_x = region.x_min + norm_x * region.width
                abs_y = region.y_min + norm_y * region.height
                absolute_points.append((abs_x, abs_y))

            polyline_item = Item(
                kind="path",
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


            normalized_samples = sample_catmull_rom_spline(list(node.points), node.tolerance_mm)


            absolute_points = []
            for norm_x, norm_y in normalized_samples:
                abs_x = region.x_min + norm_x * region.width
                abs_y = region.y_min + norm_y * region.height
                absolute_points.append((abs_x, abs_y))


            spline_item = Item(
                kind="path",
                type="Polyline",
                geometry=Geometry(data={
                    "points_mm": absolute_points,
                    "spline_source": True,
                    "spline_tolerance_mm": node.tolerance_mm,
                }),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,
                shape_id=node.id,
            )
            items.append(spline_item)


        elif isinstance(node, Keepout):


            pass


        elif isinstance(node, Item):
            items.append(node)


        else:
            pass


def resolve_layout(ast: CompositionalLayoutAST) -> LayoutAST:
    resolver = LayoutResolver(ast)
    return resolver.resolve()
