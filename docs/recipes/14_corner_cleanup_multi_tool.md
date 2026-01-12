# Recipe 14: Corner Cleanup with Multi-Tool Workflow

**Goal:** Machine a rectangular pocket with sharp internal corners using multiple tools - large tool for bulk removal, small tool for corner cleanup.

**Difficulty:** Intermediate
**Time:** 15 minutes
**Prerequisites:** Recipe 02 (pocket basics), Recipe 03 (Shaker door)
**Feature:** Corner cleanup for rectangular pockets

---

## What You'll Learn

- Multi-tool workflow for pockets
- Corner cleanup to remove radiused material
- Tool selection and validation
- Separate pass generation for manual tool changes

---

## The Problem: Radiused Corners

When cutting rectangular pockets with round endmills, the tool leaves radiused internal corners:

```
┌─────────────┐
│             │  Large tool (3/8" = 9.525mm)
│             │  leaves 4.76mm radius corners
│╭───────────╮│
││           ││  ← Radiused corners
│╰───────────╯│     (tool can't reach)
│             │
└─────────────┘
```

**Solution:** After the main pocket pass, use a smaller tool to machine out the corner radius, approaching sharp 90° corners.

---

## Use Case: Shaker Door Panel

A Shaker door panel recess (300mm × 500mm × 6mm deep) cut from 19mm plywood:

1. **Primary pocket:** 3/8" (9.525mm) endmill - fast bulk removal
2. **Corner cleanup:** 1/8" (3.175mm) endmill - sharp corners
3. **Outer profile:** 1/4" (6.35mm) endmill - perimeter cutout

**Workflow:**
- Operator loads 3/8" bit → runs `pocket-9.53mm.nc`
- Operator changes to 1/8" bit → runs `corner_cleanup-3.18mm.nc`
- Operator changes to 1/4" bit → runs `profile-6.35mm.nc`

---

## Design

### Python (Programmatic)

```python
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        # Panel pocket with corner cleanup
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 300, "h_mm": 500}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(
                type="pocket",
                depth=6.0,
                corner_cleanup_tool_diameter_mm=3.175  # 1/8" for corners
            ),
            shape_id="panel"
        ),
        # Outer profile (door perimeter)
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="door_outer"
        ),
    )
)
```

**Key parameter:** `corner_cleanup_tool_diameter_mm=3.175`
- Enables corner cleanup feature
- Specifies exact tool diameter (must exist in tool_db)
- Only supported for rectangular pockets

---

## Step-by-Step Process

### Step 1: Define Tool Database

```python
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.config import Config
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints

# Multi-tool database
tool_db = [
    {
        "name": "1/8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    },
    {
        "name": "1/4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 1200,
        "feed_z": 400,
    },
    {
        "name": "3/8_endmill",
        "diameter": 9.525,
        "kind": "flat",
        "rpm": 10000,
        "feed_xy": 1500,
        "feed_z": 500,
    },
]
```

**Important:** The tool specified in `corner_cleanup_tool_diameter_mm` **must exist** in tool_db, otherwise the planner will error.

---

### Step 2: Convert AST → IR → Hints

```python
# Convert to RemovalIntent IR
intents = ast_to_removal_intents(ast)

# Convert to planner hints
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

# Inspect hints structure
print("Pockets:", len(hints["pockets"]))
print("Corner cleanups:", len(hints["corner_cleanups"]))
# Output:
# Pockets: 1
# Corner cleanups: 1
```

The adapter automatically generates a `corner_cleanups` hint when `corner_cleanup_tool_diameter_mm` is present in the pocket feature.

---

### Step 3: Plan Passes (Multi-Tool)

```python
config = Config(safe_z_mm=6.0, pocket_finish_perimeter=True)
material = Material(name="plywood")
machine = Machine()
stock = Stock(width=450, height=650, thickness=19)

passes, summary = plan_passes(
    hints,
    config=config,
    tool_db=tool_db,
    material=material,
    machine=machine,
    stock=stock,
)

# Inspect passes
for p in passes:
    print(f"{p['op']:15s} → {p['filename']:30s} ({p['tool']['name']})")

# Output:
# pocket          → pocket-9.53mm.nc              (3/8_endmill)
# corner_cleanup  → corner_cleanup-3.18mm.nc     (1/8_endmill)
# profile         → profile-6.35mm.nc            (1/4_endmill)
```

**Note:** Three separate passes, three separate `.nc` files, three manual tool changes.

---

### Step 4: Generate G-code

```python
for pass_rec in passes:
    gcode = write_gcode(pass_rec["moves"], safe_z=config.safe_z_mm)
    filename = pass_rec["filename"]

    with open(filename, 'w') as f:
        f.write(gcode)

    print(f"Generated: {filename} ({len(gcode.splitlines())} lines)")
```

---

## Understanding Corner Cleanup

### Geometry

For a 300mm × 500mm pocket with 3/8" primary tool:

```
Primary tool leaves radiused corners:
- Tool radius: 4.7625mm
- Corner arc radius: 4.7625mm

Corner cleanup tool (1/8" = 3.175mm):
- Generates 4 small circular pockets
- Positioned at pocket corners
- Diameter: 2× tool diameter = 6.35mm (conservative)
- Removes most of radiused material
- Leaves ~1.59mm radius (cleanup tool radius)
```

**Corner positions** (for 300×500mm pocket centered at 225, 325):
- SW: (75, 75)
- SE: (375, 75)
- NE: (375, 575)
- NW: (75, 575)

### Toolpath Strategy

Corner cleanup uses **concentric circular pockets** at each corner:
1. Plunge at corner center
2. Spiral outward in concentric circles
3. Stepdown follows tool's depth_per_pass
4. Finish pass on outermost circle

**Result:** Cleans out radiused material left by primary tool.

---

## Configuration Options

### Option 1: Different Corner Tool

```python
feature=Feature(
    type="pocket",
    depth=6.0,
    corner_cleanup_tool_diameter_mm=1.5875  # 1/16" for very sharp corners
)
```

Smaller tool = sharper corners, but slower and more fragile.

---

### Option 2: Disable Pocket Finish Perimeter

```python
config = Config(
    pocket_finish_perimeter=False,  # Skip wall finish on primary pocket
    safe_z_mm=6.0
)
```

**Use case:** If corner cleanup tool will also clean the walls (if it's not too much smaller).

**Trade-off:** Faster primary pocket pass, but may leave scalloping on non-corner walls.

---

### Option 3: No Corner Cleanup

```python
feature=Feature(
    type="pocket",
    depth=6.0,
    # No corner_cleanup_tool_diameter_mm
)
```

System behaves like Recipe 02 - single tool, radiused corners.

---

## Validation

### Error: Tool Not Found

```python
corner_cleanup_tool_diameter_mm=2.0  # Tool not in database

# Raises:
# ValueError: Corner cleanup tool with diameter 2.0mm not found in tool_db.
# Available tools: [3.175, 6.35, 9.525]
```

**Solution:** Add tool to tool_db or change `corner_cleanup_tool_diameter_mm` to existing tool.

---

### Error: Non-Rectangular Pocket

```python
Item(
    type="Circle",  # Circular pockets have no corners!
    feature=Feature(
        type="pocket",
        depth=6.0,
        corner_cleanup_tool_diameter_mm=3.175  # ERROR
    )
)

# Raises:
# ValueError: Corner cleanup only supported for rectangular pockets, got: Circle
```

**Solution:** Corner cleanup is only for `Rect` pockets. Circles don't have corners.

---

## Performance

Test: 300mm × 500mm × 6mm pocket in plywood

| Pass | Tool | Operations | Time Est. | Purpose |
|------|------|------------|-----------|---------|
| Pocket | 3/8" | Raster + perimeter | ~8 min | Bulk removal |
| Corner cleanup | 1/8" | 4× circular pockets | ~2 min | Sharp corners |
| Profile | 1/4" | Outside cutout | ~3 min | Door perimeter |
| **Total** | | | **~13 min** | |

**Without corner cleanup:** ~11 min total, but radiused 4.76mm corners.

**Trade-off:** +2 minutes for sharp corners (18% time increase).

---

## Common Variations

### Variation 1: Shaker Door Template

```python
from templates import Shaker

# Shaker template doesn't yet support corner_cleanup_tool_diameter_mm
# Manual modification needed:

params = {
    "outer_w": 400.0,
    "outer_h": 600.0,
    "stile_w": 50.0,
    "rail_h": 50.0,
    "panel_recess": 6.0,
}

ast = Shaker.expand_to_ast(params, sheet_thickness_mm=19.0)

# Modify panel item to add corner cleanup
items_list = list(ast.items)
for i, item in enumerate(items_list):
    if item.shape_id == "panel" and item.feature and item.feature.type == "pocket":
        items_list[i] = Item(
            kind=item.kind,
            type=item.type,
            geometry=item.geometry,
            placement=item.placement,
            feature=Feature(
                type=item.feature.type,
                depth=item.feature.depth,
                corner_cleanup_tool_diameter_mm=3.175  # Add corner cleanup
            ),
            shape_id=item.shape_id,
        )

ast = LayoutAST(sheet=ast.sheet, items=tuple(items_list))
```

**Future enhancement:** Add `corner_cleanup_tool_diameter_mm` parameter to Shaker template.

---

### Variation 2: Multiple Pockets

```python
items = (
    Item(
        type="Rect",
        geometry=Geometry(data={"w_mm": 100, "h_mm": 150}),
        placement=Placement(center_xy_mm=(100, 150)),
        feature=Feature(
            type="pocket",
            depth=6.0,
            corner_cleanup_tool_diameter_mm=3.175
        ),
        shape_id="pocket_1"
    ),
    Item(
        type="Rect",
        geometry=Geometry(data={"w_mm": 120, "h_mm": 180}),
        placement=Placement(center_xy_mm=(300, 150)),
        feature=Feature(
            type="pocket",
            depth=6.0,
            corner_cleanup_tool_diameter_mm=3.175  # Same tool
        ),
        shape_id="pocket_2"
    ),
)
```

**Result:** Single `corner_cleanup-3.18mm.nc` file with 8 corner pockets (4 per pocket).

**Efficiency:** Tool changes are grouped - all pockets with same primary tool run first, then all corner cleanups.

---

## Troubleshooting

### Problem: Corner cleanup removes too much material

**Cause:** Corner pocket diameter heuristic (2× tool diameter) is too large.

**Current implementation:** Hard-coded to `2× corner_tool_diameter`.

**Solution (future enhancement):** Make corner pocket diameter configurable:
```python
corner_cleanup_pocket_diameter_mm=5.0  # Custom diameter
```

---

### Problem: Corner cleanup tool breaks

**Cause:** Tool too small/fragile for material or feed rates too aggressive.

**Solution:** Use larger corner tool or reduce feeds:
```python
tool_db = [
    {
        "name": "1/8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 12000,  # Lower RPM
        "feed_xy": 600,  # Slower feed
        "feed_z": 200,   # Slower plunge
    },
]
```

---

### Problem: Corners still not sharp enough

**Cause:** Corner cleanup tool radius still visible.

**Options:**
1. Use smaller tool (1/16" = 1.5875mm)
2. Accept remaining radius (1-2mm typical)
3. Manual chisel cleanup for perfect 90° (woodworking)

**Note:** Perfect 90° internal corners require zero-radius tooling (impossible with round endmills).

---

## Full Example Script

```python
#!/usr/bin/env python3
"""Shaker door with multi-tool corner cleanup."""

from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

# Design: Shaker door 400x600mm, panel recess 300x500mm
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        # Panel pocket (with corner cleanup)
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 300, "h_mm": 500}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(
                type="pocket",
                depth=6.0,
                corner_cleanup_tool_diameter_mm=3.175  # 1/8" corners
            ),
            shape_id="panel"
        ),
        # Door outer profile
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="door_outer"
        ),
    )
)

# Convert to IR and hints
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

# Multi-tool database
tool_db = [
    {"name": "1/8_endmill", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
    {"name": "1/4_endmill", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    {"name": "3/8_endmill", "diameter": 9.525, "kind": "flat", "rpm": 10000, "feed_xy": 1500, "feed_z": 500},
]

# Configuration
config = Config(safe_z_mm=6.0, pocket_finish_perimeter=True)
material = Material(name="plywood")
machine = Machine()
stock = Stock(width=450, height=650, thickness=19)

# Plan passes
passes, summary = plan_passes(
    hints,
    config=config,
    tool_db=tool_db,
    material=material,
    machine=machine,
    stock=stock,
)

# Generate G-code
print("Generating G-code for multi-tool job:")
for pass_rec in passes:
    gcode = write_gcode(pass_rec["moves"], safe_z=config.safe_z_mm)
    filename = pass_rec["filename"]

    with open(filename, 'w') as f:
        f.write(gcode)

    op = pass_rec["op"]
    tool_name = pass_rec["tool"]["name"]
    line_count = len(gcode.splitlines())

    print(f"  {filename:30s} ({op:15s} with {tool_name}, {line_count:5d} lines)")

print("\nWorkflow:")
print("  1. Load 3/8\" endmill → Run pocket-9.53mm.nc")
print("  2. Change to 1/8\" endmill → Run corner_cleanup-3.18mm.nc")
print("  3. Change to 1/4\" endmill → Run profile-6.35mm.nc")
print("  4. Done!")
```

Save as `shaker_with_corner_cleanup.py`, run:
```bash
PYTHONPATH=. python3 shaker_with_corner_cleanup.py
```

---

## Next Steps

- **Recipe 15:** (Future) Tool change comments in G-code for ATC machines
- **Recipe 16:** (Future) Optimizing pass ordering for minimal tool changes

---

## Summary

**Corner cleanup feature enables:**
✅ Sharp internal corners in rectangular pockets
✅ Multi-tool workflow with automatic pass separation
✅ Manual tool change workflow (separate .nc files)
✅ Validation of tool availability

**Key takeaway:** Specify `corner_cleanup_tool_diameter_mm` on pocket features to automatically generate corner cleanup passes with smaller tools.
