# Validation Invariants

**Applies to:** Removal checks, constraint validation

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| VL-1 | HARD | GRADIENT_DEPTH_CHECK | Gradient depth <= sheet thickness |
| VL-2 | HARD | VCARVE_ANGLE_MATCH | V-carve angle must match tooling (within 1°) |
| VL-3 | HARD | 3D_OVERLAP_CHECK | Overlap requires x, y, AND z overlap |
| VL-4 | HARD | Z_TOP_GTE_Z_BOTTOM | z_top >= z_bottom |
| VL-5 | HARD | MARGIN_ZONE_INVIOLABLE | Nothing extends into margin zone |
| VL-6 | HARD | OUTSIDE_PROFILE_OFFSET | Outside profiles add tool_diameter |
| VL-7 | HARD | TOOL_DIAMETER_FITS | Tool diameter <= min feature dimension |

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
