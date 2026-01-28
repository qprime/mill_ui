# PML (Panel Machining Language) Syntax Specification

PML is a YAML-based declarative language for defining CNC machining layouts. It compiles to LayoutAST.

## Design Principles

- **Declarative**: No control flow, no execution, pure data
- **Standard format**: Valid YAML with JSON Schema validation
- **Dimension-explicit**: All dimensions use `mm` suffix for clarity (e.g., `100mm`)
- **Type-safe**: Shape types, feature types, and parameters are explicit
- **IDE-friendly**: JSON Schema enables autocomplete and validation

## Quick Example

```yaml
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
  margin: 10mm

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
  width: 1200mm
  height: 2400mm
  thickness: 19mm
  margin: 10mm                      # Optional, default 0mm
components:                         # Optional reusable components
  my_component:
    params: {width: 100mm}
    body: {Rect: {children: [...]}}
children:                           # Required - list of child nodes
  - Rect: {...}
  - Circle: {...}
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

Multi-panel assembly with automatic topology, joinery selection, and part layout:

```yaml
# Simple finger-jointed box
- Assembly:
    topology: box       # box | pyramid | prism
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 6mm
    joinery: finger     # finger | butt
    finger_width: 12mm
    clearance: 0.15mm
```

```yaml
# Box with dado bottom
- Assembly:
    topology: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    bottom_style: dado  # captured | finger | dado
    dado_inset: 6mm
    show_labels: true
    show_edge_colors: true
```

```yaml
# Pyramid (butt joints for non-90° angles)
- Assembly:
    topology: pyramid
    base: 150mm
    slant_height: 120mm
    thickness: 6mm
    joinery: butt
```

```yaml
# Frameless cabinet carcass with shelves
- Assembly:
    topology: carcass
    width: 600mm
    depth: 560mm
    height: 720mm
    thickness: 18mm
    joinery: butt
    cap_style: between_sides  # between_sides | over_sides
    back: captured            # none | captured
    back_thickness: 6mm
    back_inset: 18mm
    back_dado_depth: 6mm
    fixed_shelves: 2
    shelf_dado_depth: 6mm
    show_labels: true
    show_edge_colors: true
```

```yaml
# Cubby grid with vertical partitions
- Assembly:
    topology: carcass
    width: 1200mm
    depth: 300mm
    height: 900mm
    thickness: 18mm
    joinery: finger
    finger_width: 15mm
    cap_style: between_sides
    fixed_shelves: 2
    vertical_partitions: 3
    show_labels: true
```

**Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| topology | no | box | Assembly shape (box, pyramid, carcass) |
| width | yes* | - | Outer width (X dimension) |
| depth | yes* | - | Outer depth (Y dimension) |
| height | yes* | - | Outer height (Z dimension) |
| thickness | yes | - | Material thickness |
| joinery | no | finger | Joint type (finger, butt) |
| finger_width | no | - | Target finger width (mutually exclusive with finger_count) |
| finger_count | no | - | Explicit finger count (mutually exclusive with finger_width) |
| clearance | no | 0.1mm | Gap for joint fit |
| include_top | no | false (box), true (carcass) | Generate top panel |
| include_bottom | no | true | Generate bottom panel |
| bottom_style | no | captured | Bottom connection (captured, finger, dado) - box only |
| top_style | no | captured | Top connection (captured, finger, dado) - box only |
| dado_inset | no | 0mm | Distance from wall bottom to dado bottom - box only |
| dado_drop | no | 0mm | Distance from wall top to dado top - box only |
| layout_gap | no | 10mm | Gap between laid-out panels |
| show_labels | no | false | Display panel name labels |
| show_edge_colors | no | false | Display edge color visualization |
| base | pyramid | - | Base dimension for pyramid |
| slant_height | pyramid | - | Slant height for pyramid |
| cap_style | carcass | between_sides | How top/bottom meet sides (between_sides, over_sides) |
| back | carcass | none | Back panel style (none, captured) |
| back_thickness | carcass | thickness | Back panel material thickness |
| back_inset | carcass | 0mm | Distance from rear edge to back panel plane |
| back_dado_depth | carcass | thickness/2 | Depth of back capture dado |
| fixed_shelves | carcass | 0 | Number of uniformly-spaced shelves |
| shelf_dado_depth | carcass | thickness/2 | Depth of shelf dados |
| shelf_setback_front | carcass | 0mm | Shelf inset from front edge |
| shelf_setback_back | carcass | 0mm | Shelf inset from back edge |
| vertical_partitions | carcass | 0 | Number of uniformly-spaced vertical dividers |
| partition_dado_depth | carcass | thickness/2 | Depth of partition dados |

*Required dimensions depend on topology. Box/carcass require width/depth/height; pyramid requires base/slant_height.

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
