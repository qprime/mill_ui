# LLM Documentation Update Guide

When code changes, update the corresponding documentation to reflect current reality.

---

## Tier 1: Core Architecture

| Document | Update When | Instructions |
|----------|-------------|--------------|
| **GROUND_TRUTH.md** | Data models, pipeline, adapters, validation change | Review against current source code and update to reflect actual implementation. Extract dataclass definitions verbatim. Verify all file:line references are accurate. Document what IS, not what should be. |
| **README.md** | User-facing features, quick start examples, architecture change | Review examples - ensure they parse and run. Update pipeline diagram if stages changed. Keep user-focused and concise. Test all code blocks. |

---

## Tier 2: Technical Specifications

| Document | Update When | Instructions |
|----------|-------------|--------------|
| **pml/syntax_spec.md** | Parser changes, new shapes/features added | Review parser source. Document grammar as it exists. Ensure all examples parse correctly. Update syntax for any new constructs. |
| **docs/WORKFLOW.md** | Pipeline stages, adapters, export formats change | Review complete data flow. Update ASCII diagram to match current stages. Mark broken exports honestly. Include actual function names. |
| **docs/compositional_layout.md** | Layout managers, component system, resolution changes | Review compositional AST and resolver. Document how each layout manager transforms regions. Update examples to match current API. |
| **docs/shape_primitives.md** | New shapes, geometry parameters, bounds calculation changes | Review all shape types in codebase. Document geometry parameters and bounds calculations. Ensure examples work. |
| **docs/layout_primitives.md** | Layout managers, parameters, resolution logic changes | Review layout manager implementations. Document region transformations. Show formulas that match actual code. |
| **docs/keepout_islands.md** | Constraint types, dataclass structure changes | Review constraint dataclasses in `ir/removal_intent.py`. Document current structure and planner support status. |
| **docs/edge_treatment.md** | EdgeTreatment changes, new treatment types | Review `EdgeTreatment` dataclass. Document available types and parameters. Note implementation status. |
| **docs/studio_mode_geometry.md** | Spline/polyline changes, curve types, sampling | Review spline and polyline implementations. Document coordinate systems and sampling. Update examples. |

---

## How to Use

1. **Identify changed files** - Note which source files you modified
2. **Find affected docs** - Check "Update When" column
3. **Run the update** - Give LLM the doc + prompt: "Review this document against current source code and update in the spirit of the document"
4. **Verify** - Test examples, check references
5. **Commit together** - Code + docs in same commit

---

**Last Updated:** 2025-12-19
