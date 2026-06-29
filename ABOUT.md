# About mill_ui

## Project Context

mill_ui was built solo over roughly three months as an AI-augmented engineering project. It serves a dual purpose: a production CAM tool used by TenneCNC LLC for real CNC work, and a worked demonstration of structured AI-collaborative software development.

The system is in active use. Recipes in `docs/recipes/` are not toy examples — they correspond to real parts that have been cut on a real CNC machine. The validation discipline (golden metrics, IR-level checks, recipe regression tests) exists because the cost of a bad G-code file is wasted material and machine time, not a failed unit test.

## Why This Architecture

Most CAM software is procedural: read input, generate paths, write output. mill_ui uses compiler-construction discipline — explicit intermediate representations, validation at each layer, a reverse path from layout back to source — because that architecture is what makes the system *safe to drive with an AI assistant*.

When an AI generates PML, the human reviewer cannot verify the resulting toolpaths line by line. They can only verify the *design* — the SVG blueprint, the shape of the part, the joinery. The compiler pipeline guarantees that if the design is correct, the toolpath is correct, because every layer between PML and G-code is validated against the layer above it. That guarantee is what lets a human collaborate with an AI on real manufacturing work without losing the trust boundary.

## Development Methodology

The codebase enforces design discipline through documents and tooling rather than per-line code review:

- **Invariants** ([docs/invariants/](docs/invariants/)) — Subsystem-level axioms that any change must respect. Loaded via the `/check-invariants` skill before edits.
- **Skills** ([.claude/commands/](.claude/commands/)) — Encoded workflows for review, debugging, extension, snapshot regeneration, and architectural audit. The skills define *how* the system is changed, not just *what*.
- **Recipe tests** — 70+ worked examples with golden metrics. Regressions surface as concrete diffs against known-good output, not as unit-test failures with vague messages.
- **PML-first principle** — Every machining capability must be expressible declaratively. Python-level generators without PML syntax are considered incomplete.

This approach scales human attention to the architectural and invariant level while AI handles the implementation level. The result is a codebase that demonstrates what AI-augmented engineering produces when architectural judgment and invariant discipline are treated as deliberate human contributions — every design decision, invariant, and validation rule in this system reflects that.

## Scope

What mill_ui does today:

- Single-sheet panel layouts via PML
- Multi-part nesting via `.nest.yml` (guillotine + maxrects)
- Full assembly system (boxes, carcasses, cubbies, beams) with interface-resolved joinery
- Multi-sheet partitioning when assemblies exceed a single sheet
- Nine machining feature types: profile (with tabs), pocket, surface facing, hole, engrave, bevel, chamfer, roundover, wave
- SVG and PDF blueprint export with dimensions
- Machine configuration (endmill library, feed rates, per-machine profiles)
- Optional native C++ backend for performance on large jobs

What it deliberately doesn't do:

- 3D toolpaths (the system is 2.5D)
- GUI editing (the input is declarative; visualization is read-only SVG)
- Adaptive clearing or trochoidal milling (the planner is geometric, not feed-optimized)

## Author

Stephen Quinlan — built mill_ui to run TenneCNC LLC's CNC operations and to explore what structured AI-collaborative development looks like when the goal is production-grade code, not demos.

Available for consulting on applied AI in industrial systems and AI-augmented engineering practice. See the repository owner profile for contact.
