# Recipe 19: Domain/Generator Basics

## Goal

Learn how to use the domain/generator system to create complex designs programmatically.

The domain/generator system separates **where** to machine (domains) from **what** to machine (generators), enabling hundreds of SKUs from few primitives.

## Concepts

### Domains

Domains are bounded 2D regions (polygons with optional holes) that support algebraic operations:

| Operation | Description | Result |
|-----------|-------------|--------|
| `inset(d)` | Contract boundary inward by d mm | Smaller domain |
| `offset(d)` | Expand boundary outward by d mm | Larger domain |
| `subtract(other)` | Remove overlapping region | Domain with hole(s) |
| `intersect(other)` | Keep only overlapping region | Intersection |

### Generators

Generators are deterministic functions that produce LayoutAST Items from Domains:

| Type | Generators | Use Case |
|------|-----------|----------|
| **Area** | `flat_pocket_generator`, `wave_generator`, `grid_generator` | Fill regions |
| **Loop** | `profile_generator`, `bead_generator` | Follow boundaries |
| **SVG** | `svg_stamp_generator` | Stamp SVG paths as engravings |

### Pipeline

```
Domain Composition → Generators → LayoutAST → RemovalIntent → G-code
```

## Example 1: Simple Shaker Door

```python
from domains import Domain
from generators import profile_generator, flat_pocket_generator, ProfileParams, FlatPocketParams
from layout_ast.layout import LayoutAST, Sheet
from adapters.ast_to_removal import ast_to_removal_intents

# 1. Create domains
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(50).domains[0]  # Frame is 50mm wide

# 2. Generate items
profile_items = profile_generator(
    outer,
    ProfileParams(side="outside", depth="through"),
)
pocket_items = flat_pocket_generator(
    panel,
    FlatPocketParams(depth_mm=6.0),
)

# 3. Build LayoutAST
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)

# 4. Convert to RemovalIntent IR
intents = ast_to_removal_intents(ast)
print(f"Generated {len(intents)} RemovalIntents")
```

## Example 2: Wave Pattern Panel

```python
from domains import Domain
from generators import profile_generator, wave_generator, ProfileParams, WaveParams
from layout_ast.layout import LayoutAST, Sheet

# Create panel domain
panel = Domain.from_rectangle(300, 200, center=(150, 100))

# Generate profile cut
profile_items = profile_generator(
    panel,
    ProfileParams(side="outside", depth="through"),
)

# Generate wave pattern fill
wave_items = wave_generator(
    panel,
    WaveParams(
        amplitude_mm=8.0,
        wavelength_mm=25.0,
        depth_mm=2.0,
        tool_width_mm=3.175,  # 1/8" bit
    ),
)

# Build AST
ast = LayoutAST(
    sheet=Sheet(width_mm=350, height_mm=250, thickness_mm=19.0),
    items=tuple(profile_items + wave_items),
)

print(f"Generated {len(wave_items)} wave segments")
```

## Example 3: Grid Pattern Panel

```python
from domains import Domain
from generators import profile_generator, grid_generator, ProfileParams, GridParams
from layout_ast.layout import LayoutAST, Sheet

# Create panel domain
panel = Domain.from_rectangle(250, 250, center=(125, 125))

# Generate profile and grid
profile_items = profile_generator(panel, ProfileParams(side="outside", depth="through"))
grid_items = grid_generator(
    panel,
    GridParams(
        spacing_x_mm=25.0,
        spacing_y_mm=25.0,
        line_width_mm=3.175,
        depth_mm=2.0,
    ),
)

ast = LayoutAST(
    sheet=Sheet(width_mm=300, height_mm=300, thickness_mm=19.0),
    items=tuple(profile_items + grid_items),
)
```

## Example 4: Beaded Frame Door

```python
from domains import Domain
from generators import (
    profile_generator, flat_pocket_generator, bead_generator,
    ProfileParams, FlatPocketParams, BeadParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Create domains
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(60).domains[0]  # 60mm frame
frame = outer.subtract(panel).domains[0]  # Frame region with hole

# Generate items
profile_items = profile_generator(outer, ProfileParams(side="outside", depth="through"))
pocket_items = flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))

# Bead around the panel opening (follows inner boundary of frame)
bead_items = bead_generator(
    frame,
    BeadParams(
        width_mm=6.0,
        depth_mm=3.0,
        offset_mm=15.0,
        loop_selection="inner_only",  # Only the panel opening edge
    ),
)

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items + bead_items),
)
```

## Example 5: Custom Polygon Domain

```python
from domains import Domain
from generators import profile_generator, ProfileParams
from layout_ast.layout import LayoutAST, Sheet

# Create a hexagon domain from vertices
import math
radius = 100.0
center = (150, 150)
vertices = [
    (center[0] + radius * math.cos(math.radians(60 * i)),
     center[1] + radius * math.sin(math.radians(60 * i)))
    for i in range(6)
]

hexagon = Domain.from_polygon(vertices)
profile_items = profile_generator(hexagon, ProfileParams(side="outside", depth="through"))

ast = LayoutAST(
    sheet=Sheet(width_mm=300, height_mm=300, thickness_mm=19.0),
    items=tuple(profile_items),
)
```

## Process: Running the Examples

```bash
# Run the integration example
PYTHONPATH=. python3 docs/examples/domain_generator_example.py

# Run domain tests
PYTHONPATH=. python3 tests/test_domain.py

# Run generator tests
PYTHONPATH=. python3 tests/test_generators.py
PYTHONPATH=. python3 tests/test_stage5_generators.py
```

## Output

The domain/generator system produces:
- `list[Item]` from each generator
- Combined into `LayoutAST`
- Convertible to `RemovalIntent` via `ast_to_removal_intents()`
- Ready for standard CAM pipeline

## Key Points

1. **Domains are 2D only** - Depth is specified in generator parameters
2. **MultiDomain for split results** - Operations like `inset()` return `MultiDomain` which may contain 0, 1, or many domains
3. **Check for empty results** - `result.is_empty` tells you if the operation produced nothing
4. **Deterministic** - Same domain + params = same output, always
5. **Composable** - Chain operations: `outer.inset(50).domains[0].inset(10)`

## Variations

### Different Frame Widths
```python
# Unequal frame widths (different stile/rail sizes)
# Not directly supported by inset - use subtract with offset rectangles instead
```

### Loop Selection
```python
ProfileParams(
    side="outside",
    depth="through",
    loop_selection="outer_only",  # Only outer boundary
    # or "inner_only", "all", "largest", "smallest"
)
```

### Pattern Depth Control
```python
WaveParams(
    amplitude_mm=8.0,
    wavelength_mm=25.0,
    depth_mm=2.0,  # Shallow decorative engrave
    # vs depth_mm=10.0 for deeper relief
)
```

## See Also

- [docs/domain_generator_design.md](../../domain_generator_design.md) - Full architecture specification
- [docs/examples/domain_generator_example.py](../../examples/domain_generator_example.py) - Complete integration example
- [FEATURES.md](../../../FEATURES.md#f006-domaingenerator-system-math-based-composition) - Feature documentation
