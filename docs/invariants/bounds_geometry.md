# Bounds & Geometry Invariants

**Applies to:** Bounds validation, shape calculations, coordinate ordering

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| BG-1 | HARD | X_ORDERING | x_max >= x_min (raises ValueError if violated) |
| BG-2 | HARD | Y_ORDERING | y_max >= y_min (raises ValueError if violated) |
| BG-3 | HARD | Z_ORDERING | z_bottom <= z_top (raises ValueError if violated) |
| BG-4 | HARD | POLYGON_MIN_3 | Polygon requires at least 3 points |
| BG-5 | HARD | POLYLINE_MIN_2 | Polyline requires at least 2 points |
| BG-6 | HARD | NORMALIZED_RANGE | Polyline/Spline points in [0.0, 1.0] range |
| BG-7 | HARD | SPLINE_TOLERANCE_POSITIVE | SplinePath tolerance_mm must be > 0 |
| BG-8 | STRUCTURAL | RECT_CENTER_BASED | Rect bounds are ±half_width/half_height from center |
| BG-9 | STRUCTURAL | CIRCLE_DIAMETER_RADIUS | Circle radius = diameter / 2 |
| BG-10 | FALLBACK | UNKNOWN_SHAPE_FALLBACK | Unknown shapes return 1x1mm box at center |
| BG-11 | HARD | IR_POINTS_BOUNDS_CENTERED | RemovalIntent `shape_geometry` points, holes, start and end are relative to `bounds.center` |

---

## Bounds Ordering

All bounds must maintain proper ordering:

```python
# X and Y: max >= min
assert x_max >= x_min
assert y_max >= y_min

# Z: bottom <= top (because Z is inverted for depth)
assert z_bottom <= z_top
```

These are enforced at construction time and raise `ValueError` on violation.

---

## Center-Based Rectangles

Rectangle bounds are calculated from center:

```python
x_min = center_x - width / 2
x_max = center_x + width / 2
y_min = center_y - height / 2
y_max = center_y + height / 2
```

---

## Point Frame in the IR (BG-11)

An Item's `points`, `holes`, `start` and `end` are relative to `placement.center_xy_mm`, which is often not the bounds center: `shapely_to_item` uses the centroid, and `polyline_engrave_item` uses the mean of the points. Every planner pass adds these fields to `FeatureInput.center_xy_mm`, which the adapter takes from `RemovalIntent.bounds.center`.

`_geometry_dict_to_shape_geometry` (`adapters/hints_to_removal.py`) therefore re-bases them onto the bounds center when an Item becomes a RemovalIntent. Offsets below 1e-9 mm are float noise and are treated as zero, so shapes already centered on their bounds keep their exact coordinates.

---

## Normalized Coordinates

Polyline and Spline points use normalized [0.0, 1.0] coordinates within their parent domain. These are resolved to absolute coordinates during layout resolution.

---

## Fallback Behavior

Unknown shapes return a 1x1mm bounding box centered at the shape's center. This is defensive—if you see this behavior, it indicates an upstream bug (shape type not recognized).

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
| FALLBACK | Defensive behavior, signals upstream bug |
