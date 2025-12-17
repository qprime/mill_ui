# Layout Primitives

This document describes the layout managers and shapes available in the v2 compositional layout system.

## Overview

The v2 layout system provides **layout managers** that subdivide regions hierarchically, and **shapes** that fill those regions with CAM features (profiles, pockets, etc.).

**Key concepts:**
- **Region-relative composition**: Children fill their parent region by default, no explicit XY coordinates required
- **Layout managers**: Nodes that subdivide the current region (inset, frame, grid, split)
- **Shapes**: Geometric primitives that fill the current region (rect, circle, rounded_rect, line)
- **Features**: CAM operations applied to shapes (profile, pocket, engrave, hole)

## Layout Managers

Layout managers subdivide the current region and provide new regions for their children.

### Inset

Shrinks the current region inward by a specified amount on all sides.

**Syntax:**
```
inset <amount>mm
    <children...>
```

**Example:**
```
inset 50.00mm
    rect panel pocket 6.00mm
```

**Use case:** Creating margins, borders, or inset panels.

---

### Frame

Creates a profile at the boundary of the current region and provides an inner field region for children.

**Syntax:**
```
frame <width>mm
    <children...>
```

**Example:**
```
rect outer profile through outside
    frame 40.00mm
        rect inner pocket 5.00mm
```

**Use case:** Picture frames, panel fields, raised panels.

**Details:**
- Frame works on any closed region (rect, circle, rounded_rect)
- Profile is created at the boundary (default: through-cut, outside)
- Inner region is shrunk by frame width on all sides

---

### Grid

Subdivides the current region into rows × columns cells with optional gap spacing.

**Syntax:**
```
grid <rows> <cols> gap <gap>mm
    cell
        <children...>
```

**Example:**
```
grid 2 3 gap 10.00mm
    cell
        rect pocket 5.00mm
```

**Use case:** Regular tile patterns, grid layouts, multi-instance placement.

**Details:**
- Gap is the spacing between cells (not inset from edges)
- Cell content is replicated in each grid cell
- Cell sizes account for gap spacing: `cell_width = (region_width - (cols-1)*gap) / cols`

---

### Split

Subdivides the current region into panes with rail/mullion bars (material reserved between panes).

**Syntax:**
```
split <rows> <cols> rail <rail>mm mullion <mullion>mm
    cell
        <children...>
```

**Example:**
```
split 2 2 rail 50.00mm mullion 40.00mm
    cell
        rect glass_pane pocket 6.00mm
```

**Use case:** French doors, drawer faces with decorative mullions, cabinet doors with divided lights.

**Details:**
- **Rails** are horizontal bars (between rows)
- **Mullions** are vertical bars (between columns)
- Pane sizes account for material reserved by bars:
  - `pane_width = (region_width - (cols-1)*mullion_mm) / cols`
  - `pane_height = (region_height - (rows-1)*rail_mm) / rows`
- When `rail_mm=0` and `mullion_mm=0`, behaves identically to `grid` with `gap=0`
- Cell content is replicated in each pane

**Comparison with Grid:**
- **Grid**: Gap is empty space between cells (no material)
- **Split**: Rails/mullions reserve material between panes (for structural bars)

**Example: French Door**
```
sheet 800.00mm 1200.00mm 19.00mm

rect door_outer profile through outside
    frame 60.00mm
        split 2 2 rail 50.00mm mullion 40.00mm
            cell
                rect glass_pane pocket 8.00mm
```

This produces:
- Outer profile (800×1200mm)
- Frame profile with 60mm width
- Inner field (680×1080mm)
- 4 panes subdivided by 50mm rails (horizontal) and 40mm mullions (vertical)
- Each pane: 320×515mm glass pocket

---

## Shapes

Shapes are geometric primitives that fill the current region.

### Rect

Rectangle that fills the current region by default.

**Syntax:**
```
rect <id> [feature]
    <children...>
```

**Example:**
```
rect panel pocket 6.00mm
```

---

### Circle

Circular region, either with explicit diameter or inscribed in current region.

**Syntax:**
```
circle <id> [diameter <size>mm | fit] [feature]
    <children...>
```

**Example (fit mode):**
```
circle hole fit hole 8.00mm
```

**Example (explicit diameter):**
```
circle button diameter 50.00mm pocket 3.00mm
```

---

### RoundedRect

Rectangle with rounded corners that fills the current region.

**Syntax:**
```
rounded_rect <id> radius <radius>mm [feature]
    <children...>
```

**Example:**
```
rounded_rect panel radius 10.00mm pocket 6.00mm
```

---

### Line

Open path for engraving (horizontal or vertical spanning current region).

**Syntax:**
```
line <id> <orientation> [feature]
```

**Example:**
```
line divider horizontal engrave 1.00mm
```

---

## Features

Features are CAM operations applied to shapes.

- **profile**: Through-cut or partial-depth cut along shape boundary
  - `profile through outside` (default)
  - `profile 10.00mm inside`
- **pocket**: Milling out material within shape boundary
  - `pocket 6.00mm`
- **hole**: Drilling operation (typically on circles)
  - `hole 8.00mm`
- **engrave**: Shallow v-carving or line engraving
  - `engrave 1.00mm`

---

## Nesting and Composition

Layout managers and shapes can be freely nested:

```
sheet 600.00mm 600.00mm 19.00mm

rect outer profile through outside
    inset 20.00mm
        frame 30.00mm
            split 2 2 rail 40.00mm mullion 30.00mm
                cell
                    rect pane pocket 5.00mm
```

This produces:
1. Outer profile (600×600mm)
2. Inset by 20mm → 560×560mm region
3. Frame (30mm width) → profile + 500×500mm inner region
4. Split (2×2 with 40mm rails, 30mm mullions) → 4 panes
5. Each pane gets a pocket

**Execution order:**
1. Layout managers subdivide regions top-down
2. Shapes emit items with absolute coordinates
3. Resolution produces flat LayoutAST compatible with RemovalIntent pipeline

---

## Design Principles

**1. Region-relative composition**
- No explicit XY coordinates in authored PML
- Children inherit and subdivide parent regions
- Positioning is deterministic and compositional

**2. Fill-by-default semantics**
- Shapes fill their current region unless explicitly sized
- Layout managers subdivide equally unless constrained

**3. Layout managers vs Shapes**
- **Layout managers** (inset, frame, grid, split): Subdivide regions, provide context for children
- **Shapes** (rect, circle, line): Emit CAM features (profiles, pockets, etc.)

**4. Separation of geometry and intent**
- Shapes define geometry (what to cut)
- Features define intent (how to cut: profile, pocket, etc.)
- Resolution computes absolute coordinates
- Lowering to RemovalIntent handles toolpath strategy

---

## Advanced Examples

### Drawer Face with Decorative Mullions
```
sheet 400.00mm 200.00mm 19.00mm

rect outer profile through outside
    inset 15.00mm
        split 1 3 rail 0.00mm mullion 25.00mm
            cell
                rect panel pocket 4.00mm
```

### Nested Grid in Frame
```
sheet 500.00mm 500.00mm 19.00mm

rect outer profile through outside
    frame 40.00mm
        grid 2 2 gap 20.00mm
            cell
                circle fit pocket 5.00mm
```

### French Door with Frame and Split
```
sheet 800.00mm 1200.00mm 19.00mm

rect door profile through outside
    frame 60.00mm
        split 2 2 rail 50.00mm mullion 40.00mm
            cell
                rounded_rect glass radius 5.00mm pocket 8.00mm
```
