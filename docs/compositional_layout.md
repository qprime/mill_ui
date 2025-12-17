# Compositional Layout System (Stage 12)

## Overview

The compositional layout system enables hierarchical, region-relative layout specification without explicit XY coordinates. It's designed to match the mental model of UI frameworks (React, QML) for physical manufacturing.

**Key principles:**
- **Region-relative**: Children operate within their parent's computed region
- **No coordinates required**: Layout managers (frame, grid) compute positions
- **Declarative composition**: Rectangles within rectangles, layouts within regions
- **Reusable components**: Parameterized subtrees for design reuse
- **Sheet composition**: Multiple instances on one sheet via deterministic placement

## Architecture

```
Compositional AST → Layout Resolution → Flat LayoutAST → RemovalIntent → G-code
     (authored)         (computed)         (positioned)      (operations)
```

**Regions are computed, never authored.** The layout resolution pass propagates region context through the tree and calculates absolute positions.

## Compositional Nodes

### Panel
Root workpiece/stock region. Establishes initial region from sheet bounds.

```python
Panel(
    children=(...)  # Nested layout nodes
    id="panel1"     # Optional identifier
)
```

### Inset
Shrinks current region inward by amount on all sides.

```python
Inset(
    amount_mm=25,   # Shrink by 25mm on each edge
    children=(...)  # Operate within inset region
)
```

**Use case:** Margins, safety zones, workholding clearance

### Frame
Creates profile at boundary and produces inner field region.

```python
Frame(
    width_mm=50,            # Frame width (edge to inner field)
    children=(...),         # Nodes within inner field
    profile_depth="through", # Default depth
    profile_side="outside"   # Default side
)
```

**Properties:**
- Works on ANY closed region (rect, circle, irregular)
- Automatically creates outer profile
- Children operate in inner region (shrunk by frame width)

**Use case:** Shaker panels, decorative frames, structural borders

### Grid
Subdivides current region into rows × cols cells.

```python
Grid(
    rows=2,
    cols=3,
    gap_mm=10,      # Spacing between cells
    children=(...)  # Cell content (via Cell node)
)
```

**Gap semantics:**
- Gap is spacing BETWEEN cells, not inset from edges
- Total available space is divided after accounting for gaps
- Cell size = (region_size - gaps) / count

**Use case:** Multi-panel layouts, paned doors, grid patterns

### Cell
Content template for grid cells. Each Cell subtree is replicated once per grid cell.

```python
Grid(
    rows=2, cols=2,
    children=(
        Cell(
            inset_mm=5,     # Optional per-cell inset
            children=(...)  # Content for each cell
        ),
    )
)
```

**Note:** If Grid has no explicit Cell children, all direct children are treated as cell content.

### Rect
Rectangle that fills current region by default.

```python
Rect(
    children=(...),  # Nested layout nodes
    feature=Feature(type="pocket", depth_mm=5.0),
    id="panel"
)
```

**Unlike legacy Item nodes**, compositional Rect participates in region hierarchy.

### ComponentDef
Reusable component definition (named, parameterized subtree).

```python
ComponentDef(
    name="ShakerPanel",
    params={"frame_width": 50.0, "recess_depth": 6.0},
    body=Rect(
        children=(
            Frame(width_mm=50, ...),
        ),
        feature=...
    )
)
```

**Components are region-relative:** They operate within the current region when instantiated, not at absolute coordinates.

### UseComponent
Component instantiation with parameter substitution.

```python
UseComponent(
    component_name="ShakerPanel",
    args={"frame_width": 60.0, "recess_depth": 8.0}
)
```

**Parameter binding:** Component params provide defaults; args override.

### Place
Sheet-level multi-instance placement.

```python
Place(
    layout=Grid(rows=2, cols=2, gap_mm=100),
    children=(
        UseComponent(component_name="ShakerPanel"),
        UseComponent(component_name="ShakerPanel"),
        UseComponent(component_name="ShakerPanel"),
        UseComponent(component_name="ShakerPanel"),
    )
)
```

**Deterministic layout first:** Simple grid-based placement. Irregular nesting optimization deferred to later stages.

## Layout Resolution

The `resolve_layout()` pass transforms compositional AST to flat LayoutAST:

1. **Start from Panel**: Initial region = full sheet bounds
2. **Propagate region context**: Each node receives parent's region
3. **Apply layout managers**:
   - `Inset`: Shrink region
   - `Frame`: Create profile, shrink for children
   - `Grid`: Subdivide into cells
4. **Replicate content**: Cell and Place repeat subtrees
5. **Expand components**: UseComponent → expanded body with param substitution
6. **Output flat shapes**: Absolute-positioned Item nodes

**Invariants:**
- Children fill parent region by default
- Layout is order-independent
- Regions never overlap (deterministic subdivision)
- Output compatible with existing RemovalIntent pipeline

## Example: 4 Shaker Panels on One Sheet

```python
# Define reusable component
shaker = ComponentDef(
    name="ShakerPanel",
    params={},
    body=Rect(
        children=(
            Frame(
                width_mm=50,
                children=(
                    Rect(feature=Feature(type="pocket", depth_mm=6.0)),
                ),
            ),
        ),
        feature=Feature(type="profile", depth="through", side="outside"),
    )
)

# Compose sheet layout
ast = CompositionalLayoutAST(
    sheet=Sheet(width_mm=1200, height_mm=1200, thickness_mm=19),
    components={"ShakerPanel": shaker},
    root=Place(
        layout=Grid(rows=2, cols=2, gap_mm=100),
        children=(
            UseComponent(component_name="ShakerPanel"),
            UseComponent(component_name="ShakerPanel"),
            UseComponent(component_name="ShakerPanel"),
            UseComponent(component_name="ShakerPanel"),
        ),
    ),
)

# Resolve to flat layout
flat = resolve_layout(ast)

# Output FlatPML for inspection
pml = format_pml(flat)
```

**Result:** 4 identical Shaker panels placed in 2×2 grid with 100mm gap, each with frame + inner pocket.

## Coordinate System

**Sheet coordinates:**
- Origin (0, 0) at bottom-left
- +X right, +Y up
- All regions specified as (x_min, y_min, x_max, y_max)

**Region center:** `((x_min + x_max) / 2, (y_min + y_max) / 2)`

## Integration with Existing Pipeline

**Compositional nodes are pre-lowering:**

```
CompositionalLayoutAST → [resolve_layout] → LayoutAST (flat) → [existing pipeline]
```

After resolution, the flat LayoutAST contains:
- Absolute-positioned Item nodes (kind="shape")
- Geometry with w_mm, h_mm
- Placement with center_xy_mm
- Feature specifications (profile, pocket, hole)

**This output is compatible with:**
- FlatPML formatter (Stage 11)
- RemovalIntent lowering (Stage 4-6)
- Existing planner/strategy layers

## What NOT to Do

- ❌ Do not author ResolvedRegion nodes (they're computed)
- ❌ Do not use absolute XY coordinates in compositional AST
- ❌ Do not add algebra/expressions (use layout managers + params)
- ❌ Do not treat compositional nodes as RemovalIntent (separate layers)

## Future Extensions

**Deferred to later stages:**
- `Split` layout manager (cabinetry-style division with rails/mullions)
- Irregular nesting optimization for Place
- Circular/polar grids
- Advanced component parameter binding (expressions, constraints)
- Edge treatments as compositional nodes (fillet, chamfer)
