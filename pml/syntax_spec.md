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
    points: [[0, 0], [50, 0], [50, 50], [100, 50]]
    feature: {type: engrave, depth: 0.3mm}

- Spline:
    points: [[0, 0], [25, 10], [50, 0], [75, -10], [100, 0]]
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
    side: outside   # outside | inside | on
    depth: through  # or specific depth like 10mm
    tab_count: 4    # Optional holding tabs
    tab_height: 3mm
    tab_width: 10mm # Optional, auto-calculated if omitted
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
    minor_length: 3mm
    major_length: 6mm
    depth: 0.3mm
    labels: true
    label_height: 4mm
```

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
    height: 10mm
    depth: 0.5mm
    font: rowmans
    alignment: center   # left | center | right
    orientation: horizontal
```

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
| top | no | butt | Top panel joinery |
| bottom | no | butt | Bottom panel joinery |
| back_thickness | no | - | Back panel thickness (enables captured back) |
| back_inset | no | 0mm | Back panel setback from rear edge |
| fixed_shelves | no | 0 | Number of fixed shelves |
| shelf_joinery | no | captured | Shelf-to-side joinery |
| shelf_dado_depth | no | t/2 | Shelf dado depth |
| vertical_partitions | no | 0 | Number of vertical dividers |
| partition_joinery | no | captured | Partition-to-cap joinery |
| partition_dado_depth | no | t/2 | Partition dado depth |

**Cubby Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| grid | yes | - | Grid dimensions: [cols, rows] |
| perimeter_joinery | no | finger | Joinery for outer box |
| internal_joinery | no | half_lap | Joinery for shelf/partition intersections |
| back_thickness | no | - | Back panel thickness (enables captured back) |
| back_inset | no | 0mm | Back panel setback from rear edge |

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
    min_width: 150mm
    min_height: 150mm
    tab_count: 4
    tab_height: 3mm
    strategy: largest  # largest | simple
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

## Migration from Legacy Format

The legacy indent-based PML format has been replaced with YAML. Existing files can be converted using:

```bash
python -m pml.convert_to_yaml path/to/file.pml.yml --dry-run  # Preview
python -m pml.convert_to_yaml path/to/file.pml.yml            # Convert in place
python -m pml.convert_to_yaml --all-recipes                   # Convert all recipes
```
