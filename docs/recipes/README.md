# mill_ui Recipes

Practical examples showing complete workflows from design to G-code.

## Recipe Index

### Basic Workflows
- [01_simple_profile.md](01_simple_profile.md) - Cut a simple rectangle outline
- [02_pocket_with_cleanup.md](02_pocket_with_cleanup.md) - Pocket with finish pass (F001 feature)
- [03_shaker_door_template.md](03_shaker_door_template.md) - Using the Shaker template

### Advanced Patterns
- [04_custom_template.md](04_custom_template.md) - Creating your own parametric template
- [05_validation_workflow.md](05_validation_workflow.md) - Validating designs at IR level
- [06_multiple_depths.md](06_multiple_depths.md) - Features at different depths

### Integration Examples
- [07_json_generation.md](07_json_generation.md) - Generating LayoutAST from JSON (AI-friendly)
- [08_svg_visualization.md](08_svg_visualization.md) - Debugging with SVG export
- [09_config_tuning.md](09_config_tuning.md) - Tuning feeds, speeds, and finish quality

## Recipe Format

Each recipe includes:
- **Goal**: What you're trying to accomplish
- **Input**: PML/JSON/Python code
- **Process**: Step-by-step commands
- **Output**: Expected results and verification steps
- **Variations**: Common modifications to the pattern

## For AI Agents

These recipes demonstrate:
- Complete input → output workflows
- Error handling and validation
- Common patterns and idioms
- Configuration options and their effects

Use these as reference implementations when helping users with similar tasks.
