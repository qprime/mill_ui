# Recipe 02: Pocket with Finish Cleanup Pass

**Goal:** Create a rectangular pocket with optional perimeter finish pass to clean scalloped walls.

**Difficulty:** Beginner
**Time:** 10 minutes
**Prerequisites:** Recipe 01 (understanding basic workflow)
**Feature:** F001 Pocket Wall Cleanup Pass

---

## What You'll Learn

- Pocket feature syntax
- Finish perimeter cleanup pass (default behavior)
- Comparing rough-only vs rough+finish strategies
- Configuring cleanup offset
- Understanding raster scalloping problem

---

## The Problem: Scalloped Walls

When cutting pockets with a raster (zigzag) strategy:

```
Tool path (top view):
┌─────────────────┐
│ →→→→→→→→→→→→→→→ │  Round bit creates scallops
│ ←←←←←←←←←←←←←←← │  on walls perpendicular to
│ →→→→→→→→→→→→→→→ │  raster direction
└─────────────────┘
     ↑ Scallops here
```

**Solution:** Add a finish profile pass around the perimeter after rough raster.

**mill_ui default:** `pocket_finish_perimeter=True` (enabled by default since F001)

---

## The Design

We'll create a 100mm × 80mm pocket, 6mm deep, in a 200mm × 150mm × 19mm sheet.

### PML (Compositional)

```pml
sheet 200mm 150mm 19mm

rect panel pocket 6mm
    center 100mm 75mm
    size 100mm 80mm
```

Save as `pocket_with_cleanup.pml`

### Python (Programmatic)

```python
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

ast = LayoutAST(
    sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
            placement=Placement(center_xy_mm=(100, 75)),
            feature=Feature(type="pocket", depth_mm=6.0),
            shape_id="panel"
        ),
    )
)
```

---

## Step-by-Step Process

### Step 1: Generate with Default (Finish Enabled)

```python
#!/usr/bin/env python3
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

# Create design
ast = LayoutAST(
    sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
            placement=Placement(center_xy_mm=(100, 75)),
            feature=Feature(type="pocket", depth_mm=6.0),
            shape_id="panel"
        ),
    )
)

# Convert to IR
intents = ast_to_removal_intents(ast)

# Config with finish enabled (DEFAULT)
config = Config(pocket_finish_perimeter=True)  # This is the default

# Generate
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

tool_db = [
    {"name": "6mm_flat", "diameter": 6.0, "kind": "flat", "rpm": 18000, "feed_xy": 2000, "feed_z": 300}
]
material = Material(name="MDF")
machine = Machine()
stock = Stock(width=200, height=150, thickness=19)

def plan_gcode(cfg: Config) -> str:
    passes, _summary = plan_passes(
        hints,
        config=cfg,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
    )
    return "\n".join(write_gcode(p["moves"], safe_z=cfg.safe_z_mm) for p in passes if p.get("moves"))

gcode_with_finish = plan_gcode(config)

# Save
with open("pocket_with_finish.nc", "w") as f:
    f.write(gcode_with_finish)

print(f"WITH FINISH: {len(gcode_with_finish.splitlines())} lines")
```

---

### Step 2: Generate Without Finish (Comparison)

```python
# Config with finish DISABLED
config_no_finish = Config(pocket_finish_perimeter=False)

gcode_no_finish = plan_gcode(config_no_finish)

with open("pocket_no_finish.nc", "w") as f:
    f.write(gcode_no_finish)

print(f"NO FINISH:   {len(gcode_no_finish.splitlines())} lines")
```

---

### Step 3: Compare Strategies

**Inspect G-code comments:**

```bash
# With finish enabled
grep "BEGIN" pocket_with_finish.nc
```

Expected output:
```
; BEGIN rough pocket cleanup=0.250mm sd=3.000 so=2.400
; BEGIN finish profile pass
```

```bash
# Without finish
grep "BEGIN" pocket_no_finish.nc
```

Expected output:
```
; BEGIN pocket (no finish) sd=3.000 so=2.400
```

**Key difference:**
- **With finish:** Rough pocket is *smaller* (leaves cleanup_offset margin), then finish pass cleans perimeter
- **Without finish:** Full raster pocket to final boundary (no cleanup pass)

---

### Step 4: Verify RemovalIntent IR

```python
# Check what the IR contains
for intent in intents:
    print(f"Region: {intent.region_id}")
    print(f"  Bounds: {intent.bounds}")
    print(f"  Z range: {intent.z_top} to {intent.z_bottom}")
    print(f"  Allowance: {intent.allowance}")
```

Expected:
```
Region: panel
  Bounds: Bounds2D(x_min=50.0, x_max=150.0, y_min=35.0, y_max=115.0)
  Z range: 0.0 to -6.0
  Allowance: inside
```

**Important:** The finish pass decision is made at the **planner level**, not in the IR. The IR just says "remove this volume inside the boundary."

---

## Configuration Options

### Option 1: Change Cleanup Offset

Default cleanup offset is `0.25mm`. You can adjust:

```python
config = Config(
    pocket_finish_perimeter=True,
    cleanup_offset_mm=0.5  # Leave 0.5mm for finish pass instead of 0.25mm
)
```

**Effect:**
- Rough pocket shrinks more
- Finish pass removes more material
- Better for rougher raster or larger scallops

---

### Option 2: Disable Finish Globally

```python
config = Config(pocket_finish_perimeter=False)
```

**When to use:**
- Interior pockets where wall finish doesn't matter
- Time-critical jobs
- Very small pockets where finish pass is impractical

---

### Option 3: Environment Variable Override

```bash
export CAM_POCKET_FINISH_PERIMETER=false
PYTHONPATH=. python3 generate_pocket.py
```

Config will read from environment:
```python
config = Config.from_env()  # Picks up CAM_POCKET_FINISH_PERIMETER
```

---

## Understanding the Strategy

### With Finish Enabled (Default)

```
Step 1: Rough pocket (shrunken)
┌─────────────────┐
│ ░░░░░░░░░░░░░░░ │  ░ = Rough raster (leaves margin)
│ ░░░░░░░░░░░░░░░ │
│ ░░░░░░░░░░░░░░░ │  Margin = tool_radius + cleanup_offset
└─────────────────┘

Step 2: Finish profile (perimeter)
┌─────────────────┐
│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│  ▓ = Finish pass removes margin
│▓               ▓│     (clean walls, no scallops)
│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
└─────────────────┘
```

**Math:**
- Pocket boundary: 100mm × 80mm
- Tool diameter: 6mm (radius = 3mm)
- Cleanup offset: 0.25mm
- Rough pocket size: (100 - 2×(3+0.25))mm × (80 - 2×(3+0.25))mm = 93.5mm × 73.5mm
- Finish boundary: (100 - 6)mm × (80 - 6)mm = 94mm × 74mm (tool center path)

---

### Without Finish

```
Single step: Full raster
┌─────────────────┐
│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│  ▒ = Raster to boundary
│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│     (scallops on perp walls)
│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
└─────────────────┘
```

**Result:** Faster (fewer moves), but scalloped walls on sides perpendicular to raster direction.

---

## Common Variations

### Variation 1: Shaker Door Panel (Typical Use Case)

```pml
sheet 400mm 600mm 19mm

rect door profile through outside
    inset 50mm
        rect panel pocket 6mm  # Finish cleanup enabled by default
```

**Why finish matters here:** Panel recess is visible, needs clean walls.

---

### Variation 2: Deep Pocket (Multiple Depths)

```pml
rect deep_pocket pocket 12mm
    size 100mm 100mm
    center 100mm 100mm
```

**Behavior with finish enabled:**
- Rough raster at each depth level (e.g., 3mm stepdown = 4 levels)
- Finish profile **only at final depth** (cleanup pass happens once at bottom)

**Note:** Current implementation does cleanup at final depth only. Intermediate depth cleanup could be a future enhancement.

---

### Variation 3: Circular Pocket (Different Strategy)

```pml
circle round_pocket pocket 10mm
    center 100mm 100mm
    diameter 80mm
```

**Note:** Circular pockets use concentric strategy, not raster. Finish perimeter flag doesn't apply (no scalloping issue with concentric circles).

---

## Troubleshooting

### Problem: Finish pass removes too much material

**Cause:** `cleanup_offset_mm` is too large.

**Solution:** Reduce cleanup offset:
```python
config = Config(cleanup_offset_mm=0.1)  # Instead of default 0.25mm
```

---

### Problem: Scallops still visible with finish enabled

**Possible causes:**
1. **Stepover too large:** Reduce stepover percentage in config
2. **Tool wear:** Dull bit creates larger scallops
3. **Feed rate too high:** Reduces cut quality

**Check stepover:**
```python
config = Config(
    pocket_finish_perimeter=True,
    # Adjust stepover (default is 40% of tool diameter)
)
```

**Note:** Stepover isn't currently exposed in Config, it's calculated in strategy. Future enhancement.

---

### Problem: Pocket too small for finish pass

**Symptom:** G-code has only rough pocket, no finish pass.

**Cause:** After shrinking by `tool_radius + cleanup_offset`, pocket is too small (≤ 0 area).

**Solution:** Increase pocket size or reduce tool diameter.

**Example:**
- Pocket: 10mm × 10mm
- Tool: 6mm diameter (3mm radius)
- Cleanup: 0.25mm
- Shrunk size: 10 - 2×(3+0.25) = 3.5mm × 3.5mm ✓ (still valid)
- Pocket: 6mm × 6mm → shrunk: 6 - 6.5 = -0.5mm ✗ (too small, finish skipped)

---

## Performance Comparison

Tested with 100mm × 100mm pocket, 6mm tool, 10mm depth:

| Configuration | Total Moves | Time Estimate | Wall Quality |
|---------------|-------------|---------------|--------------|
| No finish     | 844         | ~8 min        | Scalloped    |
| With finish (default) | 820 | ~9 min   | Clean        |

**Key insight:** Finish pass doesn't always add moves! The rough pocket is smaller, which can save moves. Time difference comes from the finish pass itself.

---

## Next Steps

- **Recipe 03:** Use the Shaker template (includes pocket with finish)
- **Recipe 06:** Multiple features at different depths
- **Recipe 09:** Fine-tune config for your material and machine

---

## Full Example Script

```python
#!/usr/bin/env python3
"""Pocket with and without finish cleanup - side-by-side comparison"""

from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

# Design
ast = LayoutAST(
    sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
            placement=Placement(center_xy_mm=(100, 75)),
            feature=Feature(type="pocket", depth_mm=6.0),
            shape_id="panel"
        ),
    )
)

intents = ast_to_removal_intents(ast)

stock = Stock(width=200, height=150, thickness=19)
material = Material(name="MDF")
machine = Machine()
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

# Generate both versions
config_finish = Config(pocket_finish_perimeter=True)
config_no_finish = Config(pocket_finish_perimeter=False)

tool_db = [
    {"name": "6mm_flat", "diameter": 6.0, "kind": "flat", "rpm": 18000, "feed_xy": 2000, "feed_z": 300}
]

def plan_gcode(cfg: Config) -> str:
    passes, _summary = plan_passes(
        hints,
        config=cfg,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
    )
    return "\n".join(write_gcode(p["moves"], safe_z=cfg.safe_z_mm) for p in passes if p.get("moves"))

gcode_with = plan_gcode(config_finish)
gcode_without = plan_gcode(config_no_finish)

# Save and report
with open("pocket_with_finish.nc", "w") as f:
    f.write(gcode_with)
with open("pocket_no_finish.nc", "w") as f:
    f.write(gcode_without)

print("COMPARISON:")
print(f"  With finish:    {len(gcode_with.splitlines()):4d} lines → pocket_with_finish.nc")
print(f"  Without finish: {len(gcode_without.splitlines()):4d} lines → pocket_no_finish.nc")
print(f"  Difference:     {abs(len(gcode_with.splitlines()) - len(gcode_without.splitlines())):4d} lines")
print()
print("Check G-code comments:")
print("  grep 'BEGIN' pocket_with_finish.nc")
print("  grep 'BEGIN' pocket_no_finish.nc")
```

Save as `pocket_comparison.py`, run:
```bash
PYTHONPATH=. python3 pocket_comparison.py
```
