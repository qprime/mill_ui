# Recipe 03: Shaker Cabinet Door Template

**Goal:** Generate a parametric Shaker-style cabinet door using the built-in template.

**Difficulty:** Beginner
**Time:** 10 minutes
**Prerequisites:** Recipe 01 (basic workflow), Recipe 02 (pocket understanding)

---

## What You'll Learn

- Using parametric templates
- Template parameter meaning
- Understanding generated LayoutAST
- Typical cabinet door workflow

---

## What is a Shaker Door?

A traditional cabinet door style:

```
┌────────────────────────────────────┐
│  ╔══════════════════════════════╗  │  ═ = Outer frame (profile cut)
│  ║                              ║  │
│  ║    ┌──────────────────────┐  ║  │  ┌─┐ = Panel recess (pocket)
│  ║    │  Panel Recess (6mm)  │  ║  │
│  ║    │     (Optional)        │  ║  │
│  ║    └──────────────────────┘  ║  │
│  ║                              ║  │
│  ╚══════════════════════════════╝  │
└────────────────────────────────────┘
```

**Features:**
- Outer perimeter (through-cut profile)
- Panel recess (optional pocket, typically 6mm deep)
- Parametric: Adjust size, frame width, panel depth

---

## Template Parameters

```python
from templates import Shaker

ast = Shaker.expand_to_ast(
    params={
        "outer_w": 400.0,         # Total width (mm)
        "outer_h": 600.0,         # Total height (mm)
        "stile_w": 50.0,          # Vertical frame width (mm)
        "rail_h": 50.0,           # Horizontal frame width (mm)
        "panel_recess": 6.0,      # Panel pocket depth (mm), 0 for no pocket
    },
    sheet_thickness_mm=19.0
)
```

### Parameter Guide

| Parameter | Description | Typical Range | Example |
|-----------|-------------|---------------|---------|
| `outer_w` | Door width | 200-600mm | 400mm |
| `outer_h` | Door height | 300-900mm | 600mm |
| `stile_w` | Frame width (vertical) | 40-70mm | 50mm |
| `rail_h` | Frame width (horizontal) | 40-70mm | 50mm |
| `panel_recess` | Panel depth | 0-10mm | 6mm (0=flat) |

**Note:** `stile_w` and `rail_h` are often the same (e.g., 50mm) but can differ for design variation.

---

## Step-by-Step: Basic Shaker Door

### Step 1: Generate LayoutAST

```python
#!/usr/bin/env python3
from templates import Shaker

# Define parameters
params = {
    "outer_w": 400.0,
    "outer_h": 600.0,
    "stile_w": 50.0,
    "rail_h": 50.0,
    "panel_recess": 6.0,
}

# Generate AST
ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)

# Inspect
print(f"Sheet: {ast.sheet.width_mm}mm × {ast.sheet.height_mm}mm × {ast.sheet.thickness_mm}mm")
print(f"Items: {len(ast.items)}")
for item in ast.items:
    print(f"  - {item.shape_id}: {item.feature.type} ({item.feature.depth})")
```

**Expected output:**
```
Sheet: 450.0mm × 650.0mm × 19.0mm
Items: 2
  - door_outer: profile (through)
  - door_panel: pocket (6.0mm)
```

**What happened:**
- Template calculated sheet size with margin (450mm × 650mm for 400mm × 600mm door)
- Generated 2 items:
  1. Outer profile (through-cut)
  2. Panel pocket (6mm deep)

---

### Step 2: Visualize LayoutAST as JSON

```python
import json

# Export to JSON
json_output = ast.to_json()
print(json.dumps(json.loads(json_output), indent=2))
```

**Expected structure:**
```json
{
  "sheet": {
    "width_mm": 450.0,
    "height_mm": 650.0,
    "thickness_mm": 19.0
  },
  "items": [
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": {"w_mm": 400.0, "h_mm": 600.0},
      "placement": {"center_xy_mm": [225.0, 325.0]},
      "feature": {"type": "profile", "side": "outside", "depth": "through"},
      "shape_id": "door_outer"
    },
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": {"w_mm": 300.0, "h_mm": 500.0},
      "placement": {"center_xy_mm": [225.0, 325.0]},
      "feature": {"type": "pocket", "depth_mm": 6.0},
      "shape_id": "door_panel"
    }
  ]
}
```

**Panel size calculation:**
- Outer: 400mm × 600mm
- Frame: 50mm on all sides
- Panel: 400 - 2×50 = 300mm wide, 600 - 2×50 = 500mm tall

---

### Step 3: Generate G-code

```python
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.plan import plan_all_passes
from cam.model.setup import Setup
from cam.model.tool import Tool
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

# Convert to IR
intents = ast_to_removal_intents(ast)

print(f"Generated {len(intents)} removal intents:")
for intent in intents:
    print(f"  {intent.region_id}: {intent.z_top}mm to {intent.z_bottom}mm, allowance={intent.allowance}")

# Setup
tool = Tool(name="6mm_endmill", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
stock = Stock(width=450, height=650, thickness=19)
material = Material(name="MDF")
machine = Machine(name="grbl_router")
setup = Setup(stock=stock, tool=tool, material=material, machine=machine, safe_z=5.0)

# Config (pocket finish enabled by default)
config = Config(pocket_finish_perimeter=True)

# Generate
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
gcode = plan_all_passes(hints, setup, config)

# Save
with open("shaker_door.nc", "w") as f:
    f.write(gcode)

print(f"\n✓ Generated {len(gcode.splitlines())} lines → shaker_door.nc")
```

**Expected output:**
```
Generated 2 removal intents:
  door_outer: 0.0mm to -19.0mm, allowance=outside
  door_panel: 0.0mm to -6.0mm, allowance=inside

✓ Generated 1247 lines → shaker_door.nc
```

---

## Common Variations

### Variation 1: Flat Door (No Panel Recess)

```python
params = {
    "outer_w": 400.0,
    "outer_h": 600.0,
    "stile_w": 50.0,
    "rail_h": 50.0,
    "panel_recess": 0.0,  # Flat door, no pocket
}

ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)
```

**Result:** Only 1 item (outer profile), no panel pocket.

---

### Variation 2: Wider Frame (Mission Style)

```python
params = {
    "outer_w": 400.0,
    "outer_h": 600.0,
    "stile_w": 70.0,  # Wider frame (70mm instead of 50mm)
    "rail_h": 70.0,
    "panel_recess": 8.0,  # Deeper recess
}
```

**Effect:**
- Bolder appearance
- Smaller panel (400 - 2×70 = 260mm wide)

---

### Variation 3: Different Stile/Rail Widths

```python
params = {
    "outer_w": 400.0,
    "outer_h": 600.0,
    "stile_w": 50.0,  # Narrow vertical frame
    "rail_h": 80.0,   # Wide horizontal frame (top/bottom emphasis)
    "panel_recess": 6.0,
}
```

**Effect:** Asymmetric design (wider top/bottom bars).

---

### Variation 4: Multiple Doors on One Sheet

```python
from layout_ast.layout import LayoutAST, Sheet

# Generate 2 doors
door1_ast = Shaker.expand_to_ast(
    {"outer_w": 300, "outer_h": 500, "stile_w": 50, "rail_h": 50, "panel_recess": 6},
    sheet_thickness_mm=19.0
)
door2_ast = Shaker.expand_to_ast(
    {"outer_w": 350, "outer_h": 600, "stile_w": 50, "rail_h": 50, "panel_recess": 6},
    sheet_thickness_mm=19.0
)

# Manually combine on larger sheet (requires manual placement)
# Note: Template currently generates individual sheets.
# For multi-part layouts, use compositional PML grid layout instead.
```

**Better approach for multiple parts:** Use compositional PML `place grid`:

```pml
sheet 1200mm 800mm 19mm

place grid 1 2 gap 50mm
    use ShakerDoor1
    use ShakerDoor2
```

(Requires defining components in PML, not yet supported by Python template API. Future enhancement.)

---

## Understanding Generated Geometry

### Outer Profile Calculation

Template generates:
```python
Item(
    type="Rect",
    geometry=Geometry(data={"w_mm": outer_w, "h_mm": outer_h}),
    placement=Placement(center_xy_mm=(sheet_cx, sheet_cy)),
    feature=Feature(type="profile", side="outside", depth="through"),
    shape_id="door_outer"
)
```

**Sheet centering:**
- Sheet has 25mm margin on all sides
- `sheet_cx = (outer_w + 50) / 2`
- `sheet_cy = (outer_h + 50) / 2`

---

### Panel Pocket Calculation

Template generates:
```python
panel_w = outer_w - 2 * stile_w
panel_h = outer_h - 2 * rail_h

Item(
    type="Rect",
    geometry=Geometry(data={"w_mm": panel_w, "h_mm": panel_h}),
    placement=Placement(center_xy_mm=(sheet_cx, sheet_cy)),  # Same center as outer
    feature=Feature(type="pocket", depth_mm=panel_recess),
    shape_id="door_panel"
)
```

**Key insight:** Panel is concentric with outer profile.

---

## Machining Order

The planner determines pass order automatically:

1. **Profile pass (outside):**
   - Multi-depth (typically 3mm stepdown for 19mm stock)
   - Cuts outer perimeter
   - **Note:** Part will be loose after this! Use tabs or clamps.

2. **Pocket pass (if panel_recess > 0):**
   - Rough raster (leaves margin if finish enabled)
   - Finish profile (cleans walls)
   - Depth: 6mm (single level or multi-depth depending on step_down)

---

## Adding Tabs (Hold-Down)

Templates currently don't include tabs. Add manually in LayoutAST:

```python
from layout_ast.layout import Constraint, Tab

# Modify the profile item to include tabs
profile_item = ast.items[0]  # Outer profile
profile_with_tabs = replace(
    profile_item,
    feature=replace(
        profile_item.feature,
        constraints=Constraint(
            tabs=[
                Tab(position=(50, 300), width_mm=10, height_mm=3),  # Left side
                Tab(position=(350, 300), width_mm=10, height_mm=3), # Right side
            ]
        )
    )
)

# Rebuild AST
ast = replace(ast, items=(profile_with_tabs, ast.items[1]))
```

**Future:** Template could accept `tabs=True` parameter to auto-generate tabs.

---

## Troubleshooting

### Problem: Panel pocket is too small or missing

**Cause:** Frame width (`stile_w` + `rail_h`) is too large for door size.

**Check:**
```python
panel_w = outer_w - 2 * stile_w
panel_h = outer_h - 2 * rail_h

if panel_w <= 0 or panel_h <= 0:
    print("ERROR: Panel would be negative size!")
```

**Fix:** Reduce frame width or increase door size.

**Example:**
- Door: 200mm × 200mm
- Frame: 100mm (each side)
- Panel: 200 - 2×100 = 0mm (invalid!)
- Solution: Reduce frame to 60mm → panel = 200 - 2×60 = 80mm

---

### Problem: Door falls out after profile cut

**Cause:** No tabs or hold-down method.

**Solutions:**
1. Add tabs (see "Adding Tabs" above)
2. Use double-sided tape on waste areas
3. Use vacuum table or clamps
4. Cut profile passes last (do pocket first)

**Recommended:** Add tabs for production work.

---

### Problem: Panel pocket has scalloped walls

**Cause:** Finish perimeter might be disabled.

**Check:**
```python
config = Config.from_env()
print(f"Pocket finish: {config.pocket_finish_perimeter}")
```

**Fix:** Enable finish (it's on by default):
```python
config = Config(pocket_finish_perimeter=True)
```

---

## Material Considerations

### MDF (Medium-Density Fiberboard)

```python
material = Material(name="MDF")
config = Config(
    pocket_finish_perimeter=True,  # Recommended: MDF benefits from clean walls
    cleanup_offset_mm=0.25,        # Default is fine
)
```

**Feeds/speeds:**
- Spindle: 18000 RPM
- Feed XY: 2000 mm/min
- Feed Z: 300 mm/min

---

### Plywood

```python
material = Material(name="Plywood")
config = Config(
    pocket_finish_perimeter=True,  # Recommended: prevents tear-out on cross-grain
)
```

**Note:** Use downcut bit for finish pass to reduce tear-out.

---

### Hardwood (Maple, Oak)

```python
material = Material(name="Maple")
# Slower feeds for hardwood
tool = Tool(name="6mm_carbide", diameter=6.0, rpm=18000, feed_xy=1200, feed_z=200)
```

---

## Next Steps

- **Recipe 04:** Create your own custom template
- **Recipe 05:** Validate designs before machining
- **Recipe 06:** Combine multiple features at different depths

---

## Full Example Script

```python
#!/usr/bin/env python3
"""Complete Shaker door generation: Template → G-code"""

from templates import Shaker
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.plan import plan_all_passes
from cam.model.setup import Setup
from cam.model.tool import Tool
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

# 1. Define door parameters
params = {
    "outer_w": 400.0,
    "outer_h": 600.0,
    "stile_w": 50.0,
    "rail_h": 50.0,
    "panel_recess": 6.0,
}

# 2. Generate LayoutAST from template
ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)
print(f"✓ Generated LayoutAST: {len(ast.items)} items")

# 3. Convert to RemovalIntent IR
intents = ast_to_removal_intents(ast)
print(f"✓ Converted to IR: {len(intents)} removal intents")

# 4. Setup tooling
tool = Tool(name="6mm_endmill", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
stock = Stock(width=450, height=650, thickness=19)
material = Material(name="MDF")
machine = Machine(name="grbl_router")
setup = Setup(stock=stock, tool=tool, material=material, machine=machine, safe_z=5.0)

# 5. Configure (pocket finish enabled by default)
config = Config(pocket_finish_perimeter=True)

# 6. Generate G-code
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
gcode = plan_all_passes(hints, setup, config)

# 7. Save output
with open("shaker_door.nc", "w") as f:
    f.write(gcode)

print(f"✓ Generated {len(gcode.splitlines())} lines of G-code → shaker_door.nc")
print()
print("Next steps:")
print("  1. Verify G-code: grep 'BEGIN' shaker_door.nc")
print("  2. Simulate: camotics shaker_door.nc")
print("  3. Machine: Load shaker_door.nc into your CNC controller")
```

Save as `generate_shaker_door.py`, run:
```bash
PYTHONPATH=. python3 generate_shaker_door.py
```

**Output:**
```
✓ Generated LayoutAST: 2 items
✓ Converted to IR: 2 removal intents
✓ Generated 1247 lines of G-code → shaker_door.nc

Next steps:
  1. Verify G-code: grep 'BEGIN' shaker_door.nc
  2. Simulate: camotics shaker_door.nc
  3. Machine: Load shaker_door.nc into your CNC controller
```
