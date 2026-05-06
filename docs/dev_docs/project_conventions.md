# Project Conventions

Mill_ui-specific deltas and concrete instantiations of the universal standard. Curated patterns that name *real* layers, modules, and contracts in this codebase.

The universal Python standard lives in [docs/python_guidelines.md](../python_guidelines.md) — frozen-dataclass field ordering, naming verbs, error-message format, type-system mechanisms, nullable-numeric `or`-trap, etc. This file documents only what's specific to mill_ui: the layer names, the named protocols, the concrete dispatch registries, the coordinate-transform timing.

Invariants say "don't violate this." This file says "when you need X in mill_ui, this is the pattern we use."

---

## Error Semantics by Layer

The generic table in python_guidelines.md §17 names the categories. This is the mill_ui instantiation:

| Layer | On Failure | Mechanism |
|-------|-----------|-----------|
| PML Parser | Fail | Raise `PMLParseError`; caught at parse entry point |
| Layout Resolver | Skip | Catch `GeneratorSkipError` from generators; continue with remaining items |
| Generators | Skip or Fail | Raise `GeneratorSkipError` (non-fatal) when domain too small or constraints violated; raise `ValueError` for truly invalid params. `allow_empty=True` returns `[]` instead of raising. |
| Adapters (AST→IR) | Warn + Skip | `try/except ValueError` around each item; log warning, append to `warnings` list, continue |
| Adapters (IR→Planner) | Warn + Skip | Same pattern — catch, log, append to warnings |
| Planner Passes | Warn + Skip | Log to `accumulator.add_warning()`; skip individual feature, continue job |
| Pipeline (`run_pipeline`) | Collect + Gate | Accumulates `errors`/`warnings` lists; halts on safety-critical constraint failures |

## GeneratorSkipError Protocol

`GeneratorSkipError` (subclass of `ValueError`) signals "domain too small or constraints unsatisfiable" — a normal condition, not a bug. Mill_ui's instantiation of the §18 expected-failure pattern.

The full protocol:
- Generators raise `GeneratorSkipError` when `allow_empty=False` and work is impossible
- Generators return `[]` when `allow_empty=True` and work is impossible
- Resolver handlers always call generators with `allow_empty=True` and silently catch `GeneratorSkipError`
- When a generator calls another generator internally, it conditionally re-raises based on its own `allow_empty` flag

The error-semantics table covers where this is caught. The key convention is: resolver handlers never let `GeneratorSkipError` propagate — they swallow it.

## Dispatch Patterns

- **Feature-type dispatch in adapters**: `@register_feature` decorator populates `FEATURE_HANDLERS` dict; handler looked up via `FEATURE_HANDLERS.get(feature_type)`. Layer routing uses `FEATURE_LAYER` dict (feature_type → layer name), with `WASTE_LAYER` override for waste items. Both registries live in `adapters/layoutast_to_ir.py`. New feature types can pass `layer=` to `@register_feature` to register both handler and layer in one call.
- **PML node-type dispatch**: Currently a large if/elif chain in `parse_node()`. Not registry-based, known debt, deferred.
- **Generator dispatch**: No central registry. Layout resolver imports generators individually and dispatches by AST node type.
- **Shape-type dispatch in planner**: Currently if/elif chains with `.lower()` comparison. Not registry-based, known debt, deferred.
- When adding new dispatch, prefer the `@register_feature` dict pattern over if/elif chains.

## Shape Names

- Canonical form is PascalCase, defined in `core.constants.ShapeType`: `"Rect"`, `"Circle"`, `"Polygon"`, `"RoundedRect"`
- All comparison code calls `.lower()` at function entry before dispatching
- Planner passes work with lowercase; adapters receive PascalCase from AST
- When adding shape dispatch, always normalize with `.lower()` first

## Data Flow Through Adapters

Adapter functions follow a consistent sequence:
1. Validate preconditions — raise `ValueError` if required fields missing
2. Build intermediate representation (hint dict or typed input)
3. Dispatch to specialized converter by feature type
4. Post-process via `replace()` for optional overrides
5. Return a single typed dataclass (never a tuple with mixed types)

## Generator Function Signature

All generators follow: `generator_fn(domain: Domain, params: FrozenParams, *, allow_empty=False)`
- `params` is always a frozen dataclass
- `allow_empty` is keyword-only (after `*`)
- No generator takes more than 3 positional parameters; everything else in the params object

## Import Layering

No backward imports across layer boundaries:
- Generators import from `generators.core` and `core.*` — never from `resolution`
- Adapters import from both sides of the boundary they bridge (e.g., `layout_ast` and `ir`)
- Planner passes import from `cam.ops.*` and sibling modules — never from adapters
- Layout resolver imports generators — generators never import from resolver

## Pipeline Structured Output

`run_pipeline()` returns a result with `errors: list[str]` and `warnings: list[str]`. All layers should contribute to these lists rather than logging independently. This is the contract between layers and the pipeline orchestrator.

## DiagramIR Metadata

- `DiagramIR.metadata` is `dict[str, Any]` with JSON-serializable values
- Adapter collects raw data; renderer (`diagram_render/render_svg.py`) builds presentation chrome
- Metadata keys are descriptive strings: `"sheet_width"`, `"feature_counts"`, `"depth_info"`

## Coordinate Transform Timing

Two pipelines apply margin and y-flip at different points. Never mix.

**Diagram pipeline** — transforms early, in the adapter (`adapters/layoutast_to_ir.py`):
- X: `sx = margin + cx`
- Y: `sy = margin + working_height - y` (back origin, the default)
- Renderer receives `ViewportSpec(y_flip=False)` — no second flip

**CAM pipeline** — transforms late, at G-code export (`cam/post/gcode.py`):
- `_move_to_dict()` folds margin and optional Y-flip into the native-call dict in a single pass
- X: `x + margin_mm`
- Y: `sheet_height - (y + margin_mm)` when `y_origin="front"`, else `y + margin_mm`

The rule: diagram path bakes transforms into shape coordinates during IR generation. CAM path preserves working-area coordinates through the entire pipeline and transforms at the output boundary.

## PML Round-Trip Convention

All Feature fields must survive `parse → format → parse`. This is tested and enforced.

- Formatter emits only non-default fields (e.g., dogbone omitted when all defaults)
- Parser accepts both detailed and simplified forms; formatter emits simplest valid form
- Idempotency: `format(parse(x))` is stable — formatting twice produces identical output
- JSON emitter/parser (`layout_ast/emitters.py`, `layout_ast/parsers.py`) follows the same convention

When adding a new Feature field: add it to parser, formatter, JSON emitter, JSON parser, and round-trip tests. Incomplete coverage will silently drop the field.

## Planner Pass Accumulation

`PassAccumulator` deduplicates by `pass_key = (operation, diameter, kind, rotation, v_angle_deg, roundover_radius_mm)`. Multiple features with identical tool + operation share one `PassRecord` — moves are appended to the same record.

Each `plan_X_passes()` function: pick tool → call ops function → append moves to accumulator record. Ops functions (`cam/ops/`) are pure: `(geometry, setup, **params) → list[Move]`.

## Test Organization

- No shared pytest fixtures — all test state built via `_make_*()` factory functions inline in each test file
- Golden file pattern: generate → normalize → compare; auto-create if missing locally, fail in CI
- Recipe auto-discovery: `docs/recipes/*/*.pml.yml` discovered by glob, no manual registration
- Parametrize with descriptive IDs: `pytest.param(..., id="profile_outside_through")`
- Property-based tests use Hypothesis `@st.composite` strategies for domain geometry

## Mode-Specific Fields on `DepthProfile`

When a new depth mode adds fields, enforce cross-field invariants in `__post_init__`:
- Field REQUIRED when mode matches (raise if absent)
- Field FORBIDDEN when mode doesn't match (raise if present)

Example from `DepthProfile.heightfield`:

```python
if self.mode == "heightfield" and self.image_path is None:
    raise ValueError("image_path required for heightfield mode")
if self.mode != "heightfield" and self.image_path is not None:
    raise ValueError(f"image_path only valid for heightfield mode, got mode={self.mode!r}")
```

This preserves PL-8 spirit (DepthProfile is semantic, not computed geometry) while keeping mode-specific parameters on the single dataclass rather than forking `RemovalIntent`. Matching serializers (`to_dict` / `from_dict`) must emit/require the field only when mode matches.
