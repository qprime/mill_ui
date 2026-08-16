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
| PL-9 | STRUCTURAL | DOMAIN_VIA_PARAMS | Shape handlers pass true geometry to children via `params["domain"]` (Domain) and `params["domain_center"]` (Point2D). Domain-aware child handlers consume these when present, falling back to ResolvedRegion (Rect) when absent. Shape handlers must not special-case child types to pass geometry — all children receive the same params. Structural nodes (Frame, Inset, Grid, Split) strip domain from params before dispatching children. |
| PL-10 | HARD | SINGLE_WRITER | Each serialized artifact type has exactly one canonical writer function. All code paths — CLI, tests, regen, batch — must call it. The writer owns filename and layout; callers pass data only. Any other path that writes this artifact type is a defect. |
| PL-11 | HARD | BACK_SETUP_FIRST | Back-face programs machine before front; through-cuts exist only in the front setup |

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

## Domain Propagation (PL-9)

Shape handlers (`_handle_rect`, `_handle_circle`, `_handle_polygon`, etc.) construct a `Domain`
from their true geometry and pass it to children via `params["domain"]`. Children that need
shape geometry pull the domain from params rather than being special-cased inside the parent handler.

**Convention:**
- `params["domain"]`: `Domain` — the parent shape's true geometry
- `params["domain_center"]`: `Point2D` — the center used for computing relative points and placement

**Contract:**
- Shape handlers MUST set both keys before dispatching children
- Domain-aware handlers (ProfileGen, PocketGen, ChamferGen, RoundoverGen, etc.) MUST check for
  `params.get("domain")` and emit Polygon Items with true geometry when present
- When `params["domain"]` is absent (structural parent like Frame, Inset, Grid), handlers
  fall back to ResolvedRegion and emit Rect Items — preserving backward compatibility
- Shape handlers MUST NOT use isinstance checks on children to pass geometry.
  All children receive the same params; each child decides whether to consume the domain.
- Structural nodes (Frame, Inset, Grid, Split, SplitHorizontal, SplitVertical, SplitGrid,
  SplitHorizontalGaps, AtPosition) MUST strip `domain` and `domain_center` from params
  before dispatching children, since they change the region.

**Wrong:**
Shape handler special-cases a child type:
```python
for child in node.children:
    if isinstance(child, PocketGen):
        # hand-build polygon Item from shape geometry
    else:
        self._resolve_node(child, region, items, params)
```

**Right:**
Shape handler passes domain, all children dispatched uniformly:
```python
domain = Domain.from_polygon(abs_points)
child_params = {**params, "domain": domain, "domain_center": bounds_center}
for child in node.children:
    self._resolve_node(child, region, items, child_params)
```

---

## Back Setup First (PL-11)

A job with any `face: back` feature machines in two setups. The back programs
(`back-*.nc`) run first with the back face up. The operator then flips the
sheet about the X axis and runs the front programs.

Through-profiles are rejected on the back face, so every cut that frees a part
from the sheet lives in the front setup. Parts stay captive through the whole
back setup and through every front operation but the last.

Both setups run the full plan-and-emit sequence against their own AST and
intent set. `PipelineResult.intents` carries the authored-frame set for the
whole job — the validation artifact. The mirrored back intents are internal to
planning and feed the back blueprint view only; mixing the two frames renders
toolpath overlays flipped relative to geometry.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
