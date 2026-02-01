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

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
