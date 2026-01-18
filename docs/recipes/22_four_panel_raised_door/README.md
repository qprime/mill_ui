# Recipe 22: Four-Panel Raised Door

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** split_grid, raised_panel_generator, profile cut

## Overview

This recipe creates a 500x700mm door, insets a 65mm frame, then splits the
panel region into a 2x2 grid with 35mm rails. Each cell receives a raised
panel generator pass, and the outer door boundary is profiled through.

## Output

Running the example writes these files to `output/`:
- `ast.json`
- `intents.json`
- `preview.svg`

## Run

```bash
PYTHONPATH=. python docs/recipes/22_four_panel_raised_door/example.py
```
