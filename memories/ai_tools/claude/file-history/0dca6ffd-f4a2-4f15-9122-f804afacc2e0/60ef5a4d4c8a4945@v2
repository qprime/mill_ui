# Keepout/Island Semantics (Stage 17)

This document describes the keepout feature for creating pockets with preserved material islands (faux raised panels, cutouts).

## Overview

**Keepout** allows you to define regions within a pocket where material should be preserved, creating "islands" or "raised panels". This is essential for decorative panels, recessed regions with preserved sections, and complex multi-level milling.

## Key Concepts

- **Keepout**: A layout node that marks subregions to preserve during pocket milling
- **Island**: The physical result - material left standing within a pocket
- **Region-relative**: Keepouts use the same region-relative composition as other layout nodes
- **Geometry-aware**: Keepouts work with any shape (rect, circle, rounded_rect)

## PML Syntax

```pml
rect <id> pocket <depth>mm
    keepout [id]
        <shape nodes defining island boundaries>
```

## Basic Examples

### Simple Faux Raised Panel

```pml
sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
```

This creates:
- 400×400mm rectangular panel
- 6mm deep pocket
- Preserved rectangular island inset by 50mm (300×300mm island)

### Circular Island

```pml
sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        circle diameter 100.00mm
```

This creates:
- 400×400mm panel with pocket
- Circular island (100mm diameter) preserved at center

### Multiple Islands

```pml
sheet 500.00mm 500.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            inset 50.00mm
                rect island1
    keepout
        inset 200.00mm
            circle fit
```

This creates:
- Two separate islands in the same pocket
- One rectangular island (inset twice)
- One circular island (fit to smaller region)

## Composition Patterns

### Keepout in Grid

Keepouts work inside grid cells:

```pml
grid 2 2 gap 10.00mm
    cell
        rect pocket 5.00mm
            keepout
                inset 20.00mm
                    rect
```

Each grid cell gets its own pocket with keepout island.

### Keepout with Layout Managers

Combine keepouts with any layout manager:

```pml
rect panel pocket 6.00mm
    keepout
        frame 30.00mm
            circle fit
```

This creates a frame-shaped region preserved in the center.

### Rounded Islands

Use rounded_rect for islands with rounded corners:

```pml
rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rounded_rect radius 10.00mm
```

## Resolution Behavior

During layout resolution:

1. **Keepout children are resolved** within the parent region
2. **Island bounds are computed** from resolved keepout shapes
3. **Bounds are stored** in the parent shape's geometry data as `islands` array
4. **Keepout shapes are not emitted** as separate items (they only define island bounds)

Example resolution:

```python
# PML input
rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect

# After resolution
Item(
    kind="shape",
    type="Rect",
    geometry=Geometry(data={
        "w_mm": 400.0,
        "h_mm": 400.0,
        "islands": [
            {
                "x_min": 50.0,
                "x_max": 350.0,
                "y_min": 50.0,
                "y_max": 350.0,
            }
        ]
    }),
    feature=Feature(type="pocket", depth_mm=6.0),
    ...
)
```

## Island Data Structure

Islands are stored as bounding boxes in the shape's geometry data:

```python
{
    "islands": [
        {
            "x_min": float,  # Left edge (absolute sheet coordinates)
            "x_max": float,  # Right edge
            "y_min": float,  # Bottom edge
            "y_max": float,  # Top edge
        },
        ...  # Additional islands
    ]
}
```

For circular islands, the bounding box encloses the circle.

## Constraints (v1)

### Supported Features

- **Keepout with pocket features**: Primary use case
- **Multiple keepouts per shape**: Supported
- **Any shape type for islands**: Rect, Circle, RoundedRect all supported
- **Composition with layout managers**: Full support (inset, frame, grid, split)

### Limitations

- **Nested keepouts not validated**: Keepouts inside keepouts are allowed but not semantically validated
- **Profile features**: Keepouts are ignored for profile features (pockets only)
- **Complex shapes**: Polyline and Line cannot define keepout boundaries (closed shapes only)

## Future Enhancements (Deferred)

- **Validation**: Detect and reject nested keepouts
- **Profile integration**: Keepouts affecting profile operations
- **Toolpath strategy**: Island-aware adaptive clearing strategies
- **Minimum island size**: Validate island dimensions against tool size
- **Island labeling**: Support named islands for multi-pass operations

## Integration with RemovalIntent

The island bounds are available in the Item geometry data. Adapter layers (hints_to_removal.py) can use this information when creating RemovalIntent instances:

```python
# In adapter layer
if "islands" in item.geometry.data:
    island_bounds = [
        Island(
            bounds=Bounds2D(
                x_min=island["x_min"],
                x_max=island["x_max"],
                y_min=island["y_min"],
                y_max=island["y_max"],
            )
        )
        for island in item.geometry.data["islands"]
    ]

    constraints = Constraints(islands=tuple(island_bounds))
```

## Testing

See `v2/tests/test_keepout_islands.py` for comprehensive acceptance tests covering:
- Simple pocket with island
- Keepouts in grid cells
- Multiple keepouts per region
- Round-trip preservation
- Circular and rounded rectangle islands

## Stage 17 Implementation Notes

**Files**:
- `v2/ast/compositional.py`: Keepout node definition
- `v2/resolution/layout_resolver.py`: Island bounds collection logic
- `v2/pml/compositional_parser.py`: PML syntax parsing
- `v2/pml/compositional_formatter.py`: Canonical PML formatting
- `v2/tests/test_keepout_islands.py`: Acceptance tests (7 tests)
- `v2/tests/run_keepout_tests.py`: Standalone test runner

**Compatibility**:
- Existing shapes unchanged (Rect, Circle, RoundedRect)
- Stage 12-16 tests still pass
- No changes to RemovalIntent or strategy/lowering layers (adapter integration deferred)

**Next Steps** (future stages):
- Adapter layer integration: hints_to_removal.py → RemovalIntent with islands
- Toolpath strategy: island-aware clearing algorithms
- Validation: nested keepout detection
- Edge cases: minimum island size, tool clearance validation
