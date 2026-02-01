# Nesting Invariants

**Applies to:** Bin packing, sheet utilization

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| NS-1 | HARD | PART_WIDTH_POSITIVE | width_mm must be > 0 |
| NS-2 | HARD | PART_HEIGHT_POSITIVE | height_mm must be > 0 |
| NS-3 | HARD | QUANTITY_NON_NEGATIVE | quantity must be >= 0 |
| NS-4 | HARD | SHEET_THICKNESS_POSITIVE | thickness_mm must be > 0 |
| NS-5 | HARD | MARGIN_NON_NEGATIVE | margin_mm must be >= 0 |
| NS-6 | HARD | KERF_NON_NEGATIVE | kerf_mm must be >= 0 |
| NS-7 | HARD | USABLE_AREA_POSITIVE | Margins must leave usable area > 0 |
| NS-8 | STRUCTURAL | ROTATION_SWAPS_DIMS | When rotated, width/height swap |
| NS-9 | STRUCTURAL | GAP_FORMULA | gap_mm = kerf_mm + gap_margin_mm |
| NS-10 | STRUCTURAL | USABLE_FORMULA | usable = dimension - 2*margin |

---

## Part Dimensions

- `width_mm > 0`
- `height_mm > 0`
- `quantity >= 0` (0 means "don't include")

---

## Sheet Constraints

- `thickness_mm > 0`
- `margin_mm >= 0`
- `kerf_mm >= 0`
- Usable area must be > 0 after margins applied

---

## Formulas

### Usable Area
```
usable_width = physical_width - 2 * margin_mm
usable_height = physical_height - 2 * margin_mm
```

### Part Gap
```
gap_mm = kerf_mm + gap_margin_mm
```

The gap between parts accounts for:
- `kerf_mm`: Material removed by the cutting tool
- `gap_margin_mm`: Additional clearance (optional)

---

## Rotation

When a part is rotated 90°, its width and height swap:

```python
if rotated:
    effective_width = original_height
    effective_height = original_width
```

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
