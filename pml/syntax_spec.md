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

sheet 400mm 600mm 19mm margin 10mm

# Shapes: type identifier at x,y with features
rect door:outer at 200mm,300mm size 400mm,600mm profile through outside
rect door:panel at 200mm,300mm size 300mm,500mm pocket 6mm

circle hole:1 at 50mm,50mm diameter 10mm hole 8mm

# Templates (stored in templates/*.pml)
# template shaker
#     params
#         stile_w 57mm
#         rail_h 57mm
#         panel_recess 6mm
#         panel_style pocket
#
#     rect door
#         profile outside through
#         frame ${stile_w}
#             ${panel_style} ${panel_recess}
```

## Grammar

### Sheet Declaration

```
sheet <width>mm <height>mm <thickness>mm margin <margin>mm
```

The `margin` parameter defines a no-machining holddown zone around all sheet edges. When specified:
- The root layout region starts at (margin, margin) and extends to (width-margin, height-margin)
- Shapes without explicit positioning fill this region, not the full sheet
- `waste_cuts` without explicit margin will inherit this sheet margin

Example:
```pml
sheet 450mm 650mm 19mm margin 10mm
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

#### Measurement Grid

```
measurement_grid [unit metric|imperial|custom] [minor_spacing <mm>] [major_spacing <mm>] [minor_length <mm>] [major_length <mm>] [depth <mm>] [labels] [label_height <mm>] [label_offset <mm>]
```

Creates ruler-style tick marks for calibration surfaces and measurement references. Tick marks are generated along all four edges of the shape, pointing inward. Minor ticks occur at regular intervals, with longer major ticks at larger intervals.

**Parameters:**
- `unit metric|imperial|custom` - Preset unit mode (optional, default: metric)
  - `metric`: minor=1mm, major=10mm
  - `imperial`: minor=1/16" (1.5875mm), major=1" (25.4mm)
  - `custom`: uses explicit spacing values (requires minor_spacing and major_spacing)
- `minor_spacing <mm>` - Distance between minor tick marks (required for custom mode)
- `major_spacing <mm>` - Distance between major tick marks (required for custom mode)
- `minor_length <mm>` - Length of minor tick marks (optional, default: 3mm)
- `major_length <mm>` - Length of major tick marks (optional, default: 6mm)
- `depth <mm>` - Engraving depth (optional, default: 0.5mm)
- `labels` - Enable numeric labels at major tick intervals (optional flag)
- `label_height <mm>` - Height of label text (optional, default: 3mm)
- `label_offset <mm>` - Distance from tick mark end to label center (optional, default: auto-calculated)

Example:
```pml
rect calibration_surface
    measurement_grid unit metric minor_length 3mm major_length 6mm depth 0.5mm

rect labeled_ruler
    measurement_grid unit metric labels label_height 4mm depth 0.5mm

rect custom_grid
    measurement_grid unit custom minor_spacing 2mm major_spacing 20mm minor_length 4mm major_length 8mm depth 0.5mm
```

#### Measurement Edge

```
measurement_edge edges [<edge>, ...] [unit metric|imperial|custom] [minor_spacing <mm>] [major_spacing <mm>] [minor_length <mm>] [major_length <mm>] [depth <mm>] [labels] [label_height <mm>] [label_offset <mm>]
```

Creates ruler-style tick marks along specified edges of a shape, leaving the interior clear for other content. Useful for ruler borders around work areas.

**Parameters:**
- `edges [<edge>, ...]` - Which edges to add tick marks to (required)
  - Valid edges: `top`, `bottom`, `left`, `right`
  - Specify any combination, e.g., `[top, left]` or `[top, bottom, left, right]`
- `unit metric|imperial|custom` - Preset unit mode (optional, default: metric)
  - `metric`: minor=1mm, major=10mm
  - `imperial`: minor=1/16" (1.5875mm), major=1" (25.4mm)
  - `custom`: uses explicit spacing values (requires minor_spacing and major_spacing)
- `minor_spacing <mm>` - Distance between minor tick marks (required for custom mode)
- `major_spacing <mm>` - Distance between major tick marks (required for custom mode)
- `minor_length <mm>` - Length of minor tick marks (optional, default: 3mm)
- `major_length <mm>` - Length of major tick marks (optional, default: 6mm)
- `depth <mm>` - Engraving depth (optional, default: 0.3mm)
- `labels` - Enable numeric labels at major tick intervals (optional flag)
- `label_height <mm>` - Height of label text (optional, default: 3mm)
- `label_offset <mm>` - Distance from tick mark end to label center (optional, default: auto-calculated)

Example:
```pml
rect workbench_top
    measurement_edge edges [top, left] unit metric minor_length 3mm major_length 6mm depth 0.3mm

rect labeled_drafting_table
    measurement_edge edges [top, bottom, left, right] unit metric labels label_height 4mm depth 0.3mm

rect custom_ruler_border
    measurement_edge edges [left] unit custom minor_spacing 5mm major_spacing 50mm depth 0.3mm

#### Engrave Text

```
engrave_text text "<string>" [height <mm>] [depth <mm>] [font <name>] [alignment left|center|right] [orientation horizontal|vertical]
```

Creates single-stroke engraved text using Hershey fonts. Suitable for CNC engraving labels, part numbers, and other text markings.

**Parameters:**
- `text "<string>"` - The text to engrave (required)
- `height <mm>` - Height of text in mm (optional, default: 4mm)
- `depth <mm>` - Engraving depth (optional, default: 0.3mm)
- `font <name>` - Hershey font name (optional, default: rowmans)
  - Available: rowmans, rowmand, futural, futuram, scripts, scriptc, cursive, etc.
- `alignment left|center|right` - Text alignment relative to position (optional, default: left)
- `orientation horizontal|vertical` - Text orientation (optional, default: horizontal)

Example:
```pml
rect labeled_part
    engrave_text text "FRONT" height 10mm depth 0.5mm alignment center

rect serial_number
    engrave_text text "SN-12345" height 4mm depth 0.3mm

rect vertical_label
    engrave_text text "TOP" height 8mm orientation vertical alignment center
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

### Template Definition

Templates are reusable layout patterns stored as `.pml` files in the `templates/` directory. They support parameter substitution using `${param}` syntax.

```
template <name>
    params
        <param_name> <default_value>mm    # numeric parameter
        <param_name> <keyword>            # string parameter
        ...

    <body>
```

**Components:**
- `template <name>`: Declares the template name (used for lookup)
- `params` block: Declares parameters with default values
- `<body>`: Any valid PML shape/generator node as the template content

**Parameter Types:**
- **Numeric parameters**: Have `mm` suffix, substituted as `<value>mm`
- **String parameters**: No suffix, substituted as the literal string (useful for generator selection)

**Parameter Substitution:**
- Use `${param_name}` anywhere a value is expected
- Parameters are substituted before parsing
- Numeric params → `${depth}` becomes `6.0mm`
- String params → `${style}` becomes `pocket` (literal)
- Caller can override any parameter when invoking the template

Example template file (`templates/shaker.pml`):
```pml
template shaker
    params
        stile_w 57mm
        rail_h 57mm
        panel_recess 6mm
        panel_style pocket

    rect door
        profile outside through
        frame ${stile_w}
            ${panel_style} ${panel_recess}
```

In this example, `panel_style` is a string parameter that defaults to `pocket`. This allows the template to be used with different generators without changing the template file.

**Special Parameters:**
- `outer_w` and `outer_h` are automatically set from the target region dimensions when expanding a template
- These do not need to be declared in the params block

**Usage in .nest files:**

Templates are referenced by name in `.nest` files (see `nest_syntax_spec.md`):
```nest
parts
    door 400mm 600mm x20
        template shaker
            stile_w 57mm
            panel_recess 6mm
```

### Waste Cuts Directive

```
waste_cuts
    min_size <width>mm <height>mm
    margin <mm>
    tabs <count> height <height>mm
    strategy largest|simple
```

Automatically decomposes leftover sheet material into rectangular pieces with profile cuts. This prevents irregular waste polygons that require manual trimming.

**Parameters:**
- `min_size <width>mm <height>mm` - Minimum dimensions for waste rectangles (default: 200mm 200mm)
- `margin <mm>` - Holddown no-go zone from sheet edges (default: 15mm)
- `tabs <count> height <height>mm` - Tab configuration for waste cuts (required)
- `strategy largest|simple` - Decomposition algorithm (default: largest)
  - `largest`: Maximal rectangles algorithm, produces fewer larger pieces
  - `simple`: Guillotine decomposition, recursive splits along part edges

**Behavior:**
- Must appear after all part definitions (shapes with features)
- Expands into synthetic `rect` items with `profile outside through tabs`
- Waste rectangles are only created if they meet the min_size threshold
- Waste cuts run last in the profile pass (parts stay fixtured until removed)

Example:
```pml
sheet 1220mm 1220mm 19mm

rect panel1 at 300mm,300mm size 400mm,400mm
    profile outside through tabs 4 height 3mm

waste_cuts
    min_size 200mm 200mm
    margin 15mm
    tabs 4 height 3mm
    strategy largest
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

### Revision Header

PML files automatically receive a revision header when processed by the CLI or recipe regeneration:

```pml
# mill_ui: fa974a8
# generated: 2026-01-22

sheet 1220mm 1220mm 19mm
...
```

**Purpose:**
- `# mill_ui: <hash>` - Git revision of mill_ui used to generate outputs
- `# generated: <date>` - ISO date when file was processed

This enables backward compatibility: checkout the referenced mill_ui revision to regenerate G-code from older PML files. The header is overwritten on each successful pipeline run.

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
