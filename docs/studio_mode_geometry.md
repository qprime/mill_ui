<!-- spec-style -->
# Studio Mode Geometry

As-Of Date: 2026-01-19
Document Type: Mode Specification

---

## Purpose

Define Studio Mode geometry policy and centerline spline/path support.
Studio Mode prioritizes creative freedom and visual outcomes over dimensional accuracy.

---

## Studio Mode Policy

### Core Principles

| Principle | Description |
|-----------|-------------|
| Centerline paths | Tool center follows specified path; tool diameter is expressive |
| Visual outcome | What you see is what you cut; iterate via test cuts |
| Permissive validation | ERROR only on crash risks; warnings never block |
| Test-driven | Material waste accepted as part of creative process |

### Allowed

- Sine-wave frame artwork
- Flowing decorative outlines
- Organic, hand-drawn curves
- Image-derived toolpaths
- Tight-radius turns
- Self-intersecting patterns
- Variable-width line art (via tool diameter)

### Not Guaranteed

- Dimensional accuracy for fit-critical parts
- Offset-corrected boundaries
- Tool radius compensation
- Production-grade tolerances
- Kerf correctness for joinery

---

## SplinePath Primitive

### Properties

| Property | Description |
|----------|-------------|
| Intent | Centerline (tool follows path exactly) |
| Lowering | Immediately converted to polyline during resolution |
| Paths | Open only in v1 |
| Use case | Decorative engraving, flowing outlines |
| NOT for | Pocket/profile boundaries, fit-critical geometry |

### PML Syntax

```pml
spline <id> [feature <type> <depth>]
    points (<x>,<y>) (<x>,<y>) ...
    [tolerance <value>mm]
```

Coordinates are normalized (0.0 to 1.0) relative to current region.
Default tolerance: 0.1mm.

---

## Resolution Behavior

SplinePath nodes are IMMEDIATELY lowered to polylines:

1. Parse stage: SplinePath AST node with control points
2. Resolution stage: Spline sampled into polyline segments
3. CAM output: Only polyline geometry emitted

Coordinate transformation:
- `x_mm = region.x_min + (x_norm * region.width)`
- `y_mm = region.y_min + (y_norm * region.height)`

---

## Validation Rules

### ALLOWED (no errors)

- Tight curvature (tool coupling accepted)
- Self-intersecting paths
- Paths approaching region boundaries
- Arbitrary tool diameters
- Rapid direction changes

### ERROR (blocking)

- Motion exits machine envelope
- Z violates safety limits
- Rapid moves at cutting depth

### WARNING (informational only)

- Tool diameter larger than curve radius
- Self-intersection detected
- High point density

Warnings NEVER block execution in Studio Mode.

---

## Feature Support

| Feature | Supported |
|---------|-----------|
| Engrave | Yes (primary use case) |
| Profile/Pocket | No (use boundary shapes) |
| Edge treatment | No (paths, not boundaries) |

---

## RemovalIntent Output

Spline-derived polylines emit standard RemovalIntent:

| Field | Value |
|-------|-------|
| region_id | Generated from spline ID |
| bounds | Bounding box of sampled polyline |
| z_top | 0.0 |
| z_bottom | -depth_mm (from engrave feature) |
| metadata | `spline_source: true` |

---

## Files

| File | Purpose |
|------|---------|
| layout_ast/compositional.py | SplinePath dataclass |
| pml/yaml_parser.py | Spline parsing |
| resolution/layout_resolver.py | Spline lowering logic |
