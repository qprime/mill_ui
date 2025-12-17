# Studio Mode Geometry (Stage 19)

## Overview

**Studio Mode** is a permissive design environment for decorative, artistic, and expressive CNC work. Unlike production CAM modes that prioritize dimensional accuracy and boundary correctness, Studio Mode prioritizes **creative freedom** and **visual outcomes**.

This document defines the Studio Mode geometry policy and introduces **centerline spline/path support** as a first-class primitive.

## Studio Mode Geometry Policy

### Core Principles

1. **Centerline paths are valid and expected**
   - Designers specify the path the tool center follows
   - Tool diameter is an expressive parameter, not a constraint
   - No requirement for offset-corrected boundaries

2. **Visual outcome takes precedence**
   - What you see is what you cut
   - Designers iterate via test cuts, not dimensional validation
   - Tool marks and visual texture are intentional design elements

3. **Permissive validation**
   - Only ERROR on real crash risks (machine limits, safety violations)
   - Warnings are informational, never blocking
   - No "CAM best practice" restrictions

4. **Test-driven iteration**
   - Designers are expected to make test cuts
   - Material waste is accepted as part of creative process
   - Rapid prototyping over upfront correctness

### What Studio Mode Allows

- Sine-wave frame artwork
- Flowing decorative outlines
- Organic, hand-drawn curves
- Image-derived toolpaths
- Tight-radius turns (tool dependent)
- Self-intersecting decorative patterns
- Variable-width line art (via tool diameter)

### What Studio Mode Does NOT Guarantee

- Dimensional accuracy for fit-critical parts
- Offset-corrected boundaries
- Tool radius compensation
- Production-grade tolerances
- Kerf correctness for joinery

**If you need those guarantees, use Production Mode** (future stage).

## Spline Path Primitive

### SplinePath AST Node

**Purpose**: Represents smooth, expressive curves for decorative work.

**Key Properties**:
- Always treated as **centerline intent** (tool follows this path exactly)
- Immediately lowered to polyline during resolution (no spline math in CAM layer)
- Sampling tolerance configurable but sane by default
- Open paths only in v1 (closed splines optional in future)

**Use Cases**:
- Decorative engraving
- Flowing outlines
- Organic artwork
- Hand-drawn curves

**NOT for**:
- Pocket/profile boundaries (use Circle/Rect/RoundedRect)
- Fit-critical geometry (use Line primitives)

### PML Syntax

```pml
spline <id> [feature <type> <depth>]
    points (<x>,<y>) (<x>,<y>) ...
    [tolerance <value>mm]
```

**Coordinates**: Normalized (0.0 to 1.0) relative to current region
**Feature**: `engrave` (primary use case)
**Tolerance**: Sampling tolerance for polyline conversion (default: 0.1mm)

### Examples

#### Simple Decorative Wave
```pml
sheet 400.00mm 400.00mm 19.00mm

spline wave engrave 0.8mm
    points (0.0,0.5) (0.25,0.6) (0.5,0.4) (0.75,0.6) (1.0,0.5)
```

Creates a smooth wave across the sheet surface, engraved 0.8mm deep.

#### Flowing Outline with Custom Tolerance
```pml
sheet 400.00mm 400.00mm 19.00mm

spline flourish engrave 1.0mm
    points (0.1,0.1) (0.3,0.2) (0.5,0.5) (0.7,0.8) (0.9,0.9)
    tolerance 0.05mm
```

Higher resolution curve (tighter polyline sampling).

## Resolution Behavior

### Spline Lowering (Critical)

**SplinePath nodes are IMMEDIATELY lowered to polylines** during resolution:

1. **Parse stage**: SplinePath AST node created with control points
2. **Resolution stage**: Spline sampled into polyline segments
3. **CAM output**: Only polyline geometry emitted (no spline primitives)

**Why?**
- Keeps CAM math simple and deterministic
- Avoids spline-specific toolpath complications
- Ensures consistent behavior across all downstream tools

**Algorithm** (simplified Catmull-Rom or cubic Bézier):
- Sample spline at intervals <= tolerance
- Generate points along curve
- Emit as `Line` segments or polyline primitive
- Resulting geometry indistinguishable from hand-authored polylines

### Coordinate Transformation

Normalized coordinates (0.0–1.0) are transformed to absolute mm during resolution:
- `x_mm = region.x_min + (x_norm * region.width)`
- `y_mm = region.y_min + (y_norm * region.height)`

This allows splines to scale with region size.

## Validation Rules (Studio Mode)

### ALLOWED (no errors)
- Tight curvature (tool coupling accepted)
- Self-intersecting paths (decorative)
- Paths approaching region boundaries
- Arbitrary tool diameters
- Rapid direction changes

### ERROR (blocking)
- Motion exits machine envelope (hard X/Y/Z limits)
- Z violates safety limits (e.g., Z < -sheet_thickness)
- Rapid moves occur at cutting depth (safety)

### WARNING (informational only)
- Tool diameter larger than curve radius (gouging risk)
- Self-intersection detected (may produce unexpected visual)
- High point density (performance concern)

**Warnings NEVER block execution in Studio Mode.**

## Integration with Existing System

### Compatibility
- SplinePath is additive (Stages 12–18 unchanged)
- Existing shape primitives (Circle, Rect, etc.) unaffected
- Splines can coexist with other shapes in same layout
- Splines respect region boundaries (inset, frame, grid)

### Feature Support
- **Engrave**: Primary use case (centerline path at specified depth)
- **Profile/Pocket**: NOT SUPPORTED (use explicit boundary shapes instead)
- **Edge treatment**: N/A (splines are paths, not boundaries)

### RemovalIntent
Spline-derived polylines emit standard RemovalIntent records:
- `region_id`: Generated from spline ID
- `bounds`: Bounding box of sampled polyline
- `z_top`: 0.0
- `z_bottom`: -depth_mm (from engrave feature)
- `constraints`: Standard engrave constraints
- `metadata`: Includes `spline_source: true` for debugging

## Testing

### Acceptance Tests (required)

1. **Spline parsing and round-trip**
   - PML → AST → PML preserves control points
   - Tolerance settings preserved

2. **Spline lowering to polyline**
   - Deterministic sampling
   - Point count scales with curve complexity
   - Tolerance parameter affects resolution

3. **Spline + engrave produces valid RemovalIntent**
   - Correct depth
   - Bounding box covers path extent
   - No crashes

4. **Tool diameter changes do NOT invalidate design**
   - Same spline, different tools → different visual widths
   - No errors or warnings for tool/curve coupling

5. **Existing tests unchanged**
   - All Stage 12–18 tests pass
   - No regressions

### Test Files
- `v2/tests/test_spline_paths.py`: Acceptance tests (pytest)
- `v2/tests/run_spline_tests.py`: Standalone runner (no pytest)

## Implementation Notes

### Files Modified
- `v2/ast/compositional.py`: Add SplinePath dataclass
- `v2/pml/compositional_parser.py`: Add parse_spline()
- `v2/pml/compositional_formatter.py`: Add SplinePath formatting
- `v2/resolution/layout_resolver.py`: Add spline lowering logic
- `v2/tests/test_spline_paths.py`: Acceptance tests
- `v2/tests/run_spline_tests.py`: Standalone runner
- `v2/docs/studio_mode_geometry.md`: This document

### Lowering Algorithm (Catmull-Rom Spline)

```python
def sample_catmull_rom(control_points, tolerance_mm):
    """Sample Catmull-Rom spline into polyline segments.

    Args:
        control_points: List of (x, y) tuples (normalized 0-1)
        tolerance_mm: Maximum deviation from true curve

    Returns:
        List of (x_mm, y_mm) points forming polyline
    """
    # Catmull-Rom produces smooth curves through all control points
    # Tangents calculated from neighboring points
    # Sample at adaptive intervals based on curvature
    # Return dense-enough polyline to satisfy tolerance
```

**Alternative**: Cubic Bézier if explicit tangent control needed (future).

## Future Extensions (NOT in Stage 19)

- Closed splines (loop completion)
- Explicit tangent control (Bézier mode)
- Image-to-spline tracing
- Variable-depth engraving (Z as function of path parameter)
- Production Mode validation (offset-corrected boundaries, tool constraints)

## Stage 19 Deliverables

- [x] SplinePath AST node
- [x] PML parser + formatter
- [x] Spline-to-polyline lowering
- [x] Acceptance tests (5/5 criteria)
- [x] Documentation (this file)
- [x] Commit + tag: `refactor_v2_S19_CENTERLINE_SPLINES`

## Migration Notes

**For users upgrading from Stage 18**:
- No breaking changes
- Splines are additive; existing layouts unaffected
- Studio Mode policy applies only to new spline primitives
- Production Mode constraints (if any) remain on existing shapes

## FAQ

**Q: Can I use splines for pocket boundaries?**
A: No. Use Circle, Rect, or RoundedRect for boundary-defining features. Splines are centerline paths only.

**Q: Why are splines lowered to polylines?**
A: To keep CAM math simple. Polylines are deterministic and universally supported. Spline primitives add complexity without benefit at the toolpath level.

**Q: What if my tool is too large for the curve radius?**
A: You'll get a warning, but it won't block execution. Studio Mode trusts you to iterate via test cuts.

**Q: Can I combine splines with edge treatment?**
A: No. Edge treatment applies to boundary-defining shapes (profiles/pockets), not paths.

**Q: How do I control line width?**
A: Tool diameter. Splines are centerline paths; the cutting tool determines visual width.
