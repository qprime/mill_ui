# Recipe 05: Validation Workflow (IR-Level)

**Goal:** Catch common mistakes (bad depths, tiny features, accidental collisions) by validating `RemovalIntent` before running the CAM planner.

**Difficulty:** Intermediate  
**Time:** 10–15 minutes  
**Prerequisites:** Recipe 01 (AST → IR basics)

---

## What This Recipe Covers

- Running built-in validators in `validation/removal_checks.py`
- Interpreting errors vs warnings vs suggestions
- A pragmatic way to validate multi-operation parts

---

## Important Note About Overlap Checking

`check_overlap()` is conservative: it flags any 3D overlap between intents.

That means **common, valid designs** like “pocket inside an outer profile” will overlap in XY and in Z, and will be flagged.

Use overlap checking primarily to catch:
- Two pockets accidentally placed on top of each other
- Duplicate features (same region cut twice)
- Conflicting operations at the same depth band

---

## Example Part to Validate

We’ll validate a small layout with:
- One pocket (6mm deep)
- One through profile (outer cut)
- Two holes

Create `validate_demo.pml` (flat PML, explicit placement):

```pml
sheet 200mm 150mm 19mm

rect outer at 100mm,75mm size 180mm,130mm profile through outside
rect recess at 100mm,75mm size 140mm,90mm pocket 6mm
circle mount:1 at 40mm,40mm diameter 6mm hole 10mm
circle mount:2 at 160mm,40mm diameter 6mm hole 10mm
```

Convert to JSON (optional):
```bash
PYTHONPATH=. python3 -m cli.convert_layout --from pml --to json validate_demo.pml validate_demo.json
```

---

## Validation Script

Create `validate_demo.py`:

```python
from layout_ast.parsers import parse_layout_json
from adapters.ast_to_removal import ast_to_removal_intents
from validation.removal_checks import check_depth_feasibility, check_toolability, check_overlap

ast = parse_layout_json("validate_demo.json")
intents = ast_to_removal_intents(ast)

print(f"Intents: {len(intents)}")
for it in intents:
    print(f"- {it.region_id}: depth={it.depth_mm():.2f}mm bounds={it.bounds}")

print("\nDepth feasibility:")
for it in intents:
    r = check_depth_feasibility(it, sheet_thickness_mm=ast.sheet.thickness_mm)
    if r.has_issues():
        print(r.summary())

print("\nToolability (basic):")
for it in intents:
    r = check_toolability(it)
    if r.has_issues():
        print(r.summary())

print("\nOverlap (conservative):")
overlaps = check_overlap(intents)
if overlaps.has_issues():
    print(overlaps.summary())
else:
    print("✓ No overlaps detected")
```

Run:
```bash
PYTHONPATH=. python3 validate_demo.py
```

---

## Practical Pattern: “Overlap Check Within a Bucket”

If you want overlap checking to be useful on multi-operation parts, a good heuristic is:
- Only compare intents of the same semantic type (e.g., pocket vs pocket)

The `RemovalIntent` includes `metadata["hint_type"]` when produced via the AST adapter.

Example filter:

```python
pockets = [it for it in intents if it.metadata.get("hint_type") == "pocket"]
print(check_overlap(pockets).summary())
```

---

## Next Steps

- Recipe 06: multi-depth parts (profiles + pockets + holes)
- Recipe 09: config tuning (safe Z, cleanup pass toggles)

