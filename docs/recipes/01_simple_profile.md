# Recipe 01: Simple Profile Cut

**Goal:** Cut a rectangular part outline from sheet stock.

**Difficulty:** Beginner
**Time:** 5 minutes
**Prerequisites:** None

---

## What You'll Learn

- Basic PML syntax
- Profile feature (outside cutting)
- Running the pipeline manually
- Verifying G-code output

---

## The Design

We'll cut a 200mm × 150mm rectangle from a 450mm × 650mm × 19mm sheet.

### Option 1: Compositional PML

```pml
sheet 450mm 650mm 19mm

rect part profile through outside
    center 225mm 325mm
    size 200mm 150mm
```

Save as `simple_profile.pml`

### Option 2: Flat PML (Absolute Positioning)

```pml
sheet 450mm 650mm 19mm

rect part at 225mm,325mm size 200mm,150mm profile through outside
```

Save as `simple_profile_flat.pml`

### Option 3: Python (Programmatic)

```python
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="part"
        ),
    )
)
```

---

## Step-by-Step Process

### Step 1: Parse to LayoutAST

**Using Compositional PML:**
```bash
PYTHONPATH=. python3 -m cli.parse_compositional_pml simple_profile.pml --resolve --format json > layout.json
```

**Using Flat PML:**
```bash
PYTHONPATH=. python3 -m cli.convert_layout --from pml --to json simple_profile_flat.pml layout.json
```

**Verify the LayoutAST:**
```bash
cat layout.json
```

Expected output structure:
```json
{
  "sheet": {"width_mm": 450, "height_mm": 650, "thickness_mm": 19},
  "items": [
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": {"w_mm": 200, "h_mm": 150},
      "placement": {"center_xy_mm": [225, 325]},
      "feature": {"type": "profile", "side": "outside", "depth": "through"},
      "shape_id": "part"
    }
  ]
}
```

---

### Step 2: Convert to RemovalIntent IR

```python
from layout_ast.parsers import parse_layout_json
from adapters.ast_to_removal import ast_to_removal_intents

# Load LayoutAST
with open("layout.json") as f:
    ast = parse_layout_json(f.read())

# Convert to IR
intents = ast_to_removal_intents(ast)

# Inspect
for intent in intents:
    print(f"Region: {intent.region_id}")
    print(f"  Bounds: {intent.bounds}")
    print(f"  Depth: {intent.z_top}mm to {intent.z_bottom}mm")
    print(f"  Allowance: {intent.allowance}")
```

Expected output:
```
Region: part
  Bounds: Bounds2D(x_min=125.0, x_max=325.0, y_min=250.0, y_max=400.0)
  Depth: 0.0mm to -19.0mm
  Allowance: outside
```

**Key Insight:** The IR captures *what* to remove (200×150mm region, full depth, outside the boundary), not *how* (tool selection, stepdown, etc.).

---

### Step 3: Validate Design

```python
from validation.removal_checks import check_overlap, check_depth_feasibility, check_toolability

# Check for overlaps
overlap_result = check_overlap(intents)
if overlap_result.has_issues():
    print("OVERLAP ISSUES:")
    print(overlap_result.summary())

# Check depth feasibility
for intent in intents:
    depth_result = check_depth_feasibility(intent, sheet_thickness_mm=19.0)
    if depth_result.has_issues():
        print(f"DEPTH ISSUE in {intent.region_id}:")
        print(depth_result.summary())

# Check toolability (minimum feature sizes)
for intent in intents:
    tool_result = check_toolability(intent, min_feature_mm=3.0)
    if tool_result.has_issues():
        print(f"TOOLABILITY ISSUE in {intent.region_id}:")
        print(tool_result.summary())
```

Expected: All checks pass (no output if clean).

---

### Step 4: Generate G-code

```python
	from adapters.removal_to_planner import removal_intents_to_v1_hints
	from cam.config import Config
	from cam.planner.passes import plan_passes
	from cam.post.gcode import write_gcode
	from cam.model.stock import Stock
	from cam.model.material import Material
	from cam.model.machine import Machine

	# Convert IR to planner hints
	hints = removal_intents_to_v1_hints(
	    intents,
	    kerf_width_mm=3.175,  # 1/8" bit typical
	    min_channel_width_mm=6.0
	)

	tool_db = [
	    {"name": "6mm_endmill", "diameter": 6.0, "kind": "flat", "rpm": 18000, "feed_xy": 2000, "feed_z": 300}
	]
	config = Config(safe_z_mm=5.0)
	material = Material(name="MDF")
	machine = Machine()
	stock = Stock(width=450, height=650, thickness=19)

	passes, _summary = plan_passes(
	    hints,
	    config=config,
	    tool_db=tool_db,
	    material=material,
	    machine=machine,
	    stock=stock,
	)

	gcode = "\n".join(
	    write_gcode(p["moves"], safe_z=config.safe_z_mm)
	    for p in passes
	    if p.get("moves")
	)

	# Save
	with open("simple_profile.nc", "w") as f:
	    f.write(gcode)

print(f"Generated {len(gcode.splitlines())} lines of G-code")
```

---

### Step 5: Verify G-code

**Check for key commands:**
```bash
grep -E "^G0|^G1|^M3|^M5" simple_profile.nc | head -20
```

**Expected patterns:**
- `M3 S18000` - Spindle on at 18000 RPM
- `G0 Z5.000` - Rapid to safe height
- `G1 X... Y... Z... F2000` - Feed moves at 2000 mm/min
- Multiple depth passes (stepdown typically 3mm for MDF)
- `M5` - Spindle off at end

**Visualize toolpath (if CAMotics installed):**
```bash
camotics simple_profile.nc
```

---

## Common Variations

### Variation 1: Cut Inside Instead of Outside

Change PML:
```pml
rect part profile through inside
```

This cuts *inside* the 200×150mm boundary instead of outside. Useful for creating a hole/window.

**IR difference:**
- `allowance: inside` instead of `outside`
- Profile will be offset inward by tool radius

---

### Variation 2: Partial Depth Cut

Change depth from `through` to specific depth:

```pml
rect part profile 6mm outside
```

**IR difference:**
- `z_bottom: -6.0` instead of `-19.0`

---

### Variation 3: Cut On-Line (No Offset)

```pml
rect part profile through on
```

**IR difference:**
- `allowance: on` - tool center follows the exact boundary
- Useful for grooves or when compensating in design

---

### Variation 4: Rounded Corners

Use `RoundedRect` instead:

```python
Item(
    type="RoundedRect",
    geometry=Geometry(data={"w_mm": 200, "h_mm": 150, "r_mm": 10}),
    # ... rest same
)
```

This creates 10mm radius corners instead of sharp 90° corners.

---

## Troubleshooting

### Problem: "Native backend not available"

**Solution:** Build the native CAM backend (see README "Building the Native CAM Backend" section).

**Quick check:**
```bash
PYTHONPATH=. python3 -c "from cam.native import core; print('Native backend OK')"
```

---

### Problem: G-code has no moves

**Cause:** Feature might be too small for the tool diameter.

**Check:**
- Tool diameter: 6mm
- Feature size must be > tool diameter for pockets
- Profile outside: part must be larger than tool diameter

**Fix:** Increase part size or reduce tool diameter.

---

### Problem: Validation fails with overlap error

**Cause:** Multiple shapes sharing the same space.

**Check IR bounds:**
```python
for intent in intents:
    print(f"{intent.region_id}: {intent.bounds}")
```

Look for overlapping x/y ranges.

---

## Next Steps

- **Recipe 02:** Add a pocket feature with finish cleanup pass
- **Recipe 03:** Use the Shaker template for parametric design
- **Recipe 05:** See validation workflow for catching errors early

---

## Full Example Script

```python
#!/usr/bin/env python3
"""Complete pipeline: PML → LayoutAST → RemovalIntent → G-code"""

	from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
	from adapters.ast_to_removal import ast_to_removal_intents
	from validation.removal_checks import check_overlap, check_depth_feasibility
	from adapters.removal_to_planner import removal_intents_to_v1_hints
	from cam.config import Config
	from cam.planner.passes import plan_passes
	from cam.post.gcode import write_gcode
	from cam.model.stock import Stock
	from cam.model.material import Material
	from cam.model.machine import Machine

# 1. Create LayoutAST
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="part"
        ),
    )
)

# 2. Convert to RemovalIntent IR
intents = ast_to_removal_intents(ast)

# 3. Validate
overlap = check_overlap(intents)
assert not overlap.has_issues(), overlap.summary()

for intent in intents:
    depth_check = check_depth_feasibility(intent, sheet_thickness_mm=19.0)
    assert not depth_check.has_issues(), depth_check.summary()

	print("✓ Validation passed")

	# 4. Generate G-code
	hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
	tool_db = [
	    {"name": "6mm_endmill", "diameter": 6.0, "kind": "flat", "rpm": 18000, "feed_xy": 2000, "feed_z": 300}
	]
	config = Config(safe_z_mm=5.0)
	material = Material(name="MDF")
	machine = Machine()
	stock = Stock(width=450, height=650, thickness=19)

	passes, _summary = plan_passes(
	    hints,
	    config=config,
	    tool_db=tool_db,
	    material=material,
	    machine=machine,
	    stock=stock,
	)
	gcode = "\n".join(
	    write_gcode(p["moves"], safe_z=config.safe_z_mm)
	    for p in passes
	    if p.get("moves")
	)

# 5. Save
with open("simple_profile.nc", "w") as f:
    f.write(gcode)

print(f"✓ Generated {len(gcode.splitlines())} lines of G-code → simple_profile.nc")
```

Save as `simple_profile_complete.py`, run with:
```bash
PYTHONPATH=. python3 simple_profile_complete.py
```
