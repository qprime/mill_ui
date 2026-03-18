<!-- spec-style -->
# Shape Primitives

As-Of Date: 2026-01-19
Document Type: Shape Specification

---

## Purpose

Define geometric primitives available in the compositional layout system.
All shapes are region-relative and follow fill-by-default semantics.

---

## Shape Catalog

### Rect

Rectangle filling current region.

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| feature | Feature (optional) | CAM feature |
| children | tuple (optional) | Nested layout nodes |

PML: `rect [id] [feature]`

Resolution: Fills current region width and height, centered at region center.

### Circle

Circular region with explicit diameter or fit-to-region.

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| diameter_mm | float (optional) | Explicit diameter |
| fit | bool (optional) | Inscribe in region |
| feature | Feature (optional) | CAM feature |
| children | tuple (optional) | Nested layout nodes |

PML: `circle [id] [diameter <value>mm | fit] [feature]`

Resolution:
- Explicit diameter: Uses specified diameter, centered in region
- Fit mode: diameter = min(region.width, region.height), centered in region
- Children operate within bounding box of circle

### RoundedRect

Rectangle with rounded corners filling current region.

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| radius_mm | float | Corner radius |
| corners | frozenset (optional) | Which corners to round (tl, tr, bl, br) |
| feature | Feature (optional) | CAM feature |
| children | tuple (optional) | Nested layout nodes |

PML: `rounded_rect [id] radius <value>mm [corners tl tr bl br] [feature]`

**Selective Corner Rounding:**

The optional `corners` keyword specifies which corners receive rounding. Omitted corners get radius 0 (square).

```pml
# All corners rounded (default behavior, corners keyword omitted)
rounded_rect radius 12.7mm profile through outside

# Only left side rounded (table top half with straight joint edge)
rounded_rect table_half radius 12.7mm corners tl bl profile through outside

# Single corner rounded (corner piece)
rounded_rect corner radius 25mm corners tr profile through outside
```

Resolution:
- Fills current region with specified corner radii
- Geometry includes per-corner radii: `radius_tl_mm`, `radius_tr_mm`, `radius_bl_mm`, `radius_br_mm`
- When all corners equal, `radius_mm` is also set for backward compatibility

### Line

Open path for engraving (horizontal or vertical).

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| orientation | str | "horizontal" or "vertical" |
| feature | Feature (optional) | CAM feature (typically engrave) |

PML: `line [id] horizontal|vertical [feature]`

Lines do NOT support children (open paths, not regions).

Resolution:
- Horizontal: spans region.x_min to region.x_max at vertical center
- Vertical: spans region.y_min to region.y_max at horizontal center
- Emitted as kind="shape", type="Line"
- Geometry stores relative coordinates (start/end) with center_xy_mm offset

### Polyline

Arbitrary open path using normalized coordinates.

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| points | list | Normalized coordinates (0..1, 0..1) |
| feature | Feature (optional) | CAM feature (typically engrave) |

PML: `polyline [id] points (x1,y1) (x2,y2) ... [feature]`

Coordinate system:
- (0, 0) = bottom-left of region
- (1, 1) = top-right of region
- Minimum 2 points required

Polylines do NOT support children (open paths, not regions).

Resolution:
- Normalized coordinates mapped to mm within region, then stored relative to center
- Points validated to be in range [0, 1] at parse time
- Emitted as kind="shape", type="Polyline"
- Geometry stores relative coordinates (points) with center_xy_mm offset

### Polygon

Arbitrary closed polygon with explicit absolute coordinates.

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| points | list | Absolute coordinates in mm |
| feature | Feature (optional) | CAM feature |
| children | tuple (optional) | Nested layout nodes |

PML: `polygon [id] points (x1mm,y1mm) (x2mm,y2mm) (x3mm,y3mm) ... [feature]`

Coordinate system:
- Points are specified in absolute mm in PML, stored relative to center_xy_mm
- Minimum 3 points required

Resolution:
- Bounds computed from min/max of all points
- Emitted as kind="shape", type="Polygon"
- Children operate within bounding box of polygon

### Triangle

Triangular region with parametric base and height, centered in current region.

| Field | Type | Description |
|-------|------|-------------|
| id | str (optional) | Shape identifier |
| base_mm | float | Width of triangle base |
| height_mm | float | Height from base to apex |
| feature | Feature (optional) | CAM feature |
| children | tuple (optional) | Nested layout nodes |

PML: `triangle [id] base <value>mm height <value>mm [feature]`

Resolution:
- Triangle centered in current region
- Base at bottom, apex at top
- Emitted as kind="shape", type="Polygon" with 3 points
- Children operate within bounding box of triangle

---

## Features

| Feature | Description | Example |
|---------|-------------|---------|
| profile | Cut along boundary | `profile through outside` |
| pocket | Shallow recess within bounds | `pocket 6.00mm` |
| hole | Through-hole (typically circular) | `hole` |
| engrave | Surface decoration (shallow) | `engrave 1.00mm` |
| edge | Edge treatment (future) | chamfer, round-over |

---

## Region-Relative Behavior

| Principle | Description |
|-----------|-------------|
| Fill-by-default | Shapes without explicit size fill current region |
| Centered placement | Shapes centered within region |
| Children inheritance | Nested layouts operate within shape's region |
| Deterministic sizing | Resolution is predictable and reproducible |

---

## Limitations

| Limitation | Description |
|------------|-------------|
| Circle fit mode | Uses bounding box min dimension; non-square regions leave unused space |
| Line orientations | Only horizontal/vertical; use Polyline for arbitrary angles |
| RoundedRect radius | No automatic clamping if radius > min(width, height) / 2 |
| RoundedRect corners | Corner identifiers are position-based (tl=top-left assumes Y+ is up) |
| Line/Polyline children | Not supported (open paths are not regions) |
| Circle children | Use bounding box, not circular clipping |

---

## Nest Job Availability

Shape primitives `Rect`, `RoundedRect`, `Circle`, `Polygon`, and `Triangle` are available in `.nest.yml` files via the `shape` field on part definitions. Packing is always by bounding box. See [Nest Syntax Spec](../pml/nest_syntax_spec.md#parts-with-shape-primitives) for syntax and examples.

`Line` and `Polyline` are open paths and are not supported as nest parts.

---

## Files

| File | Purpose |
|------|---------|
| layout_ast/compositional.py | Circle, RoundedRect, Line, Polyline, Polygon, Triangle nodes |
| resolution/layout_resolver.py | Shape resolution logic |
| pml/yaml_parser.py | PML YAML parsing |
| pml/yaml_formatter.py | PML YAML formatting |
| nesting/template_expander.py | Shape dispatch for nest parts (`_build_geometry_data`) |
