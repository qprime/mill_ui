# Recipe Outputs

A recipe is a folder `docs/recipes/<category>/<recipe>/` that directly holds at least one input file (`*.pml.yml` or `*.nest.yml`). Its category must be listed in `docs/recipes/catalog.yml`, and its folder name must be unique across all categories. `validation/recipes.py` finds recipes; every recipe tool uses it.

A recipe with PML sources commits its outputs under `<recipe>/output/`. Nest recipes commit no `output/`. The recipe gate checks that the committed outputs, the recipe index and the feature guide are exactly what current code generates.

## The rule

For every recipe, `output/` holds exactly the files `cam.pipeline.write_run_outputs` produces from current code, byte for byte, and git tracks all of them. The same holds for the generated documents: `docs/recipes/README.md`, `docs/recipes/<category>/README.md` (for categories with recipes) and `docs/feature_guide.md`.

When a change alters recipe output, regenerate every recipe, review every changed file, and commit all of them with the change that caused them. An unintended change is a regression to fix in code. Outputs are never reverted to make the gate pass.

## Commands

```bash
# Gate: outputs and generated documents match current code; nothing generated is untracked
python -m cli.recipes

# Regenerate every recipe's output/ and the generated documents
python -m cli.recipes --regen
```

The gate is not part of the test suite: tests never read `docs/recipes/`. It runs `cli.mill`'s recipe code (`cli.mill.write_recipe_outputs`) on each recipe, so `cli.mill --recipe` and the gate write identical files. The gate also runs as the `recipe-outputs` pre-commit hook. Pre-commit stashes unstaged changes before running hooks, so the hook checks the files being committed. A regenerated file left unstaged fails the commit.

## What the gate reports

Each PML recipe is written into a temporary directory and compared with its `output/`:

| Message | Meaning |
|---|---|
| `Missing generated file: <name>` | Current code writes a file that `output/` does not have |
| `File no longer generated: <name>` | `output/` has a file current code no longer writes |
| `<name> differs: N lines changed` | The committed file's content differs from what current code writes |
| `Untracked recipe file: <path>` | A file under some `output/`, or a generated document, is not tracked by git |
| `Generated document is missing / out of date / no longer generated` | Run `python -m cli.recipes --regen` |
| `no README.md`, `README.md has no ...` | The README needs a `# ` title, a `**Demonstrates:**` line, and (for PML recipes) an image from its own `output/` that exists |
| `Misplaced input file: <path>` | An input file that is not directly in a recipe folder (or in its `output/`) |
| `category '<name>' is not listed in catalog.yml` | Add the category to `catalog.yml` |
| `... does not fit altmill_4x4: ...` | A resolved PML sheet, or a nest job's sheet, minus its margin exceeds the Altmill envelope |
| `capability '<name>' names recipe '<name>', which does not exist` | A `{recipes: [...]}` rule in `catalog.yml` is stale |

Nest recipes are run through `cli.nest.nest_job`; the gate fails one that produces no sheets or uses under 30% of the sheet area.

## Adding a recipe

1. Create `docs/recipes/<category>/<recipe>/` with `<recipe>.pml.yml` (or several input files) and a `README.md` in this form:

   ```markdown
   # Shaker door

   ![Blueprint](output/shaker_door.svg)

   **Demonstrates:** One sentence.

   ## What gets cut
   Sheet, parts, features with depths, tools.

   ## Run
   `python -m cli.mill --recipe docs/recipes/doors/shaker_door`

   ## Outputs
   The files in `output/`.
   ```

2. If the recipe shows a capability its PML does not spell out (multi-sheet partitioning, splicing, a joinery default), add `{recipes: [<recipe>]}` to that capability's `detect` in `catalog.yml`.
3. Run `python -m cli.recipes --regen`.
4. Stage every file in the new `output/` and every changed generated document, and commit them with the recipe.

## Output structure

```
docs/recipes/doors/shaker_door/
├── README.md
├── shaker_door.pml.yml
└── output/
    ├── shaker_door.svg                     # Blueprint
    ├── pocket-12.70mm.nc                   # G-code per operation and tool
    ├── profile-3.17mm.nc
    ├── machining_summary.json              # Per-file tools, feeds, depths, runtime
    └── metrics.json                        # Complexity, fidelity, errors, warnings
```

A recipe with a back face also writes `<name>.back.svg`. A multi-sheet recipe prefixes each G-code file with `sheet_N.`, writes one SVG per sheet, and adds `manifest.json`. A recipe with several PML sources names each source's outputs after `Path(source).stem` (`a.pml.svg`, `a.pml.profile-3.17mm.nc`) and writes one `metrics.json`, `machining_summary.json` and `manifest.json` for all of them.

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
  "build": {"kerf_mm": 3.175, "theme": "dark", "y_origin": "back", "source": "shaker_door.pml.yml"}
}
```

`errors` lists design errors; a non-empty list makes `cli.mill` exit 3. Pipeline timing is stripped before the file is written. Recipe outputs carry no commit hash: the commit that holds them is their provenance. `--project` and `--input` runs add `"provenance": {"mill_ui": "<short hash>"}`.

A run with more than one sheet (a multi-sheet layout, or several input files) writes one `metrics.json` with a `sheets` list. Each entry holds that sheet's metrics, `errors` and `warnings`, plus `source`, `sheet_index` and `job_name`. The top-level `errors` and `warnings` collect every sheet's messages, prefixed `sheet N: ` (or `<source> sheet N: ` when the run has several input files):

```json
{
  "total_sheets": 3,
  "sheets": [{"source": "bookcase.pml.yml", "sheet_index": 1, "job_name": "bookcase_sheet_1", "...": "...", "errors": [], "warnings": []}],
  "errors": [],
  "warnings": [],
  "build": {...}
}
```

`cam.pipeline.write_run_outputs` is the single writer for `.nc`, `.svg`, `metrics.json`, `machining_summary.json` and `manifest.json` (runs with more than one sheet); `cli.mill --recipe` and `cli.recipes --regen` both reach it through `cli.mill.write_recipe_outputs`, so either one refreshes a recipe's outputs. A run with several input files prefixes each `.nc` with its input stem (`door.pml.profile-6.35mm.nc`). The writer raises `GcodeNameCollisionError` if two G-code files would share a name.

