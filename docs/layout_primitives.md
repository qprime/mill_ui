<!-- spec-style -->
# Layout Primitives

As-Of Date: 2026-01-19
Document Type: Layout Manager Specification

---

## Purpose

Define layout managers and shapes available in the compositional layout system.
Layout managers subdivide regions; shapes fill regions with CAM features.

---

## Terminology

| Term | Definition |
|------|------------|
| Layout Manager | Node that subdivides current region (Inset, Frame, Grid, Split) |
| Shape | Geometric primitive that fills current region (Rect, Circle, RoundedRect, Line) |
| Feature | CAM operation applied to shape (profile, pocket, engrave, hole) |
| Region | Computed rectangular bounds passed to children |

---

## Layout Managers

### Inset

Shrinks current region inward by specified amount on all sides.

| Field | Type | Description |
|-------|------|-------------|
| amount_mm | float | Shrink distance per edge |
| children | tuple | Nodes within inset region |

PML: `inset <amount>mm`

### Frame

Creates profile at boundary, provides inner field region for children.

| Field | Type | Description |
|-------|------|-------------|
| width_mm | float | Frame width |
| children | tuple | Nodes within inner field |

PML: `frame <width>mm`

Properties:
- Works on any closed region (rect, circle, rounded_rect)
- Profile created at boundary (default: through-cut, outside)
- Inner region shrunk by frame width on all sides

### Grid

Subdivides current region into rows × columns cells with optional gap.

| Field | Type | Description |
|-------|------|-------------|
| rows | int | Row count |
| cols | int | Column count |
| gap_mm | float | Spacing between cells |
| children | tuple | Cell content |

PML: `grid <rows> <cols> gap <gap>mm`

Cell size calculation: `cell_width = (region_width - (cols-1)*gap) / cols`

### Split

Subdivides region into panes with rail/mullion bars (material reserved).

| Field | Type | Description |
|-------|------|-------------|
| rows | int | Row count |
| cols | int | Column count |
| rail_mm | float | Horizontal bar width |
| mullion_mm | float | Vertical bar width |
| children | tuple | Pane content |

PML: `split <rows> <cols> rail <rail>mm mullion <mullion>mm`

Pane size calculation:
- `pane_width = (region_width - (cols-1)*mullion_mm) / cols`
- `pane_height = (region_height - (rows-1)*rail_mm) / rows`

Grid vs Split: Grid gaps are empty space; Split rails/mullions reserve material.

---

## Shapes

### Rect

Rectangle filling current region.

PML: `rect <id> [feature]`

### Circle

Circular region (explicit diameter or fit-to-region).

PML: `circle <id> [diameter <size>mm | fit] [feature]`

### RoundedRect

Rectangle with rounded corners.

PML: `rounded_rect <id> radius <radius>mm [feature]`

### Line

Open path for engraving (horizontal or vertical).

PML: `line <id> <orientation> [feature]`

---

## Features

| Feature | Description | Example |
|---------|-------------|---------|
| profile | Cut along boundary | `profile through outside` |
| pocket | Shallow recess | `pocket 6.00mm` |
| hole | Drilling operation | `hole 8.00mm` |
| engrave | Surface decoration | `engrave 1.00mm` |

---

## Design Principles

| Principle | Description |
|-----------|-------------|
| Region-relative | No explicit XY coordinates; children inherit/subdivide parent regions |
| Fill-by-default | Shapes fill current region unless explicitly sized |
| Separation | Layout managers subdivide regions; shapes emit CAM features |
| Layered | Geometry → Features → Resolution → RemovalIntent → Toolpath |

---

## Execution Order

1. Layout managers subdivide regions top-down
2. Shapes emit items with absolute coordinates
3. Resolution produces flat LayoutAST
4. LayoutAST compatible with RemovalIntent pipeline
