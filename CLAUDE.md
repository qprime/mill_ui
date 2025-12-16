# CLAUDE.md - Mill UI Skill

## Project Context

Mill UI is a compositional CAD/CAM system designed for AI agent consumption. It generates CNC toolpaths and exports from declarative JSON layouts using parameterizable template components.

**Owner Path**: `skills/mill_ui/`
**Primary User**: AI agents (Claude, Codex) generating manufacturing layouts programmatically
**Architecture**: Monolithic Python package with optional native C++ acceleration

## Mental Model

Think of mill_ui as **React for physical objects**:
- **Templates** (Shaker, FrameInsetClamp, ClampBar) = React components
- **Parameters** (width_mm, depth_mm, border config) = props
- **Primitives** (rectangle, circle) = HTML div/span
- **Layouts** (grid placement, anchor points) = flexbox/grid
- **Features** (profile, pocket, hole) = semantic attributes/event handlers
- **Output** = G-code instead of HTML

The system transforms declarative specifications into machine-executable toolpaths through a deterministic pipeline.

## Current Architecture

**Pipeline**: JSON Layout → Config Resolution → Template Expansion → CAM Hints → Pass Planning → G-code Generation

**Key Components**:
- `apps/compose_cam.py` - CLI orchestrator (804 lines, needs refactoring)
- `compositions/` - Template registry with decorator-based registration
- `cam/planner/` - Toolpath planning with native backend acceleration
- `cad/export/` - SVG, STL, STEP exporters
- `api/` - Public surface re-exports

**Data Flow**: File-based I/O, no persistence layer, deterministic execution enforced via `PYTHONHASHSEED=0`

## Active Work

**Current Initiative**: AI-first refactoring with staged execution model

See [mill_ui_refactor.md](mill_ui_refactor.md) for comprehensive architectural changes. Implementation follows an 11-stage plan with explicit acceptance criteria and rollback mechanisms.

**Key Changes**:
1. RemovalIntent IR as canonical material removal representation
2. Canonical LayoutAST as single source of truth (JSON/PML → LayoutAST convergence)
3. Machine-readable template metadata for agent discovery
4. Structured validation with field-level errors
5. Agent CLI introspection (dump-ast, dump-removal-intent, convert-layout)

**Phase 2 Features** (deferred): PML surface syntax for human readability

## Foundational Intermediate Representations

### RemovalIntent IR
The canonical representation for material removal operations. When working with CAM operations:
- **RemovalIntent** captures *what* volume to remove (boundaries, z_top/z_bottom depths, inside/outside/on allowances, tabs/bridges/keepouts/islands)
- **Legacy operations** (profile, pocket, hole, engrave) are adapters that produce RemovalIntent
- **Planners** consume RemovalIntent to generate toolpaths
- Think: "declarative removal specification" vs "imperative toolpath commands"

### Canonical Layout AST
The single source of truth for layout definitions:
- Both JSON and PML (Phase 2) compile into LayoutAST
- System guarantees **semantic equivalence with canonical re-emission** (not formatting preservation)
- Order-preserving for sequences, canonically sorted for collections
- Enables introspection, validation, and format conversion

## Equivalence Philosophy for v2 Templates

**Byte-for-byte G-code equivalence with legacy output is NOT required** for v2 templates (e.g., ShakerPanel v2).

The goal is **semantic/geometric equivalence**:
- Same finished panel geometry (outer dimensions, aperture sizes, rabbet depths)
- Same decorative intent (border patterns, relief features)
- Toolpaths may differ in motion planning, ordering, or efficiency
- New planners and strategies are encouraged

**Acceptance is based on**:
- **RemovalIntent correctness**: Expected region count/types from template expansion
- **SVG verification**: Design boundary, tool centerlines, tool radius envelopes; no overlap; within stock bounds
- **Safety invariants**: Respects safe-Z, depth limits, feeds/spindle constraints from tool database
- **Geometry verification**: Finished dimensions match spec; features present and correct depths

This philosophy enables improved planners without coupling to legacy motion quirks while keeping acceptance criteria objective and testable.

## Agent Collaboration Protocol

This codebase is collaboratively maintained by multiple AI agents (Claude, Codex). When working on mill_ui:

### Before Making Changes
1. **Read [mill_ui_refactor.md](mill_ui_refactor.md)** to understand planned architectural direction
2. **Check consensus status** - only implement changes with ☑ from both reviewers
3. **Review [README.md](README.md)** for current API surface and invariants
4. **Verify test coverage** - run `python run.py mill_ui_tests` before major changes

### When Adding Templates
- Use `@register_template(name)` decorator pattern
- Implement `TemplateBase.expand(params, thickness_mm)` contract
- Return list of shape dictionaries with `kind`, `type`, `geometry`, `placement`, `feature`
- Add example usage to `examples/agent_generated/` when complete
- Document parameter schema in template docstring until metadata system ships

### When Modifying Core Architecture
- Maintain backward compatibility with existing JSON layouts
- Preserve deterministic execution guarantees
- Keep native backends optional with graceful degradation
- Update both README.md and relevant refactor document sections
- Add regression tests for changed behavior
- **Understand equivalence requirements** for the work:
  - **Byte-identical**: Adapter stages (S6) require exact G-code match for correctness validation
  - **Semantic/geometry-equivalent**: Template stages (S10) require same finished geometry and decorative intent; toolpaths may differ in motion planning, ordering, or efficiency
  - **Behavioral/safety-equivalent**: Safe toolpaths respecting bounds, depths, feeds/spindle constraints

### Code Style
- Use dataclasses for structured data over dicts where possible (migration in progress)
- Prefer pure functions returning immutable results
- Keep helpers in `compositions/base.py` for consistency across templates
- All dimensions in millimeters, no mixed units
- Configuration precedence: CLI > env > file > defaults

## Key Invariants

**DO NOT BREAK**:
- All linear dimensions are millimeters
- Deterministic output (seeded random, sorted dicts)
- Native backends are optional (check via `get_capabilities()`)
- Templates must be idempotent given same params
- G-code generation fails fast on missing tools
- File paths use absolute references from cwd

**PRESERVE**:
- Single-process execution model (no microservices)
- File-based I/O (no database layer)
- CLI and programmatic API contracts
- Existing test suite passes
- RemovalIntent IR as canonical material removal representation
- Semantic equivalence guarantees (ordering, values, operations)
- Deterministic G-code output for regression testing

## Common Pitfalls

1. **Don't add implicit state** - Pass configuration explicitly through pipeline
2. **Don't mutate shared structures** - Copy before modifying (see `_offset_items` pattern)
3. **Don't assume native backend availability** - Always check capabilities first
4. **Don't break template ID threading** - IDs must be unique per shape for seam merging
5. **Don't add time estimates** - Focus on actionable steps, let user decide scheduling
6. **Don't create new files unnecessarily** - Prefer editing existing over creating new
7. **Don't assume formatting preservation** - System guarantees semantic equivalence via canonical re-emission, not surface syntax preservation
8. **Don't bypass RemovalIntent IR** - New CAM operations must produce RemovalIntent, not raw hints
9. **Don't confuse equivalence types** - Adapters require byte-identical G-code (S6); templates require semantic/geometry equivalence (S10)

## Extension Points

**To add a new template**:
1. Create file under `compositions/{category}/`
2. Subclass `TemplateBase`, implement `expand()`
3. Use `@register_template("TemplateName")` decorator
4. Import in `compositions/__init__.py` (will be auto-discovery in refactor)
5. Add test in `tests/unit/`

**To add a CAM operation**:
1. Create operation in `cam/ops/`
2. Export through `api/cam.py`
3. Add planner logic in `cam/planner/passes/`
4. Update native backend if performance-critical

**To add an export format**:
1. Create exporter in `cad/export/`
2. Export through `api/cad.py`
3. Add CLI flag in `compose_cam.py`
4. Document in README section 4

## Testing

**Run all tests**: `python run.py mill_ui_tests`
**Run specific test**: `python -m pytest tests/unit/test_gcode.py -v`
**Generate code context**: `python -m tools.context_builder skills.mill_ui --output skills/mill_ui/code_context.txt`

Tests use real file I/O in temp directories, no mocking. Deterministic seeding prevents flaky tests.

## Reading Order for New Agents

Start here when familiarizing with codebase:

1. [README.md](README.md) - Public API and usage patterns
2. [mill_ui_refactor.md](mill_ui_refactor.md) - Architectural direction and staged execution plan
3. `apps/compose_cam.py` - End-to-end orchestration flow
4. `compositions/base.py` - Template framework design
5. `api/cam.py` - CAM operations public surface
6. `cam/planner/passes/__init__.py` - Pass planning pipeline
7. `v2/ir/removal_intent.py` - Canonical material removal IR (post-S4 implementation)
8. Example templates: `compositions/panels/frame_inset_clamp.py`, `compositions/cabinets/shaker.py`

## Questions & Decisions

When uncertain about architectural decisions:

**For small changes** - Follow existing patterns, maintain consistency
**For medium changes** - Propose in [mill_ui_refactor.md](mill_ui_refactor.md) review table
**For large changes** - Discuss with user before implementing

**Agent coordination** - Use mill_ui_refactor.md as shared design document with explicit consensus tracking

## Resources

- **Tool Database**: `cam/tools/tool_db.json`
- **Example Layouts**: `memories/cam_projects/sheet_layouts/*/input/layout.json`
- **Layout Schema**: `docs/schemas/layout.schema.json` (outdated, needs refresh)
- **Native Backends**: Optional, built via scikit-build-core + CMake + pybind11

---

**Last Updated**: 2025-12-16
**Active Reviewers**: Claude, Codex
**Status**: Architecture refactor planning phase
