# Validation Invariants

**Applies to:** Removal checks, constraint validation

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| VL-1 | HARD | GRADIENT_DEPTH_CHECK | Gradient depth <= sheet thickness |
| VL-2 | HARD | VCARVE_ANGLE_MATCH | V-carve angle must match tooling (within 1°) |
| VL-3 | HARD | 3D_OVERLAP_CHECK | Overlap requires x, y, AND z overlap, and the same `face` |
| VL-4 | HARD | Z_TOP_GTE_Z_BOTTOM | z_top >= z_bottom |
| VL-5 | HARD | MARGIN_ZONE_INVIOLABLE | Nothing extends into margin zone |
| VL-6 | HARD | OUTSIDE_PROFILE_OFFSET | Outside profiles add tool_diameter |
| VL-7 | HARD | TOOL_DIAMETER_FITS | Tool diameter <= min feature dimension |
| VL-8 | HARD | CROSS_FACE_WEB | Overlapping front/back area features leave >= `min_web` of material |

---

## Depth Validation

- Gradient depth must not exceed sheet thickness
- V-carve angle must match available tooling (±1° tolerance)

---

## Overlap Detection

True overlap requires intersection in all three dimensions:
- X ranges overlap AND
- Y ranges overlap AND
- Z ranges overlap

Two features at different Z depths do not overlap even if their XY projections intersect.

Overlap is also face-scoped: a front feature and a back feature never conflict,
because they are machined in separate setups from opposite surfaces.
`check_overlap` skips any pair whose `face` differs.

Bounding boxes are a conservative first check. For two engravings,
the pipeline supplies the diameter selected by the engraving planner. The check
may discard a bounding-box overlap only when the distance between their shared
planner paths exceeds that full diameter plus numerical tolerance. This uses
the cutter's full cylindrical width, including for ball and V bits, rather than
assuming a narrower cut at a particular depth. Crossing, touching and closely
spaced cuts retain the existing conflict policy. Missing tool diameter
and unsupported geometry retain the bounding-box check. Ramped engraving follows
the same XY path; its varying Z does not widen the conservative cutter envelope.

For two pockets, use the shared planner region for polygons with holes and
rectangles with islands. A pocket occupies the material it removes, excluding
those preserved regions. Unknown shapes retain their bounding box as a
conservative envelope. Discard a bounding-box overlap only when the two regions
have a positive separation greater than numerical tolerance; touching or
intersecting regions retain the existing conflict policy. Pockets with edge
treatments or dogbone relief keep the prior bounding-box check because their
boundary modifications are not represented by the plain pocket region.

Perpendicular elongated pockets are an existing allowed crossing pattern.
Retain the horizontal/vertical rule and recognize rotated plain convex pockets
using the long axes of their minimum rotated bounds. The bounds must have a
long-to-short ratio greater than 1.5, and normalized axes must be perpendicular
within numerical tolerance. This includes straight grooves clipped at the
parent boundary. Squares, nonconvex or modified pockets, parallel paths and
oblique crossings do not gain this rotated-pattern exemption. Face and depth
checks still apply before the crossing rule.

---

## Cross-Face Web (VL-8)

Front and back features that overlap in XY share the same material. Their
combined depth may not exceed `thickness − min_web`, or the two cuts break
through into each other. `check_cross_face_web` enforces this, erroring
strictly beyond the budget — equality passes.

Only area features participate (pocket, hole, engrave). Profiles are excluded:
their bounds cover the whole part and would flag every job that has any back
feature at all. `min_web: 0` on the Sheet disables the check.

---

## Margin Zone

The margin zone is inviolable:
- No cutting operations may enter it
- No part geometry may extend into it
- Outside profile tool paths must account for tool radius

---

## Tool Clearance

For outside profiles:
- Part edge + tool_diameter must fit within working area
- Tool centerline follows part edge, so actual cut extends by radius

For inside features:
- Tool diameter must be <= minimum feature dimension
- Otherwise feature cannot be machined

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
