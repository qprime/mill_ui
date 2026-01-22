# PML (Panel Machining Language) Syntax Specification

PML is a human-readable declarative language for defining CNC machining layouts. It compiles to LayoutAST.

## Design Principles

- **Declarative**: No control flow, no execution, pure data
- **Human-friendly**: Natural indentation, minimal punctuation
- **Dimension-explicit**: All dimensions use `mm` suffix for clarity
- **Type-safe**: Shape types, feature types, and parameters are explicit

## Syntax Overview

```pml
# This is a comment

sheet 400mm 600mm 19mm

# Shapes: type identifier at x,y with features
rect door:outer at 200mm,300mm size 400mm,600mm profile through outside
rect door:panel at 200mm,300mm size 300mm,500mm pocket 6mm

circle hole:1 at 50mm,50mm diameter 10mm hole 8mm

# Templates (future extension)
template Shaker door:shaker params {
  outer_w: 400.0
  outer_h: 600.0
  stile_w: 50.0
  rail_h: 50.0
  panel_recess: 6.0
}
```

## Grammar

### Sheet Declaration

```
sheet <width>mm <height>mm <thickness>mm
```

Example:
```pml
sheet 450mm 650mm 19mm
```

### Shape Declarations

#### Rectangle

```
rect <id> at <x>mm,<y>mm size <w>mm,<h>mm <feature>
```

Example:
```pml
rect outer at 100mm,200mm size 80mm,120mm profile through outside
rect panel at 100mm,200mm size 60mm,100mm pocket 5mm
```

#### Circle

```
circle <id> at <x>mm,<y>mm diameter <d>mm <feature>
circle <id> at <x>mm,<y>mm radius <r>mm <feature>
```

Example:
```pml
circle hole1 at 50mm,50mm diameter 10mm hole 8mm
circle hole2 at 150mm,50mm radius 6mm hole through
```

#### RoundedRect

```
roundedrect <id> at <x>mm,<y>mm size <w>mm,<h>mm radius <r>mm [corners <corner>...] <feature>
```

**Optional selective corners:**
- `corners tl tr bl br`: Specify which corners to round (any combination)
- `tl` = top-left, `tr` = top-right, `bl` = bottom-left, `br` = bottom-right
- Omitted corners get radius 0 (square)
- If `corners` keyword is omitted, all four corners are rounded

Example:
```pml
roundedrect panel at 100mm,100mm size 80mm,60mm radius 5mm pocket 4mm
roundedrect table_half at 343mm,432mm size 686mm,864mm radius 12.7mm corners tl bl profile through outside
roundedrect corner at 50mm,50mm size 100mm,100mm radius 25mm corners tr pocket 3mm
```

### Features

#### Profile (cut outline)

```
profile through [inside|outside|on] [tabs <count> height <height>mm [width <width>mm]]
profile <depth>mm [inside|outside|on] [tabs <count> height <height>mm [width <width>mm]]
```

**Optional tabs** (holding bridges during cutting):
- `tabs <count>`: Number of tabs (positive integer)
- `height <height>mm`: Tab height (material left uncut)
- `width <width>mm`: Tab width along boundary (optional, defaults to 2× tool diameter, minimum 6mm)

Example:
```pml
profile through outside
profile 10mm inside
profile through outside tabs 4 height 3mm width 12mm
profile 6mm inside tabs 6 height 2mm
```

#### Pocket (recessed area)

```
pocket <depth>mm [corner_cleanup <diameter>mm]
pocket through [corner_cleanup <diameter>mm]
```

**Optional corner_cleanup** (multi-tool workflow for square corners):
- `corner_cleanup <diameter>mm`: Tool diameter for corner finishing pass
- Enables two-tool strategy: large tool for roughing, small tool specified here for corners
- Small tool must be smaller than primary tool to reach into corners

Example:
```pml
pocket 5mm
pocket through
pocket 6mm corner_cleanup 3.175mm
```

#### Hole (circular bore)

```
hole <depth>mm
hole through
```

Example:
```pml
hole 12mm
hole through
```

#### Engrave (surface decoration)

```
engrave <depth>mm
```

Example:
```pml
engrave 0.5mm
```

### Generators (Surface Patterns)

Generators create patterns within a shape's bounds. They are specified as children of a shape declaration using indentation.

#### Wave Pattern

```
wave count <n> amplitude <mm> wavelength <mm> groove <mm> depth <mm>
```

Creates parallel sinusoidal grooves across the surface.

Example:
```pml
rect panel
    profile outside through
    wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
```

#### Line Pattern

```
lines angle <degrees> spacing <mm> width <mm> depth <mm>
```

Creates parallel line grooves at specified angle. Use multiple `lines` declarations for crosshatch/lattice patterns.

Example:
```pml
rect panel
    profile outside through
    lines angle 45 spacing 25mm width 4mm depth 3mm
    lines angle -45 spacing 25mm width 4mm depth 3mm
```

#### Raised Panel

```
raised_panel border <mm> border_depth <mm> field_depth <mm>
```

Creates a raised panel with beveled border and recessed field.

Example:
```pml
rect panel
    profile outside through
    raised_panel border 25mm border_depth 6mm field_depth 2mm
```

#### X-Panel

```
x_panel bar_width <mm> depth <mm>
```

Creates 4 triangular pockets forming an X pattern. The bar_width controls the width of the raised X bars between the pockets.

Example:
```pml
rect panel
    profile outside through
    frame 50mm
        x_panel bar_width 50mm depth 6mm
```

#### Hole Grid

```
hole_grid spacing <mm> diameter <mm> depth <mm>|through [pattern rectangular|hexagonal|offset] [inset <mm>] [align center|corner]
```

Creates a grid of circular holes within the shape bounds. Holes are only placed where they fit entirely within the domain boundary.

**Parameters:**
- `spacing <mm>` - Center-to-center distance between holes (required)
- `diameter <mm>` - Hole diameter (required)
- `depth <mm>|through` - Hole depth or "through" for full material penetration (required)
- `pattern rectangular|hexagonal|offset` - Grid pattern type (optional, default: rectangular)
  - `rectangular`: Standard grid aligned to X/Y axes
  - `hexagonal`: Honeycomb pattern (alternating rows offset by spacing/2)
  - `offset`: Like rectangular but alternating rows offset by spacing/2
- `inset <mm>` - Inset from domain boundary (optional, default: 0)
- `align center|corner` - Grid alignment within domain (optional, default: center)
  - `center`: Grid centered on domain centroid
  - `corner`: Grid aligned to domain bounds corner

Example:
```pml
rect pegboard
    profile outside through
    hole_grid spacing 50mm diameter 6.35mm depth through pattern rectangular inset 50mm align center

rounded_rect panel radius 25mm
    profile outside through
    hole_grid spacing 25mm diameter 5mm depth 10mm pattern hexagonal
```

#### Concentric Border

```
concentric_border insets <mm> <mm> ... groove <mm> depth <mm>
```

Creates concentric rectangular grooves at specified inset distances.

Example:
```pml
rect panel
    profile outside through
    concentric_border insets 15mm 30mm 45mm groove 3mm depth 2mm
```

#### Split Grid

```
split_grid <rows> <cols> gap <mm>
    <generator>
```

Divides the shape into a grid and applies a generator to each cell.

Example:
```pml
rect panel
    profile outside through
    split_grid 2 2 gap 35mm
        raised_panel border 25mm border_depth 6mm field_depth 2mm
```

#### Split Horizontal / Split Vertical

```
split_horizontal <n> gap <mm>
    <children>

split_vertical <n> gap <mm>
    <children>
```

Divides region into n equal segments with gaps between. Children applied to each segment.

Example:
```pml
rect panel
    profile outside through
    split_horizontal 3 gap 20mm
        pocket 6mm
```

#### Split Horizontal Gaps

```
split_horizontal_gaps <n> gap <mm>
    <children>
```

Splits region into n+1 segments, applies children to the n gaps (not segments). Used for louver/dado patterns where gaps are machined.

Example:
```pml
rect panel
    profile outside through
    split_horizontal_gaps 12 gap 12mm
        pocket 8mm
        chamfer 4mm 2mm
```

#### Chamfer

```
chamfer <width>mm <depth>mm
```

Creates a chamfered edge at specified width and depth.

Example:
```pml
rect panel
    profile outside through
    chamfer 5mm 3mm
```

#### Subtract (Ring/Donut)

```
subtract inner <mm>
    <children>
```

Creates a ring by subtracting inner region from outer. Children applied to the resulting ring domain.

Example:
```pml
rect frame
    subtract inner 50mm
        pocket 5mm
```

#### At Position

```
at <x>mm <y>mm [width <w>mm height <h>mm]
    <child>
```

Positions child at explicit coordinates within current region. Optional width/height specify region size.

Example:
```pml
rect panel
    at 300mm 150mm width 600mm height 19mm
        pocket 10mm
```

### Shapes

#### Arch

```
arch [id] width <mm> height <mm> radius <mm> [feature]
    <children>
```

Creates an arch shape (rectangle with semicircular top).

Example:
```pml
arch door width 500mm height 800mm radius 250mm
    profile outside through
    frame 60mm
        raised_panel border 25mm border_depth 6mm field_depth 2mm
```

#### Polygon

```
polygon [id] points (<x>mm,<y>mm) (<x>mm,<y>mm) (<x>mm,<y>mm) ... [feature]
    <children>
```

Creates an arbitrary polygon shape from explicit coordinate points. Minimum 3 points required.

Example:
```pml
polygon wedge points (0mm,0mm) (100mm,0mm) (50mm,80mm)
    pocket 6mm
```

#### Triangle

```
triangle [id] base <mm> height <mm> [feature]
    <children>
```

Creates a triangular shape centered in the current region. The triangle has its base at the bottom and apex at the top.

Example:
```pml
triangle corner base 100mm height 80mm
    pocket 4mm
```

### Template Invocation (Phase 2)

```
template <TemplateName> <id> params {
  <param_name>: <value>
  ...
}
```

Example:
```pml
template Shaker door:main params {
  outer_w: 400.0
  outer_h: 600.0
  stile_w: 50.0
  rail_h: 50.0
  panel_recess: 6.0
}
```

### Metadata (Optional)

```
project <name>
kerf <width>mm
```

Example:
```pml
project cabinet_door_001
kerf 0.2mm
```

## Comments

```pml
# Single-line comment (entire line only)
```

## Whitespace

- Indentation is significant for nested structures (layout managers, generators, children)
- Blank lines are ignored
- Top-level declarations are single logical lines
- Child nodes must be indented under their parent

## Canonical Formatting

When PML is emitted from LayoutAST (format_pml), the system produces:

1. Sheet declaration first
2. Optional metadata (project, kerf)
3. Items in order (shapes, then templates)
4. 2 decimal places for dimensions
5. Consistent spacing

## Example: Complete Layout

```pml
# Shaker cabinet door with anchor holes
project shaker_door_v1
kerf 0.15mm

sheet 450mm 650mm 19mm

rect door:outer at 225mm,325mm size 400mm,600mm profile through outside
rect door:panel at 225mm,325mm size 300mm,500mm pocket 6mm

circle door:anchor:1 at 95mm,545mm diameter 10mm hole 8mm
circle door:anchor:2 at 355mm,545mm diameter 10mm hole 8mm
circle door:anchor:3 at 95mm,105mm diameter 10mm hole 8mm
circle door:anchor:4 at 355mm,105mm diameter 10mm hole 8mm
```

## Compilation to LayoutAST

PML compiles directly to LayoutAST:

- `sheet` → Sheet(width_mm, height_mm, thickness_mm)
- `rect`/`circle`/`roundedrect` → Item(kind="shape", ...)
- `template` → Item(kind="template", ...)
- Feature syntax → Feature(type, depth, side, depth_mm)
- `project` → LayoutAST.project
- `kerf` → LayoutAST.kerf_width_mm

## Semantic Equivalence

PML → AST → PML produces canonical formatting, not original formatting:

- Comments are lost
- Whitespace is normalized
- Item ordering may be canonicalized (shapes before templates)
- Dimension precision normalized to 2 decimal places
- Geometry representation may differ (radius vs diameter)

This preserves **semantic equivalence** while losing **surface formatting**.
