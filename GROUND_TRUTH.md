<!-- spec-style -->
# mill_ui — AI Contract README (Ground Truth)

Document Type: Ground Truth + AI Contract
Authority: This document is authoritative for repository behavior described herein.
As-Of Date: 2026-01-15
Scope: PML → Layout resolution → IR (RemovalIntent) → Planner hints → Pass planning → G-code emission. Includes data models, coordinate systems, validation coverage, and test coverage map.

Specification Rules
	•	Statements containing MUST / MUST NOT / SHOULD / MAY are normative.
	•	If a behavior is not specified, it is not permitted to assume it.
	•	If any requirement is ambiguous, an implementer (human or AI) MUST ask a clarification question before changing code.
	•	Terms defined in Terminology MUST be used consistently. Synonyms are disallowed.

Table of Contents
	1.	Purpose
	2.	Non-Goals
	3.	Terminology
	4.	Canonical Pipeline
	5.	Data Models (Verbatim)
	6.	Planner Hint Schema (Concrete)
	7.	Coordinates, Units, and Conventions
	8.	Validation Coverage
	9.	Duplicate or Legacy Paths
	10.	Test Coverage Map
	11.	Nesting Module
	12.	Extension Points
	13.	Known Gaps and Recommended Actions
	14.	AI Instructions

⸻

1. Purpose

The purpose of mill_ui is to transform PML input into G-code output through a deterministic pipeline of parsing, layout resolution, intermediate representation (IR), planning, and post-processing.

⸻

2. Non-Goals

The system does NOT:
	•	Perform unit conversion internally.
	•	Infer missing geometry or feature parameters.
	•	Provide exact geometric collision detection at the IR level.
	•	Validate feeds/speeds against material/tool compatibility.
	•	Perform fixture/clamp interference analysis beyond explicit keepouts.

⸻

3. Terminology
	•	PML: A plaintext language used to specify layouts and operations.
	•	CompositionalLayoutAST: Hierarchical AST produced by compositional PML parsing.
	•	LayoutAST: Flat AST with absolute coordinates. This is the canonical resolved layout representation.
	•	RemovalIntent: Canonical IR representing what volume to remove independent of toolpath strategy.
	•	Planner Hints: v1-compatible dict structures consumed by the planner pass generator.
	•	Safe Z: Z height used for rapid (G0) moves to avoid collisions with stock.

⸻

4. Canonical Pipeline

The canonical execution path MUST follow these stages in order.

Stage 1: Parse Compositional PML
	•	Entry: parse_compositional_pml(text: str) in pml/compositional_parser.py
	•	Input: PML text string
	•	Output: CompositionalLayoutAST

Stage 2: Resolve Layout
	•	Entry: resolve_layout(comp_ast: CompositionalLayoutAST) in resolution/layout_resolver.py
	•	Input: CompositionalLayoutAST
	•	Output: LayoutAST
	•	Behavior: Applies layout managers and computes absolute positions.

Stage 3: Convert AST → RemovalIntent
	•	Entry: ast_to_removal_intents(ast: LayoutAST) in adapters/ast_to_removal.py
	•	Input: LayoutAST
	•	Output: list[RemovalIntent]
	•	Behavior: For each Item, converts through item_to_removal_intent() and feature-specific converters.

Stage 4: Convert RemovalIntent → Planner Hints
	•	Entry: removal_intents_to_v1_hints(intents, kerf_width_mm, min_channel_width_mm) in adapters/removal_to_planner.py
	•	Input: list[RemovalIntent], kerf_width_mm, min_channel_width_mm
	•	Output: hints dict with keys: profiles, pockets, holes, engraves, kerf_width_mm, min_channel_width_mm, and units.

Stage 5: Plan Passes
	•	Entry: plan_passes(hints, config, tool_db, material, machine, stock, safe_z, prime_spindle, profile_opts) in cam/planner/passes/__init__.py
	•	Output: (pass_records, summary)
	•	Behavior: Plans pockets/holes/engraves then processes profiles.

Stage 6: Generate G-code
	•	Entry: write_gcode(moves, unit, prec, safe_z, header, footer) in cam/post/gcode.py
	•	Output: G-code string
	•	Behavior: Delegates to native_core.post_gcode().

⸻

5. Data Models (Verbatim)

5.1 LayoutAST Core Dataclasses (layout_ast/layout.py)

Sheet
	•	Fields: width_mm, height_mm, thickness_mm

Placement
	•	Fields: center_xy_mm: tuple[float, float]

Geometry
	•	Fields: data: dict[str, Any]
	•	Rule: No separate classes exist for Rect/Circle/etc. Shape identity is Item.type. Parameters live in Geometry.data.

Feature
	•	Fields: type: str, depth: str | float, side: str | None, depth_mm: float | None

Item
	•	Fields include: kind, type, geometry, placement, feature, params, shape_id, id

LayoutAST
	•	Fields: sheet, items, plus v1 config compatibility fields (project, kerf_width_mm, cam, layout, config)

5.2 RemovalIntent IR Dataclasses (ir/removal_intent.py)

Bounds2D
	•	Fields: x_min, x_max, y_min, y_max
	•	Validation: x_max >= x_min and y_max >= y_min MUST hold.

RemovalIntent
	•	Fields: region_id, bounds, z_top, z_bottom, allowance, constraints, metadata
	•	Validation: z_bottom <= z_top MUST hold.

⸻

6. Planner Hint Schema (Concrete)

Planner hints MUST follow this top-level schema:

{
    "units": "mm",
    "kerf_width_mm": float,
    "min_channel_width_mm": float,
    "profiles": [<profile hint dict>],
    "pockets": [<pocket hint dict>],
    "holes": [<hole hint dict>],
    "engraves": [<engrave hint dict>]
}

Profile hint (Rect outside profile example)

Required keys:
	•	id, shape, geometry, center_xy_mm, depth_mm, side

Optional keys:
	•	tabs

Pocket hint (Rect pocket example)

Required keys:
	•	id, shape, geometry, center_xy_mm, depth_mm

Optional keys:
	•	start_depth_mm (only if z_top != 0)

Planner consumption points
	•	Profiles: reads keys geometry, center_xy_mm, depth_mm, side, tabs
	•	Pockets: reads keys shape, geometry, depth_mm, start_depth_mm
	•	Holes: reads keys geometry.diameter_mm, center_xy_mm, depth_mm

⸻

7. Coordinates, Units, and Conventions

7.1 Units
	•	All internal layers MUST use millimeters.
	•	No internal unit conversions are permitted.
	•	G-code output MAY be configured as mm or inch for output formatting only.

7.2 XY Coordinates
	•	Placement.center_xy_mm uses center-based coordinates.
	•	Stock origin is lower-left (per stock model origin='lower_left_top').
	•	Compositional AST uses normalized coordinates (0.0–1.0) relative to parent region and MUST be resolved to absolute coordinates during layout resolution.

7.3 Z Convention
	•	Positive Z is away from the material.
	•	Negative Z is into the material.
	•	z_top is typically 0.0 at the stock surface.
	•	z_bottom MUST be negative for material removal.

⸻

8. Validation Coverage

8.1 IR-Level Validation (Implemented)
	•	Overlap checking uses 3D bounding-box intersection only.
	•	Depth feasibility checks z_top >= z_bottom and warns on depth vs thickness.
	•	Toolability checks feature size vs tool diameter when tools are provided.

8.2 IR-Level Validation (Not Implemented)

The system MUST NOT claim these validations exist at IR level:
	•	Exact geometry intersection testing
	•	Pocket-corner reachability vs tool diameter
	•	Stepdown suitability vs material/tool
	•	Feed/speed validation
	•	Fixture/clamp interference beyond keepouts
	•	Tab placement feasibility
	•	Toolpath continuity optimization
	•	Exact kerf compensation validation

8.3 Later Validation

Planner/backend performs tool selection and pass parameter calculation.

⸻

9. Duplicate or Legacy Paths
	•	adapters/ast_to_removal.py is the canonical AST→IR adapter.
	•	adapters/hints_to_removal.py contains converters used both by:
	•	canonical path (via intermediate hint dict), and
	•	legacy v1 hint workflows.

This duplication is intentional and supports incremental migration.

⸻

10. Test Coverage Map

The pipeline stages have the following coverage:
	•	parse_compositional_pml() is well tested.
	•	resolve_layout() is well tested.
	•	ast_to_removal_intents() has zero direct tests.
	•	item_to_removal_intent() is tested.
	•	removal_intents_to_v1_hints() is well tested.
	•	IR validation functions are tested.
	•	plan_passes() is tested.
	•	write_gcode() is tested.

Broken Tests
	•	tests/test_cli_dump.py imports cli/introspect.py, which is missing.
	•	These tests will fail on import until the module exists or imports are corrected.

⸻

11. Nesting Module

The nesting module performs bin packing and produces LayoutAST outputs that feed the same canonical pipeline.
	•	Parse .nest via parse_nest_pml(source: str) → NestJob
	•	Convert via nest_job_to_api_params(job: NestJob) → params
	•	Execute via nest_and_generate(**params) → output layouts
	•	Each LayoutAST MUST be processed through: LayoutAST → RemovalIntent → Planner Hints → CAM → G-code

⸻

12. Extension Points

Implementers MAY extend the system only through the following verified points:
	1.	Add new shape: extend _item_geometry_to_bounds() in adapters/hints_to_removal.py
	2.	Add new feature: update Feature.type usage and implement converter in adapters/hints_to_removal.py
	3.	Add new template: implement expand_to_ast() and register in templates/__init__.py
	4.	Add IR validation: add new function in validation/removal_checks.py
	5.	Add planner strategy: implement under cam/planner/passes/

⸻

13. Known Gaps and Recommended Actions

Known gaps:
	•	No geometry-level collision detection at IR level.
	•	Missing cli/introspect.py referenced by tests.
	•	CAD export imports are broken in cad/export/step.py and cad/export/svg.py.
	•	ast_to_removal_intents() has no direct tests.

Recommended actions:
	1.	Implement cli/introspect.py or remove test dependency.
	2.	Add direct tests for ast_to_removal_intents().
	3.	Fix CAD export import errors.
	4.	Extend validation beyond bounding boxes if required.

⸻

14. AI Instructions

When modifying this repository:
	•	Treat this document as authoritative for described behaviors.
	•	Preserve all stated invariants (units, coordinate conventions, IR semantics).
	•	Do not remove v1 hint compatibility unless the planner interface changes.
	•	Do not infer unspecified behavior.
	•	If a change affects the canonical pipeline stages, update this document in the same commit.

