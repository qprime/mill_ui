# Mill UI Refactor: AI-First Compositional Architecture

## Overall Goal

Transform mill_ui into an explicitly AI-agent-first compositional CAD/CAM system. The architecture already supports template-based composition with parameterization, but lacks discoverability, introspection, and documentation that signals this design philosophy. The refactor should make the mental model explicit: **templates are parameterizable UI components for physical objects**, where agents author layouts declaratively similar to building React/SwiftUI interfaces but generating G-code instead of HTML.

Key principles:
- **Machine-readable schemas** for template discovery and parameter validation
- **Structured error feedback** enabling agents to self-correct invalid specifications
- **Explicit compositional patterns** documented with agent-oriented examples
- **Maintain monolithic deployment** while enforcing internal modularity boundaries
- **Preserve deterministic execution** and existing CLI/API contracts

---

## Architectural Changes

| Claude | Codex | Change Category | Description |
|:------:|:-----:|-----------------|-------------|
| ☐ | ☐ | **Material Removal IR (Volume-Intent Core)** | Introduce a canonical intermediate representation (RemovalIntent) that explicitly models what material volume is to be removed, independent of operation names, tool selection, or toolpath strategy. RemovalIntent is not an operation label—it is a normalized material-removal specification describing boundaries, depth models (z_top/z_bottom, not just scalar depth), allowances (inside/outside/on + kerf), and constraints (tabs/bridges, keepouts/islands, tolerance bands). All machining operations fundamentally remove material; this IR captures semantic intent as the bridge between declarative templates and planner lowerings. Existing operation types (profile/pocket/hole/engrave) become adapters that produce RemovalIntent records. Enables inspectable, dumpable, strategy-agnostic material intent for agent debugging and optimization. Scope limited to 3-axis 2.5D; no full solid/mesh boolean modeling required. RemovalIntent does not guarantee manufacturability—toolability, collision checks, and physics remain validation layers. Implement incrementally behind existing planner entry points. |
| ☑ | ☑ | **Template Metadata System** | Extend `@register_template` decorator to accept machine-readable metadata including description, parameter schema (type, required, constraints, description), example parameter sets, and capability flags. Export registry metadata via CLI command and programmatic API for agent discovery. |
| ☐ | ☐ | **Canonical Layout AST** | Introduce a canonical `LayoutAST` (typed tree) as the authoritative internal model for layout specifications. Both JSON and PML surface syntaxes compile into `LayoutAST`. All downstream stages (template expansion, RemovalIntent generation, planners) consume only the AST. AST instances are fully normalized: defaults injected, stable child ordering (order-insensitive collections canonically sorted; order-preserving sequences left intact where ordering carries semantic meaning), numeric normalization, schema-validated. This AST is the single source of truth that enables semantic equivalence with canonical re-emission—the system guarantees both JSON and PML can be re-emitted canonically from the AST, but does not preserve surface formatting, comments, syntactic sugar, or original ordering from human-authored inputs. Implement with `.from_json()`, `.to_json()`, `.from_pml()`, `.to_pml()` methods. |
| ☐ | ☐ | **Formalize Data Contracts** | Introduce strongly-typed models at system boundaries (e.g., `LayoutAST`, `Item`, `FeatureSpec`, `RemovalIntent`, `CamHints`, `Move`, `PassPlan`) with `.from_dict()`/`.to_dict()` adapters. The RemovalIntent IR becomes the canonical representation of material removal semantics. Keep internal dicts initially to avoid a big-bang rewrite; migrate incrementally behind adapters. Generate JSON Schema artifacts for the Layout DSL, RemovalIntent IR, and key intermediates (hints/passes) for external consumption. Legacy operation-based hints map cleanly to RemovalIntent via adapters. |
| ☐ | ☐ | **Structured Validation Framework** | Implement validation result objects returning field-level errors with suggestions instead of raw exceptions. Add template parameter validators as declarative schema constraints. Extend validation to RemovalIntent IR records (overlap detection, depth feasibility, toolability checks). Provide partial success indicators for incremental agent corrections. |
| ☑ | ☑ | **Agent-Facing Documentation** | Create `docs/ai_agent_guide.md` explaining the mental model (templates as components), composition patterns (primitives → templates → layouts), JSON schema references, and example agent workflows. Include natural language → JSON transformation examples. Document the feature specification DSL as first-class interface. |
| ☑ | ☑ | **Hexagonal Architecture Refactoring** | Extract orchestration core from 804-line compose_cam into domain layer with explicit ports. Primary port accepts layout specifications and configuration, returns planned operations. Secondary ports for tool database, template resolver, native backend. Move CLI adapter to separate layer. Enables programmatic API usage without CLI dependency. |
| ☑ | ☑ | **Functional Pipeline Transformation** | Reframe as a pragmatic step: keep mutation localized (builder/accumulator) but make outputs immutable, typed, and replayable (e.g., `PassPlan` records + per-stage result records). Add deterministic ordering and stage-level event emission first; treat full fold-based immutability/parallelization as a later optimization if it proves valuable. |
| ☑ | ☑ | **Plugin Architecture for Templates** | Replace ad-hoc imports in `compositions/__init__.py` with an explicit `load_templates()` step that supports deterministic module discovery (e.g., `pkgutil.walk_packages` with allow/deny filters) and optional entry-point plugins when packaged. Keep core usable with minimal deps by guarding optional imports. |
| ☐ | ☐ | **PML Surface Syntax (Declarative Front-End)** | **Phase 2 feature**—not a foundational dependency. Introduce PML (Panel Markup Language), a purely declarative, non-executable syntax inspired by QML/SwiftUI for human authoring and review. PML compiles directly to canonical LayoutAST (not to JSON or planners). Allowed: component blocks, literal values, lists, nested components, named regions. Explicitly disallowed: loops, conditionals, variables, expressions, imports with side effects. Implement both `pml → ast` parser and `ast → pml` pretty-printer. System-emitted PML must be canonical (all defaults explicit, stable ordering, no syntactic sugar). Human-authored PML may include sugar, desugared before AST creation. PML is not a programming language; AI agents emit JSON, not PML. PML exists for human readability and canonical AST visualization. JSON remains the primary interface until PML is implemented. |
| ☐ | ☐ | **Observability Layer** | Add structured event emission throughout pipeline for template expansion decisions, RemovalIntent generation, tool selection rationale, pass planning heuristics, native backend invocations. Emit RemovalIntent IR as inspectable intermediate artifact. Enable trace collection without logger pollution. Support debugging of agent-generated layouts by exposing material removal semantics explicitly. |
| ☑ | ☑ | **Module Boundary Enforcement** | Define explicit public APIs for cad.* and cam.* namespaces exported only through api/* re-exports. Start with conventions + lightweight tests (or a simple internal checker) to prevent boundary violations; optionally adopt import-linter later if the repo already supports that tooling. |
| ☑ | ☑ | **Example Gallery & Test Corpus** | Create `examples/agent_generated/` with natural language prompts, generated JSON layouts, and expected intermediate artifacts (resolved items, hints, pass plans, manifests). Avoid committing large binary STL/STEP outputs; generate previews on demand and/or validate via deterministic hashes and summaries for regression stability. |
| ☐ | ☐ | **Layout DSL v1 + JSON Schema** | Define a versioned Layout DSL (`schema_version`) and ship `schemas/layout_v1.schema.json` for validation/autocomplete. JSON remains the **preferred AI interface**—agents emit JSON, not PML. Include schema for RemovalIntent IR as canonical material removal representation. Include a small set of canonical examples covering single items and composed sheets, and document the stable "shape/feature" vocabulary aligned to 3-axis 2.5D capabilities. Feature specs become adapters that lower to RemovalIntent. Both JSON and PML compile to the same canonical LayoutAST. |
| ☑ | ☑ | **Canonicalization & Reproducibility** | Implement canonical JSON normalization for layouts and intermediate artifacts (stable key ordering for order-insensitive collections, default injection, numeric normalization rules). Schema definitions must declare whether ordering is semantic. Canonicalization must not reorder sequences where ordering affects machining precedence or intent. Emit stable manifests/hashes so agent edits can be regression-tested and compared without manual debugging. |
| ☐ | ☐ | **Agent CLI Introspection** | Add CLI subcommands oriented to agents: `list-templates`, `show-template <name>` (metadata + schema), `validate-layout` (JSON or PML input), `dump-schemas`, `dump-ast`, `dump-removal-intent`, `convert-layout --from json --to pml`, `convert-layout --from pml --to json`, and `compose` options like `--dump-intermediates` / `--trace-json`. Expose LayoutAST and RemovalIntent IR as inspectable artifacts. All outputs machine-readable, deterministic, and stable. Conversion commands validate semantic equivalence and emit canonical forms—formatting, comments, syntactic sugar, and original ordering are not preserved. |
| ☑ | ☑ | **Migration & Backward Compatibility Plan** | Define an explicit migration plan: legacy layouts/move dicts remain supported via adapters; new typed/model+schema layer becomes the "source of truth". Document deprecation milestones and ensure `apps/compose_cam.py` behavior/output stays compatible during the transition. |

---

## Review Instructions

### For Each Change:
1. **Evaluate** whether the change aligns with the AI-first goal
2. **Assess** impact on maintainability, complexity, and existing contracts
3. **Consider** implementation effort vs value delivered
4. **Check** for conflicts with other proposed changes
5. **Mark** your column with ☑ when satisfied, or edit the description and clear all checks

### Consensus Criteria:
- Both reviewers have checked the row (☑ in both columns)
- Description clearly articulates scope, rationale, and approach
- Change preserves monolithic deployment and deterministic execution
- Implementation path is tractable without excessive rework

### Iteration Protocol:
- Each reviewer makes edits in their turn
- When editing a row description, clear all checkmarks for that row
- Add new rows if needed to address gaps
- Remove rows if deemed unnecessary
- Continue until all rows have dual consensus or explicit documented disagreement

---

## Pipeline Flow (with LayoutAST and RemovalIntent IR)

The refactored architecture introduces dual surface syntaxes with canonical intermediate representations:

```
JSON Layout (AI-first)          PML Layout (human-readable)
      ↓                                    ↓
   parse_json()                       parse_pml()
      ↓                                    ↓
      └──────────────→ LayoutAST ←────────┘
                (CANONICAL INTERNAL MODEL)
           - fully normalized (defaults injected)
           - stable child ordering
           - numeric normalization
           - schema-validated
                       ↓
            Template Expansion (compositions/*)
                       ↓
            RemovalIntent IR ← CANONICAL MATERIAL REMOVAL SEMANTICS
                │  (what volume to remove, independent of strategy/tool)
                │  - region bounds (2D shape + depth)
                │  - removal type (through-cut, pocket, relief)
                │  - constraints (min tool diameter, tolerances)
                │  - provenance (source template/feature)
                       ↓
            Planner Lowerings (cam/planner/*)
                │  (strategy selection: zigzag, spiral, helical, etc.)
                │  (tool selection: choose appropriate tool from database)
                       ↓
            Move IR (typed move records)
                │  (linear, arc, rapid, plunge sequences)
                       ↓
            G-code Generation (cam/post/gcode)
                │  (machine-specific output)
                       ↓
            G-code Files (.nc)
```

**Key Properties**:
- **LayoutAST is the single source of truth**: Both JSON and PML compile to LayoutAST
- **Semantic equivalence with canonical re-emission**: `JSON → AST → PML → AST → JSON` preserves semantics; the system guarantees stable canonical re-emission but does not preserve surface formatting, comments, syntactic sugar, or original ordering from human-authored inputs
- **JSON is AI-preferred**: Agents emit JSON with schema validation
- **PML is human-friendly (Phase 2)**: Declarative syntax for authoring and review (no control flow, no execution); JSON remains primary interface until PML is implemented
- RemovalIntent is **inspectable** (agents can dump/validate before planning)
- RemovalIntent is **strategy-agnostic** (same intent → multiple valid toolpaths)
- RemovalIntent is **tool-agnostic** (planner selects tools based on intent constraints)
- RemovalIntent is **not an operation label**—it specifies boundaries, depth models (z_top/z_bottom), allowances, and constraints (tabs, keepouts, tolerance bands)
- RemovalIntent **does not guarantee manufacturability**—toolability, collision checks, and physics remain validation layers
- Legacy operation hints (profile/pocket/hole) **adapter** to RemovalIntent
- RemovalIntent enables **optimization passes** (merge overlapping removals, reorder by depth)

---

## Non-Goals (PML Constraints)

PML is an **enabling constraint**, not a feature expansion:
- **PML is not a programming language**: No control flow, macros, or execution model
- **No attempt to mirror full QML semantics**: Inspired by QML syntax only; no QML runtime features
- **No dependency on Qt or QML runtimes**: Pure Python parser/formatter
- **No requirement that AI agents generate PML**: JSON remains the AI-first interface
- **PML exists for humans**: Authoring, review, and visualization of canonical ASTs only

---

## Interactions / Conflicts (Reviewer Notes)

- **LayoutAST is foundational**: Must be defined before PML parser/formatter or JSON Schema v1. Both surface syntaxes compile to AST.
- **LayoutAST precedes Template Expansion**: Templates consume normalized AST, not raw JSON/PML dicts.
- **Material Removal IR is foundational**: Should be defined early alongside Data Contracts; other systems (Validation, Observability, CLI) reference it.
- **RemovalIntent precedes planner refactoring**: Existing planners become lowering passes that consume RemovalIntent; implement adapters first to preserve behavior.
- **PML is Phase 2**: LayoutAST, RemovalIntent, JSON schema, and CLI introspection take priority. PML depends on stable LayoutAST schema; defer until core semantic work is complete.
- **JSON ↔ PML semantic equivalence testing is critical (when PML ships)**: Canonicalization rules must guarantee semantic equivalence; implement round-trip test suite with canonical re-emission validation. Surface formatting, comments, and syntactic sugar are not preserved.
- Template Metadata depends on Template Discovery/Loading; discovery should be explicit before metadata export becomes reliable.
- Data Contracts and Validation should share one error format (JSON Pointer paths + suggestions) to avoid duplicated "validation languages".
- **RemovalIntent schema must be stable before Example Gallery**: Examples should include dumped RemovalIntent artifacts alongside layouts.
- Example Corpus depends on Canonicalization/Reproducibility; do that early to prevent test churn.
- Hexagonal refactor is easiest once boundary models exist; extract the orchestration core as a pure function/API first, then peel off adapters.
- Module boundary enforcement should follow (or be introduced alongside) the public API surface definition so it doesn't lock in accidental dependencies.
- Full functional/parallel planning is likely lower priority than typed outputs + traces; treat it as an optimization track.
- Agent CLI Introspection commands should be designed alongside Template Metadata System to ensure consistent output formats (both should use same JSON Schema representations).
- **Agent CLI Introspection should expose LayoutAST and RemovalIntent**: `dump-ast` and `dump-removal-intent` commands align with observability layer.
- **CLI conversion commands validate semantic equivalence (when PML ships)**: `convert-layout` should emit warnings if semantic drift detected; canonical re-emission expected.
- Layout DSL v1 should be finalized before Example Gallery to avoid needing to update all examples when schema changes.
- Template discovery should be deterministic (stable ordering) so exported metadata/CLI dumps are diff-friendly and regression-stable.
- **Canonicalization applies only to order-insensitive collections**: Schema must declare semantic ordering; sequences where order affects machining precedence or intent remain untouched.
- Canonicalization rules should be reused by CLI/schema/artifact dumps so hashes and diffs don't drift between tools.

---

---

## Staged Implementation Plan (AI-Driven)

### Execution Model

The refactor proceeds **stage-by-stage** with the following constraints:

**Process Requirements:**
- Legacy repo tagged and frozen before work begins
- Each stage results in a clean, reviewable commit
- Stages execute sequentially—no parallel work on multiple stages
- Stage marked `done` only when all deliverables and acceptance tests pass
- AI agents work autonomously within stage boundaries

**AI Execution Contract:**

AI agents implementing stages **MUST**:
- Read complete stage definition before starting
- Implement code changes only within stated scope
- Add/update unit tests as specified in deliverables
- Run all acceptance tests and verify they pass
- Commit changes with message: `[StageID] Stage Name`
- Update stage status to `done` with commit hash

AI agents **MUST NOT**:
- Skip stages or combine multiple stages
- Expand scope beyond stage definition
- Refactor unrelated code outside scope
- Proceed to next stage without passing all acceptance tests
- Modify earlier stage implementations while working on later stages

**Rollback Safety:**
- Each stage identifies rollback mechanism
- Git tag created after each completed stage: `refactor_v2_[StageID]`
- Back-compat guarantees specify what existing behavior must preserve

---

### Equivalence Types for Staged Acceptance

The staged implementation uses different equivalence criteria depending on the nature of the change:

- **Byte-identical**: Exact G-code match, including whitespace and formatting (used only for low-level regression or adapter validation stages like S6)
- **Semantic / Geometry-equivalent**: Same intended geometry, visual result, and decorative intent; toolpaths may differ in motion planning, ordering, or efficiency (used for v2 templates like ShakerPanel in S10)
- **Behavioral / Safety-equivalent**: Safe toolpaths respecting bounds, depths, feeds/spindle constraints from tool database

**Important**: Core pipeline adapters (S5, S6) aim for byte-identical or behavioral equivalence to validate correctness. **New v2 templates explicitly target semantic/geometry equivalence**, allowing improved planners and strategies without coupling to legacy motion quirks.

---

### Stage Definition Template

Every stage follows this structure:

| Field | Description |
|-------|-------------|
| **Stage ID** | Short stable identifier (e.g., `S1_AST_CORE`) |
| **Stage Name** | Human-readable name |
| **Goal** | One-sentence objective |
| **Scope** | Files/modules expected to change |
| **Deliverables** | Concrete artifacts produced (types, schemas, CLI commands, dumps, tests) |
| **Acceptance Tests** | Exact commands/tests and assertions required to pass |
| **Equivalence Type** | One of: byte-identical, semantic/geometry-equivalent, behavioral/safety-equivalent |
| **Back-Compat Guarantee** | What existing behavior must remain unchanged |
| **Risk / Rollback** | How to revert or disable this stage if needed |
| **Blocking Dependencies** | Prior stages that must complete first |
| **Status** | `todo` / `in-progress` / `done` |
| **Commits** | Commit hash(es) completing the stage |

---

### Implementation Stages

#### Stage 1: Tag Legacy + Create v2 Skeleton

| Field | Value |
|-------|-------|
| **Stage ID** | `S1_TAG_SKELETON` |
| **Stage Name** | Tag Legacy Codebase and Create v2 Namespace |
| **Goal** | Freeze current implementation and establish v2 development namespace |
| **Scope** | - Create `skills/mill_ui/v2/` directory<br>- Add `skills/mill_ui/v2/__init__.py`<br>- Tag repo: `mill_ui_v1_frozen` |
| **Deliverables** | - Git tag `mill_ui_v1_frozen`<br>- Empty `v2/` namespace with stub `__init__.py`<br>- `v2/README.md` stating "v2 refactor in progress—do not use" |
| **Acceptance Tests** | - `git tag -l \| grep mill_ui_v1_frozen` returns tag<br>- `ls skills/mill_ui/v2/__init__.py` exists<br>- v1 tests still pass: `python run.py mill_ui_tests` |
| **Back-Compat Guarantee** | All v1 code unchanged; v1 imports continue working |
| **Risk / Rollback** | Delete `v2/` directory; no risk to existing code |
| **Blocking Dependencies** | None |
| **Status** | `done` |
| **Commits** | `5e79908` |

---

#### Stage 2: Minimal LayoutAST Definition + JSON Loader

| Field | Value |
|-------|-------|
| **Stage ID** | `S2_AST_CORE` |
| **Stage Name** | Define Canonical LayoutAST with JSON Parser |
| **Goal** | Create typed LayoutAST structure that can parse existing JSON layouts |
| **Scope** | - `v2/ast/layout.py` (LayoutAST, Sheet, Item dataclasses)<br>- `v2/ast/parsers.py` (`.from_json()` method)<br>- `v2/tests/test_ast_json_parse.py` |
| **Deliverables** | - `LayoutAST` dataclass with `sheet`, `items`, `config` fields<br>- `Sheet`, `Item`, `Placement` dataclasses<br>- `LayoutAST.from_json(path)` static method<br>- Unit tests parsing 3 existing v1 layout files |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_ast_json_parse.py -v` passes<br>- Parse `cnc_clamp_v1/input/layout.json` without errors<br>- Assert AST contains correct sheet dimensions and item count |
| **Back-Compat Guarantee** | v1 code untouched; v2 only consumes, does not emit |
| **Risk / Rollback** | Delete `v2/ast/`; no impact on v1 |
| **Blocking Dependencies** | `S1_TAG_SKELETON` |
| **Status** | `done` |
| **Commits** | `8c1102d`, `718290d` (fix for template layouts) |

---

#### Stage 3: Canonical JSON Emission + Normalization

| Field | Value |
|-------|-------|
| **Stage ID** | `S3_AST_EMIT` |
| **Stage Name** | Implement Canonical JSON Emission from LayoutAST |
| **Goal** | Enable AST to emit canonical JSON with normalization rules |
| **Scope** | - `v2/ast/emitters.py` (`.to_json()` method)<br>- `v2/ast/canonicalize.py` (normalization rules)<br>- `v2/tests/test_ast_roundtrip.py` |
| **Deliverables** | - `LayoutAST.to_json()` method<br>- Canonicalization: stable key ordering (order-insensitive collections), default injection, numeric normalization<br>- Round-trip test: `json → AST → json` preserves semantics |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_ast_roundtrip.py -v` passes<br>- Round-trip 3 layouts: semantic equivalence verified<br>- Emitted JSON is deterministic (hash stable across runs) |
| **Back-Compat Guarantee** | v1 unchanged; v2 AST semantically equivalent to v1 JSON |
| **Risk / Rollback** | v2 AST remains read-only; emission failures don't affect v1 |
| **Blocking Dependencies** | `S2_AST_CORE` |
| **Status** | `done` |
| **Commits** | `1adc2a9` |

---

#### Stage 4: Minimal RemovalIntent IR Definition

| Field | Value |
|-------|-------|
| **Stage ID** | `S4_REMOVAL_IR_CORE` |
| **Stage Name** | Define RemovalIntent IR Data Structures |
| **Goal** | Create typed RemovalIntent models with core semantics (boundaries, depths, constraints) |
| **Scope** | - `v2/ir/removal_intent.py` (RemovalIntent, RemovalRegion dataclasses)<br>- `v2/tests/test_removal_intent_model.py` |
| **Deliverables** | - `RemovalIntent` dataclass with `region_id`, `bounds`, `z_top`, `z_bottom`, `allowance`, `constraints` fields<br>- `Bounds2D`, `Allowance` (inside/outside/on + kerf), `Constraints` (tabs, keepouts, tolerance) types<br>- Unit tests validating model construction |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_removal_intent_model.py -v` passes<br>- Create RemovalIntent instance with all fields<br>- Assert serialization to dict preserves semantics |
| **Back-Compat Guarantee** | v1 unchanged; RemovalIntent is v2-only construct |
| **Risk / Rollback** | Delete `v2/ir/`; no impact on v1 |
| **Blocking Dependencies** | `S1_TAG_SKELETON` |
| **Status** | `done` |
| **Commits** | `d84b021` |

---

#### Stage 5: Adapter: Legacy Hints → RemovalIntent

| Field | Value |
|-------|-------|
| **Stage ID** | `S5_HINTS_ADAPTER` |
| **Stage Name** | Build Adapter from v1 CAM Hints to RemovalIntent IR |
| **Goal** | Convert existing operation hints (profile/pocket/hole) to RemovalIntent records |
| **Scope** | - `v2/adapters/hints_to_removal.py` (adapter functions)<br>- `v2/tests/test_hints_adapter.py` |
| **Deliverables** | - `profile_hint_to_removal_intent()` function<br>- `pocket_hint_to_removal_intent()` function<br>- `hole_hint_to_removal_intent()` function<br>- Unit tests converting v1 hints to RemovalIntent |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_hints_adapter.py -v` passes<br>- Convert v1 profile hint with depth="through" → RemovalIntent with correct z_top/z_bottom<br>- Convert v1 pocket with depth_mm=5 → RemovalIntent with z_top=0, z_bottom=-5 |
| **Back-Compat Guarantee** | v1 hint generation unchanged; adapter is one-way v1→v2 |
| **Risk / Rollback** | Adapter is pure function; no state changes |
| **Blocking Dependencies** | `S4_REMOVAL_IR_CORE` |
| **Status** | `done` |
| **Commits** | `93b2f10` (tag: `refactor_v2_S5_HINTS_ADAPTER`) |

---

#### Stage 6: Planner Adapter: RemovalIntent → Existing Strategies

| Field | Value |
|-------|-------|
| **Stage ID** | `S6_PLANNER_ADAPTER` |
| **Stage Name** | Adapt RemovalIntent IR to Existing v1 Planners |
| **Goal** | Build adapter enabling RemovalIntent to feed v1 planner (infrastructure for Stage 10 Shaker panel) |
| **Scope** | - `v2/adapters/removal_to_planner.py` (adapter to v1 planner inputs)<br>- `v2/tests/test_planner_adapter.py` |
| **Deliverables** | - `removal_intent_to_v1_hints()` function converting RemovalIntent → v1 hint format<br>- `removal_intents_to_v1_hints()` batch converter with proper bucketing (profiles/pockets/holes/engraves)<br>- Round-trip tests validating adapter correctness (v1 hint → RemovalIntent → v1 hint) |
| **Acceptance Tests** | - Standalone test runner passes (pytest-independent)<br>- Round-trip preserves geometry, depth, side, tabs, start_depth<br>- Output structure matches `build_cam_hints()` format<br>- Coverage: profile, pocket, hole operations |
| **Equivalence Type** | **N/A** (infrastructure; validated via round-trip correctness, proven in Stage 10 end-to-end) |
| **Back-Compat Guarantee** | v1 unchanged; adapter is pure function layer |
| **Risk / Rollback** | Delete `v2/adapters/removal_to_planner.py`; no impact on v1 |
| **Blocking Dependencies** | `S5_HINTS_ADAPTER` |
| **Status** | `done` |
| **Commits** | `9ac0ef9` (tag: `refactor_v2_S6_PLANNER_ADAPTER`) |
| **Notes** | G-code equivalence framework in `ea4d4e8` available for environments with native CAM core |

---

#### Stage 7: AST & RemovalIntent Dump / Introspection

| Field | Value |
|-------|-------|
| **Stage ID** | `S7_CLI_DUMP` |
| **Stage Name** | Add CLI Commands for AST and RemovalIntent Inspection |
| **Goal** | Enable agents to dump/validate AST and RemovalIntent artifacts |
| **Scope** | - `v2/cli/introspect.py` (`dump-ast`, `dump-removal-intent` commands)<br>- `v2/tests/test_cli_dump.py` |
| **Deliverables** | - `python v2/cli/introspect.py dump-ast <layout.json>` outputs canonical JSON AST<br>- `python v2/cli/introspect.py dump-removal-intent <layout.json>` outputs RemovalIntent IR as JSON<br>- Both commands produce deterministic, machine-readable output |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_cli_dump.py -v` passes<br>- Dump AST for test layout, parse output JSON successfully<br>- Dump RemovalIntent for test layout, verify region count and bounds |
| **Back-Compat Guarantee** | v1 CLI unchanged; v2 CLI is additive |
| **Risk / Rollback** | Delete `v2/cli/`; no impact on v1 |
| **Blocking Dependencies** | `S3_AST_EMIT`, `S5_HINTS_ADAPTER` |
| **Status** | `done` |
| **Commits** | `77136aa` (tag: `refactor_v2_S7_CLI_DUMP`) |

---

#### Stage 8: Validation Hooks for RemovalIntent

| Field | Value |
|-------|-------|
| **Stage ID** | `S8_VALIDATION` |
| **Stage Name** | Implement RemovalIntent Validation Framework |
| **Goal** | Add validation layer for RemovalIntent (overlap detection, depth feasibility, toolability) |
| **Scope** | - `v2/validation/removal_checks.py` (validation functions)<br>- `v2/validation/results.py` (ValidationResult dataclass)<br>- `v2/tests/test_removal_validation.py` |
| **Deliverables** | - `ValidationResult` dataclass with `errors`, `warnings`, `suggestions` fields<br>- `check_overlap()`, `check_depth_feasibility()`, `check_toolability()` functions<br>- Unit tests with valid and invalid RemovalIntent scenarios |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_removal_validation.py -v` passes<br>- Overlapping regions detected with field-level error<br>- Invalid depth (z_top < z_bottom) caught with suggestion |
| **Back-Compat Guarantee** | v1 validation unchanged; v2 validation is stricter but optional |
| **Risk / Rollback** | Validation is advisory; can be disabled via flag |
| **Blocking Dependencies** | `S4_REMOVAL_IR_CORE` |
| **Status** | `done` |
| **Commits** | `2222261` |

---

#### Stage 9: SVG Verification Overlays (Kerf/Offsets)

| Field | Value |
|-------|-------|
| **Stage ID** | `S9_SVG_OVERLAYS` |
| **Stage Name** | Add SVG Rendering with RemovalIntent Visualization |
| **Goal** | Visualize RemovalIntent regions with kerf/offset overlays for debugging |
| **Scope** | - `v2/export/svg_removal.py` (SVG exporter with RemovalIntent layer)<br>- `v2/tests/test_svg_removal.py` |
| **Deliverables** | - `render_svg_with_removal_intent(ast, removal_ir, output_path)` function<br>- SVG output includes: original shapes (black), RemovalIntent bounds (red), kerf offsets (blue dashed)<br>- Sample SVG for visual inspection |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_svg_removal.py -v` passes<br>- Generate SVG for test layout with RemovalIntent overlay<br>- SVG file size > 0, contains `<path>` elements for removal regions |
| **Back-Compat Guarantee** | v1 SVG export unchanged; v2 SVG is additive |
| **Risk / Rollback** | SVG export is debugging aid; failures don't block G-code |
| **Blocking Dependencies** | `S5_HINTS_ADAPTER` |
| **Status** | `done` |
| **Commits** | `34977c3` |

---

#### Stage 10: ShakerPanel v2 Template (Flagship Recovery)

| Field | Value |
|-------|-------|
| **Stage ID** | `S10_SHAKER_V2` |
| **Stage Name** | Rebuild Shaker Template Using v2 AST/RemovalIntent |
| **Goal** | Demonstrate end-to-end v2 pipeline with production-ready template |
| **Scope** | - `v2/templates/shaker.py` (Shaker template using v2 AST)<br>- `v2/tests/test_shaker_v2.py` |
| **Deliverables** | - `ShakerV2` template class implementing `expand_to_ast()` method<br>- Integration test: natural language → JSON → AST → RemovalIntent → G-code<br>- RemovalIntent dump with expected region count/types<br>- SVG verification layers (design boundary, tool centerlines, tool radius envelopes)<br>- Deterministic summary artifacts (tools used, depths, bounds) |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_shaker_v2.py -v` passes<br>- Generate Shaker panel via v2 pipeline<br>- **RemovalIntent verification**: Correct count of regions (outer profile, inner pocket, rabbet passes, borders)<br>- **SVG verification**: Design boundary, tool centerlines, tool envelopes visible; no overlap; within stock bounds<br>- **Safety verification**: Respects safe-Z, depth limits, feeds/spindle within tool DB constraints<br>- **Geometry verification**: Finished panel dimensions match spec; rabbet depths correct; border decorations present |
| **Equivalence Type** | **semantic/geometry-equivalent** (same finished panel geometry and decorative intent; toolpaths may differ in motion planning, ordering, or efficiency) |
| **Back-Compat Guarantee** | v2 Shaker produces geometrically equivalent panels; G-code motion may differ from v1 |
| **Risk / Rollback** | If geometry/safety verification fails, template or planner has semantic errors—block until resolved |
| **Blocking Dependencies** | `S2_AST_CORE`, `S4_REMOVAL_IR_CORE`, `S6_PLANNER_ADAPTER` |
| **Status** | `done` |
| **Commits** | `f954aa5` |

---

#### Stage 11: PML Surface Syntax (Phase 2 - Deferred)

| Field | Value |
|-------|-------|
| **Stage ID** | `S11_PML_SYNTAX` |
| **Stage Name** | Implement PML Parser and Formatter |
| **Goal** | Add human-readable PML surface syntax compiling to LayoutAST |
| **Scope** | - `v2/pml/parser.py` (PML → AST parser)<br>- `v2/pml/formatter.py` (AST → PML pretty-printer)<br>- `v2/tests/test_pml_roundtrip.py` |
| **Deliverables** | - `parse_pml(text) → LayoutAST` function<br>- `format_pml(ast) → str` function<br>- Semantic equivalence tests: `PML → AST → JSON → AST` preserves semantics<br>- CLI: `convert-layout --from pml --to json` |
| **Acceptance Tests** | - `python -m pytest v2/tests/test_pml_roundtrip.py -v` passes<br>- Parse sample PML, emit canonical JSON, verify semantics preserved<br>- PML → AST → PML produces canonical (not original) formatting |
| **Back-Compat Guarantee** | JSON remains primary; PML is additive human interface |
| **Risk / Rollback** | PML is Phase 2; delete `v2/pml/` if needed without affecting core |
| **Blocking Dependencies** | `S2_AST_CORE`, `S3_AST_EMIT` (LayoutAST must be stable) |
| **Status** | `done` |
| **Commits** | `d704125` |

---

#### Stage 12: Layout Resolution Foundation

| Field | Value |
|-------|-------|
| **Stage ID** | `S12_LAYOUT_RESOLUTION` |
| **Stage Name** | Compositional Layout Resolution Foundation |
| **Goal** | Enable hierarchical, region-relative composition without explicit XY coordinates |
| **Scope** | - `v2/ast/compositional.py` (Panel, Frame, Grid, Cell, Inset, ComponentDef, UseComponent, Place, Rect nodes)<br>- `v2/resolution/layout_resolver.py` (resolve_layout pass)<br>- `v2/tests/test_layout_resolution.py` |
| **Deliverables** | - Compositional AST schema extensions (minimal, explicit)<br>- Layout resolution pass: hierarchical → flat LayoutAST<br>- Children fill parent region by default<br>- Frame works on any closed region<br>- Multiple component instances placeable on one sheet<br>- Output compatible with FlatPML/RemovalIntent pipeline |
| **Acceptance Tests** | - 4 identical component instances via grid<br>- Each instance: frame + 2×2 grid + pockets<br>- No explicit coordinates required in authored AST<br>- FlatPML output valid and inspectable<br>- All 8 resolution tests pass |
| **Equivalence Type** | **foundation** (compositional layer; semantic preservation through lowering) |
| **Back-Compat Guarantee** | Compositional AST is additive; existing flat LayoutAST/Item nodes unchanged |
| **Risk / Rollback** | Delete `v2/ast/compositional.py` and `v2/resolution/` if needed; FlatPML unaffected |
| **Blocking Dependencies** | `S2_AST_CORE`, `S11_PML_SYNTAX` (FlatPML for output inspection) |
| **Status** | `done` |
| **Commits** | `8b6a702` |

---

#### Stage 13: Compositional PML Parser

| Field | Value |
|-------|-------|
| **Stage ID** | `S13_COMPOSITIONAL_PML` |
| **Stage Name** | Compositional PML Parser (Indentation-Based) |
| **Goal** | Implement human-facing compositional language that compiles to Stage 12 compositional AST |
| **Scope** | - `v2/pml/compositional_parser.py` (PML → CompositionalAST parser)<br>- `v2/pml/compositional_formatter.py` (CompositionalAST → PML formatter)<br>- `v2/tests/test_compositional_pml.py` |
| **Deliverables** | - Indentation-based parser supporting: `sheet`, `project`, `component`, `use`, `place`, `panel`, `rect`, `inset`, `frame`, `grid`, `cell`<br>- Feature nodes: `pocket`, `profile`, `engrave`, `hole`, `edge` (as intent labels)<br>- NO arithmetic, NO expressions, NO conditionals<br>- Strict error messages with line/column numbers<br>- Round-trip formatter (CompositionalAST → canonical PML)<br>- CLI integration: `parse-compositional-pml <file.pml>` |
| **Acceptance Tests** | - Parse Stage 12 gold exemplar PML (4 instances × frame+grid+pockets)<br>- Resolve to 24 items (8 profiles, 16 pockets)<br>- Match exact item counts from Stage 12 Python test<br>- Round-trip: PML → AST → PML produces canonical formatting<br>- Error handling: Invalid indentation, unknown keywords, missing required fields |
| **Equivalence Type** | **semantic/geometry-equivalent** (same resolved items as Stage 12 Python AST) |
| **Back-Compat Guarantee** | Compositional PML is additive; FlatPML (Stage 11) and Python AST construction unchanged |
| **Risk / Rollback** | Delete `v2/pml/compositional_*`; Stage 12 Python API unaffected |
| **Blocking Dependencies** | `S12_LAYOUT_RESOLUTION` |
| **Status** | `done` |
| **Commits** | `b09cf42` |

---

#### Stage 14: Basic Shape Primitives

| Field | Value |
|-------|-------|
| **Stage ID** | `S14_BASIC_SHAPES` |
| **Stage Name** | Basic Shape Primitives (Circle, RoundedRect, Line) |
| **Goal** | Expand primitive shape coverage for core 3-axis 2.5D CNC capabilities (geometry + intent, not toolpath strategy) |
| **Scope** | - `v2/ast/compositional.py` (Circle, RoundedRect, Line nodes)<br>- `v2/resolution/layout_resolver.py` (resolve new shapes to regions/paths)<br>- `v2/pml/compositional_parser.py` (parse new shape syntax)<br>- `v2/pml/compositional_formatter.py` (format new shapes)<br>- `v2/tests/test_basic_shapes.py` |
| **Deliverables** | - Circle (closed region): `diameter` or `fit` mode (inscribed in current region)<br>- RoundedRect (closed region): `radius` for corners, fills current region by default<br>- Line (open path): simple horizontal/vertical canned forms for engraving<br>- Region-relative positioning (no explicit XY)<br>- Fill-by-default semantics consistent with rect<br>- Parse/format round-trip tests<br>- Resolution correctness tests<br>- Doc update: "Shapes" section in v2/docs |
| **Acceptance Tests** | - New PML parses and formats canonically<br>- Circle `fit` works inside rect region<br>- RoundedRect fills region with corner radius preserved<br>- Line horizontal/vertical spans region deterministically<br>- Existing Stage 12/13 exemplar still passes unchanged<br>- No changes to strategy/lowering behavior |
| **Equivalence Type** | **foundation** (geometry primitives; semantic preservation through lowering) |
| **Back-Compat Guarantee** | New shapes are additive; existing rect/inset/frame/grid nodes unchanged |
| **Risk / Rollback** | Delete new shape nodes from AST/parser/resolver; existing shapes unaffected |
| **Blocking Dependencies** | `S12_LAYOUT_RESOLUTION`, `S13_COMPOSITIONAL_PML` |
| **Status** | `todo` |
| **Commits** | _(pending)_ |

---

### Stage Execution Status

**Current Stage**: `S5_HINTS_ADAPTER`
**Completed Stages**: S1 (5e79908), S2 (718290d), S3 (1adc2a9), S4 (d84b021)
**Blocked Stages**: S5-S11 (awaiting respective dependencies)
**Deferred Stages**: S11 (PML - Phase 2)

**Progress Tracking**:
- **S1_TAG_SKELETON**: Completed 2025-12-16, commit 5e79908, tag refactor_v2_S1_TAG_SKELETON
- **S2_AST_CORE**: Completed 2025-12-16, commits 8c1102d (initial), 718290d (template fix), tag refactor_v2_S2_AST_CORE
- **S3_AST_EMIT**: Completed 2025-12-16, commit 1adc2a9, tag refactor_v2_S3_AST_EMIT
- **S4_REMOVAL_IR_CORE**: Completed 2025-12-16, commit d84b021, tag refactor_v2_S4_REMOVAL_IR_CORE

---

## Current Status

**Reviewer**: User (Codex review refinements)
**Turn**: 7
**Action**: Refined scope and semantics based on Codex feedback to tighten technical correctness:
1. **RemovalIntent IR strengthened**: Added explicit semantics—z_top/z_bottom depth models, inside/outside/on allowances, tabs/bridges/keepouts/islands constraints, tolerance bands. Clarified RemovalIntent is not an operation label but a normalized material-removal specification. Stated RemovalIntent does not guarantee manufacturability (toolability/collision/physics remain validation layers).
2. **Replaced "lossless round-trip" language**: Changed to "semantic equivalence with canonical re-emission" throughout. Clarified system preserves semantics but not surface formatting, comments, syntactic sugar, or original ordering.
3. **Gated PML as Phase 2**: Marked PML Surface Syntax as later-phase feature (not foundational dependency). LayoutAST, RemovalIntent, JSON schema, CLI introspection take priority. JSON remains primary interface until PML ships.
4. **Clarified "stable child ordering" semantics**: Distinguished order-preserving sequences (semantic) from order-insensitive collections (canonically sorted). Schema must declare semantic ordering; canonicalization must not reorder sequences affecting machining precedence/intent.
5. Updated Canonicalization row, Agent CLI Introspection row, Pipeline Flow Key Properties, and Interactions/Conflicts to reflect refined semantics.

**Turn 8 Addition**: Added staged implementation plan with 11 discrete stages designed for AI-driven execution. Each stage includes explicit scope, deliverables, acceptance tests, back-compat guarantees, and rollback mechanisms. Critical stages (S6, S10) enforce byte-for-byte G-code equivalence with v1. PML deferred to Phase 2 (Stage 11).

**Turn 9 Clarification**: Relaxed equivalence requirements to distinguish adapter validation (byte-identical) from template recovery (semantic/geometry-equivalent). Added **Equivalence Types** section defining three levels: byte-identical (S6 adapter), semantic/geometry-equivalent (S10 ShakerPanel v2), and behavioral/safety-equivalent. Updated Stage 10 acceptance tests to focus on RemovalIntent correctness, SVG verification (design boundary, tool paths, envelopes), safety invariants (safe-Z, depth limits, feed constraints), and geometry verification (panel dimensions, rabbet depths, decorations). This enables improved planners and strategies without coupling to legacy motion quirks while maintaining objective, testable acceptance criteria.

CONSENSUS RESET - Requires Claude/Codex re-review of refined RemovalIntent semantics, LayoutAST ordering guarantees, PML phasing, staged execution plan, and equivalence type clarifications.
