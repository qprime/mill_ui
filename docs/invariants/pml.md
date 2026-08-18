# PML Parsing Invariants

**Applies to:** PML parser, syntax handling

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| PM-1 | STRUCTURAL | DIMENSION_MM_SUFFIX | Accepts "NNNmm" format |
| PM-2 | STRUCTURAL | DIMENSION_BARE_NUMBER | Accepts bare numbers (int/float) |
| PM-3 | STRUCTURAL | THROUGH_SPECIAL | "through" is special depth value |
| PM-4 | HARD | SINGLE_TYPE_KEY | Each node must have exactly one uppercase key |
| PM-5 | HARD | FEATURE_REQUIRES_TYPE | Feature dict must have "type" key |
| PM-6 | POLICY | DEPTH_DEFAULT_THROUGH | depth defaults to "through" |
| PM-7 | HARD | KEEPOUT_NO_NESTING | Nested Keepout nodes not allowed |
| PM-8 | HARD | INSET_REQUIRES_DISTANCE | Inset requires "distance" key |
| PM-9 | HARD | FRAME_REQUIRES_WIDTH | Frame requires "width" key |
| PM-10 | HARD | PROFILE_REQUIRES_SIDE | Profile requires "side" key |
| PM-11 | STRUCTURAL | PHYSICAL_OR_WORKING | Sheet uses physical or working dimensions |
| PM-12 | STRUCTURAL | CENTER_COORDS | at.x and at.y specify part CENTER |
| PM-13 | HARD | FACE_BACK_SCOPE | `face: back` valid only on pocket/hole/engrave with a finite depth |

---

## Dimension Formats

Both formats are valid:

```yaml
width: 100mm    # with suffix
width: 100      # bare number (interpreted as mm)
```

---

## Special Values

| Value | Meaning |
|-------|---------|
| `"through"` | Cut through entire material thickness |

---

## Node Structure

Each PML node must have exactly one uppercase key identifying its type:

```yaml
# Correct
- Rect:
    width: 100mm
    height: 50mm

# Wrong (multiple type keys)
- Rect:
    Circle:  # invalid
```

---

## Required Keys by Node Type

| Node Type | Required Keys |
|-----------|---------------|
| Feature | `type` |
| Inset | `distance` |
| Frame | `width` |
| Profile | `side` |

---

## Coordinate Semantics

`at.x` and `at.y` specify the CENTER of the part, not the corner.

```yaml
- Rect:
    at: {x: 100, y: 100}  # center at (100, 100)
    width: 50
    height: 30
# Actual bounds: x=[75, 125], y=[85, 115]
```

---

## Face Semantics

`Feature.face` (`front` / `back`, PM-13) selects the panel surface a feature is machined from. It is unrelated to `Feature.side` (`inside` / `outside`), which selects the offset side of a profile.

Beam primitives carry a separate `FaceFeature.face` (`assembly/beam.py`) naming a face of a beam blank. That field is stored and never consumed by the CAM pipeline; it does not select a machining setup and must not be routed into the panel face mechanism.

---

## Sheet Dimensions

Sheet can specify either:
- `physical_width` / `physical_height` (total sheet size)
- `width` / `height` (working area, margin=0 implied)

Working area = physical - 2*margin

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
| POLICY | Current default, can change with care |
