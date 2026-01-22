# Domain/Generator System

The domain/generator system separates **where** to machine (domains) from **what** to machine (generators). This enables hundreds of SKUs from a small set of composable primitives.

```
Domain Composition → Generators → LayoutAST → RemovalIntent → G-code
```

## Quick Start

```python
from domains import Domain
from generators import profile_generator, flat_pocket_generator, ProfileParams, FlatPocketParams
from layout_ast.layout import LayoutAST, Sheet
from adapters.ast_to_removal import ast_to_removal_intents

# 1. Define regions
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(50).domains[0]  # 50mm frame

# 2. Generate machining operations
profile_items = profile_generator(outer, ProfileParams(side="outside", depth="through"))
pocket_items = flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))

# 3. Build AST and convert to IR
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)
intents = ast_to_removal_intents(ast)
```

## Domain API

### Constructors

| Method | Description |
|--------|-------------|
| `Domain.from_rectangle(width, height, center, rotation_rad)` | Create rectangular domain |
| `Domain.from_polygon(vertices, holes, local_origin, local_rotation_rad)` | Create from explicit vertices |
| `Domain.from_arch(width, height, arch_radius, center, arc_segments)` | Create rectangle with arched top |

### Algebraic Operations

All operations return `MultiDomain` (may contain 0, 1, or many domains).

| Operation | Description | Example |
|-----------|-------------|---------|
| `inset(distance)` | Contract boundary inward | `panel = door.inset(50).domains[0]` |
| `offset(distance)` | Expand boundary outward | `larger = door.offset(10).domains[0]` |
| `subtract(other)` | Remove overlapping region | `frame = outer.subtract(inner).domains[0]` |
| `intersect(other)` | Keep only overlap | `overlap = a.intersect(b).domains[0]` |

### Split Operations

| Operation | Description | Example |
|-----------|-------------|---------|
| `split_horizontal(n, gap_mm)` | Divide into n rows | `rows = panel.split_horizontal(3, gap_mm=20)` |
| `split_vertical(n, gap_mm)` | Divide into n columns | `cols = panel.split_vertical(2, gap_mm=20)` |
| `split_grid(rows, cols, gap_mm)` | Divide into grid | `cells = panel.split_grid(2, 2, gap_mm=20)` |

All split operations accept `local_coords=True` to split along the domain's rotated local axes instead of sheet axes.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `bounds` | `Bounds2D` | Axis-aligned bounding box |
| `area_mm2` | `float` | Area in square millimeters |
| `centroid` | `Point2D` | Geometric center |
| `outer_boundary` | `Boundary` | Outer edge vertices (CCW) |
| `inner_boundaries` | `tuple[Boundary, ...]` | Hole vertices (CW) |
| `local_origin` | `Point2D` | Origin for local coordinate system |
| `local_rotation_rad` | `float` | Rotation of local X-axis |

### MultiDomain

Operations return `MultiDomain` to handle cases where results split into multiple regions.

```python
result = outer.inset(50)

if result.is_empty:
    raise ValueError("Inset too large")

for domain in result:
    items.extend(generator(domain, params))

# Or access directly
first_domain = result.domains[0]
```

## Generator Catalog

### Area Generators

Fill 2D regions with machining operations.

| Generator | Params Class | Use Case |
|-----------|--------------|----------|
| `flat_pocket_generator` | `FlatPocketParams` | Uniform depth pocket |
| `wave_generator` | `WaveParams` | Sinusoidal wave pattern |
| `grid_generator` | `GridParams` | Crosshatch grid lines |
| `raised_panel_generator` | `RaisedPanelParams` | Traditional raised panel bevel |
| `line_pattern_generator` | `LinePatternParams` | Parallel lines at any angle |
| `concentric_border_generator` | `ConcentricBorderParams` | Nested contour-following grooves |
| `hole_grid_generator` | `HoleGridParams` | Regular pattern of holes (pegboard, ventilation) |

### Loop Generators

Follow domain boundaries.

| Generator | Params Class | Use Case |
|-----------|--------------|----------|
| `profile_generator` | `ProfileParams` | Cut along boundary (through or partial) |
| `bead_generator` | `BeadParams` | Decorative groove along boundary |
| `chamfer_generator` | `ChamferParams` | Angled edge cut |

### SVG Generators

| Generator | Params Class | Use Case |
|-----------|--------------|----------|
| `svg_stamp_generator` | `SVGPathParams` | Engrave SVG paths |

## Parameter Reference

### FlatPocketParams

```python
FlatPocketParams(
    depth_mm: float,        # Pocket depth (required, positive)
    allowance_mm: float = 0.0,  # Inward allowance from boundary
)
```

### ProfileParams

```python
ProfileParams(
    side: "outside" | "inside" | "on",  # Cut position relative to boundary
    depth: "through" | float,           # Cut depth
    loop_selection: LoopSelection = "outer_only",  # Which boundaries to cut
    tab_count: int = 0,                 # Number of holding tabs
    tab_width_mm: float = 10.0,         # Tab width
    tab_height_mm: float = 3.0,         # Tab height above cut
)
```

**Loop selection options:**
- `"outer_only"` - Only the outer boundary
- `"inner_only"` - Only inner boundaries (holes)
- `"all_loops"` - All boundaries
- `[0, 2]` - Specific indices (0=outer, 1+=inner)

### WaveParams

```python
WaveParams(
    amplitude_mm: float,      # Wave height from centerline
    wavelength_mm: float,     # Distance between peaks
    depth_mm: float,          # Groove depth
    direction_rad: float = 0.0,   # Wave direction (0=along X)
    phase_rad: float = 0.0,       # Phase offset
    tool_width_mm: float = 3.175, # Tool width for line spacing
    wave_count: int | None = None,  # Fixed count or fit to domain
)
```

### GridParams

```python
GridParams(
    spacing_x_mm: float,    # Horizontal line spacing
    spacing_y_mm: float,    # Vertical line spacing
    line_width_mm: float,   # Groove width
    depth_mm: float,        # Groove depth
    offset_x_mm: float = 0.0,  # Grid origin X offset
    offset_y_mm: float = 0.0,  # Grid origin Y offset
)
```

### RaisedPanelParams

```python
RaisedPanelParams(
    border_width_mm: float,   # Width of angled border
    border_depth_mm: float,   # Depth at outer edge (deeper)
    field_depth_mm: float,    # Depth of center field (shallower)
    angle_degrees: float = 15.0,  # Bevel angle (informational)
)
```

### BeadParams

```python
BeadParams(
    width_mm: float,          # Bead groove width
    depth_mm: float,          # Bead groove depth
    offset_mm: float = 0.0,   # Distance from boundary to centerline
    loop_selection: LoopSelection = "outer_only",
)
```

### ChamferParams

```python
ChamferParams(
    width_mm: float,          # Horizontal chamfer width
    depth_mm: float,          # Vertical chamfer depth
    loop_selection: LoopSelection = "outer_only",
)
```

### LinePatternParams

```python
LinePatternParams(
    angle_deg: float = 0.0,     # Line angle (0=horizontal, 90=vertical)
    spacing_mm: float = 25.0,   # Distance between lines
    line_width_mm: float = 4.0, # Groove width
    depth_mm: float = 3.0,      # Groove depth
)
```

### ConcentricBorderParams

```python
ConcentricBorderParams(
    insets_mm: tuple[float, ...],  # Inset distances, e.g., (15.0, 30.0, 45.0)
    groove_width_mm: float = 3.0,  # Groove width
    depth_mm: float = 2.0,         # Groove depth
)
```

### HoleGridParams

```python
HoleGridParams(
    spacing_mm: float,              # Center-to-center distance between holes
    diameter_mm: float,             # Hole diameter
    depth_mm: "through" | float,    # Hole depth or "through"
    pattern: "rectangular" | "hexagonal" | "offset" = "rectangular",
    inset_mm: float = 0.0,          # Additional inset from domain boundary
    align: "center" | "corner" = "center",  # Grid alignment within domain
)
```

**Pattern options:**
- `"rectangular"` - Standard grid aligned to X/Y axes
- `"hexagonal"` - Honeycomb pattern (rows offset by spacing/2, row spacing × √3/2)
- `"offset"` - Like rectangular but alternating rows offset by spacing/2

### SVGPathParams

```python
SVGPathParams(
    svg_path: str,            # SVG path data (d attribute)
    depth_mm: float,          # Engrave depth
    scale: float = 1.0,       # Scale factor
    center: Point2D | None = None,  # Placement center
)
```

## Common Patterns

### Shaker Door

```python
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(50).domains[0]

items = []
items.extend(profile_generator(outer, ProfileParams(side="outside", depth="through")))
items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))
```

### Four-Panel Door

```python
outer = Domain.from_rectangle(500, 700, center=(250, 350))
panel_region = outer.inset(65).domains[0]
cells = panel_region.split_grid(2, 2, gap_mm=35)

items = []
items.extend(profile_generator(outer, ProfileParams(side="outside", depth="through")))
for cell in cells:
    items.extend(raised_panel_generator(cell, RaisedPanelParams(
        border_width_mm=20,
        border_depth_mm=8,
        field_depth_mm=2,
    )))
```

### Beaded Frame

```python
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(60).domains[0]
frame = outer.subtract(panel).domains[0]

items = []
items.extend(profile_generator(outer, ProfileParams(side="outside", depth="through")))
items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))
items.extend(bead_generator(frame, BeadParams(
    width_mm=6.0,
    depth_mm=3.0,
    offset_mm=15.0,
    loop_selection="inner_only",  # Bead around panel opening
)))
```

### Pegboard Panel

```python
from generators import hole_grid_generator, HoleGridParams

panel = Domain.from_rectangle(600, 400, center=(300, 200))
inner = panel.inset(25).domains[0]  # Keep holes away from edges

items = []
items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))
items.extend(hole_grid_generator(inner, HoleGridParams(
    spacing_mm=25.0,
    diameter_mm=6.35,  # 1/4" holes
    depth_mm="through",
    pattern="rectangular",
)))
```

### Ventilation Panel with Keepout

```python
panel = Domain.from_rectangle(400, 300, center=(200, 150))
motor_mount = Domain.from_rectangle(80, 80, center=(200, 150))
vent_region = panel.subtract(motor_mount).domains[0]

items = hole_grid_generator(vent_region, HoleGridParams(
    spacing_mm=15.0,
    diameter_mm=8.0,
    depth_mm="through",
    pattern="hexagonal",  # Honeycomb for max airflow
))
```

### Custom Polygon

```python
import math

radius = 100.0
center = (150, 150)
vertices = [
    (center[0] + radius * math.cos(math.radians(60 * i)),
     center[1] + radius * math.sin(math.radians(60 * i)))
    for i in range(6)
]

hexagon = Domain.from_polygon(vertices)
items = profile_generator(hexagon, ProfileParams(side="outside", depth="through"))
```

## Coordinate System

Domains maintain two coordinate systems:

- **Sheet coordinates**: Absolute position on the material sheet
- **Local coordinates**: Relative to the domain's origin and rotation

Most operations work in sheet coordinates. Use `local_coords=True` on split operations when working with rotated domains:

```python
rotated = Domain.from_rectangle(400, 600, center=(200, 300), rotation_rad=math.pi/4)
cells = rotated.split_grid(2, 2, local_coords=True)  # Grid aligns to rotated axes
```

## Error Handling

Generators raise `ValueError` for invalid parameters. Use `allow_empty=True` to return empty lists instead:

```python
# Raises if domain too small
items = wave_generator(tiny_domain, params)

# Returns [] if domain too small
items = wave_generator(tiny_domain, params, allow_empty=True)
```

Check `MultiDomain.is_empty` after operations that might produce no results:

```python
result = domain.inset(huge_distance)
if result.is_empty:
    raise ValueError("Inset distance exceeds domain size")
```

## See Also

- [Recipe 19: Domain/Generator Basics](recipes/19_domain_generator_basics/README.md) - Tutorial with examples
- [Recipe 21-30](recipes/) - Domain/generator recipe examples
- [CLAUDE.md](../CLAUDE.md) - AI development guide with domain/generator patterns
