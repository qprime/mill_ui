# CLAUDE.md - AI Development Guide

**Practical guide for AI agents working with mill_ui. For architecture details, see [README.md](README.md).**

## Project Directory

**User projects go here:** `/home/squinlan/cliff_ai/memories/cam_projects/mill_ui`

This is distinct from `docs/recipes/` which contains documented examples for the codebase. When the user asks to create a project or save work, use the project directory above.

## Quick Commands

Common CLI operations (run from mill_ui root with venv activated):

```bash
# Convert PML to JSON
python -m cli.convert_layout --from pml --to json input.pml output.json

# Export STL (3D model for visualization)
python -m cli.export_cad --input layout.pml --out output/ --kerf 6.35 --quality high

# Export SVG blueprint
python -m cli.export_blueprint --input layout.pml --out output/ --theme dark

# Validate CAM outputs
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary

# Run nesting from .nest file
python -m cli.nest job.nest -o output/ -v

# Nesting with automatic STL/SVG export
python -m cli.nest job.nest -o output/ --export-stl --export-svg
```

For compositional PML (frame/inset/grid syntax), add `--compositional` flag to export commands.

**Input formats:** `.pml`, `.json`, `.nest`

## Quick Orientation

You're working on a CAM system that generates G-code for CNC routers. The key innovation is **RemovalIntent IR** - a semantic layer that separates *what* to machine from *how* to machine it.

**Read [README.md](README.md) first** for architecture, pipeline explanation, and design rationale.

This guide covers:
- Mental models for understanding the codebase
- Common tasks with code examples
- Pitfalls to avoid
- Development workflows

## Code Style

**No inline comments.** Code should be self-documenting through clear naming and structure. Docstrings are acceptable for public APIs, but inline `# comments` should not be added to new code. If you add comments, they will need to be removed.

## Documentation Style

When writing or rewriting documentation files marked with `<!-- spec-style -->`, follow the rules in [docs/SPEC_STYLE.md](docs/SPEC_STYLE.md).

Use spec-style for:
- Contract documents (GROUND_TRUTH.md)
- API specifications
- Data model definitions

Do NOT use spec-style for:
- Tutorials and guides (README.md, recipes)
- Feature trackers (FEATURES.md)
- This file (CLAUDE.md)

## Token Efficiency

**Keep responses concise.** Let the user request more detail if needed.

When making changes:
- **Use system reminders**: File contents in `<system-reminder>` tags are already in context. Don't re-read them.
- **Execute directly**: On clear directives ("revert X", "change Y to Z"), edit directly rather than exploring first.
- **Minimize tool calls**: For simple changes: edit → test → done.
- **Skip redundant verification**: Don't `git diff` or re-read files to confirm what you just changed.

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

### Domain/Generator Layer

For complex designs, mill_ui provides a **math-based composition layer** above the AST:

```
Domain Composition → Generators → LayoutAST → RemovalIntent → G-code
(regions/algebra)    (patterns)   (items)     (semantics)     (output)
```

**Domains** are bounded 2D regions with algebraic operations:
- `inset(distance)` - Contract boundary inward
- `offset(distance)` - Expand boundary outward
- `subtract(other)` - Remove overlapping region
- `intersect(other)` - Keep only overlapping region

**Generators** are deterministic functions that produce LayoutAST Items from Domains:
- **Area generators**: Fill regions (flat pocket, wave pattern, grid)
- **Loop generators**: Follow boundaries (profile cut, bead, groove)

**Key insight:** Domains define *where*, generators define *what*. This separation enables hundreds of SKUs from few primitives.

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

For domain/generator system:
- **[domains/](domains/)** - Domain type and operations (inset, subtract, intersect)
- **[generators/](generators/)** - Generators that produce LayoutAST Items from Domains
- **[docs/domain_generator_design.md](docs/domain_generator_design.md)** - Full architecture spec
- **[docs/examples/domain_generator_example.py](docs/examples/domain_generator_example.py)** - Integration examples

For CAM validation:
- **[validation/runner.py](validation/runner.py)** - Main validation entry points
- **[validation/invariants/](validation/invariants/)** - Structural checks (SVG, STL, G-code)
- **[docs/cam_validation_plan.md](docs/cam_validation_plan.md)** - Complete validation architecture

For nesting:
- **[pml/nest_parser.py](pml/nest_parser.py)** - `.nest` parser
- **[nesting/api.py](nesting/api.py)** - High-level nesting API
- **[docs/recipes/18_nesting_maxrects/](docs/recipes/18_nesting_maxrects/)** - Complete nesting example

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

### Task 4: Validate Before Planning (IR Level)

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

### Task 5: Validate CAM Artifacts (Post-Generation)

**Use case:** Validate generated SVG, STL, and G-code against structural invariants and regression baselines.

```python
from validation.runner import validate_recipe, ValidationOptions

# Validate a recipe directory with all checks
options = ValidationOptions(
    extract_metrics=True,
    check_invariants=True,
    check_assertions=True,
    check_regressions=True,
)

result = validate_recipe(
    "docs/recipes/01_simple_profile",
    golden_metrics=golden_metrics,  # Optional: from tests/golden/<recipe>/metrics.json
    options=options,
)

# Inspect results
print(f"Verdict: {result.verdict}")  # pass, warn, or fail
print(f"Invariants: {result.invariants.passed}/{result.invariants.total}")
print(f"Assertions: {result.assertions.passed}/{result.assertions.total}")
```

**CLI alternative:**
```bash
# Quick validation with summary output
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary

# With golden baseline comparison
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile \
    --golden tests/golden/01_simple_profile/metrics.json
```

**Why this matters:** CAM artifact validation catches structural issues (non-watertight STL, unsafe G-code rapids, etc.) and metric regressions without manual inspection.

### Task 6: Extract Metrics for Comparison

**Use case:** Extract stable metrics from CAM artifacts for deterministic comparison.

```python
from validation.metrics import extract_svg_metrics, extract_stl_metrics, extract_gcode_metrics

# Extract from files
svg_metrics = extract_svg_metrics("output/drawing.svg")
stl_metrics = extract_stl_metrics("output/model.stl")
gcode_metrics = extract_gcode_metrics("output/toolpath.nc")

# Access specific values
print(f"SVG layers: {svg_metrics.to_dict()['layers']['count']}")
print(f"STL watertight: {stl_metrics.to_dict()['mesh']['is_watertight']}")
print(f"G-code depth: {gcode_metrics.to_dict()['z_profile']['max_plunge_z_mm']}")
```

**Why this matters:** Metrics are deterministic and comparable across runs, enabling regression testing without byte-level file comparison.

### Task 7: Create a Design with Domains and Generators

**Use case:** Build complex panel designs using composable domain operations and generators.

```python
from domains import Domain
from generators import (
    flat_pocket_generator,
    profile_generator,
    wave_generator,
    FlatPocketParams,
    ProfileParams,
    WaveParams,
)
from layout_ast.layout import LayoutAST, Sheet

# Create outer domain from door dimensions
outer_domain = Domain.from_rectangle(
    width_mm=400.0,
    height_mm=600.0,
    center=(200.0, 300.0),
)

# Create panel domain by insetting (frame = 50mm)
panel_result = outer_domain.inset(50.0)
panel_domain = panel_result.domains[0]  # MultiDomain returns tuple of domains

# Generate profile cut for outer edge
profile_items = profile_generator(
    outer_domain,
    ProfileParams(side="outside", depth="through"),
)

# Generate pocket for panel recess
pocket_items = flat_pocket_generator(
    panel_domain,
    FlatPocketParams(depth_mm=6.0),
)

# Build LayoutAST
all_items = profile_items + pocket_items
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(all_items),
)

# Convert to RemovalIntent IR
from adapters.ast_to_removal import ast_to_removal_intents
intents = ast_to_removal_intents(ast)
```

**Why this matters:** Domains and generators enable hundreds of SKUs from few primitives. A wave pattern generator works on any domain. Combining domains and generators creates variety without new code.

**See also:** [docs/examples/domain_generator_example.py](docs/examples/domain_generator_example.py) for complete examples.

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

### Pattern 3: Use Nesting for Production Runs

**When:** You have multiple parts to cut from sheet material and want to minimize waste.

**Steps:**
1. Create a `.nest` file specifying parts, quantities, and sheet size
2. Run nesting to generate PML layouts
3. Process generated PML through the CAM pipeline

**Example:**

```pml
# job.nest
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        door 457mm 597mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        panel 305mm 203mm x15
```

```python
from pml.nest_parser import parse_nest_pml, nest_job_to_api_params
from nesting import nest_and_generate
from pml.formatter import format_pml

# Parse and run nesting
job = parse_nest_pml(open("job.nest").read())
result = nest_and_generate(**nest_job_to_api_params(job), output_format="ast")

# result["output"] is list[LayoutAST], one per sheet
for i, ast in enumerate(result["output"]):
    pml_text = format_pml(ast)
    open(f"sheet_{i+1}.pml", "w").write(pml_text)
```

**Why this matters:** Nesting is essential for production efficiency. The `.nest` format keeps job specifications readable while the algorithms optimize material usage.

### Pattern 4: Add a New Validation Invariant

**When:** You need to add a new structural check for CAM artifacts (e.g., a new G-code safety check).

**Steps:**
1. Add invariant ID and check function in the appropriate `validation/invariants/*_invariants.py`
2. Add to `*_INVARIANT_IDS` list for documentation
3. Add tests

**Example:** Adding a G-code spindle speed limit check

```python
# In validation/invariants/gcode_invariants.py

# 1. Add to invariant IDs
GCODE_INVARIANT_IDS = [
    # ... existing IDs ...
    "GCODE_SPINDLE_SPEED_LIMIT",
]

# 2. Add check function
def _check_spindle_speed_limit(
    gcode_content: str,
    max_speed: float = 24000.0,
) -> InvariantResult:
    """Check spindle speed doesn't exceed limit."""
    # Parse S values from M3/M4 lines
    speeds = []
    for line in gcode_content.splitlines():
        if ("M3" in line or "M4" in line) and "S" in line:
            match = re.search(r"S([\d.]+)", line)
            if match:
                speeds.append(float(match.group(1)))

    violations = [s for s in speeds if s > max_speed]

    return InvariantResult(
        id="GCODE_SPINDLE_SPEED_LIMIT",
        category="safety",
        artifact="gcode",
        description=f"Spindle speed must not exceed {max_speed} RPM",
        status=Verdict.FAIL if violations else Verdict.PASS,
        details={
            "max_allowed": max_speed,
            "violations": violations,
        }
    )

# 3. Call from check_gcode_invariants()
def check_gcode_invariants(gcode_path: str, ...) -> list[InvariantResult]:
    # ... existing checks ...
    results.append(_check_spindle_speed_limit(content, max_speed=config.max_spindle_speed))
    return results
```

**Test:**
```python
# In tests/test_gcode_invariants.py
def test_spindle_speed_limit_violation():
    gcode = "M3 S30000\nG1 X100"
    results = check_gcode_invariants_from_content(gcode, max_spindle_speed=24000)
    limit_check = next(r for r in results if r.id == "GCODE_SPINDLE_SPEED_LIMIT")
    assert limit_check.status == Verdict.FAIL
```

**Why this matters:** The invariant system is the primary way to catch structural issues. Adding invariants for new safety or quality rules is a common extension.

### Pattern 5: Add a New Metric

**When:** You need to extract a new measurement from CAM artifacts (e.g., a new G-code operation count).

**Steps:**
1. Add field to the appropriate `*Metrics` dataclass in `validation/metrics/*_metrics.py`
2. Extract the value in the `extract_*_metrics()` function
3. Add tests

**Example:** Adding arc count to G-code metrics

```python
# In validation/metrics/gcode_metrics.py

@dataclass
class GCodeMetrics:
    # ... existing fields ...
    arc_count: int = 0  # New field

def extract_gcode_metrics(gcode_path: str, config: GCodeConfig = None) -> GCodeMetrics:
    # ... existing extraction ...

    # Count arc moves
    arc_count = sum(1 for line in lines if line.startswith(("G2", "G3")))

    return GCodeMetrics(
        # ... existing values ...
        arc_count=arc_count,
    )
```

**Why this matters:** Metrics enable regression testing. Adding new metrics allows catching regressions in previously unmeasured aspects.

### Pattern 6: Create a New Generator

**When:** You need a new pattern or operation type (e.g., spiral pattern, zigzag fill).

**Steps:**
1. Create a parameter dataclass in `generators/base.py`
2. Implement the generator function in `generators/area/` or `generators/loop/`
3. Export from `generators/__init__.py`
4. Add tests

**Example:** Creating a simple circle pattern generator

```python
# 1. In generators/base.py - add parameter class
@dataclass(frozen=True)
class CirclePatternParams(BaseParams):
    """Parameters for circle pattern generator."""
    circle_diameter_mm: float
    spacing_mm: float
    depth_mm: float

    def __post_init__(self):
        if self.circle_diameter_mm <= 0:
            raise ValueError(f"circle_diameter_mm must be positive, got {self.circle_diameter_mm}")
        if self.spacing_mm <= 0:
            raise ValueError(f"spacing_mm must be positive, got {self.spacing_mm}")
        if self.depth_mm <= 0:
            raise ValueError(f"depth_mm must be positive, got {self.depth_mm}")

# 2. In generators/area/circles.py - implement generator
from domains import Domain
from domains.transforms import local_to_sheet
from layout_ast.layout import Item, Geometry, Placement, Feature
from generators.base import CirclePatternParams, generate_shape_id

def circle_pattern_generator(
    domain: Domain,
    params: CirclePatternParams,
    *,
    allow_empty: bool = False,
) -> list[Item]:
    """Generate a grid of circles within the domain."""
    items = []
    bounds = domain.bounds
    spacing = params.spacing_mm + params.circle_diameter_mm

    y = bounds.y_min + spacing / 2
    row = 0
    while y < bounds.y_max:
        x = bounds.x_min + spacing / 2
        col = 0
        while x < bounds.x_max:
            # Check if circle center is inside domain
            if domain.contains_point((x, y)):
                items.append(Item(
                    kind="shape",
                    type="Circle",
                    geometry=Geometry(data={"diameter_mm": params.circle_diameter_mm}),
                    placement=Placement(center_xy_mm=(x, y)),
                    feature=Feature(type="pocket", depth=params.depth_mm),
                    shape_id=generate_shape_id("circle", f"r{row}c{col}"),
                ))
            x += spacing
            col += 1
        y += spacing
        row += 1

    if not items and not allow_empty:
        raise ValueError("Domain too small for circle pattern")

    return items

# 3. In generators/__init__.py - export
from generators.area.circles import circle_pattern_generator
from generators.base import CirclePatternParams
```

**Why this matters:** Generators are the composable units of the domain system. New generators extend capability without modifying existing code.

### Pattern 7: Add a New Domain Operation

**When:** You need a new algebraic operation on domains (e.g., union, convex hull).

**Steps:**
1. Add method to `Domain` class in `domains/domain.py`
2. Use Shapely for the underlying geometry operation
3. Return `MultiDomain` for consistency with existing operations
4. Add tests

**Example:** Adding union operation

```python
# In domains/domain.py, add to Domain class:

def union(self, other: "Domain") -> "MultiDomain":
    """Combine this domain with another domain.

    Args:
        other: Domain to union with

    Returns:
        MultiDomain containing the combined region(s)
    """
    from shapely.ops import unary_union
    result = unary_union([self._polygon, other._polygon])
    return MultiDomain._from_shapely(
        result,
        local_origin=self.local_origin,
        local_rotation=self.local_rotation,
    )
```

**Why this matters:** Domain operations are the algebraic building blocks. New operations enable new design patterns.

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
**Validation system:** Read [docs/cam_validation_plan.md](docs/cam_validation_plan.md) for schemas and invariants

**Ask the user if:**
- Architectural change needed (new feature types, pipeline modifications)
- Multiple valid approaches exist (choose based on user priorities)
- Ambiguous requirements (clarify before implementing)

---

**Last Updated:** 2026-01-17
**Complementary Doc:** [README.md](README.md) for architecture
**Status:** Production (current architecture)
