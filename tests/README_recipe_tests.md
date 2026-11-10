# Recipe Output Tests

Every recipe with a `*.pml.yml` source has its outputs committed under `docs/recipes/<name>/output/`. The recipe gate checks that those committed files are exactly what current code generates.

## The rule

For every recipe, `output/` holds exactly the files `cam.pipeline.write_run_outputs` produces from current code, byte for byte, and git tracks all of them.

When a change alters recipe output, regenerate every recipe, review every changed file, and commit all of them with the change that caused them. An unintended change is a regression to fix in code. Outputs are never reverted to make the gate pass.

## Commands

```bash
# Gate: every output file matches current code, and no output file is untracked
python -m tests.test_recipes

# Regenerate every recipe's output/
python -m tests.test_recipes --regen_recipes

# The same gate inside the full suite
.venv/bin/python tools/run_tests.py tests/test_recipes.py
```

The gate also runs as the `recipe-outputs` pre-commit hook. Pre-commit stashes unstaged changes before running hooks, so the hook checks the files being committed. A regenerated output left unstaged fails the commit.

## What the gate reports

Each recipe is written into a temporary directory and compared with its `output/`:

| Message | Meaning |
|---|---|
| `Missing generated file: <name>` | Current code writes a file that `output/` does not have |
| `File no longer generated: <name>` | `output/` has a file current code no longer writes |
| `<name> differs: N lines changed` | The committed file's content differs from what current code writes |
| `Untracked recipe output: <path>` | A file under some `output/` is not tracked by git |

## Adding a recipe

1. Create `docs/recipes/NN_name/` with `README.md` and `example.pml.yml`.
2. Run `python -m tests.test_recipes --regen_recipes`.
3. Stage every file in the new `output/` and commit them with the recipe.

## Output structure

```
docs/recipes/14_corner_cleanup_multi_tool/
├── example.pml.yml
└── output/
    ├── 14_corner_cleanup_multi_tool.svg    # Blueprint
    ├── corner_cleanup-3.17mm.nc            # G-code per tool
    ├── pocket-12.70mm.nc
    ├── profile-3.17mm.nc
    ├── machining_summary.json              # Per-file tools, feeds, depths, runtime
    └── metrics.json                        # Complexity, fidelity, errors, warnings
```

A recipe with a back face also writes `<name>.back.svg`. A multi-sheet recipe prefixes each G-code file with `sheet_N.`, writes one SVG per sheet, and adds `manifest.json`.

### Metrics schema

```json
{
  "constraint_audit": {},
  "complexity": {
    "total_moves": 3366,
    "rapid_moves": 0,
    "cut_moves": 3366,
    "rapid_ratio": 0.0
  },
  "fidelity": {
    "tool_changes": 3,
    "passes": [{"name": "pocket", "tool_diameter_mm": 9.525, "move_count": 1314}]
  },
  "output_size": {
    "total_bytes": 75532,
    "total_lines": 3368,
    "files": {"pocket-9.53mm": {"bytes": 23734, "lines": 1320}}
  },
  "errors": [],
  "warnings": [],
  "build": {"kerf_mm": 3.175, "theme": "dark", "y_origin": "back", "source": "example.pml.yml"}
}
```

`errors` lists design errors; a non-empty list makes `cli.mill` exit 3. Pipeline timing is stripped before the file is written. Recipe outputs carry no commit hash: the commit that holds them is their provenance. `--project` and `--input` runs add `"provenance": {"mill_ui": "<short hash>"}`.

A run with more than one sheet (a multi-sheet layout, or several input files) writes one `metrics.json` with a `sheets` list. Each entry holds that sheet's metrics, `errors` and `warnings`, plus `source`, `sheet_index` and `job_name`. The top-level `errors` and `warnings` collect every sheet's messages, prefixed `sheet N: ` (or `<source> sheet N: ` when the run has several input files):

```json
{
  "total_sheets": 3,
  "sheets": [{"source": "example.pml.yml", "sheet_index": 1, "job_name": "74_multi_sheet_assembly_sheet_1", "...": "...", "errors": [], "warnings": []}],
  "errors": [],
  "warnings": [],
  "build": {...}
}
```

`cam.pipeline.write_run_outputs` is the single writer for `.nc`, `.svg`, `metrics.json`, `machining_summary.json` and `manifest.json` (runs with more than one sheet); `cli.mill` and `tests.test_recipes --regen_recipes` both call it with the same build parameters, so either one refreshes a recipe's outputs. A run with several input files prefixes each `.nc` with its input stem (`door.pml.profile-6.35mm.nc`). The writer raises `GcodeNameCollisionError` if two G-code files would share a name.

## Golden metrics

Golden metrics in `tests/golden/` are a separate baseline, built from the committed outputs. When outputs change on purpose, update the goldens for the changed recipes with `python -m cli.generate_golden --recipe docs/recipes/<name> --update`, or all of them with `/snapshot-recipes`.

## Scope

The gate covers recipes with a `*.pml.yml` source. Nest recipes (`*.nest.yml`) are run by `tests/test_nesting_recipes.py`, which does not compare outputs.
