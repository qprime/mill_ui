# Conventions

Curated patterns that define "how we do things here." Manually maintained — the audit skill reads this but cannot modify it.

These complement the invariant files. Invariants say "don't violate this." Conventions say "when you need X, this is the pattern we use."

---

## Error Semantics by Layer

| Layer | On Failure | Mechanism |
|-------|-----------|-----------|
| PML Parser | Fail | Raise `PMLParseError`; caught at parse entry point |
| Layout Resolver | Skip | Catch `GeneratorSkipError` from generators; continue with remaining items |
| Generators | Skip or Fail | Raise `GeneratorSkipError` (non-fatal) when domain too small or constraints violated; raise `ValueError` for truly invalid params. `allow_empty=True` returns `[]` instead of raising. |
| Adapters (AST→IR) | Warn + Skip | `try/except ValueError` around each item; log warning, append to `warnings` list, continue |
| Adapters (IR→Planner) | Warn + Skip | Same pattern — catch, log, append to warnings |
| Planner Passes | Warn + Skip | Log to `accumulator.add_warning()`; skip individual feature, continue job |
| Pipeline (`run_pipeline`) | Collect + Gate | Accumulates `errors`/`warnings` lists; halts on safety-critical constraint failures |

## Shape Names

- Canonical form is PascalCase, defined in `core.constants.ShapeType`: `"Rect"`, `"Circle"`, `"Polygon"`, `"RoundedRect"`
- All comparison code calls `.lower()` at function entry before dispatching
- Planner passes work with lowercase; adapters receive PascalCase from AST
- When adding shape dispatch, always normalize with `.lower()` first

## Dispatch Patterns

- **Feature-type dispatch in adapters**: `@register_feature` decorator populates `FEATURE_HANDLERS` dict; handler looked up via `FEATURE_HANDLERS.get(feature_type)`. Layer routing uses `FEATURE_LAYER` dict (feature_type → layer name), with `WASTE_LAYER` override for waste items. Both registries live in `adapters/layoutast_to_ir.py`. New feature types can pass `layer=` to `@register_feature` to register both handler and layer in one call.
- **PML node-type dispatch**: Currently a large if/elif chain in `parse_node()`. Not registry-based (known debt, deferred).
- **Generator dispatch**: No central registry. Layout resolver imports generators individually and dispatches by AST node type.
- **Shape-type dispatch in planner**: Currently if/elif chains with `.lower()` comparison. Not registry-based (known debt, deferred).
- When adding new dispatch, prefer the `@register_feature` dict pattern over if/elif chains.

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

## Logging

- Module-level logger: `_logger = logging.getLogger(__name__)` (underscore prefix)
- Warning messages use parametrized formatting: `_logger.warning("message %s", value)`

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

---

## Frozen Dataclass Conventions

All core data types are `@dataclass(frozen=True)`. This is the default — use frozen unless you have an explicit reason not to.

**Field ordering** (strict, no exceptions observed):
1. Required fields (no default)
2. Optional typed fields (`| None = None`)
3. Factory-default fields (`field(default_factory=...)`)
4. Scalar defaults (`= value`)

**Collections are tuples**, not lists: `items: tuple[Item, ...] = ()`. Empty tuple default uses literal `()`. Use `field(default_factory=tuple)` only for non-empty or complex defaults.

**Mutation via `replace()` only.** Some classes provide `with_*()` helpers that wrap `replace()`:
```python
def with_notches(self, notches: tuple[NotchSpec, ...]) -> PanelSpec:
    return replace(self, notches=self.notches + notches)
```

**`__post_init__` for invariant validation.** Validates at construction time — ranges, enum membership, cross-field constraints. Raises `ValueError` with message format: `"{field} {constraint}, got {value}"`.

## GeneratorSkipError Protocol

`GeneratorSkipError` (subclass of `ValueError`) signals "domain too small or constraints unsatisfiable" — a normal condition, not a bug.

The full protocol:
- Generators raise `GeneratorSkipError` when `allow_empty=False` and work is impossible
- Generators return `[]` when `allow_empty=True` and work is impossible
- Resolver handlers always call generators with `allow_empty=True` and silently catch `GeneratorSkipError`
- When a generator calls another generator internally, it conditionally re-raises based on its own `allow_empty` flag

The error-semantics table covers where this is caught. The key convention is: resolver handlers never let `GeneratorSkipError` propagate — they swallow it.

## Coordinate Transform Timing

Two pipelines apply margin and y-flip at different points. Never mix.

**Diagram pipeline** — transforms early, in the adapter (`adapters/layoutast_to_ir.py`):
- X: `sx = margin + cx`
- Y: `sy = margin + working_height - y` (back origin, the default)
- Renderer receives `ViewportSpec(y_flip=False)` — no second flip

**CAM pipeline** — transforms late, at G-code export (`cam/post/gcode.py`):
- `_apply_margin_offset()` adds margin to X and Y of all moves
- `_flip_y_in_moves()` only applies when `y_origin="front"`

The rule: diagram path bakes transforms into shape coordinates during IR generation. CAM path preserves working-area coordinates through the entire pipeline and transforms at the output boundary.

## PML Round-Trip Convention

All Feature fields must survive `parse → format → parse`. This is tested and enforced.

- Formatter emits only non-default fields (e.g., dogbone omitted when all defaults)
- Parser accepts both detailed and simplified forms; formatter emits simplest valid form
- Idempotency: `format(parse(x))` is stable — formatting twice produces identical output
- JSON emitter/parser (`layout_ast/emitters.py`, `layout_ast/parsers.py`) follows the same convention

When adding a new Feature field: add it to parser, formatter, JSON emitter, JSON parser, and round-trip tests. Incomplete coverage will silently drop the field.

## Type System Conventions

Six type mechanisms, each with a specific use case:

| Mechanism | When to Use | Example |
|-----------|------------|---------|
| `Enum` with `auto()` | Internal identity types (value doesn't matter) | `PanelRole`, `InterfaceType`, `RemovalKind` |
| `Enum` with string values | Serialized or user-facing values | `Verdict`, `PackingAlgorithm`, `ConstraintSupport` |
| `Literal[...]` | Inline field constraints on dataclass fields | `EdgeName`, `MachiningStage`, orientation fields |
| Plain constants class | String keys for dict lookup and dispatch | `HintKeys`, `FeatureType`, `ShapeType`, `Side` in `core/constants.py` |
| Pipe union (`A \| B`) | Sum types at module level | `Move`, `Shape`, `EdgeFeatureSpec` |
| `@runtime_checkable Protocol` | Structural subtyping interfaces | `JoineryStrategy`, `Generator` |

## Naming Vocabulary

Layer boundaries use consistent verbs. Match the verb to the operation:

| Verb | Meaning | Used At |
|------|---------|---------|
| `parse_*` | String → structured data | PML parser, dimension parser |
| `format_*` | Structured data → string | PML formatter |
| `resolve_*` | Structural resolution (AST simplification, assembly expansion) | Layout resolver, assembly |
| `*_to_*` | Adapter conversion between typed representations | `ast_to_removal_intents`, `removal_intents_to_planner_input` |
| `plan_*` | Toolpath planning from features | `plan_passes`, `plan_pocket_passes` |
| `write_*` | Emit machine-readable output | `write_gcode` |
| `render_*` | Emit visual/diagram output | `render_diagram_svg`, `render_blueprint_svg` |
| `load_*` | Read from disk | `load_pml_template`, `load_machine_tool_db` |
| `expand_*` | Parameterized instantiation | `expand_template` |
| `build_*` | Construct complex objects from parts | `build_tool_db`, `_build_assembly` |
| `nest_*` | Bin-packing optimization | `nest_parts`, `nest_and_generate` |

Private helpers use underscore prefix with verb patterns: `_handle_*` (dispatch), `_build_*` (construction), `_validate_*` (checks), `_collect_*` / `_count_*` (aggregation), `_is_*` / `_has_*` (predicates).

## Validation and Control Flow

**Guard clauses at entry.** Functions validate preconditions with early `raise` before real work. Style is `if bad: raise ValueError(...)` — not nested conditionals.

**Normalize before validating.** Call `.lower()`, `.strip()`, `float()` at function entry to canonicalize inputs before any branching or validation.

**Per-item isolation in loops.** Adapters and planner passes wrap each item in `try/except ValueError`, log the skip with item identity, and continue. No batch failures — one bad item never kills the rest.

**Error message format:** `"{ClassName}: {field} {constraint}, got {value}"` — always includes the field name, the violated constraint, and the actual value.

## Logging vs Structured Warnings

When an item is skipped, emit **both**:
1. `_logger.warning(...)` — developer-facing diagnostic (parametrized: `"%s", msg`)
2. `warnings.append(msg)` or `accumulator.add_warning(msg)` — pipeline-facing, appears in `PipelineResult`

Pure `_logger` without structured warning is only for diagram-path skips (non-pipeline, no user report needed). If the skip affects G-code output, it must reach `warnings`.

Warning messages always include: feature/item ID, specific problem, action taken (`"— feature skipped"`).

## Collection Building

- Build with explicit loop + `append`/`extend`, not list comprehension. This keeps per-item error handling and conditional logic readable.
- Convert to tuple at the return boundary: `return tuple(result_list)`. Internal accumulation uses `list`; frozen dataclass fields store `tuple`.
- Input order is preserved by default. Deduplication, when needed, uses `pass_key()` tuples as dict keys (planner pass accumulation).

## Planner Pass Accumulation

`PassAccumulator` deduplicates by `pass_key = (operation, diameter, kind, rotation, v_angle_deg, roundover_radius_mm)`. Multiple features with identical tool + operation share one `PassRecord` — moves are appended to the same record.

Each `plan_X_passes()` function: pick tool → call ops function → append moves to accumulator record. Ops functions (`cam/ops/`) are pure: `(geometry, setup, **params) → list[Move]`.

## Test Organization

- No shared pytest fixtures — all test state built via `_make_*()` factory functions inline in each test file
- Golden file pattern: generate → normalize → compare; auto-create if missing locally, fail in CI
- Recipe auto-discovery: `docs/recipes/*/*.pml.yml` discovered by glob, no manual registration
- Parametrize with descriptive IDs: `pytest.param(..., id="profile_outside_through")`
- Property-based tests use Hypothesis `@st.composite` strategies for domain geometry

## Serialization Completeness

`to_dict()` methods must serialize all non-private fields. If a field is intentionally omitted, document the omission with a comment at the serialization site explaining why. Silent omission is a data-loss bug.

## Nullable Numeric Parsing

Never use `or` for nullable numeric fields where `0` is a valid value. Python's `or` treats `0`, `0.0`, and `""` as falsy, silently falling through to the alternative.

**Wrong:**
```python
width = node_data.get("width") or fallback_value
```

**Correct:**
```python
width = node_data.get("width")
if width is None:
    width = fallback_value
```

This applies to all YAML/JSON parsing where numeric fields may legitimately be zero.
