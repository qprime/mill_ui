# Nest Job Syntax Specification

Nest job files (`.nest.yml`) define bin-packing jobs for optimizing part placement on stock sheets using YAML format. They compile to multiple `LayoutAST` objects (one per sheet).

## Design Principles

- **Declarative**: Define parts and quantities, let the algorithm optimize placement
- **Standard format**: Valid YAML with JSON Schema validation
- **Dimension-explicit**: All dimensions use `mm` suffix for clarity
- **Template-aware**: Parts can reference parametric templates (e.g., Shaker doors)

## Quick Example

```yaml
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: large_door
      width: 457mm
      height: 597mm
      quantity: 20
      template:
        name: shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm

    - name: small_door
      width: 305mm
      height: 203mm
      quantity: 15

    - name: tall_door
      width: 457mm
      height: 914mm
      quantity: 2
```

## Document Structure

```yaml
Nest:                           # Required root key
  algorithm: maxrects           # Required: guillotine | maxrects

  Sheet:                        # Required sheet specification
    width: 1200mm
    height: 2400mm
    thickness: 19mm

  kerf: 6.35mm                  # Optional, default 6.35mm
  margin: 10mm                  # Optional, default 10mm

  parts:                        # Required list of parts
    - name: part_name
      width: 400mm
      height: 600mm
      quantity: 20
      template: shaker          # Optional template
```

## Algorithms

### guillotine

Guillotine cutting - creates full-width or full-height cuts across the sheet. Produces simpler cut patterns that work well with panel saws.

```yaml
Nest:
  algorithm: guillotine
```

### maxrects

MaxRects algorithm - higher utilization with free rectangle tracking. Best for mixed part sizes.

```yaml
Nest:
  algorithm: maxrects
```

**Typical utilization:**
- `guillotine`: ~62% for uniform parts
- `maxrects`: ~83% for mixed sizes

## Sheet Specification

```yaml
Sheet:
  width: 1220mm      # Stock sheet width
  height: 2440mm     # Stock sheet height
  thickness: 19mm    # Material thickness
```

**Common stock sheet sizes:**
- Full sheet (4' x 8'): `1220mm x 2440mm`
- Half sheet (4' x 4'): `1220mm x 1220mm`
- Quarter sheet (2' x 4'): `610mm x 1220mm`

## Kerf and Margin

```yaml
kerf: 6.35mm    # Cutter width for spacing between parts (default: 6.35mm / 1/4")
margin: 10mm    # No-cut zone around sheet edges (default: 10mm)
```

## Parts

Each part specifies:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Part identifier (alphanumeric, no spaces) |
| `width` | Yes | Part width in millimeters |
| `height` | Yes | Part height in millimeters |
| `quantity` | No | Number of copies (default: 1) |
| `template` | No | Template to apply to part |
| `shape` | No | Shape primitive (mutually exclusive with `template`) |

### Basic Parts

```yaml
parts:
  - name: shelf
    width: 600mm
    height: 300mm
    quantity: 8

  - name: side_panel
    width: 400mm
    height: 800mm
    quantity: 4
```

### Parts with Templates

Templates can be referenced two ways:

**Simple reference (uses template defaults):**
```yaml
parts:
  - name: door
    width: 400mm
    height: 600mm
    quantity: 10
    template: shaker
```

**With parameter overrides:**
```yaml
parts:
  - name: door
    width: 400mm
    height: 600mm
    quantity: 10
    template:
      name: shaker
      params:
        stile_w: 65mm
        rail_h: 65mm
        panel_recess: 8mm
```

### Template Resolution

- Template names are case-insensitive for file lookup (e.g., `shaker` finds `templates/shaker.pml.yml`)
- Parameters override the template's default values
- Part dimensions (`outer_w`, `outer_h`) are automatically passed to the template

### Built-in Templates

**shaker** - Shaker-style cabinet door with frame and panel:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `stile_w` | 57mm | Stile (vertical frame) width |
| `rail_h` | 57mm | Rail (horizontal frame) height |
| `panel_recess` | 6mm | Panel pocket depth |
| `panel_style` | pocket | Panel generator type |

### Parts with Shape Primitives

The `shape` field specifies a shape primitive instead of the default `Rect`. It is mutually exclusive with `template`.

**Supported shapes:**

| `type` | Additional fields | Notes |
|--------|-------------------|-------|
| `Rect` | *(none)* | Default behavior, equivalent to omitting `shape` |
| `RoundedRect` | `radius` (required), `corners` (optional) | Corners: `tl`, `tr`, `bl`, `br`. Default: all corners |
| `Circle` | *(none)* | `width` must equal `height` (bounding box is square) |
| `Polygon` | `points` (required) | List of `[x, y]` coordinate pairs (min 3) relative to center |
| `Triangle` | *(none)* | Isoceles triangle centered in bounding box |

**RoundedRect with all corners:**
```yaml
parts:
  - name: coaster
    width: 100mm
    height: 100mm
    quantity: 10
    shape:
      type: RoundedRect
      radius: 10mm
```

**RoundedRect with selective corners:**
```yaml
parts:
  - name: edge_strip
    width: 228.6mm
    height: 863.6mm
    quantity: 2
    shape:
      type: RoundedRect
      radius: 12.7mm
      corners: [tl, bl]
```

**Circle:**
```yaml
parts:
  - name: disc
    width: 200mm
    height: 200mm
    quantity: 4
    shape:
      type: Circle
```

**Polygon:**
```yaml
parts:
  - name: gusset
    width: 100mm
    height: 100mm
    quantity: 6
    shape:
      type: Polygon
      points: [[-50, -50], [50, -50], [50, 50]]
```

**Triangle:**
```yaml
parts:
  - name: bracket
    width: 100mm
    height: 80mm
    quantity: 4
    shape:
      type: Triangle
```

## Complete Example

```yaml
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: large_door
      width: 457mm
      height: 597mm
      quantity: 20
      template:
        name: shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm

    - name: small_panel
      width: 305mm
      height: 203mm
      quantity: 15

    - name: tall_door
      width: 457mm
      height: 914mm
      quantity: 2
      template:
        name: shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm
```

## Output

Running a `.nest.yml` file produces:
- Multiple `LayoutAST` objects (one per sheet needed)
- Each sheet contains positioned parts with absolute coordinates
- Templates are expanded to full geometry (profiles, pockets, etc.)

**CLI output files:**
- `{prefix}_{N}.pml.yml` - One PML file per sheet
- `manifest.json` - Nesting summary with utilization metrics
- `{prefix}_{N}.blueprint.{theme}.svg` - Optional SVG blueprints

## CLI Usage

```bash
# Run nesting job
python -m cli.nest --project my_project job.nest.yml

# With verbose output
python -m cli.nest job.nest.yml -v

# With SVG export
python -m cli.nest job.nest.yml -o output/ --export-svg --theme dark
```

## JSON Schema

The nest job schema is available at `pml/schema/nest.schema.json` for IDE validation.

## Migration from Legacy Format

Convert legacy nest files to YAML:

```bash
python -m pml.convert_to_yaml job.nest.yml --dry-run  # Preview
python -m pml.convert_to_yaml job.nest.yml            # Convert in place
```

---

**See Also:**
- [PML Syntax Specification](syntax_spec.md) - For single-sheet layouts
- [Recipe 17: Guillotine Nesting](../docs/recipes/17_nesting_guillotine/)
- [Recipe 18: MaxRects Nesting](../docs/recipes/18_nesting_maxrects/)
