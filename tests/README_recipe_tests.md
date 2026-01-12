# Recipe Output Tests

Recipe output tests automatically verify that recipe PML files generate expected G-code output. This provides:

- **Regression detection**: Immediately see if code changes affect output
- **Performance tracking**: Monitor generation time and complexity metrics
- **Integration testing**: Full pipeline validation from PML → G-code

## Usage

### Running Tests

**With pytest (recommended):**
```bash
# Verify all recipes match recipe outputs
pytest tests/test_recipes.py

# Verify specific recipe
pytest tests/test_recipes.py::test_recipe_output[shaker_corner_cleanup.pml]

# Regenerate all recipe outputs
pytest tests/test_recipes.py --regen_recipes
```

**Standalone mode (no pytest required):**
```bash
# Regenerate all recipe outputs
python3 tests/test_recipes.py
```

### Adding New Recipes

Recipe output tests automatically discover all `.pml` files in `docs/recipes/*/`:

1. Create your recipe PML file:
   ```
   docs/recipes/15_my_recipe/
   ├── README.md
   └── example.pml
   ```

2. Generate initial recipe outputs:
   ```bash
   pytest tests/test_recipes.py --regen_recipes
   # or
   python3 tests/test_recipes.py
   ```

3. Commit the artifacts:
   ```bash
   git add docs/recipes/15_my_recipe/output/
   git commit -m "Add recipe outputs for recipe 15"
   ```

The test will now automatically include your recipe.

## Output Structure

For each recipe, the test generates:

```
docs/recipes/14_corner_cleanup_multi_tool/
├── shaker_corner_cleanup.pml       # Source
└── output/                          # Generated (committed)
    ├── pocket-9.53mm.nc             # G-code per tool
    ├── corner_cleanup-3.17mm.nc
    ├── profile-3.17mm.nc
    └── metrics.json                 # Performance/quality metrics
```

### Metrics Schema

`metrics.json` tracks:

```json
{
  "timing": {
    "parse_ms": 0.32,      // PML parsing time
    "ir_ms": 0.02,          // RemovalIntent IR generation
    "hints_ms": 0.01,       // Planner hints generation
    "plan_ms": 3.67,        // CAM planning time
    "gcode_ms": 8.05,       // G-code generation
    "total_ms": 12.06       // End-to-end time
  },
  "complexity": {
    "total_moves": 3366,    // Total move count
    "rapid_moves": 0,       // Rapids (positioning)
    "cut_moves": 3366,      // Cuts (material removal)
    "rapid_ratio": 0.0      // Efficiency metric
  },
  "fidelity": {
    "tool_changes": 3,      // Number of tools required
    "passes": [             // Per-pass breakdown
      {
        "name": "pocket",
        "tool_diameter_mm": 9.525,
        "move_count": 1314
      }
    ]
  },
  "output_size": {
    "total_bytes": 75532,   // Total G-code size
    "total_lines": 3368,    // Total line count
    "files": {              // Per-file breakdown
      "pocket-9.53mm": {
        "bytes": 23734,
        "lines": 1320
      }
    }
  }
}
```

## Workflow Examples

### After Making Planner Changes

```bash
# Run tests to see if output changed
pytest tests/test_recipes.py

# If changes are expected/correct, regenerate
pytest tests/test_recipes.py --regen_recipes

# Review the diff
git diff docs/recipes/*/output/

# Commit if good
git add docs/recipes/*/output/
git commit -m "Update recipe outputs after planner optimization"
```

### Detecting Performance Regressions

```bash
# Before your changes
pytest tests/test_recipes.py --regen_recipes
git add docs/recipes/*/output/metrics.json
git commit -m "Baseline metrics before optimization"

# After your changes
pytest tests/test_recipes.py --regen_recipes

# Compare metrics
git diff docs/recipes/*/output/metrics.json
```

Look for changes in:
- `total_ms`: Overall performance
- `plan_ms`: Planner efficiency
- `total_moves`: Output complexity
- `rapid_ratio`: Toolpath efficiency

### Checking Algorithm Improvements

After optimizing the planner, check if output improved:

```bash
pytest tests/test_recipes.py --regen_recipes
git diff docs/recipes/*/output/
```

Look for:
- Fewer moves (better efficiency)
- Shorter G-code files (simpler paths)
- Lower `total_ms` (faster generation)
- Higher `rapid_ratio` (more efficient rapids)

## Design Philosophy

**PML as source of truth**: Recipes are PML files, not Python scripts. This matches how users interact with the system.

**Committed artifacts**: G-code outputs are committed for:
- Zero-friction review (view on GitHub)
- Historical record (see evolution over time)
- Fast testing (no generation required for verification)

**Comprehensive metrics**: Track time/complexity/fidelity to detect both improvements and regressions.

**Auto-discovery**: No manual registration - just add a `.pml` file and it's included.

## Troubleshooting

**Test fails with "Missing expected file":**
- You need to generate initial recipe outputs: `pytest --regen_recipes`

**Test fails with "differs: N lines changed":**
- Your code changed the output. Review with `git diff docs/recipes/*/output/`
- If expected: `pytest --regen_recipes` to accept changes
- If unexpected: investigate why output changed

**"No module named pytest":**
- Use standalone mode: `python3 tests/test_recipes.py`
- Or install pytest: `pip install pytest`

**Recipe not discovered:**
- Ensure `.pml` file is in `docs/recipes/*/` (subdirectory required)
- Check `python3 -c "from tests.test_recipe_outputs import discover_recipe_pml_files; print(discover_recipe_pml_files())"`
