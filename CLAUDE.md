# CLAUDE.md - AI Development Guide

**Practical guide for AI agents working with mill_ui. For architecture details, see [README.md](README.md).**

## Quick Orientation

You're working on a CAM system that generates G-code for CNC routers. The key innovation is **RemovalIntent IR** - a semantic layer that separates *what* to machine from *how* to machine it.

**Read [README.md](README.md) first** for architecture, pipeline explanation, and design rationale.

This guide covers:
- Mental models for understanding the codebase
- Common tasks with code examples
- Pitfalls to avoid
- Development workflows

## Mental Model: Compiler Analogy

Think of mill_ui as a **compiler with semantic IR**:

```
Source Code    → Syntax Tree → Intermediate Rep → Optimization → Machine Code
(PML/JSON)       (LayoutAST)   (RemovalIntent)    (Planner)      (G-code)
```

**Key insight:** Just as a compiler validates and optimizes at IR level before code generation, mill_ui validates machining operations at RemovalIntent level before toolpath planning.

This enables:
- **Fast validation**: Check semantics without expensive geometric computation
- **Multiple backends**: Different planners can target same IR
- **Testability**: Verify correctness at IR boundary

## Reading Order for New Context

When loading this codebase into a fresh chat:

1. **[README.md](README.md)** - Architecture, pipeline, why RemovalIntent IR matters
2. **This file (CLAUDE.md)** - Practical development guide
3. **[templates/shaker.py](templates/shaker.py)** - Concrete template example
4. **[tests/run_edge_tests.py](tests/run_edge_tests.py)** - Test patterns

For deep dives:
- **[layout_ast/layout.py](layout_ast/layout.py)** - AST dataclass definitions
- **[ir/removal_intent.py](ir/removal_intent.py)** - RemovalIntent IR spec
- **[adapters/ast_to_removal.py](adapters/ast_to_removal.py)** - AST → IR conversion

## Common Tasks

### Task 1: Generate a Layout Programmatically

**Use case:** AI generates a panel layout from user requirements.

```python
from layout_ast.layout import (
    LayoutAST, Sheet, Item, Geometry, Placement, Feature
)

# Build AST directly (skips parsing)
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
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

# Convert to RemovalIntent (semantic validation happens here)
from adapters.ast_to_removal import ast_to_removal_intents
intents = ast_to_removal_intents(ast)
```

**Why this matters:** Building AST directly gives you maximum control. JSON serialization is just `LayoutAST.to_json()` / `LayoutAST.from_json()`.

### Task 2: Parse Human-Authored PML

**Use case:** User provides PML text, you need to process it.

```python
from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout

pml_source = """
sheet 450mm 650mm 19mm

# Compositional PML: regions are implicit (no explicit widths/heights on rect).
# Layout managers (frame/inset/grid/split) subdivide the current region.
component Door
    rect door
        frame 50mm
            rect panel pocket 6mm

# Sheet-level placement is currently grid-based and takes `use <Component>` children.
place grid 1 1 gap 0mm
    use Door
"""

comp_ast = parse_compositional_pml(pml_source)
ast = resolve_layout(comp_ast)  # CompositionalLayoutAST -> flat LayoutAST
```

**Why this matters:** PML is concise for humans. You might need to parse it, modify the AST, and re-emit.

### Task 3: Use a Template

**Use case:** Generate a standard component (Shaker door, etc.).

```python
from templates import Shaker

ast = Shaker.expand_to_ast(
    params={
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    },
    sheet_thickness_mm=19.0
)

# Produces LayoutAST ready for conversion to RemovalIntent
```

**Why this matters:** Templates are parametric AST generators. Building new templates is a common extension point.

### Task 4: Validate Before Planning

**Use case:** Check if a layout is physically valid before expensive CAM execution.

```python
from adapters.ast_to_removal import ast_to_removal_intents
from validation.removal_checks import (
    check_overlap,
    check_depth_feasibility,
    check_toolability,
)

intents = ast_to_removal_intents(ast)

# Validate semantics at IR level (no planner required)
overlap = check_overlap(intents)
depth_results = [check_depth_feasibility(i, sheet_thickness_mm=19.0) for i in intents]
toolability_results = [check_toolability(i) for i in intents]

if overlap.has_issues() or any(r.has_issues() for r in depth_results + toolability_results):
    print(overlap.summary())
    for r in depth_results + toolability_results:
        if r.has_issues():
            print(r.summary())
```

**Why this matters:** Catching errors at IR level is fast. Don't wait for CAM execution to find invalid depths or overlaps.

## Extension Patterns

### Pattern 1: Add a New Shape

**When:** You need to support a geometric primitive not currently in the system (Ellipse, Polygon, etc.).

**Steps:**
1. AST already supports arbitrary shapes via `Item.type` field (no code change needed)
2. Add bounds calculation in `adapters/hints_to_removal.py` (geometry → bounds)
3. Add tests

**Example:** Adding Ellipse

```python
# In adapters/hints_to_removal.py, extend BOTH conversion paths:
# - `_geometry_to_bounds(shape, geometry, center_xy_mm)` (v1 hint dict path)
# - `_item_geometry_to_bounds(item_type, geometry_data, cx, cy)` (Item path)
```

**Test:**
```python
# In tests/test_removal_intent_model.py (or any existing test module under tests/)
def test_ellipse_bounds():
    item = Item(
        type="Ellipse",
        geometry=Geometry(data={"rx_mm": 50, "ry_mm": 30}),
        placement=Placement(center_xy_mm=(200, 150)),
        feature=Feature(type="profile", side="outside", depth="through")
    )
    intent = item_to_removal_intent(item, 19.0)
    assert intent.bounds == Bounds2D(x_min=150, x_max=250, y_min=120, y_max=180)
```

### Pattern 2: Create a Template

**When:** You need a reusable parametric component (cabinet door, mounting plate, etc.).

**Steps:**
1. Create class in `templates/`
2. Implement `expand_to_ast(params, sheet_thickness_mm) -> LayoutAST`
3. Register in `templates/__init__.py`

**Example:** Simple mounting plate template

```python
# templates/mounting_plate.py
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

class MountingPlate:
    @staticmethod
    def expand_to_ast(params: dict, sheet_thickness_mm: float) -> LayoutAST:
        width = params["width"]
        height = params["height"]
        hole_diameter = params["hole_diameter"]
        hole_offset = params.get("hole_offset", 10.0)

        # Outer profile
        items = [
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": width, "h_mm": height}),
                placement=Placement(center_xy_mm=(width/2, height/2)),
                feature=Feature(type="profile", side="outside", depth="through"),
                shape_id="plate_outer"
            ),
        ]

        # Corner holes
        for i, (x, y) in enumerate([
            (hole_offset, hole_offset),
            (width - hole_offset, hole_offset),
            (hole_offset, height - hole_offset),
            (width - hole_offset, height - hole_offset),
        ]):
            items.append(Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": hole_diameter}),
                placement=Placement(center_xy_mm=(x, y)),
                feature=Feature(type="hole", depth="through"),
                shape_id=f"hole_{i}"
            ))

        return LayoutAST(
            sheet=Sheet(width_mm=width + 50, height_mm=height + 50, thickness_mm=sheet_thickness_mm),
            items=tuple(items)
        )
```

**Register:**
```python
# templates/__init__.py
from .shaker import Shaker
from .mounting_plate import MountingPlate

__all__ = ["Shaker", "MountingPlate"]
```

## Critical Invariants (Don't Break These)

### 1. Always Go Through RemovalIntent IR

❌ **Wrong:**
```python
# Bypassing IR layer
hints = convert_ast_to_hints_directly(ast)  # DON'T DO THIS
```

✅ **Correct:**
```python
# Always: AST → RemovalIntent → (adapter) → hints
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents)
```

**Why:** RemovalIntent is the semantic layer. Skipping it means no validation, no extensibility.

### 2. Don't Mutate Dataclasses

❌ **Wrong:**
```python
item.geometry.data["w_mm"] = 100  # Avoid mutating nested dicts (they remain mutable even in frozen dataclasses)
```

✅ **Correct:**
```python
from dataclasses import replace
new_item = replace(item, geometry=Geometry(data={**item.geometry.data, "w_mm": 100}))
```

**Why:** Frozen dataclasses prevent accidental mutation. Use `replace()` for modifications.

### 3. Dimensions Are Always Millimeters

All dimensions in the system are millimeters. No conversions needed, no mixed units.

```python
sheet = Sheet(width_mm=450, height_mm=650, thickness_mm=19)  # All mm
```

**Why:** Consistency prevents unit conversion bugs. MM is standard for CNC.

### 4. Test at IR Level, Not CAM Level

❌ **Slow feedback:**
```python
# Testing by running full CAM pipeline
gcode = generate_full_pipeline(ast)  # Requires native backend, slow
assert "G1 X100" in gcode
```

✅ **Fast feedback:**
```python
# Testing at IR level
intents = ast_to_removal_intents(ast)
assert intents[0].bounds == Bounds2D(x_min=50, x_max=150, ...)
```

**Why:** IR tests are fast, portable, focused. Most development happens here.

## Common Pitfalls

### Pitfall 1: Assuming Formatting Preservation

The system guarantees **semantic equivalence**, not surface syntax preservation.

❌ **Wrong assumption:**
```python
pml_output = format_pml(parse_pml(pml_input))
assert pml_output == pml_input  # MAY FAIL - formatting can differ
```

✅ **Correct:**
```python
ast1 = parse_pml(pml_input)
ast2 = parse_pml(format_pml(ast1))
assert ast1 == ast2  # Semantic equivalence guaranteed
```

### Pitfall 2: Creating Unnecessary Files

Prefer editing existing files over creating new ones.

❌ **File proliferation:**
```python
create_file("tests/test_my_new_shape.py", ...)  # New file for small feature
```

✅ **Add to existing:**
```python
# Add test case to an existing module (e.g., tests/test_removal_intent_model.py)
def test_my_new_shape():
    ...
```

**Why:** Keeps codebase organized. Related code stays together.

### Pitfall 3: Mixing Concerns Across Layers

Keep pipeline layers separate. Don't generate G-code in AST building, don't parse PML in the planner.

❌ **Layer violation:**
```python
def build_layout(...):
    ast = LayoutAST(...)
    gcode = generate_gcode(ast)  # WRONG LAYER!
    return ast
```

✅ **Clean separation:**
```python
ast = build_layout(...)
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents)
gcode = plan_and_generate(hints)
```

## Development Workflow

### Standard Development Loop

1. **Write test at IR level** (fast, focused)
2. **Implement feature** (AST modification, bounds calculation, etc.)
3. **Run IR tests** (verify semantics)
4. **Optional: Run CAM tests** (end-to-end validation if needed)

Example:
```bash
# Write test
edit tests/test_removal_intent_model.py

# Run IR tests (fast, no native backend needed)
PYTHONPATH=/path/to/cliff_ai PYTHONPATH=. python3 -m tests.run_edge_tests

# Run CAM tests if needed (requires native backend)
PYTHONPATH=/path/to/cliff_ai PYTHONPATH=. python3 -m tests.run_gcode_equivalence_tests
```

### When to Run Full Tests

- **IR tests (always)**: Fast validation of semantics
- **PML tests (if parsing changes)**: Verify parser correctness
- **G-code tests (if CAM changes)**: End-to-end validation

**Focus on IR tests for development velocity.**

## Architecture Deep Dives (Reference README)

For detailed explanations of:
- **Why RemovalIntent IR?** → See README "Why This Architecture"
- **Design tradeoffs** → See README "Design Tradeoffs"
- **Extension points** → See README "Extension Points"
- **Directory structure** → See README "Directory Structure"

This guide focuses on **how to work with** the architecture, not **why it exists** (that's in README).

## Historical Context

**v1 → v2 migration** (current codebase):
- Introduced RemovalIntent IR as semantic layer
- Unified PML and JSON inputs through LayoutAST
- Retained proven CAM planner backend
- Cleaned up backward compatibility code

**Git tags for reference (run `git tag --list`):**
- `mill_ui_v1`, `mill_ui_v1_frozen` - v1 snapshots
- `S8_VALIDATION` … `S14_BASIC_SHAPES` - staged milestones

**Why this matters:** If you see references to "v1 planner" or "v2 architecture", that's historical context. Current system is just "mill_ui" now.

## When Stuck

**Architecture questions:** Check [README.md](README.md) for design rationale
**Code examples:** Look at [templates/shaker.py](templates/shaker.py) and test files
**IR semantics:** Read [ir/removal_intent.py](ir/removal_intent.py) docstrings
**Test patterns:** Study [tests/run_edge_tests.py](tests/run_edge_tests.py)

**Ask the user if:**
- Architectural change needed (new feature types, pipeline modifications)
- Multiple valid approaches exist (choose based on user priorities)
- Ambiguous requirements (clarify before implementing)

---

**Last Updated:** 2025-12-17
**Complementary Doc:** [README.md](README.md) for architecture
**Status:** Production (current architecture)
