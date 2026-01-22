# Recipe 18: Nesting with MaxRects Algorithm

Demonstrates the nesting API using the MaxRects bin-packing algorithm for optimal material utilization.

**Key concepts:**
- MaxRects algorithm with Contact Point heuristic
- Higher utilization than guillotine (~83% vs ~62%)
- Multi-sheet support when parts don't fit on one sheet
- Template expansion for Shaker-style cabinet doors
- Integration with full CAM pipeline

## When to Use

Use **MaxRects** (this recipe) when:
- Material utilization is important (less waste)
- You have many parts of varying sizes
- Processing time is not critical

Use **Guillotine** (Recipe 17) when:
- Speed is more important than utilization
- You have uniform part sizes
- You need simpler, faster packing

## API Overview

```python
from nesting import nest_and_generate

result = nest_and_generate(
    parts=[
        {"name": "door", "width_mm": 400, "height_mm": 600, "quantity": 4},
        {"name": "drawer", "width_mm": 200, "height_mm": 100, "quantity": 8},
    ],
    sheet_width_mm=1220,
    sheet_height_mm=2440,
    sheet_thickness_mm=19,
    kerf_mm=6.35,         # Cutter width (1/4" endmill)
    margin_mm=10,         # No-cut zone on edges
    gap_margin_mm=0,      # Extra margin beyond kerf
    output_format="ast",  # Returns list[LayoutAST]
    algorithm="maxrects", # Use MaxRects for better utilization
)

# Result contains:
# - output: List of LayoutAST objects, one per sheet
# - total_sheets: Number of sheets required
# - utilization: Material utilization (0.0-1.0)
# - nesting_result: Raw NestingResult for inspection
```

## Example: Cabinet Production Run

This recipe nests a realistic cabinet production run requiring multiple sheets:
- 20 large doors (457mm x 597mm / 18" x 23.5") with Shaker template
- 15 small doors (305mm x 203mm / 12" x 8") simple rectangles
- 2 tall doors (457mm x 914mm / 18" x 36") with Shaker template

Total: 37 parts

### Input

See `example.py` for the complete Python script.

```python
parts = [
    {
        "name": "large_door",
        "width_mm": 457,  # 18"
        "height_mm": 597,  # 23.5"
        "quantity": 20,
        "template": "Shaker",
        "template_params": {
            "stile_w": 57,
            "rail_h": 57,
            "panel_recess": 6,
        },
    },
    {
        "name": "small_door",
        "width_mm": 305,  # 12"
        "height_mm": 203,  # 8"
        "quantity": 15,
    },
    {
        "name": "tall_door",
        "width_mm": 457,  # 18"
        "height_mm": 914,  # 36"
        "quantity": 2,
        "template": "Shaker",
        "template_params": {
            "stile_w": 57,
            "rail_h": 57,
            "panel_recess": 6,
        },
    },
]
```

### Output

The MaxRects algorithm:
1. Sorts parts by area (largest first) for optimal packing
2. Maintains a list of free rectangles
3. Uses Contact Point heuristic to maximize edges touching other parts or bin edges
4. Respects kerf gaps between parts
5. Expands templates to full LayoutAST Items
6. Generates separate LayoutAST for each sheet
7. When a sheet is full, starts a new sheet automatically

### Results

- **Total sheets**: 3 (vs 4 with guillotine)
- **Utilization**: ~83% overall (vs ~62% with guillotine)
- **Parts placed**: 37 (20 large + 15 small + 2 tall)

### Comparison with Guillotine

| Metric | Guillotine (Recipe 17) | MaxRects (Recipe 18) |
|--------|------------------------|----------------------|
| Sheets | 4 | 3 |
| Utilization | ~62% | ~83% |
| Algorithm | Simple guillotine cuts | Free rectangle tracking |
| Heuristic | Best Short Side Fit | Contact Point |

## Algorithm Details

The MaxRects algorithm maintains a list of free rectangles and places parts using the **Contact Point** heuristic:

1. **Initialize** with one free rectangle covering the entire bin
2. **For each part**:
   - Find free rectangle that maximizes contact with placed parts or bin edges
   - Place part in that position
   - Split the free rectangle into smaller free rectangles
   - Prune any free rectangles that are fully contained within others
3. **Multi-sheet**: When no suitable free rectangle exists, start new sheet

The Contact Point heuristic tends to create tighter packings by clustering parts together, reducing fragmentation.

## Processing Through CAM

```python
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_hints
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode

for ast in result["output"]:
    # Convert to RemovalIntent IR
    intents = ast_to_removal_intents(ast)

    # Convert to planner hints
    hints = removal_intents_to_hints(intents, kerf_width_mm=6.35)

    # Plan and generate G-code
    passes, _ = plan_passes(hints, config, tool_db, material, machine, stock, safe_z)

    for pass_dict in passes:
        gcode = write_gcode(pass_dict["moves"], safe_z=pass_dict["setup"].safe_z)
```

## Validation

The nesting API includes built-in validation:

```python
from nesting import nest_parts

result = nest_parts(
    parts=parts,
    sheet_width_mm=1220,
    sheet_height_mm=2440,
    sheet_thickness_mm=19,
    kerf_mm=6.35,
    validate=True,  # Enable validation
    algorithm="maxrects",
)

validation = result["validation"]
if not validation["is_valid"]:
    for error in validation["errors"]:
        print(f"ERROR: {error['message']}")
for warning in validation["warnings"]:
    print(f"WARNING: {warning['message']}")
```

Validation checks:
- No overlapping placements
- All placements within sheet bounds
- Kerf gap respected between parts
- Low utilization warning (<50%)
