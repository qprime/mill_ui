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
| feature | Feature (optional) | CAM feature |
| children | tuple (optional) | Nested layout nodes |

PML: `rounded_rect [id] radius <value>mm [feature]`

Resolution: Fills current region with specified corner radius.

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
- Emitted as kind="path" (open), not kind="shape" (closed)

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
- Normalized coordinates mapped to absolute mm within region
- Points validated to be in range [0, 1] at parse time
- Emitted as kind="path" (open)

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
- Points are absolute (in mm), not normalized
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
| Line/Polyline children | Not supported (open paths are not regions) |
| Circle children | Use bounding box, not circular clipping |

---

## Files

| File | Purpose |
|------|---------|
| layout_ast/compositional.py | Circle, RoundedRect, Line, Polyline, Polygon, Triangle nodes |
| resolution/layout_resolver.py | Shape resolution logic |
| pml/compositional_parser.py | PML syntax parsing |
| pml/compositional_formatter.py | Canonical PML formatting |
