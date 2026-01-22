# Recipe 17: Automatic Nesting API

Demonstrates the programmatic nesting API for auto-layout of parts on sheets with optimal material utilization.

**Key concepts:**
- Automatic bin-packing using guillotine algorithm
- Multi-sheet support when parts don't fit on one sheet
- Template expansion for Shaker-style cabinet doors
- Integration with full CAM pipeline

## When to Use

Use the nesting API when:
- You have a list of parts with dimensions and quantities
- You want automatic optimal placement (don't want to manually position parts)
- You're generating layouts programmatically (AI, batch processing, etc.)
- You need multi-sheet support for large jobs

Use manual PML (Recipe 16) when:
- You need precise control over part positions
- Parts have special relationship requirements
- You're designing a single-sheet layout interactively

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

The nesting algorithm:
1. Sorts parts by area (largest first) for optimal packing
2. Places parts using guillotine bin-packing with BSSF heuristic
3. Respects kerf gaps between parts
4. Expands templates to full LayoutAST Items
5. Generates separate LayoutAST for each sheet
6. When a sheet is full, starts a new sheet automatically

### Results

- **Total sheets**: 4 (parts distributed across multiple 4'x8' sheets)
- **Utilization**: ~62% overall
- **Parts placed**: 37 (20 large + 15 small + 2 tall)

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

## Variations

### Simple Rectangles Only

```python
parts = [
    {"name": "panel_a", "width_mm": 300, "height_mm": 400, "quantity": 10},
    {"name": "panel_b", "width_mm": 200, "height_mm": 150, "quantity": 20},
]

result = nest_and_generate(parts, 1220, 2440, 19, kerf_mm=6.35, output_format="ast")
```

### Disable Rotation

```python
parts = [
    {"name": "grain_panel", "width_mm": 300, "height_mm": 600, "allow_rotation": False},
]
```

### Limit Sheet Count

```python
from nesting import nest_parts

result = nest_parts(
    parts=parts,
    sheet_width_mm=1220,
    sheet_height_mm=2440,
    sheet_thickness_mm=19,
    kerf_mm=6.35,
    max_sheets=2,  # Limit to 2 sheets
)

# Check for unplaced parts
if result["unplaced"]:
    print(f"Could not place: {result['unplaced']}")
```

### Get PML Output (for debugging)

```python
result = nest_and_generate(
    parts=parts,
    sheet_width_mm=1220,
    sheet_height_mm=2440,
    sheet_thickness_mm=19,
    kerf_mm=6.35,
    output_format="pml",  # Returns list[str] of PML sources
)

for i, pml_source in enumerate(result["output"]):
    print(f"--- Sheet {i+1} ---")
    print(pml_source)
```

## Algorithm Details

The nesting uses a **guillotine bin-packing** algorithm with **Best Short Side Fit (BSSF)** heuristic:

1. **Expand** parts by quantity into individual items
2. **Sort** by area (largest first) - greedy approach
3. **Pack** using guillotine cuts:
   - Find best-fitting free rectangle for each part
   - Place part in corner of free rectangle
   - Split remaining space with guillotine cut
4. **Multi-sheet**: When current sheet is full, start new sheet
5. **Track** any parts that couldn't be placed

This is a simple, fast algorithm suitable for rectangular parts. For complex shapes or tighter packing, consider specialized nesting software.
