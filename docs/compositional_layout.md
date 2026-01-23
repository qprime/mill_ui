<!-- spec-style -->
# Compositional Layout System

As-Of Date: 2026-01-22
Document Type: Layout System Specification

---

## Purpose

The compositional layout system enables hierarchical, region-relative layout specification.
Children operate within their parent's computed region.
Layout managers compute positions; explicit XY coordinates are not required.

---

## Non-Goals

- Absolute coordinate authoring at compositional level
- Constraint solving or algebra expressions
- Direct RemovalIntent generation (separate layer)

---

## Terminology

| Term | Definition |
|------|------------|
| Region | Computed rectangular bounds (x_min, y_min, x_max, y_max) |
| Layout Manager | Node that subdivides current region (Inset, Frame, Grid, Split) |
| Component | Reusable parameterized subtree |
| Resolution | Transform from compositional AST to flat LayoutAST |

---

## Pipeline Position

```
CompositionalLayoutAST → resolve_layout() → LayoutAST (flat) → RemovalIntent → G-code
```

Regions are computed during resolution, never authored.

---

## Compositional Nodes

### Panel

Root workpiece region. Establishes initial region from sheet bounds.

| Field | Type | Description |
|-------|------|-------------|
| children | tuple | Nested layout nodes |
| id | str (optional) | Identifier |

### Inset

Shrinks current region inward by amount on all sides.

| Field | Type | Description |
|-------|------|-------------|
| amount_mm | float | Shrink distance per edge |
| children | tuple | Nodes within inset region |

Use case: Margins, safety zones, workholding clearance.

### Frame

Layout manager that insets the current region, producing an inner field for children.

| Field | Type | Description |
|-------|------|-------------|
| width_mm | float | Frame width (edge to inner field) |
| children | tuple | Nodes within inner field |

Properties:
- Works on ANY closed region (rect, circle, irregular)
- Children operate in region shrunk by frame width
- Parent shape is responsible for its own profile cut

Use case: Shaker panels, decorative frames, structural borders.

### Grid

Subdivides current region into rows × cols cells.

| Field | Type | Description |
|-------|------|-------------|
| rows | int | Row count |
| cols | int | Column count |
| gap_mm | float | Spacing between cells |
| children | tuple | Cell content |

Gap semantics:
- Gap is spacing BETWEEN cells, not inset from edges
- Cell size = (region_size - gaps) / count

Use case: Multi-panel layouts, paned doors, grid patterns.

### Cell

Content template for grid cells. Replicated once per grid cell.

| Field | Type | Description |
|-------|------|-------------|
| inset_mm | float (optional) | Per-cell inset |
| children | tuple | Content for each cell |

If Grid has no explicit Cell children, direct children are treated as cell content.

### Split

Subdivides region into panes with rail/mullion bars (material reserved between panes).

| Field | Type | Description |
|-------|------|-------------|
| rows | int | Row count |
| cols | int | Column count |
| rail_mm | float | Horizontal bar width |
| mullion_mm | float | Vertical bar width |
| children | tuple | Pane content |

Pane size calculation:
- `pane_width = (region_width - (cols-1)*mullion_mm) / cols`
- `pane_height = (region_height - (rows-1)*rail_mm) / rows`

Difference from Grid: Rails/mullions reserve material; Grid gaps are empty space.

### Rect

Rectangle that fills current region by default.

| Field | Type | Description |
|-------|------|-------------|
| children | tuple (optional) | Nested layout nodes |
| feature | Feature (optional) | CAM feature |
| id | str (optional) | Identifier |

### ComponentDef

Reusable component definition.

| Field | Type | Description |
|-------|------|-------------|
| name | str | Component name |
| params | dict | Default parameters |
| body | Node | Component body |

Components are region-relative: operate within current region when instantiated.

### UseComponent

Component instantiation with parameter substitution.

| Field | Type | Description |
|-------|------|-------------|
| component_name | str | Component to instantiate |
| args | dict | Parameter overrides |

### Place

Sheet-level multi-instance placement.

| Field | Type | Description |
|-------|------|-------------|
| layout | Grid | Placement grid |
| children | tuple | Components to place |

---

## Resolution Process

1. Start from Panel: initial region = full sheet bounds
2. Propagate region context: each node receives parent's region
3. Apply layout managers: Inset shrinks, Frame creates profile + shrinks, Grid/Split subdivide
4. Replicate content: Cell and Place repeat subtrees
5. Expand components: UseComponent → expanded body with param substitution
6. Output flat shapes: absolute-positioned Item nodes

### Invariants

- Children fill parent region by default
- Layout is order-independent
- Regions never overlap (deterministic subdivision)
- Output compatible with existing RemovalIntent pipeline

---

## Coordinate System

| Property | Value |
|----------|-------|
| Origin | Bottom-left (0, 0) |
| +X | Right |
| +Y | Up |
| Region format | (x_min, y_min, x_max, y_max) |
| Region center | ((x_min + x_max) / 2, (y_min + y_max) / 2) |

---

## Output Format

After resolution, flat LayoutAST contains:
- Absolute-positioned Item nodes (kind="shape")
- Geometry with w_mm, h_mm
- Placement with center_xy_mm
- Feature specifications (profile, pocket, hole)

Compatible with: FlatPML formatter, RemovalIntent lowering, existing planner/strategy layers.

---

## Constraints

MUST NOT:
- Author ResolvedRegion nodes (computed only)
- Add algebra/expressions (use layout managers + params)
- Treat compositional nodes as RemovalIntent

Note: Shapes may use inline `at X,Y size W,H` for absolute positioning when needed (e.g., nesting output, machine-generated layouts). Both syntaxes are valid - use layout managers for design-time composition and absolute positioning for computed layouts.

---

## Files

| File | Purpose |
|------|---------|
| layout_ast/compositional.py | Compositional node definitions |
| resolution/layout_resolver.py | Resolution logic |
| pml/compositional_parser.py | PML parsing |
| pml/compositional_formatter.py | PML formatting |

---

## Future Extensions (Deferred)

- Irregular nesting optimization for Place
- Circular/polar grids
- Advanced component parameter binding (expressions, constraints)
- Edge treatments as compositional nodes
