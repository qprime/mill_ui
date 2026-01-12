# Corner Cleanup Multi-Tool Workflow

Complete implementation of automatic corner cleanup for rectangular pockets using multi-tool workflows.

## Usage

### Option 1: PML (Human-Friendly)
```pml
sheet 450mm 650mm 19mm

rect panel at 225mm,325mm size 300mm,500mm pocket 6mm corner_cleanup 3.175mm
rect door at 225mm,325mm size 400mm,600mm profile through outside
```

### Option 2: Python (Programmatic)
```python
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        Item(
            type="Rect",
            geometry=Geometry(data={"w_mm": 300, "h_mm": 500}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(
                type="pocket",
                depth=6.0,
                corner_cleanup_tool_diameter_mm=3.175
            ),
            shape_id="panel"
        ),
    )
)
```

### Option 3: JSON (AI-Generated)
```json
{
  "feature": {
    "type": "pocket",
    "depth_mm": 6.0,
    "corner_cleanup_tool_diameter_mm": 3.175
  }
}
```

## Output

Three separate G-code files for manual tool changes:
1. `pocket-9.53mm.nc` - Primary pocket with 3/8" bit
2. `corner_cleanup-3.17mm.nc` - Corner cleanup with 1/8" bit
3. `profile-6.35mm.nc` - Outer profile with 1/4" bit

## Files

- [shaker_corner_cleanup.pml](shaker_corner_cleanup.pml) - PML example
- [corner_cleanup_example.py](corner_cleanup_example.py) - Python example
- [../14_corner_cleanup_multi_tool.md](../14_corner_cleanup_multi_tool.md) - Complete recipe guide

## Testing

```bash
# Test PML syntax
PYTHONPATH=. python3 tests/test_pml_corner_cleanup.py

# Test feature implementation
PYTHONPATH=. python3 tests/test_corner_cleanup.py

# Run example
cd docs/recipes/14_corner_cleanup_multi_tool
PYTHONPATH=../../.. python3 corner_cleanup_example.py
```

All tests pass!
