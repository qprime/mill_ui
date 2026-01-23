<!-- spec-style -->
# CAM Validation System

As-Of Date: 2026-01-19
Document Type: Validation System Specification
Status: Implementation Complete (Stage 13)

---

## Purpose

Extract stable metrics from CAM artifacts (SVG, STL, G-code).
Validate structural invariants.
Support intent-aware assertions from source PML/AST.
Enable regression testing via metric comparison.
Produce machine-readable JSON output.

---

## Design Principles

| Principle | Description |
|-----------|-------------|
| Deterministic | Same input always produces same metrics |
| Explainable | Every metric has clear definition and unit |
| Intent-aware | Assertions derived from design intent |
| Layered | Metrics → Invariants → Assertions → Verdicts |
| CI-compatible | Headless, structured JSON output |

---

## Architecture

```
Artifacts (SVG/STL/NC) → Metric Extractors → Metric Signature
                                                    ↓
                        ┌───────────────────────────┴───────────────────────────┐
                        ↓                                                       ↓
                Invariant Checks                                    Regression Compare
                        ↓                                                       ↓
                        └───────────────────────────┬───────────────────────────┘
                                                    ↓
                                            Intent Assertions
                                                    ↓
                                          Validation Result (JSON)
                                          {verdict, metrics, invariants, assertions, regressions}
```

---

## Module Structure

```
validation/
├── core.py                 # Verdict, CAMValidationResult
├── results.py              # IR-level ValidationResult
├── removal_checks.py       # IR-level validation
├── runner.py               # Pipeline orchestrator
├── metrics/
│   ├── svg_metrics.py      # SVGMetrics, extract_svg_metrics
│   ├── stl_metrics.py      # STLMetrics, extract_stl_metrics
│   └── gcode_metrics.py    # GCodeMetrics, extract_gcode_metrics
├── invariants/
│   ├── svg_invariants.py   # check_svg_invariants
│   ├── stl_invariants.py   # check_stl_invariants
│   └── gcode_invariants.py # check_gcode_invariants
├── assertions/
│   └── intent_assertions.py # derive_assertions, check_assertions
└── regression/
    ├── comparator.py       # compare_metrics
    └── golden_store.py     # GoldenStore
```

---

## SVG Invariants

| ID | Description |
|----|-------------|
| SVG_VALID_XML | Parses as valid XML |
| SVG_HAS_VIEWBOX | viewBox attribute with positive dimensions |
| SVG_POSITIVE_DIMENSIONS | Width/height > 0 |
| SVG_PATHS_VALID | All path d attributes valid |
| SVG_CLOSED_PROFILES | PROFILE_CUTS geometry is closed |
| SVG_CLOSED_POCKETS | POCKET_REGIONS geometry is closed |
| SVG_NO_EMPTY_LAYERS | Expected layers have content |
| SVG_DIMENSIONS_PRESENT | At least one dimension annotation |
| SVG_BOUNDS_WITHIN_VIEWBOX | Content within viewBox |

---

## STL Invariants

| ID | Description |
|----|-------------|
| STL_VALID_FILE | Parseable STL (binary or ASCII) |
| STL_POSITIVE_VOLUME | Volume > 0 |
| STL_IS_MANIFOLD | Each edge shared by exactly 2 faces |
| STL_IS_WATERTIGHT | Closed surface |
| STL_CONSISTENT_NORMALS | Outward-pointing normals |
| STL_NO_DEGENERATE_FACES | No zero-area triangles |
| STL_BOUNDS_POSITIVE | All dimensions > 0 |
| STL_Z_WITHIN_SHEET | Z in [0, sheet_thickness] |
| STL_CONNECTED | Expected connected components |

---

## G-code Invariants

| ID | Description |
|----|-------------|
| GCODE_PARSEABLE | Valid G-code syntax |
| GCODE_SAFE_Z_RESPECTED | Rapids at/above safe_z |
| GCODE_NO_NEGATIVE_FEED | Feed rates positive |
| GCODE_Z_MONOTONIC_PLUNGE | Z decreases during plunge |
| GCODE_MAX_STEPDOWN | Single step ≤ max_stepdown |
| GCODE_XY_WITHIN_BOUNDS | XY within sheet + margin |
| GCODE_SPINDLE_BEFORE_CUT | M3/M4 before G1 at negative Z |
| GCODE_TOOL_DECLARED | Tool declared before M6 |
| GCODE_ENDS_AT_SAFE | Program ends at safe Z |
| GCODE_CONTINUOUS_PATH | No large XY jumps during cut |
| GCODE_TAB_PATTERN | Tabs at max depth with consistent heights |

---

## Assertion Types

| Type | Source | Description |
|------|--------|-------------|
| SHEET_DIMENSIONS | AST.Sheet | SVG SHEET_OUTLINE matches spec |
| ITEM_COUNT | AST.items | Record item count |
| PROFILE_EXISTS | Item.feature=profile | Geometry exists in PROFILE_CUTS |
| PROFILE_SIDE | Item.feature.side | Outside profile bounds > shape |
| POCKET_DEPTH | Item.feature.depth | Z level in STL |
| HOLE_POSITION | Item.placement | Position in HOLES layer |
| HOLE_DIAMETER | Item.geometry | Radius in HOLES layer |
| THROUGH_CUT | depth="through" | G-code reaches full depth |
| TAB_COUNT | tab_count | G-code Z lifts match |

---

## Tolerances

| Metric | Default | Unit |
|--------|---------|------|
| Position | 0.01 | mm |
| Depth | 0.01 | mm |
| Angle | 0.1 | degrees |
| Area | 0.1 | percent |
| Volume | 0.1 | percent |

---

## Regression Verdicts

| Delta | Verdict |
|-------|---------|
| Within tolerance | PASS |
| Exceeds, < 2× | WARN |
| Exceeds, ≥ 2× | FAIL |
| New metric | PASS (info) |
| Missing metric | WARN |

---

## CLI Usage

```bash
# Validate recipe
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile

# With golden baseline
python -m cli.validate_cam --recipe <path> --golden tests/golden/<name>/metrics.json

# Extract metrics only
python -m cli.validate_cam --svg output/drawing.svg --metrics-only

# Human-readable summary
python -m cli.validate_cam --recipe <path> --summary
```

Exit codes: 0=PASS, 1=WARN, 2=FAIL

---

## Golden Baseline Structure

```
tests/golden/
├── index.json
├── 01_simple_profile/
│   ├── metrics.json
│   └── source.pml
└── ...
```

---

## Programmatic API

```python
from validation.runner import validate_recipe, ValidationOptions

result = validate_recipe(
    "docs/recipes/01_simple_profile",
    options=ValidationOptions(
        extract_metrics=True,
        check_invariants=True,
        check_assertions=True,
        check_regressions=True,
    ),
    golden_metrics=golden,
)

print(f"Verdict: {result.verdict}")  # pass, warn, fail
```

---

## Key Files

| File | Purpose |
|------|---------|
| validation/runner.py | validate(), validate_recipe() |
| cli/validate_cam.py | CLI interface |
| cli/generate_golden.py | Golden baseline generation |
| tests/golden/ | Golden metric store |
