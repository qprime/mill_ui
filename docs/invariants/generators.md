# Generator System Invariants

**Applies to:** Pattern generators, feature creation

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| GN-1 | HARD | DETERMINISTIC | Same domain + params = same output |
| GN-2 | HARD | NO_DOMAIN_MUTATION | Generators never modify the input domain |
| GN-3 | STRUCTURAL | RAISE_OR_EMPTY | Raise on invalid params unless allow_empty=True |
| GN-4 | HARD | OUTPUT_SHEET_COORDS | Emit Items in sheet coordinates |
| GN-5 | HARD | DEPTH_POSITIVE | All depth_mm fields must be > 0 |
| GN-6 | HARD | PROFILE_VALID_SIDES | side must be "outside", "inside", or "on" |
| GN-7 | HARD | PROFILE_DEPTH | depth is "through" or positive number |
| GN-8 | STRUCTURAL | LOOP_SELECTION_VALID | "outer_only", "inner_only", "all_loops", or list[int] |
| GN-9 | HARD | TAB_COUNT_NON_NEGATIVE | tab_count >= 0 |
| GN-10 | HARD | TABS_REQUIRE_DIMENSIONS | If tab_count > 0, width and height must be > 0 |
| GN-11 | HARD | SPACING_POSITIVE | All spacing fields must be > 0 |
| GN-12 | HARD | RAISED_PANEL_FIELD_LT_BORDER | field_depth_mm < border_depth_mm |
| GN-13 | HARD | HOLE_DIAMETER_LT_SPACING | diameter_mm < spacing_mm (no overlap) |
| GN-14 | HARD | TEXT_NOT_EMPTY | EngraveText text must not be empty |
| GN-15 | HARD | RAMP_NON_NEGATIVE | ramp_mm must be >= 0 (0 = no ramp, flat-bottom) |
| GN-16 | HARD | RAMP_CLAMPED | ramp_mm clamped to line_length/2 at G-code generation |
| GN-17 | HARD | FONT_NAME_VALID | EngraveText font must be a bundled HersheyFonts name; validated at PML parse and in params |

---

## Generator Purity

Generators are pure functions: same input always produces same output, and input is never mutated.

**Wrong:**
```python
def generate(self, domain: Domain) -> list[Item]:
    domain.metadata["processed"] = True  # mutation!
    return items
```

**Correct:**
```python
def generate(self, domain: Domain) -> list[Item]:
    # domain is read-only
    return items
```

---

## Profile Parameters

| Parameter | Valid Values |
|-----------|--------------|
| `side` | "outside", "inside", "on" |
| `depth` | "through" or positive float |
| `loop_selection` | "outer_only", "inner_only", "all_loops", or list[int] |

---

## Tab Constraints

If `tab_count > 0`:
- `tab_width_mm` must be > 0
- `tab_height_mm` must be > 0

If `tab_count == 0`, tab dimensions are ignored.

---

## Spacing and Overlap

- All spacing values must be > 0
- For hole grids: `diameter_mm < spacing_mm` (prevents overlap)
- For raised panels: `field_depth_mm < border_depth_mm`

---

## Output Coordinates

Generators emit Items in absolute sheet coordinates, not domain-local coordinates. Coordinate transformation happens before output.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
