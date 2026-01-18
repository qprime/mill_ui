# Recipe 20: Multi-Panel Doors with Split Operations

## Goal

Create multi-panel cabinet doors using the Stage 9 split operations and advanced generators (raised panel, chamfer). This recipe covers:

- Using `split_horizontal`, `split_vertical`, and `split_grid` to divide domains
- Creating 6-panel doors with proper rail spacing
- Using the `raised_panel_generator` for traditional panel looks
- Using the `chamfer_generator` for presentation edges

## Concepts

### Split Operations

Split operations divide a domain into equal-sized regions with optional gaps for rails:

| Operation | Description | Result |
|-----------|-------------|--------|
| `split_horizontal(n, gap_mm)` | Divide into n rows | MultiDomain, bottom to top |
| `split_vertical(n, gap_mm)` | Divide into n columns | MultiDomain, left to right |
| `split_grid(rows, cols, gap_mm)` | Divide into rows × cols grid | MultiDomain, row-major from bottom |

### New Generators

| Generator | Parameters | Use Case |
|-----------|-----------|----------|
| `raised_panel_generator` | `RaisedPanelParams` | Traditional raised panels with beveled borders |
| `chamfer_generator` | `ChamferParams` | Angled edge cuts for presentation |

## Example 1: Simple 2-Panel Door

```python
from domains import Domain
from generators import (
    profile_generator, flat_pocket_generator,
    ProfileParams, FlatPocketParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Create door outer domain
door = Domain.from_rectangle(400, 600, center=(200, 300))

# Create panel region by insetting (frame width)
panel_region = door.inset(50).domains[0]

# Split into 2 vertical panels with center rail
panels = panel_region.split_horizontal(2, gap_mm=30)  # 30mm center rail

# Generate profile cut for outer
profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

# Generate pockets for each panel
pocket_items = []
for panel in panels:
    pocket_items.extend(
        flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))
    )

# Build AST
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)

print(f"Generated {len(panels)} panels")
```

## Example 2: Classic 6-Panel Door

The traditional 6-panel door has 2 columns and 3 rows, with rails between panels:

```python
from domains import Domain
from generators import (
    profile_generator, flat_pocket_generator,
    ProfileParams, FlatPocketParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Standard 6-panel door dimensions
door = Domain.from_rectangle(
    width_mm=610,   # 24 inches
    height_mm=2032,  # 80 inches
    center=(305, 1016),
)

# Panel opening (inside the frame)
frame_width = 75  # 3 inch stiles/rails
panel_region = door.inset(frame_width).domains[0]

# Split into 3 rows × 2 cols with rail gaps
rail_width = 30
panels = panel_region.split_grid(rows=3, cols=2, gap_mm=rail_width)

print(f"Created {len(panels)} panels")
# Expected: 6 panels, ordered:
# [0]=bottom-left, [1]=bottom-right
# [2]=middle-left, [3]=middle-right
# [4]=top-left, [5]=top-right

# Generate items
profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

pocket_items = []
for i, panel in enumerate(panels):
    pocket_items.extend(
        flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))
    )

ast = LayoutAST(
    sheet=Sheet(width_mm=700, height_mm=2100, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)
```

## Example 3: Raised Panel Door

Traditional raised panels have a beveled border transitioning from the frame depth to the raised center:

```python
from domains import Domain
from generators import (
    profile_generator, raised_panel_generator,
    ProfileParams, RaisedPanelParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Create door and panel region
door = Domain.from_rectangle(400, 600, center=(200, 300))
panel_region = door.inset(60).domains[0]  # 60mm frame

# Generate profile cut
profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

# Generate raised panel effect
# border_depth_mm=6 is the deepest cut (outer edge of border)
# field_depth_mm=2 is the shallower cut (center field appears raised)
raised_items = raised_panel_generator(
    panel_region,
    RaisedPanelParams(
        border_width_mm=25.0,   # Width of angled border
        border_depth_mm=6.0,    # Depth at outer edge
        field_depth_mm=2.0,     # Depth of raised center
        angle_degrees=15.0,     # Bevel angle (informational)
    ),
)

# raised_items contains 2 items:
# - Border polygon with 'bevel' feature
# - Field polygon with 'pocket' feature

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + raised_items),
)

print(f"Raised panel items: {len(raised_items)}")
```

## Example 4: Multi-Panel Raised Door

Combining split operations with raised panels:

```python
from domains import Domain
from generators import (
    profile_generator, raised_panel_generator,
    ProfileParams, RaisedPanelParams,
)
from layout_ast.layout import LayoutAST, Sheet

# 4-panel door (2×2 grid)
door = Domain.from_rectangle(500, 700, center=(250, 350))
panel_region = door.inset(65).domains[0]

# Split into 2×2 grid with 35mm rails
panels = panel_region.split_grid(rows=2, cols=2, gap_mm=35)

# Generate profile
profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

# Generate raised panels for each cell
raised_items = []
for panel in panels:
    raised_items.extend(
        raised_panel_generator(
            panel,
            RaisedPanelParams(
                border_width_mm=20.0,
                border_depth_mm=6.0,
                field_depth_mm=1.5,
            ),
        )
    )

ast = LayoutAST(
    sheet=Sheet(width_mm=550, height_mm=750, thickness_mm=19.0),
    items=tuple(profile_items + raised_items),
)

print(f"Total raised panel items: {len(raised_items)}")
# Expected: 8 items (2 per panel × 4 panels)
```

## Example 5: Door with Chamfered Edge

Add a decorative chamfer to the door's presentation face:

```python
from domains import Domain
from generators import (
    profile_generator, flat_pocket_generator, chamfer_generator,
    ProfileParams, FlatPocketParams, ChamferParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Create door
door = Domain.from_rectangle(400, 600, center=(200, 300))
panel_region = door.inset(50).domains[0]

# Generate operations
profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))
pocket_items = flat_pocket_generator(panel_region, FlatPocketParams(depth_mm=6.0))

# Add chamfer around the outer edge
chamfer_items = chamfer_generator(
    door,
    ChamferParams(
        width_mm=5.0,   # 5mm horizontal width
        depth_mm=3.0,   # 3mm vertical depth
        loop_selection="outer_only",
    ),
)

# chamfer_items[0].feature.chamfer_angle_deg will be ~31° (arctan(3/5))

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items + chamfer_items),
)
```

## Example 6: French Door Pair

Two doors side by side using vertical split:

```python
from domains import Domain
from generators import (
    profile_generator, flat_pocket_generator,
    ProfileParams, FlatPocketParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Full sheet with two doors
sheet_domain = Domain.from_rectangle(900, 600, center=(450, 300))

# Split into 2 doors with 20mm gap between
doors = sheet_domain.split_vertical(2, gap_mm=20)

all_items = []

for door in doors:
    # Profile each door
    all_items.extend(
        profile_generator(door, ProfileParams(side="outside", depth="through"))
    )

    # Create panel in each door
    panel = door.inset(50).domains[0]
    all_items.extend(
        flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))
    )

ast = LayoutAST(
    sheet=Sheet(width_mm=950, height_mm=650, thickness_mm=19.0),
    items=tuple(all_items),
)

print(f"French door pair: {len(all_items)} items")
```

## Process: Running the Examples

```bash
# Run tests for Stage 9 features
PYTHONPATH=. python3 tests/test_domain.py
PYTHONPATH=. python3 tests/test_generators.py

# Run the complete example
PYTHONPATH=. python3 docs/recipes/20_multi_panel_doors/example.py
```

## Key Points

1. **Split ordering** - Results are always ordered:
   - `split_horizontal`: bottom to top
   - `split_vertical`: left to right
   - `split_grid`: row-major from bottom-left

2. **Gap spacing** - The gap parameter removes material for rails:
   ```python
   # 600mm height, split into 3 panels with 30mm rails:
   # Available height = 600 - (2 × 30) = 540mm
   # Panel height = 540 / 3 = 180mm each
   ```

3. **Raised panel geometry** - Creates 2 items:
   - Border with `bevel` feature type
   - Field with `pocket` feature type

4. **Chamfer angle** - Computed from width and depth:
   ```python
   angle = arctan(depth_mm / width_mm)
   ```

5. **Composability** - Chain operations:
   ```python
   door.inset(50).domains[0].split_grid(2, 2, gap_mm=20)
   ```

## Variations

### Unequal Row Heights

For different row heights, use subtract operations instead of split:

```python
# Top panel larger than bottom
full_region = door.inset(50).domains[0]
bounds = full_region.bounds

# Create a divider 40% from bottom
divider_y = bounds.y_min + bounds.height * 0.4
divider = Domain.from_rectangle(
    bounds.width + 20,  # Wider than region
    30,  # Rail width
    center=(bounds.center[0], divider_y),
)

# Subtract to get two unequal panels
result = full_region.subtract(divider)
bottom_panel = [d for d in result if d.centroid[1] < divider_y][0]
top_panel = [d for d in result if d.centroid[1] > divider_y][0]
```

### Partial-Depth Profile

Use numeric depth for partial-depth profile cuts:

```python
profile_items = profile_generator(
    door,
    ProfileParams(
        side="outside",
        depth=15.0,  # Cut 15mm deep instead of through
    ),
)
```

## See Also

- [Recipe 19: Domain/Generator Basics](../19_domain_generator_basics/README.md) - Foundational domain/generator concepts
- [docs/domain_generator_design.md](../../domain_generator_design.md) - Full architecture specification
- [FEATURES.md](../../../FEATURES.md) - Feature documentation
