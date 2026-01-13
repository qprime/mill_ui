# Recipe 16: Sheet Layout Nesting

Demonstrates efficient nesting of multiple shaker-style cabinet doors and drawer fronts on a half-sheet of MDF with real-world constraints.

**Key concepts:**
- Sheet-level layout optimization with workholding margins
- Multiple profile-outside parts on single sheet
- Kerf allowance between parts
- Maximizing material utilization from waste areas

## Sheet Specifications

- **Material**: Half-sheet MDF (49" x 48.5" actual)
- **Dimensions**: 1245mm x 1232mm x 19mm (3/4")
- **No-carve margin**: 10mm on all sides for workholding
- **Kerf gap**: 6mm between parts (1/4" endmill)

## Parts Produced

### 4x Shaker Cabinet Doors
- Size: 457mm x 597mm (18" x 23.5")
- Frame width: 57mm (2.25") stile/rail
- Panel size: 343mm x 483mm
- Panel recess: 6mm pocket
- Arranged in 2x2 grid

### 7x Shaker-Style Drawer Fronts
- Size: 254mm x 152mm (10" x 6")
- Frame width: 38mm (1.5")
- Panel size: 178mm x 76mm
- Panel recess: 4mm pocket
- Stacked vertically in right waste strip

## Layout Strategy

```
+------------------------------------------+
|  margin                                  |
|  +-------+--+-------+--+-------+         |
|  | Door3 |  | Door4 |  |Drawer7|         |
|  |       |  |       |  +-------+         |
|  |       |  |       |  |Drawer6|         |
|  |       |  |       |  +-------+         |
|  |       |  |       |  |Drawer5|         |
|  +-------+--+-------+--+-------+         |
|  | Door1 |  | Door2 |  |Drawer4|         |
|  |       |  |       |  +-------+         |
|  |       |  |       |  |Drawer3|         |
|  |       |  |       |  +-------+         |
|  |       |  |       |  |Drawer2|         |
|  |       |  |       |  +-------+         |
|  +-------+--+-------+--+Drawer1|         |
|                        +-------+ margin  |
+------------------------------------------+
```

## Material Efficiency

- Door area: 4 × (457 × 597) = 1,091,316 mm²
- Drawer area: 7 × (254 × 152) = 270,256 mm²
- Total part area: 1,361,572 mm²
- Sheet area: 1,533,840 mm²
- Usable area (after margins): 1,491,300 mm²
- **Utilization: ~91%** of usable area
