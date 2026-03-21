# PML (Panel Machining Language) Syntax Specification

PML is a YAML-based declarative language for defining CNC machining layouts. It compiles to LayoutAST.

## Design Principles

- **Declarative**: No control flow, no execution, pure data
- **Standard format**: Valid YAML with JSON Schema validation
- **Dimension-explicit**: All dimensions use `mm` suffix for clarity (e.g., `100mm`)
- **Type-safe**: Shape types, feature types, and parameters are explicit
- **IDE-friendly**: JSON Schema enables autocomplete and validation

## Coordinate System

PML uses a **working-area coordinate system**:

- **Physical sheet dimensions** (`physical_width`, `physical_height` or `width`, `height`): The actual size of the material
- **Margin**: The clamp zone around the perimeter that cannot be machined (default 0mm)
- **Working area**: The cuttable zone, derived as `physical - 2*margin`

**All part coordinates are relative to the working area origin (0,0)**. The margin is applied automatically during G-code/SVG export.

This design makes it **impossible** to accidentally cut in the margin zone—that coordinate space doesn't exist internally.

### Tool Clearance for Outside Profiles

For outside profile cuts, don't place parts at the very edge of the working area. The validation will catch parts that are too close to the boundary and report an error.

**Simple rule:** Keep part edges ~10mm or more from working area boundaries. Use round numbers for coordinates.

```yaml
# Good - parts well within working area, simple coordinates
- Rect:
    at:
      x: 100mm
      y: 100mm
      width: 200mm
      height: 150mm
    children:
      - Profile: {side: outside, depth: through}
```

**Note:** `at.x` and `at.y` specify the part **center**, not the edge. A 200mm wide part at x=100mm has edges at x=0mm and x=200mm.

## Quick Example

```yaml
Sheet:
  physical_width: 420mm   # actual sheet size
  physical_height: 620mm
  thickness: 19mm
  margin: 10mm            # working area = 400x600mm

children:
  - Rect:
      id: door
      children:
        - Profile:
            side: outside
            depth: through
        - Frame:
            width: 50mm
            children:
              - Pocket:
                  depth: 6mm
```

## Document Structure

A PML document has the following top-level keys:

```yaml
project: "optional project name"    # Optional
kerf: 3.175mm                       # Optional tool kerf override
Sheet:                              # Required
  physical_width: 1220mm            # or 'width' for backward compat
  physical_height: 2420mm           # or 'height' for backward compat
  thickness: 19mm
  margin: 10mm                      # Optional, default 0mm (working area = 1200x2400)
  material: mdf                     # Optional, default "mdf" — validated against feeds.yml (data-driven)
  gcode_output: per-tool            # Optional, default "per-operation"
Surface:                              # Optional — full-sheet facing passes
  depth: 0.5mm
  passes: 2
  stepover: 70%
  direction: x
  cool_every: 5
  cool_dwell: 3s
  margin: 5mm
components:                         # Optional reusable components
  my_component:
    params: {width: 100mm}
    body: {Rect: {children: [...]}}
children:                           # Required - list of child nodes
  - Rect: {...}
  - Circle: {...}
```

### Working-Area Dimensions

As an alternative to specifying physical sheet dimensions, you can specify the working area directly using `working_width` and `working_height`. The parser derives physical dimensions as `working + 2*margin`:

```yaml
Sheet:
  working_width: 1200mm     # cuttable area width
  working_height: 1200mm    # cuttable area height
  thickness: 19mm
  margin: 10mm              # physical sheet = 1220x1220mm
```

This is useful when you want to work in a coordinate system where (0,0) is the corner of the cuttable zone without thinking about physical sheet size.

Generate a starter file with working-area dimensions using:

```bash
python -m cli.mill --init_project layout --sheet 1220x1220 --thickness 19 --margin 10
```

For assembly projects (finger-jointed boxes, etc.), use:

```bash
python -m cli.mill --init_project assembly --sheet 800x600 --thickness 6
```

For nesting projects, use:

```bash
python -m cli.nest --init_project --sheet 1220x2440 --thickness 19
```

## Dimensions

All dimensions use the `mm` suffix:

```yaml
width: 100mm      # Integer
height: 50.5mm    # Float
depth: 6mm
```

Bare numbers without `mm` are also accepted:

```yaml
width: 100        # Interpreted as 100mm
```

## Surface (Full-Sheet Facing)

The `Surface` top-level key adds full-width raster facing passes — for spoilboard surfacing, stock prep, or face milling. The resolver desugars it into full-sheet pocket items.

```yaml
Surface:
  depth-per-pass: 0.5mm # Required — depth per pass
  passes: 2             # Optional, default 1 — number of stacked passes
  stepover: 70%         # Optional, default 70% — tool diameter percentage
  direction: x          # Optional, default "x" — raster direction ("x" or "y")
  cool_every: 5         # Optional, default 0 — retract every N rows (0 = disabled)
  cool_dwell: 3s        # Optional, default 0s — dwell time at safe-z per cooling retract
  margin-overrun: 5mm   # Optional, default 0mm — overscan beyond working area
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `depth-per-pass` | dimension | *required* | Material removal per pass |
| `passes` | integer | 1 | Number of stacked passes (each removes `depth-per-pass` more) |
| `stepover` | percentage | 70% | Tool diameter overlap between rows |
| `direction` | `x` or `y` | `x` | Raster sweep direction |
| `cool_every` | integer | 0 | Insert cooling retract every N rows (0 = disabled) |
| `cool_dwell` | duration | 0s | Dwell time at safe-z during cooling retracts |
| `margin-overrun` | dimension | 0mm | Overscan beyond working area edges |

Multi-pass example: with `depth-per-pass: 0.5mm` and `passes: 3`, pass 0 cuts 0→0.5mm, pass 1 cuts 0.5→1.0mm, pass 2 cuts 1.0→1.5mm. Surface items are exempt from working-area bounds validation (overscan is intentional).

## G-code Output Modes

Controls how G-code files are grouped. Set on the Sheet block:

```yaml
Sheet:
  width: 600mm
  height: 400mm
  thickness: 19mm
  gcode_output: per-tool    # or per-operation (default)
```

| Mode | Behavior | Use Case |
|------|----------|----------|
| `per-operation` | One file per operation+tool (e.g. `pocket-9.53mm.nc`, `profile-3.18mm.nc`) | Production runs, maximum control between operations |
| `per-tool` | One file per tool diameter (e.g. `9.53mm.nc`, `3.18mm.nc`) | One-offs, fewer files, fewer operator mistakes |

In `per-tool` mode, all operations sharing the same tool are concatenated into a single G-code file. The planner's internal operation ordering (pockets before profiles) is preserved within each file.

## Node Types

Each node is a single-key object where the key is the node type:

```yaml
- Rect:
    id: my_rect
    children: [...]

- Circle:
    diameter: 50mm
    feature:
      type: hole
      depth: 10mm
```

### Shapes

#### Rect

Rectangle filling parent region or positioned explicitly.

```yaml
- Rect:
    id: panel              # Optional identifier
    label: "Door Panel"    # Optional display label (defaults to id)
    feature:               # Optional inline feature
      type: profile
      side: outside
      depth: through
    children:              # Optional nested nodes
      - Pocket: {depth: 6mm}
```

With explicit position:

```yaml
- Rect:
    id: cutout
    at:
      x: 100mm
      y: 50mm
      width: 200mm
      height: 150mm
    feature:
      type: pocket
      depth: 6mm
```

#### Circle

```yaml
- Circle:
    diameter: 50mm         # Either diameter or radius
    # radius: 25mm
    label: "Dowel Hole"    # Optional display label
    feature:
      type: hole
      depth: through
```

#### RoundedRect

```yaml
- RoundedRect:
    radius: 10mm
    corners: [tl, tr]      # Optional: only round these corners
    feature:
      type: profile
      depth: through
```

#### Polygon

```yaml
- Polygon:
    id: custom_shape
    label: "Bracket"       # Optional display label (defaults to id)
    points:
      - [0mm, 0mm]
      - [100mm, 0mm]
      - [100mm, 50mm]
      - [50mm, 100mm]
      - [0mm, 50mm]
    feature:
      type: profile
      depth: through
```

#### Triangle

```yaml
- Triangle:
    base: 100mm
    height: 80mm
    label: "Gusset"        # Optional display label
    feature:
      type: pocket
      depth: 5mm
```

#### Arch

```yaml
- Arch:
    width: 500mm
    height: 800mm
    radius: 250mm
    children:
      - Profile: {side: outside, depth: through}
      - Frame:
          width: 60mm
          children:
            - RaisedPanel: {border_width: 25mm, border_depth: 6mm, field_depth: 2mm}
```

#### Line / Polyline / Spline

```yaml
- Line:
    orientation: horizontal  # or vertical
    feature: {type: engrave, depth: 0.5mm}

- Polyline:
    points: [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [1.0, 0.5]]
    feature: {type: engrave, depth: 0.3mm}

- Spline:
    points: [[0.0, 0.5], [0.25, 0.6], [0.5, 0.4], [0.75, 0.6], [1.0, 0.5]]
    tolerance: 0.1mm
    feature: {type: engrave, depth: 0.3mm}
```

### Layout Containers

#### Inset

Shrink all sides by specified amount:

```yaml
- Inset:
    distance: 25mm
    children:
      - Pocket: {depth: 6mm}
```

#### Frame

Create a frame border around content:

```yaml
- Frame:
    width: 50mm
    children:
      - Pocket: {depth: 6mm}
```

#### Grid

Divide region into rows × cols cells:

```yaml
- Grid:
    rows: 4
    cols: 2
    gap: 10mm
    children:
      - Cell:
          children:
            - Circle: {diameter: 20mm}
```

#### Split

Window-pane style division:

```yaml
- Split:
    rows: 2
    cols: 3
    rail: 40mm      # Horizontal dividers
    mullion: 30mm   # Vertical dividers
    children: [...]
```

### Generators

#### Profile

Cut around shape boundary:

```yaml
- Profile:
    side: outside       # outside | inside | on
    depth: through      # or specific depth like 10mm
    tab_count: 4        # Optional holding tabs (mutually exclusive with onion_skin_mm)
    tab_height: 3mm
    tab_width: 10mm     # Optional, auto-calculated if omitted
    onion_skin_mm: 0.3  # Optional onion skin holding (mutually exclusive with tabs)
```

#### Pocket

Clear material from enclosed area:

```yaml
- Pocket:
    depth: 6mm
```

#### RaisedPanel

Decorative panel with beveled border:

```yaml
- RaisedPanel:
    border_width: 25mm
    border_depth: 6mm
    field_depth: 2mm
```

#### Chamfer

Beveled edge treatment:

```yaml
- Chamfer:
    width: 5mm
    depth: 3mm
```

#### Roundover

Rounded (fillet) edge using a roundover bit:

```yaml
- Roundover:
    radius: 6mm
```

#### SplitGrid

Divide region into grid, apply children to all cells:

```yaml
- SplitGrid:
    rows: 2
    cols: 2
    gap: 35mm
    children:
      - RaisedPanel: {...}
```

#### SplitHorizontal / SplitVertical

Divide into strips:

```yaml
- SplitHorizontal:
    count: 3
    gap: 20mm
    children:
      - Pocket: {depth: 6mm}
```

#### SplitHorizontalGaps

Apply children to gaps (louver/dado patterns):

```yaml
- SplitHorizontalGaps:
    count: 12
    gap: 12mm
    children:
      - Pocket: {depth: 8mm}
      - Chamfer: {width: 4mm, depth: 2mm}
```

#### Lines

Parallel line pattern:

```yaml
- Lines:
    angle: 45
    spacing: 25mm
    width: 4mm
    depth: 3mm
```

#### ConcentricBorder

Nested border grooves:

```yaml
- ConcentricBorder:
    insets: [15mm, 30mm, 45mm]
    groove: 3mm
    depth: 2mm
```

#### XPanel

X-pattern decoration:

```yaml
- XPanel:
    bar_width: 50mm
    depth: 6mm
```

#### Wave

Wavy groove pattern:

```yaml
- Wave:
    count: 5
    amplitude: 10mm
    wavelength: 60mm
    groove: 3mm
    depth: 2mm
```

#### HoleGrid

Grid of holes:

```yaml
- HoleGrid:
    spacing: 50mm
    diameter: 6.35mm
    depth: through
    pattern: rectangular  # rectangular | hexagonal | offset
    inset: 25mm
    align: center        # center | corner
```

#### MeasurementEdge

Ruler marks on edges:

```yaml
- MeasurementEdge:
    edges: [top, left]
    unit: metric         # metric | imperial | custom
    minor_spacing: 1mm   # Custom minor tick spacing (overrides unit preset)
    major_spacing: 10mm  # Custom major tick spacing (overrides unit preset)
    minor_length: 3mm
    major_length: 6mm
    depth: 0.3mm
    minor_ticks: true    # Include minor tick marks
    labels: true
    label_height: 4mm
    label_offset: 8mm    # Label offset from edge
    label_interval: 5    # Label every Nth major tick
    label_start: 0       # Starting label value
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| edges | yes | - | Edges to mark: top, bottom, left, right |
| unit | no | metric | Preset spacing (metric: 10mm major/1mm minor) |
| major_spacing | no | - | Custom major tick spacing |
| minor_spacing | no | - | Custom minor tick spacing |
| minor_length | no | 3mm | Minor tick mark length |
| major_length | no | 6mm | Major tick mark length |
| depth | no | 0.3mm | Engrave depth |
| minor_ticks | no | true | Include minor tick marks |
| labels | no | false | Include numeric labels |
| label_height | no | 3mm | Label text height |
| label_offset | no | - | Label offset from edge |
| label_interval | no | 1 | Label every Nth major tick |
| label_start | no | 0 | Starting label value |

#### MeasurementGrid

Full measurement grid with tick marks on all edges and optional labels:

```yaml
- MeasurementGrid:
    unit: metric         # metric | imperial | custom
    depth: 0.5mm
    minor_ticks: true
    labels: true
    label_height: 3mm
    label_interval: 1
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| unit | no | metric | Preset spacing (metric: 10mm major/1mm minor) |
| major_spacing | no | - | Custom major tick spacing |
| minor_spacing | no | - | Custom minor tick spacing |
| minor_length | no | 3mm | Minor tick mark length |
| major_length | no | 6mm | Major tick mark length |
| depth | no | 0.5mm | Engrave depth |
| minor_ticks | no | true | Include minor tick marks |
| labels | no | false | Include numeric labels |
| label_height | no | 3mm | Label text height |
| label_offset | no | - | Label offset from edge |
| label_interval | no | 1 | Label every Nth major tick |
| label_start | no | 0 | Starting label value |

#### GridLines

Interior grid lines spanning edge-to-edge (graph paper / cutting mat style):

```yaml
- GridLines:
    unit: metric         # metric | imperial | custom
    depth: 0.3mm
    minor_lines: true    # include minor grid lines
```

Parameters:
- `unit`: Preset spacing (metric: 10mm major/1mm minor, imperial: 1"/1/16")
- `spacing`: Custom major line spacing (alternative to unit)
- `minor_spacing`: Custom minor line spacing
- `depth`: Engrave depth
- `minor_lines`: Include minor grid lines between major lines

For labeled grids, combine with MeasurementEdge:

```yaml
- GridLines:
    unit: metric
    depth: 0.3mm
- MeasurementEdge:
    edges: [bottom, left]
    unit: metric
    labels: true
    depth: 0.3mm
```

#### EngraveText

Text engraving:

```yaml
- EngraveText:
    text: "FRONT"
    height: 4mm         # Default: 4mm
    depth: 0.3mm        # Default: 0.3mm
    font: rowmans
    alignment: center   # left | center | right
    orientation: horizontal
```

#### SvgStamp

Mill vector artwork from SVG files or inline path data:

```yaml
- SvgStamp:
    path: "logo.svg"          # SVG file path (relative to PML file) or inline SVG path data
    depth: 0.3mm              # Required. Machining depth, or "through"
    feature: engrave           # engrave | pocket | profile (default: engrave)
    scale: fit                 # fit | fill | none (default: fit)
    svg_unit: 1.0             # SVG-unit-to-mm factor, only used when scale: none (default: 1.0)
    center: true              # Center artwork within domain (default: true)
    invert_y: true            # Flip Y axis for SVG y-down → CNC y-up (default: true)
```

Inline path data example:

```yaml
- SvgStamp:
    path: "M 0 0 L 100 0 L 100 60 L 0 60 Z"
    depth: through
    feature: profile
    scale: fit
```

SvgStamp is a leaf node — it does not accept children.

SVG files must contain `<path>` elements. Non-path elements (`<rect>`, `<circle>`, etc.) require "Object to Path" conversion in the design tool.

### Assembly Generators

#### Assembly

Multi-panel assembly with interface-first architecture. Each assembly type (box, carcass, cubby) generates panels and their joinery based on explicit interface specifications.

**Core Concept:** Assemblies are built from panels joined at interfaces. Each interface selects one joinery strategy. Edge-based joinery (butt, finger, step, rabbet) modifies panel edges. Face-based joinery (half-lap, captured, dado) modifies panel faces.

##### Box Assembly

A closed box with four sides and optional top/bottom panels:

```yaml
# Simple finger-jointed box (default)
- Assembly:
    type: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 6mm
    joinery: finger           # Default for side-to-side interfaces
    finger_width: 12mm
    bottom: captured          # Default: captured in dado
    top: none                 # No top panel
```

```yaml
# Box with finger-jointed bottom
- Assembly:
    type: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    bottom: finger            # Bottom uses finger joints too
    show_labels: true
```

##### Carcass Assembly

Open-sided cabinet with optional back, shelves, and partitions:

```yaml
# Simple carcass with butt joints
- Assembly:
    type: carcass
    width: 600mm
    depth: 560mm
    height: 720mm
    thickness: 18mm
    joinery: butt
    cap_style: between_sides  # Cap sits between side panels
    top: butt
    bottom: butt
```

```yaml
# Frameless cabinet with back and shelves
- Assembly:
    type: carcass
    width: 600mm
    depth: 560mm
    height: 720mm
    thickness: 18mm
    cap_style: between_sides
    back_thickness: 6mm       # Captured back panel
    back_inset: 18mm          # Setback from rear
    fixed_shelves: 2
    shelf_joinery: captured   # Shelves in dados
    show_labels: true
```

```yaml
# Carcass with partitions
- Assembly:
    type: carcass
    width: 1200mm
    depth: 400mm
    height: 800mm
    thickness: 18mm
    fixed_shelves: 2
    vertical_partitions: 3
    shelf_joinery: dado
    partition_joinery: dado
```

##### Cubby Assembly

Grid of cubbies with perimeter and internal joinery:

```yaml
# 3x2 cubby grid
- Assembly:
    type: cubby
    width: 900mm
    depth: 300mm
    height: 600mm
    thickness: 18mm
    grid: [3, 2]              # cols, rows
    perimeter_joinery: finger
    internal_joinery: half_lap
    finger_width: 15mm
```

```yaml
# Cubby with captured back
- Assembly:
    type: cubby
    width: 900mm
    depth: 300mm
    height: 600mm
    thickness: 18mm
    grid: [4, 3]
    perimeter_joinery: finger
    internal_joinery: half_lap
    back_thickness: 6mm
    back_inset: 18mm
    show_labels: true
```

##### Joinery Types

| Joinery | Removal | Valid Interfaces | Description |
|---------|---------|------------------|-------------|
| `butt` | None | All | Simple butt joint, no modification |
| `finger` | Edge | side_to_side, top, bottom | Alternating finger pattern |
| `step` | Edge | side_to_side, top, bottom | Half-lap step on each panel |
| `rabbet` | Edge | side_to_side, top, bottom | Shoulder cut on receiving panel |
| `captured` | Face | top, bottom | Dados in side panels for cap |
| `dado` | Face | top, bottom, internal | Groove in receiving panel |
| `half_lap` | Face | internal | Cross-lap at intersection (t/2 each) |

##### Parameters

**Common Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| type | yes | - | Assembly type: box, carcass, cubby |
| width | yes | - | Outer width (X dimension) |
| depth | yes | - | Outer depth (Y dimension) |
| height | yes | - | Outer height (Z dimension) |
| thickness | yes | - | Material thickness |
| joinery | no | finger | Default joinery for side interfaces |
| finger_width | no | 12mm | Target finger width |
| finger_count | no | - | Explicit finger count (alternative to width) |
| clearance | no | 0.12mm | Joint fit clearance |
| layout_gap | no | 10mm | Gap between laid-out panels |
| show_labels | no | false | Display panel name labels |
| show_edge_colors | no | false | Display edge color visualization |

**Box Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| top | no | none | Top joinery: none, finger, captured, dado |
| bottom | no | captured | Bottom joinery: none, finger, captured, dado |

**Carcass Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| cap_style | no | between_sides | Cap placement: between_sides, over_sides |
| top | no | none | Top panel joinery |
| bottom | no | captured | Bottom panel joinery |
| back | no | none | Back panel joinery strategy |
| back_thickness | no | - | Back panel thickness (enables captured back) |
| back_inset | no | 0mm | Back panel setback from rear edge |
| back_joinery | no | - | Alternative back joinery specification |
| back_rabbet_depth | no | - | Depth of rabbet/dado for back panel |
| back_internal_support | no | true | Internal bracing for back panel |
| fixed_shelves | no | 0 | Number of fixed shelves |
| shelf_joinery | no | captured | Shelf-to-side joinery |
| shelf_dado_depth | no | t/2 | Shelf dado depth |
| shelf_back_support | no | false | Add back panel support for shelves |
| vertical_partitions | no | 0 | Number of vertical dividers |
| partition_joinery | no | captured | Partition-to-cap joinery |
| partition_dado_depth | no | t/2 | Partition dado depth |
| toe_kick_height | no | - | Height of toe kick cutout |
| toe_kick_depth | no | - | Depth (setback) of toe kick from front |
| toe_kick_style | no | open | Toe kick style: open, between_sides, over_sides |
| toe_kick_cover | no | false | Add a cover panel for toe kick |

**Cubby Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| grid | yes | - | Grid dimensions: [cols, rows] |
| perimeter_joinery | no | finger | Joinery for outer box |
| internal_joinery | no | half_lap | Joinery for shelf/partition intersections |
| back_thickness | no | - | Back panel thickness (enables captured back) |
| back_inset | no | 0mm | Back panel setback from rear edge |

##### Multi-Sheet Partitioning

When an assembly's panels exceed the sheet's working area, the system automatically partitions panels across multiple sheets. No PML syntax change is needed — partitioning is triggered by panel dimensions vs sheet size.

Each sheet produces its own G-code and SVG output with `_sheet_N` suffixed filenames plus a `manifest.json` listing all sheets. Panel labels (`show_labels: true`) are essential for identifying which panel belongs where across sheets.

```yaml
# This box's panels won't fit on a 500×500mm sheet — automatic 3-sheet output
Sheet:
  width: 500mm
  height: 500mm
  thickness: 6mm
  margin: 10mm
  material: mdf
children:
- Assembly:
    type: box
    width: 400mm
    depth: 300mm
    height: 200mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    bottom: captured
    top: none
    show_labels: true
```

**Constraints:**
- Assembly panels are never rotated (joinery is edge-specific)
- Mixed content (shapes + overflowing assembly) is an error — move the assembly to its own PML file
- Beam assemblies do not support multi-sheet partitioning
- Panels too large for a single sheet produce a hard error

### Utility Nodes

#### AtPosition

Explicit positioning within parent:

```yaml
- AtPosition:
    x: 100mm
    y: 50mm
    width: 200mm    # Optional
    height: 150mm   # Optional
    child:
      Pocket: {depth: 6mm}
```

#### Subtract

Ring by subtracting inner from outer:

```yaml
- Subtract:
    inner_inset: 50mm
    children:
      - Pocket: {depth: 5mm}
```

#### Shell

Contour-following hollow border on any closed shape. Insets the parent shape by `wall` and removes the interior as a profile (through-cut) or pocket. Children are applied to the resulting ring (wall face).

```yaml
- Polygon:
    points: [[0,0], [200,0], [200,150], [100,200], [0,150]]
    children:
    - Profile: {side: outside, depth: through}
    - Shell:
        wall: 15mm
        interior: profile
```

Pocket interior with wall chamfer:

```yaml
- Circle:
    diameter: 200mm
    children:
    - Shell:
        wall: 20mm
        interior: pocket
        depth: 8mm
        children:
        - Chamfer: {width: 3mm, depth: 2mm}
```

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `wall` | dimension | yes | — | Wall thickness |
| `interior` | string | yes | — | `"profile"` (through-cut) or `"pocket"` (flat-bottom) |
| `depth` | dimension/string | no | `through` | Depth for interior removal. Required when `interior: pocket` |
| `children` | list | no | — | Operations applied to wall ring (Chamfer, Roundover, Pocket, etc.) |

#### Place

Container with optional layout manager for positioning children:

```yaml
- Place:
    layout:
      Grid: {rows: 2, cols: 3, gap: 10mm}
    children:
      - Circle: {diameter: 20mm, feature: {type: hole, depth: through}}
```

#### Edge

Edge treatment specification for profile cross-section callouts:

```yaml
- Edge:
    treatment: chamfer
    distance: 5mm
    rough_allowance: 1mm
    finish_allowance: 0.2mm
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| treatment | yes | - | Treatment type identifier |
| rough_allowance | no | - | Rough pass allowance |
| finish_allowance | no | - | Finish pass allowance |
| radius | no | - | Radius for rounded treatments |
| distance | no | - | Distance parameter |

#### Engrave

Shorthand for an engrave feature:

```yaml
- Engrave:
    depth: 0.5mm
```

Equivalent to `feature: {type: engrave, depth: 0.5mm}` on the parent shape.

#### Keepout

No-machining zone:

```yaml
- Keepout:
    id: clamp_zone
    children:
      - Rect: {at: {x: 100mm, y: 100mm, width: 50mm, height: 50mm}}
```

#### WasteCuts

Decompose remaining sheet into usable pieces:

```yaml
- WasteCuts:
    min_width: 200mm    # Default: 200mm
    min_height: 200mm   # Default: 200mm
    margin: 5mm         # Optional safety margin around parts
    tab_count: 4
    tab_height: 3mm
    strategy: largest   # largest | simple
```

#### Beam

Laminated 3D member that expands to multiple panel layers. Beams enable building furniture with structural wooden members (posts, rails, legs) from plywood sheets.

```yaml
- Beam:
    name: post_left
    length: 800mm      # Total beam length (U dimension)
    width: 76mm        # Cross-section height (V dimension)
    thickness: 19mm    # Per-layer sheet thickness
    layers: 3          # Number of laminated layers
    role: POST         # Optional: POST, RAIL, LEG, APRON, STRETCHER, STILE, MUNTIN
```

##### Beam Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | yes | - | Beam identifier |
| length | yes | - | Total beam length (U dimension) |
| width | yes | - | Cross-section height (V dimension) |
| thickness | yes | - | Per-layer sheet thickness |
| layers | yes | - | Number of layers (int) or explicit LayerSpec list |
| role | no | - | Beam role: POST, RAIL, LEG, APRON, STRETCHER, STILE, MUNTIN |
| show_labels | no | false | Display panel name labels on each beam segment |

##### Splicing

When beam length exceeds sheet size, layers are automatically spliced with staggered butt joints:

```yaml
- Beam:
    name: long_rail
    length: 2000mm     # Exceeds typical sheet size
    width: 100mm
    thickness: 19mm
    layers: 3          # Stagger = sheet_size / layers
```

##### Explicit Layer Specs

For beams with varying layer lengths (e.g., integral tenons):

```yaml
- Beam:
    name: rail_with_tenon
    length: 500mm
    width: 100mm
    thickness: 19mm
    layers:
      - {length: 500mm}               # Outer layer
      - {length: 538mm, offset: 0mm}  # Center extends for tenon
      - {length: 500mm}               # Outer layer
```

##### Beam Features

Features can be added to faces, ends, or edges:

```yaml
- Beam:
    name: post
    length: 800mm
    width: 76mm
    thickness: 19mm
    layers: 3
    face_features:
      - SquareMortise:
          x: 200mm
          y: 38mm
          width: 38mm
          height: 50mm
          depth: 19mm
    edge_features:
      - Chamfer:
          edge: top
          width: 3mm
          layers: outer    # outer (default) or all
    end_features:
      - Tenon:
          end: right
          extension: 38mm
          width: 100mm
          height: 19mm
          layers: center
```

##### Face Features

| Feature | Parameters | Description |
|---------|------------|-------------|
| DrillHole | x, y, diameter, depth, face, stage | Drill hole on face |
| SquareMortise | x, y, width, height, depth, face | Rectangular mortise |
| CarvedDesign | x, y, design, depth, face | Reference to design template |
| GeometricPattern | x, y, pattern_type, params, depth | Geometric pattern (fluting, etc) |

##### End Features

| Feature | Parameters | Description |
|---------|------------|-------------|
| Tenon | end, extension, width, height, layers | Projecting tenon |
| EndCap | end, profile, params | End profile (square, rounded, etc) |
| EndProfile | end, contour | Custom contour points |

##### Edge Features

| Feature | Parameters | Description |
|---------|------------|-------------|
| Chamfer | edge, width, angle_deg, layers | Chamfered edge |
| Fillet | edge, radius, layers | Rounded edge |
| Rabbet | edge, width, depth, layers | Step profile |
| EdgeDado | edge, position, width, depth, layers | Groove on edge |
| EdgeNotch | edge, position, width, depth, layers | Notch on edge |
| EdgeContour | edge, contour, layers | Custom edge profile |

Edge features default to `layers: outer` (first and last layers only) since middle layer edges are hidden by lamination. Use `layers: all` for structural features.

## Features

Features can be specified inline on shapes:

```yaml
- Rect:
    feature:
      type: profile
      side: outside
      depth: through
      tab_count: 4
      tab_height: 3mm
```

Or as generator children:

```yaml
- Rect:
    children:
      - Profile:
          side: outside
          depth: through
```

### Feature Types

| Type | Description |
|------|-------------|
| `profile` | Cut around boundary |
| `pocket` | Clear enclosed area |
| `hole` | Drill/bore operation |
| `engrave` | Shallow surface marking |

### Rest Pocketing

Two-stage pocket machining: a large tool clears bulk material (rough pass), then a smaller tool clears remaining unmachined corners and profiles the perimeter (rest pass). Produces better surface finish and faster cycle times for deep or wide pockets.

Simple form (default allowances: rough 0.5mm, finish 0mm):

```yaml
- Rect:
    feature:
      type: pocket
      depth: 12mm
      rest_tool: 6mm
    at:
      x: 100mm
      y: 100mm
      width: 200mm
      height: 150mm
```

Explicit form:

```yaml
- Rect:
    feature:
      type: pocket
      depth: 12mm
      rest:
        tool: 6mm
        rough_allowance: 0.5mm
        finish_allowance: 0.0mm
    at:
      x: 100mm
      y: 100mm
      width: 200mm
      height: 150mm
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `tool` / `rest_tool` | yes | — | Finish tool diameter |
| `rough_allowance` | no | `0.5mm` | Stock left by rough pass on all walls |
| `finish_allowance` | no | `0mm` | Final surface allowance after rest pass |

Only supported on rectangular pocket shapes (Rect, Polygon). Cannot specify both `rest` and `rest_tool`. Mutually exclusive with `edge_treatment: {type: allowance}` — rest pocketing subsumes the allowance pattern by adding a tool change between passes.

The rough pass uses the standard `pocket` operation name. Only the rest pass introduces `pocket_rest`. Operator workflow: run `pocket-*.nc`, tool change, run `pocket_rest-*.nc`.

### Corner Cleanup

Pocket features can specify a secondary tool pass at each corner for better corner access:

```yaml
- Rect:
    feature:
      type: pocket
      depth: 6mm
      corner_cleanup: 3.175mm
```

The `corner_cleanup` value is the diameter of the cleanup tool. A circular bore pocket is cut at each rectangular corner using this smaller tool.

### Dogbone Fillets

Pocket features can specify dogbone fillets to provide clearance at internal corners for mating parts. CNC routers leave tool-radius fillets at internal corners; dogbone bores at each corner allow square parts to fit.

Simple form (default style, auto tool selection):

```yaml
- Rect:
    feature:
      type: pocket
      depth: 9.5mm
      dogbone: true
```

Explicit parameters:

```yaml
- Rect:
    feature:
      type: pocket
      depth: 9.5mm
      dogbone:
        style: t-bone_x       # dogbone | t-bone_x | t-bone_y
        diameter: 3.175mm      # tool diameter (default: smallest flat tool)
        overcut: 0.5mm         # extend past corner (default: 0)
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `style` | no | `dogbone` | Fillet style: `dogbone` (diagonal), `t-bone_x` (X-axis), `t-bone_y` (Y-axis) |
| `diameter` | no | smallest flat tool | Tool diameter for the bore |
| `overcut` | no | `0` | Extra material removal beyond tool radius |

Only supported on rectangular pockets (including assembly dados).

#### Assembly Joinery Dogbone

All joinery strategies that produce internal corners (`Captured`, `Finger`, `HalfLap`) emit dogbone bores automatically using the default diagonal style. No PML configuration is needed for default behavior.

Three-way semantics on interface configs:

| PML | Meaning |
|-----|---------|
| *(absent)* | Use strategy default (dogbone on) |
| `dogbone: false` | Explicitly suppress dogbone on this interface |
| `dogbone: { style: t-bone_x }` | Override style |

```yaml
- Assembly:
    type: carcass
    width: 400mm
    depth: 350mm
    height: 500mm
    thickness: 18mm
    shelf_joinery:
      joinery: captured
      dogbone:
        style: t-bone_x
    bottom:
      joinery: captured
      dogbone: false
```

The `dogbone` parameter on an interface config accepts: `false` to suppress, or a dict with `style`, `diameter`, and `overcut` to override.

### Feed Overrides

Features can optionally override resolved feeds/speeds. This lets operators slow down a specific cut without changing the global feeds table.

```yaml
- Rect:
    feature:
      type: pocket
      depth: 6mm
      feeds:
        rpm: 14000
        feed_xy: 600
        feed_z: 200
```

Or on generator children:

```yaml
- Rect:
    children:
      - Profile:
          side: outside
          depth: through
          feeds:
            rpm: 14000
```

All fields in the `feeds:` block are optional — only specified fields override the material-resolved defaults:

| Field | Description |
|-------|-------------|
| `rpm` | Spindle speed override |
| `feed_xy` | XY feed rate override (mm/min) |
| `feed_z` | Plunge feed rate override (mm/min) |
| `depth_per_pass` | Depth per pass override (mm) |
| `stepover_percent` | Stepover percentage override |

## Components

Reusable components with parameters:

```yaml
components:
  door_panel:
    params:
      stile_width: 57mm
      panel_depth: 6mm
    body:
      Rect:
        children:
          - Profile: {side: outside, depth: through}
          - Frame:
              width: ${stile_width}  # Parameter reference
              children:
                - Pocket: {depth: ${panel_depth}}

children:
  - UseComponent:
      name: door_panel
      args:
        stile_width: 65mm
        panel_depth: 8mm
```

## JSON Schema

JSON Schema files for IDE validation:

- `pml/schema/pml.schema.json` - PML document schema
- `pml/schema/nest.schema.json` - Nesting job schema

Configure your IDE to use these schemas for `.pml.yml` files.
