# Pipeline & Layer Invariants

**Applies to:** AST, IR, CAM layers, data flow

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| PL-1 | HARD | PIPELINE_ORDER | PML/JSON → LayoutAST → RemovalIntent IR → CAM Planner → G-code |
| PL-2 | HARD | IR_LAYER_REQUIRED | All AST-to-CAM conversion MUST pass through RemovalIntent IR layer |
| PL-3 | HARD | SEMANTIC_NOT_SYNTAX | Round-trip preserves semantics, not surface syntax |
| PL-4 | HARD | TEST_AT_IR | Write tests against RemovalIntent IR, not full CAM pipeline |
| PL-5 | HARD | DETERMINISTIC | Pipeline is deterministic |
| PL-6 | STRUCTURAL | LAYOUT_TOPDOWN | Layout managers subdivide regions top-down |
| PL-7 | STRUCTURAL | SHAPES_EMIT_ABSOLUTE | Shapes emit items with absolute coordinates |
| PL-8 | HARD | NO_PASSTHROUGH_GEOMETRY | Do not add computed planner-geometry fields to Feature or RemovalIntent. See "Known Exception" below. |

---

## Always Go Through RemovalIntent IR

**Wrong:**
```python
hints = convert_ast_to_hints_directly(ast)
```

**Correct:**
```python
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_hints(intents)
```

**Why:** RemovalIntent is the semantic validation layer. Bypassing it means no validation, no extensibility.

---

## Test at IR Level

**Wrong:**
```python
gcode = generate_full_pipeline(ast)
assert "G1 X100" in gcode
```

**Correct:**
```python
intents = ast_to_removal_intents(ast)
assert intents[0].bounds == Bounds2D(x_min=50, x_max=150, ...)
```

**Why:** IR tests are fast, portable, and focused. CAM tests require native backend and are slow.

---

## Semantic Equivalence

**Wrong assumption:**
```python
pml_output = format_pml(parse_pml(pml_input))
assert pml_output == pml_input
```

**Correct:**
```python
ast1 = parse_pml(pml_input)
ast2 = parse_pml(format_pml(ast1))
assert ast1 == ast2
```

**Why:** Round-trip preserves semantics, not surface syntax. Whitespace, key order, and comments may change.

---

## Layer Separation

Keep pipeline layers separate. Don't mix concerns.

**Wrong:**
```python
def build_layout(...):
    ast = LayoutAST(...)
    gcode = generate_gcode(ast)  # <-- mixing layers
    return ast
```

**Correct:**
```python
ast = build_layout(...)
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_hints(intents)
gcode = plan_and_generate(hints)
```

---

## No Pass-Through Geometry on Semantic Dataclasses (PL-8)

`Feature` and `RemovalIntent` are semantic dataclasses. They describe *what* to machine, not *how*. Do not add fields that carry computed planner-level geometry (absolute corner coordinates, tool-specific offsets, reference points) through these layers.

**Known exceptions:**

1. `dogbone_corners` and `dogbone_reference_point` on `Feature` and `RemovalIntent` exist because the resolver has geometric context (panel placement, notch edge, cursor position) that the adapter lacks. These fields are consumed by exactly one path in `removal_to_planner.py` to build `DogboneInput` for 2-corner assembly notch dogbones.

2. `RestSpec.tool_diameter_mm` on `Feature` and `RemovalIntent` constrains the removal geometry — it determines which corner regions get machined (areas the rough tool can't reach are defined by the rough/rest tool diameter relationship). This is analogous to `corner_cleanup_tool_diameter_mm`, which exists on Feature/RemovalIntent because the tool diameter defines the bore geometry at each corner.

These are contained exceptions — do not use them as a pattern for new fields.

**Wrong:**
```python
@dataclass(frozen=True)
class Feature:
    my_computed_corners: tuple[tuple[float, float], ...] | None = None
```

**Right:** Compute planner geometry in the adapter from bounds, shape, and semantic metadata already on RemovalIntent. If the adapter lacks sufficient context, raise the design question rather than threading geometry through semantic layers.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
