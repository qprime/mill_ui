# Nest File Syntax Specification

`.nest` files define bin-packing jobs for optimizing part placement on stock sheets. They compile to multiple `LayoutAST` objects (one per sheet).

## Design Principles

- **Declarative**: Define parts and quantities, let the algorithm optimize placement
- **Human-friendly**: Natural indentation, minimal punctuation
- **Dimension-explicit**: All dimensions use `mm` suffix for clarity
- **Template-aware**: Parts can reference parametric templates (e.g., Shaker doors)

## Syntax Overview

```nest
# This is a comment

nest maxrects
    sheet 1220mm 2440mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        door 400mm 600mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        panel 300mm 200mm x15
```

## Grammar

### Nest Declaration (Required, First Directive)

```
nest <algorithm>
```

**Algorithms:**
- `guillotine` - Fast, simple guillotine cuts. Best for uniform parts. ~62% utilization.
- `maxrects` - Higher utilization with free rectangle tracking. Best for mixed sizes. ~83% utilization.

Example:
```nest
nest maxrects
```

### Sheet Declaration (Required)

```
sheet <width>mm <height>mm <thickness>mm
```

Defines the stock sheet dimensions.

Example:
```nest
sheet 1220mm 2440mm 19mm
```

### Kerf Declaration (Optional)

```
kerf <width>mm
```

Cutter width for spacing between parts. Default: `6.35mm` (1/4" endmill).

Example:
```nest
kerf 3.175mm
```

### Margin Declaration (Optional)

```
margin <width>mm
```

No-cut zone around sheet edges. Default: `10mm`.

Example:
```nest
margin 15mm
```

### Parts Block (Required)

```
parts
    <part declarations>
```

Contains one or more part declarations.

### Part Declaration

```
<name> <width>mm <height>mm [x<quantity>]
```

**Fields:**
- `name` - Identifier for this part type (alphanumeric, no spaces)
- `width` - Part width in millimeters
- `height` - Part height in millimeters
- `quantity` - Number of parts to cut (optional, default: 1)

Example:
```nest
parts
    door 400mm 600mm x20
    drawer 200mm 100mm x8
    panel 300mm 200mm
```

### Template Declaration (Optional, Per-Part)

```
template <TemplateName>
    <param> <value>mm
    <param> <value>mm
    ...
```

Associates a parametric template with a part. Template parameters are indented under the template line.

**Available Templates:**
- `Shaker` - Shaker-style cabinet door with frame and panel

**Shaker Template Parameters:**
- `stile_w` - Stile (vertical frame) width
- `rail_h` - Rail (horizontal frame) height
- `panel_recess` - Panel pocket depth

Example:
```nest
parts
    cabinet_door 457mm 597mm x20
        template Shaker
            stile_w 57mm
            rail_h 57mm
            panel_recess 6mm
```

## Complete Example

```nest
# Production run: 37 cabinet parts
# Uses MaxRects for optimal material utilization

nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        # Large shaker doors (18" x 23.5")
        large_door 457mm 597mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        # Small plain panels (12" x 8")
        small_panel 305mm 203mm x15

        # Tall shaker doors (18" x 36")
        tall_door 457mm 914mm x2
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm
```

## Output

Running a `.nest` file produces:
- Multiple `LayoutAST` objects (one per sheet needed)
- Each sheet contains positioned parts with absolute coordinates
- Templates are expanded to full geometry (profiles, pockets, etc.)

## Validation

The parser validates:
- Required directives present (`nest`, `sheet`, `parts`)
- At least one part defined
- Valid numeric values for dimensions
- Valid algorithm name
- Template parameters match expected types

## Common Patterns

### Simple Rectangles (No Template)

```nest
nest guillotine
    sheet 1220mm 2440mm 18mm
    kerf 6.35mm

    parts
        shelf 600mm 300mm x8
        side_panel 400mm 800mm x4
```

### Mixed Parts with Templates

```nest
nest maxrects
    sheet 1220mm 2440mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        door_large 500mm 700mm x10
            template Shaker
                stile_w 60mm
                rail_h 60mm
                panel_recess 6mm

        door_small 400mm 500mm x15
            template Shaker
                stile_w 50mm
                rail_h 50mm
                panel_recess 6mm

        drawer_front 400mm 150mm x20
```

### Standard Sheet Sizes

Common stock sheet sizes:
- Full sheet (4' x 8'): `1220mm 2440mm`
- Half sheet (4' x 4'): `1220mm 1220mm`
- Quarter sheet (2' x 4'): `610mm 1220mm`

---

**See Also:**
- [PML Syntax Specification](syntax_spec.md) - For single-sheet layouts
- [Recipe 17: Guillotine Nesting](../docs/recipes/17_nesting_guillotine/README.md)
- [Recipe 18: MaxRects Nesting](../docs/recipes/18_nesting_maxrects/README.md)
