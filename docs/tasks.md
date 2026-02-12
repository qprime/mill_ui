# Common Tasks

<!-- spec-style -->

**As-Of:** 2026-01-22

Load this document when you need code examples for standard operations.

---

## Task Index

| Task | Use case |
|------|----------|
| [Generate Layout Programmatically](#task-1-generate-layout-programmatically) | AI generates panel layout from requirements |
| [Parse Human-Authored PML](#task-2-parse-human-authored-pml) | Process user-provided PML text |
| [Use a Template](#task-3-use-a-template) | Generate standard components (Shaker door, etc.) |
| [Validate at IR Level](#task-4-validate-at-ir-level) | Check layout validity before CAM execution |
| [Validate CAM Artifacts](#task-5-validate-cam-artifacts) | Check generated SVG/G-code |
| [Extract Metrics](#task-6-extract-metrics) | Get stable metrics for comparison |
| [Create Design with Domains](#task-7-create-design-with-domains) | Build complex designs using domain algebra |
| [Run Nesting](#task-8-run-nesting) | Optimize part placement on sheets |
| [Run Tests](#task-9-run-tests) | Verify changes with IR and CAM tests |
| [Generate G-code](#task-10-generate-g-code) | Export CNC-ready G-code from PML |
| [Control Dimension Placement](#task-11-control-dimension-label-placement) | Configure dimension label positioning in SVG |

---

## Task 1: Generate Layout Programmatically

**Use case:** AI generates a panel layout from user requirements.

```python
from layout_ast.layout import (
    LayoutAST, Sheet, Item, Geometry, Placement, Feature
)

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", side="outside", depth_mm=0.0, is_through=True),
            shape_id="door_outer"
        ),
    )
)

from adapters.ast_to_removal import ast_to_removal_intents
intents = ast_to_removal_intents(ast)
```

**Key point:** Building AST directly gives maximum control. Serialize with `LayoutAST.to_json()` / `LayoutAST.from_json()`.

---

## Task 2: Parse Human-Authored PML

**Use case:** Process user-provided PML text.

```python
from pml import parse_pml

pml_source = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm

children:
  - Rect:
      id: door
      children:
        - Frame:
            width: 50mm
            children:
              - Rect:
                  id: panel
                  children:
                    - Pocket:
                        depth: 6mm
"""

ast = parse_pml(pml_source)
```

**Key point:** `resolve_layout` converts CompositionalLayoutAST to flat LayoutAST.

---

## Task 3: Use a Template

**Use case:** Generate standard components using PML templates.

```python
from templates import expand_template

items = expand_template(
    template_name="shaker",
    params={
        "stile_w": 50.0,
        "panel_recess": 6.0,
    },
    region_width=400.0,
    region_height=600.0,
    sheet_thickness=19.0,
)
```

**Key point:** Templates are PML files with parameter substitution. See `templates/*.pml.yml` for available templates and `pml/syntax_spec.md` for template syntax.

---

## Task 4: Validate at IR Level

**Use case:** Check layout validity before expensive CAM execution.

```python
from adapters.ast_to_removal import ast_to_removal_intents
from validation.removal_checks import (
    check_overlap,
    check_depth_feasibility,
    check_toolability,
)

intents = ast_to_removal_intents(ast)

overlap = check_overlap(intents)
depth_results = [check_depth_feasibility(i, sheet_thickness_mm=19.0) for i in intents]
toolability_results = [check_toolability(i) for i in intents]

if overlap.has_issues() or any(r.has_issues() for r in depth_results + toolability_results):
    print(overlap.summary())
```

**Key point:** IR validation is fast. Catch errors before CAM execution.

---

## Task 5: Validate CAM Artifacts

**Use case:** Validate generated SVG and G-code against invariants.

```python
from validation.runner import validate_recipe, ValidationOptions

options = ValidationOptions(
    extract_metrics=True,
    check_invariants=True,
    check_assertions=True,
    check_regressions=True,
)

result = validate_recipe(
    "docs/recipes/01_simple_profile",
    golden_metrics=golden_metrics,
    options=options,
)

print(f"Verdict: {result.verdict}")
print(f"Invariants: {result.invariants.passed}/{result.invariants.total}")
```

**CLI alternative:**
```bash
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
```

**Key point:** See `docs/cam_validation_plan.md` for full validation architecture.

---

## Task 6: Extract Metrics

**Use case:** Get stable metrics for deterministic comparison.

```python
from validation.metrics import extract_svg_metrics, extract_gcode_metrics

svg_metrics = extract_svg_metrics("output/drawing.svg")
gcode_metrics = extract_gcode_metrics("output/toolpath.nc")

print(f"SVG layers: {svg_metrics.to_dict()['layers']['count']}")
print(f"G-code depth: {gcode_metrics.to_dict()['z_profile']['max_plunge_z_mm']}")
```

**Key point:** Metrics enable regression testing without byte-level comparison.

---

## Task 7: Create Design with Domains

**Use case:** Build complex designs using domain algebra and generators.

```python
from domains import Domain
from generators import (
    flat_pocket_generator,
    profile_generator,
    FlatPocketParams,
    ProfileParams,
)
from layout_ast.layout import LayoutAST, Sheet

outer_domain = Domain.from_rectangle(
    width_mm=400.0,
    height_mm=600.0,
    center=(200.0, 300.0),
)

panel_result = outer_domain.inset(50.0)
panel_domain = panel_result.domains[0]

profile_items = profile_generator(
    outer_domain,
    ProfileParams(side="outside", depth_mm=0.0, is_through=True),
)

pocket_items = flat_pocket_generator(
    panel_domain,
    FlatPocketParams(depth_mm=6.0),
)

ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)
```

**Key point:** Domains define *where*, generators define *what*. See `docs/domain_generator.md`.

---

## Task 8: Run Nesting

**Use case:** Optimize part placement on sheet material.

```python
from pml.yaml_parser import parse_nest_yaml
from pml.nest_parser import nest_job_to_api_params
from nesting import nest_and_generate
from pml.formatter import format_pml

job = parse_nest_yaml(open("job.nest.yml").read())
result = nest_and_generate(**nest_job_to_api_params(job), output_format="ast")

for i, ast in enumerate(result["output"]):
    pml_text = format_pml(ast)
    open(f"sheet_{i+1}.pml.yml", "w").write(pml_text)
```

**CLI alternative:**
```bash
python -m cli.nest job.nest.yml -o output/ --export-svg
```

**Key point:** See `docs/recipes/18_nesting_maxrects/` for complete example.

---

## Task 9: Run Tests

**Use case:** Verify changes with appropriate test level.

**Activate venv first:** `source .venv/bin/activate`

```bash
# All core tests (PML, Edge, Resolution, Removal Intent)
./run_tests.sh

# IR-level tests (fast, no native backend required)
python -m tests.run_edge_tests

# CAM/G-code equivalence tests (requires native backend)
python -m tests.run_gcode_equivalence_tests

# Recipe validation tests
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
```

**Key point:** Prefer IR tests for development velocity. Run CAM tests only when planner behavior changes.

---

## Task 10: Generate G-code

**Use case:** Export CNC-ready G-code from PML layouts.

**CLI (unified command - generates G-code and SVG):**
```bash
source .venv/bin/activate

# Projects (user workspaces in $MILL_UI_PROJECTS)
python -m cli.mill --project my_table
python -m cli.mill --project my_table --input layout.pml

# Recipes (examples in docs/recipes/)
python -m cli.mill --recipe docs/recipes/01_simple_profile
```

**Projects vs Recipes:**
- `--project`: User workspace for real manufacturing (looks in `$MILL_UI_PROJECTS`)
- `--recipe`: Recipe directory for examples/documentation (outputs to `{recipe}/output/`)

**Options:**
- `--kerf 6.35` — Tool kerf in mm (default: 6.35 for projects, 3.175 for recipes)
- `--theme dark` — Blueprint theme (dark/light/print)
- `--no-svg` — Skip SVG generation
- `--no-clean` — Don't clean output directory before writing

**Regenerate all recipe outputs:**
```bash
python -m tests.test_recipes --regen_recipes
```

**Programmatic (using shared pipeline):**
```python
from pml import parse_pml
from cam.pipeline import run_pipeline, write_pipeline_outputs
from pathlib import Path

pml = """
Sheet:
  width: 300mm
  height: 200mm
  thickness: 19mm

children:
  - RoundedRect:
      id: table_top
      radius: 20mm
      corners: [tl, tr]
      children:
        - Profile:
            side: outside
            depth: through
"""

ast = parse_pml(pml)

result = run_pipeline(ast, kerf_mm=3.175)

outputs = write_pipeline_outputs(
    result,
    output_dir=Path("output"),
    job_name="table_top",
)
```

**Supported shapes:** Rect, Circle, Polygon, RoundedRect (including selective corner rounding).

**Key point:** The unified pipeline handles tool compensation automatically and generates all outputs (G-code and SVG) in one step.

---

## Task 11: Control Dimension Label Placement

**Use case:** Change where dimension labels appear in SVG blueprints.

```python
from diagram_ir.dimensions import place_on_rails, DimensionPlacement

placed = place_on_rails(
    requests,
    sheet_width_mm=ast.sheet.width_mm,
    offset_x=offset_x,
    offset_y=offset_y,
    placement_mode="shape_relative",  # or "sheet_edge"
)
```

**Placement modes:**
- `"shape_relative"` (default) — Dimension labels appear near each shape, with rails positioned relative to the shape's anchor point
- `"sheet_edge"` — All dimension labels appear at the sheet edges (top for horizontal dimensions, right for vertical dimensions)

**Key point:** Use `"shape_relative"` for layouts with shapes spread across the sheet. Use `"sheet_edge"` for simpler layouts or when you prefer all dimensions grouped at the edges.
