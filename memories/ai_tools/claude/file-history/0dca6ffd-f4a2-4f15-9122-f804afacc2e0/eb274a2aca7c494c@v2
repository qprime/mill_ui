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

from skills.mill_ui.v2.ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    ResolvedRegion,
    CompositionalLayoutAST,
)
from skills.mill_ui.v2.ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
)


class LayoutResolver:
    """Resolves compositional layout to flat positioned shapes."""

    def __init__(self, ast: CompositionalLayoutAST):
        self.ast = ast
        self.components = ast.components  # Component library

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

        # Cell: should only appear as Grid child (handled in Grid case)
        elif isinstance(node, Cell):
            # If encountered outside Grid, treat as passthrough
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
            # Rect fills the current region
            rect_item = Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": region.width, "h_mm": region.height}),
                placement=Placement(center_xy_mm=region.center),
                feature=node.feature,  # May be None or a Feature dataclass
                shape_id=node.id,
            )
            items.append(rect_item)

            # Resolve children within same region (for nested features)
            for child in node.children:
                self._resolve_node(child, region, items, params)

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
