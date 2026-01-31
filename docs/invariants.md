# Critical Invariants

<!-- spec-style -->

**As-Of:** 2026-01-19

Load this document before modifying core system behavior.

---

## Invariants

These properties MUST hold. Breaking them causes subtle bugs.

### 1. Always Go Through RemovalIntent IR

**Rule:** All AST-to-CAM conversion MUST pass through RemovalIntent IR layer.

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

### 2. Don't Mutate Frozen Dataclasses

**Rule:** Use `replace()` to modify frozen dataclasses. Never mutate nested dicts.

**Wrong:**
```python
item.geometry.data["w_mm"] = 100
```

**Correct:**
```python
from dataclasses import replace
new_item = replace(item, geometry=Geometry(data={**item.geometry.data, "w_mm": 100}))
```

**Why:** Frozen dataclasses prevent accidental mutation. Nested dicts remain technically mutable but should be treated as immutable.

---

### 3. Dimensions Are Always Millimeters

**Rule:** All dimensions in the system use millimeters. No unit suffixes in variable names, no conversions.

```python
sheet = Sheet(width_mm=450, height_mm=650, thickness_mm=19)
```

**Why:** Consistency prevents unit conversion bugs. MM is standard for CNC.

---

### 4. Test at IR Level

**Rule:** Write tests against RemovalIntent IR, not full CAM pipeline.

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

### 5. Semantic Equivalence, Not Syntax Preservation

**Rule:** Round-trip through parser/formatter preserves semantics, not surface syntax.

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

---

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Bypassing IR layer | No semantic validation | Always: AST → RemovalIntent → hints |
| Mutating dataclasses | Shared state corruption | Use `replace()` |
| Creating new files | File proliferation | Edit existing files |
| Adding inline comments | Code style violation | Remove comments, use clear naming |
| Mixing pipeline layers | Coupling, hard to test | Keep layers separate |
| Testing at CAM level | Slow, requires native backend | Test at IR level |

---

## Layer Separation

Keep pipeline layers separate. Don't mix concerns.

**Wrong:**
```python
def build_layout(...):
    ast = LayoutAST(...)
    gcode = generate_gcode(ast)
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

## Error Philosophy

| Category | Behavior | Use when |
|----------|----------|----------|
| Hard error | Raise exception | Invalid input, constraint violation |
| Soft failure | Return empty + flag | Optional operation, absence acceptable |
| Never allowed | Silent partial output | — |

Error messages MUST include:
- What operation failed
- What constraint was violated
- Actual vs. expected values

---

### 6. Working-Area Coordinate System

**Rule:** PML specifies physical sheet dimensions (`physical_width`, `physical_height` or `width`, `height`) and margin. The working area is derived as `physical - 2*margin`. All part coordinates are relative to working area origin (0,0). The margin defines a physical offset applied only at G-code/SVG export.

**Wrong:**
```python
item_x = margin + offset
```

**Correct:**
```python
item_x = offset  # margin applied at export
```

**Why:** The margin zone is a physical no-cut zone reserved for clamps. No cutting operation may encroach on this zone—including tool paths for outside profiles. The margin zone cannot be addressed and never exists in internal coordinates.

**Tool clearance:** Outside profile cuts require part edges to be at least one tool diameter from working area boundaries. See [pml/syntax_spec.md](../pml/syntax_spec.md#tool-clearance-for-outside-profiles) for PML placement rules.

---

### 7. Toe-Kick Dado Positioning

**Rule:** The bottom face of the bottom panel sits at `toe_kick_height` above the cabinet bottom. For the side-panel capture groove, `position_mm` for the bottom-panel interface must equal `toe_kick_height` (measured from the side panel bottom edge to the near side of the groove).

**Wrong:**
```python
bottom_dado_position = toe_kick_height + thickness
```

**Correct:**
```python
bottom_dado_position = toe_kick_height
```

**Why:** The groove's near edge aligns with the bottom panel's bottom face. Any visual offset in SVG output comes from groove width and centering math in the resolver, not the physical alignment requirement. Do not add thickness or other offsets to `position_mm`.
