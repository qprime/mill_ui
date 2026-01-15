# mill_ui Recipes

Practical examples showing complete workflows from design to G-code.

## Recipe Index

### Basic Workflows
- [01_simple_profile.md](01_simple_profile.md) - Cut a simple rectangle outline
  - Reference outputs: [SVG](01_simple_profile/simple_profile.blueprint.light.svg) | [STL](01_simple_profile/simple_profile.stl) | [G-code](01_simple_profile/simple_profile.nc)
- [02_pocket_with_cleanup.md](02_pocket_with_cleanup.md) - Pocket with finish pass (F001 feature)
  - Reference outputs: [SVG](02_pocket_with_cleanup/pocket_with_cleanup.blueprint.light.svg) | [STL](02_pocket_with_cleanup/pocket_with_cleanup.stl) | [G-code](02_pocket_with_cleanup/pocket_with_cleanup.nc)
- [03_shaker_door_template.md](03_shaker_door_template.md) - Using the Shaker template
  - Reference outputs: [SVG](03_shaker_door_template/shaker_door.blueprint.light.svg) | [STL](03_shaker_door_template/shaker_door.stl) | [G-code](03_shaker_door_template/shaker_door.nc)

### Advanced Patterns
- [04_custom_template.md](04_custom_template.md) - Creating your own template class (Python)
- [05_validation_workflow.md](05_validation_workflow.md) - Validating designs at IR level (fast feedback)
- [06_multiple_depths.md](06_multiple_depths.md) - Profile + pocket + holes in one part

### Integration Examples
- [07_json_generation.md](07_json_generation.md) - Generating `LayoutAST` from JSON (AI-friendly)
- [08_svg_visualization.md](08_svg_visualization.md) - Debugging with blueprint SVG export
- [09_config_tuning.md](09_config_tuning.md) - Tuning planner config (safe Z, pocket finish, tolerances)

### Layout Recipes
- [10_hole_patterns_grid.md](10_hole_patterns_grid.md) - Hole arrays with compositional `grid`
- [11_keepout_islands.md](11_keepout_islands.md) - Pockets with keepout islands (IR semantics)
- [12_edge_treatment_intent.md](12_edge_treatment_intent.md) - Edge intent annotations (allowance/fillet/chamfer)
- [13_split_layout_french_door.md](13_split_layout_french_door.md) - Paned doors with `split` (rails/mullions)

### CNC Workflow Recipes
- [14_corner_cleanup_multi_tool.md](14_corner_cleanup_multi_tool.md) - Multi-tool corner cleanup for rectangular pockets
- [15_profile_with_tabs.md](15_profile_with_tabs.md) - Holding tabs for profile cuts (prevents part movement)

### Sheet Nesting Recipes
- [16_sheet_layout_nesting/](16_sheet_layout_nesting/) - Basic sheet nesting concepts
- [17_nesting_guillotine/](17_nesting_guillotine/) - Guillotine bin-packing algorithm (fast, simple)
- [18_nesting_maxrects/](18_nesting_maxrects/) - MaxRects bin-packing algorithm (better utilization)

## Reference Outputs

Many recipes include complete reference outputs in their `output/` subdirectories:
- **SVG Blueprint**: 2D visualization with dimensions and feature annotations
- **STL Model**: 3D mesh for visual validation (open in FreeCAD, MeshLab, or online viewers)
- **G-code**: Machine-ready toolpath (verify in CAMotics or similar simulators)
- **metrics.json**: Performance metrics (timing, complexity, tool usage)

These outputs are automatically generated and serve as:
- Expected results for recipe verification
- Visual examples for documentation
- Test fixtures for regression testing

To regenerate all outputs:
```bash
# Standalone mode (regenerates all recipes)
PYTHONPATH=. python3 tests/test_recipes.py

# Or via pytest
pytest tests/test_recipes.py --regen_recipes
```

## Recipe Format

Each recipe includes:
- **Goal**: What you're trying to accomplish
- **Input**: PML/JSON/Python code
- **Process**: Step-by-step commands
- **Output**: Expected results and verification steps (with links to reference outputs)
- **Variations**: Common modifications to the pattern

## For AI Agents

These recipes demonstrate:
- Complete input → output workflows
- Error handling and validation
- Common patterns and idioms
- Configuration options and their effects

Use these as reference implementations when helping users with similar tasks.
