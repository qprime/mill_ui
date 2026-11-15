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
| NS-11 | HARD | MACHINING_EDGE_CLEARANCE | Geometry-only nesting reserves requested kerf at working-area edges. Manufacturing nesting reserves the selected actual profile cutter diameter, preserving nominal dimensions even when requested kerf differs. |
| NS-12 | HARD | LAYOUT_WORKING_COORDINATES | Convert physical packing placements to working-area coordinates when producing LayoutAST/PML; export applies the physical sheet margin once. |

---

## Assembly and Beam Perimeter Clearance

Waste-cut decomposition uses the resolved profile diameter. With tabs or onion
skin anywhere in the job, it reserves two diameters between parts and offcuts
and between offcuts. The declared waste margin adds clearance around existing
parts. Waste profiles still pass the ordinary planner holding and sweep checks.

Machining-aware assembly partitioning and row-wrapped assembly/beam placement
reserve the selected profile cutter diameter inside the working-area boundary.
The context arrives from orchestration before resolution, including when the
requested kerf differs from an available cutter. Perimeter clearance therefore
accounts for the complete outside cut rather than only its centerline. Numeric
part gaps retain their authored total separation and must accommodate the cutter.
Numeric gaps and their omitted 10mm default retain their legacy meaning.
Explicit `layout_gap: auto` uses the actual cutter plus measured extra clearance
through the existing SheetSpec gap formula. Geometry-only auto resolution requires
a supplied machining context; it never substitutes an authored kerf.

Assembly partitioning sends nominal dimensions and the gap to the packer. Its
results retain the original PanelSpec identities and impose no trailing gap at
the final sheet edge. Both packers obey this contract.

Automatic machining resolution preflights every sheet and retries at most four
times with conservatively increased clearance, preserving dimensions and
rotation/grain policy. Attempts and final gaps are recorded. Numeric gaps are
never enlarged. Protected tabs/onion stock requires disjoint neighboring kerfs;
ordinary profiles with holding therefore need at least twice the cutter diameter.

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

The sheet packer passes this gap to both packing algorithms. Their internal
rectangles include a trailing gap, so the packing bin extends by one gap on each
axis. This reserves space between parts without requiring an additional gap at
the sheet's usable outer edge; nominal parts must still fit inside the usable area.

The general sheet packer accepts optional `edge_clearance_mm`, defaulting to
zero for geometry-only packing. Geometry-only nesting APIs supply requested kerf;
manufacturing entry points supply the selected actual profile cutter diameter.
This reduces the packing bin on both sides of each axis and insets placements
without changing nominal part dimensions or part-to-part gap.

`cli.nest`, recipe compilation and recipe validation share that tool selection.
`cli.nest` packs and machines the original `.nest.yml` in one invocation, with
in-memory AST handoffs. It writes final manufacturing/review outputs through the
canonical pipeline writer without deleting the output directory. Packing overlap
and bounds checks complete before machining. Existing files are preserved and
only the current output list identifies current artifacts. Resolved layouts, flattened PML and tool snapshots
are neither exported nor accepted as machining inputs.

Packing results describe physical sheet placements. At the LayoutAST boundary,
subtract the physical sheet margin from each placement. The generated layout
keeps the original physical sheet dimensions and margin; the exporter applies
that margin once, as required by CS-13/CS-14.

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
