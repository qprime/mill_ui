# Domain System Invariants

**Applies to:** Domain algebra, boundary definitions, geometric operations

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| DM-1 | HARD | OUTER_MIN_3_POINTS | Outer boundary must have at least 3 points |
| DM-2 | HARD | INNER_MIN_3_POINTS | Each inner boundary must have at least 3 points |
| DM-3 | HARD | CCW_OUTER | Outer boundaries normalized to counter-clockwise |
| DM-4 | HARD | CW_INNER | Inner boundaries (holes) normalized to clockwise |
| DM-5 | HARD | INNER_CONTAINMENT | Inner boundaries must be fully contained within outer |
| DM-6 | HARD | NO_INNER_OVERLAP | Inner boundaries cannot overlap (except touching) |
| DM-7 | HARD | VALID_GEOMETRY | Shapely polygon must be valid |
| DM-8 | HARD | INSET_NON_NEGATIVE | inset distance must be >= 0 |
| DM-9 | HARD | OFFSET_NON_NEGATIVE | offset distance must be >= 0 |
| DM-10 | HARD | OPERATIONS_RETURN_MULTIDOMAIN | All algebraic operations return MultiDomain |
| DM-11 | STRUCTURAL | MULTIDOMAIN_MAY_BE_EMPTY | Operations may return empty MultiDomain |
| DM-12 | STRUCTURAL | ORIGIN_ROTATION_PRESERVED | Child domains inherit parent's local_origin/rotation |
| DM-13 | HARD | SPLIT_N_MIN_1 | Split operations require n >= 1 |
| DM-14 | HARD | SPLIT_GAP_NON_NEGATIVE | gap_mm must be >= 0 |
| DM-15 | HARD | SPLIT_GAP_FITS | Total gap must fit within dimension |
| DM-16 | HARD | RECT_DIMS_POSITIVE | from_rectangle width/height must be > 0 |
| DM-17 | HARD | VALID_JOIN_STYLES | Join style must be "mitre", "round", or "bevel" |
| DM-18 | STRUCTURAL | AREA_THRESHOLD | Tiny polygons (area < 1e-10) excluded from results |

---

## Boundary Winding Order

Boundaries are normalized on construction:

- **Outer boundary:** Counter-clockwise (CCW)
- **Inner boundaries (holes):** Clockwise (CW)

This follows the Shapely/GeoJSON convention and is enforced automatically.

---

## Algebraic Operations

All domain operations (union, intersection, difference, inset, offset, split) return `MultiDomain`, never a single `Domain`.

**Wrong:**
```python
def inset(self, distance: float) -> Domain:
    ...
```

**Correct:**
```python
def inset(self, distance: float) -> MultiDomain:
    ...
```

**Why:** Operations may produce zero, one, or multiple disjoint regions. Returning `MultiDomain` handles all cases uniformly.

---

## Domain Purity

Generators and operations MUST NOT mutate the input domain.

**Wrong:**
```python
def generate(self, domain: Domain) -> list[Item]:
    domain.boundaries = new_boundaries  # mutation!
    ...
```

**Correct:**
```python
def generate(self, domain: Domain) -> list[Item]:
    modified = domain.inset(10)  # returns new MultiDomain
    ...
```

---

## Split Operations

- `n` must be >= 1
- `gap_mm` must be >= 0
- Total gap `(n-1) * gap_mm` must fit within the dimension being split

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
