# Recipe 28: Diamond Lattice Panel

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** Rotated geometry generation, diagonal line buffering

## Overview

This recipe creates a 400x400mm panel with a diamond lattice pattern. It
buffers 45-degree and -45-degree lines at 25mm spacing into 4mm wide
pocket grooves.

## Output

Running the example writes these files to `output/`:
- `ast.json`
- `intents.json`
- `preview.svg`

## Run

```bash
PYTHONPATH=. python docs/recipes/28_diamond_lattice_panel/example.py
```
