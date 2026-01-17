# Recipe 05: Validation Workflow

Example layout for IR-level validation (overlap, depth feasibility, toolability checks) and CAM artifact validation.

**Key concepts:**
- Multiple overlapping features
- Validation at RemovalIntent level
- Depth and toolability checking
- CAM artifact validation (SVG, STL, G-code)

## IR-Level Validation

RemovalIntent validation checks design semantics before CAM execution:

```python
from adapters.ast_to_removal import ast_to_removal_intents
from validation.removal_checks import (
    check_overlap,
    check_depth_feasibility,
    check_toolability,
)

intents = ast_to_removal_intents(ast)

# Check for overlapping removal regions
overlap = check_overlap(intents)
if overlap.has_issues():
    print(overlap.summary())

# Check depth feasibility per intent
for intent in intents:
    result = check_depth_feasibility(intent, sheet_thickness_mm=19.0)
    if result.has_issues():
        print(result.summary())
```

## CAM Artifact Validation

After CAM execution, validate the generated artifacts:

### Command Line

```bash
# Validate this recipe
python -m cli.validate_cam --recipe docs/recipes/05_validation_workflow --summary

# Validate with golden baseline
python -m cli.validate_cam --recipe docs/recipes/05_validation_workflow \
    --golden tests/golden/05_validation_workflow/metrics.json

# Extract metrics only (no checks)
python -m cli.validate_cam --recipe docs/recipes/05_validation_workflow --metrics-only
```

### Programmatic

```python
from validation.runner import validate_recipe, ValidationOptions

options = ValidationOptions(
    extract_metrics=True,
    check_invariants=True,
    check_assertions=True,
    check_regressions=False,  # No golden baseline
)

result = validate_recipe("docs/recipes/05_validation_workflow", options=options)

# Check result
print(f"Verdict: {result.verdict}")  # pass, warn, or fail
print(f"Invariants: {result.invariants.passed}/{result.invariants.total}")

# Access extracted metrics
if "svg" in result.metrics:
    print(f"SVG layers: {result.metrics['svg']['layers']['count']}")
if "stl" in result.metrics:
    print(f"STL watertight: {result.metrics['stl']['mesh']['is_watertight']}")
if "gcode" in result.metrics:
    print(f"G-code lines: {result.metrics['gcode']['summary']['total_lines']}")
```

## Golden Baseline

This recipe has a golden baseline at `tests/golden/05_validation_workflow/metrics.json`.

To regenerate after intentional changes:
```bash
python -m cli.generate_golden --recipe docs/recipes/05_validation_workflow --update
```

## Output Files

- `output/05_validation_workflow.svg` - Blueprint drawing
- `output/example.stl` - 3D mesh preview
- `output/*.nc` - G-code toolpath files
