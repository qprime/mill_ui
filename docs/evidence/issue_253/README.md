# Issue #253: explicit cutting presets and source builds

All 33 canonical recipes were regenerated with `cli.recipes --regen`, reviewed,
tracked, and checked with `cli.recipes`. The selected recipe machine is
`machines/defaults.yml:recipe_machine` → `altmill_4x4` → `altmill_production`.

[timings.csv](timings.csv) compares the original and retuned historical estimates
with the current explicit preset. [comparison.json](comparison.json) records
per-recipe estimates, sheet counts and the complete final-artifact inventory
review. [validation.json](validation.json) records the extended artifact checks.
These files are evidence only and never compilation inputs.

| Configuration | Combined estimated minutes |
|---|---:|
| Original configuration after #248 | 3,790.0 |
| Retune checkpoint | 1,189.1 |
| Explicit AltMill production preset | 1,121.3 |

Every recipe retains its sheet count and nominal authored part dimensions.
Historical files under `../altmill_recipe_tooling/` were preserved unchanged.
The historical code baseline is #248's `b4943220`; the recorded comparison names
`c4e92a37`, the following documentation-only evidence-removal commit. Neither
baseline was replaced with this implementation.

The new total is 67.8 minutes below the retune estimate. Selecting the production
machine now also applies its configured 3mm retract height; the checkpoint recipe
route used the generic 6mm retract. This particularly changes jobs containing many
short engraving strokes: layout board 156.7 → 115.8 minutes and shop ruler
61.0 → 35.1. Explicit approved detail/hole tools and cutter reach checks change
some jobs in the other direction: cubby organizer 118.4 → 125.8, hinge-cup door
18.2 → 20.6. Bookcase is 34.8 → 34.3 and production sheet 30.7 → 32.7.
Main profile and PCD cutting parameters retain the retune's modeled assumptions.
The shared-profile alternating-depth traversal from #248 is unchanged.
Profile reach is resolved before packing: a 30mm through-cut selects the approved
longer-reach 12.7mm profile alternative, while a binding short-cutter override
fails before packing. Unused profile roles are not required for pocket-only jobs.
These are modeled estimates, not measured machine performance or isolated
measurements of the effect of cutter diameter.

The engraving role explicitly retains the existing 1mm engraving bit. The SVG
artwork recipe exposed insufficient clearance with a 1.6mm candidate; its margin
and nominal artwork dimensions were preserved. Dogbone detail uses the existing
longer-reach 1/8-inch plunge tool rather than exceeding the short cutter's flutes.
No new confirmed V-bit model, spindle power, or Genmitsu cutting parameters were
invented. Genmitsu has an independent, unsupported-until-configured preset.

Verification completed:

- 4,048 general Python tests and 3 explicit shipped-configuration checks pass
  separately through `tools/run_tests.py` (see the isolation addendum below).
- Ruff lint/format and mypy pass through the repository wrappers.
- All 33 recipes regenerate and pass the recipe gate; all generated output files
  are tracked. Final JSON parses, SVG XML parses, and NC programs have complete
  endings. Reports contain no compilation fingerprints or library snapshots.
- Extended validation resolves current authored source/configuration. Only the
  previously recorded `raised_panel_doors` and `production_sheet` checks fail:
  raised-panel item counts; production waste counts/profile matching and the
  checker's safe-Z-inclusive stepdown diagnostics. The numeric diagnostics differ
  with current passes. These failures were recorded rather than waived.
- Nest source validation now checks its actual parts. Its rounded-profile SVG
  paths exposed a checker gap: path metrics lacked dimensions and treated arc
  parameters as coordinates. Reusing the existing SVG path parser fixes that
  check, with targeted coverage; the nesting recipe now passes.
- The duplicate-code audit reports existing matches outside the changed tool
  selection/compilation code. No duplication suppression was added.

Cleanup audit:

- `cam/compilation.py` retains per-invocation resolution and clearance, with no
  serialization, fingerprints, saved-context readers or replay parameters.
- `cam/pipeline.py` accepts the in-memory handoff and emits selected effective
  settings, without saved-state reads or full-library report output.
- `cli.mill` rejects legacy resolved-layout JSON with an original-source rebuild
  instruction. `cli.nest` packs and machines source in one invocation using the
  shared final-artifact writer.
- Resolved layout JSON readers/writers, the AST lifter, flattened nesting exports,
  `convert_layout --for-machining`, and `parse_compositional_pml --resolve` were
  removed. Source parsing/validation/formatting remains available.
- Recipe and explicit-source validation do not read machining settings from
  metrics, manifests or summaries. Custom configuration is an explicit input.
- Remaining domain/nesting-result JSON methods are data conversion utilities;
  application machining entry points cannot consume them as saved layouts.
  RemovalIntent/planner diagnostic conversions have no saved-job reader.
- Tool/feed parsing, font and asset caches remain process-local. No persistent
  replacement checkpoint/cache format was introduced.

## Addendum: test isolation (2026-11-14)

General tests now construct fresh synthetic machine, cutter, material and
cutting-preset files for each machining test. They neither read nor copy the
production configuration. Each test selects a new configuration root and clears
process-local tool/feed caches. Configuration inputs live separately from output
directories so output cleanup cannot remove them.

`MILL_UI_MACHINES_DIR` explicitly selects the configuration root. Missing inputs
fail without a production fallback. CLI/compiler imports no longer resolve the
production defaults eagerly. Ordinary CLI subprocess tests inherit the test
configuration. Isolation uses explicit inputs and no fallback; no audit hooks or
custom subprocess launcher are needed.

Actual shipped-configuration checks are marked and run separately. Canonical
recipes continue to validate the actual production configuration.

Final verification:

- `tools/run_tests.py -q --maxfail 5`: 4,037 passed; 3 shipped checks deselected.
- `tools/run_tests.py -m shipped_configuration -q`: 3 passed; 4,037 deselected.
- Ruff lint/format and mypy: pass.
- `python -m cli.recipes`: 33 recipes checked, zero failures. The isolation
  changes leave the canonical production artifacts and timing evidence unchanged.
- Regression coverage checks missing configuration in process and in ordinary
  CLI subprocesses, configuration-root changes, and imports/help without any
  machine configuration.

The issue's earlier extended-validator limitations remain recorded above; test
isolation does not change those artifact checks.

## Review follow-up

The review of `5adc9422` identified 13 findings, addressed in the follow-up:

- Nesting preserves its output directory, source and unrelated files. Existing
  packing overlap/bounds validation runs before layout generation and machining.
- Radial pocket and Phyllotaxis hole/pocket element tool overrides survive the
  parser, source formatter, resolution and RemovalIntent conversion. Unknown
  explicit cutters fail rather than silently selecting a preset default.
- Reports identify an explicitly supplied preset file. Recipe validation uses
  the recipe-machine default, while honoring an explicit machine selection.
- Legacy endmill/feed inputs with multiple cutters require a named role or
  operation tool; file order cannot choose one. Profile, V-angle and pocket-error
  checks use the relevant role configuration instead of the specialty table.
- Compilation context is passed alongside resolved layouts through existing
  build functions. LayoutAST has no CAM context or dependency on CAM types.
- Unused nesting CLI switches, obsolete validation parameters, the unreachable
  safe-Z fallback and unused material-listing helper were removed. Tool lookup
  diagnostics retain the available candidates, and source/configuration docs
  describe the supported workflow.

The canonical 33-recipe gate passes without changing production artifacts or
timing estimates. Targeted regressions use the existing synthetic configuration
fixtures and ordinary CLI subprocesses.

Follow-up verification: 4,048 general tests and 3 separate shipped-configuration
checks pass; Ruff lint/format and mypy pass. The duplication audit retains only
the existing matches, with no new duplicate-code pairs. The extended-validator
limitations recorded above remain unchanged.
