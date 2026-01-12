# Recipe: Profile Cuts with Holding Tabs

**Status:** Production
**Difficulty:** Beginner
**Related:** [Shaker Door Template](../03_shaker_door_template)

## Overview

This recipe demonstrates how to add holding tabs to profile cuts. Tabs are small bridges of uncut material that keep parts secured to the stock sheet during cutting, preventing movement and allowing safe completion of through-cuts.

## Use Case

When cutting out a part with a profile cut, the part can shift or fall once the cut completes, causing:
- Damage to the part
- Safety hazards
- Poor cut quality on the final segments

Tabs solve this by leaving small uncut sections that hold the part in place. After cutting, tabs can be broken off and sanded smooth.

## Basic Syntax

```pml
rect <id> at <x>mm,<y>mm size <w>mm,<h>mm profile through outside tabs <count> height <height>mm [width <width>mm]
```

**Required:**
- `tabs <count>`: Number of tabs (positive integer)
- `height <height>mm`: Tab height in millimeters (how much material to leave uncut)

**Optional:**
- `width <width>mm`: Tab width along the perimeter (defaults to 2× tool diameter, minimum 6mm)

## Examples

### Simple Cutout

```pml
sheet 600mm 400mm 19mm

rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm width 12mm
```

This creates a rectangular cutout with 4 tabs, each 3mm high and 12mm wide.

### Default Width

```pml
sheet 600mm 400mm 19mm

rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm
```

Omitting width uses the planner's default: `max(tool_diameter × 2, 6mm)`

### Multiple Parts with Different Tab Counts

```pml
sheet 800mm 600mm 19mm

# Small part: 3 tabs
rect small at 200mm,150mm size 150mm,100mm profile through outside tabs 3 height 2mm width 8mm

# Medium part: 4 tabs
rect medium at 200mm,400mm size 250mm,150mm profile through outside tabs 4 height 3mm width 12mm

# Large part: 6 tabs
rect large at 550mm,300mm size 400mm,250mm profile through outside tabs 6 height 4mm width 15mm
```

## How It Works

### Pipeline Flow

```
PML with tabs → LayoutAST (Feature.tab_*) → RemovalIntent (Constraints.tabs) → Planner → G-code
```

1. **Parser** ([pml/parser.py:275-319](../../../pml/parser.py#L275-L319)): Parses `tabs <count> height <height>mm [width <width>mm]` syntax into `Feature` dataclass fields
2. **AST** ([layout_ast/layout.py:43-46](../../../layout_ast/layout.py#L43-L46)): Stores tab parameters in `Feature.tab_count`, `tab_height_mm`, `tab_width_mm`
3. **Adapter** ([adapters/ast_to_removal.py:111-117](../../../adapters/ast_to_removal.py#L111-L117)): Converts to `TabConstraint` in `RemovalIntent.constraints.tabs`
4. **Planner** ([cam/path/strategies.py:117-235](../../../cam/path/strategies.py#L117-L235)): Generates toolpath with Z lifts at tab positions

### Tab Distribution

Tabs are evenly distributed around the perimeter:
- **4 tabs** on a rectangle: one per side (centered)
- **6 tabs** on a rectangle: typically 2 on long sides, 1 on short sides
- The planner calculates optimal spacing based on perimeter length

### Tab Geometry

```
Material surface (Z=0)
      |
      |  <-- Tab height (e.g., 3mm)
      |      Uncut material
─────────────────────────  <-- Tab bottom (Z = -depth + height)
      |
      | <-- Continue cutting below tabs
      ▼
Material bottom (Z = -19mm for through-cut)
```

During cutting:
- Tool plunges to bottom depth as normal
- At tab positions, tool lifts to `z_bottom + tab_height_mm`
- Tool traverses across tab width at lifted height
- Tool plunges back to full depth after tab

## Configuration Guidelines

### Tab Count

| Part Size | Recommended Tabs | Reason |
|-----------|------------------|--------|
| < 200mm | 3 tabs | Minimal holding for small parts |
| 200-400mm | 4 tabs | Standard holding |
| > 400mm | 6+ tabs | Secure holding for large parts |

### Tab Height

| Material Thickness | Recommended Height | Notes |
|--------------------|-------------------|-------|
| 12-19mm (1/2"-3/4") | 2-4mm | Standard: 3mm |
| 6-12mm (1/4"-1/2") | 1-3mm | Thinner material needs shorter tabs |
| > 19mm (> 3/4") | 4-6mm | Proportional to thickness |

**Rule of thumb:** Tab height should be 15-25% of material thickness.

### Tab Width

| Width | Characteristics |
|-------|----------------|
| 6-10mm | Easy to break, quick cleanup, less support |
| 10-15mm | Standard trade-off between strength and cleanup |
| 15-20mm | Strong holding, more sanding required |

**Default (if omitted):** `max(tool_diameter × 2, 6mm)` ensures tabs are wide enough for tool to enter/exit cleanly.

## Limitations & Constraints

### What Works
✅ Profile cuts (inside, outside, on)
✅ Through-cuts and partial depth profiles
✅ Any shape (Rect, Circle, etc.)
✅ Optional width (uses planner default)

### What Doesn't Work
❌ Cannot combine with onion-skin roughing (`onion_skin_mm > 0`)
❌ Tabs on pockets (use profiles instead)
❌ Tabs on holes (not applicable)

### Validation

The system enforces these constraints:
- At planner level: `ValueError` if tabs + onion-skin both specified ([cam/planner/passes/profile.py:77](../../../cam/planner/passes/profile.py#L77))
- Tab count must be positive integer
- Tab height must be positive (parser validates)
- Tab width must be positive if specified (parser validates)

## Code Example

### Programmatic AST Construction

```python
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents

ast = LayoutAST(
    sheet=Sheet(width_mm=600, height_mm=400, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400, "h_mm": 250}),
            placement=Placement(center_xy_mm=(300, 200)),
            feature=Feature(
                type="profile",
                depth="through",
                side="outside",
                tab_count=4,
                tab_height_mm=3.0,
                tab_width_mm=12.0,
            ),
            shape_id="cutout"
        ),
    )
)

# Convert to RemovalIntent
intents = ast_to_removal_intents(ast)
intent = intents[0]

# Access tab information
if intent.constraints.tabs:
    print(f"Tabs: {intent.constraints.tabs.count}")
    print(f"Height: {intent.constraints.tabs.height_mm}mm")
    print(f"Width: {intent.constraints.tabs.width_mm}mm")
```

### JSON Format

```json
{
  "sheet": {"width_mm": 600, "height_mm": 400, "thickness_mm": 19},
  "items": [{
    "kind": "shape",
    "type": "Rect",
    "geometry": {"w_mm": 400, "h_mm": 250},
    "placement": {"center_xy_mm": [300, 200]},
    "feature": {
      "type": "profile",
      "depth": "through",
      "side": "outside",
      "tab_count": 4,
      "tab_height_mm": 3.0,
      "tab_width_mm": 12.0
    },
    "shape_id": "cutout"
  }]
}
```

## Testing

Run the tab test suite:

```bash
PYTHONPATH=. python3 -m tests.test_tabs
```

Test coverage includes:
- PML parsing with tabs (explicit width and default width)
- AST construction with tabs
- RemovalIntent conversion with tabs
- PML roundtrip (parse → format → parse)
- Full pipeline (PML → AST → RemovalIntent)

## Run the Example

```bash
PYTHONPATH=. python3 docs/recipes/15_profile_with_tabs/example.py
```

This demonstrates:
1. Simple cutout with tabs
2. Multiple parts with different tab configurations
3. Default width behavior
4. Inside profiles with tabs

## See Also

- [Corner Cleanup](../14_corner_cleanup_multi_tool) - Multi-tool workflow
- [Shaker Door Template](../03_shaker_door_template) - Template-based layouts
- [Shape Primitives](../../shape_primitives.md) - Available shape types

## Implementation Notes

### Architecture

Tabs follow the standard pipeline layers:

1. **AST Layer** ([layout_ast/layout.py:43-46](../../../layout_ast/layout.py#L43-L46))
   `Feature` dataclass stores tab parameters

2. **IR Layer** ([ir/removal_intent.py:44-48](../../../ir/removal_intent.py#L44-L48))
   `TabConstraint` in `RemovalIntent.constraints.tabs`

3. **Adapter Layer** ([adapters/ast_to_removal.py:111-117](../../../adapters/ast_to_removal.py#L111-L117))
   Converts Feature tabs → RemovalIntent tabs

4. **Planner Layer** ([cam/path/strategies.py:117-235](../../../cam/path/strategies.py#L117-L235))
   Generates G-code with Z lifts at tab positions

### Extension

The tab infrastructure is already complete. To extend:
- **New shapes**: Tabs automatically work with any shape (Circle, RoundedRect, etc.)
- **Advanced placement**: Modify planner's `_tab_windows()` function for custom spacing
- **Different strategies**: Tabs are a `Constraint`, so alternative planners can implement differently

## FAQs

**Q: Can I specify exact tab positions?**
A: No, tabs are automatically distributed evenly. This ensures balanced holding force.

**Q: What if I don't specify tab width?**
A: The planner defaults to `max(tool_diameter × 2, 6mm)`, ensuring tabs are wide enough for clean entry/exit.

**Q: Can I use tabs with onion-skin roughing?**
A: No, these strategies conflict. Tabs are for final passes; onion-skin is for roughing.

**Q: How do I remove tabs after cutting?**
A: Break tabs manually with pliers/chisel, then sand smooth. Tab height determines how easy they are to remove.

**Q: Can I use tabs on inside profiles?**
A: Yes, syntax supports it. Practically, inside profile tabs are unusual (tabs would be inside the pocket).
