# Shape Primitives (Stage 14)

This document describes the basic geometric primitives available in the compositional layout system.

All shapes are **region-relative**: they operate within their parent's current region and follow **fill-by-default** semantics unless explicitly sized.

## Shape Catalog

### Rect (Rectangle)

**Purpose**: Creates a rectangular region filling the current space.

**PML Syntax**:
```pml
rect [id] [feature]
    <children>
```

**Parameters**:
- `id` (optional): Shape identifier
- `feature` (optional): CAM feature (pocket, profile, engrave, hole, edge)
- `children` (optional): Nested layout nodes (Frame, Grid, etc.)

**Examples**:
```pml
# Simple filled rect with profile
rect outer profile through outside

# Rect with pocket and nested frame
rect panel pocket 6.00mm
    frame 40.00mm
        grid 2 2 gap 10.00mm
            cell
                rect pocket 3.00mm
```

**Resolution**:
- Fills current region width and height
- Centered at region center
- Children operate within same region

---

### Circle

**Purpose**: Creates a circular region.

**PML Syntax**:
```pml
circle [id] [diameter <value>mm | fit] [feature]
    <children>
```

**Parameters**:
- `id` (optional): Shape identifier
- `diameter` (optional): Explicit diameter in millimeters
- `fit` (optional): Fit mode - largest circle inscribed in current region
- `feature` (optional): CAM feature (pocket, profile, hole, engrave, edge)
- `children` (optional): Nested layout nodes

**Examples**:
```pml
# Circle with explicit diameter
circle medallion diameter 120.00mm pocket 3.00mm

# Circle fit to region (inscribed)
circle badge fit profile through outside

# Circle in inset region
inset 50.00mm
    circle fit hole
```

**Resolution**:
- **Explicit diameter**: Uses specified diameter, centered in region
- **Fit mode**: Diameter = min(region.width, region.height), centered in region
- Children operate within bounding box of circle

---

### RoundedRect (Rounded Rectangle)

**Purpose**: Creates a rectangular region with rounded corners.

**PML Syntax**:
```pml
rounded_rect [id] radius <value>mm [feature]
    <children>
```

**Parameters**:
- `id` (optional): Shape identifier
- `radius` (required): Corner radius in millimeters
- `feature` (optional): CAM feature (pocket, profile, engrave, edge)
- `children` (optional): Nested layout nodes

**Examples**:
```pml
# Rounded rectangle badge
rounded_rect badge radius 8.00mm pocket 3.00mm

# Rounded panel with profile
rounded_rect panel radius 12.00mm profile through outside

# Rounded rect in inset region
inset 25.00mm
    rounded_rect radius 10.00mm pocket 5.00mm
```

**Resolution**:
- Fills current region width and height
- Corner radius preserved
- Centered at region center
- Children operate within same region

---

### Line (Open Path)

**Purpose**: Creates an open path for engraving/decoration.

**PML Syntax**:
```pml
line [id] horizontal|vertical [feature]
```

**Parameters**:
- `id` (optional): Shape identifier
- `orientation` (required): `horizontal` or `vertical`
- `feature` (optional): CAM feature (typically `engrave`)

**Note**: Lines do NOT support children (open paths, not regions).

**Examples**:
```pml
# Horizontal decorative line
line decoration horizontal engrave

# Vertical divider
line divider vertical engrave

# Line in inset region
inset 50.00mm
    line flourish horizontal engrave
```

**Resolution**:
- **Horizontal**: Spans from region.x_min to region.x_max at vertical center
- **Vertical**: Spans from region.y_min to region.y_max at horizontal center
- Lines are emitted as `kind="path"` (open), not `kind="shape"` (closed)

---

### Polyline (Arbitrary Path)

**Purpose**: Creates arbitrary open paths for engraving using normalized coordinates.

**PML Syntax**:
```pml
polyline [id] points (x1,y1) (x2,y2) ... [feature]
```

**Parameters**:
- `id` (optional): Shape identifier
- `points` (required): List of normalized coordinates (0..1, 0..1) relative to current region
  - (0, 0) = bottom-left of region
  - (1, 1) = top-right of region
  - Minimum 2 points required
- `feature` (optional): CAM feature (typically `engrave`)

**Note**: Polylines do NOT support children (open paths, not regions).

**Examples**:
```pml
# Diagonal line across region
polyline diagonal points (0.0,0.0) (1.0,1.0) engrave 1.00mm

# Zigzag pattern
polyline zigzag points (0.1,0.1) (0.5,0.9) (0.9,0.1) engrave 1.00mm

# Cross pattern
polyline cross points (0.25,0.5) (0.75,0.5) (0.5,0.5) (0.5,0.25) (0.5,0.75) engrave 1.00mm
```

**Resolution**:
- Normalized coordinates (0..1) are mapped to absolute coordinates within the current region
- Points are validated to be in range [0, 1] at parse time
- Polylines are emitted as `kind="path"` (open), not `kind="shape"` (closed)
- Works inside any layout manager (rect, inset, frame, grid, split, circle, rounded_rect)

**Use Cases**:
- Decorative engraving patterns
- Custom alignment marks
- Arbitrary text or logo outlines (when converted to normalized coordinates)
- Registration crosses or targets

---

## Composition Patterns

### Mixed Shapes in Grid

Combine different shape types in a grid layout:

```pml
sheet 800.00mm 600.00mm 19.00mm

grid 2 2 gap 20.00mm
    cell
        circle fit pocket 5.00mm
    cell
        rounded_rect radius 8.00mm pocket 5.00mm
    cell
        rect pocket 5.00mm
    cell
        circle diameter 100.00mm hole
```

### Frame + Shaped Insets

Use shapes within frames:

```pml
rect outer profile through outside
    frame 40.00mm
        circle fit pocket 6.00mm
```

### Decorative Lines

Add engraved lines for visual elements:

```pml
rounded_rect panel radius 12.00mm profile through outside

line decoration horizontal engrave

inset 30.00mm
    line border vertical engrave
```

---

## Region-Relative Behavior

All shapes follow these principles:

1. **Fill-by-default**: Shapes without explicit size fill their current region
2. **Centered placement**: Shapes are centered within their region
3. **Children inheritance**: Nested layouts operate within the shape's region
4. **Deterministic sizing**: Resolution is predictable and reproducible

### Region Propagation Example

```pml
sheet 400.00mm 600.00mm 19.00mm

inset 50.00mm                          # Region: 300×500mm, center (200,300)
    rounded_rect radius 10.00mm        # Fills: 300×500mm, radius 10mm
        frame 40.00mm                  # Inner region: 220×420mm
            circle fit pocket 5.00mm   # Diameter: min(220,420)=220mm
```

Resolution chain:
1. Sheet region: 400×600mm
2. Inset shrinks to: 300×500mm (centered at 200,300)
3. RoundedRect fills: 300×500mm with 10mm corners
4. Frame creates inner region: 220×420mm
5. Circle fits: diameter=220mm (min of 220,420)

---

## Feature Application

Features specify CAM intent (what material to remove):

- **pocket**: Shallow recess within bounds
- **profile**: Cut along boundary (through or partial depth)
- **hole**: Through-hole (typically circular)
- **engrave**: Surface decoration (shallow, typically open paths)
- **edge**: Edge treatment (chamfer, round-over - future)

Example with features:

```pml
# Outer profile cut
rounded_rect panel radius 8.00mm profile through outside

# Inner pocket
inset 10.00mm
    circle diameter 80.00mm pocket 3.00mm

# Decorative engraving
line flourish horizontal engrave
```

---

## Limitations (v1)

### Circle Fit Mode
- Fit mode uses **bounding box** min dimension
- For non-square regions, may leave unused space
- Future: Support `fit_width`, `fit_height` modes

### Line Orientations
- Line supports `horizontal` and `vertical` (canned orientations)
- For arbitrary angles and custom paths, use Polyline with normalized coordinates

### RoundedRect Radius Constraints
- No automatic clamping if radius > min(width, height) / 2
- User must ensure radius is valid for region size
- Future: Add validation warnings

### Shape-Specific Children
- Lines do NOT support children (open paths)
- Circles use bounding box for children (not circular clipping)
- Future: Proper circular child clipping

---

## Stage 14 Implementation Notes

**Files**:
- `v2/ast/compositional.py`: Circle, RoundedRect, Line nodes
- `v2/resolution/layout_resolver.py`: Shape resolution logic
- `v2/pml/compositional_parser.py`: PML syntax parsing
- `v2/pml/compositional_formatter.py`: Canonical PML formatting
- `v2/tests/test_basic_shapes.py`: 13 comprehensive tests

**Compatibility**:
- Existing rect/inset/frame/grid nodes unchanged
- Stage 12/13 tests still pass (8/8, 10/10)
- No changes to RemovalIntent or strategy/lowering layers

**Next Steps** (future stages):
- Arbitrary polylines with point lists
- Ellipse support
- Regular polygons (hexagon, octagon, etc.)
- Bezier curves for organic shapes
