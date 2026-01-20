# Recipes

Worked examples demonstrating mill_ui capabilities.

| # | Name | Folder |
|---|------|--------|
| 01 | Simple Profile Cut | `01_simple_profile/` |
| 02 | Pocket with Cleanup | `02_pocket_with_cleanup/` |
| 03 | Shaker Door Template | `03_shaker_door_template/` |
| 04 | Custom Template | `04_custom_template/` |
| 05 | Validation Workflow | `05_validation_workflow/` |
| 06 | Multiple Depths | `06_multiple_depths/` |
| 07 | JSON Generation | `07_json_generation/` |
| 08 | SVG Visualization | `08_svg_visualization/` |
| 09 | Config Tuning | `09_config_tuning/` |
| 10 | Hole Patterns (Grid) | `10_hole_patterns_grid/` |
| 11 | Keepout Islands | `11_keepout_islands/` |
| 12 | Edge Treatment Intent | `12_edge_treatment_intent/` |
| 13 | Split Layout (French Door) | `13_split_layout_french_door/` |
| 14 | Corner Cleanup (Multi-Tool) | `14_corner_cleanup_multi_tool/` |
| 15 | Profile with Tabs | `15_profile_with_tabs/` |
| 16 | Sheet Layout Nesting | `16_sheet_layout_nesting/` |
| 17 | Nesting (Guillotine) | `17_nesting_guillotine/` |
| 18 | Nesting (MaxRects) | `18_nesting_maxrects/` |
| 19 | Domain/Generator Basics | `19_domain_generator_basics/` |
| 20 | Multi-Panel Doors | `20_multi_panel_doors/` |
| 21 | Simple Shaker Door | `21_simple_shaker_door/` |
| 22 | Four-Panel Raised Door | `22_four_panel_raised_door/` |
| 23 | Chamfered Cabinet Panel | `23_chamfered_cabinet_panel/` |
| 24 | Shelf Dados Side Panel | `24_shelf_dados_side/` |
| 25 | Decorative Border Panel | `25_decorative_border_panel/` |
| 26 | Faux Shutter Panel | `26_faux_shutter_panel/` |
| 27 | Wave Texture Panel | `27_wave_texture_panel/` |
| 28 | Diamond Lattice Panel | `28_diamond_lattice_panel/` |
| 29 | Picture Frame Panel | `29_picture_frame_panel/` |
| 30 | Cathedral Arch Door | `30_cathedral_arch_door/` |
| 31 | X-Panel Door | `31_x_panel_door/` |

## Structure

Each recipe folder contains:
- `README.md` — Description and key concepts
- `example.pml` or `input.pml` — PML source
- `output/` — Generated artifacts (SVG, STL, G-code)

## Usage

```bash
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
```

## MCP Access

```
get_docs(name="README", section="docs/recipes")           # This index
get_docs(name="README", section="docs/recipes/21_simple_shaker_door")  # Specific recipe
```
